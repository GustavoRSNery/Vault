"""Rotas de acesso de máquina: aplicações, AppRole e leases.

Separadas das rotas de pessoa de propósito. Um RPA não tem sessão, não faz
MFA e não renova token por refresh — ele autentica com `role_id` +
`secret_id`, recebe um lease curto e o usa até expirar.

A rota `/maquina/segredo` é o ponto onde o robô lê de fato. Ela **não** passa
pelo `get_current_user`: o portador é a aplicação, não uma pessoa, e tratá-la
como usuário exigiria criar um usuário-robô — que é justamente o antipadrão
(conta de pessoa sem pessoa, que ninguém desliga e ninguém audita direito).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.machines.entities import (
    Application,
    SecretId,
    emitir_lease,
    gerar_secret_id,
)
from ...domain.shared.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from ...domain.shared.value_objects import PolicyPath, Slug
from ...infrastructure.crypto.envelope import EnvelopeCryptoService
from ...infrastructure.db.repositories import (
    ApplicationRepository,
    AuditRepository,
    LeaseRepository,
    PolicyRepository,
    SecretIdRepository,
    SecretRepository,
    UserRepository,
    VaultRepository,
)
from ..deps import (
    CurrentUser,
    get_audit,
    get_crypto,
    get_current_user,
    get_db,
    get_policies,
    get_secrets,
    get_vaults,
)

router = APIRouter(tags=["Acesso de máquina"])

CAMINHO_APLICACOES = PolicyPath("aplicacoes")

# Mensagem única para qualquer falha de autenticação de máquina: distinguir
# "role_id não existe" de "secret_id errado" conta ao atacante metade da
# resposta.
FALHA_AUTENTICACAO = "Credenciais inválidas."


def get_applications(db: Annotated[Session, Depends(get_db)]) -> ApplicationRepository:
    return ApplicationRepository(db)


def get_secret_ids(db: Annotated[Session, Depends(get_db)]) -> SecretIdRepository:
    return SecretIdRepository(db)


def get_leases(db: Annotated[Session, Depends(get_db)]) -> LeaseRepository:
    return LeaseRepository(db)


# ------------------------------------------------------------------ schemas


class AplicacaoResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    owner_label: str
    status: str
    lease_minutos: int
    role_id: str
    papel: str | None
    credenciais_ativas: int
    leases_ativos: int
    created_at: datetime


class CriarAplicacaoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    owner_label: str = Field(min_length=1, max_length=200)
    description: str = ""
    lease_minutos: int = Field(default=60, ge=1, le=720)
    papel: str | None = Field(default=None, max_length=64)


class CredencialEmitidaResponse(BaseModel):
    """O `secret_id` na única vez em que ele existe em claro."""

    id: str
    role_id: str
    secret_id: str
    label: str
    expires_at: datetime | None
    aviso: str


class CriarCredencialRequest(BaseModel):
    label: str = Field(default="", max_length=200)
    dias_de_validade: int | None = Field(default=None, ge=1, le=3650)


class CredencialResponse(BaseModel):
    id: str
    label: str
    created_by: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    usos: int
    valida: bool


class AutenticarRequest(BaseModel):
    role_id: str = Field(min_length=1, max_length=64)
    secret_id: str = Field(min_length=1, max_length=200)


class LeaseEmitidoResponse(BaseModel):
    token: str
    expires_at: datetime
    minutos: float
    caminhos: list[str]
    capacidades: list[str]
    negados: list[str]


class LeaseResponse(BaseModel):
    id: str
    caminhos: list[str]
    capacidades: list[str]
    negados: list[str]
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    leituras: int
    ativo: bool
    minutos_restantes: float | None


class LerSegredoRequest(BaseModel):
    cofre: str = Field(min_length=1, max_length=64)
    segredo: str = Field(min_length=1, max_length=64)


class SegredoResponse(BaseModel):
    cofre: str
    segredo: str
    versao: int
    valor: str


# ------------------------------------------------------------------ helpers


def _evento(
    actor_id: str | None,
    actor_label: str,
    action: AuditAction,
    target: str,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
    reason: str = "",
    ip: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        action=action,
        actor_id=actor_id,
        actor_label=actor_label,
        target_path=target,
        outcome=outcome,
        reason=reason,
        ip_address=ip,
    )


def _exigir_admin(
    current: CurrentUser,
    policies: PolicyRepository,
    audit: AuditRepository,
    db: Session,
    acao: str,
) -> None:
    if evaluate(
        policies.policies_for_user(current.id), CAMINHO_APLICACOES, Capability.ADMIN
    ):
        return
    audit.append(
        _evento(
            current.id, current.email, AuditAction.ACCESS_DENIED,
            str(CAMINHO_APLICACOES), AuditOutcome.FAILURE,
            f"Sem permissão para administrar aplicações: {acao}.",
            current.ip_address,
        )
    )
    db.commit()
    raise PermissionDeniedError("Esta área é restrita a quem administra aplicações.")


# -------------------------------------------------------------- aplicações


@router.get(
    "/aplicacoes", response_model=list[AplicacaoResponse], summary="Listar aplicações"
)
def listar_aplicacoes(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    leases: Annotated[LeaseRepository, Depends(get_leases)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AplicacaoResponse]:
    _exigir_admin(current, policies, audit, db, "listar")
    papeis = {p.id: p.name for p in UserRepository(db).list_roles()}
    return [
        _aplicacao_response(app, secret_ids, leases, papeis.get(app.papel_id))
        for app in apps.list_all()
    ]


@router.post(
    "/aplicacoes",
    response_model=AplicacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar aplicação",
)
def criar_aplicacao(
    payload: CriarAplicacaoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    leases: Annotated[LeaseRepository, Depends(get_leases)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> AplicacaoResponse:
    _exigir_admin(current, policies, audit, db, "cadastrar")
    papel_id = None
    if payload.papel:
        papel = next(
            (p for p in UserRepository(db).list_roles() if p.name == payload.papel),
            None,
        )
        if papel is None:
            raise NotFoundError(f"Papel '{payload.papel}' não existe.")
        papel_id = papel.id

    app = Application(
        name=Slug(payload.name),
        display_name=payload.display_name,
        owner_label=payload.owner_label,
        description=payload.description,
        lease_minutos=payload.lease_minutos,
        papel_id=papel_id,
    )
    apps.add(app)
    audit.append(
        _evento(
            current.id, current.email, AuditAction.APPLICATION_CREATED,
            str(app.path), reason=f"Responsável: {payload.owner_label}.",
            ip=current.ip_address,
        )
    )
    return _aplicacao_response(app, secret_ids, leases, payload.papel)


@router.post(
    "/aplicacoes/{nome}/credenciais",
    response_model=CredencialEmitidaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Emitir secret_id",
)
def emitir_credencial(
    nome: str,
    payload: CriarCredencialRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> CredencialEmitidaResponse:
    """Emite um `secret_id`. Ele aparece uma vez e não é guardado em claro.

    Várias credenciais podem coexistir de propósito: é assim que se rotaciona
    sem janela de indisponibilidade — emite a nova, atualiza o robô, revoga a
    antiga.
    """
    _exigir_admin(current, policies, audit, db, "emitir credencial")
    app = apps.get_by_name(Slug(nome))

    valor, digest = gerar_secret_id()
    expira = None
    if payload.dias_de_validade is not None:
        from datetime import timedelta

        from ...domain.shared.value_objects import utcnow

        expira = utcnow() + timedelta(days=payload.dias_de_validade)

    credencial = SecretId(
        application_id=app.id,
        secret_hash=digest,
        label=payload.label,
        created_by=current.email,
        expires_at=expira,
    )
    secret_ids.add(credencial)
    audit.append(
        _evento(
            current.id, current.email, AuditAction.APPLICATION_CREDENTIAL_ISSUED,
            str(app.path), reason=payload.label or "sem rótulo",
            ip=current.ip_address,
        )
    )

    return CredencialEmitidaResponse(
        id=credencial.id,
        role_id=app.role_id,
        secret_id=valor,
        label=payload.label,
        expires_at=expira,
        aviso=(
            "O secret_id aparece uma única vez. Guarde-o no gerenciador de "
            "segredos do robô agora — o sistema não poderá recuperá-lo."
        ),
    )


@router.get(
    "/aplicacoes/{nome}/credenciais",
    response_model=list[CredencialResponse],
    summary="Listar credenciais",
)
def listar_credenciais(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CredencialResponse]:
    _exigir_admin(current, policies, audit, db, "listar credenciais")
    app = apps.get_by_name(Slug(nome))
    return [
        CredencialResponse(
            id=c.id,
            label=c.label,
            created_by=c.created_by,
            created_at=c.created_at,
            expires_at=c.expires_at,
            revoked_at=c.revoked_at,
            last_used_at=c.last_used_at,
            usos=c.usos,
            valida=c.is_valid(),
        )
        for c in secret_ids.list_for_application(app.id)
    ]


@router.post(
    "/aplicacoes/{nome}/credenciais/{credencial_id}/revogar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revogar credencial",
)
def revogar_credencial(
    nome: str,
    credencial_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    _exigir_admin(current, policies, audit, db, "revogar credencial")
    app = apps.get_by_name(Slug(nome))

    alvo = next(
        (c for c in secret_ids.list_for_application(app.id) if c.id == credencial_id),
        None,
    )
    if alvo is None:
        raise NotFoundError("Credencial não encontrada.")

    alvo.revoke()
    secret_ids.save(alvo)
    audit.append(
        _evento(
            current.id, current.email, AuditAction.APPLICATION_CREDENTIAL_REVOKED,
            str(app.path), reason=alvo.label or "sem rótulo", ip=current.ip_address,
        )
    )


@router.post(
    "/aplicacoes/{nome}/leases/revogar-todos",
    summary="Revogar todos os leases ativos",
)
def revogar_leases(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    leases: Annotated[LeaseRepository, Depends(get_leases)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """Botão de emergência: suspeita de robô comprometido fecha tudo agora."""
    _exigir_admin(current, policies, audit, db, "revogar leases")
    app = apps.get_by_name(Slug(nome))
    quantos = leases.revogar_todos(app.id)
    audit.append(
        _evento(
            current.id, current.email, AuditAction.APPLICATION_LEASES_REVOKED,
            str(app.path), reason=f"{quantos} lease(s) encerrados.",
            ip=current.ip_address,
        )
    )
    return {"revogados": quantos}


@router.get(
    "/aplicacoes/{nome}/leases",
    response_model=list[LeaseResponse],
    summary="Leases da aplicação",
)
def listar_leases(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    leases: Annotated[LeaseRepository, Depends(get_leases)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[LeaseResponse]:
    _exigir_admin(current, policies, audit, db, "listar leases")
    app = apps.get_by_name(Slug(nome))
    return [
        LeaseResponse(
            id=lease.id,
            caminhos=lease.caminhos,
            capacidades=[str(c) for c in lease.capacidades],
            negados=lease.negados,
            created_at=lease.created_at,
            expires_at=lease.expires_at,
            revoked_at=lease.revoked_at,
            leituras=lease.leituras,
            ativo=lease.is_active(),
            minutos_restantes=lease.minutos_restantes(),
        )
        for lease in leases.list_for_application(app.id)
    ]


# ------------------------------------------------- o que o robô de fato usa


@router.post(
    "/maquina/autenticar",
    response_model=LeaseEmitidoResponse,
    summary="Autenticar aplicação (AppRole)",
)
def autenticar(
    payload: AutenticarRequest,
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    leases: Annotated[LeaseRepository, Depends(get_leases)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> LeaseEmitidoResponse:
    """Troca `role_id` + `secret_id` por um lease de curta duração.

    O escopo do lease é lido da política da aplicação AGORA e congelado: o
    robô não ganha acesso novo sem reautenticar, mesmo que a política mude.
    """
    app = apps.get_by_role_id(payload.role_id)
    if app is None:
        # Registra sem actor_id: não há usuário, e o role_id apresentado pode
        # ser lixo. O evento importa — tentativa de autenticação com role_id
        # inexistente é sinal de varredura.
        audit.append(
            _evento(
                None, f"maquina:{payload.role_id[:12]}", AuditAction.LOGIN_FAILURE,
                str(CAMINHO_APLICACOES), AuditOutcome.FAILURE,
                "role_id desconhecido.",
            )
        )
        db.commit()
        raise AuthenticationError(FALHA_AUTENTICACAO)

    credencial = secret_ids.find_valid(app.id, payload.secret_id)
    if credencial is None:
        audit.append(
            _evento(
                None, f"maquina:{app.name}", AuditAction.LOGIN_FAILURE,
                str(app.path), AuditOutcome.FAILURE, "secret_id inválido.",
            )
        )
        db.commit()
        raise AuthenticationError(FALHA_AUTENTICACAO)

    # O escopo vem da política da APLICAÇÃO, não de um usuário.
    caminhos, capacidades, negados = _escopo_da_aplicacao(app, policies)
    if not caminhos:
        audit.append(
            _evento(
                None, f"maquina:{app.name}", AuditAction.LOGIN_FAILURE,
                str(app.path), AuditOutcome.FAILURE,
                "Aplicação sem política: nada a conceder.",
            )
        )
        db.commit()
        raise PermissionDeniedError(
            "Esta aplicação não tem nenhuma política atribuída. Um lease sem "
            "escopo não serviria para nada."
        )

    try:
        lease, token = emitir_lease(
            app, credencial, caminhos, capacidades, negados
        )
    except ConflictError:
        audit.append(
            _evento(
                None, f"maquina:{app.name}", AuditAction.LOGIN_FAILURE,
                str(app.path), AuditOutcome.FAILURE, "Aplicação suspensa.",
            )
        )
        db.commit()
        raise AuthenticationError(FALHA_AUTENTICACAO) from None

    leases.add(lease)
    credencial.registrar_uso()
    secret_ids.save(credencial)
    audit.append(
        _evento(
            None, f"maquina:{app.name}", AuditAction.APPLICATION_AUTHENTICATED,
            str(app.path),
            reason=f"Lease de {app.lease_minutos} min em {', '.join(caminhos)}.",
        )
    )

    return LeaseEmitidoResponse(
        token=token,
        expires_at=lease.expires_at,
        minutos=float(app.lease_minutos),
        caminhos=lease.caminhos,
        capacidades=[str(c) for c in lease.capacidades],
        negados=lease.negados,
    )


@router.post(
    "/maquina/segredo",
    response_model=SegredoResponse,
    summary="Ler segredo com lease",
)
def ler_segredo(
    payload: LerSegredoRequest,
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    leases: Annotated[LeaseRepository, Depends(get_leases)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    crypto: Annotated[EnvelopeCryptoService, Depends(get_crypto)],
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> SegredoResponse:
    """Lê um segredo usando o token do lease.

    Não passa por `get_current_user`: o portador é a aplicação. Tratá-la como
    usuário exigiria um usuário-robô — conta de pessoa sem pessoa, que ninguém
    desliga quando o robô é aposentado.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError(FALHA_AUTENTICACAO)

    token = authorization.split(" ", 1)[1].strip()
    lease = leases.find_by_token(token)
    if lease is None or not lease.is_active():
        raise AuthenticationError("Lease inválido ou expirado.")

    cofre = vaults.get_by_name(Slug(payload.cofre))
    nome_segredo = Slug(payload.segredo)
    caminho = cofre.secret_path(nome_segredo)

    if not lease.cobre(caminho, Capability.REVEAL):
        audit.append(
            _evento(
                None, _rotulo_da_aplicacao(apps, lease), AuditAction.ACCESS_DENIED,
                str(caminho), AuditOutcome.FAILURE,
                "Fora do escopo do lease.",
            )
        )
        db.commit()
        raise PermissionDeniedError(
            "Este lease não alcança este segredo. O escopo foi fixado na "
            "autenticação; reautentique se a política mudou."
        )

    cofre.ensure_usable()
    segredo = secrets.get_in_vault(cofre.id, nome_segredo)
    if segredo.is_deleted:
        raise NotFoundError("Segredo não encontrado.")

    versao = segredo.current_version
    valor = crypto.decrypt(versao.value)

    lease.registrar_leitura()
    leases.save(lease)
    audit.append(
        _evento(
            None, _rotulo_da_aplicacao(apps, lease), AuditAction.SECRET_REVEALED,
            str(caminho), reason="Leitura por aplicação, via lease.",
        )
    )

    return SegredoResponse(
        cofre=str(cofre.name),
        segredo=str(segredo.name),
        versao=versao.version,
        valor=valor,
    )


# ----------------------------------------------------------------- helpers


def _escopo_da_aplicacao(
    app: Application, policies: PolicyRepository
) -> tuple[list[str], list[Capability], list[str]]:
    """Lê o escopo da aplicação do papel atribuído a ela.

    Mesmo mecanismo das pessoas: a aplicação recebe um papel, o papel carrega
    políticas. Assim o editor de políticas vale para os dois, em vez de haver
    um sistema de permissão paralelo que ninguém lembra de revisar.

    Devolve (permitidos, capacidades, negados). As negações viajam junto: um
    `allow` amplo não pode engolir um `deny` específico, senão o robô teria
    mais acesso que a pessoa a quem a mesma política se aplica. Descartar o
    `deny` aqui foi um bug real, encontrado validando no ambiente.
    """
    from ...domain.access.policy import Effect

    caminhos: list[str] = []
    negados: list[str] = []
    capacidades: set[Capability] = set()

    for politica in policies.policies_for_application(app.papel_id):
        for regra in politica.rules:
            caminho = str(regra.path)
            if regra.effect is Effect.ALLOW:
                if caminho not in caminhos:
                    caminhos.append(caminho)
                capacidades.update(regra.capabilities)
            elif caminho not in negados:
                negados.append(caminho)

    return caminhos, sorted(capacidades, key=str), negados


def _rotulo_da_aplicacao(apps: ApplicationRepository, lease) -> str:  # noqa: ANN001
    for app in apps.list_all():
        if app.id == lease.application_id:
            return f"maquina:{app.name}"
    return "maquina:desconhecida"


def _aplicacao_response(
    app: Application,
    secret_ids: SecretIdRepository,
    leases: LeaseRepository,
    papel_nome: str | None = None,
) -> AplicacaoResponse:
    credenciais = secret_ids.list_for_application(app.id)
    ativos = [lease for lease in leases.list_for_application(app.id) if lease.is_active()]
    return AplicacaoResponse(
        id=app.id,
        name=str(app.name),
        display_name=app.display_name,
        description=app.description,
        owner_label=app.owner_label,
        status=str(app.status),
        lease_minutos=app.lease_minutos,
        role_id=app.role_id,
        papel=papel_nome,
        credenciais_ativas=sum(1 for c in credenciais if c.is_valid()),
        leases_ativos=len(ativos),
        created_at=app.created_at,
    )
