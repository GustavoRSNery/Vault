"""Rotas de cofres e segredos."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...application.vaults.reveal_secret import RevealSecret, RevealSecretCommand
from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import DomainError, PermissionDeniedError
from ...domain.shared.value_objects import Slug
from ...domain.vaults.entities import Secret, SecretKind, Vault
from ...infrastructure.crypto.envelope import EnvelopeCryptoService
from ...infrastructure.db.repositories import (
    AuditRepository,
    PolicyRepository,
    SecretRepository,
    VaultRepository,
)
from ..deps import (
    CurrentUser,
    get_audit,
    get_crypto,
    get_current_user,
    get_db,
    get_policies,
    get_secrets,
    get_vaults,
)

router = APIRouter(prefix="/cofres", tags=["Cofres e segredos"])


class VaultResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    state: str
    created_at: datetime


class CreateVaultRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    description: str = ""


class SecretSummary(BaseModel):
    """Metadados do segredo. Nunca o valor — listar não é revelar."""

    id: str
    name: str
    kind: str
    description: str
    current_version: int
    updated_at: datetime


class CreateSecretRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1)
    kind: SecretKind = SecretKind.PASSWORD
    description: str = ""


class RevealResponse(BaseModel):
    secret_id: str
    secret_name: str
    version: int
    value: str


def _commit_then_raise(db: Session, error: DomainError) -> None:
    """Preserva o evento de auditoria antes de propagar a negação.

    Sem isto, o rollback da sessão apagaria o registro da tentativa negada —
    e tentativa negada sem rastro é exatamente o que interessa a quem está
    sondando permissões.
    """
    db.commit()
    raise error


@router.get("", response_model=list[VaultResponse], summary="Listar cofres")
def listar_cofres(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
) -> list[VaultResponse]:
    """Só os cofres que o usuário pode listar.

    O filtro acontece aqui, não na tela: devolver tudo e esconder no front
    deixaria os nomes visíveis para quem lesse a resposta da API.
    """
    user_policies = policies.policies_for_user(current.id)
    visiveis = [
        v for v in vaults.list_all()
        if evaluate(user_policies, v.path, Capability.LIST)
        or evaluate(user_policies, v.path, Capability.READ)
    ]
    return [_vault_response(v) for v in visiveis]


@router.post(
    "", response_model=VaultResponse, status_code=status.HTTP_201_CREATED,
    summary="Criar cofre",
)
def criar_cofre(
    payload: CreateVaultRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> VaultResponse:
    cofre = Vault(
        name=Slug(payload.name),
        display_name=payload.display_name,
        description=payload.description,
    )
    user_policies = policies.policies_for_user(current.id)
    if not evaluate(user_policies, cofre.path, Capability.CREATE):
        audit.append(_evento(current, AuditAction.ACCESS_DENIED, str(cofre.path),
                             AuditOutcome.FAILURE, "Sem permissão para criar cofre."))
        _commit_then_raise(db, PermissionDeniedError("Você não pode criar este cofre."))

    vaults.add(cofre)
    audit.append(_evento(current, AuditAction.VAULT_CREATED, str(cofre.path)))
    return _vault_response(cofre)


@router.get(
    "/{vault_name}/segredos", response_model=list[SecretSummary],
    summary="Listar segredos do cofre",
)
def listar_segredos(
    vault_name: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SecretSummary]:
    cofre = vaults.get_by_name(Slug(vault_name))
    user_policies = policies.policies_for_user(current.id)
    if not evaluate(user_policies, cofre.path, Capability.LIST):
        audit.append(_evento(current, AuditAction.ACCESS_DENIED, str(cofre.path),
                             AuditOutcome.FAILURE, "Sem permissão para listar o cofre."))
        _commit_then_raise(db, PermissionDeniedError("Você não tem acesso a este cofre."))

    return [
        SecretSummary(
            id=s.id,
            name=str(s.name),
            kind=str(s.kind),
            description=s.description,
            current_version=s.current_version.version,
            updated_at=s.current_version.created_at,
        )
        for s in secrets.list_in_vault(cofre.id)
    ]


@router.post(
    "/{vault_name}/segredos", response_model=SecretSummary,
    status_code=status.HTTP_201_CREATED, summary="Criar segredo",
)
def criar_segredo(
    vault_name: str,
    payload: CreateSecretRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    crypto: Annotated[EnvelopeCryptoService, Depends(get_crypto)],
    db: Annotated[Session, Depends(get_db)],
) -> SecretSummary:
    cofre = vaults.get_by_name(Slug(vault_name))
    nome = Slug(payload.name)
    caminho = cofre.secret_path(nome)

    user_policies = policies.policies_for_user(current.id)
    if not evaluate(user_policies, caminho, Capability.CREATE):
        audit.append(_evento(current, AuditAction.ACCESS_DENIED, str(caminho),
                             AuditOutcome.FAILURE, "Sem permissão para criar segredo."))
        _commit_then_raise(db, PermissionDeniedError("Você não pode criar segredos aqui."))

    cofre.ensure_usable()

    segredo = Secret(
        name=nome, vault_id=cofre.id, kind=payload.kind, description=payload.description
    )
    segredo.add_version(crypto.encrypt(payload.value), created_by=current.id)
    secrets.add(segredo)

    audit.append(_evento(current, AuditAction.SECRET_CREATED, str(caminho)))
    versao = segredo.current_version
    return SecretSummary(
        id=segredo.id, name=str(segredo.name), kind=str(segredo.kind),
        description=segredo.description, current_version=versao.version,
        updated_at=versao.created_at,
    )


@router.post(
    "/{vault_name}/segredos/{secret_name}/revelar",
    response_model=RevealResponse, summary="Revelar segredo",
)
def revelar_segredo(
    vault_name: str,
    secret_name: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    crypto: Annotated[EnvelopeCryptoService, Depends(get_crypto)],
    db: Annotated[Session, Depends(get_db)],
) -> RevealResponse:
    """POST, não GET, de propósito: GET entra em log de acesso, histórico do
    navegador e cache de proxy. A revelação de um segredo não deve passar por
    nenhum dos três."""
    caso = RevealSecret(vaults, secrets, policies, audit, crypto)
    try:
        revelado = caso.execute(
            RevealSecretCommand(
                actor_id=current.id,
                actor_label=current.email,
                vault_name=vault_name,
                secret_name=secret_name,
                ip_address=current.ip_address,
                user_agent=current.user_agent,
            )
        )
    except DomainError as erro:
        # O caso de uso já registrou o evento; preserva antes de propagar.
        _commit_then_raise(db, erro)
        raise  # inalcançável; mantém o type checker satisfeito

    return RevealResponse(
        secret_id=revelado.secret_id,
        secret_name=revelado.secret_name,
        version=revelado.version,
        value=revelado.value,
    )


def _vault_response(vault: Vault) -> VaultResponse:
    return VaultResponse(
        id=vault.id,
        name=str(vault.name),
        display_name=vault.display_name,
        description=vault.description,
        state=str(vault.state),
        created_at=vault.created_at,
    )


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
