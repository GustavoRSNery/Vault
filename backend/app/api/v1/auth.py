"""Rotas de autenticação."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ...application.access.login import Login, LoginCommand
from ...domain.access.policy import Capability, evaluate
from ...domain.shared.errors import AuthenticationError
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.auth.tokens import REFRESH, TokenService
from ...infrastructure.db.models import UserModel
from ...infrastructure.db.repositories import PolicyRepository
from ..deps import (
    CurrentUser,
    get_current_user,
    get_db,
    get_login,
    get_policies,
    get_tokens,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    totp_code: str | None = Field(default=None, max_length=10)


class TokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(BaseModel):
    """Ou os tokens, ou o desafio de MFA."""

    mfa_required: bool
    tokens: TokensResponse | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    # Apelido e foto viajam aqui para que o cabeçalho trate a pessoa como ela
    # pediu, sem uma segunda chamada em cada tela.
    apelido: str = ""
    foto: str = ""
    mfa_enabled: bool
    # Quem decide e a politica, no servidor. O front usa isto apenas para
    # escolher o que desenhar no menu: cada rota de admin checa de novo, e
    # esconder item de menu nunca e controle de acesso.
    is_admin: bool


@router.post("/login", response_model=LoginResponse, summary="Entrar")
def login(
    payload: LoginRequest,
    request: Request,
    caso: Annotated[Login, Depends(get_login)],
) -> LoginResponse:
    resultado = caso.execute(
        LoginCommand(
            email=str(payload.email),
            password=payload.password,
            totp_code=payload.totp_code,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    )
    if resultado.mfa_required or resultado.tokens is None:
        return LoginResponse(mfa_required=True)
    return LoginResponse(
        mfa_required=False,
        tokens=TokensResponse(
            access_token=resultado.tokens.access_token,
            refresh_token=resultado.tokens.refresh_token,
            expires_in=resultado.tokens.expires_in,
        ),
    )


@router.post("/refresh", response_model=TokensResponse, summary="Renovar sessão")
def refresh(
    payload: RefreshRequest,
    tokens: Annotated[TokenService, Depends(get_tokens)],
    db: Annotated[Session, Depends(get_db)],
) -> TokensResponse:
    """Troca um refresh por um par novo.

    A conta é reconsultada: um refresh emitido antes do desligamento não pode
    render um acesso novo depois dele.
    """
    claims = tokens.verify(payload.refresh_token, expected_type=REFRESH)
    user = db.get(UserModel, claims.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Credenciais inválidas.")

    par = tokens.issue(user.id, user.email)
    return TokensResponse(
        access_token=par.access_token,
        refresh_token=par.refresh_token,
        expires_in=par.expires_in,
    )


@router.get("/me", response_model=MeResponse, summary="Quem sou eu")
def me(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
) -> MeResponse:
    user = db.get(UserModel, current.id)
    assert user is not None  # get_current_user já garantiu
    minhas = policies.policies_for_user(current.id)
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        apelido=user.apelido or "",
        foto=user.foto or "",
        mfa_enabled=user.mfa_enabled,
        is_admin=(
            evaluate(minhas, PolicyPath("admin"), Capability.ADMIN)
            or evaluate(minhas, PolicyPath("auditoria"), Capability.ADMIN)
        ),
    )


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
