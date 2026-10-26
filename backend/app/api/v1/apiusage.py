"""Rotas de governança da API: quem consome o Vault de fora, e como.

Restrita a quem administra auditoria: o relatório mostra IP, agente e
padrão de consumo de cada integração, que é mapa de superfície de ataque
para quem não deveria tê-lo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...application.ports.apiusage import FiltroDeUso
from ...domain.access.policy import Capability, evaluate
from ...domain.apiusage.entities import Origem, Resultado
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import PermissionDeniedError
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.apiusage_repo import RegistroDeUsoSql
from ...infrastructure.db.repositories import AuditRepository, PolicyRepository
from ..deps import (
    CurrentUser,
    get_audit,
    get_current_user,
    get_db,
    get_policies,
)

router = APIRouter(prefix="/api-uso", tags=["Governança da API"])

CAMINHO_AUDITORIA = PolicyPath("auditoria")

# Janela padrão da tela. Sete dias mostra o ciclo semanal de um robô — o que
# roda só de madrugada, o que roda só em dia útil — que 24 horas esconderia.
DIAS_PADRAO = 7


def _exigir_admin(
    current: CurrentUser,
    policies: PolicyRepository,
    audit: AuditRepository,
    db: Session,
) -> None:
    if evaluate(
        policies.policies_for_user(current.id), CAMINHO_AUDITORIA, Capability.ADMIN
    ):
        return
    audit.append(
        AuditEvent(
            action=AuditAction.ACCESS_DENIED,
            actor_id=current.id,
            actor_label=current.email,
            target_path=str(CAMINHO_AUDITORIA),
            outcome=AuditOutcome.FAILURE,
            reason="Sem permissão para ver a governança da API.",
            ip_address=current.ip_address,
            user_agent=current.user_agent,
        )
    )
    # Commit antes de propagar: o rollback da sessão levaria embora o
    # registro da negativa, e tentativa de ver o mapa de consumo sem
    # permissão é exatamente o que a trilha precisa guardar.
    db.commit()
    raise PermissionDeniedError("Esta área é restrita a quem administra auditoria.")


class ChamadaResponse(BaseModel):
    id: str
    recebida_em: datetime
    metodo: str
    caminho: str
    status: int
    resultado: str
    origem: str
    quem: str
    anonima: bool
    ip: str
    agente: str
    duracao_ms: int
    bytes_recebidos: int


class ConsumidorResponse(BaseModel):
    chave: str
    rotulo: str
    origem: str
    chamadas: int
    recusadas: int
    erros: int
    ultima_em: datetime | None
    duracao_media_ms: int


class RotaResponse(BaseModel):
    metodo: str
    caminho: str
    chamadas: int
    recusadas: int
    erros: int
    duracao_media_ms: int
    duracao_maxima_ms: int


class ResumoResponse(BaseModel):
    """Os números do topo da tela."""

    chamadas: int
    recusadas: int
    erros: int
    consumidores: int
    anonimas: int
    dias: int


class PanoramaResponse(BaseModel):
    resumo: ResumoResponse
    consumidores: list[ConsumidorResponse]
    rotas: list[RotaResponse]


def _filtro(dias: int, origem: str, resultado: str, aplicacao: str, limite: int) -> FiltroDeUso:
    """Monta o recorte, sempre **sem** as chamadas da própria tela.

    A exclusão é aplicada aqui e não só na gravação: ainda que um registro
    de origem `tela` entre por engano (classificação errada, importação),
    ele não aparece neste relatório.
    """
    origens: tuple[Origem, ...]
    if origem in ("aplicacao", "externa"):
        origens = (Origem(origem),)
    else:
        origens = (Origem.APLICACAO, Origem.EXTERNA)

    resultados: tuple[Resultado, ...] = ()
    if resultado:
        try:
            resultados = (Resultado(resultado),)
        except ValueError:
            resultados = ()

    return FiltroDeUso(
        desde=datetime.now(UTC) - timedelta(days=dias),
        origens=origens,
        resultados=resultados,
        aplicacao_id=aplicacao or None,
        limite=limite,
    )


@router.get(
    "/panorama",
    response_model=PanoramaResponse,
    summary="Quem consome a API e o que consome",
)
def panorama(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
    dias: Annotated[int, Query(ge=1, le=90)] = DIAS_PADRAO,
    origem: Annotated[str, Query()] = "",
) -> PanoramaResponse:
    _exigir_admin(current, policies, audit, db)

    registro = RegistroDeUsoSql(db)
    filtro = _filtro(dias, origem, "", "", 100)
    consumidores = registro.consumidores(filtro)
    rotas = registro.rotas(filtro)

    # O total vem da soma dos consumidores e não de uma consulta à parte:
    # duas consultas com recortes que se pretendem iguais acabam divergindo
    # quando alguém mexe num filtro e esquece do outro, e aí o topo da tela
    # deixa de bater com a lista logo abaixo.
    chamadas = sum(c.chamadas for c in consumidores)
    recusadas = sum(c.recusadas for c in consumidores)
    erros = sum(c.erros for c in consumidores)
    anonimas = sum(c.chamadas for c in consumidores if c.origem is Origem.EXTERNA and not c.rotulo)

    return PanoramaResponse(
        resumo=ResumoResponse(
            chamadas=chamadas,
            recusadas=recusadas,
            erros=erros,
            consumidores=len(consumidores),
            anonimas=anonimas,
            dias=dias,
        ),
        consumidores=[
            ConsumidorResponse(
                chave=c.chave,
                rotulo=c.rotulo,
                origem=c.origem.value,
                chamadas=c.chamadas,
                recusadas=c.recusadas,
                erros=c.erros,
                ultima_em=c.ultima_em,
                duracao_media_ms=c.duracao_media_ms,
            )
            for c in consumidores
        ],
        rotas=[
            RotaResponse(
                metodo=r.metodo,
                caminho=r.caminho,
                chamadas=r.chamadas,
                recusadas=r.recusadas,
                erros=r.erros,
                duracao_media_ms=r.duracao_media_ms,
                duracao_maxima_ms=r.duracao_maxima_ms,
            )
            for r in rotas
        ],
    )


@router.get(
    "/chamadas",
    response_model=list[ChamadaResponse],
    summary="As chamadas recebidas, uma a uma",
)
def chamadas(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
    dias: Annotated[int, Query(ge=1, le=90)] = DIAS_PADRAO,
    origem: Annotated[str, Query()] = "",
    resultado: Annotated[str, Query()] = "",
    aplicacao: Annotated[str, Query()] = "",
    limite: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[ChamadaResponse]:
    _exigir_admin(current, policies, audit, db)

    registro = RegistroDeUsoSql(db)
    return [
        ChamadaResponse(
            id=c.id,
            recebida_em=c.recebida_em,
            metodo=c.metodo,
            caminho=c.caminho,
            status=c.status,
            resultado=c.resultado.value,
            origem=c.origem.value,
            quem=c.quem,
            anonima=c.anonima,
            ip=c.ip,
            agente=c.agente,
            duracao_ms=c.duracao_ms,
            bytes_recebidos=c.bytes_recebidos,
        )
        for c in registro.listar(_filtro(dias, origem, resultado, aplicacao, limite))
    ]
