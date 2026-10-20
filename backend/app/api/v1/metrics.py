"""Séries e rankings para os gráficos do painel.

Tudo aqui é derivado da trilha de auditoria, nunca de contador próprio: a
trilha já é a fonte de verdade do que o sistema fez, e um contador paralelo
divergiria dela no primeiro erro de escrita — com o agravante de que o
gráfico mentiria com ar de autoridade.

**Visibilidade.** Um ranking de "quem mais acessou" expõe a atividade dos
colegas, que é exatamente o que a trilha protege. Sem essa regra, o painel
seria a porta lateral para o que a tela de auditoria tranca pela porta da
frente.

Qual capacidade em `auditoria` libera os rankings é **configurável**
(`capacidade_do_ranking`): `admin` restringe a administradores, `approve`
estende a quem aprova pedidos de acesso — o perfil de gestor. O padrão é o
restritivo, e a escolha fica registrada na trilha como qualquer outra
mudança de configuração.

A série de atividade continua visível a qualquer autenticado: ela mostra o
movimento do cofre em agregado, sem dizer quem fez o quê.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditOutcome
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import (
    AuditRepository,
    ConfiguracaoRepository,
    PolicyRepository,
)
from ..deps import CurrentUser, get_audit, get_current_user, get_policies
from .settings import get_configuracao

router = APIRouter(prefix="/metricas", tags=["Métricas"])

CAMINHO_AUDITORIA = PolicyPath("auditoria")

# As três faixas do gráfico de atividade. Separadas porque respondem a
# perguntas diferentes: volume de trabalho, tentativa barrada e erro de
# autenticação. Somá-las num total só esconderia a crista vermelha.
ACOES_NEGADAS = (
    str(AuditAction.ACCESS_DENIED),
    str(AuditAction.CREDENTIAL_CHECKOUT_DENIED),
    str(AuditAction.ACCESS_DENIED_REQUEST),
)
ACOES_FALHA_LOGIN = (
    str(AuditAction.LOGIN_FAILURE),
    str(AuditAction.PASSWORD_RESET_FAILED),
)
ACOES_LEITURA = (str(AuditAction.SECRET_REVEALED),)


class PontoDaSerie(BaseModel):
    dia: date
    sucesso: int
    negado: int
    falha_login: int


class ItemDoRanking(BaseModel):
    rotulo: str
    quantas: int


class MetricasResponse(BaseModel):
    dias: int
    # Dias com evento, não o tamanho da janela pedida: é o que permite à tela
    # dizer "3 dias de histórico" em vez de desenhar 30 posições vazias e
    # sugerir uma queda de atividade que não houve.
    dias_com_dado: int
    total: int
    serie: list[PontoDaSerie]
    por_ator: list[ItemDoRanking]
    por_caminho: list[ItemDoRanking]
    restrito: bool
    # Qual capacidade estava valendo nesta leitura. A tela usa para explicar
    # ao usuário POR QUE não vê os rankings, em vez de simplesmente omiti-los
    # e deixar parecer que não há dado.
    capacidade_exigida: str


@router.get("/serie", response_model=MetricasResponse, summary="Série e rankings")
def serie(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    config: Annotated[ConfiguracaoRepository, Depends(get_configuracao)],
    dias: Annotated[int, Query(ge=1, le=365)] = 30,
) -> MetricasResponse:
    """Atividade por dia e os dois rankings, na janela pedida."""
    exigida = Capability(config.atual().capacidade_do_ranking)
    # ADMIN passa sempre, mesmo quando a instalação exige APPROVE: quem
    # administra a auditoria já lê a trilha inteira pela tela de auditoria, e
    # recusar aqui só produziria a pergunta "por que o painel esconde o que a
    # trilha mostra?".
    politicas = policies.policies_for_user(current.id)
    pode_ver_tudo = evaluate(politicas, CAMINHO_AUDITORIA, exigida) or evaluate(
        politicas, CAMINHO_AUDITORIA, Capability.ADMIN
    )

    # O corte é por dia inteiro, não por "agora menos N dias": senão a barra
    # mais antiga nasceria cortada ao meio e encolheria a cada recarga.
    hoje = datetime.now(UTC).date()
    desde = datetime.combine(
        hoje - timedelta(days=dias - 1), datetime.min.time(), tzinfo=UTC
    )

    linhas = audit.serie_por_dia(desde=desde)

    por_dia: dict[date, dict[str, int]] = {}
    for dia, acao, desfecho, quantas in linhas:
        balde = por_dia.setdefault(dia, {"sucesso": 0, "negado": 0, "falha_login": 0})
        if acao in ACOES_NEGADAS:
            balde["negado"] += quantas
        elif acao in ACOES_FALHA_LOGIN:
            balde["falha_login"] += quantas
        elif desfecho == str(AuditOutcome.SUCCESS):
            balde["sucesso"] += quantas
        else:
            # Falha que não é login nem negação (erro de integração, por
            # exemplo) entra em `negado`: é anomalia, e silenciá-la faria as
            # faixas não fecharem o total mostrado no topo.
            balde["negado"] += quantas

    # A série sai com TODOS os dias da janela, inclusive os vazios: um dia sem
    # evento é informação ("ninguém acessou"), e omiti-lo faria o eixo X
    # mentir, colando terça em sexta como se fossem consecutivas.
    serie_cheia = []
    for passo in range(dias):
        dia = hoje - timedelta(days=dias - 1 - passo)
        balde = por_dia.get(dia, {"sucesso": 0, "negado": 0, "falha_login": 0})
        serie_cheia.append(
            PontoDaSerie(
                dia=dia,
                sucesso=balde["sucesso"],
                negado=balde["negado"],
                falha_login=balde["falha_login"],
            )
        )

    total = sum(p.sucesso + p.negado + p.falha_login for p in serie_cheia)
    # Derivado da serie, NAO de `len(por_dia)`: aquele balde recebe o que a
    # consulta trouxe, e qualquer folga no filtro de data contaria um dia
    # fora da janela. Contar sobre o que a tela de fato desenha mantem o
    # numero e o grafico contando a mesma coisa.
    dias_com_dado = sum(
        1 for p in serie_cheia if p.sucesso or p.negado or p.falha_login
    )

    if pode_ver_tudo:
        por_ator = [
            ItemDoRanking(rotulo=rotulo, quantas=quantas)
            for rotulo, quantas in audit.ranking(
                "ator",
                acoes=ACOES_LEITURA,
                desde=desde,
                desfecho=str(AuditOutcome.SUCCESS),
            )
        ]
        por_caminho = [
            ItemDoRanking(rotulo=rotulo, quantas=quantas)
            for rotulo, quantas in audit.ranking(
                "caminho",
                acoes=ACOES_LEITURA,
                desde=desde,
                desfecho=str(AuditOutcome.SUCCESS),
            )
        ]
    else:
        # Sem ADMIN os rankings não saem. Devolver os próprios números num
        # ranking de um item só sugeriria uma comparação que não existe.
        por_ator, por_caminho = [], []

    return MetricasResponse(
        dias=dias,
        dias_com_dado=dias_com_dado,
        total=total,
        serie=serie_cheia,
        por_ator=por_ator,
        por_caminho=por_caminho,
        restrito=not pode_ver_tudo,
        capacidade_exigida=str(exigida),
    )
