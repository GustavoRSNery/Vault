"""Configuração da aplicação.

Nenhum segredo tem valor padrão utilizável: a aplicação recusa subir sem que
a chave-mestra e o segredo de JWT venham do ambiente. Um default conveniente
aqui viraria a chave de produção de alguém.
"""

from __future__ import annotations

import base64
import secrets
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
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

    # ARN ou alias da chave no AWS KMS. Preenchido, o KMS passa a ser o
    # provedor da KEK e `master_key_b64` deixa de ser usada: a chave-mestra
    # nunca entra neste processo.
    kms_key_id: str = ""
    kms_region: str = ""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15      # curto: o refresh renova
    refresh_token_days: int = 7

    # Janela do TOTP: 1 significa aceitar o código anterior e o próximo,
    # cobrindo relógio dessincronizado sem abrir margem relevante.
    totp_window: int = 1

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Destino da exportacao da trilha de auditoria. O arquivo local serve para
    # desenvolvimento: ele NAO e inviolavel, e a API diz isso na resposta.
    # Em producao, aponte para um destino somente-anexacao que a aplicacao nao
    # possa reescrever (Splunk HEC, CloudWatch, bucket com Object Lock) — a
    # troca e de uma linha em deps.py, porque o caso de uso so conhece a porta.
    audit_export_path: str = "./exportacoes/trilha.jsonl"

    # Gravacao de sessao. Trocar o adaptador e trocar estes valores — o
    # dominio e as rotas nao conhecem nenhuma tecnologia de captura.
    #   captura:     "manual" | "proxy-ssh"
    #   armazenamento: "local" | "s3"
    sessao_captura: str = "manual"
    sessao_armazenamento: str = "local"
    sessao_gravacoes_path: str = "./gravacoes"
    sessao_proxy_host: str = ""
    sessao_proxy_porta: int = 2222
    # Chave de host do proxy SSH, em ARQUIVO. Gerada a cada boot, ela faria
    # todo cliente ver o aviso de "host key changed" — o mesmo aviso de um
    # ataque man-in-the-middle — e as pessoas aprenderiam a ignora-lo, que e
    # o pior resultado possivel. O servidor recusa subir sem o arquivo.
    sessao_proxy_chave_host: str = ""
    sessao_s3_bucket: str = ""
    # Prefixo das gravacoes no bucket e endpoint alternativo (LocalStack ou
    # S3 compativel). Vazio = o endpoint padrao da AWS.
    sessao_s3_prefixo: str = "sessoes/"
    sessao_s3_endpoint: str = ""
    sessao_s3_region: str = ""

    # Retencao do registro de uso da API, em dias. Diferente da trilha de
    # auditoria, que nao expira: aquilo e prova, isto e operacional, e uma
    # tabela de chamadas sem teto cresce ate as consultas da tela doerem.
    # Zero desliga o expurgo.
    api_uso_retencao_dias: int = 90

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
    def usa_kms(self) -> bool:
        return bool(self.kms_key_id.strip())

    @model_validator(mode="after")
    def _exigir_kms_em_producao(self) -> "Settings":
        """Produção não roda com a chave-mestra em memória.

        Com `LocalKeyProvider`, quem lê o processo lê a KEK e decifra o cofre
        inteiro offline. É aceitável em desenvolvimento e inaceitável em
        produção — e uma configuração que "funciona" com a chave errada é pior
        que uma que falha ao subir, porque o erro só aparece no vazamento.
        """
        if self.environment == "production" and not self.usa_kms:
            raise ValueError(
                "Em produção, defina VAULT_KMS_KEY_ID. A chave-mestra em "
                "memória expõe todo o cofre a quem ler o processo."
            )
        return self

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
