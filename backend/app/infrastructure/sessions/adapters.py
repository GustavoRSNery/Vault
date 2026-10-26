"""Adaptadores das portas de gravação de sessão.

Dois funcionam hoje, sem nenhuma infraestrutura externa:

- `CapturaManual` — a pessoa registra o que fez. Não é gravação de verdade, e
  **diz isso de si mesmo** (`captura_automatica = False`), porque "gravação
  completa" e "o que a pessoa quis anotar" merecem confiança diferente numa
  investigação. Serve para registrar acesso a sistemas que não passam por
  proxy nenhum — que, numa empresa real, são a maioria no primeiro ano.

- `ArmazenamentoLocal` — guarda no sistema de arquivos. **Não é imutável**, e
  também diz isso: quem tem o disco reescreve a gravação.

E dois de produção, que precisam de infraestrutura externa:

- `ProxySsh` — a sessão passa pelo proxy e fica gravada, com a credencial do
  alvo saindo do cofre sem passar pela pessoa. O servidor que o alimenta está
  em `servidor.py`; este módulo guarda só a fila de eventos, para que a
  captura seja testável sem subir SSH.

- `ArmazenamentoS3` — bucket com Object Lock. Ele **confere** o Object Lock
  antes de afirmar `imutavel`, em vez de presumir: bucket sem lock aceita
  gravação igual e nada falha, então presumir produziria anos de "isto é
  prova" para algo apagável.

Nenhum dos dois devolve lista vazia ou silêncio quando falta configuração:
eles levantam. Um stub silencioso viraria "a gravação está ligada" numa
auditoria, e descobrir que não estava é o tipo de surpresa que não se quer
ter depois de um incidente.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


# ------------------------------------------------- adaptadores de producao


class ProxySsh:
    """Captura por proxy SSH: a sessão passa por aqui e fica gravada.

    A pessoa abre SSH **neste** processo, não no alvo. O proxy busca a
    credencial do alvo no cofre, conecta por fora, e liga os dois canais
    copiando tudo que passa. Dois ganhos que só existem juntos:

    - **A senha do alvo nunca chega a quem usa.** Quem acessa autentica no
      proxy com a identidade dele; a credencial do servidor sai do cofre
      direto para a conexão. Revogar o acesso é revogar no cofre, não trocar
      a senha em vinte servidores e avisar vinte pessoas.
    - **A gravação é do que aconteceu**, não do que alguém anotou. Daí
      `captura_automatica = True` — ao contrário de `CapturaManual`.

    ## Por que uma fila por sessão e não leitura sob demanda

    `coletar` é chamado pelo caso de uso quando lhe convém, e a sessão SSH
    produz bytes quando a pessoa digita: as duas velocidades não têm relação.
    Entre uma coleta e outra os eventos ficam numa fila por sessão, e
    `coletar` a drena. Ler do socket dentro de `coletar` perderia tudo que
    chegasse fora da janela da chamada.

    ## O que fica de fora de propósito

    Não há `atualizar` nem `apagar` evento: gravação é prova. E o proxy não
    monta `Sessao` nenhuma — entrega `EventoCapturado` cru, porque regra de
    domínio em adaptador é a regra espalhada que a arquitetura evita.

    ## Limite conhecido

    Grava o canal de terminal (pty). Túnel, `scp` e encaminhamento de porta
    passam por canais que este adaptador **não** grava: ele os recusa, em vez
    de deixá-los passar sem gravação — sessão parcialmente gravada numa
    auditoria é pior que sessão recusada, porque parece completa.
    """

    # Tipos de evento, no vocabulário do asciicast v2 que `serializar` usa.
    SAIDA = "o"  # output: o que o alvo devolveu
    ENTRADA = "i"  # input: o que a pessoa digitou

    def __init__(
        self,
        host: str = "",
        porta: int = 2222,
        *,
        buscar_credencial: Callable[[str], tuple[str, str]] | None = None,
    ) -> None:
        """
        `buscar_credencial` recebe o alvo e devolve `(usuario, senha)` do
        cofre. É injetado em vez de o proxy conhecer o repositório: assim o
        adaptador não ganha acesso ao banco, e o teste não precisa de cofre.

        A chave de host **não** vem aqui: ela é do `ServidorDeSessoes`, que é
        quem fala SSH. Aceitá-la e guardá-la sem usar faria a configuração
        parecer aplicada quando não está — o pior tipo de parâmetro.
        """
        self._host = host
        self._porta = porta
        self._buscar_credencial = buscar_credencial
        # Uma fila por sessão, drenada por `coletar`.
        self._filas: dict[str, list[EventoCapturado]] = {}
        self._inicios: dict[str, float] = {}
        self._alvos: dict[str, str] = {}

    @property
    def nome(self) -> str:
        return f"proxy-ssh:{self._host or 'nao-configurado'}"

    @property
    def captura_automatica(self) -> bool:
        return True

    def abrir(self, sessao_id: str, alvo: str) -> None:
        """Registra a sessão e marca o instante zero.

        O `deslocamento_ms` de cada evento é relativo a este instante, e é
        por isso que ele é guardado aqui em vez de calculado na coleta: a
        linha do tempo tem de começar quando a sessão começou, não quando
        alguém resolveu perguntar.
        """
        if not alvo.strip():
            raise ValidationError(
                "A sessão precisa de um alvo. Sem ele o proxy não tem onde "
                "conectar."
            )
        self._filas[sessao_id] = []
        self._inicios[sessao_id] = time.monotonic()
        self._alvos[sessao_id] = alvo

    def registrar(self, sessao_id: str, tipo: str, conteudo: str) -> None:
        """Enfileira um evento capturado do canal.

        Chamado pelo servidor SSH (ver `servidor.py`) a cada bloco de bytes
        nos dois sentidos. Sessão desconhecida é **erro**, não evento
        descartado em silêncio: significaria gravação sem sessão aberta, e
        engolir isso produziria buraco na linha do tempo sem aviso.
        """
        if sessao_id not in self._filas:
            raise ValidationError(
                f"Sessão {sessao_id} não está aberta no proxy. Evento sem "
                "sessão seria lacuna silenciosa na gravação."
            )
        decorrido = time.monotonic() - self._inicios[sessao_id]
        self._filas[sessao_id].append(
            EventoCapturado(
                deslocamento_ms=int(decorrido * 1000),
                tipo=tipo,
                conteudo=conteudo,
            )
        )

    def credencial_do_alvo(self, alvo: str) -> tuple[str, str]:
        """Credencial do alvo, vinda do cofre.

        Sem buscador injetado o proxy **recusa** em vez de pedir a senha à
        pessoa: cair para "digite a senha do servidor" derrotaria o propósito
        do cofre justamente no caminho que ele existe para proteger.
        """
        if self._buscar_credencial is None:
            raise ValidationError(
                "O proxy SSH não tem de onde buscar a credencial do alvo. "
                "Sem o cofre, a senha teria de passar pela pessoa — que é "
                "exatamente o que este caminho evita."
            )
        return self._buscar_credencial(alvo)

    def coletar(self, sessao_id: str) -> list[EventoCapturado]:
        """Drena a fila: eventos novos desde a última coleta."""
        fila = self._filas.get(sessao_id)
        if not fila:
            return []
        self._filas[sessao_id] = []
        return fila

    def fechar(self, sessao_id: str) -> None:
        """Encerra e libera a sessão.

        Não levanta para sessão desconhecida: fechar o que já está fechado é
        a situação normal de um encerramento repetido, e falhar aqui
        impediria a limpeza de seguir adiante.
        """
        self._filas.pop(sessao_id, None)
        self._inicios.pop(sessao_id, None)
        self._alvos.pop(sessao_id, None)

    def pendentes(self, sessao_id: str) -> int:
        """Quantos eventos aguardam coleta. Para diagnóstico."""
        return len(self._filas.get(sessao_id, []))


class ArmazenamentoS3:
    """Gravações em bucket S3 com Object Lock.

    **A imutabilidade não vem deste código — vem do bucket.** O adaptador
    nunca chama `delete`, mas isso é disciplina, não garantia: o que impede
    de verdade é o Object Lock em modo COMPLIANCE, onde nem o root da conta
    remove a versão antes do prazo.

    O que o bucket precisa ter, do lado de fora deste código:

    1. **Object Lock em COMPLIANCE** com retenção definida. Em GOVERNANCE,
       quem tiver `BypassGovernanceRetention` apaga — e aí a gravação deixa
       de ser prova sem ninguém perceber.
    2. **Credencial sem `DeleteObject`.** Defesa em profundidade: se um dia
       alguém acrescentar um `delete` aqui, a permissão recusa.
    3. Versionamento ligado (o Object Lock exige).

    A cifragem fica fora daqui: o que chega em `guardar` já é bytes cifrados,
    e o S3 guarda blob opaco, como a porta manda.
    """

    def __init__(
        self,
        bucket: str = "",
        prefixo: str = "sessoes/",
        *,
        client: Any | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        if not bucket.strip():
            raise ValidationError(
                "O bucket das gravações é obrigatório. Sem ele o adaptador "
                "não tem onde guardar, e descobrir isso no fim de uma sessão "
                "perderia a gravação."
            )
        self._bucket = bucket
        # Prefixo sempre terminando em barra: sem ela, "sessoes" + "abc.jsonl"
        # vira "sessoesabc.jsonl" e as gravações se espalham na raiz.
        self._prefixo = prefixo if not prefixo or prefixo.endswith("/") else prefixo + "/"
        self._region = region
        self._endpoint_url = endpoint_url
        # Injetável para teste; em produção é criado na primeira chamada.
        self._client = client
        self._imutavel_conferido: bool | None = None

    @property
    def nome(self) -> str:
        return f"s3:{self._bucket}"

    @property
    def imutavel(self) -> bool:
        """Só afirma imutabilidade depois de **conferir** no bucket.

        O esqueleto devolvia `True` fixo, com o argumento de que "conectado, o
        destino é de fato imutável". O argumento tem um furo: um bucket sem
        Object Lock aceita `PutObject` igual e nada falha — a aplicação
        anunciaria prova durante anos, e a primeira auditoria descobriria que
        dava para apagar.

        Confere uma vez e guarda: é configuração de bucket, não muda a cada
        gravação, e uma chamada à AWS por listagem de tela seria desperdício.
        """
        if self._imutavel_conferido is None:
            self._imutavel_conferido = self._conferir_object_lock()
        return self._imutavel_conferido

    def _s3(self) -> Any:
        if self._client is None:
            import boto3  # import tardio: só quem usa S3 precisa da dependência

            self._client = boto3.client(
                "s3", region_name=self._region, endpoint_url=self._endpoint_url
            )
        return self._client

    def _conferir_object_lock(self) -> bool:
        """O bucket tem Object Lock em COMPLIANCE?

        GOVERNANCE devolve `False` de propósito: é contornável por quem tiver
        a permissão de bypass, e "imutável, menos para alguns" não é a
        garantia que a palavra promete numa auditoria.
        """
        try:
            resposta = self._s3().get_object_lock_configuration(Bucket=self._bucket)
        except Exception:  # noqa: BLE001 — sem lock, boto3 levanta ClientError
            return False
        config = resposta.get("ObjectLockConfiguration", {})
        if config.get("ObjectLockEnabled") != "Enabled":
            return False
        modo = config.get("Rule", {}).get("DefaultRetention", {}).get("Mode")
        return bool(modo == "COMPLIANCE")

    def _chave(self, sessao_id: str) -> str:
        return f"{self._prefixo}{sessao_id}.jsonl"

    def guardar(self, sessao_id: str, conteudo: bytes) -> str:
        """Grava e devolve a chave no bucket.

        `IfNoneMatch="*"` recusa sobrescrever gravação existente, como o
        `"xb"` do armazenamento local. O Object Lock já preservaria a versão
        anterior, mas sem isto a antiga sairia da listagem — e "sumiu da tela"
        é o bastante para alguém concluir que não existe.
        """
        chave = self._chave(sessao_id)
        try:
            self._s3().put_object(
                Bucket=self._bucket,
                Key=chave,
                Body=conteudo,
                IfNoneMatch="*",
                ContentType="application/x-ndjson",
            )
        except Exception as erro:  # noqa: BLE001 — ClientError de boto3
            resposta = getattr(erro, "response", None) or {}
            codigo = resposta.get("Error", {}).get("Code", "")
            if codigo in ("PreconditionFailed", "ConditionalRequestConflict"):
                raise ValidationError(
                    f"Já existe gravação para a sessão {sessao_id}. Gravação "
                    "não se sobrescreve — é prova."
                ) from erro
            raise ValidationError(
                f"A gravação da sessão {sessao_id} não pôde ser guardada no "
                f"S3: {erro}"
            ) from erro
        return chave

    def ler(self, referencia: str) -> bytes:
        try:
            resposta = self._s3().get_object(Bucket=self._bucket, Key=referencia)
            return bytes(resposta["Body"].read())
        except Exception as erro:  # noqa: BLE001 — ClientError de boto3
            raise ValidationError(
                f"Gravação '{referencia}' não encontrada no S3: {erro}"
            ) from erro

    def verificar_bucket(self) -> list[str]:
        """Problemas que fariam a imutabilidade ser só promessa.

        Serve ao boot e ao diagnóstico: melhor descobrir que o bucket não tem
        Object Lock ao subir do que ao procurar a gravação de um incidente.
        Lista vazia quando está tudo certo.
        """
        problemas: list[str] = []
        s3 = self._s3()

        try:
            s3.head_bucket(Bucket=self._bucket)
        except Exception as erro:  # noqa: BLE001
            return [f"bucket '{self._bucket}' inacessível: {erro}"]

        if not self._conferir_object_lock():
            problemas.append(
                f"bucket '{self._bucket}' não tem Object Lock em COMPLIANCE: "
                "as gravações podem ser apagadas e não servem como prova"
            )

        try:
            versionamento = s3.get_bucket_versioning(Bucket=self._bucket)
            if versionamento.get("Status") != "Enabled":
                problemas.append(
                    "versionamento desligado: sem ele o Object Lock não "
                    "protege nada"
                )
        except Exception as erro:  # noqa: BLE001
            problemas.append(f"versionamento não pôde ser verificado: {erro}")

        return problemas
