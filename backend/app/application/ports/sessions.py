"""Portas da gravação de sessão.

São **duas** e separadas de propósito, porque respondem a perguntas
diferentes e tendem a ter tecnologias diferentes:

- `CapturaDeSessao` — *como os eventos chegam*. Um proxy SSH com pty, um
  gateway RDP, um proxy HTTP, ou o adaptador manual (a pessoa registra o que
  fez). Quem implementa conhece protocolo.

- `ArmazenamentoDeGravacao` — *onde a gravação fica depois de fechada*. Banco
  local, bucket com Object Lock, storage WORM. Quem implementa conhece
  durabilidade e imutabilidade.

Juntá-las numa porta só forçaria quem quer trocar o armazenamento a mexer na
captura, e vice-versa — exatamente o acoplamento que ports and adapters existe
para evitar.

## O que o domínio não aceita

Nenhuma das duas portas devolve entidade de domínio montada. A captura entrega
eventos crus (instante, tipo, texto) e o caso de uso os transforma; o
armazenamento recebe e devolve bytes opacos. Se um adaptador pudesse construir
uma `Sessao`, ele passaria a carregar regra — e a regra voltaria a estar
espalhada, que é o problema que a arquitetura resolve.

## Imutabilidade

`ArmazenamentoDeGravacao` tem `guardar` e `ler`, **sem** atualizar nem apagar.
Gravação de sessão é prova; se a aplicação puder reescrevê-la, ela não prova
nada. É a mesma razão pela qual a porta do SIEM só tem `append`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class EventoCapturado:
    """Um evento como o adaptador o entrega: cru, sem interpretação.

    `deslocamento_ms` é relativo ao início da sessão. Pedi-lo ao adaptador —
    em vez de calcular aqui com o relógio — é o que permite importar uma
    gravação feita offline, onde "agora" não significa nada.
    """

    deslocamento_ms: int
    tipo: str
    conteudo: str


@runtime_checkable
class CapturaDeSessao(Protocol):
    """De onde os eventos de uma sessão vêm."""

    @property
    def nome(self) -> str:
        """Identificação do adaptador, gravada na sessão.

        Fica no registro para que, meses depois, se saiba *como* aquela
        gravação foi feita — uma sessão capturada por proxy SSH e outra
        registrada à mão merecem confiança diferente numa investigação.
        """
        ...

    @property
    def captura_automatica(self) -> bool:
        """O adaptador observa a sessão, ou depende de alguém registrar?

        Falso para o adaptador manual. A interface usa isto para não anunciar
        uma garantia que o ambiente não tem: "gravação completa" e "o que a
        pessoa quis anotar" são coisas distintas, e confundi-las numa auditoria
        seria pior que não ter gravação.
        """
        ...

    def abrir(self, sessao_id: str, alvo: str) -> None:
        """Prepara a captura. Levanta se o alvo for inalcançável."""
        ...

    def coletar(self, sessao_id: str) -> list[EventoCapturado]:
        """Eventos novos desde a última coleta. Lista vazia é normal."""
        ...

    def fechar(self, sessao_id: str) -> None:
        """Encerra a captura e libera o que for preciso."""
        ...


@runtime_checkable
class ArmazenamentoDeGravacao(Protocol):
    """Onde a gravação fechada fica guardada.

    Sem atualizar e sem apagar, de propósito: ver o cabeçalho do módulo.
    """

    @property
    def nome(self) -> str:
        ...

    @property
    def imutavel(self) -> bool:
        """O destino impede que a própria aplicação reescreva o que guardou?

        Falso para o banco local. A interface usa isto para dizer o tamanho
        real da garantia, em vez de anunciar prova onde há só registro.
        """
        ...

    def guardar(self, sessao_id: str, conteudo: bytes) -> str:
        """Grava e devolve a referência para recuperar depois."""
        ...

    def ler(self, referencia: str) -> bytes:
        """Recupera pelo que `guardar` devolveu."""
        ...
