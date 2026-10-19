"""Rotas de auditoria.

A trilha é lida por mais gente do que os segredos, então a leitura tem regra
própria: só quem tem ADMIN no caminho de auditoria enxerga a trilha inteira.
Quem não tem vê apenas os próprios eventos — o suficiente para conferir o que
fez em seu nome, sem revelar a atividade dos colegas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...application.audit.export_chain import ExportChain
from ...application.ports.siem import SiemExporter
from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import AuditRepository, PolicyRepository
from ..deps import (
    CurrentUser,
    get_audit,
    get_current_user,
    get_db,
    get_policies,
    get_siem_exporter,
)

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])

CAMINHO_AUDITORIA = PolicyPath("auditoria")


class EventoResponse(BaseModel):
    id: str
    sequence: int
    action: str
    actor_label: str
    target_path: str
    outcome: str
    reason: str
    ip_address: str | None
    occurred_at: datetime


class TrilhaResponse(BaseModel):
    eventos: list[EventoResponse]
    total: int
    escopo: Literal["tudo", "proprios"]


class IntegridadeResponse(BaseModel):
    """Resultado da verificação da cadeia.

    `integra` sem âncoras significa apenas que ninguém adulterou sem recosturar
    os elos; `ancoras_conferidas` diz quanto dessa garantia é de fato forte.
    `eventos_ancorados` diz até onde a garantia forte alcança: eventos após a
    última âncora ainda dependem só do encadeamento.
    """

    integra: bool
    eventos_verificados: int
    ancoras_conferidas: int
    eventos_ancorados: int
    quebras: list[str]
    aviso: str | None


class ExportacaoResponse(BaseModel):
    """O que a exportação fez.

    `destino_inviolavel` é falso para o arquivo local de desenvolvimento: a
    tela não deve anunciar uma garantia que o ambiente não tem.
    """

    exportados: int
    ancora_sequencia: int | None
    destino: str
    destino_inviolavel: bool
    aviso: str | None


@router.get("", response_model=TrilhaResponse, summary="Listar eventos")
def listar_eventos(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    db: Annotated[Session, Depends(get_db)],
    limite: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> TrilhaResponse:
    from ...infrastructure.db.repositories import ConfiguracaoRepository

    efetivo = limite or ConfiguracaoRepository(db).atual().trilha_limite_padrao
    pode_ver_tudo = evaluate(
        policies.policies_for_user(current.id), CAMINHO_AUDITORIA, Capability.ADMIN
    )

    eventos = audit.list_chain()
    if not pode_ver_tudo:
        eventos = [e for e in eventos if e.actor_id == current.id]

    # Mais recentes primeiro: é o que se quer ver numa trilha.
    recentes = list(reversed(eventos))[:efetivo]

    return TrilhaResponse(
        eventos=[
            EventoResponse(
                id=e.id,
                sequence=e.sequence,
                action=str(e.action),
                actor_label=e.actor_label,
                target_path=e.target_path,
                outcome=str(e.outcome),
                reason=e.reason,
                ip_address=e.ip_address,
                occurred_at=e.occurred_at,
            )
            for e in recentes
        ],
        total=len(eventos),
        escopo="tudo" if pode_ver_tudo else "proprios",
    )


@router.get(
    "/integridade", response_model=IntegridadeResponse, summary="Verificar a cadeia"
)
def verificar_integridade(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
) -> IntegridadeResponse:
    """Varre a trilha inteira e confronta com as âncoras externas."""
    from ...domain.audit.events import verify_chain
    from ...domain.shared.errors import PermissionDeniedError

    if not evaluate(
        policies.policies_for_user(current.id), CAMINHO_AUDITORIA, Capability.ADMIN
    ):
        raise PermissionDeniedError("Apenas administradores verificam a trilha.")

    eventos = audit.list_chain()
    ancoras = audit.anchors()
    quebras = verify_chain(eventos, anchors=ancoras)

    # Sem âncora, "íntegra" quer dizer menos do que parece. Dizer isso na
    # própria resposta evita que a tela mostre um selo verde enganoso.
    ultima_ancorada = max((a.sequence for a in ancoras), default=-1)
    ancorados = sum(1 for e in eventos if e.sequence <= ultima_ancorada)
    pendentes = len(eventos) - ancorados

    aviso = None
    if not ancoras:
        aviso = (
            "Nenhuma âncora externa registrada: a verificação detecta alteração "
            "simples, mas não uma trilha reescrita por inteiro. Exporte a trilha "
            "para criar a primeira âncora."
        )
    elif pendentes:
        # Honestidade sobre o alcance: a garantia forte cobre o que foi
        # ancorado, e o resto ainda depende só do encadeamento.
        aviso = (
            f"{pendentes} evento(s) após a última âncora ainda não foram "
            "exportados: nesse trecho a verificação detecta alteração simples, "
            "mas não uma reescrita completa."
        )

    return IntegridadeResponse(
        integra=not quebras,
        eventos_verificados=len(eventos),
        ancoras_conferidas=len(ancoras),
        eventos_ancorados=ancorados,
        quebras=[f"evento #{q.sequence}: {q.detail}" for q in quebras],
        aviso=aviso,
    )


@router.post(
    "/exportar", response_model=ExportacaoResponse, summary="Exportar e ancorar"
)
def exportar_trilha(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    exporter: Annotated[SiemExporter, Depends(get_siem_exporter)],
) -> ExportacaoResponse:
    """Envia os eventos ainda não exportados e ancora o último deles.

    É o que transforma a trilha de "detecta descuido" em "detecta fraude": sem
    um registro fora deste banco, uma cadeia recosturada por inteiro passa na
    verificação. Exigir ADMIN porque a exportação revela a trilha inteira ao
    destino configurado.
    """
    from ...domain.shared.errors import PermissionDeniedError

    if not evaluate(
        policies.policies_for_user(current.id), CAMINHO_AUDITORIA, Capability.ADMIN
    ):
        raise PermissionDeniedError("Apenas administradores exportam a trilha.")

    resultado = ExportChain(audit, exporter).execute()

    # A própria exportação é um evento — e entra DEPOIS do lote, então fica
    # para a próxima âncora. Registrar antes criaria um evento que a âncora
    # recém-criada não cobre, o que confunde a leitura da trilha.
    #
    # `vale_registrar` e não `houve_trabalho`: registrar toda exportação faria
    # o processo se auto-alimentar, e um agendamento encheria a trilha sozinho.
    if resultado.vale_registrar:
        audit.append(
            AuditEvent(
                action=AuditAction.AUDIT_EXPORTED,
                actor_id=current.id,
                actor_label=current.email,
                target_path=str(CAMINHO_AUDITORIA),
                outcome=AuditOutcome.SUCCESS,
                reason=(
                    f"{resultado.exportados} evento(s) para {resultado.destino}; "
                    f"âncora na sequência {resultado.ancora_sequencia}."
                ),
                ip_address=current.ip_address,
                user_agent=current.user_agent,
            )
        )

    aviso = None
    if not resultado.destino_inviolavel:
        aviso = (
            f"O destino '{resultado.destino}' não é inviolável pela aplicação: "
            "quem tem acesso a ele pode reescrevê-lo, e então a âncora deixa de "
            "provar. Em produção, use um destino somente-anexação."
        )

    return ExportacaoResponse(
        exportados=resultado.exportados,
        ancora_sequencia=resultado.ancora_sequencia,
        destino=resultado.destino,
        destino_inviolavel=resultado.destino_inviolavel,
        aviso=aviso,
    )
