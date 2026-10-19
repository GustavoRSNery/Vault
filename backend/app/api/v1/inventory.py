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

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.inventory.entities import (
    Certificate,
    Credential,
    Device,
    DeviceKind,
)
from ...domain.shared.errors import DomainError, PermissionDeniedError
from ...domain.shared.value_objects import PolicyPath, Slug
from ...infrastructure.db.repositories import (
    AuditRepository,
    CertificateRepository,
    CredentialRepository,
    DeviceRepository,
    PolicyRepository,
)
from ..deps import CurrentUser, get_audit, get_current_user, get_db, get_policies

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
    hours: int = Field(default=4, ge=1, le=720)


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
        DispositivoResponse(
            id=d.id,
            name=str(d.name),
            display_name=d.display_name,
            kind=str(d.kind),
            address=d.address,
            tags=d.tags,
            description=d.description,
            is_active=d.is_active,
            credenciais=len(credentials.list_for_device(d.id)),
            created_at=d.created_at,
        )
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
    return DispositivoResponse(
        id=dispositivo.id,
        name=str(dispositivo.name),
        display_name=dispositivo.display_name,
        kind=str(dispositivo.kind),
        address=dispositivo.address,
        tags=dispositivo.tags,
        description=dispositivo.description,
        is_active=dispositivo.is_active,
        credenciais=0,
        created_at=dispositivo.created_at,
    )


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
    try:
        credencial.check_out(
            current.id, current.email, payload.reason, payload.hours
        )
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
            reason=f"Prazo de {payload.hours}h. Motivo: {payload.reason}",
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
) -> list[CertificadoResponse]:
    todos = certificates.list_all()
    permitidos = _visiveis(policies, current, [c.path for c in todos])
    return [_certificado_response(c) for c in todos if str(c.path) in permitidos]


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


# ----------------------------------------------------------------- resposta


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


def _certificado_response(certificado: Certificate) -> CertificadoResponse:
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
        estado=str(certificado.state()),
        dias_restantes=certificado.days_remaining(),
    )
