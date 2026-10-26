"""Repositório do registro de uso da API.

Em arquivo próprio: `repositories.py` já passa de duas mil linhas, e este
adaptador não compartilha nada com os outros além da sessão.

**Por que as agregações são SQL e não Python.** Contar chamadas por
consumidor lendo tudo para a memória funciona com mil linhas e derruba o
processo com um milhão — e um milhão é o volume normal de 90 dias de uma
API consumida por robôs. O `GROUP BY` resolve isso no banco, que é onde os
índices estão.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from ...application.ports.apiusage import (
    ConsumidorDeApi,
    FiltroDeUso,
    RotaDeApi,
)
from ...domain.apiusage.entities import ChamadaDeApi, Origem, Resultado
from .models import ChamadaApiModel


def _para_dominio(linha: ChamadaApiModel) -> ChamadaDeApi:
    return ChamadaDeApi(
        id=linha.id,
        recebida_em=linha.recebida_em,
        metodo=linha.metodo,
        caminho=linha.caminho,
        status=linha.status,
        resultado=Resultado(linha.resultado),
        origem=Origem(linha.origem),
        aplicacao_id=linha.aplicacao_id,
        aplicacao_nome=linha.aplicacao_nome,
        usuario_id=linha.usuario_id,
        usuario_email=linha.usuario_email,
        ip=linha.ip,
        agente=linha.agente,
        duracao_ms=linha.duracao_ms,
        bytes_recebidos=linha.bytes_recebidos,
    )


class RegistroDeUsoSql:
    """Guarda e consulta as chamadas recebidas."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def registrar(self, chamada: ChamadaDeApi) -> None:
        """Grava a chamada. Engole o próprio erro, por contrato da porta.

        Uma falha ao gravar log não pode transformar uma requisição bem
        sucedida em erro para quem chamou — o cliente já recebeu a resposta
        quando isto roda. O rollback é necessário porque uma sessão com erro
        pendente recusa qualquer uso posterior.
        """
        try:
            self._session.add(
                ChamadaApiModel(
                    id=chamada.id,
                    recebida_em=chamada.recebida_em,
                    metodo=chamada.metodo,
                    caminho=chamada.caminho,
                    status=chamada.status,
                    resultado=chamada.resultado.value,
                    origem=chamada.origem.value,
                    aplicacao_id=chamada.aplicacao_id,
                    aplicacao_nome=chamada.aplicacao_nome,
                    usuario_id=chamada.usuario_id,
                    usuario_email=chamada.usuario_email,
                    ip=chamada.ip,
                    agente=chamada.agente,
                    duracao_ms=chamada.duracao_ms,
                    bytes_recebidos=chamada.bytes_recebidos,
                )
            )
            self._session.commit()
        except Exception:  # noqa: BLE001
            self._session.rollback()

    def _condicoes(self, filtro: FiltroDeUso) -> list[Any]:
        onde: list[Any] = []
        if filtro.desde is not None:
            onde.append(ChamadaApiModel.recebida_em >= filtro.desde)
        if filtro.ate is not None:
            onde.append(ChamadaApiModel.recebida_em <= filtro.ate)
        if filtro.origens:
            onde.append(
                ChamadaApiModel.origem.in_([o.value for o in filtro.origens])
            )
        if filtro.resultados:
            onde.append(
                ChamadaApiModel.resultado.in_([r.value for r in filtro.resultados])
            )
        if filtro.aplicacao_id:
            onde.append(ChamadaApiModel.aplicacao_id == filtro.aplicacao_id)
        if filtro.caminho:
            # `startswith` e não `contains`: o índice de caminho serve o
            # prefixo e não serve o "contém", que varreria a tabela.
            onde.append(ChamadaApiModel.caminho.startswith(filtro.caminho))
        return onde

    def listar(self, filtro: FiltroDeUso) -> list[ChamadaDeApi]:
        consulta = (
            select(ChamadaApiModel)
            .where(*self._condicoes(filtro))
            .order_by(ChamadaApiModel.recebida_em.desc())
            .limit(max(1, min(filtro.limite, 1000)))
        )
        return [_para_dominio(linha) for linha in self._session.scalars(consulta)]

    def consumidores(self, filtro: FiltroDeUso) -> list[ConsumidorDeApi]:
        """Agrega por quem chamou.

        A chave é a aplicação quando há uma, o e-mail quando é pessoa, e o
        IP quando não há identidade nenhuma. O IP no lugar de um "anônimo"
        único é o que separa uma varredura vinda de um endereço de várias
        tentativas espalhadas — que são problemas diferentes.
        """
        chave = func.coalesce(
            func.nullif(ChamadaApiModel.aplicacao_id, ""),
            func.nullif(ChamadaApiModel.usuario_email, ""),
            func.nullif(ChamadaApiModel.ip, ""),
            "desconhecido",
        )
        rotulo = func.coalesce(
            func.nullif(ChamadaApiModel.aplicacao_nome, ""),
            func.nullif(ChamadaApiModel.usuario_email, ""),
            func.nullif(ChamadaApiModel.ip, ""),
            "desconhecido",
        )
        recusadas = func.sum(
            case((ChamadaApiModel.resultado == Resultado.RECUSADO.value, 1), else_=0)
        )
        erros = func.sum(
            case((ChamadaApiModel.resultado == Resultado.ERRO.value, 1), else_=0)
        )
        consulta = (
            select(
                chave.label("chave"),
                func.min(rotulo).label("rotulo"),
                func.min(ChamadaApiModel.origem).label("origem"),
                func.count().label("chamadas"),
                recusadas.label("recusadas"),
                erros.label("erros"),
                func.max(ChamadaApiModel.recebida_em).label("ultima_em"),
                func.avg(ChamadaApiModel.duracao_ms).label("media"),
            )
            .where(*self._condicoes(filtro))
            .group_by(chave)
            .order_by(func.count().desc())
            .limit(max(1, min(filtro.limite, 500)))
        )
        saida: list[ConsumidorDeApi] = []
        for linha in self._session.execute(consulta):
            saida.append(
                ConsumidorDeApi(
                    chave=str(linha.chave),
                    rotulo=str(linha.rotulo),
                    origem=Origem(linha.origem),
                    chamadas=int(linha.chamadas or 0),
                    recusadas=int(linha.recusadas or 0),
                    erros=int(linha.erros or 0),
                    ultima_em=linha.ultima_em,
                    duracao_media_ms=int(linha.media or 0),
                )
            )
        return saida

    def rotas(self, filtro: FiltroDeUso) -> list[RotaDeApi]:
        recusadas = func.sum(
            case((ChamadaApiModel.resultado == Resultado.RECUSADO.value, 1), else_=0)
        )
        erros = func.sum(
            case((ChamadaApiModel.resultado == Resultado.ERRO.value, 1), else_=0)
        )
        consulta = (
            select(
                ChamadaApiModel.metodo,
                ChamadaApiModel.caminho,
                func.count().label("chamadas"),
                recusadas.label("recusadas"),
                erros.label("erros"),
                func.avg(ChamadaApiModel.duracao_ms).label("media"),
                func.max(ChamadaApiModel.duracao_ms).label("maxima"),
            )
            .where(*self._condicoes(filtro))
            .group_by(ChamadaApiModel.metodo, ChamadaApiModel.caminho)
            .order_by(func.count().desc())
            .limit(max(1, min(filtro.limite, 500)))
        )
        return [
            RotaDeApi(
                metodo=linha.metodo,
                caminho=linha.caminho,
                chamadas=int(linha.chamadas or 0),
                recusadas=int(linha.recusadas or 0),
                erros=int(linha.erros or 0),
                duracao_media_ms=int(linha.media or 0),
                duracao_maxima_ms=int(linha.maxima or 0),
            )
            for linha in self._session.execute(consulta)
        ]

    def expurgar(self, antes_de: datetime) -> int:
        """Apaga o que passou da retenção. Devolve quantas linhas saíram."""
        resultado = self._session.execute(
            delete(ChamadaApiModel).where(ChamadaApiModel.recebida_em < antes_de)
        )
        self._session.commit()
        # `rowcount` existe no CursorResult de um DELETE, mas o tipo
        # declarado de `execute` e o Result generico, que nao o anuncia.
        return int(getattr(resultado, "rowcount", 0) or 0)
