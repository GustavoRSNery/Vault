"""Adaptadores das portas de gravação de sessão.

Dois funcionam hoje, sem nenhuma infraestrutura externa:

- `CapturaManual` — a pessoa registra o que fez. Não é gravação de verdade, e
  **diz isso de si mesmo** (`captura_automatica = False`), porque "gravação
  completa" e "o que a pessoa quis anotar" merecem confiança diferente numa
  investigação. Serve para registrar acesso a sistemas que não passam por
  proxy nenhum — que, numa empresa real, são a maioria no primeiro ano.

- `ArmazenamentoLocal` — guarda no sistema de arquivos. **Não é imutável**, e
  também diz isso: quem tem o disco reescreve a gravação.

Os de produção ficam esboçados abaixo, com a interface pronta e o corpo
levantando `NotImplementedError` — o esqueleto existe para que conectar seja
preencher um método, não redesenhar a camada. `ProxySsh` precisa de um
servidor SSH intermediário; `ArmazenamentoS3` precisa de bucket com Object
Lock e credencial.

Deixá-los como esqueleto que falha alto é deliberado: um stub que devolve
lista vazia em silêncio viraria "a gravação está ligada" numa auditoria, e
descobrir que não estava é o tipo de surpresa que não se quer ter depois de
um incidente.
"""

from __future__ import annotations

import json
from pathlib import Path

from ...application.ports.sessions import EventoCapturado
from ...domain.shared.errors import ValidationError


class CapturaManual:
    """A pessoa registra o que fez; o sistema não observa nada.

    Honesto sobre o que é: `captura_automatica` é falso, e a interface usa
    isso para não anunciar gravação onde há anotação.
    """

    def __init__(self) -> None:
        self._abertas: set[str] = set()

    @property
    def nome(self) -> str:
        return "manual"

    @property
    def captura_automatica(self) -> bool:
        return False

    def abrir(self, sessao_id: str, alvo: str) -> None:
        self._abertas.add(sessao_id)

    def coletar(self, sessao_id: str) -> list[EventoCapturado]:
        """Sempre vazio: quem registra é a pessoa, pela API."""
        return []

    def fechar(self, sessao_id: str) -> None:
        self._abertas.discard(sessao_id)


class ArmazenamentoLocal:
    """Gravações no sistema de arquivos. Não é imutável, e declara isso."""

    def __init__(self, pasta: Path | str) -> None:
        self._pasta = Path(pasta)

    @property
    def nome(self) -> str:
        return f"arquivo:{self._pasta.name}"

    @property
    def imutavel(self) -> bool:
        # Arquivo no mesmo host que a aplicação é editável pela aplicação.
        return False

    def guardar(self, sessao_id: str, conteudo: bytes) -> str:
        self._pasta.mkdir(parents=True, exist_ok=True)
        destino = self._pasta / f"{sessao_id}.jsonl"
        # "xb" e não "wb": recusa sobrescrever uma gravação existente. A
        # imutabilidade que o armazenamento não garante, ao menos a escrita
        # não viola por acidente.
        try:
            with destino.open("xb") as arquivo:
                arquivo.write(conteudo)
        except FileExistsError as erro:
            raise ValidationError(
                f"Já existe gravação para a sessão {sessao_id}. Gravação não "
                "se sobrescreve — é prova."
            ) from erro
        return str(destino.name)

    def ler(self, referencia: str) -> bytes:
        caminho = self._pasta / referencia
        if not caminho.exists():
            raise ValidationError(f"Gravação '{referencia}' não encontrada.")
        return caminho.read_bytes()


def serializar(eventos: list[tuple[int, str, str]]) -> bytes:
    """Serializa a linha do tempo como JSON Lines.

    Uma linha por evento, no formato `[ms, tipo, conteúdo]` — o mesmo do
    asciicast v2, de propósito: a gravação pode ser reproduzida por
    ferramentas que já existem, em vez de depender para sempre do player
    deste sistema.
    """
    return "\n".join(
        json.dumps([ms, tipo, conteudo], ensure_ascii=False)
        for ms, tipo, conteudo in eventos
    ).encode("utf-8")


def desserializar(conteudo: bytes) -> list[tuple[int, str, str]]:
    linhas = conteudo.decode("utf-8").strip().splitlines()
    saida: list[tuple[int, str, str]] = []
    for linha in linhas:
        if not linha.strip():
            continue
        ms, tipo, texto = json.loads(linha)
        saida.append((int(ms), str(tipo), str(texto)))
    return saida


# --------------------------------------------------------------- esqueletos


class ProxySsh:
    """Captura por proxy SSH. **Esqueleto — falta conectar.**

    O que falta para funcionar:

    1. um servidor SSH intermediário (asyncssh ou equivalente) que a pessoa
       acesse em vez de ir direto ao alvo;
    2. um pty por sessão, lendo os dois sentidos do canal;
    3. credencial do alvo, vinda do cofre, injetada sem passar pela pessoa —
       que é o ponto: a senha nunca chega a quem usa.

    Os métodos levantam `NotImplementedError` de propósito. Um stub que
    devolvesse lista vazia viraria "a gravação está ligada" numa auditoria, e
    descobrir que não estava é a pior hora para descobrir.
    """

    def __init__(self, host: str = "", porta: int = 2222) -> None:
        self._host = host
        self._porta = porta

    @property
    def nome(self) -> str:
        return f"proxy-ssh:{self._host or 'nao-configurado'}"

    @property
    def captura_automatica(self) -> bool:
        return True

    def abrir(self, sessao_id: str, alvo: str) -> None:
        raise NotImplementedError(
            "Proxy SSH ainda não está conectado. Falta o servidor "
            "intermediário; veja o docstring de ProxySsh."
        )

    def coletar(self, sessao_id: str) -> list[EventoCapturado]:
        raise NotImplementedError("Proxy SSH ainda não está conectado.")

    def fechar(self, sessao_id: str) -> None:
        raise NotImplementedError("Proxy SSH ainda não está conectado.")


class ArmazenamentoS3:
    """Gravações em bucket com Object Lock. **Esqueleto — falta conectar.**

    O que falta:

    1. bucket com Object Lock em modo COMPLIANCE e retenção definida — sem
       isso o armazenamento não é imutável e `imutavel` estaria mentindo;
    2. credencial com permissão de `PutObject`, e **sem** `DeleteObject`: a
       aplicação não deve conseguir apagar o que gravou;
    3. boto3 instalado (extra `kms` já o traz).

    `imutavel` devolve True porque, conectado, o destino é de fato imutável —
    e devolver False aqui faria a interface subestimar a garantia justamente
    no ambiente onde ela existe.
    """

    def __init__(self, bucket: str = "", prefixo: str = "sessoes/") -> None:
        self._bucket = bucket
        self._prefixo = prefixo

    @property
    def nome(self) -> str:
        return f"s3:{self._bucket or 'nao-configurado'}"

    @property
    def imutavel(self) -> bool:
        return True

    def guardar(self, sessao_id: str, conteudo: bytes) -> str:
        raise NotImplementedError(
            "Armazenamento S3 ainda não está conectado. Falta bucket com "
            "Object Lock; veja o docstring de ArmazenamentoS3."
        )

    def ler(self, referencia: str) -> bytes:
        raise NotImplementedError("Armazenamento S3 ainda não está conectado.")
