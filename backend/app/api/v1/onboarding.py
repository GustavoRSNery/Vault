"""Rotas de convite e recuperação de senha.

Dois caminhos para recuperar, e a diferença entre eles importa:

1. **Com MFA** — a pessoa prova identidade pelo código do autenticador e
   troca a senha na hora, sem envolver ninguém. É o caminho bom: o segundo
   fator já é a prova, e esperar aprovação de um colega só adiaria o óbvio.

2. **Sem MFA** — abre um pedido que um administrador aprova. Não é
   autoatendimento porque não há o que provar; o valor está em deixar o
   pedido e a aprovação registrados, em vez de a conversa acontecer por fora
   sem rastro.

Os links são **gerados e exibidos**, não enviados. Quem convida copia e
entrega pelo canal que quiser. Quando houver servidor de e-mail, o mesmo link
vai por lá sem mudar nada aqui — é a porta `Notificador` que muda, não esta
camada.

## Por que as respostas não distinguem

`/recuperar` responde igual para e-mail que existe e que não existe. Caso
contrário, a tela de recuperação vira um oráculo que diz quem tem conta —
e saber quem trabalha na empresa é o primeiro passo de um ataque dirigido.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, evaluate
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.onboarding.entities import (
    CONVITE_DIAS_MAXIMO,
    PedidoDeRedefinicao,
    TipoDeConvite,
    criar_convite,
    criar_redefinicao,
)
from ...domain.shared.errors import (
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)
from ...domain.shared.value_objects import Email, PolicyPath
from ...infrastructure.auth.totp import TotpService, require_six_digits
from ...infrastructure.crypto.passwords import Argon2PasswordHasher
from ...infrastructure.db.models import UserModel
from ...infrastructure.db.repositories import (
    AuditRepository,
    ConviteRepository,
    PedidoRedefinicaoRepository,
    PolicyRepository,
    UserRepository,
)
from ..deps import (
    CurrentUser,
    get_audit,
    get_current_user,
    get_db,
    get_policies,
    get_totp,
)

router = APIRouter(tags=["Convites e recuperação"])

CAMINHO_ADMIN = PolicyPath("admin")

# Resposta única de `/recuperar`: não conta se o e-mail existe.
RESPOSTA_NEUTRA = (
    "Se houver uma conta com este e-mail e segundo fator ativo, o código do "
    "autenticador permite redefinir a senha agora."
)


def get_convites(db: Annotated[Session, Depends(get_db)]) -> ConviteRepository:
    return ConviteRepository(db)


def get_pedidos(
    db: Annotated[Session, Depends(get_db)],
) -> PedidoRedefinicaoRepository:
    return PedidoRedefinicaoRepository(db)


def get_users(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


# ------------------------------------------------------------------ schemas


class ConviteResponse(BaseModel):
    """O convite criado, com o link que aparece uma única vez."""

    id: str
    email: str
    tipo: str
    link: str
    expira_em: datetime
    aviso: str


class ConvitePendenteResponse(BaseModel):
    id: str
    email: str
    tipo: str
    nome_sugerido: str
    papeis: list[str]
    criado_por: str
    criado_em: datetime
    expira_em: datetime
    expirado: bool


class CriarConviteRequest(BaseModel):
    email: EmailStr
    nome_sugerido: str = Field(default="", max_length=200)
    papeis: list[str] = Field(default_factory=list)
    dias: int = Field(default=7, ge=1, le=CONVITE_DIAS_MAXIMO)


class RecuperarRequest(BaseModel):
    email: EmailStr


class RecuperarResponse(BaseModel):
    mensagem: str
    # True quando a conta tem MFA: a tela sabe se pede o código ou oferece
    # abrir pedido ao administrador. Não revela se o e-mail existe — vale
    # False tanto para conta sem MFA quanto para e-mail inexistente.
    pode_usar_autenticador: bool


class RedefinirComTotpRequest(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=6, max_length=10)
    nova_senha: str = Field(min_length=12, max_length=200)


class PedirRedefinicaoRequest(BaseModel):
    email: EmailStr
    motivo: str = Field(default="", max_length=500)


class PedidoResponse(BaseModel):
    id: str
    email: str
    motivo: str
    ip_address: str | None
    criado_em: datetime


class AceitarConviteRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    nome: str = Field(min_length=1, max_length=200)
    senha: str = Field(min_length=12, max_length=200)


class ConviteInfoResponse(BaseModel):
    """O que a tela de aceite mostra antes de pedir a senha."""

    email: str
    tipo: str
    nome_sugerido: str
    valido: bool


class RedefinirComLinkRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    nova_senha: str = Field(min_length=12, max_length=200)


# ------------------------------------------------------------------ helpers


def _evento(
    actor_id: str | None,
    actor_label: str,
    action: AuditAction,
    target: str,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
    reason: str = "",
    ip: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        action=action,
        actor_id=actor_id,
        actor_label=actor_label,
        target_path=target,
        outcome=outcome,
        reason=reason,
        ip_address=ip,
    )


def _exigir_admin(
    current: CurrentUser,
    policies: PolicyRepository,
    audit: AuditRepository,
    db: Session,
    acao: str,
) -> None:
    if evaluate(policies.policies_for_user(current.id), CAMINHO_ADMIN, Capability.ADMIN):
        return
    audit.append(
        _evento(
            current.id, current.email, AuditAction.ACCESS_DENIED,
            str(CAMINHO_ADMIN), AuditOutcome.FAILURE,
            f"Sem permissão: {acao}.", current.ip_address,
        )
    )
    db.commit()
    raise PermissionDeniedError("Esta ação exige administração.")


def _link(token: str, tipo: TipoDeConvite) -> str:
    """Caminho relativo. O host é do front — a API não o conhece, e inventá-lo
    aqui daria link quebrado atrás de qualquer proxy."""
    rota = "convite" if tipo is TipoDeConvite.NOVO_USUARIO else "redefinir"
    return f"/{rota}/{token}"


# ------------------------------------------------------------------ convite


@router.post(
    "/convites",
    response_model=ConviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convidar usuário",
)
def convidar(
    payload: CriarConviteRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    convites: Annotated[ConviteRepository, Depends(get_convites)],
    users: Annotated[UserRepository, Depends(get_users)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> ConviteResponse:
    """Cria o convite e devolve o link, que aparece uma única vez."""
    _exigir_admin(current, policies, audit, db, "convidar usuário")

    if users.get_by_email(str(payload.email)) is not None:
        raise ConflictError("Já existe uma conta com este e-mail.")

    convite, token = criar_convite(
        str(payload.email),
        current.email,
        nome_sugerido=payload.nome_sugerido,
        papeis=payload.papeis,
        dias=payload.dias,
    )
    convites.add(convite)
    audit.append(
        _evento(
            current.id, current.email, AuditAction.USER_INVITED,
            f"convites/{payload.email}",
            reason=f"Válido por {payload.dias} dia(s). Papéis: {', '.join(payload.papeis) or '—'}.",
            ip=current.ip_address,
        )
    )

    return ConviteResponse(
        id=convite.id,
        email=str(convite.email),
        tipo=str(convite.tipo),
        link=_link(token, convite.tipo),
        expira_em=convite.expira_em,
        aviso=(
            "Este link aparece uma única vez e não fica guardado. Entregue-o "
            "pelo canal que preferir — ele dá acesso à criação da conta."
        ),
    )


@router.get(
    "/convites", response_model=list[ConvitePendenteResponse], summary="Convites pendentes"
)
def listar_convites(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    convites: Annotated[ConviteRepository, Depends(get_convites)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConvitePendenteResponse]:
    """Os convites em aberto. O token não volta — nem para quem administra."""
    _exigir_admin(current, policies, audit, db, "listar convites")
    return [
        ConvitePendenteResponse(
            id=c.id,
            email=str(c.email),
            tipo=str(c.tipo),
            nome_sugerido=c.nome_sugerido,
            papeis=c.papeis,
            criado_por=c.criado_por,
            criado_em=c.criado_em,
            expira_em=c.expira_em,
            expirado=not c.esta_valido(),
        )
        for c in convites.pendentes()
    ]


@router.post(
    "/convites/{convite_id}/cancelar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar convite",
)
def cancelar_convite(
    convite_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    convites: Annotated[ConviteRepository, Depends(get_convites)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Para quando o convite foi mandado para o endereço errado."""
    _exigir_admin(current, policies, audit, db, "cancelar convite")
    convite = convites.get(convite_id)
    convite.cancelar()
    convites.save(convite)
    audit.append(
        _evento(
            current.id, current.email, AuditAction.INVITE_CANCELLED,
            f"convites/{convite.email}", ip=current.ip_address,
        )
    )


@router.get(
    "/convites/{token}/info",
    response_model=ConviteInfoResponse,
    summary="O que o convite oferece",
)
def info_do_convite(
    token: str,
    convites: Annotated[ConviteRepository, Depends(get_convites)],
) -> ConviteInfoResponse:
    """Dados mínimos para a tela de aceite, sem autenticação.

    Devolve `valido: false` em vez de 404 para link inválido: um 404
    distinguiria "token errado" de "token expirado", e isso ajuda quem está
    testando tokens.
    """
    convite = convites.por_token(token)
    if convite is None or not convite.esta_valido():
        return ConviteInfoResponse(
            email="", tipo="", nome_sugerido="", valido=False
        )
    return ConviteInfoResponse(
        email=str(convite.email),
        tipo=str(convite.tipo),
        nome_sugerido=convite.nome_sugerido,
        valido=True,
    )


@router.post(
    "/convites/aceitar",
    status_code=status.HTTP_201_CREATED,
    summary="Criar a conta pelo convite",
)
def aceitar_convite(
    payload: AceitarConviteRequest,
    convites: Annotated[ConviteRepository, Depends(get_convites)],
    users: Annotated[UserRepository, Depends(get_users)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Cria a conta. Sem autenticação: o token É a prova."""
    convite = convites.por_token(payload.token)
    if convite is None or convite.tipo is not TipoDeConvite.NOVO_USUARIO:
        raise ValidationError("Convite inválido ou expirado.")

    # Consumir primeiro: se a criação falhar, o link não fica vivo para uma
    # segunda tentativa de quem o interceptou.
    convite.consumir()
    convites.save(convite)

    if users.get_by_email(str(convite.email)) is not None:
        raise ConflictError("Já existe uma conta com este e-mail.")

    usuario = UserModel(
        email=str(convite.email),
        full_name=payload.nome,
        password_hash=Argon2PasswordHasher().hash(payload.senha),
        is_active=True,
    )
    db.add(usuario)
    db.flush()

    if convite.papeis:
        users.set_roles(usuario.id, convite.papeis)

    audit.append(
        _evento(
            usuario.id, usuario.email, AuditAction.USER_JOINED,
            f"usuarios/{usuario.email}",
            reason=f"Conta criada por convite de {convite.criado_por}.",
        )
    )
    return {"email": usuario.email, "mensagem": "Conta criada. Faça login."}


# -------------------------------------------------------------- recuperação


@router.post(
    "/recuperar", response_model=RecuperarResponse, summary="Começar a recuperação"
)
def recuperar(
    payload: RecuperarRequest,
    users: Annotated[UserRepository, Depends(get_users)],
) -> RecuperarResponse:
    """Diz se a conta pode usar o autenticador — sem revelar se ela existe.

    `pode_usar_autenticador` é False tanto para conta sem MFA quanto para
    e-mail inexistente. A tela mostra o mesmo texto nos dois casos, e quem
    tem MFA simplesmente vê o campo de código aparecer.
    """
    usuario = users.get_by_email(str(payload.email))
    tem_mfa = usuario is not None and usuario.is_active and usuario.mfa_enabled
    return RecuperarResponse(
        mensagem=RESPOSTA_NEUTRA, pode_usar_autenticador=tem_mfa
    )


@router.post(
    "/recuperar/autenticador",
    summary="Redefinir a senha com o código do autenticador",
)
def redefinir_com_totp(
    payload: RedefinirComTotpRequest,
    users: Annotated[UserRepository, Depends(get_users)],
    totp: Annotated[TotpService, Depends(get_totp)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Troca a senha provando identidade pelo segundo fator.

    O código do autenticador É a prova: quem o tem possui o segredo que foi
    cadastrado no enrolamento. Exigir também um link por e-mail não somaria
    segurança — somaria dependência de um canal que não é seguro.
    """
    require_six_digits(payload.codigo)
    usuario = users.get_by_email(str(payload.email))

    # Mesma mensagem para conta inexistente, sem MFA e código errado: as três
    # situações não devem ser distinguíveis de fora.
    falha = ValidationError(
        "Não foi possível redefinir. Confira o e-mail e o código do "
        "autenticador."
    )
    if usuario is None or not usuario.is_active or not usuario.mfa_enabled:
        raise falha

    from ...domain.vaults.entities import EncryptedValue

    cifrado = EncryptedValue(
        ciphertext=usuario.mfa_secret_ciphertext or b"",
        nonce=usuario.mfa_secret_nonce or b"",
        wrapped_dek=usuario.mfa_secret_wrapped_dek or b"",
        key_id=usuario.mfa_key_id or "",
    )
    if not totp.verify(cifrado, payload.codigo):
        audit.append(
            _evento(
                usuario.id, usuario.email, AuditAction.PASSWORD_RESET_FAILED,
                f"usuarios/{usuario.email}", AuditOutcome.FAILURE,
                "Código do autenticador inválido na recuperação.",
            )
        )
        db.commit()
        raise falha

    usuario.password_hash = Argon2PasswordHasher().hash(payload.nova_senha)
    db.flush()
    audit.append(
        _evento(
            usuario.id, usuario.email, AuditAction.PASSWORD_RESET,
            f"usuarios/{usuario.email}",
            reason="Redefinida pelo próprio usuário, via autenticador.",
        )
    )
    return {"mensagem": "Senha redefinida. Faça login com a nova senha."}


@router.post(
    "/recuperar/pedido",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Pedir redefinição ao administrador",
)
def pedir_redefinicao(
    payload: PedirRedefinicaoRequest,
    pedidos: Annotated[PedidoRedefinicaoRepository, Depends(get_pedidos)],
    users: Annotated[UserRepository, Depends(get_users)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
) -> dict[str, str]:
    """Para quem não tem MFA. Registra o pedido; um administrador decide.

    Responde 202 mesmo para e-mail inexistente — criar o pedido só quando a
    conta existe tornaria a resposta um oráculo pelo tempo ou pelo efeito.
    """
    usuario = users.get_by_email(str(payload.email))
    if usuario is not None and usuario.is_active:
        pedido = PedidoDeRedefinicao(
            email=Email(str(payload.email)), motivo=payload.motivo
        )
        pedidos.add(pedido)
        audit.append(
            _evento(
                None, str(payload.email), AuditAction.PASSWORD_RESET_REQUESTED,
                f"usuarios/{payload.email}", reason=payload.motivo,
            )
        )
    return {
        "mensagem": (
            "Pedido registrado. Um administrador vai confirmar sua identidade "
            "e liberar a redefinição."
        )
    }


@router.get(
    "/recuperar/pedidos",
    response_model=list[PedidoResponse],
    summary="Pedidos de redefinição pendentes",
)
def listar_pedidos(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    pedidos: Annotated[PedidoRedefinicaoRepository, Depends(get_pedidos)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PedidoResponse]:
    _exigir_admin(current, policies, audit, db, "ver pedidos de redefinição")
    return [
        PedidoResponse(
            id=p.id,
            email=str(p.email),
            motivo=p.motivo,
            ip_address=p.ip_address,
            criado_em=p.criado_em,
        )
        for p in pedidos.pendentes()
    ]


@router.post(
    "/recuperar/pedidos/{pedido_id}/aprovar",
    response_model=ConviteResponse,
    summary="Aprovar e gerar o link de redefinição",
)
def aprovar_pedido(
    pedido_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    pedidos: Annotated[PedidoRedefinicaoRepository, Depends(get_pedidos)],
    convites: Annotated[ConviteRepository, Depends(get_convites)],
    policies: Annotated[PolicyRepository, Depends(get_policies)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> ConviteResponse:
    """Gera o link de redefinição, de prazo curto.

    Quem aprova confirmou a identidade por outro meio — ligação, presencial,
    o que a empresa usa. O sistema registra que a confirmação aconteceu e
    quem a fez; não tem como verificá-la, e fingir que tem seria pior.
    """
    _exigir_admin(current, policies, audit, db, "aprovar redefinição")
    pedido = pedidos.get(pedido_id)
    pedido.atender(current.email)
    pedidos.save(pedido)

    convite, token = criar_redefinicao(str(pedido.email), current.email)
    convites.add(convite)
    audit.append(
        _evento(
            current.id, current.email, AuditAction.PASSWORD_RESET_APPROVED,
            f"usuarios/{pedido.email}",
            reason=f"Link de redefinição gerado para {pedido.email}.",
            ip=current.ip_address,
        )
    )

    return ConviteResponse(
        id=convite.id,
        email=str(convite.email),
        tipo=str(convite.tipo),
        link=_link(token, convite.tipo),
        expira_em=convite.expira_em,
        aviso=(
            "Este link vale por 15 minutos e some desta tela ao recarregar. "
            "Entregue-o à pessoa agora, pelo canal que você usou para "
            "confirmar a identidade dela."
        ),
    )


@router.post("/recuperar/link", summary="Redefinir a senha pelo link")
def redefinir_com_link(
    payload: RedefinirComLinkRequest,
    convites: Annotated[ConviteRepository, Depends(get_convites)],
    users: Annotated[UserRepository, Depends(get_users)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Troca a senha usando o link gerado pelo administrador."""
    convite = convites.por_token(payload.token)
    if convite is None or convite.tipo is not TipoDeConvite.REDEFINICAO:
        raise ValidationError("Link inválido ou expirado.")

    convite.consumir()
    convites.save(convite)

    usuario = users.get_by_email(str(convite.email))
    if usuario is None:
        raise ValidationError("Link inválido ou expirado.")

    usuario.password_hash = Argon2PasswordHasher().hash(payload.nova_senha)
    db.flush()
    audit.append(
        _evento(
            usuario.id, usuario.email, AuditAction.PASSWORD_RESET,
            f"usuarios/{usuario.email}",
            reason=f"Redefinida por link aprovado por {convite.criado_por}.",
        )
    )
    return {"mensagem": "Senha redefinida. Faça login com a nova senha."}
