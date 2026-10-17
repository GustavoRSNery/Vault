"""Rotas de cadastro do segundo fator.

O fluxo é em duas etapas de propósito: o `POST /iniciar` gera o segredo e
devolve a URI do QR Code, mas **não** liga o MFA. Só o `POST /confirmar`, com
um código válido, ativa. Sem isso, um usuário que fechasse a tela antes de
escanear ficaria trancado para fora da própria conta.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import ConflictError, ValidationError
from ...domain.vaults.entities import EncryptedValue
from ...infrastructure.auth.totp import TotpService
from ...infrastructure.db.models import UserModel
from ...infrastructure.db.repositories import AuditRepository
from ..deps import CurrentUser, get_audit, get_current_user, get_db, get_totp

router = APIRouter(prefix="/mfa", tags=["Verificação em duas etapas"])


class IniciarResponse(BaseModel):
    """A URI contém o segredo em claro: é exibida uma vez e nunca persistida."""

    provisioning_uri: str


class ConfirmarRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class StatusResponse(BaseModel):
    mfa_enabled: bool


@router.get("/status", response_model=StatusResponse, summary="Situação do MFA")
def status(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StatusResponse:
    user = db.get(UserModel, current.id)
    assert user is not None
    return StatusResponse(mfa_enabled=user.mfa_enabled)


@router.post("/iniciar", response_model=IniciarResponse, summary="Gerar segredo")
def iniciar(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    totp: Annotated[TotpService, Depends(get_totp)],
) -> IniciarResponse:
    user = db.get(UserModel, current.id)
    assert user is not None
    if user.mfa_enabled:
        raise ConflictError("A verificação em duas etapas já está ativa.")

    cifrado, uri = totp.enroll(user.email)
    # Grava o segredo mas deixa mfa_enabled=False: ativar é o próximo passo.
    user.mfa_secret_ciphertext = cifrado.ciphertext
    user.mfa_secret_nonce = cifrado.nonce
    user.mfa_secret_wrapped_dek = cifrado.wrapped_dek
    user.mfa_key_id = cifrado.key_id
    db.flush()

    return IniciarResponse(provisioning_uri=uri)


@router.post("/confirmar", response_model=StatusResponse, summary="Ativar MFA")
def confirmar(
    payload: ConfirmarRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    totp: Annotated[TotpService, Depends(get_totp)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
) -> StatusResponse:
    user = db.get(UserModel, current.id)
    assert user is not None
    if user.mfa_enabled:
        raise ConflictError("A verificação em duas etapas já está ativa.")
    if user.mfa_secret_ciphertext is None:
        raise ValidationError("Gere o segredo antes de confirmar.")

    cifrado = EncryptedValue(
        ciphertext=user.mfa_secret_ciphertext,
        nonce=user.mfa_secret_nonce or b"",
        wrapped_dek=user.mfa_secret_wrapped_dek or b"",
        key_id=user.mfa_key_id or "",
    )
    if not totp.verify(cifrado, payload.code):
        raise ValidationError("Código inválido. Confira o aplicativo e tente de novo.")

    user.mfa_enabled = True
    db.flush()

    audit.append(
        AuditEvent(
            action=AuditAction.MFA_ENROLLED,
            actor_id=user.id,
            actor_label=user.email,
            target_path="auth/mfa",
            outcome=AuditOutcome.SUCCESS,
            ip_address=current.ip_address,
            user_agent=current.user_agent,
        )
    )
    return StatusResponse(mfa_enabled=True)
