"""Rotas de sessões privilegiadas e suas gravações.

Três telas do inventário: sessões ativas (com encerrar), histórico pesquisável
e player com timeline.

A escolha dos adaptadores acontece em `deps.py`, não aqui — este módulo só
conhece as portas `CapturaDeSessao` e `ArmazenamentoDeGravacao`. Conectar um
proxy SSH real ou um bucket com Object Lock é trocar a linha da injeção, sem
tocar nestas rotas.

## Quem vê o quê

Uma sessão gravada mostra o que alguém digitou num sistema de produção — e
isso é mais sensível que a maioria dos segredos. Por isso:

- cada pessoa vê as **próprias** sessões sempre;
- ver as dos outros exige `ADMIN` em `sessoes`;
- derrubar a sessão de alguém exige `ADMIN` **e** justificativa.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...application.ports.sessions import (
    ArmazenamentoDeGravacao,
    CapturaDeSessao,
)
from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.sessions.entities import (
    ConsumoDaSessao,
    OrigemDaSessao,
    TipoDeConsumo,
    EstadoDaSessao,
    EventoDeSessao,
    Sessao,
    TipoDeEvento,
    TipoDeSessao,
    expirar_ociosas,
)
from ...domain.shared.errors import PermissionDeniedError
from ...domain.shared.value_objects import PolicyPath
from ...infrastructure.db.repositories import (
    AuditRepository,
    PolicyRepository,
    SessaoRepository,
)
from ...infrastructure.sessions.adapters import serializar
from ..deps import (
    CurrentUser,
    get_audit,
    get_captura,
    get_current_user,
    get_db,
    get_gravacoes,
    get_policies,
    get_sessoes,
)

router = APIRouter(prefix="/sessoes", tags=["Sessões"])

CAMINHO_SESSOES = PolicyPath("sessoes")


class EventoResponse(BaseModel):
    deslocamento_ms: int
    tipo: str
    conteudo: str


class OrigemResponse(BaseModel):
    """De onde a sessão partiu."""

    ip_address: str | None
    hostname: str
    user_agent: str
    dispositivo_name: str
    # Uma linha pronta para a tela, do mais específico ao menos.
    descricao: str
    identificada: bool


class ConsumoResponse(BaseModel):
    """O que a sessão consumiu do cofre.

    **Nunca carrega o valor do segredo** — só o nome e o caminho. Quem
    precisa do valor passa pela rota de revelar, que registra evento.
    """

    tipo: str
    nome: str
    caminho: str
    pertence_a: str
    descricao: str
    saiu_do_cofre: bool


class SessaoResponse(BaseModel):
    id: str
    usuario_label: str
    tipo: str
    alvo: str
    motivo: str
    estado: str
    ip_address: str | None
    iniciada_em: datetime
    ultima_atividade_em: datetime
    encerrada_em: datetime | None
    encerrada_por: str
    motivo_encerramento: str
    duracao_ms: int
    eventos: int
    minha: bool
    # Honestidade sobre a origem: anotação manual e captura por proxy não
    # merecem a mesma confiança numa investigação.
    capturado_por: str
    captura_automatica: bool
    # De onde partiu e o que consumiu — duas perguntas diferentes que a
    # revisão faz sobre a mesma sessão.
    origem: OrigemResponse
    consumo: ConsumoResponse


class DetalheSessaoResponse(SessaoResponse):
    """A sessão com a linha do tempo, para o player."""

    linha_do_tempo: list[EventoResponse]
    aviso: str | None


class AbrirSessaoRequest(BaseModel):
    tipo: TipoDeSessao = TipoDeSessao.OUTRO
    alvo: str = Field(min_length=1, max_length=300)
    motivo: str = Field(default="", max_length=1000)
    segredo_path: str | None = Field(default=None, max_length=256)
    # De onde parte. O IP vem do servidor; estes vêm de quem abre, porque só
    # o cliente sabe o nome da própria máquina.
    origem_hostname: str = Field(default="", max_length=253)
    origem_dispositivo: str = Field(default="", max_length=64)
    # O que está sendo usado para entrar. O caminho identifica o segredo
    # sem revelá-lo: é o que a auditoria precisa e o máximo que ela deve ver.
    consumo_tipo: TipoDeConsumo = TipoDeConsumo.NAO_IDENTIFICADO
    consumo_nome: str = Field(default="", max_length=200)
    consumo_pertence_a: str = Field(default="", max_length=200)


class RegistrarEventoRequest(BaseModel):
    deslocamento_ms: int = Field(ge=0)
    tipo: TipoDeEvento = TipoDeEvento.ENTRADA
    conteudo: str = Field(min_length=1, max_length=10_000)


class EncerrarRequest(BaseModel):
    motivo: str = Field(default="", max_length=1000)


class DerrubarRequest(BaseModel):
    """Derrubar exige justificativa: é interromper o trabalho de alguém."""

    motivo: str = Field(min_length=1, max_length=1000)


def _evento_auditoria(
    current: CurrentUser,
    action: AuditAction,
    target: str,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
    reason: str = "",
) -> AuditEvent:
    return AuditEvent(
        action=action,
        actor_id=current.id,
        actor_label=current.email,
        target_path=target,
        outcome=outcome,
        reason=reason,
        ip_address=current.ip_address,
        user_agent=current.user_agent,
    )


def _pode_ver_todas(current: CurrentUser, policies: PolicyRepository) -> bool:
    return evaluate(
        policies.policies_for_user(current.id), CAMINHO_SESSOES, Capability.ADMIN
    )


@router.get("", response_model=list[SessaoResponse], summary="Sessões ativas")
def listar_ativas(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SessaoResponse]:
    """As sessões em andamento que este usuário pode ver.

    Expira as vencidas antes de listar: uma sessão ociosa há horas não deve
    aparecer como ativa só porque ninguém passou por aqui. Fazer isso na
    leitura, em vez de num agendador, evita um processo que precisa estar no
    ar para a regra valer.
    """
    todas = sessoes.ativas()
    for expirada in expirar_ociosas(todas):
        sessoes.save_estado(expirada)
    db.commit()

    visiveis = (
        sessoes.ativas()
        if _pode_ver_todas(current, policies)
        else sessoes.ativas_do_usuario(current.id)
    )
    return [_resposta(s, current, sessoes) for s in visiveis]


@router.post(
    "", response_model=SessaoResponse, status_code=status.HTTP_201_CREATED,
    summary="Abrir sessão",
)
def abrir(
    payload: AbrirSessaoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
    captura: Annotated[CapturaDeSessao, Depends(get_captura)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
) -> SessaoResponse:
    """Abre uma sessão e liga a captura.

    Qualquer autenticado pode abrir uma sessão sua: registrar o que se faz não
    é privilégio, é o oposto — exigir permissão para se auto-auditar só
    reduziria o registro.
    """
    sessao = Sessao(
        usuario_id=current.id,
        usuario_label=current.email,
        tipo=payload.tipo,
        alvo=payload.alvo,
        motivo=payload.motivo,
        segredo_path=payload.segredo_path,
        ip_address=current.ip_address,
        origem=OrigemDaSessao(
            ip_address=current.ip_address,
            hostname=payload.origem_hostname,
            # O user-agent vem do servidor: o cliente poderia mentir, mas
            # mentir no próprio cabeçalho é outro tipo de problema, e aqui
            # pelo menos o valor é o mesmo que a auditoria registrou.
            user_agent=current.user_agent or "",
            dispositivo_name=payload.origem_dispositivo,
        ),
        consumo=ConsumoDaSessao(
            tipo=payload.consumo_tipo,
            nome=payload.consumo_nome,
            # O caminho do segredo é o que já veio em `segredo_path`: evita
            # duas fontes para o mesmo dado, que divergiriam na primeira
            # chamada que preenchesse só uma delas.
            caminho=payload.segredo_path or "",
            pertence_a=payload.consumo_pertence_a,
        ),
    )
    captura.abrir(sessao.id, sessao.alvo)
    sessoes.add(sessao, captura.nome, captura.captura_automatica)
    audit.append(
        _evento_auditoria(
            current, AuditAction.SESSION_OPENED, str(sessao.path),
            reason=f"{payload.tipo} em {payload.alvo}. {payload.motivo}".strip(),
        )
    )
    return _resposta(sessao, current, sessoes)


@router.post(
    "/{sessao_id}/eventos", status_code=status.HTTP_204_NO_CONTENT,
    summary="Registrar evento",
)
def registrar_evento(
    sessao_id: str,
    payload: RegistrarEventoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
) -> None:
    """Acrescenta um evento à gravação.

    Só o dono da sessão registra. Permitir que outro escreva na gravação
    alheia destruiria o valor dela como prova — e seria a forma mais simples
    de forjar um registro.
    """
    sessao = sessoes.get(sessao_id)
    if sessao.usuario_id != current.id:
        raise PermissionDeniedError(
            "Só o dono da sessão registra eventos nela. Gravação que terceiros "
            "escrevem não prova nada."
        )

    evento = EventoDeSessao(
        deslocamento_ms=payload.deslocamento_ms,
        tipo=payload.tipo,
        conteudo=payload.conteudo,
    )
    # O domínio recusa se a sessão estiver encerrada ou o evento fora de ordem.
    sessao.registrar(evento)
    sessoes.registrar_evento(sessao_id, evento)


@router.post(
    "/{sessao_id}/encerrar", response_model=SessaoResponse, summary="Encerrar sessão"
)
def encerrar(
    sessao_id: str,
    payload: EncerrarRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
    captura: Annotated[CapturaDeSessao, Depends(get_captura)],
    gravacoes: Annotated[ArmazenamentoDeGravacao, Depends(get_gravacoes)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
) -> SessaoResponse:
    """Encerra a própria sessão e arquiva a gravação.

    A gravação é guardada no armazenamento externo ANTES de a sessão ser
    marcada como encerrada no banco. Se o arquivamento falhar, a sessão
    continua aberta e alguém percebe — o inverso perderia a gravação em
    silêncio, que é a pior falha possível aqui.
    """
    sessao = sessoes.get(sessao_id)
    if sessao.usuario_id != current.id:
        raise PermissionDeniedError(
            "Esta sessão é de outra pessoa. Para interrompê-la, use a "
            "derrubada — que exige permissão e justificativa."
        )

    captura.fechar(sessao_id)
    referencia = gravacoes.guardar(sessao_id, serializar(sessao.linha_do_tempo()))

    sessao.encerrar(por=current.email, motivo=payload.motivo)
    salva = sessoes.save_estado(
        sessao, gravacao_ref=referencia, gravacao_destino=gravacoes.nome
    )
    audit.append(
        _evento_auditoria(
            current, AuditAction.SESSION_CLOSED, str(sessao.path),
            reason=f"{len(sessao.eventos)} evento(s); gravação em {gravacoes.nome}.",
        )
    )
    return _resposta(salva, current, sessoes)


@router.post(
    "/{sessao_id}/derrubar", response_model=SessaoResponse, summary="Derrubar sessão"
)
def derrubar(
    sessao_id: str,
    payload: DerrubarRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    captura: Annotated[CapturaDeSessao, Depends(get_captura)],
    gravacoes: Annotated[ArmazenamentoDeGravacao, Depends(get_gravacoes)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> SessaoResponse:
    """Interrompe a sessão de alguém. Exige ADMIN e justificativa."""
    sessao = sessoes.get(sessao_id)
    if not _pode_ver_todas(current, policies):
        audit.append(
            _evento_auditoria(
                current, AuditAction.ACCESS_DENIED, str(sessao.path),
                AuditOutcome.FAILURE, "Sem permissão para derrubar sessões.",
            )
        )
        db.commit()
        raise PermissionDeniedError(
            "Derrubar a sessão de outra pessoa exige administração."
        )

    captura.fechar(sessao_id)
    referencia = gravacoes.guardar(sessao_id, serializar(sessao.linha_do_tempo()))

    sessao.derrubar(por=current.email, motivo=payload.motivo)
    salva = sessoes.save_estado(
        sessao, gravacao_ref=referencia, gravacao_destino=gravacoes.nome
    )
    audit.append(
        _evento_auditoria(
            current, AuditAction.SESSION_TERMINATED, str(sessao.path),
            reason=f"Sessão de {sessao.usuario_label} interrompida: {payload.motivo}",
        )
    )
    return _resposta(salva, current, sessoes)


@router.get(
    "/gravacoes", response_model=list[SessaoResponse], summary="Histórico de sessões"
)
def historico(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    termo: Annotated[str | None, Query(max_length=100)] = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SessaoResponse]:
    """Sessões encerradas, pesquisáveis por alvo e motivo.

    Quem não administra vê só as próprias — uma gravação mostra o que a pessoa
    digitou em produção, e isso é mais sensível que a maioria dos segredos.
    """
    if _pode_ver_todas(current, policies):
        encontradas = sessoes.historico(termo=termo, limite=limite)
    else:
        encontradas = sessoes.historico(
            termo=termo, usuario_label=current.email, limite=limite
        )
    return [_resposta(s, current, sessoes) for s in encontradas]


@router.get(
    "/{sessao_id}", response_model=DetalheSessaoResponse, summary="Reproduzir sessão"
)
def detalhe(
    sessao_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DetalheSessaoResponse:
    """A gravação completa, para o player.

    Abrir a gravação de outra pessoa **vira evento de auditoria**. Quem revisa
    também é revisado — senão a tela de gravações seria uma janela para a
    atividade alheia sem rastro nenhum.
    """
    sessao = sessoes.get(sessao_id)
    minha = sessao.usuario_id == current.id

    if not minha and not _pode_ver_todas(current, policies):
        audit.append(
            _evento_auditoria(
                current, AuditAction.ACCESS_DENIED, str(sessao.path),
                AuditOutcome.FAILURE, "Sem permissão para ver sessão alheia.",
            )
        )
        db.commit()
        raise PermissionDeniedError("Esta gravação é de outra pessoa.")

    if not minha:
        audit.append(
            _evento_auditoria(
                current, AuditAction.SESSION_REPLAYED, str(sessao.path),
                reason=f"Gravação de {sessao.usuario_label} reproduzida.",
            )
        )

    capturado_por, automatica, _, _ = sessoes.metadados(sessao_id)
    base = _resposta(sessao, current, sessoes)
    return DetalheSessaoResponse(
        **base.model_dump(),
        linha_do_tempo=[
            EventoResponse(deslocamento_ms=ms, tipo=str(tipo), conteudo=texto)
            for ms, tipo, texto in sessao.linha_do_tempo()
        ],
        aviso=(
            None
            if automatica
            else (
                "Esta gravação foi registrada manualmente, não capturada: ela "
                "contém o que a pessoa anotou, não necessariamente tudo o que "
                "aconteceu."
            )
        ),
    )


@router.get(
    "/{sessao_id}/busca", response_model=list[EventoResponse], summary="Buscar na gravação"
)
def buscar(
    sessao_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    sessoes: Annotated[SessaoRepository, Depends(get_sessoes)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    termo: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[EventoResponse]:
    """Procura dentro de uma gravação.

    É o que torna a gravação útil: ninguém assiste três horas de sessão para
    achar um comando. Sem busca, a gravação vira arquivo que se guarda e nunca
    se lê.
    """
    sessao = sessoes.get(sessao_id)
    if sessao.usuario_id != current.id and not _pode_ver_todas(current, policies):
        raise PermissionDeniedError("Esta gravação é de outra pessoa.")

    return [
        EventoResponse(
            deslocamento_ms=e.deslocamento_ms, tipo=str(e.tipo), conteudo=e.conteudo
        )
        for e in sessoes.buscar_em(sessao_id, termo)
    ]


def _resposta(
    sessao: Sessao, current: CurrentUser, sessoes: SessaoRepository
) -> SessaoResponse:
    capturado_por, automatica, _, _ = sessoes.metadados(sessao.id)
    return SessaoResponse(
        id=sessao.id,
        usuario_label=sessao.usuario_label,
        tipo=str(sessao.tipo),
        alvo=sessao.alvo,
        motivo=sessao.motivo,
        estado=str(sessao.estado),
        ip_address=sessao.ip_address,
        iniciada_em=sessao.iniciada_em,
        ultima_atividade_em=sessao.ultima_atividade_em,
        encerrada_em=sessao.encerrada_em,
        encerrada_por=sessao.encerrada_por,
        motivo_encerramento=sessao.motivo_encerramento,
        duracao_ms=sessao.duracao_ms,
        eventos=len(sessao.eventos),
        minha=sessao.usuario_id == current.id,
        capturado_por=capturado_por,
        captura_automatica=automatica,
        origem=_origem_response(sessao),
        consumo=_consumo_response(sessao),
    )


def _origem_response(sessao: Sessao) -> OrigemResponse:
    return OrigemResponse(
        ip_address=sessao.origem.ip_address,
        hostname=sessao.origem.hostname,
        user_agent=sessao.origem.user_agent,
        dispositivo_name=sessao.origem.dispositivo_name,
        descricao=sessao.origem.descricao,
        identificada=sessao.origem.identificada,
    )


def _consumo_response(sessao: Sessao) -> ConsumoResponse:
    """Nome e caminho, nunca o valor.

    O caminho responde "qual segredo foi usado?" sem revelar nada: quem
    quiser o valor passa pela rota de revelar, que registra evento próprio.
    """
    return ConsumoResponse(
        tipo=str(sessao.consumo.tipo),
        nome=sessao.consumo.nome,
        caminho=sessao.consumo.caminho,
        pertence_a=sessao.consumo.pertence_a,
        descricao=sessao.consumo.descricao,
        saiu_do_cofre=sessao.consumo.saiu_do_cofre,
    )
