"""Servidor SSH intermediário que grava as sessões.

A pessoa abre SSH **neste** servidor, não no alvo. Ele autentica quem chegou,
busca a credencial do alvo no cofre, conecta por fora, e liga os dois canais
copiando tudo que passa para o `ProxySsh`.

## Por que um servidor e não um wrapper de cliente

Um script que chamasse `ssh` e gravasse a saída dependeria de a pessoa usar o
script. Quem abrisse o `ssh` direto ficaria sem gravação, e a trilha teria um
buraco exatamente no caso de quem não quer ser gravado. Como servidor, o
caminho até o alvo passa por aqui porque o alvo só aceita conexão de origem
daqui — a gravação deixa de depender de boa vontade.

## O que o servidor recusa, e por quê

Recusa o que não sabe gravar: encaminhamento de porta, SFTP/SCP, túnel, e
execução de comando sem pty. Deixá-los passar daria sessão gravada pela
metade — e numa auditoria uma gravação parcial é pior que nenhuma, porque
parece completa. Recusar é visível; gravar pela metade, não.

## Chave do host

Em produção a chave vem de arquivo e é estável. Se ela mudar a cada boot,
todo cliente vê o aviso de host key changed — que é o aviso de ataque
man-in-the-middle — e as pessoas aprendem a ignorá-lo, que é o pior
resultado possível para a segurança do acesso.

## Estado

`asyncssh` é importado dentro dos métodos: quem roda com `CapturaManual` não
precisa da dependência instalada (extra `ssh`).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...domain.shared.errors import ValidationError
from .adapters import ProxySsh

logger = logging.getLogger(__name__)

# Blocos maiores que isto viram vários eventos. Mantém a linha do tempo com
# granularidade útil para a reprodução: um despejo de 2 MB como evento único
# apareceria como um salto instantâneo no player.
BLOCO_MAXIMO = 8192


PORTA_SSH_PADRAO = 22


def separar_host_e_porta(alvo: str) -> tuple[str, int]:
    """Separa `host:porta`, devolvendo a porta 22 quando não houver.

    **Por que não basta `alvo.split(":")`.** Passar `"servidor:2222"` inteiro
    ao `asyncssh.connect` não dá erro: ele trata a string como nome de host,
    tenta a porta 22, e a sessão falha com "não foi possível conectar" —
    mensagem que manda investigar rede e firewall quando o problema era a
    porta ter sido ignorada. Falhar assim custa caro porque mente sobre a
    causa.

    IPv6 vem entre colchetes (`[::1]:2222`), que é como a URL o escreve: sem
    eles, `::1:2222` não tem como ser separado de um endereço que termina em
    `:2222`.
    """
    texto = alvo.strip()
    if texto.startswith("["):
        host, _, resto = texto.partition("]")
        host = host[1:]
        if resto.startswith(":"):
            return host, _porta_valida(resto[1:], alvo)
        return host, PORTA_SSH_PADRAO
    # Dois pontos ou mais sem colchete: IPv6 sem porta.
    if texto.count(":") > 1:
        return texto, PORTA_SSH_PADRAO
    host, sep, porta = texto.partition(":")
    if not sep:
        return host, PORTA_SSH_PADRAO
    return host, _porta_valida(porta, alvo)


def _porta_valida(texto: str, alvo: str) -> int:
    try:
        porta = int(texto)
    except ValueError as erro:
        raise ValidationError(
            f"O alvo {alvo!r} tem porta inválida: {texto!r} não é um número."
        ) from erro
    if not 1 <= porta <= 65535:
        raise ValidationError(
            f"O alvo {alvo!r} tem porta fora da faixa: {porta}."
        )
    return porta


@dataclass(frozen=True, slots=True)
class Credenciais:
    """O que a autenticação estabeleceu sobre a conexão.

    Guardado por conexão num registro do servidor, e não lido de dentro do
    asyncssh: depender da estrutura interna da biblioteca funcionaria até a
    primeira atualização dela — e o que quebraria é a gravação.
    """

    usuario_id: str
    alvo: str
    usuario_no_alvo: str


class ServidorDeSessoes:
    """Aceita conexões SSH, conecta ao alvo e grava os dois sentidos.

    O alvo vem do nome de usuário com que a pessoa se conecta, no formato
    `usuario@alvo` — `ssh ana.souza@servidor-01@proxy:2222`. É feio, e é o
    padrão dos bastion hosts justamente porque funciona sem cliente especial:
    qualquer `ssh` chega aqui.
    """

    def __init__(
        self,
        proxy: ProxySsh,
        *,
        autenticar: Callable[[str, str], Awaitable[str | None]],
        abrir_sessao: Callable[[str, str], Awaitable[str]],
        fechar_sessao: Callable[[str], Awaitable[None]],
        porta: int = 2222,
        chave_do_host: Path | str | None = None,
    ) -> None:
        """
        `autenticar` recebe `(usuario, senha)` e devolve o id do usuário, ou
        `None` se recusar. `abrir_sessao` recebe `(usuario_id, alvo)` e
        devolve o id da sessão — é o caso de uso que grava a sessão no banco
        e aplica o RBAC. Injetados para que o servidor não conheça banco nem
        política: ele sabe de SSH, e nada mais.
        """
        self._proxy = proxy
        self._autenticar = autenticar
        self._abrir_sessao = abrir_sessao
        self._fechar_sessao = fechar_sessao
        self._porta = porta
        self._chave_do_host = Path(chave_do_host) if chave_do_host else None
        self._servidor: Any | None = None
        # Identidade por conexão, posta pela autenticação e lida pelo handler
        # do processo. Limpa em `connection_lost`.
        self._autenticados: dict[int, Credenciais] = {}

    async def iniciar(self) -> None:
        """Sobe o servidor e passa a aceitar conexões."""
        import asyncssh

        if self._chave_do_host is None:
            raise ValidationError(
                "O servidor SSH precisa de uma chave de host em arquivo. "
                "Chave gerada a cada boot faz todo cliente ver o aviso de "
                "host key changed — o mesmo aviso de um ataque — e as "
                "pessoas aprendem a ignorá-lo."
            )
        if not self._chave_do_host.exists():
            raise ValidationError(
                f"Chave de host não encontrada em {self._chave_do_host}. "
                "Gere com: ssh-keygen -t ed25519 -f <caminho> -N ''"
            )

        servidor_ref = self

        class _Servidor(asyncssh.SSHServer):
            """Uma instância por conexão.

            O que a autenticação descobre vai para o registro do servidor,
            indexado pela conexão — é de lá que o handler do processo lê.
            """

            def __init__(self) -> None:
                self._conn: Any | None = None

            def connection_made(self, conn: Any) -> None:
                self._conn = conn

            def connection_lost(self, exc: Exception | None) -> None:
                # Sem isto o registro cresce para sempre: uma entrada por
                # conexão já encerrada é vazamento de memória num processo
                # que roda por meses.
                if self._conn is not None:
                    servidor_ref._autenticados.pop(id(self._conn), None)

            def begin_auth(self, username: str) -> bool:
                # True = exige autenticação. Nunca False: sessão sem
                # identidade é gravação que não responde "quem fez".
                return True

            def password_auth_supported(self) -> bool:
                return True

            async def validate_password(self, username: str, password: str) -> bool:
                # `usuario@alvo`: o último @ separa, porque o alvo pode ser um
                # FQDN e o usuário não contém @.
                if "@" not in username:
                    logger.warning(
                        "conexão recusada: usuário %r sem alvo (use usuario@alvo)",
                        username,
                    )
                    return False
                usuario, _, alvo = username.rpartition("@")
                usuario_id = await servidor_ref._autenticar(usuario, password)
                if usuario_id is None:
                    return False
                if self._conn is not None:
                    servidor_ref._autenticados[id(self._conn)] = Credenciais(
                        usuario_id=usuario_id, alvo=alvo, usuario_no_alvo=usuario
                    )
                return True

            # ------------------------------------------- o que se recusa

            def connection_requested(self, *args: Any, **kwargs: Any) -> bool:
                """Encaminhamento de porta: não sabemos gravar, então não passa."""
                logger.warning("encaminhamento de porta recusado: não é gravável")
                return False

            def server_requested(self, *args: Any, **kwargs: Any) -> bool:
                logger.warning("encaminhamento reverso recusado: não é gravável")
                return False

        async def _processo(processo: Any) -> None:
            """Uma sessão de terminal aceita.

            O que a autenticação descobriu — quem é e para onde vai — viaja
            pelo `Credenciais` guardado por conexão, não por atributo privado
            do asyncssh: alcançar a interna da biblioteca funciona até a
            primeira atualização dela, e o que quebraria é a gravação.
            """
            conexao = processo.get_extra_info("connection")
            dados = servidor_ref._autenticados.get(id(conexao))
            await servidor_ref._conduzir(processo, dados)

        self._servidor = await asyncssh.create_server(
            _Servidor,
            "",
            self._porta,
            server_host_keys=[str(self._chave_do_host)],
            process_factory=_processo,
        )
        logger.info("servidor SSH de sessões ouvindo na porta %d", self._porta)

    async def _conduzir(self, processo: Any, dados: Credenciais | None) -> None:
        """Liga a pessoa ao alvo e grava os dois sentidos.

        A ordem importa: a sessão é aberta (e o RBAC aplicado) **antes** de
        conectar ao alvo. Conectar primeiro abriria acesso a quem a política
        depois recusaria, e o fecho da conexão não desfaz o que já foi
        digitado.
        """
        import asyncssh

        if dados is None:
            # Não deveria acontecer: o asyncssh só chama o handler depois da
            # autenticação. Mas "não deveria" não é garantia, e sessão sem
            # identidade é gravação que não responde "quem fez" — então
            # recusa, em vez de gravar um acesso anônimo.
            processo.stderr.write("sessão sem identidade\r\n")
            processo.exit(1)
            return
        usuario_id, alvo = dados.usuario_id, dados.alvo

        if processo.get_terminal_type() is None:
            # Sem pty é execução de comando — passaria por um canal que este
            # adaptador não grava.
            processo.stderr.write(
                "este proxy só aceita sessão interativa: a gravação cobre o "
                "terminal, e comando avulso passaria sem registro\r\n"
            )
            processo.exit(1)
            return

        sessao_id = await self._abrir_sessao(usuario_id, alvo)
        self._proxy.abrir(sessao_id, alvo)

        try:
            usuario_alvo, senha_alvo = self._proxy.credencial_do_alvo(alvo)
            largura, altura, _, _ = processo.get_terminal_size()
            host_alvo, porta_alvo = separar_host_e_porta(alvo)

            async with (
                asyncssh.connect(
                    host_alvo,
                    port=porta_alvo,
                    username=usuario_alvo,
                    password=senha_alvo,
                    known_hosts=None,  # a confiança no alvo é gerida pelo cofre
                ) as conexao_alvo,
                conexao_alvo.create_process(
                    term_type=processo.get_terminal_type(),
                    term_size=(largura, altura),
                ) as alvo_proc,
            ):
                await self._copiar_ambos(processo, alvo_proc, sessao_id)
        except ValidationError:
            raise
        except Exception as erro:  # noqa: BLE001 — qualquer falha de rede/SSH
            logger.exception("sessão %s falhou", sessao_id)
            processo.stderr.write(f"não foi possível conectar a {alvo}: {erro}\r\n")
            processo.exit(1)
        finally:
            await self._fechar_sessao(sessao_id)
            self._proxy.fechar(sessao_id)

    async def _copiar_ambos(
        self, pessoa: Any, alvo: Any, sessao_id: str
    ) -> None:
        """Copia nos dois sentidos, gravando cada bloco.

        Duas tarefas e `FIRST_COMPLETED`: quando um lado fecha, a sessão
        acabou, e esperar o outro deixaria a conexão pendurada.
        """

        async def da_pessoa_para_o_alvo() -> None:
            while not pessoa.stdin.at_eof():
                dados = await pessoa.stdin.read(BLOCO_MAXIMO)
                if not dados:
                    break
                self._gravar(sessao_id, ProxySsh.ENTRADA, dados)
                alvo.stdin.write(dados)

        async def do_alvo_para_a_pessoa() -> None:
            while not alvo.stdout.at_eof():
                dados = await alvo.stdout.read(BLOCO_MAXIMO)
                if not dados:
                    break
                self._gravar(sessao_id, ProxySsh.SAIDA, dados)
                pessoa.stdout.write(dados)

        tarefas = [
            asyncio.create_task(da_pessoa_para_o_alvo()),
            asyncio.create_task(do_alvo_para_a_pessoa()),
        ]
        try:
            await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for tarefa in tarefas:
                tarefa.cancel()

    def _gravar(self, sessao_id: str, tipo: str, dados: Any) -> None:
        """Enfileira no proxy, tolerando byte inválido.

        `errors="replace"` de propósito: um byte quebrado no meio de um
        caractere multibyte não pode derrubar a sessão da pessoa nem
        interromper a gravação. Perde-se um caractere; mantém-se a prova.
        """
        texto = dados if isinstance(dados, str) else dados.decode("utf-8", "replace")
        self._proxy.registrar(sessao_id, tipo, texto)

    async def parar(self) -> None:
        if self._servidor is not None:
            self._servidor.close()
            await self._servidor.wait_closed()
            self._servidor = None
            logger.info("servidor SSH de sessões encerrado")
