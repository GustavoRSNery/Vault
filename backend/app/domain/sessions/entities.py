"""Sessões privilegiadas e sua gravação.

Responde o que a trilha de auditoria não responde. A trilha diz *quem revelou
qual segredo, quando e de onde*; a gravação diz **o que a pessoa fez com ele
depois**. Numa investigação, a diferença é entre saber que alguém pegou a
senha do banco às 3h e saber que comando ela rodou lá dentro.

## O que este domínio sabe, e o que ele ignora

Sabe: que uma sessão começa, acumula eventos ordenados no tempo, e termina.
Que ela pode ser encerrada à força. Que a gravação é imutável depois de
fechada.

Ignora, deliberadamente: SSH, RDP, terminal, vídeo, S3. Nada disso aparece
aqui. Um `EventoDeSessao` é um instante, um tipo e um texto — e é o adaptador
que decide se aquilo veio de um pty, de um proxy HTTP ou de um arquivo
asciicast.

Essa ignorância é o que permite trocar a captura sem tocar na regra. O custo
é que o domínio não valida o conteúdo: se o adaptador mandar lixo, lixo entra.
A validação do formato pertence a quem conhece o formato.

## Por que a gravação é imutável

Gravação de sessão é prova. Se a aplicação puder reescrevê-la, ela não prova
nada — mesma lógica da âncora da auditoria. Por isso `encerrar()` é terminal:
depois dele, nenhum evento entra, e o domínio recusa em vez de ignorar em
silêncio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from ..shared.errors import ConflictError, ValidationError
from ..shared.value_objects import PolicyPath, new_id, utcnow

# Teto de uma sessão sem atividade. Sessão esquecida aberta é acesso
# privilegiado disponível para quem sentar na cadeira.
OCIOSA_MINUTOS_MAXIMO = 60

# Teto absoluto. Mesmo ativa, uma sessão que dura um dia inteiro deixou de ser
# "uma tarefa" e virou acesso permanente por outro nome.
DURACAO_MINUTOS_MAXIMO = 720


class TipoDeSessao(StrEnum):
    """Como a pessoa alcançou o alvo. O domínio só rotula; não implementa."""

    SSH = "ssh"
    RDP = "rdp"
    BANCO = "banco_de_dados"
    WEB = "web"
    OUTRO = "outro"


class EstadoDaSessao(StrEnum):
    ATIVA = "ativa"
    ENCERRADA = "encerrada"
    EXPIRADA = "expirada"
    DERRUBADA = "derrubada"


class TipoDeEvento(StrEnum):
    """O que aconteceu num instante da sessão.

    `ENTRADA` é o que a pessoa digitou, `SAIDA` o que o sistema respondeu.
    Separá-los importa na revisão: o comando digitado é a intenção, e a saída
    é o que de fato aconteceu — nem sempre coincidem.
    """

    ENTRADA = "entrada"
    SAIDA = "saida"
    MARCO = "marco"       # anotação do sistema: "sessão aberta", "alvo trocado"
    ALERTA = "alerta"     # algo que merece atenção na revisão


@dataclass(frozen=True, slots=True)
class EventoDeSessao:
    """Um instante da sessão.

    `deslocamento_ms` é relativo ao início da sessão, não um horário absoluto.
    Isso é o que torna a reprodução possível sem depender de relógio: o player
    só precisa somar deslocamentos.
    """

    deslocamento_ms: int
    tipo: TipoDeEvento
    conteudo: str
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.deslocamento_ms < 0:
            raise ValidationError(
                "O deslocamento não pode ser negativo: um evento não acontece "
                "antes do início da própria sessão."
            )


@dataclass(slots=True)
class Sessao:
    """Uma sessão privilegiada, do início ao encerramento."""

    usuario_id: str
    usuario_label: str
    tipo: TipoDeSessao
    alvo: str
    motivo: str = ""
    segredo_path: str | None = None
    estado: EstadoDaSessao = EstadoDaSessao.ATIVA
    eventos: list[EventoDeSessao] = field(default_factory=list)
    ip_address: str | None = None
    iniciada_em: datetime = field(default_factory=utcnow)
    ultima_atividade_em: datetime = field(default_factory=utcnow)
    encerrada_em: datetime | None = None
    encerrada_por: str = ""
    motivo_encerramento: str = ""
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.alvo.strip():
            raise ValidationError(
                "A sessão precisa de um alvo. Sessão sem alvo é registro que "
                "não responde a pergunta nenhuma depois."
            )

    @property
    def path(self) -> PolicyPath:
        return PolicyPath(f"sessoes/{self.id}")

    @property
    def esta_ativa(self) -> bool:
        return self.estado is EstadoDaSessao.ATIVA

    @property
    def duracao_ms(self) -> int:
        fim = self.encerrada_em or utcnow()
        return max(int((fim - self.iniciada_em).total_seconds() * 1000), 0)

    def ociosa_ha_minutos(self, now: datetime | None = None) -> float:
        return (
            (now or utcnow()) - self.ultima_atividade_em
        ).total_seconds() / 60

    def deveria_expirar(self, now: datetime | None = None) -> bool:
        """Passou do teto de ociosidade ou do teto absoluto?

        Os dois tetos existem por razões diferentes: o de ociosidade pega a
        sessão esquecida aberta; o absoluto pega a sessão que alguém mantém
        viva de propósito para não precisar pedir acesso de novo.
        """
        if not self.esta_ativa:
            return False
        agora = now or utcnow()
        if self.ociosa_ha_minutos(agora) > OCIOSA_MINUTOS_MAXIMO:
            return True
        decorrido = (agora - self.iniciada_em).total_seconds() / 60
        return decorrido > DURACAO_MINUTOS_MAXIMO

    def registrar(self, evento: EventoDeSessao, now: datetime | None = None) -> None:
        """Acrescenta um evento à gravação.

        Recusa depois do encerramento em vez de ignorar em silêncio: gravação
        que aceita evento tardio não é mais prova de nada, e falhar alto é o
        que faz o adaptador quebrado aparecer.
        """
        if not self.esta_ativa:
            raise ConflictError(
                f"A sessão está {self.estado}: nenhum evento entra depois do "
                "encerramento. Gravação que muda não prova nada."
            )
        if self.eventos and evento.deslocamento_ms < self.eventos[-1].deslocamento_ms:
            raise ValidationError(
                "Evento fora de ordem: o deslocamento é menor que o do evento "
                "anterior, e a reprodução ficaria incoerente."
            )
        self.eventos.append(evento)
        self.ultima_atividade_em = now or utcnow()

    def encerrar(
        self,
        por: str = "",
        motivo: str = "",
        estado: EstadoDaSessao = EstadoDaSessao.ENCERRADA,
        now: datetime | None = None,
    ) -> None:
        """Fecha a sessão. Terminal: não há como reabrir."""
        if not self.esta_ativa:
            raise ConflictError("Esta sessão já foi encerrada.")
        if estado is EstadoDaSessao.ATIVA:
            raise ValidationError("Encerrar exige um estado final.")
        self.estado = estado
        self.encerrada_em = now or utcnow()
        self.encerrada_por = por
        self.motivo_encerramento = motivo

    def derrubar(self, por: str, motivo: str, now: datetime | None = None) -> None:
        """Encerramento à força, por um administrador.

        Separado de `encerrar` no estado final de propósito: numa revisão,
        "quem terminou normalmente" e "quem foi interrompido" são perguntas
        diferentes, e um estado só não as distinguiria.
        """
        if not motivo.strip():
            raise ValidationError(
                "Derrubar uma sessão exige justificativa: é interromper o "
                "trabalho de alguém, e a trilha precisa dizer por quê."
            )
        self.encerrar(
            por=por, motivo=motivo, estado=EstadoDaSessao.DERRUBADA, now=now
        )

    def expirar(self, now: datetime | None = None) -> None:
        self.encerrar(
            por="sistema",
            motivo="Tempo esgotado.",
            estado=EstadoDaSessao.EXPIRADA,
            now=now,
        )

    def linha_do_tempo(self) -> list[tuple[int, TipoDeEvento, str]]:
        """Os eventos prontos para o player: (ms, tipo, conteúdo)."""
        return [(e.deslocamento_ms, e.tipo, e.conteudo) for e in self.eventos]

    def buscar(self, termo: str) -> list[EventoDeSessao]:
        """Eventos cujo conteúdo contém o termo.

        É o que torna a gravação útil: ninguém assiste três horas de sessão
        para achar um comando. Sem busca, a gravação vira arquivo que se
        guarda e nunca se lê.
        """
        alvo = termo.strip().lower()
        if not alvo:
            return []
        return [e for e in self.eventos if alvo in e.conteudo.lower()]


def expirar_ociosas(
    sessoes: list[Sessao], now: datetime | None = None
) -> list[Sessao]:
    """Expira as sessões que passaram do prazo. Devolve as que mudaram.

    Função pura sobre a lista: quem chama decide quando rodar e o que fazer
    com o resultado. O domínio não agenda nada — agendamento é da
    infraestrutura, e um domínio que agenda não é testável sem esperar.
    """
    agora = now or utcnow()
    expiradas = []
    for sessao in sessoes:
        if sessao.deveria_expirar(agora):
            sessao.expirar(agora)
            expiradas.append(sessao)
    return expiradas
