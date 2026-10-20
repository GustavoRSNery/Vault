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

from fastapi import APIRouter, Depends, Header, Query, status
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


class LinhaConsumo(BaseModel):
    caminho: str
    leituras: int
    ultima: datetime
    # Que tipo de segredo é este caminho: senha, chave de API, certificado.
    # Sem isto a tela mostra uma lista de strings que ninguém consegue
    # julgar; com isto, dá para ver que um robô lê três senhas e uma chave.
    tipo: str = "desconhecido"
    cofre: str = ""


class ConsumoResponse(BaseModel):
    """O que a aplicação leu, e o que tentou ler sem conseguir.

    As duas listas importam. Só a de leituras diria qual escopo está em uso;
    a de negativas diz onde o escopo está mal dimensionado — ou onde um robô
    pede o que não deveria, que é o sinal que uma revisão procura.
    """

    aplicacao: str
    dias: int
    lidos: list[LinhaConsumo]
    negados: list[LinhaConsumo]
    caminhos_no_escopo: list[str]
    nunca_lidos: list[str]
    # Quantos caminhos de cada tipo o robô consome. É o resumo que responde
    # "que tipo de credencial esta aplicação usa?" sem ler a lista inteira.
    por_tipo: dict[str, int] = {}


class RenovarRequest(BaseModel):
    """O robô apresenta a credencial atual e recebe a próxima."""

    role_id: str = Field(min_length=1, max_length=64)
    secret_id: str = Field(min_length=1, max_length=200)
    dias_de_validade: int | None = Field(default=None, ge=1, le=3650)


class RenovacaoResponse(BaseModel):
    secret_id: str
    expires_at: datetime | None
    anterior_vale_ate: datetime
    aviso: str


class CredencialVencendo(BaseModel):
    aplicacao: str
    responsavel: str
    credencial_id: str
    label: str
    dias_para_vencer: int | None
    ultimo_uso: datetime | None
    nunca_usada: bool


class VencimentosResponse(BaseModel):
    """Credenciais que vencem em breve, e as que nunca foram usadas.

    As duas listas pedem ação diferente: a primeira é renovar antes que o
    robô pare; a segunda é apagar, porque credencial emitida e nunca usada é
    credencial que alguém esqueceu — e ela autentica do mesmo jeito.
    """

    dias: int
    vencendo: list[CredencialVencendo]
    nunca_usadas: list[CredencialVencendo]


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


@router.get(
    "/aplicacoes/{nome}/consumo",
    response_model=ConsumoResponse,
    summary="O que a aplicação leu",
)
def consumo_da_aplicacao(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    leases: Annotated[LeaseRepository, Depends(get_leases)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
    dias: Annotated[int, Query(ge=1, le=365)] = 30,
) -> ConsumoResponse:
    """Consumo derivado da trilha, não de um contador próprio.

    A trilha já é a fonte de verdade do que foi lido; um contador paralelo
    divergiria dela no primeiro erro de escrita.

    `nunca_lidos` é o que justifica a tela: caminho no escopo que o robô nunca
    leu é escopo a enxugar. Permissão que ninguém usa é só superfície de
    ataque esperando um comprometimento.
    """
    _exigir_admin(current, policies, audit, db, "ver consumo")
    app = apps.get_by_name(Slug(nome))

    from datetime import timedelta

    from ...domain.shared.value_objects import utcnow

    desde = utcnow() - timedelta(days=dias)
    rotulo = f"maquina:{app.name}"

    lidos = audit.consumo_por_ator(rotulo, desde=desde)
    negados = audit.negados_por_ator(rotulo, desde=desde)

    # Resolve caminho -> tipo numa consulta só. Caminho que não casa com
    # segredo existente fica "desconhecido" em vez de sumir: pode ser um
    # segredo apagado depois da leitura, e esconder isso apagaria justamente
    # o rastro que a revisão procura.
    tipos = secrets.tipos_por_caminho()

    def _classificar(caminho: str) -> tuple[str, str]:
        return tipos.get(caminho, ("desconhecido", ""))

    # O escopo é o do último lease emitido: é o que vale hoje para o robô.
    historico = leases.list_for_application(app.id)
    escopo = historico[0].caminhos if historico else []

    # Caminho concedido que nunca apareceu numa leitura.
    #
    # Um padrão sem curinga (`cofres/contabil`) casa só com o caminho exato,
    # e segredos vivem em `cofres/contabil/segredos/x`. Sem tratar isso, o
    # cofre apareceria como "nunca lido" mesmo com todas as leituras dentro
    # dele — um alerta mandando enxugar escopo em uso, que é pior do que não
    # alertar: ensina a ignorar o aviso.
    lidos_set = {caminho for caminho, _, _ in lidos}

    def _alcancou(padrao: str) -> bool:
        alvo = PolicyPath(padrao)
        if any(alvo.matches(PolicyPath(c)) for c in lidos_set):
            return True
        if alvo.has_wildcard:
            return False
        # Sem curinga: conta também o que foi lido SOB este caminho.
        prefixo = f"{padrao}/"
        return any(c.startswith(prefixo) for c in lidos_set)

    nunca = [padrao for padrao in escopo if not _alcancou(padrao)]

    return ConsumoResponse(
        aplicacao=str(app.name),
        dias=dias,
        lidos=[
            LinhaConsumo(
                caminho=c, leituras=q, ultima=u,
                tipo=_classificar(c)[0], cofre=_classificar(c)[1],
            )
            for c, q, u in lidos
        ],
        negados=[
            LinhaConsumo(
                caminho=c, leituras=q, ultima=u,
                tipo=_classificar(c)[0], cofre=_classificar(c)[1],
            )
            for c, q, u in negados
        ],
        por_tipo=_contar_por_tipo([c for c, _, _ in lidos], _classificar),
        caminhos_no_escopo=escopo,
        nunca_lidos=nunca,
    )


def _contar_por_tipo(caminhos, classificar) -> dict[str, int]:  # noqa: ANN001
    """Quantos caminhos distintos de cada tipo.

    Conta caminhos, não leituras: um robô que lê a mesma senha mil vezes usa
    uma senha, e somar as leituras faria essa senha parecer o grosso do
    escopo quando o que a revisão quer saber é *quantas coisas* ele alcança.
    """
    contagem: dict[str, int] = {}
    for caminho in caminhos:
        tipo = classificar(caminho)[0]
        contagem[tipo] = contagem.get(tipo, 0) + 1
    return contagem


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
    "/maquina/renovar",
    response_model=RenovacaoResponse,
    summary="Trocar a própria credencial",
)
def renovar_credencial(
    payload: RenovarRequest,
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> RenovacaoResponse:
    """O robô troca a própria credencial, autenticando com a atual.

    Deliberadamente **sem agendador interno**: um processo de rotação dentro
    do Vault competiria com o orquestrador que a empresa já tem, e um cofre
    com cron embutido é mais uma coisa para monitorar. Quem sabe quando é
    seguro trocar é o próprio robô — entre dois ciclos de trabalho, não no
    meio de um.

    A credencial antiga não morre na hora: ganha alguns minutos de graça, para
    que um ciclo em andamento com ela em memória não seja derrubado pela
    própria rotação.
    """
    app = apps.get_by_role_id(payload.role_id)
    if app is None:
        audit.append(
            _evento(
                None, f"maquina:{payload.role_id[:12]}", AuditAction.LOGIN_FAILURE,
                str(CAMINHO_APLICACOES), AuditOutcome.FAILURE,
                "role_id desconhecido na renovação.",
            )
        )
        db.commit()
        raise AuthenticationError(FALHA_AUTENTICACAO)

    atual = secret_ids.find_valid(app.id, payload.secret_id)
    if atual is None:
        audit.append(
            _evento(
                None, f"maquina:{app.name}", AuditAction.LOGIN_FAILURE,
                str(app.path), AuditOutcome.FAILURE,
                "secret_id inválido na renovação.",
            )
        )
        db.commit()
        raise AuthenticationError(FALHA_AUTENTICACAO)

    if not app.is_active:
        raise AuthenticationError(FALHA_AUTENTICACAO)

    # Nova credencial primeiro: se a emissão falhar, a antiga continua
    # intacta e o robô segue funcionando.
    valor, digest = gerar_secret_id()
    expira = None
    if payload.dias_de_validade is not None:
        from datetime import timedelta

        from ...domain.shared.value_objects import utcnow as _agora

        expira = _agora() + timedelta(days=payload.dias_de_validade)

    nova = SecretId(
        application_id=app.id,
        secret_hash=digest,
        label=f"renovada de {atual.label or atual.id[:8]}",
        created_by=f"maquina:{app.name}",
        expires_at=expira,
    )
    secret_ids.add(nova)

    vale_ate = atual.aposentar_com_graca()
    secret_ids.save(atual)

    audit.append(
        _evento(
            None, f"maquina:{app.name}", AuditAction.APPLICATION_CREDENTIAL_ROTATED,
            str(app.path),
            reason=f"Credencial trocada pelo próprio robô; anterior vale até {vale_ate:%d/%m %H:%M}.",
        )
    )

    return RenovacaoResponse(
        secret_id=valor,
        expires_at=expira,
        anterior_vale_ate=vale_ate,
        aviso=(
            "Guarde a credencial nova agora. A anterior continua valendo por "
            "poucos minutos, só para não derrubar um ciclo em andamento."
        ),
    )


@router.get(
    "/aplicacoes-vencimentos",
    response_model=VencimentosResponse,
    summary="Credenciais vencendo e ociosas",
)
def vencimentos(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    apps: Annotated[ApplicationRepository, Depends(get_applications)],
    secret_ids: Annotated[SecretIdRepository, Depends(get_secret_ids)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
    dias: Annotated[int, Query(ge=1, le=365)] = 30,
) -> VencimentosResponse:
    """O que precisa de ação antes que um robô pare — ou vaze.

    Credencial nunca usada aparece em lista própria porque o problema dela é
    outro: não é "vai vencer", é "alguém emitiu e esqueceu" — e ela autentica
    do mesmo jeito que as em uso.
    """
    _exigir_admin(current, policies, audit, db, "ver vencimentos")

    vencendo: list[CredencialVencendo] = []
    ociosas: list[CredencialVencendo] = []

    for app in apps.list_all():
        for credencial in secret_ids.list_for_application(app.id):
            if not credencial.is_valid():
                continue
            linha = CredencialVencendo(
                aplicacao=str(app.name),
                responsavel=app.owner_label,
                credencial_id=credencial.id,
                label=credencial.label,
                dias_para_vencer=credencial.dias_para_vencer(),
                ultimo_uso=credencial.last_used_at,
                nunca_usada=credencial.usos == 0,
            )
            restantes = credencial.dias_para_vencer()
            if restantes is not None and restantes <= dias:
                vencendo.append(linha)
            if credencial.usos == 0:
                ociosas.append(linha)

    vencendo.sort(key=lambda c: c.dias_para_vencer or 0)
    return VencimentosResponse(dias=dias, vencendo=vencendo, nunca_usadas=ociosas)


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

    # O escopo é checado ANTES de resolver o cofre, de propósito: resolver
    # primeiro faria a resposta distinguir "cofre não existe" de "fora do seu
    # escopo", e um robô comprometido mapearia os cofres pela mensagem de erro
    # sem ter permissão nenhuma.
    nome_segredo = Slug(payload.segredo)
    caminho = PolicyPath(
        f"cofres/{Slug(payload.cofre)}/segredos/{nome_segredo}"
    )

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

    cofre = vaults.get_by_name(Slug(payload.cofre))
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
