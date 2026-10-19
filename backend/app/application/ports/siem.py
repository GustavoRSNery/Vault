"""Porta de exportação da trilha para um destino externo.

A âncora só vale se o destino for **inviolável pela aplicação**. Se o Vault
puder reescrever o que exportou, um atacante com o Vault na mão reescreve os
dois lados e a âncora não prova nada — vira teatro de segurança.

Por isso o contrato é só `append`: não existe update nem delete nesta porta,
e nenhuma implementação deve oferecê-los. Os destinos adequados em produção
são log somente-anexação do SIEM, bucket S3 com Object Lock, ou um WORM
equivalente. O `JsonlExporter` local serve para desenvolvimento e para
provar o fluxo; ele não é inviolável e diz isso de si mesmo.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SiemExporter(Protocol):
    """Destino somente-anexação para os eventos da trilha."""

    @property
    def nome(self) -> str:
        """Identificação do destino, gravada junto da âncora.

        Fica na âncora para que, anos depois, se saiba *onde* conferir o
        registro externo. Âncora sem destino conhecido é inverificável.
        """
        ...

    @property
    def inviolavel(self) -> bool:
        """O destino impede que a própria aplicação reescreva o que enviou?

        Falso para o exportador de arquivo local: qualquer um com acesso ao
        disco edita o arquivo. A interface usa isto para não anunciar uma
        garantia que o ambiente não tem.
        """
        ...

    def append(self, linhas: list[str]) -> int:
        """Acrescenta as linhas ao destino e devolve quantas foram aceitas.

        Deve ser idempotente do ponto de vista do chamador apenas no sentido
        de não corromper: reenviar um evento já exportado pode duplicar no
        destino, e é o chamador que controla o ponto de retomada.
        """
        ...
