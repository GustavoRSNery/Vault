"""Value objects do domínio: imutáveis, validados na construção."""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from .errors import ValidationError

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Um caminho de política: "cofres/contabil/*", "cofres/rh/segredos/123".
_PATH_SEGMENT_RE = re.compile(r"^[a-z0-9*][a-z0-9_*-]*$")


def new_id() -> str:
    """Identificador opaco. UUID4 como string, nunca sequencial."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Agora, sempre com timezone. Datetime ingênuo não entra no domínio."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        v = self.value.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValidationError("E-mail inválido.")
        if len(v) > 254:
            raise ValidationError("E-mail excede 254 caracteres.")
        object.__setattr__(self, "value", v)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Slug:
    """Nome estável usado em caminhos de política. Sem acento, sem espaço."""

    value: str

    def __post_init__(self) -> None:
        v = self.value.strip().lower()
        if not v:
            raise ValidationError("O identificador não pode ser vazio.")
        if len(v) > 64:
            raise ValidationError("O identificador excede 64 caracteres.")
        if not _SLUG_RE.match(v):
            raise ValidationError(
                "Use apenas letras minúsculas, números e hífen (sem hífen no início ou fim)."
            )
        object.__setattr__(self, "value", v)

    @classmethod
    def from_name(cls, name: str) -> Slug:
        """Deriva um slug de um nome livre: 'Contábil 2026' -> 'contabil-2026'."""
        normalized = unicodedata.normalize("NFKD", name)
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
        lowered = ascii_only.lower()
        hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
        if not hyphenated:
            raise ValidationError("O nome não produz um identificador válido.")
        return cls(hyphenated[:64].strip("-"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PolicyPath:
    """Caminho hierárquico de política, com curinga opcional no fim.

    "cofres/contabil/*" cobre tudo sob contabil; "cofres/*" cobre todos os cofres.
    O curinga só é aceito como segmento inteiro, nunca no meio de uma palavra.
    """

    value: str

    def __post_init__(self) -> None:
        v = self.value.strip().lower().strip("/")
        if not v:
            raise ValidationError("O caminho não pode ser vazio.")
        if len(v) > 256:
            raise ValidationError("O caminho excede 256 caracteres.")
        segments = v.split("/")
        for i, segment in enumerate(segments):
            if not _PATH_SEGMENT_RE.match(segment):
                raise ValidationError(f"Segmento inválido no caminho: {segment!r}.")
            if "*" in segment:
                if segment != "*":
                    raise ValidationError("O curinga '*' deve ocupar um segmento inteiro.")
                if i != len(segments) - 1:
                    raise ValidationError("O curinga '*' só é aceito no último segmento.")
        object.__setattr__(self, "value", v)

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(self.value.split("/"))

    @property
    def has_wildcard(self) -> bool:
        return self.segments[-1] == "*"

    def matches(self, concrete: PolicyPath) -> bool:
        """Este caminho (possivelmente com curinga) cobre o caminho concreto?

        A comparação é por segmento: "cofres/conta" NÃO cobre "cofres/contabil".
        """
        mine, theirs = self.segments, concrete.segments
        if self.has_wildcard:
            prefix = mine[:-1]
            # "cofres/*" cobre "cofres/x" e "cofres/x/y", mas não o próprio "cofres".
            return len(theirs) > len(prefix) and theirs[: len(prefix)] == prefix
        return mine == theirs

    def __str__(self) -> str:
        return self.value
