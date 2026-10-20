"""Integrações: destinos de webhook e a fila de entregas.

O padrão é Standard Webhooks (standardwebhooks.com) — a especificação aberta
que Svix, Resend e Clerk adotaram. O que ela resolve está comentado no
domínio; aqui ficam só as decisões da borda HTTP.

A principal: **o segredo de assinatura aparece uma vez.** Ao cadastrar e ao
rotacionar, e nunca mais. Quem o perdeu rotaciona; mostrá-lo de novo numa
listagem o espalharia por logs de proxy, histórico de navegador e captura de
tela de quem só queria conferir uma URL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...application.ports.webhooks import EntregadorDeWebhook
from ...application.services.webhooks import despachar as despachar_servico
from ...application.services.webhooks import publicar as publicar_servico
from ...application.services.webhooks import enfileirar_da_trilha
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.integrations.entities import (
    Destino,
    EstadoDoDestino,
    TipoDeEvento,
)
from ...domain.access.policy import Capability, evaluate
from ...domain.shared.errors import PermissionDeniedError
from ...domain.shared.value_objects import PolicyPath, Slug, utcnow
from ...infrastructure.db.repositories import (
    AuditRepository,
    DestinoWebhookRepository,
    EntregaWebhookRepository,
    PolicyRepository,
)
from ..deps import (
    CurrentUser,
    get_audit,
    get_current_user,
    get_db,
    get_destinos_webhook,
    get_entregador_webhook,
    get_entregas_webhook,
    get_policies,
)

router = APIRouter(tags=["integracoes"])

CAMINHO_BASE = "integracoes"


class DestinoResponse(BaseModel):
    """O destino **sem** o segredo de assinatura.

    O segredo sai só no cadastro e na rotação. Repeti-lo aqui o espalharia
    por log de proxy e histórico de navegador a cada vez que alguém abrisse
    a tela para conferir uma URL.
    """

    id: str
    name: str
    display_name: str
    url: str
    eventos: list[str]
    estado: str
    descricao: str
    falhas_seguidas: int
    ultima_entrega_em: datetime | None
    ultimo_erro: str
    created_at: datetime


class DestinoCriadoResponse(DestinoResponse):
    """O cadastro, com o segredo — a única vez que ele aparece."""

    segredo: str
    aviso: str = (
        "Guarde o segredo agora: ele não será mostrado de novo. "
        "Quem o perder rotaciona."
    )


class CriarDestinoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=1000)
    # Vazio = todos. `segredo.*` casa a família inteira, inclusive eventos
    # que ainda não existem.
    eventos: list[str] = Field(default_factory=list)
    descricao: str = Field(default="", max_length=2000)


class AtualizarDestinoRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=1000)
    eventos: list[str] | None = None
    descricao: str | None = Field(default=None, max_length=2000)


class EntregaResponse(BaseModel):
    id: str
    id_evento: str
    tipo: str
    estado: str
    tentativas: int
    proxima_em: datetime
    ultimo_status: int | None
    ultimo_erro: str
    entregue_em: datetime | None
    created_at: datetime


class DespachoResponse(BaseModel):
    tentadas: int
    entregues: int
    falhadas: int
    desistidas: int
    destinos_desligados: int
    entregador: str


def _evento(
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


def _exigir(
    current: CurrentUser,
    policies: PolicyRepository,
    audit: AuditRepository,
    db: Session,
    caminho: PolicyPath,
    capacidade: Capability,
    mensagem: str,
) -> None:
    if evaluate(policies.policies_for_user(current.id), caminho, capacidade):
        return
    audit.append(
        _evento(
            current, AuditAction.ACCESS_DENIED, str(caminho),
            AuditOutcome.FAILURE, mensagem,
        )
    )
    db.commit()
    raise PermissionDeniedError(mensagem)


def _resposta(destino: Destino) -> DestinoResponse:
    return DestinoResponse(
        id=destino.id,
        name=str(destino.name),
        display_name=destino.display_name,
        url=destino.url,
        eventos=list(destino.eventos),
        estado=str(destino.estado),
        descricao=destino.descricao,
        falhas_seguidas=destino.falhas_seguidas,
        ultima_entrega_em=destino.ultima_entrega_em,
        ultimo_erro=destino.ultimo_erro,
        created_at=destino.created_at,
    )


@router.get(
    "/integracoes",
    response_model=list[DestinoResponse],
    summary="Listar destinos de webhook",
)
def listar(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DestinoResponse]:
    _exigir(
        current, policies, audit, db, PolicyPath(CAMINHO_BASE), Capability.LIST,
        "Sem permissão para ver integrações.",
    )
    return [_resposta(d) for d in destinos.list_all()]


@router.get(
    "/integracoes/eventos",
    response_model=list[str],
    summary="Eventos que o Vault publica",
)
def eventos_disponiveis(
    current: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[str]:
    """A lista para a tela montar o seletor.

    Sem permissão especial: são nomes de tipo de evento, não dados. Exigir
    permissão aqui só impediria alguém de descobrir o que pode assinar.
    """
    return sorted(str(e) for e in TipoDeEvento)


@router.post(
    "/integracoes",
    response_model=DestinoCriadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar destino",
)
def criar(
    payload: CriarDestinoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DestinoCriadoResponse:
    """Cadastra e devolve o segredo de assinatura — a única vez que ele sai."""
    _exigir(
        current, policies, audit, db, PolicyPath(CAMINHO_BASE), Capability.CREATE,
        "Sem permissão para cadastrar integrações.",
    )

    destino = Destino(
        name=Slug(payload.name),
        display_name=payload.display_name,
        url=payload.url,
        eventos=payload.eventos,
        descricao=payload.descricao,
        criado_por=current.email,
        # Começa do presente, não do zero: um destino recém-cadastrado não
        # deve receber de uma vez todo o histórico do cofre — seria uma
        # enxurrada de eventos antigos que ninguém pediu, e os mais
        # sensíveis entre eles.
        ultima_sequencia=audit.count(),
    )
    salvo = destinos.add(destino)
    audit.append(
        _evento(
            current, AuditAction.INTEGRATION_CREATED, str(destino.path),
            reason=f"Destino {destino.display_name}. Eventos: "
            f"{', '.join(destino.eventos) or 'todos'}.",
        )
    )
    db.commit()

    base = _resposta(salvo)
    return DestinoCriadoResponse(**base.model_dump(), segredo=salvo.segredo)


@router.put(
    "/integracoes/{nome}",
    response_model=DestinoResponse,
    summary="Atualizar destino",
)
def atualizar(
    nome: str,
    payload: AtualizarDestinoRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DestinoResponse:
    destino = destinos.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, destino.path, Capability.UPDATE,
        "Sem permissão para alterar esta integração.",
    )

    campos = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    for campo, valor in campos.items():
        setattr(destino, campo, valor)
    # Revalida: trocar a URL para http tornaria o destino inseguro, e o
    # domínio recusa.
    destino.__post_init__()

    salvo = destinos.save(destino)
    audit.append(
        _evento(
            current, AuditAction.INTEGRATION_UPDATED, str(destino.path),
            reason=f"Campos alterados: {', '.join(sorted(campos))}.",
        )
    )
    db.commit()
    return _resposta(salvo)


@router.post(
    "/integracoes/{nome}/rotacionar-segredo",
    response_model=DestinoCriadoResponse,
    summary="Rotacionar o segredo de assinatura",
)
def rotacionar(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DestinoCriadoResponse:
    """Gera um segredo novo.

    **As entregas em voo passam a falhar** até o destino ser atualizado com o
    valor novo: a especificação prevê enviar duas assinaturas durante a
    transição, mas isso exigiria guardar os dois segredos, e guardar segredo
    antigo "por via das dúvidas" é o oposto de rotacionar. A tela avisa.
    """
    destino = destinos.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, destino.path, Capability.ADMIN,
        "Sem permissão para rotacionar o segredo desta integração.",
    )

    novo = destino.rotacionar_segredo()
    salvo = destinos.save(destino)
    audit.append(
        _evento(
            current, AuditAction.INTEGRATION_SECRET_ROTATED, str(destino.path),
            reason="Segredo de assinatura rotacionado. O valor anterior "
            "deixou de valer imediatamente.",
        )
    )
    db.commit()

    base = _resposta(salvo)
    return DestinoCriadoResponse(
        **base.model_dump(),
        segredo=novo,
        aviso=(
            "Atualize o destino com este segredo agora: as entregas falharão "
            "até que ele seja trocado dos dois lados."
        ),
    )


@router.post(
    "/integracoes/{nome}/pausar",
    response_model=DestinoResponse,
    summary="Pausar destino",
)
def pausar(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DestinoResponse:
    """Para de enviar sem apagar o cadastro nem a fila."""
    destino = destinos.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, destino.path, Capability.UPDATE,
        "Sem permissão para pausar esta integração.",
    )
    destino.estado = EstadoDoDestino.PAUSADO
    salvo = destinos.save(destino)
    audit.append(
        _evento(current, AuditAction.INTEGRATION_UPDATED, str(destino.path),
                reason="Destino pausado.")
    )
    db.commit()
    return _resposta(salvo)


@router.post(
    "/integracoes/{nome}/reativar",
    response_model=DestinoResponse,
    summary="Reativar destino",
)
def reativar(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DestinoResponse:
    destino = destinos.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, destino.path, Capability.UPDATE,
        "Sem permissão para reativar esta integração.",
    )
    destino.reativar()
    salvo = destinos.save(destino)
    audit.append(
        _evento(current, AuditAction.INTEGRATION_UPDATED, str(destino.path),
                reason="Destino reativado; contador de falhas zerado.")
    )
    db.commit()
    return _resposta(salvo)


@router.delete(
    "/integracoes/{nome}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir destino",
)
def excluir(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    destino = destinos.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, destino.path, Capability.DELETE,
        "Sem permissão para excluir esta integração.",
    )
    destinos.delete(destino.id)
    audit.append(
        _evento(
            current, AuditAction.INTEGRATION_DELETED, str(destino.path),
            reason=f"Destino {destino.display_name} removido com sua fila.",
        )
    )
    db.commit()


@router.get(
    "/integracoes/{nome}/entregas",
    response_model=list[EntregaResponse],
    summary="Fila de entregas do destino",
)
def entregas_do_destino(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    entregas: Annotated[EntregaWebhookRepository, Depends(get_entregas_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[EntregaResponse]:
    """O histórico recente, **sem o corpo do evento**.

    O corpo carrega caminhos de segredos e o que mais o evento descrever;
    exibi-lo numa listagem o espalharia para quem só queria conferir se a
    entrega passou.
    """
    destino = destinos.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, destino.path, Capability.READ,
        "Sem permissão para ver as entregas desta integração.",
    )
    return [
        EntregaResponse(
            id=e.id,
            id_evento=e.id_evento,
            tipo=e.tipo,
            estado=str(e.estado),
            tentativas=e.tentativas,
            proxima_em=e.proxima_em,
            ultimo_status=e.ultimo_status,
            ultimo_erro=e.ultimo_erro,
            entregue_em=e.entregue_em,
            created_at=e.created_at,
        )
        for e in entregas.list_for_destino(destino.id, limite)
    ]


@router.post(
    "/integracoes/{nome}/testar",
    response_model=DespachoResponse,
    summary="Enviar um evento de teste",
)
def testar(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    entregas: Annotated[EntregaWebhookRepository, Depends(get_entregas_webhook)],
    entregador: Annotated[EntregadorDeWebhook, Depends(get_entregador_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> DespachoResponse:
    """Dispara um evento de teste e entrega na hora.

    É a única rota que entrega dentro da requisição, e de propósito: quem
    acabou de cadastrar quer saber agora se funcionou. O conteúdo não traz
    dado de cofre nenhum — é só um aviso de que o canal está de pé.
    """
    destino = destinos.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, destino.path, Capability.UPDATE,
        "Sem permissão para testar esta integração.",
    )

    agora = utcnow()
    fila = publicar_servico(
        "teste.ping",
        {
            "mensagem": "Teste de integração do Vault.",
            "solicitado_por": current.email,
        },
        # Ignora o filtro de eventos: um teste que não chega porque o destino
        # não assina `teste.ping` não testa nada.
        destinos=[_sem_filtro(destino)],
        agora=agora,
    )
    for e in fila:
        e.destino_id = destino.id
        entregas.add(e)

    resumo, atualizadas, tocados = despachar_servico(
        fila, {destino.id: destino}, entregador, agora=agora
    )
    for e in atualizadas:
        entregas.save(e)
    for d in tocados:
        destinos.save(d)

    audit.append(
        _evento(
            current, AuditAction.INTEGRATION_TESTED, str(destino.path),
            outcome=(
                AuditOutcome.SUCCESS if resumo.entregues else AuditOutcome.FAILURE
            ),
            reason=f"Teste via {entregador.nome}: "
            f"{resumo.entregues} entregue(s), {resumo.falhadas} falha(s).",
        )
    )
    db.commit()

    return DespachoResponse(
        tentadas=resumo.tentadas,
        entregues=resumo.entregues,
        falhadas=resumo.falhadas,
        desistidas=resumo.desistidas,
        destinos_desligados=resumo.destinos_desligados,
        entregador=entregador.nome,
    )


@router.post(
    "/integracoes/despachar",
    response_model=DespachoResponse,
    summary="Processar a fila de entregas",
)
def despachar_fila(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    destinos: Annotated[DestinoWebhookRepository, Depends(get_destinos_webhook)],
    entregas: Annotated[EntregaWebhookRepository, Depends(get_entregas_webhook)],
    entregador: Annotated[EntregadorDeWebhook, Depends(get_entregador_webhook)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> DespachoResponse:
    """Entrega o que está pronto na fila.

    Existe como rota para que um agendador externo a chame — o Vault não tem
    processo de fundo próprio, e inventar um esconderia do operador quando as
    entregas acontecem.
    """
    _exigir(
        current, policies, audit, db, PolicyPath(CAMINHO_BASE), Capability.ADMIN,
        "Sem permissão para despachar a fila de integrações.",
    )

    agora = utcnow()
    todos = destinos.list_all()

    # Primeiro recolhe o que aconteceu desde a última passada. A trilha é a
    # fonte: um registro paralelo de "o que falta publicar" divergiria dela
    # no primeiro erro de escrita.
    #
    # Cada destino tem seu próprio marcador, então um destino que ficou
    # pausado uma semana recebe o que perdeu, sem reenviar nada aos demais.
    for destino in todos:
        if not destino.ativo:
            continue
        novos = audit.desde_sequencia(destino.ultima_sequencia, limite=200)
        fila, maior = enfileirar_da_trilha(novos, [destino])
        for entrega in fila:
            entregas.add(entrega)
        if maior > destino.ultima_sequencia:
            destino.ultima_sequencia = maior
            destinos.save(destino)

    prontas = entregas.prontas(agora, limite)
    por_id = {d.id: d for d in todos}

    resumo, atualizadas, tocados = despachar_servico(
        prontas, por_id, entregador, agora=agora
    )
    for e in atualizadas:
        entregas.save(e)
    for d in tocados:
        destinos.save(d)
    db.commit()

    return DespachoResponse(
        tentadas=resumo.tentadas,
        entregues=resumo.entregues,
        falhadas=resumo.falhadas,
        desistidas=resumo.desistidas,
        destinos_desligados=resumo.destinos_desligados,
        entregador=entregador.nome,
    )


def _sem_filtro(destino: Destino) -> Destino:
    """Cópia do destino que aceita qualquer evento, para o teste de ping."""
    from dataclasses import replace

    return replace(destino, eventos=[])
