"""Convites e recuperação de senha, por link de uso único.

Os dois resolvem o mesmo problema — provar que alguém é quem diz ser, sem
sessão — e por isso compartilham a mecânica: um token aleatório, entregue
uma vez, que vale por pouco tempo e morre ao ser usado.

## Por que não depende de e-mail

E-mail é frágil (atrasa, cai em spam, exige servidor) e não é canal seguro.
Aqui o link é **gerado e exibido**: quem convida copia e entrega pelo canal
que quiser — WhatsApp, pessoalmente, pelo chat interno. Quando houver
servidor de e-mail, o mesmo link pode ser enviado por lá sem mudar nada
desta camada.

Para recuperação, há um caminho melhor ainda quando a pessoa tem MFA: provar
identidade pelo **código do autenticador**, sem link nenhum e sem envolver
outra pessoa. Quem não tem MFA cai no pedido ao administrador — e isso cria
um incentivo real para ativá-lo.

## Por que só o hash é guardado

Mesma razão de senha: um dump do banco não pode entregar um link que redefine
a senha de alguém. O token em claro existe uma vez, no retorno da criação.

## Por que o uso é terminal

Um link de redefinição que funciona duas vezes é um link que o atacante usa
depois da vítima. `consumir()` marca e recusa a segunda tentativa.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from ..shared.errors import ConflictError, ValidationError
from ..shared.value_objects import Email, new_id, utcnow

TOKEN_BYTES = 32

# Convite: prazo largo porque a pessoa pode estar de férias quando é criada.
CONVITE_DIAS_PADRAO = 7
CONVITE_DIAS_MAXIMO = 30

# Redefinição: prazo curto porque o link já está na mão de quem pediu, e um
# link de redefinição vivo é uma senha esperando para ser trocada por outro.
REDEFINICAO_MINUTOS = 15


class TipoDeConvite(StrEnum):
    NOVO_USUARIO = "novo_usuario"
    REDEFINICAO = "redefinicao"


class EstadoDoConvite(StrEnum):
    PENDENTE = "pendente"
    USADO = "usado"
    EXPIRADO = "expirado"
    CANCELADO = "cancelado"


def gerar_token() -> tuple[str, str]:
    """Devolve (token_em_claro, hash). O claro não volta a existir."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hashlib.sha256(token.encode()).hexdigest()


@dataclass(slots=True)
class Convite:
    """Um link de uso único: convite de usuário ou redefinição de senha."""

    email: Email
    tipo: TipoDeConvite
    token_hash: str
    expira_em: datetime
    criado_por: str = ""
    nome_sugerido: str = ""
    papeis: list[str] = field(default_factory=list)
    estado: EstadoDoConvite = EstadoDoConvite.PENDENTE
    usado_em: datetime | None = None
    criado_em: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if len(self.token_hash) != 64:
            raise ValidationError("O hash do token deve ter 64 caracteres.")
        if self.expira_em <= self.criado_em:
            raise ValidationError("O prazo do convite deve ser no futuro.")

    @property
    def esta_pendente(self) -> bool:
        return self.estado is EstadoDoConvite.PENDENTE

    def esta_valido(self, now: datetime | None = None) -> bool:
        return self.esta_pendente and (now or utcnow()) < self.expira_em

    def confere(self, token: str) -> bool:
        """Compara em tempo constante.

        `==` vazaria, por tempo, quantos caracteres iniciais acertaram — e
        isso permite construir o token byte a byte.
        """
        return hmac.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), self.token_hash
        )

    def consumir(self, now: datetime | None = None) -> None:
        """Marca o uso. Terminal: um link que funciona duas vezes é um link
        que o atacante usa depois da vítima."""
        agora = now or utcnow()
        if self.estado is EstadoDoConvite.USADO:
            raise ConflictError("Este link já foi usado.")
        if self.estado is EstadoDoConvite.CANCELADO:
            raise ConflictError("Este link foi cancelado.")
        if agora >= self.expira_em:
            self.estado = EstadoDoConvite.EXPIRADO
            raise ConflictError("Este link expirou. Peça um novo.")
        self.estado = EstadoDoConvite.USADO
        self.usado_em = agora

    def cancelar(self) -> None:
        """Invalida antes do prazo — para quando o convite foi mandado errado."""
        if not self.esta_pendente:
            raise ConflictError(f"Este convite já está {self.estado}.")
        self.estado = EstadoDoConvite.CANCELADO


def criar_convite(
    email: str,
    criado_por: str,
    *,
    nome_sugerido: str = "",
    papeis: list[str] | None = None,
    dias: int = CONVITE_DIAS_PADRAO,
    now: datetime | None = None,
) -> tuple[Convite, str]:
    """Cria um convite de novo usuário. Devolve (convite, token em claro)."""
    if dias < 1 or dias > CONVITE_DIAS_MAXIMO:
        raise ValidationError(
            f"O prazo do convite vai de 1 a {CONVITE_DIAS_MAXIMO} dias. Convite "
            "que dura meses é porta aberta que ninguém lembra de fechar."
        )
    agora = now or utcnow()
    token, digest = gerar_token()
    convite = Convite(
        email=Email(email),
        tipo=TipoDeConvite.NOVO_USUARIO,
        token_hash=digest,
        expira_em=agora + timedelta(days=dias),
        criado_por=criado_por,
        nome_sugerido=nome_sugerido,
        papeis=list(papeis or []),
        criado_em=agora,
    )
    return convite, token


def criar_redefinicao(
    email: str, criado_por: str, now: datetime | None = None
) -> tuple[Convite, str]:
    """Cria um link de redefinição de senha, de prazo curto."""
    agora = now or utcnow()
    token, digest = gerar_token()
    convite = Convite(
        email=Email(email),
        tipo=TipoDeConvite.REDEFINICAO,
        token_hash=digest,
        expira_em=agora + timedelta(minutes=REDEFINICAO_MINUTOS),
        criado_por=criado_por,
        criado_em=agora,
    )
    return convite, token


@dataclass(slots=True)
class PedidoDeRedefinicao:
    """Pedido de quem NÃO tem MFA e precisa da senha redefinida.

    Existe porque recuperação por TOTP não cobre quem nunca ativou o segundo
    fator — e deixar essa pessoa sem caminho na interface empurraria o
    problema para uma conversa por fora, sem rastro.

    O pedido não prova nada sozinho: é um administrador que confere a
    identidade por outro meio e aprova. O valor está em deixar o pedido e a
    aprovação registrados.
    """

    email: Email
    motivo: str = ""
    ip_address: str | None = None
    atendido: bool = False
    atendido_por: str = ""
    atendido_em: datetime | None = None
    criado_em: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def atender(self, por: str, now: datetime | None = None) -> None:
        if self.atendido:
            raise ConflictError("Este pedido já foi atendido.")
        self.atendido = True
        self.atendido_por = por
        self.atendido_em = now or utcnow()
