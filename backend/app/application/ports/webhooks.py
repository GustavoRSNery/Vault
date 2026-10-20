"""Porta de entrega de webhooks.

O domínio sabe montar o corpo, assinar e agendar a próxima tentativa. O que
ele **não** sabe é fazer requisição — e é de propósito: assim a assinatura e
o cronograma de reentrega são testáveis sem rede, sem servidor de mentira e
sem esperar segundos de verdade.

O contrato é deliberadamente estreito: uma entrega, um resultado. Quem
implementa não decide quando reenviar nem quantas vezes — isso é do domínio,
onde está a regra. Um adaptador que resolvesse reentrega por conta própria
produziria duas políticas de retentativa concorrendo, e a fila do Vault
mostraria um número que não bate com o que de fato aconteceu.

Referência da especificação: https://github.com/standard-webhooks/standard-webhooks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ResultadoDaEntrega:
    """O que o destino respondeu.

    `status` é o HTTP quando houve resposta, e `None` quando nem chegou a
    haver (DNS, recusa de conexão, estouro de tempo). A diferença importa: um
    destino que responde 500 está no ar e quebrado; um que não responde pode
    estar sendo trocado — e os dois merecem a mesma reentrega, mas leituras
    diferentes de quem investiga.
    """

    sucesso: bool
    status: int | None = None
    erro: str = ""
    # Segundos pedidos pelo destino no cabeçalho `retry-after`, quando houver.
    # O domínio respeita esse pedido em vez do próprio cronograma.
    retry_after: int | None = None
    # `410 Gone`: o destino declarou que não existe mais. Continuar tentando
    # é encher a fila com o que já respondeu que não.
    desativar_destino: bool = False


@runtime_checkable
class EntregadorDeWebhook(Protocol):
    """Envia uma entrega já montada e assinada."""

    @property
    def nome(self) -> str:
        """Identificação do adaptador, para a trilha e para a tela."""
        ...

    def entregar(
        self,
        *,
        url: str,
        corpo: str,
        cabecalhos: dict[str, str],
        timeout_segundos: int = 20,
    ) -> ResultadoDaEntrega:
        """Faz a requisição e relata o que aconteceu.

        **Envia `corpo` byte a byte, sem reserializar.** O corpo já foi
        assinado exatamente como está; qualquer reformatação (reordenar
        chaves, reindentar, trocar o separador) muda os bytes e o destino
        rejeita uma assinatura que, do nosso lado, estava correta. É o erro
        mais comum nesta especificação.

        Não levanta exceção por falha de rede nem por status de erro: o
        resultado descreve a falha, e quem chama decide o que fazer. Exceção
        aqui obrigaria cada chamador a repetir o mesmo `try` e a inventar sua
        própria tradução de erro.
        """
        ...
