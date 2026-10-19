"""Rotas de administração: pessoas, papéis e políticas.

Tudo aqui exige `ADMIN` no caminho `admin`. A checagem é por requisição e não
por papel chamado "administrador": quem decide é a política, não o nome do
papel, senão renomear um papel abriria ou fecharia o sistema por acidente.

A simulação de política (`/politicas/simular`) existe porque editar RBAC às
cegas é como se escreve incidente. Ela responde à única pergunta que importa
antes de salvar: *este caminho, para esta capacidade, fica permitido ou
negado — e por causa de qual regra?*
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.access.policy import (
    Capability,
    Effect,
    Policy,
    PolicyRule,
    evaluate,
    explain,
)
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import DomainError, PermissionDeniedError, ValidationError
from ...domain.shared.value_objects import PolicyPath, Slug
from ...infrastructure.db.repositories import (
    AuditRepository,
    PolicyRepository,
    UserRepository,
)
from ..deps import CurrentUser, get_audit, get_current_user, get_db, get_policies

router = APIRouter(prefix="/admin", tags=["Administração"])

CAMINHO_ADMIN = PolicyPath("admin")


def get_users(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


class UsuarioResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    mfa_enabled: bool
    roles: list[str]
    created_at: datetime


class PapelResponse(BaseModel):
    id: str
    name: str
    description: str
    policies: list[str]
    users: int


class RegraPayload(BaseModel):
    path: str = Field(min_length=1, max_length=256)
    capabilities: list[Capability] = Field(min_length=1)
    effect: Effect = Effect.ALLOW


class RegraResponse(BaseModel):
    path: str
    capabilities: list[str]
    effect: str


class PoliticaResponse(BaseModel):
    id: str
    name: str
    description: str
    rules: list[RegraResponse]
    roles: list[str]


class AtualizarRegrasRequest(BaseModel):
    """Conjunto completo de regras. É substituição, não merge."""

    rules: list[RegraPayload] = Field(min_length=1)


class SimularRequest(BaseModel):
    path: str = Field(min_length=1, max_length=256)
    capability: Capability
    rules: list[RegraPayload] = Field(min_length=1)


class SimularResponse(BaseModel):
    permitido: bool
    motivo: str


class PapeisRequest(BaseModel):
    roles: list[str]


def _exigir_admin(
    current: CurrentUser,
    policies: PolicyRepository,
    audit: AuditRepository,
    db: Session,
    acao: str,
) -> None:
    """Porta única da administração: nega, audita e commita a negativa."""
    if evaluate(policies.policies_for_user(current.id), CAMINHO_ADMIN, Capability.ADMIN):
        return
    audit.append(
        _evento(
            current,
            AuditAction.ACCESS_DENIED,
            str(CAMINHO_ADMIN),
            AuditOutcome.FAILURE,
            f"Sem permissão de administração: {acao}.",
        )
    )
    # Commit antes de propagar: sem isto o rollback apagaria o registro da
    # tentativa, e tentativa negada sem rastro é o que interessa a quem sonda.
    db.commit()
    raise PermissionDeniedError("Esta área é restrita a administradores.")


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


def _para_regras(payload: list[RegraPayload]) -> list[PolicyRule]:
    return [
        PolicyRule(
            path=PolicyPath(r.path),
            capabilities=frozenset(r.capabilities),
            effect=r.effect,
        )
        for r in payload
    ]


# ---------------------------------------------------------------- usuários


@router.get("/usuarios", response_model=list[UsuarioResponse], summary="Listar usuários")
def listar_usuarios(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    users: Annotated[UserRepository, Depends(get_users)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[UsuarioResponse]:
    _exigir_admin(current, policies, audit, db, "listar usuários")
    return [
        UsuarioResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            mfa_enabled=u.mfa_enabled,
            roles=sorted(r.name for r in u.roles),
            created_at=u.created_at,
        )
        for u in users.list_all()
    ]


@router.post(
    "/usuarios/{user_id}/ativar", response_model=UsuarioResponse, summary="Ativar conta"
)
def ativar_usuario(
    user_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    users: Annotated[UserRepository, Depends(get_users)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioResponse:
    _exigir_admin(current, policies, audit, db, "ativar conta")
    usuario = users.set_active(user_id, True)
    audit.append(
        _evento(current, AuditAction.USER_ACTIVATED, f"usuarios/{usuario.email}")
    )
    return _usuario_response(usuario)


@router.post(
    "/usuarios/{user_id}/desativar",
    response_model=UsuarioResponse,
    summary="Desativar conta",
)
def desativar_usuario(
    user_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    users: Annotated[UserRepository, Depends(get_users)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioResponse:
    """Desativa a conta. O token existente para de valer na próxima chamada.

    Desativar-se a si mesmo é bloqueado: o sistema ficaria sem administrador
    acessível, e recuperar isso exige mexer no banco à mão.
    """
    _exigir_admin(current, policies, audit, db, "desativar conta")
    if user_id == current.id:
        raise ValidationError("Você não pode desativar a própria conta.")
    usuario = users.set_active(user_id, False)
    audit.append(
        _evento(current, AuditAction.USER_DEACTIVATED, f"usuarios/{usuario.email}")
    )
    return _usuario_response(usuario)


@router.post(
    "/usuarios/{user_id}/reiniciar-mfa",
    response_model=UsuarioResponse,
    summary="Reiniciar MFA",
)
def reiniciar_mfa(
    user_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    users: Annotated[UserRepository, Depends(get_users)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioResponse:
    """Para quem perdeu o dispositivo: descarta o segredo e desliga o MFA."""
    _exigir_admin(current, policies, audit, db, "reiniciar MFA")
    usuario = users.reset_mfa(user_id)
    audit.append(
        _evento(current, AuditAction.USER_MFA_RESET, f"usuarios/{usuario.email}")
    )
    return _usuario_response(usuario)


@router.put(
    "/usuarios/{user_id}/papeis",
    response_model=UsuarioResponse,
    summary="Definir papéis do usuário",
)
def definir_papeis(
    user_id: str,
    payload: PapeisRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    users: Annotated[UserRepository, Depends(get_users)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioResponse:
    _exigir_admin(current, policies, audit, db, "alterar papéis")
    anteriores = sorted(r.name for r in users.get(user_id).roles)
    usuario = users.set_roles(user_id, payload.roles)
    atuais = sorted(r.name for r in usuario.roles)
    # Papel removido é revogação de acesso: a trilha precisa dizer o que saiu,
    # não apenas que "houve alteração".
    audit.append(
        _evento(
            current,
            AuditAction.USER_ROLES_CHANGED,
            f"usuarios/{usuario.email}",
            reason=f"De [{', '.join(anteriores) or '—'}] para [{', '.join(atuais) or '—'}].",
        )
    )
    return _usuario_response(usuario)


# ------------------------------------------------------------------ papéis


@router.get("/papeis", response_model=list[PapelResponse], summary="Listar papéis")
def listar_papeis(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    users: Annotated[UserRepository, Depends(get_users)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PapelResponse]:
    _exigir_admin(current, policies, audit, db, "listar papéis")
    return [
        PapelResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            policies=sorted(pol.name for pol in p.policies),
            users=len(p.users),
        )
        for p in users.list_roles()
    ]


# --------------------------------------------------------------- políticas


@router.get(
    "/politicas", response_model=list[PoliticaResponse], summary="Listar políticas"
)
def listar_politicas(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PoliticaResponse]:
    _exigir_admin(current, policies, audit, db, "listar políticas")
    return [_politica_response(p, policies) for p in policies.list_all()]


@router.get(
    "/politicas/{nome}", response_model=PoliticaResponse, summary="Detalhe da política"
)
def obter_politica(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> PoliticaResponse:
    _exigir_admin(current, policies, audit, db, "ler política")
    return _politica_response(policies.get_by_name(Slug(nome)), policies)


@router.post(
    "/politicas/simular",
    response_model=SimularResponse,
    summary="Simular o efeito de um conjunto de regras",
)
def simular_politica(
    payload: SimularRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> SimularResponse:
    """Avalia as regras propostas sem gravar nada.

    Roda no mesmo motor que decide em produção (`explain`), e não numa cópia
    da regra — uma segunda implementação divergiria e a tela mentiria.
    """
    _exigir_admin(current, policies, audit, db, "simular política")
    simulada = Policy(
        name=Slug("simulacao"),
        rules=_para_regras(payload.rules),
        description="Política temporária de simulação.",
    )
    permitido, motivo = explain(
        [simulada], PolicyPath(payload.path), payload.capability
    )
    return SimularResponse(permitido=permitido, motivo=motivo)


@router.put(
    "/politicas/{nome}/regras",
    response_model=PoliticaResponse,
    summary="Substituir as regras da política",
)
def atualizar_regras(
    nome: str,
    payload: AtualizarRegrasRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> PoliticaResponse:
    """Troca o conjunto de regras inteiro.

    Alterar política é mexer em acesso de gente: a trilha guarda o antes e o
    depois em texto, para que a revisão não dependa de reconstruir o estado.
    """
    _exigir_admin(current, policies, audit, db, "alterar política")
    atual = policies.get_by_name(Slug(nome))
    antes = _resumir_regras(atual.rules)
    try:
        atualizada = policies.replace_rules(atual.id, _para_regras(payload.rules))
    except DomainError:
        raise
    depois = _resumir_regras(atualizada.rules)
    audit.append(
        _evento(
            current,
            AuditAction.POLICY_UPDATED,
            f"politicas/{nome}",
            reason=f"Antes: {antes} | Depois: {depois}",
        )
    )
    return _politica_response(atualizada, policies)


# ----------------------------------------------------------------- helpers


def _usuario_response(usuario) -> UsuarioResponse:  # noqa: ANN001
    return UsuarioResponse(
        id=usuario.id,
        email=usuario.email,
        full_name=usuario.full_name,
        is_active=usuario.is_active,
        mfa_enabled=usuario.mfa_enabled,
        roles=sorted(r.name for r in usuario.roles),
        created_at=usuario.created_at,
    )


def _politica_response(
    policy: Policy, policies: PolicyRepository
) -> PoliticaResponse:
    return PoliticaResponse(
        id=policy.id,
        name=str(policy.name),
        description=policy.description,
        rules=[
            RegraResponse(
                path=str(r.path),
                capabilities=sorted(str(c) for c in r.capabilities),
                effect=str(r.effect),
            )
            for r in policy.rules
        ],
        roles=policies.roles_of_policy(policy.id),
    )


def _resumir_regras(rules: list[PolicyRule]) -> str:
    """Texto curto das regras, para o campo `reason` da auditoria."""
    partes = [
        f"{r.effect}:{r.path}({','.join(sorted(str(c) for c in r.capabilities))})"
        for r in rules
    ]
    return "; ".join(partes) if partes else "—"
