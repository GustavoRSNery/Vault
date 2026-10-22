"""Rotas de solicitações de acesso.

O fluxo existe para o caso que o RBAC puro resolve mal: alguém precisa de um
acesso que não deveria ter para sempre. A alternativa ruim é conceder
permissão permanente e esquecer.

Duas regras do domínio aparecem aqui como respostas HTTP:

- quem pede não decide (409, mesmo tendo `APPROVE` na política);
- `deny` explícito não é contornado por concessão (a composição vive em
  `decide`, no domínio, e não é refeita nas rotas).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, evaluate
from ...domain.approvals.entities import AccessRequest, RequestStatus
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import DomainError, PermissionDeniedError
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import (
    AccessRequestRepository,
    AuditRepository,
    PolicyRepository,
)
from ..deps import CurrentUser, get_audit, get_current_user, get_db, get_policies

router = APIRouter(prefix="/solicitacoes", tags=["Aprovações"])


def get_requests(db: Annotated[Session, Depends(get_db)]) -> AccessRequestRepository:
    return AccessRequestRepository(db)


class SolicitacaoResponse(BaseModel):
    id: str
    requester_label: str
    path: str
    capabilities: list[str]
    reason: str
    hours: int
    status: str
    decided_by_label: str
    decision_note: str
    decided_at: datetime | None
    granted_until: datetime | None
    horas_restantes: float | None
    ativa: bool
    created_at: datetime


class CriarSolicitacaoRequest(BaseModel):
    path: str = Field(min_length=1, max_length=256)
    capabilities: list[Capability] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=1000)
    hours: int = Field(default=4, ge=1, le=720)


class DecisaoRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


def _evento(
    current: CurrentUser,
    action: AuditAction,
    target: str,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
    reason: str = "",
) -> AuditEvent:
    return AuditEvent(
        action=action,
        actor_id=current.id,
        actor_label=current.email,
        target_path=target,
        outcome=outcome,
        reason=reason,
        ip_address=current.ip_address,
        user_agent=current.user_agent,
    )


def _exigir_aprovador(
    current: CurrentUser,
    policies: PolicyRepository,
    audit: AuditRepository,
    db: Session,
    caminho: PolicyPath,
) -> None:
    """Aprovar exige `APPROVE` no caminho pedido, não um papel chamado chefe.

    A capacidade é avaliada sobre o caminho da solicitação: quem aprova acesso
    ao RH não aprova, por tabela, acesso à infraestrutura.
    """
    if evaluate(policies.policies_for_user(current.id), caminho, Capability.APPROVE):
        return
    audit.append(
        _evento(
            current,
            AuditAction.ACCESS_DENIED,
            str(caminho),
            AuditOutcome.FAILURE,
            "Sem permissão para aprovar solicitações neste caminho.",
        )
    )
    db.commit()
    raise PermissionDeniedError(
        "Você não tem permissão para decidir solicitações neste caminho."
    )


@router.get("", response_model=list[SolicitacaoResponse], summary="Minhas solicitações")
def minhas_solicitacoes(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
) -> list[SolicitacaoResponse]:
    return [_resposta(p) for p in requests.list_for_requester(current.id)]


@router.post(
    "",
    response_model=SolicitacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pedir acesso",
)
def criar_solicitacao(
    payload: CriarSolicitacaoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
) -> SolicitacaoResponse:
    """Qualquer pessoa autenticada pode pedir; pedir não é ter.

    Não há checagem de política aqui de propósito: negar o pedido de quem não
    tem acesso tornaria o fluxo inútil, já que é exatamente essa pessoa que
    precisa pedir.
    """
    pedido = AccessRequest(
        requester_id=current.id,
        requester_label=current.email,
        path=PolicyPath(payload.path),
        capabilities=frozenset(payload.capabilities),
        reason=payload.reason,
        hours=payload.hours,
    )
    requests.add(pedido)
    audit.append(
        _evento(
            current,
            AuditAction.ACCESS_REQUESTED,
            str(pedido.path),
            reason=f"{payload.hours}h para {', '.join(sorted(str(c) for c in pedido.capabilities))}. "
            f"Motivo: {payload.reason}",
        )
    )
    return _resposta(pedido)


@router.get(
    "/fila", response_model=list[SolicitacaoResponse], summary="Fila de aprovação"
)
def fila_de_aprovacao(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
) -> list[SolicitacaoResponse]:
    """Só as pendentes que este usuário pode decidir.

    O filtro é por caminho: a fila mostra o que cabe a quem olha, em vez de
    listar tudo e falhar na hora de decidir.
    """
    minhas = policies.policies_for_user(current.id)
    return [
        _resposta(p)
        for p in requests.list_pending()
        if evaluate(minhas, p.path, Capability.APPROVE)
        and p.requester_id != current.id
    ]


class AprovarEmLoteRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=500)


class ResultadoDoLote(BaseModel):
    """O que aconteceu com cada pedido do lote.

    Aprovar em lote é conveniência, não atalho: cada pedido passa pela mesma
    checagem de permissão e pela mesma regra de domínio que a aprovação
    individual. Um que falhe não derruba os outros, mas **aparece na
    resposta** — aprovar 20 e receber "ok" quando 3 falharam seria pior que
    não ter o botão.
    """

    id: str
    aprovada: bool
    erro: str = ""


class LoteResponse(BaseModel):
    aprovadas: int
    recusadas: int
    resultados: list[ResultadoDoLote]


@router.post(
    "/aprovar-em-lote", response_model=LoteResponse, summary="Aprovar várias"
)
def aprovar_em_lote(
    payload: AprovarEmLoteRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> LoteResponse:
    """Aprova vários pedidos, um a um, relatando cada resultado.

    Cada pedido gera o seu próprio evento de auditoria. Um evento único de
    "lote aprovado" esconderia *o que* foi concedido — e é justamente isso
    que uma auditoria vai querer revisar.

    Ids repetidos são processados uma vez só: a tela pode mandar duplicata
    sem que o pedido seja aprovado duas vezes.
    """
    resultados: list[ResultadoDoLote] = []
    vistos: set[str] = set()

    for request_id in payload.ids:
        if request_id in vistos:
            continue
        vistos.add(request_id)
        try:
            pedido = requests.get(request_id)
            _exigir_aprovador(current, policies, audit, db, pedido.path)
            pedido.approve(current.id, current.email, payload.note)
            requests.save(pedido)
            audit.append(
                _evento(
                    current,
                    AuditAction.ACCESS_APPROVED,
                    str(pedido.path),
                    reason=(
                        f"Concedido a {pedido.requester_label} por "
                        f"{pedido.hours}h. {payload.note}".strip()
                    ),
                )
            )
            resultados.append(ResultadoDoLote(id=request_id, aprovada=True))
        except DomainError as erro:
            # Segue para os próximos: um pedido já decidido, ou um que o
            # aprovador não alcança, não deve impedir a aprovação dos outros.
            resultados.append(
                ResultadoDoLote(id=request_id, aprovada=False, erro=erro.message)
            )

    return LoteResponse(
        aprovadas=sum(1 for r in resultados if r.aprovada),
        recusadas=sum(1 for r in resultados if not r.aprovada),
        resultados=resultados,
    )


@router.post(
    "/{request_id}/aprovar",
    response_model=SolicitacaoResponse,
    summary="Aprovar solicitação",
)
def aprovar(
    request_id: str,
    payload: DecisaoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> SolicitacaoResponse:
    pedido = requests.get(request_id)
    _exigir_aprovador(current, policies, audit, db, pedido.path)

    # `approve` recusa a auto-aprovação; a regra mora no domínio.
    pedido.approve(current.id, current.email, payload.note)
    salvo = requests.save(pedido)
    audit.append(
        _evento(
            current,
            AuditAction.ACCESS_APPROVED,
            str(pedido.path),
            reason=(
                f"Concedido a {pedido.requester_label} por {pedido.hours}h. "
                f"{payload.note}".strip()
            ),
        )
    )
    return _resposta(salvo)


@router.post(
    "/{request_id}/negar",
    response_model=SolicitacaoResponse,
    summary="Negar solicitação",
)
def negar(
    request_id: str,
    payload: DecisaoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> SolicitacaoResponse:
    pedido = requests.get(request_id)
    _exigir_aprovador(current, policies, audit, db, pedido.path)

    pedido.deny(current.id, current.email, payload.note)
    salvo = requests.save(pedido)
    audit.append(
        _evento(
            current,
            AuditAction.ACCESS_DENIED_REQUEST,
            str(pedido.path),
            reason=f"Negado a {pedido.requester_label}. {payload.note}".strip(),
        )
    )
    return _resposta(salvo)


@router.post(
    "/{request_id}/revogar",
    response_model=SolicitacaoResponse,
    summary="Revogar concessão",
)
def revogar(
    request_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> SolicitacaoResponse:
    """Fecha uma concessão ativa antes do prazo.

    Quem pediu também pode devolver o próprio acesso — devolver cedo nunca é
    um risco, e exigir aprovador para isso só faria o acesso durar mais.
    """
    pedido = requests.get(request_id)
    if pedido.requester_id != current.id:
        _exigir_aprovador(current, policies, audit, db, pedido.path)

    pedido.revoke()
    salvo = requests.save(pedido)
    audit.append(
        _evento(
            current,
            AuditAction.ACCESS_REVOKED,
            str(pedido.path),
            reason=(
                "Devolvido pelo próprio solicitante."
                if pedido.requester_id == current.id
                else f"Revogado o acesso de {pedido.requester_label}."
            ),
        )
    )
    return _resposta(salvo)


def _resposta(pedido: AccessRequest) -> SolicitacaoResponse:
    return SolicitacaoResponse(
        id=pedido.id,
        requester_label=pedido.requester_label,
        path=str(pedido.path),
        capabilities=sorted(str(c) for c in pedido.capabilities),
        reason=pedido.reason,
        hours=pedido.hours,
        status=str(pedido.status),
        decided_by_label=pedido.decided_by_label,
        decision_note=pedido.decision_note,
        decided_at=pedido.decided_at,
        granted_until=pedido.granted_until,
        horas_restantes=pedido.hours_remaining(),
        ativa=pedido.is_active(),
        created_at=pedido.created_at,
    )
