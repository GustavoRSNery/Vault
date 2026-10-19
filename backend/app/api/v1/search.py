"""Busca global e relatórios de situação.

A busca varre o que o usuário **pode ver** — nunca o acervo inteiro com
filtro depois. Buscar "sefaz" e receber zero resultados não pode significar
coisa diferente de "não existe" para quem não tem acesso: o contrário
transformaria a busca num mapa do que existe e está fora do alcance.

Os relatórios respondem às três perguntas que alguém faz antes de uma
auditoria: o que está vencido, o que vence logo, e quem está com o quê.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...domain.access.policy import Capability, evaluate
from ...domain.inventory.entities import CertificateState
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import (
    AccessRequestRepository,
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
from .approvals import get_requests
from .inventory import get_certificates, get_credentials, get_devices

router = APIRouter(tags=["Busca e relatórios"])

TipoResultado = Literal["cofre", "segredo", "dispositivo", "credencial", "certificado"]


class ResultadoBusca(BaseModel):
    tipo: TipoResultado
    titulo: str
    subtitulo: str
    caminho: str
    rota: str


class BuscaResponse(BaseModel):
    termo: str
    total: int
    resultados: list[ResultadoBusca]


class ItemAlerta(BaseModel):
    severidade: Literal["alta", "media", "baixa"]
    categoria: str
    titulo: str
    detalhe: str
    rota: str
    quando: datetime | None = None


class AlertasResponse(BaseModel):
    """Feed de pendências, da mais urgente para a menos.

    Tudo aqui é derivado do estado atual, não de uma tabela de alertas:
    alerta gravado precisa ser apagado quando a causa some, e esquecer de
    apagar produz painel com alarme falso — que é pior que painel vazio.
    """

    total: int
    altas: int
    itens: list[ItemAlerta]


def _pode(policies: PolicyRepository, user_id: str, caminho: PolicyPath) -> bool:
    minhas = policies.policies_for_user(user_id)
    return evaluate(minhas, caminho, Capability.LIST) or evaluate(
        minhas, caminho, Capability.READ
    )


@router.get("/busca", response_model=BuscaResponse, summary="Busca global")
def buscar(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    secrets: Annotated[SecretRepository, Depends(get_secrets)],
    devices: Annotated[DeviceRepository, Depends(get_devices)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    termo: Annotated[str, Query(min_length=2, max_length=100)],
    limite: Annotated[int, Query(ge=1, le=100)] = 40,
) -> BuscaResponse:
    """Busca por nome, descrição e caminho, sempre dentro do que é permitido.

    O valor de um segredo nunca entra na busca: casar por conteúdo revelaria
    o valor a quem só pode listar — e, pior, por tentativa e erro revelaria a
    qualquer um.
    """
    alvo = termo.strip().lower()
    achados: list[ResultadoBusca] = []

    for cofre in vaults.list_all():
        if not _pode(policies, current.id, cofre.path):
            continue
        if alvo in cofre.display_name.lower() or alvo in str(cofre.name).lower():
            achados.append(
                ResultadoBusca(
                    tipo="cofre",
                    titulo=cofre.display_name,
                    subtitulo=cofre.description or "Cofre",
                    caminho=str(cofre.path),
                    rota=f"/cofres/{cofre.name}",
                )
            )

        for segredo in secrets.list_in_vault(cofre.id):
            caminho = cofre.secret_path(segredo.name)
            if not _pode(policies, current.id, caminho):
                continue
            if (
                alvo in str(segredo.name).lower()
                or alvo in segredo.description.lower()
            ):
                achados.append(
                    ResultadoBusca(
                        tipo="segredo",
                        titulo=str(segredo.name),
                        subtitulo=f"{segredo.description or 'Segredo'} · {cofre.display_name}",
                        caminho=str(caminho),
                        rota=f"/cofres/{cofre.name}",
                    )
                )

    por_dispositivo = {d.id: d for d in devices.list_all()}
    for dispositivo in por_dispositivo.values():
        if not _pode(policies, current.id, dispositivo.path):
            continue
        if (
            alvo in dispositivo.display_name.lower()
            or alvo in dispositivo.address.lower()
            or any(alvo in t for t in dispositivo.tags)
        ):
            achados.append(
                ResultadoBusca(
                    tipo="dispositivo",
                    titulo=dispositivo.display_name,
                    subtitulo=dispositivo.address or str(dispositivo.kind),
                    caminho=str(dispositivo.path),
                    rota="/dispositivos",
                )
            )

    for credencial in credentials.list_all():
        if not _pode(policies, current.id, credencial.path):
            continue
        if (
            alvo in str(credencial.name).lower()
            or alvo in credencial.username.lower()
        ):
            dono = por_dispositivo.get(credencial.device_id)
            achados.append(
                ResultadoBusca(
                    tipo="credencial",
                    titulo=str(credencial.name),
                    subtitulo=f"{credencial.username or '—'} · {dono.display_name if dono else '—'}",
                    caminho=str(credencial.path),
                    rota="/credenciais",
                )
            )

    for certificado in certificates.list_all():
        if not _pode(policies, current.id, certificado.path):
            continue
        if (
            alvo in certificado.display_name.lower()
            or alvo in certificado.subject.lower()
            or alvo in certificado.issuer.lower()
        ):
            achados.append(
                ResultadoBusca(
                    tipo="certificado",
                    titulo=certificado.display_name,
                    subtitulo=f"{certificado.issuer} · vence {certificado.not_after:%d/%m/%Y}",
                    caminho=str(certificado.path),
                    rota="/certificados",
                )
            )

    return BuscaResponse(
        termo=termo, total=len(achados), resultados=achados[:limite]
    )


@router.get("/alertas", response_model=AlertasResponse, summary="Central de alertas")
def alertas(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    vaults: Annotated[VaultRepository, Depends(get_vaults)],
    credentials: Annotated[CredentialRepository, Depends(get_credentials)],
    certificates: Annotated[CertificateRepository, Depends(get_certificates)],
    requests: Annotated[AccessRequestRepository, Depends(get_requests)],
) -> AlertasResponse:
    """Pendências derivadas do estado atual, só do que o usuário enxerga."""
    itens: list[ItemAlerta] = []

    for certificado in certificates.list_all():
        if not _pode(policies, current.id, certificado.path):
            continue
        estado = certificado.state()
        dias = certificado.days_remaining()
        if estado is CertificateState.EXPIRED:
            itens.append(
                ItemAlerta(
                    severidade="alta",
                    categoria="Certificado",
                    titulo=f"{certificado.display_name} venceu",
                    detalhe=f"Há {abs(dias)} dia(s). Certificado vencido derruba conexão TLS.",
                    rota="/certificados",
                    quando=certificado.not_after,
                )
            )
        elif estado is CertificateState.EXPIRING:
            itens.append(
                ItemAlerta(
                    severidade="media",
                    categoria="Certificado",
                    titulo=f"{certificado.display_name} vence em {dias} dia(s)",
                    detalhe=f"Emissor {certificado.issuer}. Responsável: {certificado.owner_label or '—'}.",
                    rota="/certificados",
                    quando=certificado.not_after,
                )
            )

    for credencial in credentials.list_all():
        if not _pode(policies, current.id, credencial.path):
            continue
        if credencial.is_overdue():
            nunca = credencial.last_rotated_at is None
            itens.append(
                ItemAlerta(
                    severidade="alta" if nunca else "media",
                    categoria="Rotação",
                    titulo=f"{credencial.name} está com a rotação atrasada",
                    detalhe=(
                        "Nunca foi rotacionada — pode ainda ser a senha de fábrica."
                        if nunca
                        else f"O prazo de {credencial.rotation_days} dias venceu."
                    ),
                    rota="/credenciais",
                    quando=credencial.due_at,
                )
            )
        aberta = credencial.open_checkout
        if aberta is not None and aberta.is_late():
            itens.append(
                ItemAlerta(
                    severidade="media",
                    categoria="Custódia",
                    titulo=f"{credencial.name} não foi devolvida",
                    detalhe=f"Com {aberta.user_label} desde {aberta.taken_at:%d/%m %H:%M}; prazo vencido.",
                    rota="/credenciais",
                    quando=aberta.due_at,
                )
            )

    for cofre in vaults.list_all():
        if not _pode(policies, current.id, cofre.path):
            continue
        if cofre.is_sealed:
            itens.append(
                ItemAlerta(
                    severidade="alta",
                    categoria="Cofre",
                    titulo=f"{cofre.display_name} está selado",
                    detalhe="Nenhum segredo pode ser lido ou alterado até ser desselado.",
                    rota=f"/cofres/{cofre.name}",
                )
            )

    minhas = policies.policies_for_user(current.id)
    for pedido in requests.list_pending():
        if pedido.requester_id == current.id:
            continue
        if evaluate(minhas, pedido.path, Capability.APPROVE):
            itens.append(
                ItemAlerta(
                    severidade="media",
                    categoria="Aprovação",
                    titulo=f"{pedido.requester_label} aguarda decisão",
                    detalhe=f"Pede {', '.join(sorted(str(c) for c in pedido.capabilities))} em {pedido.path}.",
                    rota="/solicitacoes",
                    quando=pedido.created_at,
                )
            )

    for pedido in requests.active_grants_for(current.id):
        if pedido.is_active():
            itens.append(
                ItemAlerta(
                    severidade="baixa",
                    categoria="Acesso temporário",
                    titulo=f"Você tem acesso ativo a {pedido.path}",
                    detalhe=f"Expira em {pedido.hours_remaining()}h. Devolver cedo nunca é risco.",
                    rota="/solicitacoes",
                    quando=pedido.granted_until,
                )
            )

    ordem = {"alta": 0, "media": 1, "baixa": 2}
    itens.sort(key=lambda i: (ordem[i.severidade], i.categoria))

    return AlertasResponse(
        total=len(itens),
        altas=sum(1 for i in itens if i.severidade == "alta"),
        itens=itens,
    )
