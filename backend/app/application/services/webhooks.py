"""Publicação e entrega de webhooks.

Duas operações, separadas de propósito:

- `publicar` — enfileira o evento para cada destino interessado. Roda dentro
  da requisição que gerou o evento e **não faz rede**: se fizesse, revelar um
  segredo passaria a depender de um servidor de terceiro estar no ar, e um
  destino lento viraria lentidão do cofre.
- `despachar` — tira da fila o que está pronto e entrega. Roda fora da
  requisição (agendador, comando, laço de trabalho).

Essa separação é a diferença entre um cofre que avisa integrações e um cofre
que para quando a integração para.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...domain.integrations.entities import (
    Destino,
    Entrega,
    assinar,
    montar_corpo,
)
from ...domain.shared.value_objects import utcnow
from ..ports.webhooks import EntregadorDeWebhook


@dataclass(frozen=True, slots=True)
class ResumoDoDespacho:
    tentadas: int = 0
    entregues: int = 0
    falhadas: int = 0
    desistidas: int = 0
    destinos_desligados: int = 0


def publicar(
    tipo: str,
    dados: dict,
    *,
    destinos: list[Destino],
    agora: datetime | None = None,
) -> list[Entrega]:
    """Monta o evento e enfileira para quem assina esse tipo.

    O corpo é montado **uma vez** e compartilhado entre os destinos: é o
    mesmo evento, e remontar por destino geraria timestamps ligeiramente
    diferentes para o que aconteceu no mesmo instante.
    """
    momento = agora or utcnow()
    interessados = [d for d in destinos if d.ativo and d.interessa(tipo)]
    if not interessados:
        return []

    corpo = montar_corpo(tipo, dados, agora=momento)
    return [
        Entrega(destino_id=d.id, tipo=tipo, corpo=corpo, proxima_em=momento)
        for d in interessados
    ]


def cabecalhos_de(entrega: Entrega, destino: Destino, agora: datetime | None = None) -> dict[str, str]:
    """Os três cabeçalhos da especificação.

    O timestamp é o **do envio**, não o da criação do evento: é ele que o
    destino compara com o próprio relógio para recusar repetição. Usar o
    instante da criação faria toda reentrega chegar fora da janela e ser
    recusada — a integração pareceria quebrada justamente quando o
    mecanismo de reentrega funcionasse.
    """
    timestamp = int((agora or utcnow()).timestamp())
    return {
        "webhook-id": entrega.id_evento,
        "webhook-timestamp": str(timestamp),
        "webhook-signature": assinar(
            destino.segredo,
            id_evento=entrega.id_evento,
            timestamp=timestamp,
            corpo=entrega.corpo,
        ),
    }


def despachar(
    entregas: list[Entrega],
    destinos_por_id: dict[str, Destino],
    entregador: EntregadorDeWebhook,
    *,
    agora: datetime | None = None,
) -> tuple[ResumoDoDespacho, list[Entrega], list[Destino]]:
    """Entrega o que está pronto e devolve o que mudou.

    Devolve em vez de salvar: o serviço não conhece repositório, então quem
    chama decide a transação. Isso mantém esta função testável sem banco.
    """
    momento = agora or utcnow()
    tentadas = entregues = falhadas = desistidas = 0
    destinos_tocados: dict[str, Destino] = {}

    for entrega in entregas:
        destino = destinos_por_id.get(entrega.destino_id)
        if destino is None or not destino.ativo:
            # Destino removido ou desligado entre o enfileiramento e agora:
            # a entrega fica na fila, sem tentativa gasta.
            continue

        tentadas += 1
        resultado = entregador.entregar(
            url=destino.url,
            corpo=entrega.corpo,
            cabecalhos=cabecalhos_de(entrega, destino, momento),
        )

        if resultado.sucesso:
            entrega.marcar_entregue(resultado.status or 200, agora=momento)
            destino.registrar_sucesso(momento)
            entregues += 1
        else:
            entrega.marcar_falha(
                resultado.erro,
                status=resultado.status,
                agora=momento,
                retry_after=resultado.retry_after,
            )
            destino.registrar_falha(resultado.erro, momento)
            if resultado.desativar_destino:
                destino.desligar(resultado.erro)
            falhadas += 1
            if entrega.esgotou:
                desistidas += 1

        destinos_tocados[destino.id] = destino

    desligados = sum(1 for d in destinos_tocados.values() if not d.ativo)
    resumo = ResumoDoDespacho(
        tentadas=tentadas,
        entregues=entregues,
        falhadas=falhadas,
        desistidas=desistidas,
        destinos_desligados=desligados,
    )
    return resumo, entregas, list(destinos_tocados.values())


# ------------------------------------------- da trilha para o evento publicado

# Quais ações da trilha viram evento de integração, e com que nome.
#
# É um mapa explícito, não uma conversão automática do nome da ação: nem todo
# evento da trilha interessa a um sistema de fora (login, listagem), e o nome
# publicado é contrato com quem assina — derivá-lo do nome interno faria uma
# renomeação de código quebrar integrações de terceiros em silêncio.
ACAO_PARA_EVENTO: dict[str, str] = {
    "segredo_revelado": "segredo.revelado",
    "segredo_criado": "segredo.criado",
    "segredo_atualizado": "segredo.alterado",
    "segredo_excluido": "segredo.excluido",
    "credencial_retirada": "credencial.retirada",
    "credencial_devolvida": "credencial.devolvida",
    "acesso_negado": "acesso.negado",
    "acesso_remoto_iniciado": "acesso.remoto_iniciado",
    "sessao_aberta": "sessao.aberta",
    "sessao_encerrada": "sessao.encerrada",
    "cofre_selado": "cofre.selado",
    "cofre_desselado": "cofre.desselado",
    "acesso_solicitado": "aprovacao.solicitada",
    "acesso_aprovado": "aprovacao.concedida",
    "credencial_rotacionada": "credencial.devolvida",
    "sessao_derrubada": "sessao.encerrada",
}


def dados_do_evento(evento) -> dict:  # noqa: ANN001
    """O que vai no `data` do webhook.

    **Nunca o valor de um segredo** — a trilha também não o guarda. Vão o
    caminho, quem fez e o resultado: o suficiente para o destino reagir
    (abrir chamado, alertar, correlacionar) sem receber material secreto.
    """
    return {
        "acao": str(evento.action),
        "alvo": evento.target_path,
        "ator": evento.actor_label,
        "resultado": str(evento.outcome),
        "motivo": evento.reason,
        "ip": evento.ip_address,
        "sequencia": evento.sequence,
        "ocorrido_em": evento.occurred_at.isoformat(),
    }


def enfileirar_da_trilha(
    eventos: list,  # noqa: ANN001
    destinos: list[Destino],
) -> tuple[list[Entrega], int]:
    """Converte eventos da trilha em entregas e devolve até onde leu.

    O segundo valor é a maior sequência vista, inclusive de eventos que
    ninguém assina: avançar o marcador só quando há assinante faria o
    sistema reprocessar os mesmos eventos ignorados para sempre.
    """
    if not eventos:
        return [], 0

    fila: list[Entrega] = []
    maior = 0
    for evento in eventos:
        maior = max(maior, evento.sequence)
        tipo = ACAO_PARA_EVENTO.get(str(evento.action))
        if tipo is None:
            continue
        fila.extend(
            publicar(
                tipo,
                dados_do_evento(evento),
                destinos=destinos,
                agora=evento.occurred_at,
            )
        )
    return fila, maior
