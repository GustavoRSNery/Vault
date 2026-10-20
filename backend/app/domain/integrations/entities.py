"""Integrações: o Vault avisando sistemas de fora.

**Por que Standard Webhooks.** O usuário pediu "o padrão mais robusto de
mercado". Standard Webhooks (standardwebhooks.com) é a especificação aberta
que Svix, Resend, Clerk e outros adotaram; ela resolve exatamente os quatro
problemas que derrubam uma integração caseira:

1. **Autenticidade** — assinatura HMAC-SHA256 sobre `id.timestamp.corpo`.
   Sem isso, qualquer um que descubra a URL do destino injeta eventos falsos.
2. **Repetição** — o `timestamp` entra na assinatura e o destino recusa o que
   está fora da janela. Sem isso, um evento legítimo capturado hoje é
   reenviado amanhã.
3. **Entrega** — reentrega com backoff exponencial e jitter, por dias. A rede
   falha; um webhook que desiste na primeira tentativa perde o evento.
4. **Duplicata** — o `webhook-id` não muda entre tentativas, então o destino
   usa como chave de idempotência. Entrega é *ao menos uma vez*; prometer
   *exatamente uma* é prometer o que a rede não entrega.

**O que fica em aberto, de propósito.** O envio em si é um adaptador: a porta
`EntregadorDeWebhook` descreve o contrato e a implementação HTTP entra quando
houver destino real. O domínio aqui não sabe fazer requisição nenhuma — é o
que permite testar a assinatura e o agendamento sem rede.

Referência: https://github.com/standard-webhooks/standard-webhooks
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from ..shared.errors import ValidationError
from ..shared.value_objects import PolicyPath, Slug, new_id, utcnow

# Tolerância de relógio na verificação. A especificação não fixa um número —
# diz "dentro de alguma tolerância aceitável" — e 5 minutos é o valor que as
# implementações de referência usam. Curto o bastante para que um evento
# capturado não sirva amanhã; largo o bastante para relógios desalinhados.
TOLERANCIA_SEGUNDOS = 300

# Segredo simétrico: a especificação pede de 24 a 64 bytes aleatórios.
SEGREDO_BYTES = 32
PREFIXO_SEGREDO = "whsec_"

# Cronograma de reentrega, em segundos. Sai de imediato e abre até 24 horas,
# cobrindo ~75 horas no total: um destino que ficou fora do ar numa
# sexta-feira ainda recebe o evento na segunda.
ESPERAS = (0, 5, 300, 1_800, 7_200, 18_000, 36_000, 86_400, 86_400)

# Falhas seguidas antes de desligar o destino sozinho. Endpoint quebrado que
# ninguém conserta vira fila infinita de tentativa; desligar e avisar é mais
# honesto do que tentar para sempre em silêncio.
FALHAS_PARA_DESLIGAR = 15


class TipoDeEvento(StrEnum):
    """Eventos que o Vault publica.

    Nomes separados por ponto, como a especificação recomenda: deixa o
    destino assinar `segredo.*` sem conhecer cada evento futuro.
    """

    SEGREDO_REVELADO = "segredo.revelado"
    SEGREDO_CRIADO = "segredo.criado"
    SEGREDO_ALTERADO = "segredo.alterado"
    SEGREDO_EXCLUIDO = "segredo.excluido"
    CREDENCIAL_RETIRADA = "credencial.retirada"
    CREDENCIAL_DEVOLVIDA = "credencial.devolvida"
    CREDENCIAL_ATRASADA = "credencial.atrasada"
    CERTIFICADO_VENCENDO = "certificado.vencendo"
    CERTIFICADO_VENCIDO = "certificado.vencido"
    CHAVE_API_VENCENDO = "chave_api.vencendo"
    ACESSO_NEGADO = "acesso.negado"
    ACESSO_REMOTO_INICIADO = "acesso.remoto_iniciado"
    SESSAO_ABERTA = "sessao.aberta"
    SESSAO_ENCERRADA = "sessao.encerrada"
    COFRE_SELADO = "cofre.selado"
    COFRE_DESSELADO = "cofre.desselado"
    APROVACAO_SOLICITADA = "aprovacao.solicitada"
    APROVACAO_CONCEDIDA = "aprovacao.concedida"


class EstadoDoDestino(StrEnum):
    ATIVO = "ativo"
    PAUSADO = "pausado"
    # Desligado pelo próprio sistema depois de falhar demais.
    DESLIGADO = "desligado"


class EstadoDaEntrega(StrEnum):
    PENDENTE = "pendente"
    ENTREGUE = "entregue"
    FALHOU = "falhou"
    # Esgotou as tentativas; não será reenviado.
    DESISTIU = "desistiu"


def gerar_segredo() -> str:
    """Segredo de assinatura no formato da especificação.

    `whsec_` + base64. O prefixo existe para que o segredo seja reconhecível
    num log ou num repositório — varredura de credencial vazada procura
    justamente por esses prefixos.
    """
    return PREFIXO_SEGREDO + base64.b64encode(secrets.token_bytes(SEGREDO_BYTES)).decode()


def _chave(segredo: str) -> bytes:
    """Os bytes que assinam, decodificados do base64 depois do prefixo."""
    bruto = segredo[len(PREFIXO_SEGREDO):] if segredo.startswith(PREFIXO_SEGREDO) else segredo
    try:
        return base64.b64decode(bruto)
    except Exception as erro:  # noqa: BLE001
        raise ValidationError("Segredo de assinatura inválido.") from erro


def assinar(segredo: str, *, id_evento: str, timestamp: int, corpo: str) -> str:
    """Assinatura `v1,<base64>` sobre `id.timestamp.corpo`.

    O corpo entra **exatamente como será enviado**: reserializar o JSON
    depois de assinar muda bytes (ordem de chaves, espaços) e quebra a
    verificação do outro lado — é o erro mais comum nesta especificação.
    """
    if "." in id_evento:
        raise ValidationError(
            "O id do evento não pode conter ponto: ele é o separador da "
            "mensagem assinada, e um ponto a mais move a fronteira entre os "
            "campos."
        )
    conteudo = f"{id_evento}.{timestamp}.{corpo}".encode()
    digest = hmac.new(_chave(segredo), conteudo, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def conferir(
    segredo: str,
    *,
    id_evento: str,
    timestamp: int,
    corpo: str,
    assinatura_recebida: str,
    agora: datetime | None = None,
    tolerancia: int = TOLERANCIA_SEGUNDOS,
) -> bool:
    """Verifica assinatura e janela de tempo.

    Implementado aqui porque o Vault também **recebe** webhooks em alguns
    fluxos, e porque ter os dois lados no mesmo lugar deixa o teste provar
    que assinar e conferir combinam.
    """
    momento = agora or utcnow()
    if abs(int(momento.timestamp()) - timestamp) > tolerancia:
        return False

    esperada = assinar(segredo, id_evento=id_evento, timestamp=timestamp, corpo=corpo)
    # O cabeçalho pode trazer várias assinaturas separadas por espaço durante
    # a rotação do segredo: qualquer uma que confira vale.
    for candidata in assinatura_recebida.split(" "):
        # Comparação em tempo constante: comparar com `==` vaza, pelo tempo
        # de resposta, quantos bytes iniciais o atacante acertou.
        if hmac.compare_digest(candidata.strip(), esperada):
            return True
    return False


@dataclass(slots=True)
class Destino:
    """Um endpoint que recebe os eventos."""

    name: Slug
    display_name: str
    url: str
    # Quais eventos interessam. Vazio = todos; `segredo.*` casa a família.
    eventos: list[str] = field(default_factory=list)
    segredo: str = field(default_factory=gerar_segredo)
    estado: EstadoDoDestino = EstadoDoDestino.ATIVO
    descricao: str = ""
    # Falhas seguidas. Zera a cada entrega bem-sucedida.
    falhas_seguidas: int = 0
    # Até onde este destino já leu a trilha. Começa no ponto em que foi
    # cadastrado, e não em zero: um destino novo não deve receber de uma vez
    # todo o histórico do cofre — seria uma enxurrada de eventos antigos que
    # ninguém pediu, e os mais sensíveis entre eles.
    ultima_sequencia: int = 0
    ultima_entrega_em: datetime | None = None
    ultimo_erro: str = ""
    criado_por: str = ""
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("Informe um nome para o destino.")
        if not self.url.startswith("https://"):
            # HTTP simples entregaria o conteúdo do evento em claro na rede.
            # A assinatura prova a origem, não esconde o que foi enviado.
            raise ValidationError(
                "A URL do destino precisa ser https. Em http o conteúdo do "
                "evento trafega em claro, e nele vão caminhos de segredos."
            )
        self.eventos = sorted({e.strip() for e in self.eventos if e.strip()})

    @property
    def path(self) -> PolicyPath:
        return PolicyPath(f"integracoes/{self.name}")

    @property
    def ativo(self) -> bool:
        return self.estado is EstadoDoDestino.ATIVO

    def interessa(self, tipo: str) -> bool:
        """Se este destino quer este evento.

        Lista vazia quer dizer "tudo": é o padrão menos surpreendente para
        quem acabou de cadastrar e espera ver movimento.
        """
        if not self.eventos:
            return True
        for padrao in self.eventos:
            if padrao == tipo:
                return True
            if padrao.endswith(".*") and tipo.startswith(padrao[:-1]):
                return True
        return False

    def registrar_sucesso(self, agora: datetime | None = None) -> None:
        self.falhas_seguidas = 0
        self.ultimo_erro = ""
        self.ultima_entrega_em = agora or utcnow()

    def registrar_falha(self, erro: str, agora: datetime | None = None) -> None:
        self.falhas_seguidas += 1
        self.ultimo_erro = erro[:500]
        self.ultima_entrega_em = agora or utcnow()
        if self.falhas_seguidas >= FALHAS_PARA_DESLIGAR:
            self.estado = EstadoDoDestino.DESLIGADO

    def desligar(self, motivo: str) -> None:
        """Desliga na hora, sem esperar o limite.

        É o que fazer com `410 Gone`: o destino disse que não existe mais, e
        continuar tentando é gastar fila com o que já respondeu que não.
        """
        self.estado = EstadoDoDestino.DESLIGADO
        self.ultimo_erro = motivo[:500]

    def reativar(self) -> None:
        self.estado = EstadoDoDestino.ATIVO
        self.falhas_seguidas = 0
        self.ultimo_erro = ""

    def rotacionar_segredo(self) -> str:
        """Gera um segredo novo e devolve.

        Devolve em vez de só guardar porque é a única vez que o valor é
        mostrado: quem configura o destino precisa copiá-lo agora.
        """
        self.segredo = gerar_segredo()
        return self.segredo


@dataclass(slots=True)
class Entrega:
    """Uma tentativa de entregar um evento a um destino.

    Guarda o corpo **exatamente como foi assinado**. Reconstruí-lo na hora de
    reenviar produziria bytes diferentes e uma assinatura que não confere —
    o erro clássico desta especificação.
    """

    destino_id: str
    tipo: str
    corpo: str
    # O `webhook-id`: o mesmo em todas as tentativas, para o destino usar
    # como chave de idempotência. Entrega é "ao menos uma vez".
    id_evento: str = field(default_factory=new_id)
    estado: EstadoDaEntrega = EstadoDaEntrega.PENDENTE
    tentativas: int = 0
    proxima_em: datetime = field(default_factory=utcnow)
    ultimo_status: int | None = None
    ultimo_erro: str = ""
    entregue_em: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if "." in self.id_evento:
            raise ValidationError(
                "O id do evento não pode conter ponto: é o separador da "
                "mensagem assinada."
            )

    @property
    def esgotou(self) -> bool:
        return self.tentativas >= len(ESPERAS)

    def marcar_entregue(self, status: int, agora: datetime | None = None) -> None:
        self.estado = EstadoDaEntrega.ENTREGUE
        self.ultimo_status = status
        self.ultimo_erro = ""
        self.entregue_em = agora or utcnow()
        self.tentativas += 1

    def marcar_falha(
        self,
        erro: str,
        *,
        status: int | None = None,
        agora: datetime | None = None,
        retry_after: int | None = None,
    ) -> None:
        """Registra a falha e agenda a próxima tentativa.

        O atraso cresce com jitter: sem ele, mil entregas que falharam juntas
        voltam juntas e derrubam o destino de novo no momento em que ele
        tenta subir.
        """
        momento = agora or utcnow()
        self.tentativas += 1
        self.ultimo_status = status
        self.ultimo_erro = erro[:500]

        if self.esgotou:
            self.estado = EstadoDaEntrega.DESISTIU
            return

        self.estado = EstadoDaEntrega.FALHOU
        if retry_after is not None and retry_after > 0:
            # O destino pediu um tempo: respeitar é mais educado — e mais
            # eficaz — do que insistir no nosso próprio cronograma.
            espera = retry_after
        else:
            base = ESPERAS[self.tentativas]
            # Até 20% a mais, nunca a menos: adiantar não ajuda ninguém.
            espera = base + int(base * 0.2 * secrets.randbelow(100) / 100)
        self.proxima_em = momento + timedelta(seconds=espera)

    def pronta(self, agora: datetime | None = None) -> bool:
        if self.estado in (EstadoDaEntrega.ENTREGUE, EstadoDaEntrega.DESISTIU):
            return False
        return (agora or utcnow()) >= self.proxima_em


def montar_corpo(tipo: str, dados: dict, *, agora: datetime | None = None) -> str:
    """Monta o corpo no formato recomendado: `type`, `timestamp`, `data`.

    Devolve **texto**, não dicionário, porque o que é assinado tem de ser o
    que é enviado, byte a byte. Separadores compactos e sem reordenar chaves:
    qualquer reserialização depois daqui invalida a assinatura.

    O `timestamp` é quando o evento **aconteceu**, não quando foi entregue —
    numa reentrega dois dias depois, a diferença é o que permite ao destino
    ordenar corretamente.
    """
    import json

    return json.dumps(
        {
            "type": tipo,
            "timestamp": (agora or utcnow()).isoformat(),
            "data": dados,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
