"""Configuração da aplicação.

Nenhum segredo tem valor padrão utilizável: a aplicação recusa subir sem que
a chave-mestra e o segredo de JWT venham do ambiente. Um default conveniente
aqui viraria a chave de produção de alguém.
"""

from __future__ import annotations

import base64
import secrets
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VAULT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite+pysqlite:///./vault_dev.db"

    # Chave-mestra (KEK) em base64, 32 bytes. Em produção vem do KMS e este
    # campo fica vazio — o adaptador de KMS não precisa dela em processo.
    master_key_b64: str = ""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15      # curto: o refresh renova
    refresh_token_days: int = 7

    # Janela do TOTP: 1 significa aceitar o código anterior e o próximo,
    # cobrindo relógio dessincronizado sem abrir margem relevante.
    totp_window: int = 1

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("master_key_b64")
    @classmethod
    def _validate_master_key(cls, value: str) -> str:
        if not value:
            return value
        try:
            raw = base64.b64decode(value, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("VAULT_MASTER_KEY_B64 não é base64 válido.") from exc
        if len(raw) != 32:
            raise ValueError("VAULT_MASTER_KEY_B64 deve decodificar para 32 bytes.")
        return value

    @property
    def master_key(self) -> bytes:
        if not self.master_key_b64:
            raise RuntimeError(
                "VAULT_MASTER_KEY_B64 não está definida. "
                "Gere uma com: python -m app.tools.gerar_chave"
            )
        return base64.b64decode(self.master_key_b64)

    @property
    def effective_jwt_secret(self) -> str:
        """Em desenvolvimento, gera um segredo efêmero se nenhum foi dado.

        Efêmero de propósito: reiniciar o servidor invalida os tokens, o que
        é aceitável em dev e impede que um segredo fraco vire permanente.
        Em produção, a ausência é erro.
        """
        if self.jwt_secret:
            return self.jwt_secret
        if self.environment == "production":
            raise RuntimeError("VAULT_JWT_SECRET é obrigatório em produção.")
        return _dev_jwt_secret()


@lru_cache(maxsize=1)
def _dev_jwt_secret() -> str:
    return secrets.token_urlsafe(48)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
