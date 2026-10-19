"""Solicitações de acesso e concessões temporárias.

Resolve o caso que o RBAC puro não resolve bem: alguém precisa de um acesso
que não deveria ter *para sempre*. A saída ruim é dar permissão permanente e
esquecer — foi assim que o estagiário de 2023 continua com acesso à produção.

Três invariantes moram aqui:

1. **Quem pede não aprova.** Nem com permissão de aprovador: auto-aprovação
   transforma o fluxo em formalidade.
2. **Decisão é terminal.** Aprovada ou negada, a solicitação não volta a ser
   pendente; pedir de novo é outra solicitação, com outro registro.
3. **Concessão nasce com prazo.** Não existe acesso temporário sem fim — é a
   diferença entre esta entidade e simplesmente editar a política.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from ..access.policy import Capability, Effect, Policy, evaluate
from ..shared.errors import ConflictError, ValidationError
from ..shared.value_objects import PolicyPath, new_id, utcnow


class RequestStatus(StrEnum):
    PENDING = "pendente"
    APPROVED = "aprovada"
    DENIED = "negada"
    EXPIRED = "expirada"
    REVOKED = "revogada"


# Teto do acesso temporário. Mais do que isto não é temporário: é permissão
# permanente disfarçada, e deve passar por edição de política, que é revisada.
HORAS_MAXIMAS = 720  # 30 dias


@dataclass(slots=True)
class AccessRequest:
    """Pedido de acesso a um caminho, por uma janela de tempo.

    O acesso concedido não é gravado na política: vive aqui, com prazo, e a
    avaliação o soma às políticas no momento da decisão. Assim ele caduca
    sozinho — ninguém precisa lembrar de remover.
    """

    requester_id: str
    requester_label: str
    path: PolicyPath
    capabilities: frozenset[Capability]
    reason: str
    hours: int = 4
    status: RequestStatus = RequestStatus.PENDING
    decided_by_id: str | None = None
    decided_by_label: str = ""
    decision_note: str = ""
    decided_at: datetime | None = None
    granted_until: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValidationError("A solicitação precisa de uma justificativa.")
        if not self.capabilities:
            raise ValidationError("Escolha ao menos uma capacidade.")
        if self.hours < 1:
            raise ValidationError("A janela deve ser de ao menos uma hora.")
        if self.hours > HORAS_MAXIMAS:
            raise ValidationError(
                "Acesso temporário vai até 30 dias. Além disso, altere a "
                "política — que é revisada — em vez de renovar concessões."
            )

    @property
    def is_pending(self) -> bool:
        return self.status is RequestStatus.PENDING

    def is_active(self, now: datetime | None = None) -> bool:
        """A concessão está valendo neste instante?

        Vale para a avaliação de acesso: aprovada, não revogada e dentro do
        prazo. Uma aprovada que venceu não concede mais nada.
        """
        if self.status is not RequestStatus.APPROVED:
            return False
        if self.granted_until is None:
            return False
        return (now or utcnow()) < self.granted_until

    def covers(self, path: PolicyPath, capability: Capability) -> bool:
        """Esta concessão alcança este caminho e esta capacidade?"""
        return capability in self.capabilities and self.path.matches(path)

    def _ensure_decidable(self, approver_id: str) -> None:
        if not self.is_pending:
            raise ConflictError(
                f"Esta solicitação já está {self.status}. "
                "Decisão não se refaz: peça de novo, que vira outro registro."
            )
        if approver_id == self.requester_id:
            raise ConflictError(
                "Você não pode decidir a própria solicitação. Peça a outra "
                "pessoa com permissão de aprovação."
            )

    def approve(
        self,
        approver_id: str,
        approver_label: str,
        note: str = "",
        now: datetime | None = None,
    ) -> None:
        """Aprova e abre a janela de acesso a partir de agora.

        O prazo conta da aprovação, não do pedido: uma solicitação parada dois
        dias na fila não deve nascer com metade da janela já gasta.
        """
        self._ensure_decidable(approver_id)
        agora = now or utcnow()
        self.status = RequestStatus.APPROVED
        self.decided_by_id = approver_id
        self.decided_by_label = approver_label
        self.decision_note = note
        self.decided_at = agora
        self.granted_until = agora + timedelta(hours=self.hours)

    def deny(
        self,
        approver_id: str,
        approver_label: str,
        note: str = "",
        now: datetime | None = None,
    ) -> None:
        self._ensure_decidable(approver_id)
        self.status = RequestStatus.DENIED
        self.decided_by_id = approver_id
        self.decided_by_label = approver_label
        self.decision_note = note
        self.decided_at = now or utcnow()
        self.granted_until = None

    def revoke(self, now: datetime | None = None) -> None:
        """Encerra uma concessão ativa antes do prazo.

        Fecha o acesso imediatamente sem apagar o que houve: o registro fica
        como revogado, e não como se nunca tivesse sido aprovado.
        """
        if self.status is not RequestStatus.APPROVED:
            raise ConflictError("Só uma solicitação aprovada pode ser revogada.")
        self.status = RequestStatus.REVOKED
        self.granted_until = now or utcnow()

    def hours_remaining(self, now: datetime | None = None) -> float | None:
        if not self.is_active(now):
            return None
        assert self.granted_until is not None
        restante = self.granted_until - (now or utcnow())
        return round(restante.total_seconds() / 3600, 1)


def grants_access(
    requests: list[AccessRequest],
    path: PolicyPath,
    capability: Capability,
    now: datetime | None = None,
) -> AccessRequest | None:
    """Devolve a concessão ativa que cobre este acesso, se houver.

    Deliberadamente **não** nega: concessão temporária só soma. A negação é
    das políticas, onde `deny` vence — senão uma aprovação de emergência
    furaria uma proibição explícita, que é o oposto do que se quer.
    """
    for pedido in requests:
        if pedido.is_active(now) and pedido.covers(path, capability):
            return pedido
    return None


def decide(
    policies: list[Policy],
    requests: list[AccessRequest],
    path: PolicyPath,
    capability: Capability,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Decisão final: políticas + concessões temporárias, nesta ordem.

    A ordem não é detalhe de implementação, é a regra de segurança:

        1. `deny` explícito nas políticas  -> NEGA, e nada reverte
        2. `allow` nas políticas           -> PERMITE
        3. concessão temporária ativa      -> PERMITE, com prazo
        4. nada                            -> NEGA (default deny)

    O passo 1 vem antes do 3 de propósito. Compor as duas fontes com um OR
    ingênuo deixaria uma aprovação de emergência furar uma proibição
    deliberada — o oposto do que "negação vence" existe para garantir. Quem
    precisa furar um `deny` altera a política, que é revisada.
    """
    for policy in policies:
        for rule in policy.rules:
            if rule.covers(path, capability) and rule.effect is Effect.DENY:
                return False, (
                    f"Negado pela política {policy.name} em {rule.path}. "
                    "Uma negação explícita não é contornada por concessão "
                    "temporária."
                )

    if evaluate(policies, path, capability):
        return True, "Permitido pelas políticas do usuário."

    concessao = grants_access(requests, path, capability, now)
    if concessao is not None:
        restante = concessao.hours_remaining(now)
        return True, (
            f"Permitido por concessão temporária aprovada por "
            f"{concessao.decided_by_label}; expira em {restante}h."
        )

    return False, "Nenhuma política ou concessão permite este acesso."
