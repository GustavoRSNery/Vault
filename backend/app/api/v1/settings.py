"""Rotas da configuração operacional.

O que **não** está aqui é tão importante quanto o que está. Chave-mestra,
banco, destino da exportação e tamanhos de material criptográfico continuam
em variável de ambiente, e limites de segurança (quórum mínimo, teto do
lease) continuam constantes no código.

A pergunta que separa os dois grupos: *se alguém escolher o pior valor
possível, isso enfraquece a segurança?* Configuração que permite desligar a
própria proteção é pior que configuração nenhuma — dá a impressão de
flexibilidade e entrega um sistema que se desarma na primeira pressa.

Leitura é aberta a qualquer autenticado: o front precisa saber por quantos
segundos mostrar um segredo, e esconder isso não protege nada. Escrita exige
`ADMIN` em `admin`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.settings.entities import (
    ALERTA_CERTIFICADO_MAX,
    CAPACIDADES_DO_RANKING,
    ALERTA_CERTIFICADO_MIN,
    CUSTODIA_HORAS_MAX,
    CUSTODIA_HORAS_MIN,
    ROTACAO_PADRAO_MAX,
    ROTACAO_PADRAO_MIN,
    SEGUNDOS_VISIVEL_MAX,
    SEGUNDOS_VISIVEL_MIN,
    TRILHA_LIMITE_MAX,
    TRILHA_LIMITE_MIN,
)
from ...domain.shared.errors import PermissionDeniedError
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import (
    AuditRepository,
    ConfiguracaoRepository,
    PolicyRepository,
)
from ..deps import CurrentUser, get_audit, get_current_user, get_db, get_policies

router = APIRouter(prefix="/configuracao", tags=["Configuração"])

CAMINHO_ADMIN = PolicyPath("admin")


def get_configuracao(
    db: Annotated[Session, Depends(get_db)],
) -> ConfiguracaoRepository:
    return ConfiguracaoRepository(db)


class ConfiguracaoResponse(BaseModel):
    segundos_segredo_visivel: int
    custodia_horas_padrao: int
    alerta_certificado_dias: int
    rotacao_dias_padrao: int
    trilha_limite_padrao: int
    capacidade_do_ranking: str
    atualizado_por: str
    atualizado_em: datetime
    # Os limites viajam junto para que a tela mostre a faixa sem duplicar os
    # números: duplicados, divergem no primeiro ajuste.
    limites: dict[str, list[int]]
    # Pelo mesmo motivo: a tela monta as opções a partir daqui, e acrescentar
    # uma capacidade no domínio não exige mexer no front.
    capacidades_do_ranking: list[str]


class AtualizarConfiguracaoRequest(BaseModel):
    """Só o que for enviado é alterado; o resto fica como está."""

    segundos_segredo_visivel: int | None = Field(
        default=None, ge=SEGUNDOS_VISIVEL_MIN, le=SEGUNDOS_VISIVEL_MAX
    )
    custodia_horas_padrao: int | None = Field(
        default=None, ge=CUSTODIA_HORAS_MIN, le=CUSTODIA_HORAS_MAX
    )
    alerta_certificado_dias: int | None = Field(
        default=None, ge=ALERTA_CERTIFICADO_MIN, le=ALERTA_CERTIFICADO_MAX
    )
    rotacao_dias_padrao: int | None = Field(
        default=None, ge=ROTACAO_PADRAO_MIN, le=ROTACAO_PADRAO_MAX
    )
    trilha_limite_padrao: int | None = Field(
        default=None, ge=TRILHA_LIMITE_MIN, le=TRILHA_LIMITE_MAX
    )
    # Sem `Literal` aqui de proposito: a lista valida mora no dominio, e
    # repeti-la no schema criaria duas fontes que divergem no primeiro ajuste.
    # O valor invalido e recusado por `ConfiguracaoOperacional`, que responde
    # 422 com a lista de opcoes.
    capacidade_do_ranking: str | None = None


LIMITES = {
    "segundos_segredo_visivel": [SEGUNDOS_VISIVEL_MIN, SEGUNDOS_VISIVEL_MAX],
    "custodia_horas_padrao": [CUSTODIA_HORAS_MIN, CUSTODIA_HORAS_MAX],
    "alerta_certificado_dias": [ALERTA_CERTIFICADO_MIN, ALERTA_CERTIFICADO_MAX],
    "rotacao_dias_padrao": [ROTACAO_PADRAO_MIN, ROTACAO_PADRAO_MAX],
    "trilha_limite_padrao": [TRILHA_LIMITE_MIN, TRILHA_LIMITE_MAX],
}


@router.get("", response_model=ConfiguracaoResponse, summary="Ler a configuração")
def ler(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    config: Annotated[ConfiguracaoRepository, Depends(get_configuracao)],
) -> ConfiguracaoResponse:
    """Aberta a qualquer autenticado.

    O front precisa saber por quantos segundos mostrar um segredo; esconder
    isso não protegeria nada e só faria a tela adivinhar.
    """
    return _resposta(config.atual())


@router.put("", response_model=ConfiguracaoResponse, summary="Alterar a configuração")
def alterar(
    payload: AtualizarConfiguracaoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    config: Annotated[ConfiguracaoRepository, Depends(get_configuracao)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> ConfiguracaoResponse:
    """Altera o que foi enviado e registra o antes e o depois.

    "Configuração alterada" não permite revisar nada — mudança silenciosa de
    prazo é exatamente o que uma auditoria procura.
    """
    if not evaluate(
        policies.policies_for_user(current.id), CAMINHO_ADMIN, Capability.ADMIN
    ):
        audit.append(
            AuditEvent(
                action=AuditAction.ACCESS_DENIED,
                actor_id=current.id,
                actor_label=current.email,
                target_path="configuracao",
                outcome=AuditOutcome.FAILURE,
                reason="Sem permissão para alterar a configuração.",
                ip_address=current.ip_address,
                user_agent=current.user_agent,
            )
        )
        db.commit()
        raise PermissionDeniedError(
            "Apenas administradores alteram a configuração."
        )

    atual = config.atual()
    nova = atual.com(
        segundos_segredo_visivel=payload.segundos_segredo_visivel,
        custodia_horas_padrao=payload.custodia_horas_padrao,
        alerta_certificado_dias=payload.alerta_certificado_dias,
        rotacao_dias_padrao=payload.rotacao_dias_padrao,
        trilha_limite_padrao=payload.trilha_limite_padrao,
        capacidade_do_ranking=payload.capacidade_do_ranking,
        atualizado_por=current.email,
    )

    mudancas = atual.diferencas(nova)
    if not mudancas:
        # Nada mudou: não polui a trilha com evento sem conteúdo.
        return _resposta(atual)

    salva = config.salvar(nova)
    audit.append(
        AuditEvent(
            action=AuditAction.SETTINGS_UPDATED,
            actor_id=current.id,
            actor_label=current.email,
            target_path="configuracao",
            reason="; ".join(mudancas),
            ip_address=current.ip_address,
            user_agent=current.user_agent,
        )
    )
    return _resposta(salva)


def _resposta(config) -> ConfiguracaoResponse:  # noqa: ANN001
    return ConfiguracaoResponse(
        segundos_segredo_visivel=config.segundos_segredo_visivel,
        custodia_horas_padrao=config.custodia_horas_padrao,
        alerta_certificado_dias=config.alerta_certificado_dias,
        rotacao_dias_padrao=config.rotacao_dias_padrao,
        trilha_limite_padrao=config.trilha_limite_padrao,
        capacidade_do_ranking=config.capacidade_do_ranking,
        atualizado_por=config.atualizado_por,
        atualizado_em=config.atualizado_em,
        limites=LIMITES,
        capacidades_do_ranking=list(CAPACIDADES_DO_RANKING),
    )
