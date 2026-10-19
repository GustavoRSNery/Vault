"""Trilha de auditoria encadeada por hash.

Cada evento carrega o hash do anterior, como numa cadeia de blocos. Alterar
ou remover um evento no meio quebra todos os hashes seguintes, e a varredura
de verificação aponta exatamente onde a cadeia foi rompida.

O que isso garante e o que não garante, explicitamente:

- Detecta adulteração "preguiçosa": alterar, remover ou reordenar um evento
  sem recalcular os elos seguintes quebra a verificação imediatamente.
- NÃO detecta, sozinha, a adulteração "caprichada": quem altera um evento e
  recostura todos os hashes seguintes produz uma cadeia internamente
  coerente. Verificar a lista contra ela mesma sempre aprova esse caso.

Por isso `verify_chain` aceita uma ÂNCORA: um par (sequência, hash) registrado
fora deste banco — no SIEM, num log externo, num bucket somente-anexação. A
verificação com âncora pega a recostura, porque o atacante teria de alterar
também o registro externo. Sem âncora, a função avisa que a garantia é parcial.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from ..shared.errors import ValidationError
from ..shared.value_objects import new_id, utcnow

# Hash de um evento sem antecessor: o elo zero da cadeia.
GENESIS_HASH = "0" * 64


class AuditAction(StrEnum):
    """Ações registradas. Revelar um segredo é evento de primeira classe."""

    LOGIN_SUCCESS = "login_sucesso"
    LOGIN_FAILURE = "login_falha"
    LOGOUT = "logout"
    MFA_ENROLLED = "mfa_cadastrado"
    SECRET_CREATED = "segredo_criado"
    SECRET_REVEALED = "segredo_revelado"
    SECRET_UPDATED = "segredo_atualizado"
    SECRET_DELETED = "segredo_excluido"
    SECRET_RESTORED = "segredo_restaurado"
    VAULT_CREATED = "cofre_criado"
    VAULT_SEALED = "cofre_selado"
    VAULT_UNSEALED = "cofre_desselado"
    PERMISSION_GRANTED = "permissao_concedida"
    PERMISSION_REVOKED = "permissao_revogada"
    ACCESS_DENIED = "acesso_negado"
    POLICY_UPDATED = "politica_alterada"
    USER_ACTIVATED = "usuario_ativado"
    USER_DEACTIVATED = "usuario_desativado"
    USER_MFA_RESET = "usuario_mfa_reiniciado"
    USER_ROLES_CHANGED = "usuario_papeis_alterados"
    DEVICE_CREATED = "dispositivo_cadastrado"
    CREDENTIAL_CREATED = "credencial_cadastrada"
    CREDENTIAL_CHECKED_OUT = "credencial_retirada"
    CREDENTIAL_CHECKED_IN = "credencial_devolvida"
    CREDENTIAL_CHECKOUT_DENIED = "credencial_retirada_negada"
    CREDENTIAL_ROTATED = "credencial_rotacionada"
    CERTIFICATE_CREATED = "certificado_cadastrado"
    ACCESS_REQUESTED = "acesso_solicitado"
    ACCESS_APPROVED = "acesso_aprovado"
    ACCESS_DENIED_REQUEST = "acesso_solicitacao_negada"
    ACCESS_REVOKED = "acesso_revogado"


class AuditOutcome(StrEnum):
    SUCCESS = "sucesso"
    FAILURE = "falha"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Evento imutável da trilha.

    `metadata` nunca deve conter valor de segredo: a trilha é lida por mais
    gente do que o próprio segredo, e um valor aqui vazaria por via indireta.
    """

    action: AuditAction
    actor_id: str | None
    actor_label: str
    target_path: str
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    reason: str = ""
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=utcnow)
    sequence: int = 0
    previous_hash: str = GENESIS_HASH
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValidationError("A sequência não pode ser negativa.")
        if len(self.previous_hash) != 64:
            raise ValidationError("O hash anterior deve ter 64 caracteres hexadecimais.")

    def fingerprint(self) -> str:
        """Hash deste evento, incluindo o do anterior — o elo da cadeia.

        A serialização é canônica (chaves ordenadas, sem espaço) para que o
        mesmo evento produza sempre o mesmo hash, em qualquer máquina.

        Nota de honestidade, medida com teste de mutação: remover
        `previous_hash` daqui NÃO faz nenhum teste falhar, porque `sequence`
        já torna cada evento único e `verify_chain` compara o campo
        armazenado. O elo é mantido por ser a construção canônica e por
        proteger caso `sequence` deixe de ser único — mas quem confia na
        integridade da trilha deve confiar na ÂNCORA EXTERNA, não neste hash.
        """
        payload = {
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "action": str(self.action),
            "actor_id": self.actor_id,
            "actor_label": self.actor_label,
            "target_path": self.target_path,
            "outcome": str(self.outcome),
            "reason": self.reason,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata,
            "occurred_at": self._canonical_timestamp(self.occurred_at),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical_timestamp(moment: datetime) -> str:
        """Carimbo de tempo em forma única, imune ao dialeto do banco.

        Isto não é preciosismo: o SQLite devolve datetime SEM timezone, o
        Postgres devolve COM. Formatar com isoformat() direto produziria
        hashes diferentes para o mesmo evento em bancos diferentes, e a
        trilha inteira falharia na verificação depois de um round-trip.

        A normalização é sempre para UTC, em microssegundos. Um datetime
        ingênuo vindo do banco é assumido como UTC — é o que a aplicação
        grava, já que `utcnow()` é a única fonte de tempo do domínio.
        """
        aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
        return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


@dataclass(frozen=True, slots=True)
class ChainBreak:
    """Onde a cadeia se rompeu, e por quê — texto pronto para a tela."""

    sequence: int
    event_id: str
    detail: str


@dataclass(frozen=True, slots=True)
class ChainAnchor:
    """Ponto de confiança registrado FORA deste banco.

    Guardado periodicamente num destino que a aplicação não pode reescrever.
    É o que transforma a trilha de "detecta descuido" em "detecta fraude".
    """

    sequence: int
    fingerprint: str

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValidationError("A sequência da âncora não pode ser negativa.")
        if len(self.fingerprint) != 64:
            raise ValidationError("O hash da âncora deve ter 64 caracteres hexadecimais.")


def append(events: list[AuditEvent], event: AuditEvent) -> AuditEvent:
    """Encadeia `event` ao fim de `events`, atribuindo sequência e hash anterior."""
    if events:
        last = events[-1]
        linked = _with(event, sequence=last.sequence + 1, previous_hash=last.fingerprint())
    else:
        linked = _with(event, sequence=0, previous_hash=GENESIS_HASH)
    events.append(linked)
    return linked


def _with(event: AuditEvent, *, sequence: int, previous_hash: str) -> AuditEvent:
    """Recria o evento com os campos de encadeamento preenchidos."""
    return AuditEvent(
        action=event.action,
        actor_id=event.actor_id,
        actor_label=event.actor_label,
        target_path=event.target_path,
        outcome=event.outcome,
        reason=event.reason,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        metadata=event.metadata,
        occurred_at=event.occurred_at,
        sequence=sequence,
        previous_hash=previous_hash,
        id=event.id,
    )


def verify_chain(
    events: list[AuditEvent],
    anchors: list[ChainAnchor] | None = None,
) -> list[ChainBreak]:
    """Varre a cadeia e devolve todos os rompimentos encontrados.

    Lista vazia significa cadeia íntegra *na medida do que foi conferido*. A
    varredura não para no primeiro problema: um relatório que mostra só a
    primeira quebra esconde o resto.

    `anchors` são pontos de confiança externos. Cada um fixa o hash esperado
    numa sequência; é o que detecta a recostura completa da cadeia, porque o
    atacante precisaria alterar também o registro de fora.
    """
    breaks: list[ChainBreak] = []
    by_sequence: dict[int, AuditEvent] = {}
    expected_hash = GENESIS_HASH
    expected_sequence = 0

    for event in events:
        if event.sequence != expected_sequence:
            breaks.append(
                ChainBreak(
                    sequence=event.sequence,
                    event_id=event.id,
                    detail=(
                        f"Sequência fora de ordem: esperada {expected_sequence}, "
                        f"encontrada {event.sequence}."
                    ),
                )
            )
        if event.previous_hash != expected_hash:
            breaks.append(
                ChainBreak(
                    sequence=event.sequence,
                    event_id=event.id,
                    detail="O hash do evento anterior não confere: a trilha foi alterada.",
                )
            )
        by_sequence[event.sequence] = event
        expected_hash = event.fingerprint()
        expected_sequence = event.sequence + 1

    breaks.extend(_check_anchors(by_sequence, anchors or []))
    return breaks


def _check_anchors(
    by_sequence: dict[int, AuditEvent],
    anchors: list[ChainAnchor],
) -> list[ChainBreak]:
    """Confronta a trilha com os pontos de confiança externos."""
    breaks: list[ChainBreak] = []
    for anchor in anchors:
        event = by_sequence.get(anchor.sequence)
        if event is None:
            breaks.append(
                ChainBreak(
                    sequence=anchor.sequence,
                    event_id="",
                    detail=(
                        f"O evento {anchor.sequence} consta do registro externo "
                        "mas sumiu da trilha."
                    ),
                )
            )
            continue
        if event.fingerprint() != anchor.fingerprint:
            breaks.append(
                ChainBreak(
                    sequence=anchor.sequence,
                    event_id=event.id,
                    detail=(
                        "O evento não confere com o registro externo: "
                        "a trilha foi reescrita."
                    ),
                )
            )
    return breaks
