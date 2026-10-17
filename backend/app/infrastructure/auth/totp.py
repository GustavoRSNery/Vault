"""Segundo fator por TOTP (RFC 6238).

O segredo do TOTP é tratado como segredo de verdade: nasce cifrado pelo mesmo
envelope dos segredos de cofre e só é decifrado no instante da verificação.
Quem ler o banco não consegue clonar o autenticador de ninguém.
"""

from __future__ import annotations

import pyotp

from ...domain.shared.errors import ValidationError
from ...domain.vaults.entities import EncryptedValue
from ..crypto.envelope import EnvelopeCryptoService

EMISSOR = "Vault de Senhas"


class TotpService:
    def __init__(self, crypto: EnvelopeCryptoService, window: int = 1) -> None:
        self._crypto = crypto
        self._window = window

    def enroll(self, user_email: str) -> tuple[EncryptedValue, str]:
        """Gera um segredo novo. Devolve (segredo cifrado, URI para o QR Code).

        A URI contém o segredo em claro — ela é mostrada uma única vez, na
        tela de cadastro, e nunca persistida nem registrada em log.
        """
        secret = pyotp.random_base32()
        uri = pyotp.TOTP(secret).provisioning_uri(name=user_email, issuer_name=EMISSOR)
        return self._crypto.encrypt(secret), uri

    def verify(self, encrypted_secret: EncryptedValue, code: str) -> bool:
        """Confere o código. Janela de ±`window` períodos de 30s.

        `valid_window` cobre relógio dessincronizado. A comparação dentro do
        pyotp é feita em tempo constante, o que evita vazar o código por
        tempo de resposta.
        """
        normalized = (code or "").strip().replace(" ", "")
        if not normalized.isdigit() or len(normalized) != 6:
            return False
        secret = self._crypto.decrypt(encrypted_secret)
        return pyotp.TOTP(secret).verify(normalized, valid_window=self._window)

    def current_code(self, encrypted_secret: EncryptedValue) -> str:
        """Só para testes: o código válido agora."""
        return pyotp.TOTP(self._crypto.decrypt(encrypted_secret)).now()


def require_six_digits(code: str) -> str:
    normalized = (code or "").strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        raise ValidationError("O código deve ter 6 dígitos.")
    return normalized
