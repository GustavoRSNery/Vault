"""Selagem com quórum: desselar exige várias pessoas.

Sem isto, selar é teatro — quem sela desela sozinho, e um administrador
comprometido (ou coagido) abre o cofre na mesma sessão. Com quórum, a
operação passa a exigir `k` de `n` pessoas.

## O que o quinhão protege

**Um token de desselagem**, sorteado na selagem, não a chave-mestra.

Partir a KEK seria a escolha óbvia e é a errada aqui, por duas razões: no KMS
a chave-mestra não existe neste processo para ser partida, e mesmo com chave
local a rotação de KEK invalidaria todos os quinhões já distribuídos — as
pessoas teriam de receber envelopes novos a cada rotação.

O token é independente da KEK: selar e rotacionar são operações que não se
atrapalham.

## Como a verificação funciona sem guardar segredo

Guarda-se apenas o **hash** do token. Quem apresenta `k` quinhões reconstrói o
token, o hash confere, o cofre abre. Quem apresenta menos reconstrói lixo, o
hash não confere, e o cofre continua fechado — sem que o sistema precise ter
o token em lugar nenhum.

É o mesmo motivo pelo qual senha se guarda como hash: um dump do banco não
entrega nada que abra o cofre.

## O que isto NÃO protege

Os segredos continuam cifrados pela KEK, como sempre. O quórum protege a
**operação de desselar**, não o dado. Quem tiver a KEK e acesso direto ao
banco lê os segredos sem passar por aqui — é o KMS que defende esse flanco,
e por isso os dois mecanismos se somam em vez de competir.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from datetime import datetime

from ..shared.errors import ConflictError, ValidationError
from ..shared.shamir import combinar, dividir
from ..shared.value_objects import new_id, utcnow

TOKEN_BYTES = 32
LIMIAR_MINIMO = 2
QUINHOES_MAXIMO = 16  # além disso vira cerimônia impraticável, não segurança


@dataclass(frozen=True, slots=True)
class QuinhaoEmitido:
    """Um quinhão, no único momento em que ele existe em claro.

    Entregue a uma pessoa e **descartado pelo sistema**: não é persistido em
    lugar nenhum. Se todos perderem os seus, o cofre não abre mais — e isso é
    a funcionalidade, não um defeito. Por isso a emissão avisa.
    """

    indice: int
    valor: str  # hexadecimal, para caber num e-mail ou num papel
    portador: str

    def __repr__(self) -> str:
        """Mascara o valor: um traceback não pode imprimir o quinhão."""
        return (
            f"QuinhaoEmitido(indice={self.indice!r}, "
            f"portador={self.portador!r}, valor='***')"
        )


@dataclass(slots=True)
class SeloComQuorum:
    """O selo de um cofre: quantas pessoas, e a prova do token.

    `token_hash` é o SHA-256 do token de desselagem. O token em si não é
    guardado — se fosse, selar não protegeria de quem lê o banco.
    """

    vault_id: str
    limiar: int
    total_quinhoes: int
    token_hash: str
    portadores: list[str] = field(default_factory=list)
    selado_por: str = ""
    selado_em: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.limiar < LIMIAR_MINIMO:
            raise ValidationError(
                "O quórum deve exigir ao menos 2 pessoas. Com 1, selar não "
                "protege de ninguém — quem sela desela sozinho."
            )
        if self.total_quinhoes < self.limiar:
            raise ValidationError(
                "Não dá para exigir mais pessoas do que o número de quinhões: "
                "o cofre ficaria impossível de abrir."
            )
        if self.total_quinhoes > QUINHOES_MAXIMO:
            raise ValidationError(
                f"No máximo {QUINHOES_MAXIMO} quinhões — além disso a cerimônia "
                "de abertura vira impraticável, e cofre que não abre não é seguro."
            )
        if len(self.token_hash) != 64:
            raise ValidationError("O hash do token deve ter 64 caracteres.")

    def confere(self, token: bytes) -> bool:
        """O token apresentado é o que selou este cofre?

        Comparação em tempo constante: `==` em hash vaza, por tempo, quantos
        caracteres iniciais acertaram, e isso permitiria construir o token byte
        a byte.
        """
        return hmac.compare_digest(
            hashlib.sha256(token).hexdigest(), self.token_hash
        )


def selar_com_quorum(
    vault_id: str,
    portadores: list[str],
    limiar: int,
    selado_por: str,
) -> tuple[SeloComQuorum, list[QuinhaoEmitido]]:
    """Sela o cofre e emite os quinhões.

    Devolve o selo (persistível) e os quinhões (entregues e esquecidos). O
    token em claro não sai desta função — nem para quem chama.
    """
    if not portadores:
        raise ValidationError("Informe quem receberá os quinhões.")
    if len(set(portadores)) != len(portadores):
        raise ValidationError(
            "Portador repetido: a mesma pessoa com dois quinhões reduz o "
            "quórum real sem que ninguém perceba."
        )

    token = os.urandom(TOKEN_BYTES)
    partes = dividir(token, limiar=limiar, quinhoes=len(portadores))

    selo = SeloComQuorum(
        vault_id=vault_id,
        limiar=limiar,
        total_quinhoes=len(portadores),
        token_hash=hashlib.sha256(token).hexdigest(),
        portadores=list(portadores),
        selado_por=selado_por,
    )
    emitidos = [
        QuinhaoEmitido(indice=parte[0], valor=parte.hex(), portador=portador)
        for parte, portador in zip(partes, portadores, strict=True)
    ]
    return selo, emitidos


def desselar_com_quorum(selo: SeloComQuorum, quinhoes_hex: list[str]) -> bytes:
    """Reconstrói o token a partir dos quinhões e confirma que é o certo.

    Levanta se o quórum não for atingido ou se os quinhões não produzirem o
    token que selou o cofre. A mensagem é a mesma nos dois casos de falha de
    reconstrução: dizer "o quinhão 3 está errado" ajudaria quem está tentando
    adivinhar quinhões.
    """
    if len(quinhoes_hex) < selo.limiar:
        raise ConflictError(
            f"São necessários {selo.limiar} quinhões; foram apresentados "
            f"{len(quinhoes_hex)}."
        )

    try:
        partes = [bytes.fromhex(q.strip()) for q in quinhoes_hex]
    except ValueError as erro:
        raise ValidationError("Quinhão em formato inválido.") from erro

    token = combinar(partes)

    # Shamir devolve bytes plausíveis para quinhões errados, em vez de falhar.
    # A validação de verdade é esta.
    if not selo.confere(token):
        raise ConflictError(
            "Os quinhões apresentados não abrem este cofre. Confira se todos "
            "pertencem à selagem atual."
        )
    return token
