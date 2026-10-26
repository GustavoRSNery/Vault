"""Porta do registro de uso da API.

Separada do repositório de auditoria de propósito. A trilha de auditoria é
**prova**: encadeada, exportada para destino externo, nunca apagada. O
registro de uso é **operacional**: volume alto, consultado por período, e
descartado depois de 90 dias. Misturar os dois forçaria uma das duas
naturezas na outra — ou a trilha ganharia expurgo, ou o uso ganharia
encadeamento que ninguém precisa conferir.

`registrar` não devolve nada e **não pode derrubar a requisição**: quem
implementa engole o próprio erro. Um relatório de uso que faz a API
responder 500 porque o banco de log encheu é pior que não ter relatório.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ...domain.apiusage.entities import ChamadaDeApi, Origem, Resultado


@dataclass(frozen=True, slots=True)
class FiltroDeUso:
    """Recorte de uma consulta ao registro.

    Tudo opcional: sem filtro nenhum, devolve o período inteiro. `origens`
    vazio significa "todas" — o padrão de esconder a tela é decisão da
    camada de cima, não deste filtro.
    """

    desde: datetime | None = None
    ate: datetime | None = None
    origens: tuple[Origem, ...] = ()
    resultados: tuple[Resultado, ...] = ()
    aplicacao_id: str | None = None
    # Prefixo do caminho, para olhar uma família de rotas de uma vez.
    caminho: str = ""
    limite: int = 200


@dataclass(frozen=True, slots=True)
class ConsumidorDeApi:
    """Um consumidor agregado, para a visão de "quem está usando"."""

    chave: str
    rotulo: str
    origem: Origem
    chamadas: int
    recusadas: int
    erros: int
    ultima_em: datetime | None
    duracao_media_ms: int


@dataclass(frozen=True, slots=True)
class RotaDeApi:
    """Uma rota agregada, para a visão de "o que está sendo consumido"."""

    metodo: str
    caminho: str
    chamadas: int
    recusadas: int
    erros: int
    duracao_media_ms: int
    duracao_maxima_ms: int


@runtime_checkable
class RegistroDeUsoDaApi(Protocol):
    """Onde as chamadas recebidas ficam registradas."""

    def registrar(self, chamada: ChamadaDeApi) -> None:
        """Guarda uma chamada. Nunca levanta: falha de log não quebra a API."""
        ...

    def listar(self, filtro: FiltroDeUso) -> list[ChamadaDeApi]:
        """As chamadas do recorte, mais recentes primeiro."""
        ...

    def consumidores(self, filtro: FiltroDeUso) -> list[ConsumidorDeApi]:
        """Quem chamou, agregado, do que mais chamou para o que menos."""
        ...

    def rotas(self, filtro: FiltroDeUso) -> list[RotaDeApi]:
        """Quais rotas foram chamadas, agregadas."""
        ...

    def expurgar(self, antes_de: datetime) -> int:
        """Apaga o que é mais antigo que a data. Devolve quantas apagou."""
        ...
