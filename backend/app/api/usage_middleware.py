"""Middleware que registra as chamadas recebidas pela API.

## O corpo da requisição não é lido aqui

Este middleware **não** chama `await request.body()` nem toca no fluxo de
entrada. Só lê o cabeçalho `Content-Length`, que é um número já parseado
pelo servidor.

A razão é mais forte do que privacidade: ler o corpo num middleware o
consome do stream, e a rota seguinte receberia um corpo vazio. Resolver isso
exige bufferizar a requisição inteira em memória e reinjetá-la — e aí o
conteúdo de toda chamada de escrita, senha inclusive, passa a existir numa
variável deste processo, com chance de cair em log de exceção ou dump. O
caminho escolhido é não ter o dado: o que não é lido não vaza.

## Erro aqui nunca vira erro da API

Quem chamou já recebeu a resposta quando o registro acontece. Qualquer
exceção ao registrar é engolida: um banco de log cheio não pode transformar
uma leitura de segredo bem sucedida em 500 para o robô que depende dela.

## Por que middleware e não dependência de rota

Dependência só roda em rota que a declara, então qualquer rota nova nasceria
invisível no relatório — e a rota nova é justamente a que ninguém auditou
ainda. Middleware pega todas, inclusive a que ainda não existe, e inclusive
as que respondem 404 e 401, que é onde aparece quem está tateando a API.
"""

from __future__ import annotations

import contextlib
import hashlib
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..domain.apiusage.entities import Origem, registrar_chamada

# Só o que está sob este prefixo é API. `/saude`, `/docs` e os estáticos do
# front ficam de fora: são infraestrutura e página, não consumo de dados.
PREFIXO_API = "/api/v1"

# Rotas que não entram no registro nem quando chamadas de fora.
#
# `/auth/refresh` sai porque o navegador o chama sozinho a cada expiração de
# token: entraria como "externa" por não carregar `Origin` em alguns
# navegadores, e encheria o relatório de ruído do próprio sistema.
IGNORADAS = frozenset({f"{PREFIXO_API}/auth/refresh"})


class RegistroDeUsoMiddleware(BaseHTTPMiddleware):
    """Registra cada chamada de API vinda de fora da interface."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        fabrica_de_sessao: Callable[[], Session],
        origens_da_tela: tuple[str, ...],
    ) -> None:
        super().__init__(app)
        self._fabrica_padrao = fabrica_de_sessao
        self._origens = origens_da_tela

    def _fabrica(self, request: Request) -> tuple[Callable[[], Session], bool]:
        """A fábrica de sessão a usar nesta requisição.

        Honra `dependency_overrides[get_db]` quando existe. Sem isso o
        middleware abriria conexão própria contra o banco das settings
        reais, enquanto o resto da requisição usa o banco injetado — e em
        teste isso grava num banco que ninguém lê, fazendo qualquer asserção
        sobre o registrado passar por vacuidade. Foi exatamente o que
        aconteceu: o teste que varria a senha nas colunas passava varrendo
        uma tabela vazia.
        """
        from .deps import get_db

        app = getattr(request, "app", None)
        override = getattr(app, "dependency_overrides", {}).get(get_db) if app else None
        if override is None:
            return self._fabrica_padrao, True
        # O override é um gerador no formato de dependência do FastAPI. A
        # sessão que ele devolve pertence a quem o instalou, então ela é
        # usada e **não** fechada aqui — fechá-la deixaria o teste com uma
        # sessão morta nas asserções seguintes.
        sessao = next(override())
        return (lambda: sessao), False

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not request.url.path.startswith(PREFIXO_API):
            return await call_next(request)

        comeco = time.perf_counter()
        resposta = await call_next(request)
        duracao_ms = int((time.perf_counter() - comeco) * 1000)

        # Ver a nota do topo: a resposta já está pronta e vai embora inteira,
        # aconteça o que acontecer no registro. Um banco de log cheio não
        # pode transformar uma leitura de segredo bem sucedida em 500 para o
        # robô que depende dela.
        with contextlib.suppress(Exception):
            self._registrar(request, resposta, duracao_ms)

        return resposta

    def _registrar(self, request: Request, resposta: Response, duracao_ms: int) -> None:
        if request.url.path in IGNORADAS:
            return

        fabrica, pode_fechar = self._fabrica(request)
        token = _token_do_cabecalho(request)
        identidade = _identidade(fabrica, token, pode_fechar)

        origem = Origem.classificar(
            tem_lease=identidade.aplicacao_id is not None,
            origin=request.headers.get("origin"),
            sec_fetch_site=request.headers.get("sec-fetch-site"),
            origens_da_tela=self._origens,
        )
        # A tela do próprio Vault não entra no relatório: é o sistema
        # conversando consigo mesmo. Ver `Origem.classificar`.
        if origem is Origem.TELA:
            return

        chamada = registrar_chamada(
            metodo=request.method,
            # `request.url.path` e não a URL completa: a query string pode
            # carregar termo de busca, que é dado de quem usa, e nenhuma
            # pergunta deste relatório precisa dela.
            caminho=request.url.path,
            status=resposta.status_code,
            origem=origem,
            duracao_ms=duracao_ms,
            ip=_ip_do_cliente(request),
            agente=request.headers.get("user-agent", ""),
            aplicacao_id=identidade.aplicacao_id,
            aplicacao_nome=identidade.aplicacao_nome,
            usuario_id=identidade.usuario_id,
            usuario_email=identidade.usuario_email,
            bytes_recebidos=_tamanho_declarado(request),
        )

        from ..infrastructure.db.apiusage_repo import RegistroDeUsoSql

        sessao = fabrica()
        try:
            RegistroDeUsoSql(sessao).registrar(chamada)
        finally:
            if pode_fechar:
                sessao.close()


class _Identidade:
    """Quem chamou, até onde dá para saber sem custo alto."""

    __slots__ = ("aplicacao_id", "aplicacao_nome", "usuario_id", "usuario_email")

    def __init__(self) -> None:
        self.aplicacao_id: str | None = None
        self.aplicacao_nome: str = ""
        self.usuario_id: str | None = None
        self.usuario_email: str = ""


def _token_do_cabecalho(request: Request) -> str:
    cabecalho = request.headers.get("authorization", "")
    if not cabecalho.lower().startswith("bearer "):
        return ""
    return cabecalho.split(" ", 1)[1].strip()


def _identidade(
    fabrica: Callable[[], Session], token: str, pode_fechar: bool = True
) -> _Identidade:
    """Resolve quem chamou a partir do token apresentado.

    Procura **primeiro** o lease, por uma consulta de hash indexada. Se não
    for lease, tenta ler o JWT de pessoa — sem validar assinatura, porque
    aqui não se decide acesso nenhum: a rota já decidiu, e o status da
    resposta registra o que ela decidiu. Um token forjado aparece no
    relatório como o e-mail que ele alega, ao lado do 401 que levou — que é
    informação útil, não brecha.
    """
    identidade = _Identidade()
    if not token:
        return identidade

    from ..infrastructure.db.models import ApplicationModel, LeaseModel

    sessao = fabrica()
    try:
        digest = hashlib.sha256(token.encode()).hexdigest()
        lease = sessao.scalar(select(LeaseModel).where(LeaseModel.token_hash == digest))
        if lease is not None:
            identidade.aplicacao_id = lease.application_id
            app = sessao.get(ApplicationModel, lease.application_id)
            identidade.aplicacao_nome = app.display_name if app else ""
            return identidade
    except Exception:  # noqa: BLE001
        return identidade
    finally:
        if pode_fechar:
            sessao.close()

    sujeito, email = _ler_jwt_sem_validar(token)
    identidade.usuario_id = sujeito
    identidade.usuario_email = email
    return identidade


def _ler_jwt_sem_validar(token: str) -> tuple[str | None, str]:
    """Extrai `sub` e `email` do corpo do JWT, sem conferir a assinatura.

    Deliberado: validar aqui repetiria o trabalho que a rota já fez e
    exigiria o segredo de assinatura no middleware. O dado serve para
    **rotular uma linha de relatório**, nunca para liberar nada.
    """
    import base64
    import json

    try:
        partes = token.split(".")
        if len(partes) != 3:
            return None, ""
        corpo = partes[1]
        # O base64url do JWT vem sem o enchimento de "=" — repô-lo é o que
        # evita o erro de "comprimento inválido" em um token de cada quatro.
        corpo += "=" * (-len(corpo) % 4)
        dados = json.loads(base64.urlsafe_b64decode(corpo))
    except Exception:  # noqa: BLE001
        return None, ""

    sujeito = dados.get("sub")
    return (str(sujeito) if sujeito else None, str(dados.get("email", "")))


def _ip_do_cliente(request: Request) -> str:
    """O IP de quem chamou.

    `X-Forwarded-For` só é lido porque a aplicação roda atrás de um
    balanceador que o reescreve. Sem proxy confiável à frente, o cabeçalho é
    forjável e vale apenas como registro informativo — mesma ressalva de
    `api/deps.py`.
    """
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else ""


def _tamanho_declarado(request: Request) -> int:
    """Bytes declarados em `Content-Length`. O conteúdo não é lido."""
    bruto = request.headers.get("content-length")
    if not bruto:
        return 0
    try:
        return max(0, int(bruto))
    except ValueError:
        return 0
