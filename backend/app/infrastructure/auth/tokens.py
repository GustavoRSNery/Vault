"""Emissão e verificação de tokens de acesso.

Dois tokens, com propósitos distintos:

- acesso: curto (minutos), carrega a identidade, vai em toda requisição;
- refresh: longo (dias), só serve para obter um novo acesso.

O refresh carrega `type: "refresh"` e a verificação exige o tipo esperado.
Sem isso, um refresh roubado valeria como acesso direto — é a confusão de
tipo que já derrubou sistemas reais.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from ...domain.shared.errors import AuthenticationError
from ...domain.shared.value_objects import new_id

ACCESS = "access"
REFRESH = "refresh"

# RFC 7518 §3.2: a chave HMAC deve ter ao menos o tamanho do digest.
MIN_SECRET_BYTES = 32


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # segundos de vida do token de acesso


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: str
    email: str
    token_type: str
    jti: str
    expires_at: datetime


class TokenService:
    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        access_minutes: int = 15,
        refresh_days: int = 7,
    ) -> None:
        if not secret:
            raise RuntimeError("O segredo de JWT não pode ser vazio.")
        if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
            raise RuntimeError(
                f"O segredo de JWT precisa de ao menos {MIN_SECRET_BYTES} bytes "
                "(RFC 7518 §3.2 para HMAC-SHA256)."
            )
        self._secret = secret
        self._algorithm = algorithm
        self._access_delta = timedelta(minutes=access_minutes)
        self._refresh_delta = timedelta(days=refresh_days)

    def issue(self, user_id: str, email: str) -> TokenPair:
        now = datetime.now(UTC)
        return TokenPair(
            access_token=self._encode(user_id, email, ACCESS, now, self._access_delta),
            refresh_token=self._encode(user_id, email, REFRESH, now, self._refresh_delta),
            expires_in=int(self._access_delta.total_seconds()),
        )

    def _encode(
        self, user_id: str, email: str, token_type: str, now: datetime, delta: timedelta
    ) -> str:
        payload = {
            "sub": user_id,
            "email": email,
            "type": token_type,
            "jti": new_id(),
            "iat": int(now.timestamp()),
            "exp": int((now + delta).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify(self, token: str, *, expected_type: str = ACCESS) -> TokenClaims:
        """Decodifica e valida. Qualquer problema vira AuthenticationError.

        A mensagem é a mesma para token expirado, assinatura inválida e tipo
        errado: distinguir ajudaria quem está testando tokens.
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Sessão expirada. Entre novamente.") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Credenciais inválidas.") from exc

        if payload.get("type") != expected_type:
            raise AuthenticationError("Credenciais inválidas.")

        return TokenClaims(
            user_id=payload["sub"],
            email=payload.get("email", ""),
            token_type=payload["type"],
            jti=payload.get("jti", ""),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
