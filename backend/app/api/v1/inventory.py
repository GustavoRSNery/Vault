"""Rotas do inventário: dispositivos, credenciais e certificados.

Separado de `vaults.py` de propósito. Cofre guarda o *valor* de um segredo;
inventário guarda o *governo* dele — de qual equipamento é, quando foi trocado,
quem está com ele, quando o certificado vence. São caminhos de política
distintos (`dispositivos`, `credenciais`, `certificados`), então quem acompanha
vencimento não precisa de permissão para revelar senha.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.inventory.entities import (
    AcessoRemoto,
    Certificate,
    Credential,
    Device,
    DeviceKind,
    MetodoDeAcesso,
    montar_arquivo_rdp,
)
from ...domain.shared.errors import (
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from ...domain.shared.value_objects import PolicyPath, Slug
from ...domain.vaults.entities import Secret, SecretKind
from ...infrastructure.crypto.envelope import EnvelopeCryptoService
from ...infrastructure.db.repositories import (
    AuditRepository,
    ConfiguracaoRepository,
    CertificateRepository,
    CredentialRepository,
    DeviceRepository,
    PolicyRepository,
    SecretRepository,
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

router = APIRouter(tags=["Inventário"])


def get_devices(db: Annotated[Session, Depends(get_db)]) -> DeviceRepository:
    return DeviceRepository(db)


def get_credentials(db: Annotated[Session, Depends(get_db)]) -> CredentialRepository:
    return CredentialRepository(db)


def get_certificates(db: Annotated[Session, Depends(get_db)]) -> CertificateRepository:
    return CertificateRepository(db)


# ------------------------------------------------------------------ schemas


class DispositivoResponse(BaseModel):
    id: str
    name: str
    display_name: str
    kind: str
    address: str
    tags: list[str]
    description: str
    acessos: list[AcessoResponse]
    is_active: bool
    credenciais: int
    created_at: datetime


class CriarDispositivoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    kind: DeviceKind = DeviceKind.OTHER
    address: str = ""
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class AcessoResponse(BaseModel):
    """Uma forma de alcançar o dispositivo.

    O identificador é visível de propósito: ele diz *onde* a máquina está,
    não *como* entrar nela. A senha continua no cofre, mascarada.
    """

    metodo: str
    identificador: str
    porta: int | None
    usuario_sugerido: str
    observacao: str
    # A tela usa estes dois para escolher entre botão de download, link ou
    # só copiar — em vez de deduzir pelo nome do método.
    suporta_arquivo_rdp: bool
    link: str | None


class AcessoPayload(BaseModel):
    metodo: MetodoDeAcesso
    identificador: str = Field(min_length=1, max_length=200)
    porta: int | None = Field(default=None, ge=1, le=65535)
    usuario_sugerido: str = Field(default="", max_length=100)
    observacao: str = Field(default="", max_length=300)


class DefinirAcessosRequest(BaseModel):
    """Conjunto completo. É substituição, não merge."""

    acessos: list[AcessoPayload] = Field(default_factory=list, max_length=10)


class CustodiaResponse(BaseModel):
    id: str
    user_label: str
    reason: str
    taken_at: datetime
    due_at: datetime
    returned_at: datetime | None
    em_atraso: bool


class CredencialResponse(BaseModel):
    """Governo da credencial. Nunca o valor — isso é `/revelar` no cofre."""

    id: str
    name: str
    device_id: str
    device_name: str
    username: str
    description: str
    status: str
    rotation_days: int
    last_rotated_at: datetime | None
    due_at: datetime | None
    dias_para_vencer: int | None
    atrasada: bool
    custodia_aberta: CustodiaResponse | None
    historico: list[CustodiaResponse]


class CriarCredencialRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    username: str = ""
    description: str = ""
    rotation_days: int = Field(default=90, ge=0, le=3650)
    secret_id: str | None = None


class RetirarRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    # None usa o prazo padrão da configuração; o teto continua no domínio.
    hours: int | None = Field(default=None, ge=1, le=720)


class DevolverRequest(BaseModel):
    """`force` é a devolução por administrador: quem retirou está indisponível."""

    force: bool = False


class CertificadoResponse(BaseModel):
    id: str
    name: str
    display_name: str
    subject: str
    issuer: str
    serial: str
    owner_label: str
    not_before: datetime
    not_after: datetime
    description: str
    estado: str
    dias_restantes: int
    # **Se há arquivo guardado, nunca o arquivo.** A tela precisa saber se
    # oferece "baixar" ou "enviar"; o conteúdo exige a rota própria, que
    # audita cada download.
    tem_arquivo: bool
    arquivo_nome: str
    arquivo_cofre: str


class GuardarArquivoRequest(BaseModel):
    """O arquivo do certificado, para guardar cifrado no cofre.

    Vem em **base64** e não como `multipart`: o conteúdo vira segredo
    versionado como qualquer outro, e o caminho de cifragem é o mesmo de uma
    senha. Um `multipart` exigiria um segundo caminho de escrita para o mesmo
    destino — e dois caminhos divergem.
    """

    cofre: str = Field(min_length=1, max_length=64)
    arquivo_nome: str = Field(min_length=1, max_length=255)
    # 2 MiB de base64 ≈ 1,5 MiB de arquivo. Um .pfx típico tem alguns KiB;
    # um limite generoso aqui ainda recusa o upload que entrou por engano.
    conteudo_base64: str = Field(min_length=1, max_length=2_800_000)
    # A senha do .pfx, quando houver, NÃO vem aqui: ela é outro segredo, com
    # outra revelação e outra auditoria. Guardá-la junto do arquivo faria do
    # par "arquivo + senha" um único clique — que é exatamente o que a
    # separação existe para impedir.


class CriarCertificadoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=300)
    issuer: str = Field(min_length=1, max_length=300)
    not_before: datetime
    not_after: datetime
    serial: str = ""
    owner_label: str = ""
    description: str = ""


# ------------------------------------------------------------------ helpers


def _evento(
    current: CurrentUser,
    action: AuditAction,
    target: str,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
    reason: str = "",
) -> AuditEvent:
    return AuditEvent(
        action=action,
        actor_id=current.id,
        actor_label=current.email,
        target_path=target,
        outcome=outcome,
        reason=reason,
        ip_address=current.ip_address,
        user_agent=current.user_agent,
    )


def _exigir(
    current: CurrentUser,
    policies: PolicyRepository,
    audit: AuditRepository,
    db: Session,
    caminho: PolicyPath,
    capacidade: Capability,
    mensagem: str,
) -> None:
    """Checa a política, audita a negativa e commita antes de propagar.

    O commit explícito existe pelo mesmo motivo das rotas de cofre: sem ele o
    rollback da requisição apagaria o registro da tentativa negada.
    """
    if evaluate(policies.policies_for_user(current.id), caminho, capacidade):
        return
    audit.append(
        _evento(
            current,
            AuditAction.ACCESS_DENIED,
            str(caminho),
            AuditOutcome.FAILURE,
            mensagem,
        )
    )
    db.commit()
    raise PermissionDeniedError(mensagem)


def _visiveis(
    policies: PolicyRepository, current: CurrentUser, caminhos: list[PolicyPath]
) -> set[str]:
    """Quais caminhos o usuário pode listar ou ler.

    O filtro é no servidor, nunca na tela: devolver tudo e esconder no front
    deixaria os nomes visíveis para quem lesse a resposta da API.
    """
    minhas = policies.policies_for_user(current.id)
    return {
        str(c)
        for c in caminhos
        if evaluate(minhas, c, Capability.LIST) or evaluate(minhas, c, Capability.READ)
    }


# -------------------------------------------------------------- dispositivos


@router.get(
    "/dispositivos",
    response_model=list[DispositivoResponse],
    summary="Listar dispositivos",
)
def listar_dispositivos(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
) -> list[DispositivoResponse]:
    todos = devices.list_all()
    permitidos = _visiveis(policies, current, [d.path for d in todos])
    return [
        _dispositivo_response(d, credentials)
        for d in todos
        if str(d.path) in permitidos
    ]


@router.post(
    "/dispositivos",
    response_model=DispositivoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar dispositivo",
)
def criar_dispositivo(
    payload: CriarDispositivoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DispositivoResponse:
    dispositivo = Device(
        name=Slug(payload.name),
        display_name=payload.display_name,
        kind=payload.kind,
        address=payload.address,
        tags=payload.tags,
        description=payload.description,
    )
    _exigir(
        current, policies, audit, db, dispositivo.path, Capability.CREATE,
        "Sem permissão para cadastrar este dispositivo.",
    )
    devices.add(dispositivo)
    audit.append(
        _evento(current, AuditAction.DEVICE_CREATED, str(dispositivo.path))
    )
    return _dispositivo_response(dispositivo, credentials)


# --------------------------------------------------------------- credenciais


@router.get(
    "/credenciais",
    response_model=list[CredencialResponse],
    summary="Listar credenciais",
)
def listar_credenciais(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
) -> list[CredencialResponse]:
    todas = credentials.list_all()
    permitidas = _visiveis(policies, current, [c.path for c in todas])
    por_id = {d.id: d for d in devices.list_all()}
    return [
        _credencial_response(c, por_id.get(c.device_id))
        for c in todas
        if str(c.path) in permitidas
    ]


@router.post(
    "/dispositivos/{device_name}/credenciais",
    response_model=CredencialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar credencial",
)
def criar_credencial(
    device_name: str,
    payload: CriarCredencialRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> CredencialResponse:
    dispositivo = devices.get_by_name(Slug(device_name))
    credencial = Credential(
        name=Slug(payload.name),
        device_id=dispositivo.id,
        username=payload.username,
        description=payload.description,
        rotation_days=payload.rotation_days,
        secret_id=payload.secret_id,
    )
    _exigir(
        current, policies, audit, db, credencial.path, Capability.CREATE,
        "Sem permissão para cadastrar esta credencial.",
    )
    credentials.add(credencial)
    audit.append(
        _evento(current, AuditAction.CREDENTIAL_CREATED, str(credencial.path))
    )
    return _credencial_response(credencial, dispositivo)


@router.post(
    "/credenciais/{credential_id}/retirar",
    response_model=CredencialResponse,
    summary="Retirar credencial (custódia)",
)
def retirar_credencial(
    credential_id: str,
    payload: RetirarRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> CredencialResponse:
    """Retirada exclusiva: ninguém mais leva esta credencial até a devolução.

    Exige `UPDATE`, não `READ`: retirar é assumir responsabilidade por trocar
    a senha, não apenas consultar.
    """
    credencial = credentials.get(credential_id)
    _exigir(
        current, policies, audit, db, credencial.path, Capability.UPDATE,
        "Sem permissão para retirar esta credencial.",
    )
    horas = payload.hours or ConfiguracaoRepository(db).atual().custodia_horas_padrao
    try:
        credencial.check_out(current.id, current.email, payload.reason, horas)
    except DomainError as erro:
        # Conflito de custódia também é informação de auditoria: diz quem
        # tentou pegar uma credencial que já estava na mão de outra pessoa.
        audit.append(
            _evento(
                current,
                AuditAction.CREDENTIAL_CHECKOUT_DENIED,
                str(credencial.path),
                AuditOutcome.FAILURE,
                str(erro),
            )
        )
        db.commit()
        raise

    salva = credentials.save(credencial)
    audit.append(
        _evento(
            current,
            AuditAction.CREDENTIAL_CHECKED_OUT,
            str(credencial.path),
            reason=f"Prazo de {horas}h. Motivo: {payload.reason}",
        )
    )
    return _credencial_response(salva, _dispositivo_de(devices, salva))


@router.post(
    "/credenciais/{credential_id}/devolver",
    response_model=CredencialResponse,
    summary="Devolver credencial",
)
def devolver_credencial(
    credential_id: str,
    payload: DevolverRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> CredencialResponse:
    """Devolve a credencial. Forçar a devolução de outra pessoa exige ADMIN."""
    credencial = credentials.get(credential_id)
    _exigir(
        current, policies, audit, db, credencial.path, Capability.UPDATE,
        "Sem permissão para devolver esta credencial.",
    )
    if payload.force:
        _exigir(
            current, policies, audit, db, credencial.path, Capability.ADMIN,
            "Forçar a devolução de uma credencial alheia exige administração.",
        )

    aberta = credencial.open_checkout
    de_quem = aberta.user_label if aberta else "—"
    credencial.check_in(current.id, force=payload.force)
    salva = credentials.save(credencial)
    audit.append(
        _evento(
            current,
            AuditAction.CREDENTIAL_CHECKED_IN,
            str(credencial.path),
            reason=(
                f"Devolução forçada; estava com {de_quem}."
                if payload.force
                else "Devolvida por quem retirou."
            ),
        )
    )
    return _credencial_response(salva, _dispositivo_de(devices, salva))


@router.post(
    "/credenciais/{credential_id}/rotacionar",
    response_model=CredencialResponse,
    summary="Registrar rotação",
)
def registrar_rotacao(
    credential_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> CredencialResponse:
    """Marca que a credencial foi trocada agora, zerando o prazo.

    Registrar a rotação não troca a senha: quem troca é a pessoa, no
    equipamento. Isto é a anotação de que foi feito — e é por isso que exige
    `UPDATE`, não `ADMIN`.
    """
    credencial = credentials.get(credential_id)
    _exigir(
        current, policies, audit, db, credencial.path, Capability.UPDATE,
        "Sem permissão para registrar rotação desta credencial.",
    )
    credencial.mark_rotated()
    salva = credentials.save(credencial)
    audit.append(
        _evento(current, AuditAction.CREDENTIAL_ROTATED, str(credencial.path))
    )
    return _credencial_response(salva, _dispositivo_de(devices, salva))


# -------------------------------------------------------------- certificados


@router.get(
    "/certificados",
    response_model=list[CertificadoResponse],
    summary="Listar certificados",
)
def listar_certificados(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CertificadoResponse]:
    todos = certificates.list_all()
    permitidos = _visiveis(policies, current, [c.path for c in todos])
    alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
    return [
        _certificado_response(c, alerta) for c in todos if str(c.path) in permitidos
    ]


@router.post(
    "/certificados",
    response_model=CertificadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar certificado",
)
def criar_certificado(
    payload: CriarCertificadoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> CertificadoResponse:
    certificado = Certificate(
        name=Slug(payload.name),
        display_name=payload.display_name,
        subject=payload.subject,
        issuer=payload.issuer,
        not_before=payload.not_before,
        not_after=payload.not_after,
        serial=payload.serial,
        owner_label=payload.owner_label,
        description=payload.description,
    )
    _exigir(
        current, policies, audit, db, certificado.path, Capability.CREATE,
        "Sem permissão para cadastrar este certificado.",
    )
    certificates.add(certificado)
    audit.append(
        _evento(current, AuditAction.CERTIFICATE_CREATED, str(certificado.path))
    )
    return _certificado_response(certificado)


@router.put(
    "/dispositivos/{device_name}/acessos",
    response_model=DispositivoResponse,
    summary="Definir formas de acesso remoto",
)
def definir_acessos(
    device_name: str,
    payload: DefinirAcessosRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DispositivoResponse:
    """Substitui as formas de alcançar a máquina.

    Os identificadores (ID do AnyDesk, host do RDP) são dados comuns, não
    segredos: eles dizem onde a máquina está, e quem os tem sem a senha não
    entra. Mascará-los atrapalharia quem precisa ditar o número no telefone,
    sem proteger nada.
    """
    dispositivo = devices.get_by_name(Slug(device_name))
    _exigir(
        current, policies, audit, db, dispositivo.path, Capability.UPDATE,
        "Sem permissão para alterar os acessos deste dispositivo.",
    )

    acessos = [
        AcessoRemoto(
            metodo=a.metodo,
            identificador=a.identificador,
            porta=a.porta,
            usuario_sugerido=a.usuario_sugerido,
            observacao=a.observacao,
        )
        for a in payload.acessos
    ]
    salvo = devices.save_acessos(dispositivo.id, acessos)
    audit.append(
        _evento(
            current, AuditAction.DEVICE_ACCESS_UPDATED, str(dispositivo.path),
            reason=f"Métodos: {', '.join(str(a.metodo) for a in acessos) or '—'}.",
        )
    )
    return _dispositivo_response(salvo, credentials)


@router.get(
    "/dispositivos/{device_name}/rdp",
    summary="Baixar arquivo .rdp",
    response_class=Response,
)
def baixar_rdp(
    device_name: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Gera um arquivo .rdp apontado para a máquina, **sem a senha**.

    Senha dentro de arquivo é senha no disco de quem baixou, fora do cofre e
    fora da auditoria. A pessoa revela a senha no cofre — o que vira evento —
    e cola na janela do RDP, que a pede.

    Cada download é registrado: saber quem abriu conexão com qual máquina é
    metade do valor de um cofre de acesso.
    """
    dispositivo = devices.get_by_name(Slug(device_name))
    _exigir(
        current, policies, audit, db, dispositivo.path, Capability.READ,
        "Sem permissão para acessar este dispositivo.",
    )

    rdp = next(
        (a for a in dispositivo.acessos if a.metodo is MetodoDeAcesso.RDP), None
    )
    if rdp is None:
        raise NotFoundError(
            "Este dispositivo não tem acesso RDP cadastrado."
        )

    conteudo = montar_arquivo_rdp(
        rdp.identificador, usuario=rdp.usuario_sugerido, porta=rdp.porta
    )
    audit.append(
        _evento(
            current, AuditAction.REMOTE_ACCESS_STARTED, str(dispositivo.path),
            reason=f"Arquivo .rdp gerado para {rdp.identificador}.",
        )
    )
    return Response(
        content=conteudo,
        media_type="application/x-rdp",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{dispositivo.name}.rdp"'
            )
        },
    )


@router.post(
    "/dispositivos/{device_name}/acesso-registrado",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Registrar uso de acesso remoto",
)
def registrar_acesso(
    device_name: str,
    metodo: Annotated[MetodoDeAcesso, Query()],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Registra que alguém usou um acesso que o sistema não intermedia.

    AnyDesk e Google Remote Desktop acontecem fora daqui: o Vault entrega o
    identificador e perde a pista. Sem este registro, a trilha teria um
    buraco justamente nos acessos mais informais — que são os que mais
    importam numa revisão.
    """
    dispositivo = devices.get_by_name(Slug(device_name))
    _exigir(
        current, policies, audit, db, dispositivo.path, Capability.READ,
        "Sem permissão para acessar este dispositivo.",
    )
    audit.append(
        _evento(
            current, AuditAction.REMOTE_ACCESS_STARTED, str(dispositivo.path),
            reason=f"Acesso por {metodo} iniciado pelo usuário.",
        )
    )


@router.get(
    "/certificados/{nome}/exportar",
    summary="Exportar certificado em JSON",
)
def exportar_certificado(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Metadados do certificado em JSON, para copiar ou salvar.

    **Sem a chave privada**: ela, quando guardada, é segredo do cofre e sai
    pela rota de revelar, que audita. Um "exportar tudo" que incluísse a
    chave transformaria um clique de conveniência num vazamento.
    """
    certificado = certificates.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, certificado.path, Capability.READ,
        "Sem permissão para exportar este certificado.",
    )
    audit.append(
        _evento(
            current, AuditAction.CERTIFICATE_EXPORTED, str(certificado.path),
            reason="Metadados exportados (sem chave privada).",
        )
    )
    return {
        "nome": str(certificado.name),
        "nome_visivel": certificado.display_name,
        "titular": certificado.subject,
        "emissor": certificado.issuer,
        "serial": certificado.serial,
        "responsavel": certificado.owner_label,
        "valido_de": certificado.not_before.isoformat(),
        "valido_ate": certificado.not_after.isoformat(),
        "dias_restantes": certificado.days_remaining(),
        "estado": str(certificado.state()),
        "descricao": certificado.description,
        "observacao": (
            "A chave privada não é exportada. Quando guardada, ela é segredo "
            "do cofre e sai pela rota de revelar, que registra auditoria."
        ),
    }


@router.post(
    "/certificados/{nome}/arquivo",
    response_model=CertificadoResponse,
    summary="Guardar o arquivo do certificado",
)
def guardar_arquivo(
    nome: str,
    payload: GuardarArquivoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    crypto: Annotated[EnvelopeCryptoService, Depends(get_crypto)],
    db: Annotated[Session, Depends(get_db)],
) -> CertificadoResponse:
    """Guarda o arquivo do certificado como segredo cifrado no cofre.

    **Duas permissões, não uma.** Exige `UPDATE` no certificado *e* `CREATE`
    no cofre de destino. Checar só a primeira deixaria quem administra
    certificados escrever em qualquer cofre por esta porta — uma escalada
    silenciosa, porque a tela de certificados não parece uma tela de cofre.

    **O arquivo vira segredo versionado.** Reenviar não sobrescreve: grava
    outra versão. Certificado renovado mantém o histórico do anterior, que é
    o que responde "com qual arquivo aquilo foi assinado em março?".
    """
    import base64
    import binascii

    certificado = certificates.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, certificado.path, Capability.UPDATE,
        "Sem permissão para alterar este certificado.",
    )

    try:
        conteudo = base64.b64decode(payload.conteudo_base64, validate=True)
    except (binascii.Error, ValueError) as erro:
        raise ValidationError("O arquivo não chegou em base64 válido.") from erro
    if not conteudo:
        raise ValidationError("O arquivo chegou vazio.")

    cofre = vaults.get_by_name(Slug(payload.cofre))
    nome_do_segredo = Slug(f"certificado-{certificado.name}")
    caminho = cofre.secret_path(nome_do_segredo)
    _exigir(
        current, policies, audit, db, caminho, Capability.CREATE,
        "Sem permissão para guardar segredos neste cofre.",
    )
    cofre.ensure_usable()

    # Reenvio vira nova versão do mesmo segredo; o histórico é o que permite
    # responder com qual arquivo algo foi assinado numa data passada.
    valor = crypto.encrypt(base64.b64encode(conteudo).decode("ascii"))
    try:
        segredo = secrets.get_in_vault(cofre.id, nome_do_segredo)
    except NotFoundError:
        segredo = Secret(
            name=nome_do_segredo,
            vault_id=cofre.id,
            kind=SecretKind.CERTIFICATE,
            description=f"Arquivo de {certificado.display_name}.",
        )
        segredo.add_version(valor, created_by=current.id)
        secrets.add(segredo)
    else:
        versao = segredo.add_version(valor, created_by=current.id)
        secrets.add_version(segredo.id, versao)

    certificado.secret_id = segredo.id
    certificado.arquivo_nome = payload.arquivo_nome
    certificado.arquivo_cofre = str(cofre.name)
    salvo = certificates.save(certificado)

    audit.append(
        _evento(
            current, AuditAction.CERTIFICATE_FILE_STORED, str(certificado.path),
            reason=(
                f"Arquivo {payload.arquivo_nome} ({len(conteudo)} bytes) "
                f"guardado em {caminho}."
            ),
        )
    )
    alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
    return _certificado_response(salvo, alerta)


@router.get(
    "/certificados/{nome}/arquivo",
    summary="Baixar o arquivo do certificado",
)
def baixar_arquivo(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    crypto: Annotated[EnvelopeCryptoService, Depends(get_crypto)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Devolve o arquivo guardado, em base64.

    **Exige `REVEAL` no cofre**, não `READ` no certificado. Acompanhar
    vencimento e sacar o arquivo são coisas diferentes: a primeira é rotina
    de quem administra prazos, a segunda entrega material criptográfico. Um
    `.pfx` carrega a chave privada — é a assinatura da empresa, não um anexo.

    Cada download vira evento, como qualquer revelação.
    """
    certificado = certificates.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, certificado.path, Capability.READ,
        "Sem permissão para ver este certificado.",
    )
    if not certificado.secret_id or not certificado.arquivo_cofre:
        raise NotFoundError("Este certificado não tem arquivo guardado.")

    cofre = vaults.get_by_name(Slug(certificado.arquivo_cofre))
    segredo = secrets.get(certificado.secret_id)
    _exigir(
        current, policies, audit, db, cofre.secret_path(segredo.name),
        Capability.REVEAL,
        "Sem permissão para revelar o arquivo deste certificado.",
    )
    cofre.ensure_usable()

    audit.append(
        _evento(
            current, AuditAction.CERTIFICATE_FILE_DOWNLOADED,
            str(certificado.path),
            reason=f"Arquivo {certificado.arquivo_nome} baixado.",
        )
    )
    return {
        "arquivo_nome": certificado.arquivo_nome,
        "conteudo_base64": crypto.decrypt(segredo.current_version.value),
        "versao": segredo.current_version.version,
    }


@router.delete(
    "/certificados/{nome}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir certificado",
)
def excluir_certificado(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Remove o certificado do inventário.

    O segredo com a chave privada, se houver, **não** é apagado: são coisas
    separadas, e um clique que removesse os dois ao mesmo tempo apagaria o
    material criptográfico junto com o lembrete de que ele existia.
    """
    certificado = certificates.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, certificado.path, Capability.DELETE,
        "Sem permissão para excluir este certificado.",
    )
    certificates.delete(certificado.id)
    audit.append(
        _evento(
            current, AuditAction.CERTIFICATE_DELETED, str(certificado.path),
            reason=(
                f"{certificado.display_name}, emissor {certificado.issuer}. "
                "A chave privada no cofre não foi apagada."
            ),
        )
    )


@router.get(
    "/credenciais/{credential_id}/exportar",
    summary="Exportar credencial em JSON",
)
def exportar_credencial(
    credential_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Governo da credencial em JSON. **Sem o valor da senha.**

    Rotação, custódia e histórico são o que alguém precisa para auditar ou
    migrar o inventário. O valor sai pela rota de revelar, uma por vez, com
    auditoria — e não num JSON que se copia inteiro.
    """
    credencial = credentials.get(credential_id)
    _exigir(
        current, policies, audit, db, credencial.path, Capability.READ,
        "Sem permissão para exportar esta credencial.",
    )
    dispositivo = _dispositivo_de(devices, credencial)
    audit.append(
        _evento(
            current, AuditAction.CREDENTIAL_EXPORTED, str(credencial.path),
            reason="Governo exportado (sem o valor).",
        )
    )
    aberta = credencial.open_checkout
    return {
        "nome": str(credencial.name),
        "dispositivo": dispositivo.display_name if dispositivo else None,
        "endereco": dispositivo.address if dispositivo else None,
        "usuario": credencial.username,
        "descricao": credencial.description,
        "rotacao_dias": credencial.rotation_days,
        "ultima_rotacao": (
            credencial.last_rotated_at.isoformat()
            if credencial.last_rotated_at
            else None
        ),
        "vence_em": credencial.due_at.isoformat() if credencial.due_at else None,
        "atrasada": credencial.is_overdue(),
        "situacao": str(credencial.status),
        "custodia_aberta": (
            {
                "com": aberta.user_label,
                "desde": aberta.taken_at.isoformat(),
                "ate": aberta.due_at.isoformat(),
                "motivo": aberta.reason,
            }
            if aberta
            else None
        ),
        "historico_custodias": len(credencial.checkouts),
        "observacao": (
            "O valor da senha não é exportado. Ele sai pela rota de revelar, "
            "uma por vez, com registro de auditoria."
        ),
    }


# ----------------------------------------------------------------- resposta


def _acesso_response(acesso: AcessoRemoto) -> AcessoResponse:
    return AcessoResponse(
        metodo=str(acesso.metodo),
        identificador=acesso.identificador,
        porta=acesso.porta,
        usuario_sugerido=acesso.usuario_sugerido,
        observacao=acesso.observacao,
        suporta_arquivo_rdp=acesso.suporta_arquivo_rdp,
        link=acesso.link(),
    )


def _dispositivo_response(
    d: Device, credentials: CredentialRepository
) -> DispositivoResponse:
    return DispositivoResponse(
        id=d.id,
        name=str(d.name),
        display_name=d.display_name,
        kind=str(d.kind),
        address=d.address,
        tags=d.tags,
        description=d.description,
        acessos=[_acesso_response(a) for a in d.acessos],
        is_active=d.is_active,
        credenciais=len(credentials.list_for_device(d.id)),
        created_at=d.created_at,
    )


def _dispositivo_de(
    devices: DeviceRepository, credencial: Credential
) -> Device | None:
    for d in devices.list_all():
        if d.id == credencial.device_id:
            return d
    return None


def _custodia_response(checkout) -> CustodiaResponse:  # noqa: ANN001
    return CustodiaResponse(
        id=checkout.id,
        user_label=checkout.user_label,
        reason=checkout.reason,
        taken_at=checkout.taken_at,
        due_at=checkout.due_at,
        returned_at=checkout.returned_at,
        em_atraso=checkout.is_late(),
    )


def _credencial_response(
    credencial: Credential, dispositivo: Device | None
) -> CredencialResponse:
    aberta = credencial.open_checkout
    return CredencialResponse(
        id=credencial.id,
        name=str(credencial.name),
        device_id=credencial.device_id,
        device_name=dispositivo.display_name if dispositivo else "—",
        username=credencial.username,
        description=credencial.description,
        status=str(credencial.status),
        rotation_days=credencial.rotation_days,
        last_rotated_at=credencial.last_rotated_at,
        due_at=credencial.due_at,
        dias_para_vencer=credencial.days_until_due(),
        atrasada=credencial.is_overdue(),
        custodia_aberta=_custodia_response(aberta) if aberta else None,
        historico=[_custodia_response(c) for c in reversed(credencial.checkouts)],
    )


def _certificado_response(
    certificado: Certificate, alerta_dias: int | None = None
) -> CertificadoResponse:
    # A faixa de alerta vem da configuração da instalação; o padrão do
    # domínio continua valendo quando ninguém informou outra.
    estado = (
        certificado.state()
        if alerta_dias is None
        else _estado_com_faixa(certificado, alerta_dias)
    )
    return CertificadoResponse(
        id=certificado.id,
        name=str(certificado.name),
        display_name=certificado.display_name,
        subject=certificado.subject,
        issuer=certificado.issuer,
        serial=certificado.serial,
        owner_label=certificado.owner_label,
        not_before=certificado.not_before,
        not_after=certificado.not_after,
        description=certificado.description,
        estado=estado,
        dias_restantes=certificado.days_remaining(),
        tem_arquivo=bool(certificado.secret_id and certificado.arquivo_cofre),
        arquivo_nome=certificado.arquivo_nome,
        arquivo_cofre=certificado.arquivo_cofre,
    )


def _estado_com_faixa(certificado: Certificate, alerta_dias: int) -> str:
    """Estado do certificado com a faixa de alerta configurada.

    A regra de "vencido" continua no domínio; só a largura da faixa de aviso
    é ajustável — quem configura escolhe com quanta antecedência quer ser
    avisado, não o que conta como vencido.
    """
    from ...domain.inventory.entities import CertificateState

    if certificado.is_expired():
        return str(CertificateState.EXPIRED)
    if certificado.days_remaining() <= alerta_dias:
        return str(CertificateState.EXPIRING)
    return str(CertificateState.VALID)
