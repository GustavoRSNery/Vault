"""Caso de uso: exportar a trilha e ancorar o que foi exportado.

É o que fecha o buraco que a própria tela de integridade denuncia. Sem esta
exportação, `verify_chain` confere a lista contra ela mesma e aprova qualquer
cadeia internamente coerente — inclusive uma recosturada por inteiro.

O fluxo é deliberadamente nesta ordem:

    1. lê os eventos ainda não exportados
    2. envia ao destino externo
    3. SÓ ENTÃO grava a âncora local

Inverter 2 e 3 criaria âncora para evento que nunca saiu: a verificação
passaria a cobrar um registro externo inexistente e acusaria fraude onde houve
falha de rede. Melhor exportar duas vezes (o destino é somente-anexação, e
duplicata lá é ruído) do que ancorar o que não foi.

A exportação **converge**: ela registra a si mesma na trilha apenas quando
exportou algo além do próprio rastro. Sem isso, cada rodada geraria o evento
que a rodada seguinte teria de exportar, e uma exportação agendada encheria a
trilha sozinha num sistema sem nenhuma atividade.

A âncora é gravada na ÚLTIMA sequência do lote, não em todas. Uma âncora fixa
o hash de um evento, e o encadeamento faz o resto: se o evento N confere, todo
o trecho até ele confere, porque alterar qualquer antecessor mudaria o hash de
N. Ancorar todos seria custo sem ganho.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ...domain.audit.events import AuditAction, AuditEvent, ChainAnchor
from ..ports.siem import SiemExporter


@dataclass(frozen=True, slots=True)
class ExportResult:
    """O que a exportação fez, em termos que a tela e o log entendem."""

    exportados: int
    ancora_sequencia: int | None
    ancora_hash: str | None
    destino: str
    destino_inviolavel: bool
    # Quantos dos exportados NÃO eram o registro de uma exportação anterior.
    # Ver `vale_registrar`.
    exportados_relevantes: int = 0

    @property
    def houve_trabalho(self) -> bool:
        return self.exportados > 0

    @property
    def vale_registrar(self) -> bool:
        """A exportação merece virar evento da trilha?

        Registrar toda exportação faz o processo se auto-alimentar: o evento
        gerado agora vira pendência da próxima rodada, que gera outro evento,
        para sempre. Uma exportação agendada a cada 5 minutos encheria a
        trilha sozinha num sistema ocioso.

        Então só registra quando exportou algo que não era o próprio rastro
        de exportar — aí o ciclo fecha e a trilha para de crescer sozinha.
        """
        return self.exportados_relevantes > 0


class ExportChain:
    def __init__(self, audit, exporter: SiemExporter) -> None:
        self._audit = audit
        self._exporter = exporter

    def execute(self) -> ExportResult:
        eventos = self._audit.list_chain()
        ja_ancorado = self._ultima_sequencia_ancorada()

        # Só o que ainda não saiu. A retomada é por sequência, não por data:
        # relógio pode voltar, sequência não.
        pendentes = [e for e in eventos if e.sequence > ja_ancorado]

        if not pendentes:
            return ExportResult(
                exportados=0,
                ancora_sequencia=None,
                ancora_hash=None,
                destino=self._exporter.nome,
                destino_inviolavel=self._exporter.inviolavel,
            )

        linhas = [_para_linha(e) for e in pendentes]
        self._exporter.append(linhas)

        relevantes = sum(
            1 for e in pendentes if e.action is not AuditAction.AUDIT_EXPORTED
        )

        # Depois do envio bem-sucedido, e não antes.
        ultimo = pendentes[-1]
        ancora = ChainAnchor(
            sequence=ultimo.sequence, fingerprint=ultimo.fingerprint()
        )
        self._audit.add_anchor(ancora, self._exporter.nome)

        return ExportResult(
            exportados=len(pendentes),
            ancora_sequencia=ancora.sequence,
            ancora_hash=ancora.fingerprint,
            destino=self._exporter.nome,
            destino_inviolavel=self._exporter.inviolavel,
            exportados_relevantes=relevantes,
        )

    def _ultima_sequencia_ancorada(self) -> int:
        """Até onde a trilha já foi exportada.

        -1 quando nunca houve exportação, para que o evento de sequência 0
        entre no primeiro lote — com 0 ele ficaria de fora para sempre.
        """
        ancoras = self._audit.anchors()
        return max((a.sequence for a in ancoras), default=-1)


def _para_linha(evento: AuditEvent) -> str:
    """Serializa um evento como uma linha JSON.

    O `fingerprint` vai junto: é o que o destino externo guarda e o que a
    verificação confronta depois. Sem ele, o registro externo seria uma cópia
    dos dados, não uma prova sobre eles.

    Nenhum valor de segredo passa por aqui — a trilha nunca os guardou, e
    `metadata` é explicitamente proibido de carregá-los.
    """
    return json.dumps(
        {
            "sequence": evento.sequence,
            "id": evento.id,
            "action": str(evento.action),
            "actor_id": evento.actor_id,
            "actor_label": evento.actor_label,
            "target_path": evento.target_path,
            "outcome": str(evento.outcome),
            "reason": evento.reason,
            "ip_address": evento.ip_address,
            "occurred_at": evento.occurred_at.isoformat(),
            "previous_hash": evento.previous_hash,
            "fingerprint": evento.fingerprint(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
