"""Acesso de máquina: aplicações, AppRole e leases.

Resolve o problema que o login de pessoa não resolve: um RPA precisa ler
segredos às 3 da manhã, sem ninguém para digitar senha nem aprovar MFA. A
saída ruim — e comum — é embutir uma senha eterna no código do robô, que
então vaza no repositório, fica no histórico do git, e nunca é rotacionada
porque ninguém lembra que está lá.

## AppRole: dois fatores que viajam separados

- `role_id` **identifica** a aplicação. É público, estável, pode ir no código
  ou numa variável de ambiente.
- `secret_id` **autentica**. É segredo, tem validade, e pode ser revogado sem
  mexer no robô.

Separá-los é o ponto: o `role_id` vazado sozinho não autentica nada, e trocar
o `secret_id` não exige alterar o código da aplicação. É a diferença entre
"rotacionar credencial de RPA" ser uma operação de minutos ou um deploy.

## Lease: o acesso é emprestado, não concedido

A autenticação devolve um **lease** — um token de curta duração com escopo
restrito. Expira sozinho. Se o robô for comprometido, o atacante herda
minutos de acesso limitado, não a credencial permanente.

## O que não vive aqui

O `secret_id` em claro nunca é persistido: guarda-se o hash, como senha. E o
valor dos segredos continua cifrado pela KEK — este domínio governa *quem
pode pedir*, não *o que está guardado*.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from ..access.policy import Capability
from ..shared.errors import ConflictError, ValidationError
from ..shared.value_objects import PolicyPath, Slug, new_id, utcnow

SECRET_ID_BYTES = 32
# Teto do lease. Mais que isto deixa de ser "empréstimo": um token de 24h
# comprometido é um dia inteiro de acesso, o que anula a razão de existir.
LEASE_MINUTOS_MAXIMO = 720  # 12 horas
LEASE_MINUTOS_PADRAO = 60


class ApplicationStatus(StrEnum):
    ACTIVE = "ativa"
    SUSPENDED = "suspensa"


@dataclass(slots=True)
class Application:
    """Uma aplicação ou RPA que consome segredos sem pessoa envolvida."""

    name: Slug
    display_name: str
    description: str = ""
    owner_label: str = ""
    status: ApplicationStatus = ApplicationStatus.ACTIVE
    lease_minutos: int = LEASE_MINUTOS_PADRAO
    role_id: str = field(default_factory=new_id)
    # Papel que carrega as politicas desta aplicacao. Mesmo mecanismo das
    # pessoas, de proposito: um sistema de permissao paralelo so para robos
    # seria o que ninguem lembraria de revisar.
    papel_id: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("A aplicação precisa de um nome visível.")
        if not self.owner_label.strip():
            raise ValidationError(
                "A aplicação precisa de um responsável. Credencial de robô sem "
                "dono é credencial que ninguém revoga."
            )
        if self.lease_minutos < 1:
            raise ValidationError("O lease deve durar ao menos um minuto.")
        if self.lease_minutos > LEASE_MINUTOS_MAXIMO:
            raise ValidationError(
                f"O lease vai até {LEASE_MINUTOS_MAXIMO} minutos. Além disso "
                "deixa de ser empréstimo: um token comprometido daria um dia "
                "inteiro de acesso."
            )

    @property
    def path(self) -> PolicyPath:
        """Caminho de política da própria aplicação (administração dela)."""
        return PolicyPath(f"aplicacoes/{self.name}")

    @property
    def is_active(self) -> bool:
        return self.status is ApplicationStatus.ACTIVE

    def suspend(self) -> None:
        """Suspende: nenhuma autenticação nova, leases existentes seguem.

        Encerrar os leases ativos é operação separada e deliberada — suspender
        por engano não deve derrubar um robô no meio de um processamento.
        """
        self.status = ApplicationStatus.SUSPENDED

    def activate(self) -> None:
        self.status = ApplicationStatus.ACTIVE


@dataclass(slots=True)
class SecretId:
    """Credencial de autenticação da aplicação.

    Só o hash é persistido. O valor em claro existe uma vez, na emissão, e é
    entregue a quem configura o robô — o sistema não pode recuperá-lo depois,
    exatamente como uma senha.
    """

    application_id: str
    secret_hash: str
    label: str = ""
    created_by: str = ""
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    usos: int = 0
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if len(self.secret_hash) != 64:
            raise ValidationError("O hash do secret_id deve ter 64 caracteres.")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_valid(self, now: datetime | None = None) -> bool:
        if self.is_revoked:
            return False
        if self.expires_at is None:
            return True
        return (now or utcnow()) < self.expires_at

    def matches(self, apresentado: str) -> bool:
        """Compara em tempo constante.

        `==` vazaria, por tempo, quantos caracteres iniciais acertaram, e isso
        permitiria construir o segredo byte a byte.
        """
        return hmac.compare_digest(
            hashlib.sha256(apresentado.encode()).hexdigest(), self.secret_hash
        )

    def revoke(self, at: datetime | None = None) -> None:
        if self.is_revoked:
            raise ConflictError("Esta credencial já foi revogada.")
        self.revoked_at = at or utcnow()

    def registrar_uso(self, at: datetime | None = None) -> None:
        self.last_used_at = at or utcnow()
        self.usos += 1


def gerar_secret_id() -> tuple[str, str]:
    """Gera (valor_em_claro, hash). O valor não volta a existir depois."""
    valor = secrets.token_urlsafe(SECRET_ID_BYTES)
    return valor, hashlib.sha256(valor.encode()).hexdigest()


@dataclass(slots=True)
class Lease:
    """Acesso temporário concedido a uma aplicação autenticada.

    Carrega o escopo do que pode ser lido. O escopo vem da política da
    aplicação no momento da emissão e fica **congelado** no lease: alterar a
    política não amplia um lease já emitido, que é o que evita escalada
    silenciosa de privilégio em quem já está autenticado.
    """

    application_id: str
    secret_id_usado: str
    token_hash: str
    caminhos: list[str]
    capacidades: list[Capability]
    # Caminhos NEGADOS pela política da aplicação, congelados junto do escopo.
    # Sem eles o lease daria ao robô exatamente o acesso que a política nega:
    # um `allow` em `cofres/contabil/*` engoliria o `deny` em um segredo
    # específico, e a máquina teria mais permissão que a pessoa equivalente.
    negados: list[str] = field(default_factory=list)
    expires_at: datetime = field(default_factory=utcnow)
    revoked_at: datetime | None = None
    leituras: int = 0
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if len(self.token_hash) != 64:
            raise ValidationError("O hash do token deve ter 64 caracteres.")
        if not self.caminhos:
            raise ValidationError(
                "Lease sem escopo não serve para nada e esconde isso de quem "
                "o emitiu: recuse na emissão."
            )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_active(self, now: datetime | None = None) -> bool:
        return not self.is_revoked and (now or utcnow()) < self.expires_at

    def minutos_restantes(self, now: datetime | None = None) -> float | None:
        if not self.is_active(now):
            return None
        return round(
            (self.expires_at - (now or utcnow())).total_seconds() / 60, 1
        )

    def matches(self, token: str) -> bool:
        return hmac.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), self.token_hash
        )

    def cobre(self, caminho: PolicyPath, capacidade: Capability) -> bool:
        """O escopo congelado alcança este caminho?

        Casa por segmento, como as políticas: `cofres/conta` não cobre
        `cofres/contabil`.

        **Negação vence**, a mesma regra do resto do sistema. Um `allow` amplo
        não engole um `deny` específico — senão o robô teria mais acesso que a
        pessoa a quem a mesma política se aplica.
        """
        if capacidade not in self.capacidades:
            return False
        if any(PolicyPath(c).matches(caminho) for c in self.negados):
            return False
        return any(PolicyPath(c).matches(caminho) for c in self.caminhos)

    def revoke(self, at: datetime | None = None) -> None:
        if self.is_revoked:
            raise ConflictError("Este lease já foi revogado.")
        self.revoked_at = at or utcnow()

    def registrar_leitura(self) -> None:
        self.leituras += 1


def gerar_token_de_lease() -> tuple[str, str]:
    valor = secrets.token_urlsafe(32)
    return valor, hashlib.sha256(valor.encode()).hexdigest()


def emitir_lease(
    aplicacao: Application,
    secret_id: SecretId,
    caminhos: list[str],
    capacidades: list[Capability],
    negados: list[str] | None = None,
    now: datetime | None = None,
) -> tuple[Lease, str]:
    """Emite um lease para a aplicação. Devolve (lease, token_em_claro).

    Recusa aplicação suspensa e credencial inválida — e a mensagem é a mesma
    nos dois casos, para não contar a um atacante se o `role_id` existe.
    """
    if not aplicacao.is_active:
        raise ConflictError("Credenciais inválidas.")
    if not secret_id.is_valid(now):
        raise ConflictError("Credenciais inválidas.")

    agora = now or utcnow()
    token, token_hash = gerar_token_de_lease()
    lease = Lease(
        application_id=aplicacao.id,
        secret_id_usado=secret_id.id,
        token_hash=token_hash,
        caminhos=list(caminhos),
        capacidades=list(capacidades),
        negados=list(negados or []),
        expires_at=agora + timedelta(minutes=aplicacao.lease_minutos),
        created_at=agora,
    )
    return lease, token
