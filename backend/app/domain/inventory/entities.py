"""Inventário: dispositivos, credenciais e certificados.

Este domínio responde a uma pergunta que cofre de senha puro não responde:
*a senha deste equipamento está velha? este certificado vence quando?* Senha
guardada sem prazo é senha eterna, e é assim que credencial de roteador fica
cinco anos sem trocar.

Três invariantes moram aqui, longe de qualquer rota:

1. **Custódia é exclusiva.** Duas pessoas não retiram a mesma credencial ao
   mesmo tempo. Sem isso, duas trocam a senha em paralelo e a segunda invalida
   a primeira sem ninguém notar.
2. **Rotação se mede por prazo, não por intenção.** `is_overdue` compara data,
   não um booleano que alguém marca à mão e esquece.
3. **Certificado vencido não é "quase vencendo".** A faixa de alerta é
   calculada do prazo real, e o estado expirado é terminal até substituição.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from ..shared.errors import ConflictError, ValidationError
from ..shared.value_objects import PolicyPath, Slug, new_id, utcnow


class DeviceKind(StrEnum):
    SERVER = "servidor"
    ROUTER = "roteador"
    SWITCH = "switch"
    FIREWALL = "firewall"
    DATABASE = "banco_de_dados"
    APPLICATION = "aplicacao"
    OTHER = "outro"


class CredentialStatus(StrEnum):
    ACTIVE = "ativa"
    CHECKED_OUT = "em_custodia"
    RETIRED = "aposentada"


@dataclass(slots=True)
class Device:
    """Equipamento ou serviço ao qual credenciais pertencem."""

    name: Slug
    display_name: str
    kind: DeviceKind = DeviceKind.OTHER
    address: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("O dispositivo precisa de um nome visível.")
        # Tag duplicada só polui o filtro da tela.
        self.tags = sorted({t.strip().lower() for t in self.tags if t.strip()})

    @property
    def path(self) -> PolicyPath:
        return PolicyPath(f"dispositivos/{self.name}")


@dataclass(slots=True)
class Checkout:
    """Uma retirada de credencial: quem levou, até quando e por quê."""

    credential_id: str
    user_id: str
    user_label: str
    reason: str
    due_at: datetime
    taken_at: datetime = field(default_factory=utcnow)
    returned_at: datetime | None = None
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValidationError("A retirada precisa de uma justificativa.")
        if self.due_at <= self.taken_at:
            raise ValidationError("O prazo de devolução deve ser no futuro.")

    @property
    def is_open(self) -> bool:
        return self.returned_at is None

    def is_late(self, now: datetime | None = None) -> bool:
        """Em atraso é retirada aberta cujo prazo já passou."""
        if not self.is_open:
            return False
        return (now or utcnow()) > self.due_at

    def give_back(self, at: datetime | None = None) -> None:
        if not self.is_open:
            raise ConflictError("Esta retirada já foi devolvida.")
        self.returned_at = at or utcnow()


@dataclass(slots=True)
class Credential:
    """Credencial de um dispositivo, com prazo de rotação e custódia.

    O valor em si não vive aqui: fica no segredo do cofre, cifrado. Esta
    entidade guarda o *governo* da credencial — quando rotacionar, quem está
    com ela, quando foi trocada pela última vez.
    """

    name: Slug
    device_id: str
    secret_id: str | None = None
    username: str = ""
    description: str = ""
    rotation_days: int = 90
    last_rotated_at: datetime | None = None
    status: CredentialStatus = CredentialStatus.ACTIVE
    checkouts: list[Checkout] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.rotation_days < 0:
            raise ValidationError("O prazo de rotação não pode ser negativo.")
        if self.rotation_days > 3650:
            raise ValidationError("O prazo de rotação excede dez anos.")

    @property
    def path(self) -> PolicyPath:
        return PolicyPath(f"credenciais/{self.name}")

    @property
    def rotation_disabled(self) -> bool:
        """Prazo zero quer dizer "não rotaciona" — e isso é dito, não inferido."""
        return self.rotation_days == 0

    @property
    def due_at(self) -> datetime | None:
        """Quando a próxima rotação vence."""
        if self.rotation_disabled or self.last_rotated_at is None:
            return None
        return self.last_rotated_at + timedelta(days=self.rotation_days)

    def is_overdue(self, now: datetime | None = None) -> bool:
        """Atrasada compara data, nunca um booleano marcado à mão.

        Credencial que nunca foi rotacionada conta como atrasada: senão a
        pior situação — senha de fábrica — ficaria fora de todo relatório.
        """
        if self.rotation_disabled:
            return False
        if self.last_rotated_at is None:
            return True
        vencimento = self.due_at
        assert vencimento is not None  # garantido pelas duas guardas acima
        return (now or utcnow()) > vencimento

    def days_until_due(self, now: datetime | None = None) -> int | None:
        vencimento = self.due_at
        if vencimento is None:
            return None
        return (vencimento - (now or utcnow())).days

    @property
    def open_checkout(self) -> Checkout | None:
        for c in self.checkouts:
            if c.is_open:
                return c
        return None

    def check_out(
        self, user_id: str, user_label: str, reason: str, hours: int
    ) -> Checkout:
        """Retira a credencial para uso exclusivo.

        Exclusividade é a razão de existir da custódia: se duas pessoas
        retiram a mesma credencial, as duas trocam a senha e a segunda
        invalida a da primeira sem que ninguém perceba.
        """
        if self.status is CredentialStatus.RETIRED:
            raise ConflictError("Credencial aposentada não pode ser retirada.")
        aberta = self.open_checkout
        if aberta is not None:
            raise ConflictError(
                f"A credencial está com {aberta.user_label} até "
                f"{aberta.due_at:%d/%m/%Y %H:%M}."
            )
        if hours < 1 or hours > 720:
            raise ValidationError("O prazo deve ficar entre 1 hora e 30 dias.")

        agora = utcnow()
        checkout = Checkout(
            credential_id=self.id,
            user_id=user_id,
            user_label=user_label,
            reason=reason,
            due_at=agora + timedelta(hours=hours),
            taken_at=agora,
        )
        self.checkouts.append(checkout)
        self.status = CredentialStatus.CHECKED_OUT
        return checkout

    def check_in(self, user_id: str, *, force: bool = False) -> Checkout:
        """Devolve a credencial.

        Só quem retirou devolve, salvo devolução forçada por administrador —
        o caso real de quem saiu de férias com a credencial na mão.
        """
        aberta = self.open_checkout
        if aberta is None:
            raise ConflictError("A credencial não está em custódia.")
        if aberta.user_id != user_id and not force:
            raise ConflictError(
                f"A credencial está com {aberta.user_label}: só essa pessoa "
                "pode devolvê-la, ou um administrador pode forçar a devolução."
            )
        aberta.give_back()
        self.status = CredentialStatus.ACTIVE
        return aberta

    def mark_rotated(self, at: datetime | None = None) -> None:
        """Registra que a credencial foi trocada agora."""
        if self.status is CredentialStatus.RETIRED:
            raise ConflictError("Credencial aposentada não é rotacionada.")
        self.last_rotated_at = at or utcnow()

    def retire(self) -> None:
        if self.open_checkout is not None:
            raise ConflictError(
                "Devolva a credencial antes de aposentá-la: alguém ainda a tem."
            )
        self.status = CredentialStatus.RETIRED


class CertificateState(StrEnum):
    VALID = "valido"
    EXPIRING = "vencendo"
    EXPIRED = "vencido"


# Faixa de alerta do inventário de certificados. 30 dias é o prazo mínimo
# para renovar um certificado com emissão manual sem virar urgência.
DIAS_DE_ALERTA = 30


@dataclass(slots=True)
class Certificate:
    """Certificado digital com validade controlada.

    Só metadados e a cadeia pública. A chave privada, quando guardada, vive
    como segredo cifrado no cofre — aqui ficaria legível para quem só precisa
    acompanhar vencimento.
    """

    name: Slug
    display_name: str
    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    owner_label: str = ""
    serial: str = ""
    secret_id: str | None = None
    description: str = ""
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("O certificado precisa de um nome visível.")
        if not self.subject.strip():
            raise ValidationError("O certificado precisa de um titular.")
        if self.not_after <= self.not_before:
            raise ValidationError(
                "A validade final deve ser posterior à validade inicial."
            )

    @property
    def path(self) -> PolicyPath:
        return PolicyPath(f"certificados/{self.name}")

    def days_remaining(self, now: datetime | None = None) -> int:
        return (self.not_after - (now or utcnow())).days

    def state(self, now: datetime | None = None) -> CertificateState:
        """Vencido é terminal; vencendo é a faixa de alerta antes do prazo."""
        agora = now or utcnow()
        if agora >= self.not_after:
            return CertificateState.EXPIRED
        if (self.not_after - agora).days <= DIAS_DE_ALERTA:
            return CertificateState.EXPIRING
        return CertificateState.VALID

    def is_expired(self, now: datetime | None = None) -> bool:
        return self.state(now) is CertificateState.EXPIRED
