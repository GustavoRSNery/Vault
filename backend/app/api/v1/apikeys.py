"""Rotas de chaves de API.

Uma chave de API tem governo próprio: serviço, ambiente, escopo, onde está em
uso e validade. Tratá-la como senha qualquer é o que faz empresas
descobrirem, no vazamento, que tinham 40 chaves ativas sem saber de quais
serviços nem de quem.

O **valor** continua sendo um segredo do cofre, cifrado e revelado pela rota
de sempre — que registra auditoria. Estas rotas tratam do governo, e por isso
devolvem tudo **menos** o valor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, evaluate
from ...domain.apikeys.entities import (
    AmbienteDaChave,
    ChaveDeApi,
    EstadoDaChave,
    FormatoDaChave,
    expirar_vencidas,
)
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import PermissionDeniedError
from ...domain.shared.value_objects import PolicyPath, Slug
from ...infrastructure.db.repositories import (
    AuditRepository,
    ChaveApiRepository,
    ConfiguracaoRepository,
    PolicyRepository,
)
from ..deps import CurrentUser, get_audit, get_current_user, get_db, get_policies

router = APIRouter(prefix="/chaves-api", tags=["Chaves de API"])

CAMINHO_CHAVES = PolicyPath("chaves-api")


def get_chaves(db: Annotated[Session, Depends(get_db)]) -> ChaveApiRepository:
    return ChaveApiRepository(db)


class ChaveResponse(BaseModel):
    """Tudo sobre a chave, menos o valor — esse exige revelar o segredo."""

    id: str
    name: str
    display_name: str
    servico: str
    ambiente: str
    formato: str
    nome_do_campo: str
    escopo: str
    usada_em: list[str]
    responsavel: str
    documentacao_url: str
    vault_name: str
    secret_name: str
    expira_em: datetime | None
    dias_para_vencer: int | None
    situacao: str
    vencendo: bool
    como_usar: str
    criado_por: str
    created_at: datetime


class CriarChaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    servico: str = Field(min_length=1, max_length=200)
    responsavel: str = Field(min_length=1, max_length=200)
    ambiente: AmbienteDaChave = AmbienteDaChave.PRODUCAO
    formato: FormatoDaChave = FormatoDaChave.BEARER
    nome_do_campo: str = Field(default="", max_length=100)
    escopo: str = Field(default="", max_length=2000)
    usada_em: list[str] = Field(default_factory=list)
    documentacao_url: str = Field(default="", max_length=500)
    # Onde o valor está guardado. Opcional: dá para cadastrar o governo antes
    # de ter a chave em mãos, que é o caso de quem ainda vai solicitá-la.
    vault_name: str = Field(default="", max_length=64)
    secret_name: str = Field(default="", max_length=64)
    dias_de_validade: int | None = Field(default=None, ge=1, le=3650)


class AtualizarChaveRequest(BaseModel):
    """Só o que for enviado muda. O nome é imutável — é o identificador."""

    display_name: str | None = Field(default=None, max_length=200)
    servico: str | None = Field(default=None, max_length=200)
    responsavel: str | None = Field(default=None, max_length=200)
    ambiente: AmbienteDaChave | None = None
    formato: FormatoDaChave | None = None
    nome_do_campo: str | None = Field(default=None, max_length=100)
    escopo: str | None = Field(default=None, max_length=2000)
    usada_em: list[str] | None = None
    documentacao_url: str | None = Field(default=None, max_length=500)
    vault_name: str | None = Field(default=None, max_length=64)
    secret_name: str | None = Field(default=None, max_length=64)
    # `None` aqui significa "sem vencimento", um valor legítimo e diferente
    # de "não mandei este campo" — por isso a rota usa `exclude_unset` e não
    # `exclude_none`. Sem essa distinção não há como tirar o prazo de uma
    # chave que passou a ser permanente.
    expira_em: datetime | None = None


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


@router.get("", response_model=list[ChaveResponse], summary="Listar chaves")
def listar(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    chaves: Annotated[ChaveApiRepository, Depends(get_chaves)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ChaveResponse]:
    """As chaves que este usuário pode ver, ordenadas pelo que vence antes.

    Expira as vencidas na leitura: depender de um job faria a lista mostrar
    como ativa uma chave que já morreu.
    """
    todas = chaves.list_all()
    for expirada in expirar_vencidas(todas):
        chaves.save(expirada)
    db.commit()

    minhas = policies.policies_for_user(current.id)
    alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
    return [
        _resposta(c, alerta)
        for c in chaves.list_all()
        if evaluate(minhas, c.path, Capability.LIST)
        or evaluate(minhas, c.path, Capability.READ)
    ]


@router.post(
    "", response_model=ChaveResponse, status_code=status.HTTP_201_CREATED,
    summary="Cadastrar chave",
)
def criar(
    payload: CriarChaveRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    chaves: Annotated[ChaveApiRepository, Depends(get_chaves)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> ChaveResponse:
    from datetime import timedelta

    from ...domain.shared.value_objects import utcnow

    expira = (
        utcnow() + timedelta(days=payload.dias_de_validade)
        if payload.dias_de_validade is not None
        else None
    )
    chave = ChaveDeApi(
        name=Slug(payload.name),
        display_name=payload.display_name,
        servico=payload.servico,
        ambiente=payload.ambiente,
        formato=payload.formato,
        nome_do_campo=payload.nome_do_campo,
        escopo=payload.escopo,
        usada_em=payload.usada_em,
        responsavel=payload.responsavel,
        documentacao_url=payload.documentacao_url,
        vault_name=payload.vault_name,
        secret_name=payload.secret_name,
        expira_em=expira,
        criado_por=current.email,
    )
    _exigir(
        current, policies, audit, db, chave.path, Capability.CREATE,
        "Sem permissão para cadastrar esta chave.",
    )
    chaves.add(chave)
    audit.append(
        _evento(
            current, AuditAction.API_KEY_CREATED, str(chave.path),
            reason=f"{payload.servico} ({payload.ambiente}). Responsável: {payload.responsavel}.",
        )
    )
    alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
    return _resposta(chave, alerta)


@router.get("/{nome}", response_model=ChaveResponse, summary="Detalhe da chave")
def detalhe(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    chaves: Annotated[ChaveApiRepository, Depends(get_chaves)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> ChaveResponse:
    chave = chaves.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, chave.path, Capability.READ,
        "Sem permissão para ver esta chave.",
    )
    alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
    return _resposta(chave, alerta)


@router.put("/{nome}", response_model=ChaveResponse, summary="Atualizar chave")
def atualizar(
    nome: str,
    payload: AtualizarChaveRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    chaves: Annotated[ChaveApiRepository, Depends(get_chaves)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> ChaveResponse:
    """Atualiza o governo da chave. O nome não muda: é o identificador."""
    chave = chaves.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, chave.path, Capability.UPDATE,
        "Sem permissão para alterar esta chave.",
    )

    # `exclude_unset` e não `exclude_none`: o cliente que envia
    # `expira_em: null` está pedindo para TIRAR o vencimento, e com
    # `exclude_none` esse pedido sumiria junto com os campos ausentes.
    campos = payload.model_dump(exclude_unset=True)
    # Os demais campos não aceitam nulo: nulo neles é cliente antigo mandando
    # o que não devia, e sobrescrever texto com `None` quebraria a entidade.
    campos = {
        campo: valor
        for campo, valor in campos.items()
        if valor is not None or campo == "expira_em"
    }
    if not campos:
        alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
        return _resposta(chave, alerta)

    for campo, valor in campos.items():
        setattr(chave, campo, valor)
    # Revalida: trocar o formato para CABECALHO sem informar o campo tornaria
    # a chave inutilizável, e o domínio recusa.
    chave.__post_init__()

    salva = chaves.save(chave)
    audit.append(
        _evento(
            current, AuditAction.API_KEY_UPDATED, str(chave.path),
            reason=f"Campos alterados: {', '.join(sorted(campos))}.",
        )
    )
    alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
    return _resposta(salva, alerta)


@router.post(
    "/{nome}/revogar", response_model=ChaveResponse, summary="Revogar chave"
)
def revogar(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    chaves: Annotated[ChaveApiRepository, Depends(get_chaves)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> ChaveResponse:
    """Marca como revogada. Não apaga: a auditoria quer saber que existiu."""
    chave = chaves.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, chave.path, Capability.UPDATE,
        "Sem permissão para revogar esta chave.",
    )
    chave.revogar()
    salva = chaves.save(chave)
    audit.append(
        _evento(
            current, AuditAction.API_KEY_REVOKED, str(chave.path),
            reason=f"{chave.servico} ({chave.ambiente}).",
        )
    )
    alerta = ConfiguracaoRepository(db).atual().alerta_certificado_dias
    return _resposta(salva, alerta)


@router.delete(
    "/{nome}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir chave"
)
def excluir(
    nome: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    chaves: Annotated[ChaveApiRepository, Depends(get_chaves)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Remove o registro de governo. O segredo no cofre NÃO é apagado.

    São coisas separadas de propósito: apagar o governo junto com o valor
    faria um clique remover a chave e o rastro dela ao mesmo tempo. Quem
    quer apagar o valor exclui o segredo, e isso tem auditoria própria.
    """
    chave = chaves.get_by_name(Slug(nome))
    _exigir(
        current, policies, audit, db, chave.path, Capability.DELETE,
        "Sem permissão para excluir esta chave.",
    )
    chaves.delete(chave.id)
    audit.append(
        _evento(
            current, AuditAction.API_KEY_DELETED, str(chave.path),
            reason=(
                f"{chave.servico} ({chave.ambiente}). O segredo no cofre não "
                "foi apagado."
            ),
        )
    )


def _resposta(chave: ChaveDeApi, alerta_dias: int) -> ChaveResponse:
    return ChaveResponse(
        id=chave.id,
        name=str(chave.name),
        display_name=chave.display_name,
        servico=chave.servico,
        ambiente=str(chave.ambiente),
        formato=str(chave.formato),
        nome_do_campo=chave.nome_do_campo,
        escopo=chave.escopo,
        usada_em=chave.usada_em,
        responsavel=chave.responsavel,
        documentacao_url=chave.documentacao_url,
        vault_name=chave.vault_name,
        secret_name=chave.secret_name,
        expira_em=chave.expira_em,
        dias_para_vencer=chave.dias_para_vencer(),
        situacao=str(chave.situacao()),
        vencendo=chave.vencendo(alerta_dias),
        como_usar=chave.como_usar(),
        criado_por=chave.criado_por,
        created_at=chave.created_at,
    )
