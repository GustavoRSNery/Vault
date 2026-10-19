"""Models SQLAlchemy.

Estes objetos são da infraestrutura: existem para persistir, não para carregar
regra. O domínio não os importa — os repositórios traduzem model↔entidade.

Nenhuma coluna guarda segredo em claro. O valor vive em `ciphertext`, com o
nonce e a DEK protegida ao lado; quem ler o banco direto não lê senha nenhuma.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ...domain.shared.value_objects import new_id, utcnow


class Base(DeclarativeBase):
    pass


def _id_column() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=new_id)


def _now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserModel(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = _id_column()
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Segredo do TOTP: cifrado, nunca em claro — quem lê o banco não clona o MFA.
    mfa_secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    mfa_secret_nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    mfa_secret_wrapped_dek: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    mfa_key_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = _now_column()

    roles: Mapped[list[RoleModel]] = relationship(
        secondary="usuarios_papeis", back_populates="users", lazy="selectin"
    )


class RoleModel(Base):
    __tablename__ = "papeis"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = _now_column()

    users: Mapped[list[UserModel]] = relationship(
        secondary="usuarios_papeis", back_populates="roles"
    )
    policies: Mapped[list[PolicyModel]] = relationship(
        secondary="papeis_politicas", back_populates="roles", lazy="selectin"
    )


class UserRoleModel(Base):
    __tablename__ = "usuarios_papeis"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(
        ForeignKey("papeis.id", ondelete="CASCADE"), primary_key=True
    )


class PolicyModel(Base):
    __tablename__ = "politicas"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = _now_column()

    rules: Mapped[list[PolicyRuleModel]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", lazy="selectin"
    )
    roles: Mapped[list[RoleModel]] = relationship(
        secondary="papeis_politicas", back_populates="policies"
    )


class PolicyRuleModel(Base):
    __tablename__ = "politicas_regras"

    id: Mapped[str] = _id_column()
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("politicas.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(256), nullable=False)
    # Lista de capacidades; JSON para não criar uma tabela de 1 coluna.
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    effect: Mapped[str] = mapped_column(String(10), nullable=False, default="allow")

    policy: Mapped[PolicyModel] = relationship(back_populates="rules")


class RolePolicyModel(Base):
    __tablename__ = "papeis_politicas"

    role_id: Mapped[str] = mapped_column(
        ForeignKey("papeis.id", ondelete="CASCADE"), primary_key=True
    )
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("politicas.id", ondelete="CASCADE"), primary_key=True
    )


class VaultModel(Base):
    __tablename__ = "cofres"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="ativo", nullable=False)
    created_at: Mapped[datetime] = _now_column()

    secrets: Mapped[list[SecretModel]] = relationship(
        back_populates="vault", cascade="all, delete-orphan"
    )


class SecretModel(Base):
    __tablename__ = "segredos"
    __table_args__ = (
        # Dois segredos com o mesmo nome no mesmo cofre seriam ambíguos no
        # caminho de política: "cofres/x/segredos/y" precisa apontar para um só.
        UniqueConstraint("vault_id", "name", name="uq_segredo_nome_por_cofre"),
        Index("ix_segredo_cofre_ativo", "vault_id", "deleted_at"),
    )

    id: Mapped[str] = _id_column()
    vault_id: Mapped[str] = mapped_column(
        ForeignKey("cofres.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="senha", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _now_column()

    vault: Mapped[VaultModel] = relationship(back_populates="secrets")
    versions: Mapped[list[SecretVersionModel]] = relationship(
        back_populates="secret", cascade="all, delete-orphan", lazy="selectin"
    )


class SecretVersionModel(Base):
    __tablename__ = "segredos_versoes"
    __table_args__ = (
        UniqueConstraint("secret_id", "version", name="uq_versao_por_segredo"),
    )

    id: Mapped[str] = _id_column()
    secret_id: Mapped[str] = mapped_column(
        ForeignKey("segredos.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = _now_column()

    secret: Mapped[SecretModel] = relationship(back_populates="versions")


class AuditEventModel(Base):
    __tablename__ = "auditoria_eventos"
    __table_args__ = (
        UniqueConstraint("sequence", name="uq_auditoria_sequencia"),
        Index("ix_auditoria_ocorrido", "occurred_at"),
        Index("ix_auditoria_ator", "actor_id"),
    )

    id: Mapped[str] = _id_column()
    # A sequência é global e sem buraco: é o que torna a cadeia verificável.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_label: Mapped[str] = mapped_column(String(254), nullable=False)
    target_path: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="sucesso")
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = _now_column()


class AuditAnchorModel(Base):
    """Âncora externa espelhada localmente.

    A cópia que vale é a de fora (SIEM, bucket somente-anexação); esta existe
    para a verificação não precisar de rede. Divergência entre as duas é, por
    si, um sinal de adulteração.
    """

    __tablename__ = "auditoria_ancoras"

    id: Mapped[str] = _id_column()
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    exported_to: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = _now_column()


class DeviceModel(Base):
    """Dispositivo do inventário: servidor, roteador, banco, aplicação."""

    __tablename__ = "dispositivos"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="outro")
    address: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _now_column()

    credentials: Mapped[list[CredentialModel]] = relationship(
        back_populates="device", cascade="all, delete-orphan", lazy="selectin"
    )


class CredentialModel(Base):
    """Credencial de um dispositivo, com prazo de rotação e custódia.

    O valor não mora aqui: `secret_id` aponta para o segredo cifrado no cofre.
    Esta tabela guarda o governo da credencial, não a credencial.
    """

    __tablename__ = "credenciais"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("dispositivos.id", ondelete="CASCADE"), nullable=False
    )
    # SET NULL e não CASCADE: excluir o segredo não deve apagar o histórico de
    # rotação e custódia da credencial — é justamente o que a auditoria quer.
    secret_id: Mapped[str | None] = mapped_column(
        ForeignKey("segredos.id", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rotation_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    last_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="ativa", nullable=False)
    created_at: Mapped[datetime] = _now_column()

    device: Mapped[DeviceModel] = relationship(back_populates="credentials")
    checkouts: Mapped[list[CheckoutModel]] = relationship(
        back_populates="credential", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        # Nome único por dispositivo, não global: "senha-root" existe em vários.
        UniqueConstraint("device_id", "name", name="uq_credencial_por_dispositivo"),
    )


class CheckoutModel(Base):
    """Retirada de credencial para uso exclusivo.

    A exclusividade é regra de domínio, mas o índice parcial abaixo a apoia no
    banco: sem ele, duas requisições concorrentes abririam duas retiradas e o
    domínio só perceberia na leitura seguinte.
    """

    __tablename__ = "credenciais_custodias"

    id: Mapped[str] = _id_column()
    credential_id: Mapped[str] = mapped_column(
        ForeignKey("credenciais.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    user_label: Mapped[str] = mapped_column(String(254), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    taken_at: Mapped[datetime] = _now_column()
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    credential: Mapped[CredentialModel] = relationship(back_populates="checkouts")

    __table_args__ = (
        Index("ix_custodia_credencial", "credential_id"),
        # Uma única retirada aberta por credencial. O índice é parcial: as
        # devolvidas (returned_at preenchido) ficam fora da restrição.
        Index(
            "uq_custodia_aberta",
            "credential_id",
            unique=True,
            sqlite_where=text("returned_at IS NULL"),
            postgresql_where=text("returned_at IS NULL"),
        ),
    )


class CertificateModel(Base):
    """Certificado digital: metadados e validade.

    A chave privada, quando guardada, é segredo cifrado no cofre. Aqui ela
    ficaria legível para quem só precisa acompanhar vencimento.
    """

    __tablename__ = "certificados"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    issuer: Mapped[str] = mapped_column(String(300), nullable=False)
    serial: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    owner_label: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    not_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    secret_id: Mapped[str | None] = mapped_column(
        ForeignKey("segredos.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = _now_column()
