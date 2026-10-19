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


class AccessRequestModel(Base):
    """Solicitacao de acesso temporario.

    A concessao aprovada NAO vira regra de politica: vive aqui, com prazo, e a
    avaliacao a soma as politicas no momento da decisao. Assim ela caduca
    sozinha — ninguem precisa lembrar de remover, que e como acesso temporario
    vira permanente na pratica.
    """

    __tablename__ = "solicitacoes_acesso"

    id: Mapped[str] = _id_column()
    requester_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requester_label: Mapped[str] = mapped_column(String(254), nullable=False)
    path: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    hours: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pendente", nullable=False, index=True
    )
    # RESTRICT e nao SET NULL: perder quem decidiu apagaria a prestacao de
    # contas justamente do registro que existe para prestar contas.
    decided_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    decided_by_label: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    decision_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    granted_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = _now_column()


class VaultSealModel(Base):
    """Selo com quorum de um cofre.

    Guarda o HASH do token de desselagem, nunca o token: se guardasse, quem
    lesse o banco abriria o cofre sem precisar de quinhao nenhum — e o quorum
    nao protegeria de nada.

    Os quinhoes tambem nao estao aqui. Eles existem so no momento da emissao e
    vao para as pessoas; o sistema os esquece. Perder todos significa cofre que
    nao abre mais, e isso e a funcionalidade.
    """

    __tablename__ = "cofres_selos"

    id: Mapped[str] = _id_column()
    vault_id: Mapped[str] = mapped_column(
        ForeignKey("cofres.id", ondelete="CASCADE"), nullable=False, index=True
    )
    limiar: Mapped[int] = mapped_column(Integer, nullable=False)
    total_quinhoes: Mapped[int] = mapped_column(Integer, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    portadores: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    selado_por: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    selado_em: Mapped[datetime] = _now_column()
    # Preenchido ao desselar. O registro NAO e apagado: quem selou, quando e
    # quem abriu e exatamente o que uma auditoria quer ler depois.
    desselado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    desselado_por: Mapped[str] = mapped_column(String(254), default="", nullable=False)

    __table_args__ = (
        # Um unico selo ativo por cofre. Sem isto, duas selagens concorrentes
        # criariam dois conjuntos de quinhoes validos, e o segundo conjunto
        # abriria o cofre sem que os portadores do primeiro soubessem.
        Index(
            "uq_selo_ativo_por_cofre",
            "vault_id",
            unique=True,
            sqlite_where=text("desselado_em IS NULL"),
            postgresql_where=text("desselado_em IS NULL"),
        ),
    )


class ApplicationModel(Base):
    """Aplicacao ou RPA que consome segredos sem pessoa envolvida."""

    __tablename__ = "aplicacoes"

    id: Mapped[str] = _id_column()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner_label: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ativa", nullable=False)
    lease_minutos: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    # Publico por contrato: identifica, nao autentica. Pode ir no codigo do robo.
    role_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    # Papel que carrega as politicas desta aplicacao. RESTRICT: apagar um papel
    # que concede acesso a um robo em producao precisa ser decisao consciente,
    # nao efeito colateral de uma limpeza.
    application_role_id: Mapped[str | None] = mapped_column(
        ForeignKey("papeis.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = _now_column()


class SecretIdModel(Base):
    """Credencial de autenticacao de uma aplicacao.

    So o HASH e guardado. O valor em claro existe uma vez, na emissao — o
    sistema nao pode recupera-lo depois, exatamente como senha de pessoa.
    """

    __tablename__ = "aplicacoes_credenciais"

    id: Mapped[str] = _id_column()
    application_id: Mapped[str] = mapped_column(
        ForeignKey("aplicacoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    usos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = _now_column()


class LeaseModel(Base):
    """Acesso temporario concedido a uma aplicacao autenticada.

    `caminhos` e `capacidades` sao o escopo CONGELADO na emissao: alterar a
    politica depois nao amplia um lease ja emitido, o que evita escalada
    silenciosa em quem ja esta autenticado.
    """

    __tablename__ = "aplicacoes_leases"

    id: Mapped[str] = _id_column()
    application_id: Mapped[str] = mapped_column(
        ForeignKey("aplicacoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    secret_id_usado: Mapped[str] = mapped_column(
        ForeignKey("aplicacoes_credenciais.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    caminhos: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    capacidades: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    # Caminhos negados, congelados junto do escopo. Ver Lease.cobre.
    negados: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    leituras: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = _now_column()


class ConfiguracaoModel(Base):
    """Configuracao operacional da instalacao. Linha unica.

    A chave primaria fixa em "unica" e deliberada: configuracao por cofre ou
    por equipe produziria combinacoes que ninguem revisa, e a pergunta "qual
    prazo vale aqui?" deixaria de ter resposta unica.
    """

    __tablename__ = "configuracao"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default="unica")
    segundos_segredo_visivel: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    custodia_horas_padrao: Mapped[int] = mapped_column(
        Integer, default=4, nullable=False
    )
    alerta_certificado_dias: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    rotacao_dias_padrao: Mapped[int] = mapped_column(
        Integer, default=90, nullable=False
    )
    trilha_limite_padrao: Mapped[int] = mapped_column(
        Integer, default=200, nullable=False
    )
    atualizado_por: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    atualizado_em: Mapped[datetime] = _now_column()


class SessaoModel(Base):
    """Sessao privilegiada e sua gravacao.

    Os eventos ficam em tabela propria, nao num JSON aqui: uma sessao de uma
    hora tem milhares deles, e carregar tudo para listar as sessoes ativas
    seria o tipo de consulta que derruba a tela no primeiro mes de uso real.
    """

    __tablename__ = "sessoes"

    id: Mapped[str] = _id_column()
    usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    usuario_label: Mapped[str] = mapped_column(String(254), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    alvo: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    motivo: Mapped[str] = mapped_column(Text, default="", nullable=False)
    segredo_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(20), default="ativa", nullable=False, index=True
    )
    # Como a gravacao foi feita. Uma sessao capturada por proxy e outra
    # anotada a mao merecem confianca diferente numa investigacao.
    capturado_por: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    captura_automatica: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Referencia no armazenamento externo, preenchida ao encerrar.
    gravacao_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    gravacao_destino: Mapped[str] = mapped_column(
        String(100), default="", nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    iniciada_em: Mapped[datetime] = _now_column()
    ultima_atividade_em: Mapped[datetime] = _now_column()
    encerrada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    encerrada_por: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    motivo_encerramento: Mapped[str] = mapped_column(Text, default="", nullable=False)

    eventos: Mapped[list[EventoSessaoModel]] = relationship(
        back_populates="sessao", cascade="all, delete-orphan", lazy="selectin"
    )


class EventoSessaoModel(Base):
    """Um instante da gravacao."""

    __tablename__ = "sessoes_eventos"

    id: Mapped[str] = _id_column()
    sessao_id: Mapped[str] = mapped_column(
        ForeignKey("sessoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deslocamento_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)

    sessao: Mapped[SessaoModel] = relationship(back_populates="eventos")

    __table_args__ = (
        # A reproducao le em ordem; sem o indice, cada abertura de player
        # faria uma ordenacao completa.
        Index("ix_evento_sessao_ordem", "sessao_id", "deslocamento_ms"),
    )


class ConviteModel(Base):
    """Link de uso unico: convite de usuario ou redefinicao de senha.

    So o HASH do token e guardado. Se o token em claro ficasse aqui, um dump
    do banco entregaria um link que redefine a senha de qualquer pessoa.
    """

    __tablename__ = "convites"

    id: Mapped[str] = _id_column()
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    estado: Mapped[str] = mapped_column(
        String(20), default="pendente", nullable=False, index=True
    )
    nome_sugerido: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    papeis: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    criado_por: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    expira_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    usado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    criado_em: Mapped[datetime] = _now_column()


class PedidoRedefinicaoModel(Base):
    """Pedido de quem nao tem MFA e precisa da senha redefinida."""

    __tablename__ = "pedidos_redefinicao"

    id: Mapped[str] = _id_column()
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    motivo: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    atendido: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    atendido_por: Mapped[str] = mapped_column(String(254), default="", nullable=False)
    atendido_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    criado_em: Mapped[datetime] = _now_column()
