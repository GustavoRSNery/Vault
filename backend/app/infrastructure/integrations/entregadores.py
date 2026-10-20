"""Adaptadores de entrega de webhook.

Dois, por ora:

- `EntregadorDeEnsaio` — não envia nada; registra o que enviaria. É o padrão
  enquanto não há destino real, e serve para provar o fluxo inteiro
  (assinatura, fila, reentrega) sem depender de rede.
- `EntregadorHttp` — a implementação de verdade, pronta para ligar. Usa
  `httpx`, que já é dependência do projeto.

O ensaio é o padrão de propósito: um sistema recém-instalado que começasse a
disparar requisições para fora, com eventos de cofre, seria uma surpresa
desagradável. Quem quer entrega real liga o adaptador HTTP conscientemente.
"""

from __future__ import annotations

from ...application.ports.webhooks import ResultadoDaEntrega

# Status que valem reentrega mesmo sendo "erro do cliente": o destino está
# pedindo calma (429) ou atrás de um proxy com problema (502/504). Os demais
# 4xx indicam pedido malformado, e insistir só repetiria o mesmo erro.
STATUS_QUE_VALEM_REENVIO = {408, 409, 423, 425, 429}


class EntregadorDeEnsaio:
    """Registra a entrega sem sair para a rede.

    Guarda as entregas em memória para que um teste — ou a tela de
    diagnóstico — mostre exatamente o que teria ido, com os cabeçalhos de
    assinatura. É o mais perto de "ver o webhook" sem ter destino.
    """

    def __init__(self) -> None:
        self.enviadas: list[dict] = []

    @property
    def nome(self) -> str:
        return "ensaio"

    def entregar(
        self,
        *,
        url: str,
        corpo: str,
        cabecalhos: dict[str, str],
        timeout_segundos: int = 20,
    ) -> ResultadoDaEntrega:
        self.enviadas.append(
            {"url": url, "corpo": corpo, "cabecalhos": dict(cabecalhos)}
        )
        # Sucesso porque o ensaio não tem como falhar: fingir falha aleatória
        # faria a fila encher de reentregas que não ensinam nada.
        return ResultadoDaEntrega(sucesso=True, status=200)


class EntregadorHttp:
    """Entrega de verdade, por HTTP.

    Pronto para ligar: basta registrá-lo no lugar do ensaio. Não é o padrão
    porque disparar eventos de cofre para fora é decisão de quem opera, não
    do instalador.
    """

    @property
    def nome(self) -> str:
        return "http"

    def entregar(
        self,
        *,
        url: str,
        corpo: str,
        cabecalhos: dict[str, str],
        timeout_segundos: int = 20,
    ) -> ResultadoDaEntrega:
        import httpx

        try:
            resposta = httpx.post(
                url,
                # `content=` e não `json=`: o corpo já foi assinado byte a
                # byte, e deixar o cliente reserializar mudaria esses bytes
                # e invalidaria a assinatura do outro lado.
                content=corpo.encode("utf-8"),
                headers={**cabecalhos, "Content-Type": "application/json"},
                timeout=timeout_segundos,
                # Redirecionamento não é seguido: a especificação manda
                # tratar 3xx como falha. Seguir levaria o evento assinado —
                # com caminhos de segredos — para um host que não é o
                # cadastrado.
                follow_redirects=False,
            )
        except Exception as erro:  # noqa: BLE001
            # Nem chegou a haver resposta: DNS, recusa, estouro de tempo.
            return ResultadoDaEntrega(sucesso=False, erro=str(erro)[:500])

        if 200 <= resposta.status_code < 300:
            return ResultadoDaEntrega(sucesso=True, status=resposta.status_code)

        if resposta.status_code == 410:
            # O destino declarou que não existe mais.
            return ResultadoDaEntrega(
                sucesso=False,
                status=410,
                erro="O destino respondeu 410 Gone: endpoint desligado.",
                desativar_destino=True,
            )

        retry_after = _ler_retry_after(resposta.headers.get("retry-after"))

        permanente = (
            400 <= resposta.status_code < 500
            and resposta.status_code not in STATUS_QUE_VALEM_REENVIO
        )
        detalhe = (
            "Pedido recusado pelo destino; reenviar repetiria o mesmo erro."
            if permanente
            else "Falha temporária; será reenviado."
        )
        return ResultadoDaEntrega(
            sucesso=False,
            status=resposta.status_code,
            erro=f"HTTP {resposta.status_code}. {detalhe}",
            retry_after=retry_after,
            # 4xx permanente também desliga: insistir num pedido malformado
            # é gastar a fila com o que nunca vai passar.
            desativar_destino=permanente,
        )


def _ler_retry_after(valor: str | None) -> int | None:
    """Lê `retry-after` em segundos.

    Só a forma numérica: a forma com data HTTP existe, mas depende do relógio
    do destino, e aceitar uma data no passado agendaria uma reentrega
    imediata em loop.
    """
    if not valor:
        return None
    try:
        segundos = int(valor.strip())
    except ValueError:
        return None
    # Um destino que pede uma semana efetivamente desliga a integração sem
    # dizer; o teto deixa a fila andar e a tela mostrar a falha.
    return max(0, min(segundos, 86_400))
