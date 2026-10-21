"""Panorama por domínio: os números que abrem cada aba do painel.

Um endpoint só, e não um por aba, de propósito: as abas do painel trocam
rápido, e cinco chamadas separadas fariam cada clique esperar a rede. O
corpo é pequeno — são contagens, nunca listas —, então trazer tudo de uma
vez sai mais barato que buscar sob demanda.

**Visibilidade.** Toda contagem respeita a política do usuário: um número que
some recursos que a pessoa não pode ver revelaria a existência deles, que é
exatamente o que a tela de busca evita ao varrer só o que ela alcança. Quem
não tem acesso a nada vê zero em tudo, não um erro.

Aqui não há valor de segredo em lugar nenhum: são contagens e, no máximo, o
nome de um recurso que o usuário já pode listar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...domain.access.policy import Capability, evaluate
from ...domain.apikeys.entities import EstadoDaChave
from ...domain.inventory.entities import CertificateState
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import (
    ChaveApiRepository,
    CertificateRepository,
    CredentialRepository,
    DeviceRepository,
    PolicyRepository,
    SecretRepository,
    VaultRepository,
)
from ..deps import (
    CurrentUser,
    get_current_user,
    get_policies,
    get_secrets,
    get_vaults,
)
from .apikeys import get_chaves
from .inventory import get_certificates, get_credentials, get_devices

router = APIRouter(prefix="/panorama", tags=["Panorama"])


def _pode_ver(policies: PolicyRepository, user_id: str, caminho: PolicyPath) -> bool:
    minhas = policies.policies_for_user(user_id)
    return evaluate(minhas, caminho, Capability.LIST) or evaluate(
        minhas, caminho, Capability.READ
    )


class Destaque(BaseModel):
    """Uma linha do tipo "3 vencem nos próximos 30 dias"."""

    rotulo: str
    quantas: int
    tom: str  # 'danger' | 'warning' | 'success' | 'muted' | 'brand'


class PanoramaDeCofres(BaseModel):
    total: int
    ativos: int
    selados: int
    segredos: int
    na_lixeira: int
    destaques: list[Destaque]


class PanoramaDeCredenciais(BaseModel):
    total: int
    em_custodia: int
    custodia_vencida: int
    rotacao_atrasada: int
    nunca_rotacionadas: int
    destaques: list[Destaque]


class PanoramaDeCertificados(BaseModel):
    total: int
    vencidos: int
    vencendo: int
    validos: int
    proximo_nome: str
    proximo_dias: int | None
    destaques: list[Destaque]


class PanoramaDeChaves(BaseModel):
    total: int
    ativas: int
    revogadas: int
    expiradas: int
    sem_vencimento: int
    destaques: list[Destaque]


class PanoramaDeDispositivos(BaseModel):
    total: int
    ativos: int
    com_acesso_remoto: int
    sem_credencial: int
    destaques: list[Destaque]


class PanoramaResponse(BaseModel):
    cofres: PanoramaDeCofres
    credenciais: PanoramaDeCredenciais
    certificados: PanoramaDeCertificados
    chaves: PanoramaDeChaves
    dispositivos: PanoramaDeDispositivos


@router.get("", response_model=PanoramaResponse, summary="Panorama por domínio")
def panorama(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    chaves: Annotated[ChaveApiRepository, Depends(get_chaves)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
) -> PanoramaResponse:
    """Contagens por domínio, só do que o usuário enxerga."""
    agora = datetime.now(UTC)

    # --- Cofres e segredos ---------------------------------------------
    cofres_visiveis = [
        c for c in vaults.list_all() if _pode_ver(policies, current.id, c.path)
    ]
    total_segredos = 0
    total_lixeira = 0
    for cofre in cofres_visiveis:
        vivos = secrets.list_in_vault(cofre.id)
        todos = secrets.list_in_vault(cofre.id, include_deleted=True)
        total_segredos += len(vivos)
        # A lixeira é a diferença: o repositório devolve "com apagados" ou
        # "sem", e pedir os dois é mais barato que um terceiro método.
        total_lixeira += len(todos) - len(vivos)

    selados = sum(1 for c in cofres_visiveis if c.state == "selado")
    cofres = PanoramaDeCofres(
        total=len(cofres_visiveis),
        ativos=len(cofres_visiveis) - selados,
        selados=selados,
        segredos=total_segredos,
        na_lixeira=total_lixeira,
        destaques=[
            Destaque(rotulo="Cofres selados", quantas=selados, tom="danger"),
            Destaque(rotulo="Segredos na lixeira", quantas=total_lixeira, tom="muted"),
        ],
    )

    # --- Credenciais -----------------------------------------------------
    creds = [
        c for c in credentials.list_all() if _pode_ver(policies, current.id, c.path)
    ]
    abertas = [c for c in creds if c.open_checkout is not None]
    atrasadas = [c for c in creds if c.is_overdue(agora)]
    nunca = [c for c in creds if c.last_rotated_at is None]
    vencidas = [
        c
        for c in abertas
        if c.open_checkout is not None and c.open_checkout.is_late(agora)
    ]
    credenciais = PanoramaDeCredenciais(
        total=len(creds),
        em_custodia=len(abertas),
        custodia_vencida=len(vencidas),
        rotacao_atrasada=len(atrasadas),
        nunca_rotacionadas=len(nunca),
        destaques=[
            Destaque(rotulo="Custódia vencida", quantas=len(vencidas), tom="danger"),
            Destaque(
                rotulo="Nunca rotacionadas", quantas=len(nunca), tom="warning"
            ),
            Destaque(rotulo="Em custódia agora", quantas=len(abertas), tom="brand"),
        ],
    )

    # --- Certificados ----------------------------------------------------
    certs = [
        c for c in certificates.list_all() if _pode_ver(policies, current.id, c.path)
    ]
    vencidos = [c for c in certs if c.state(agora) is CertificateState.EXPIRED]
    vencendo = [c for c in certs if c.state(agora) is CertificateState.EXPIRING]
    # O mais próximo de vencer entre os que ainda valem: é a pergunta que se
    # faz antes de uma renovação, e o nome importa tanto quanto o prazo.
    a_vencer = sorted(
        (c for c in certs if c.state(agora) is not CertificateState.EXPIRED),
        key=lambda c: c.days_remaining(agora),
    )
    proximo = a_vencer[0] if a_vencer else None
    certificados = PanoramaDeCertificados(
        total=len(certs),
        vencidos=len(vencidos),
        vencendo=len(vencendo),
        validos=len(certs) - len(vencidos) - len(vencendo),
        proximo_nome=proximo.display_name if proximo else "",
        proximo_dias=proximo.days_remaining(agora) if proximo else None,
        destaques=[
            Destaque(rotulo="Vencidos", quantas=len(vencidos), tom="danger"),
            Destaque(rotulo="Vencendo", quantas=len(vencendo), tom="warning"),
        ],
    )

    # --- Chaves de API ---------------------------------------------------
    todas_chaves = [
        k for k in chaves.list_all() if _pode_ver(policies, current.id, k.path)
    ]
    ativas = [k for k in todas_chaves if k.estado is EstadoDaChave.ATIVA]
    revogadas = [k for k in todas_chaves if k.estado is EstadoDaChave.REVOGADA]
    expiradas = [k for k in todas_chaves if k.estado is EstadoDaChave.EXPIRADA]
    # Chave ativa sem vencimento não é erro, mas é dívida: ninguém decide
    # quando ela sai de circulação, então ela nunca sai.
    perpetuas = [k for k in ativas if k.expira_em is None]
    api = PanoramaDeChaves(
        total=len(todas_chaves),
        ativas=len(ativas),
        revogadas=len(revogadas),
        expiradas=len(expiradas),
        sem_vencimento=len(perpetuas),
        destaques=[
            Destaque(rotulo="Expiradas", quantas=len(expiradas), tom="danger"),
            Destaque(
                rotulo="Ativas sem vencimento", quantas=len(perpetuas), tom="warning"
            ),
        ],
    )

    # --- Dispositivos ----------------------------------------------------
    maquinas = [
        d for d in devices.list_all() if _pode_ver(policies, current.id, d.path)
    ]
    com_acesso = [d for d in maquinas if d.acessos]
    com_credencial = {c.device_id for c in creds}
    orfaos = [d for d in maquinas if d.id not in com_credencial]
    dispositivos = PanoramaDeDispositivos(
        total=len(maquinas),
        ativos=sum(1 for d in maquinas if d.is_active),
        com_acesso_remoto=len(com_acesso),
        sem_credencial=len(orfaos),
        destaques=[
            Destaque(rotulo="Sem credencial", quantas=len(orfaos), tom="muted"),
            Destaque(
                rotulo="Com acesso remoto", quantas=len(com_acesso), tom="brand"
            ),
        ],
    )

    return PanoramaResponse(
        cofres=cofres,
        credenciais=credenciais,
        certificados=certificados,
        chaves=api,
        dispositivos=dispositivos,
    )
