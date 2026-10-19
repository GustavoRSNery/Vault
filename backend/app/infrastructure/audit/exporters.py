"""Implementações da porta de exportação da trilha.

`JsonlExporter` grava num arquivo local, uma linha JSON por evento. Serve
para desenvolvimento e para exercitar o fluxo inteiro sem depender de um SIEM
no ar — mas **não é inviolável**, e declara isso em `inviolavel`. Quem tem
acesso ao disco edita o arquivo, e então a âncora não prova mais nada.

Em produção, a mesma porta recebe um destino que a aplicação não consegue
reescrever: HTTP Event Collector do Splunk, log somente-anexação do
CloudWatch, bucket S3 com Object Lock. A troca é de uma linha na injeção de
dependências, porque o caso de uso só conhece a porta.
"""

from __future__ import annotations

from pathlib import Path


class JsonlExporter:
    """Arquivo local em JSON Lines, aberto em modo append.

    O modo "a" importa: "w" truncaria o arquivo a cada exportação e apagaria
    justamente o histórico que se quer preservar fora do banco.
    """

    def __init__(self, caminho: Path | str) -> None:
        self._caminho = Path(caminho)

    @property
    def nome(self) -> str:
        return f"arquivo:{self._caminho.name}"

    @property
    def inviolavel(self) -> bool:
        # Um arquivo no mesmo host que a aplicação é editável pela aplicação.
        # Dizer o contrário seria anunciar uma garantia que não existe.
        return False

    @property
    def caminho(self) -> Path:
        return self._caminho

    def append(self, linhas: list[str]) -> int:
        if not linhas:
            return 0
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._caminho.open("a", encoding="utf-8") as arquivo:
            for linha in linhas:
                arquivo.write(linha + "\n")
        return len(linhas)
