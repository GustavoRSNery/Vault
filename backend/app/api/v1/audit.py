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
from pydantic import BaseModel

from ...domain.access.policy import Capability, evaluate
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import AuditRepository, PolicyRepository
from ..deps import CurrentUser, get_audit, get_current_user, get_policies

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
    """

    integra: bool
    eventos_verificados: int
    ancoras_conferidas: int
    quebras: list[str]
    aviso: str | None


@router.get("", response_model=TrilhaResponse, summary="Listar eventos")
def listar_eventos(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
) -> TrilhaResponse:
    pode_ver_tudo = evaluate(
        policies.policies_for_user(current.id), CAMINHO_AUDITORIA, Capability.ADMIN
    )

    eventos = audit.list_chain()
    if not pode_ver_tudo:
        eventos = [e for e in eventos if e.actor_id == current.id]

    # Mais recentes primeiro: é o que se quer ver numa trilha.
    recentes = list(reversed(eventos))[:limite]

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
    aviso = None
    if not ancoras:
        aviso = (
            "Nenhuma âncora externa registrada: a verificação detecta alteração "
            "simples, mas não uma trilha reescrita por inteiro."
        )

    return IntegridadeResponse(
        integra=not quebras,
        eventos_verificados=len(eventos),
        ancoras_conferidas=len(ancoras),
        quebras=[f"evento #{q.sequence}: {q.detail}" for q in quebras],
        aviso=aviso,
    )
