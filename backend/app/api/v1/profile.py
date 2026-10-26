"""Rotas do próprio perfil.

Separadas de `admin.py` de propósito: lá a permissão é "administrar outras
pessoas", aqui é "sou eu mesmo". Juntá-las produziria rota que decide o
alvo pelo corpo do pedido, e o primeiro bug nessa decisão é escalada de
privilégio — alguém editando outra conta pela rota de perfil.

Por isso nenhuma rota deste módulo aceita id de usuário: o alvo é sempre
`current.id`, vindo do token. Não há parâmetro para errar.

## O que exige a senha atual, e por quê

Trocar senha e trocar e-mail exigem a senha atual. O motivo não é burocracia:
um token de acesso roubado — de um XSS, de um laptop aberto, de um histórico
de terminal — permitiria ao atacante trocar a senha e o e-mail e **tomar a
conta por completo**, deixando a pessoa de fora do próprio cofre. Exigir a
senha que só a pessoa sabe transforma roubo de token em acesso temporário em
vez de perda definitiva.

Nome, apelido e foto não exigem: são cosméticos, e o pior que um token
roubado faz com eles é vandalismo visível e reversível.
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import AuthenticationError, ConflictError, ValidationError
from ...infrastructure.crypto.passwords import Argon2PasswordHasher
from ...infrastructure.db.models import UserModel
from ...infrastructure.db.repositories import AuditRepository
from ..deps import CurrentUser, get_audit, get_current_user, get_db, get_hasher

router = APIRouter(prefix="/perfil", tags=["Perfil"])

# Imagens aceitas. Lista fechada: SVG fica de fora de propósito — ele carrega
# script, e uma foto de perfil que executa JavaScript na tela de quem olha é
# XSS armazenado com o rosto de alguém em cima.
TIPOS_DE_IMAGEM = ("image/png", "image/jpeg", "image/webp")

# 512 KB depois de decodificar. A foto vai no banco e viaja em toda resposta
# de perfil; megabytes aqui pesariam em cada carregamento de tela.
FOTO_MAXIMA_BYTES = 512 * 1024


class PerfilResponse(BaseModel):
    id: str
    email: str
    full_name: str
    apelido: str
    foto: str
    mfa_enabled: bool

    @property
    def tratamento(self) -> str:
        return self.apelido or self.full_name


class AtualizarPerfilRequest(BaseModel):
    """Dados cosméticos: não exigem senha.

    `None` significa "não mexer", e string vazia significa "limpar" — a
    distinção importa para o apelido e a foto, que são apagáveis. Sem ela,
    não haveria como remover uma foto.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    apelido: str | None = Field(default=None, max_length=60)
    foto: str | None = Field(default=None, max_length=1_200_000)


class TrocarEmailRequest(BaseModel):
    novo_email: EmailStr
    senha_atual: str = Field(min_length=1)


class TrocarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=1)
    nova_senha: str = Field(min_length=12, max_length=200)


def _resposta(user: UserModel) -> PerfilResponse:
    return PerfilResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        apelido=user.apelido or "",
        foto=user.foto or "",
        mfa_enabled=user.mfa_enabled,
    )


def _evento(
    current: CurrentUser,
    action: AuditAction,
    reason: str,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
) -> AuditEvent:
    return AuditEvent(
        action=action,
        actor_id=current.id,
        actor_label=current.email,
        target_path=f"perfil/{current.email}",
        outcome=outcome,
        reason=reason,
        ip_address=current.ip_address,
        user_agent=current.user_agent,
    )


def validar_foto(dado: str) -> str:
    """Valida a foto como data URI de imagem, devolvendo-a normalizada.

    String vazia passa: é como se apaga a foto.

    **Por que validar aqui e não confiar no front.** O front compõe o data
    URI a partir do arquivo escolhido, mas a rota aceita qualquer texto de
    quem chamar a API direto. Sem esta checagem, `foto` seria um campo de
    texto livre de 1 MB no meio do perfil — e o que fosse guardado ali
    voltaria para dentro de um atributo `src` na tela de todos.
    """
    if not dado:
        return ""
    if not dado.startswith("data:"):
        raise ValidationError(
            "A foto precisa ser enviada como data URI (data:image/png;base64,…)."
        )
    cabecalho, _, corpo = dado.partition(",")
    if not corpo:
        raise ValidationError("A foto está vazia.")
    if ";base64" not in cabecalho:
        raise ValidationError("A foto precisa estar em base64.")

    tipo = cabecalho[5:].split(";")[0]
    if tipo not in TIPOS_DE_IMAGEM:
        permitidos = ", ".join(TIPOS_DE_IMAGEM)
        raise ValidationError(
            f"Formato {tipo!r} não é aceito para foto. Use: {permitidos}. "
            "SVG não entra porque pode carregar script."
        )

    try:
        bruto = base64.b64decode(corpo, validate=True)
    except (binascii.Error, ValueError) as erro:
        raise ValidationError("A foto não está em base64 válido.") from erro

    if len(bruto) > FOTO_MAXIMA_BYTES:
        kb = len(bruto) // 1024
        raise ValidationError(
            f"A foto tem {kb} KB e o limite é {FOTO_MAXIMA_BYTES // 1024} KB. "
            "Reduza a imagem antes de enviar."
        )
    if not _parece_imagem(bruto, tipo):
        raise ValidationError(
            "O conteúdo não parece ser a imagem que o formato declara. "
            "Reenvie o arquivo original."
        )
    return dado


def _parece_imagem(bruto: bytes, tipo: str) -> bool:
    """Confere a assinatura do arquivo contra o tipo declarado.

    O cabeçalho do data URI é escrito por quem chama: dizer `image/png` e
    mandar outra coisa é trivial. Conferir os primeiros bytes impede que o
    campo se torne um lugar para guardar conteúdo arbitrário com rótulo de
    imagem.
    """
    if tipo == "image/png":
        return bruto.startswith(b"\x89PNG\r\n\x1a\n")
    if tipo == "image/jpeg":
        return bruto.startswith(b"\xff\xd8\xff")
    if tipo == "image/webp":
        return bruto[:4] == b"RIFF" and bruto[8:12] == b"WEBP"
    return False


@router.get("", response_model=PerfilResponse, summary="Meu perfil")
def meu_perfil(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PerfilResponse:
    user = db.get(UserModel, current.id)
    if user is None:  # pragma: no cover — get_current_user já garantiu
        raise AuthenticationError("Credenciais inválidas.")
    return _resposta(user)


@router.put("", response_model=PerfilResponse, summary="Editar meu perfil")
def editar_perfil(
    payload: AtualizarPerfilRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> PerfilResponse:
    """Nome, apelido e foto. Sem senha: são dados cosméticos.

    A trilha guarda **o que mudou**, com o valor anterior. "Perfil alterado"
    sozinho não responde a pergunta que se faz depois — qual era o nome antes.
    """
    user = db.get(UserModel, current.id)
    if user is None:  # pragma: no cover
        raise AuthenticationError("Credenciais inválidas.")

    mudancas: list[str] = []

    if payload.full_name is not None:
        novo = payload.full_name.strip()
        if not novo:
            raise ValidationError(
                "O nome não pode ficar em branco: ele identifica você na "
                "trilha de auditoria e nas sessões."
            )
        if novo != user.full_name:
            mudancas.append(f"nome: {user.full_name!r} → {novo!r}")
            user.full_name = novo

    if payload.apelido is not None:
        novo_apelido = payload.apelido.strip()
        if novo_apelido != (user.apelido or ""):
            anterior = user.apelido or "—"
            mudancas.append(f"apelido: {anterior!r} → {novo_apelido or '—'!r}")
            user.apelido = novo_apelido

    if payload.foto is not None:
        foto = validar_foto(payload.foto.strip())
        if foto != (user.foto or ""):
            # O conteúdo da foto não vai para a trilha: são centenas de KB de
            # base64 por evento, e o que importa auditar é que mudou.
            mudancas.append("foto trocada" if foto else "foto removida")
            user.foto = foto

    if mudancas:
        db.flush()
        audit.append(
            _evento(current, AuditAction.PROFILE_UPDATED, "; ".join(mudancas))
        )
    return _resposta(user)


@router.put("/email", response_model=PerfilResponse, summary="Trocar meu e-mail")
def trocar_email(
    payload: TrocarEmailRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_hasher)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> PerfilResponse:
    """Troca o e-mail de login, exigindo a senha atual.

    **O e-mail antigo fica registrado na trilha.** Ele é o rótulo do ator em
    todos os eventos passados: sem o registro da troca, a trilha de ontem
    aponta para um endereço que não existe mais e ninguém consegue ligar as
    duas pontas.
    """
    user = db.get(UserModel, current.id)
    if user is None:  # pragma: no cover
        raise AuthenticationError("Credenciais inválidas.")

    if not hasher.verify(payload.senha_atual, user.password_hash):
        audit.append(
            _evento(
                current,
                AuditAction.PROFILE_EMAIL_CHANGED,
                "senha atual incorreta",
                outcome=AuditOutcome.FAILURE,
            )
        )
        # Commit antes de propagar: sem isto o rollback apaga o registro da
        # tentativa, e tentativa de tomar a conta sem rastro é exatamente o
        # que interessa a quem está sondando.
        db.commit()
        raise AuthenticationError(
            "Senha atual incorreta. Trocar o e-mail muda como você entra no "
            "sistema, por isso pedimos a senha."
        )

    novo = str(payload.novo_email).strip().lower()
    if novo == user.email.lower():
        return _resposta(user)

    ja_existe = db.query(UserModel.id).filter(UserModel.email == novo).first()
    if ja_existe is not None:
        raise ConflictError(f"O e-mail {novo} já pertence a outra conta.")

    anterior = user.email
    user.email = novo
    db.flush()
    audit.append(
        _evento(
            current,
            AuditAction.PROFILE_EMAIL_CHANGED,
            f"de {anterior} para {novo}",
        )
    )
    return _resposta(user)


@router.put("/senha", status_code=204, summary="Trocar minha senha")
def trocar_senha(
    payload: TrocarSenhaRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    hasher: Annotated[Argon2PasswordHasher, Depends(get_hasher)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Troca a própria senha, exigindo a atual.

    A senha nova **não** aparece na trilha, nem seu tamanho: o evento registra
    que houve troca, com quem e quando. Registrar qualquer coisa do valor
    daria ao leitor da trilha uma vantagem que ele não deve ter.
    """
    user = db.get(UserModel, current.id)
    if user is None:  # pragma: no cover
        raise AuthenticationError("Credenciais inválidas.")

    if not hasher.verify(payload.senha_atual, user.password_hash):
        audit.append(
            _evento(
                current,
                AuditAction.PROFILE_PASSWORD_CHANGED,
                "senha atual incorreta",
                outcome=AuditOutcome.FAILURE,
            )
        )
        # Ver o comentário em `trocar_email`: sem o commit, o rollback apaga
        # a tentativa e a sondagem fica invisível.
        db.commit()
        raise AuthenticationError("Senha atual incorreta.")

    if payload.nova_senha == payload.senha_atual:
        raise ValidationError(
            "A senha nova é igual à atual. Trocar por ela mesma dá a "
            "impressão de ter rotacionado a senha sem ter rotacionado nada."
        )

    user.password_hash = hasher.hash(payload.nova_senha)
    db.flush()
    audit.append(_evento(current, AuditAction.PROFILE_PASSWORD_CHANGED, "troca pelo perfil"))
