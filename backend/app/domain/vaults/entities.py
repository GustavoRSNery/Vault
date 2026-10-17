"""Cofres e segredos.

Duas invariantes que o resto do sistema assume:

1. Um cofre selado não entrega nem aceita segredo. A checagem mora aqui, no
   domínio, para que nenhuma rota consiga contorná-la por esquecimento.
2. O valor de um segredo nunca existe em claro nesta camada. O domínio guarda
   apenas o texto cifrado e o material de envelope; a decifragem é um serviço
   da camada de aplicação, e cada revelação vira evento de auditoria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from ..shared.errors import ConflictError, SealedError, ValidationError
from ..shared.value_objects import PolicyPath, Slug, new_id, utcnow


class VaultState(StrEnum):
    ACTIVE = "ativo"
    SEALED = "selado"


class SecretKind(StrEnum):
    PASSWORD = "senha"
    API_KEY = "chave_api"
    SSH_KEY = "chave_ssh"
    CERTIFICATE = "certificado"
    TOKEN = "token"
    NOTE = "nota"


@dataclass(frozen=True, slots=True)
class EncryptedValue:
    """Texto cifrado + material do envelope. Nunca contém o valor em claro."""

    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes
    key_id: str

    def __post_init__(self) -> None:
        if not self.ciphertext:
            raise ValidationError("O texto cifrado não pode ser vazio.")
        if len(self.nonce) != 12:
            raise ValidationError("O nonce AES-GCM deve ter 12 bytes.")
        if not self.wrapped_dek:
            raise ValidationError("A chave de dados protegida não pode ser vazia.")


@dataclass(slots=True)
class SecretVersion:
    """Uma versão imutável de um segredo. Versões nunca são editadas."""

    version: int
    value: EncryptedValue
    created_by: str
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValidationError("A versão deve começar em 1.")


@dataclass(slots=True)
class Secret:
    """Segredo versionado dentro de um cofre."""

    name: Slug
    vault_id: str
    kind: SecretKind = SecretKind.PASSWORD
    description: str = ""
    versions: list[SecretVersion] = field(default_factory=list)
    deleted_at: datetime | None = None
    id: str = field(default_factory=new_id)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def current_version(self) -> SecretVersion:
        if not self.versions:
            raise ConflictError("O segredo não possui nenhuma versão.")
        return max(self.versions, key=lambda v: v.version)

    def version_at(self, number: int) -> SecretVersion:
        for v in self.versions:
            if v.version == number:
                return v
        raise ConflictError(f"Versão {number} não existe neste segredo.")

    def add_version(self, value: EncryptedValue, created_by: str) -> SecretVersion:
        if self.is_deleted:
            raise ConflictError("O segredo está na lixeira: restaure antes de alterar.")
        next_number = (self.versions[-1].version + 1) if self.versions else 1
        version = SecretVersion(version=next_number, value=value, created_by=created_by)
        self.versions.append(version)
        return version

    def soft_delete(self, at: datetime | None = None) -> None:
        """Lixeira: o segredo some das listas mas as versões continuam recuperáveis."""
        if self.is_deleted:
            raise ConflictError("O segredo já está na lixeira.")
        self.deleted_at = at or utcnow()

    def restore(self) -> None:
        if not self.is_deleted:
            raise ConflictError("O segredo não está na lixeira.")
        self.deleted_at = None


@dataclass(slots=True)
class Vault:
    """Cofre: agrupa segredos de uma equipe ou cliente."""

    name: Slug
    display_name: str
    description: str = ""
    state: VaultState = VaultState.ACTIVE
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("O cofre precisa de um nome visível.")

    @property
    def path(self) -> PolicyPath:
        """Caminho do cofre para avaliação de política."""
        return PolicyPath(f"cofres/{self.name}")

    def secret_path(self, secret_name: Slug) -> PolicyPath:
        return PolicyPath(f"cofres/{self.name}/segredos/{secret_name}")

    @property
    def is_sealed(self) -> bool:
        return self.state is VaultState.SEALED

    def ensure_usable(self) -> None:
        """Porta única por onde passa toda operação sobre segredos deste cofre."""
        if self.is_sealed:
            raise SealedError(
                f"O cofre {self.display_name} está selado. "
                "Peça a um administrador para desselá-lo."
            )

    def seal(self) -> None:
        if self.is_sealed:
            raise ConflictError("O cofre já está selado.")
        self.state = VaultState.SEALED

    def unseal(self) -> None:
        if not self.is_sealed:
            raise ConflictError("O cofre não está selado.")
        self.state = VaultState.ACTIVE
