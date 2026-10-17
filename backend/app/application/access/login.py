"""Caso de uso: autenticar um usuário.

Três cuidados que o fluxo de login exige e que são fáceis de perder:

1. **Mensagem única.** E-mail inexistente, senha errada e conta inativa
   respondem a mesma coisa. Diferenciar entrega ao atacante uma lista de
   e-mails válidos da empresa.
2. **Tempo constante.** Quando o e-mail não existe, ainda assim se verifica
   uma senha contra um hash descartável. Sem isso, a resposta instantânea
   denuncia o e-mail inexistente mesmo com a mensagem igual.
3. **MFA não é opcional depois de ativado.** Quem tem MFA ativo não recebe
   token sem o segundo fator — recebe um desafio.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import AuthenticationError
from ...domain.vaults.entities import EncryptedValue
from ...infrastructure.auth.tokens import TokenPair, TokenService
from ...infrastructure.auth.totp import TotpService
from ...infrastructure.db.models import UserModel
from ...infrastructure.db.repositories import AuditRepository

@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Hash descartável para gastar o mesmo tempo quando o e-mail não existe.

    Gerado em tempo de execução, de uma senha aleatória que ninguém conhece.
    Gerar em vez de fixar no código garante que ele seja sempre um Argon2
    válido com os parâmetros ATUAIS: um hash literal desatualizado seria
    rejeitado no parse e retornaria rápido demais, denunciando pelo tempo
    de resposta exatamente o que a mensagem genérica esconde.
    """
    from ...infrastructure.crypto.passwords import Argon2PasswordHasher

    return Argon2PasswordHasher().hash(secrets.token_urlsafe(32))

MENSAGEM_GENERICA = "E-mail ou senha incorretos."


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str
    totp_code: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Ou um par de tokens, ou um desafio de MFA — nunca os dois."""

    tokens: TokenPair | None
    mfa_required: bool
    user_id: str
    email: str

    def __repr__(self) -> str:
        """Não imprime os tokens: um traceback não deve virar sessão válida."""
        return (
            f"LoginResult(user_id={self.user_id!r}, email={self.email!r}, "
            f"mfa_required={self.mfa_required!r}, tokens={'<omitido>' if self.tokens else None})"
        )


class Login:
    def __init__(
        self,
        session: Session,
        hasher,                  # PasswordHasher
        tokens: TokenService,
        totp: TotpService,
        audit: AuditRepository,
    ) -> None:
        self._session = session
        self._hasher = hasher
        self._tokens = tokens
        self._totp = totp
        self._audit = audit

    def execute(self, command: LoginCommand) -> LoginResult:
        email = command.email.strip().lower()
        user = self._session.scalar(select(UserModel).where(UserModel.email == email))

        # Tempo constante: sem usuário, verifica contra o hash descartável.
        stored_hash = user.password_hash if user is not None else _dummy_hash()
        password_ok = self._hasher.verify(command.password, stored_hash)

        if user is None or not password_ok or not user.is_active:
            self._record(command, email, None, "Credenciais inválidas ou conta inativa.")
            raise AuthenticationError(MENSAGEM_GENERICA)

        if user.mfa_enabled:
            if not command.totp_code:
                # Desafio: a senha estava certa, falta o segundo fator.
                return LoginResult(
                    tokens=None, mfa_required=True, user_id=user.id, email=user.email
                )
            if not self._verify_totp(user, command.totp_code):
                self._record(command, email, user.id, "Código de verificação inválido.")
                raise AuthenticationError("Código de verificação inválido.")

        pair = self._tokens.issue(user.id, user.email)
        self._audit.append(
            AuditEvent(
                action=AuditAction.LOGIN_SUCCESS,
                actor_id=user.id,
                actor_label=user.email,
                target_path="auth/login",
                outcome=AuditOutcome.SUCCESS,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return LoginResult(
            tokens=pair, mfa_required=False, user_id=user.id, email=user.email
        )

    def _verify_totp(self, user: UserModel, code: str) -> bool:
        if user.mfa_secret_ciphertext is None:
            # MFA marcado como ativo sem segredo: estado inconsistente, nega.
            return False
        encrypted = EncryptedValue(
            ciphertext=user.mfa_secret_ciphertext,
            nonce=user.mfa_secret_nonce or b"",
            wrapped_dek=user.mfa_secret_wrapped_dek or b"",
            key_id=user.mfa_key_id or "",
        )
        return self._totp.verify(encrypted, code)

    def _record(
        self, command: LoginCommand, email: str, user_id: str | None, reason: str
    ) -> None:
        """Falha de login é evento de auditoria: é assim que se vê um ataque.

        `actor_label` guarda o e-mail TENTADO, mesmo quando não existe — é o
        que permite ver alguém varrendo endereços.
        """
        self._audit.append(
            AuditEvent(
                action=AuditAction.LOGIN_FAILURE,
                actor_id=user_id,
                actor_label=email,
                target_path="auth/login",
                outcome=AuditOutcome.FAILURE,
                reason=reason,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
