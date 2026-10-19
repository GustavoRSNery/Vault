"""Compartilhamento de segredo de Shamir, sobre GF(256).

Parte um segredo em `n` quinhões de modo que **quaisquer `k`** o reconstroem e
`k-1` não revelam nada — nem um bit. Essa última parte é o ponto: não é que
seja "difícil" reconstruir com menos que o limiar, é que todos os segredos
possíveis continuam igualmente prováveis. É sigilo perfeito, não dificuldade
computacional.

Por que isso vale a pena num cofre: desselar passa a exigir mais de uma pessoa.
Uma única pessoa com a senha certa (ou coagida, ou comprometida) não abre o
cofre sozinha.

## Como funciona

Para cada byte do segredo, sorteia-se um polinômio de grau `k-1` cujo termo
independente é esse byte. Os quinhões são pontos desse polinômio em x = 1..n.
Com `k` pontos, a interpolação de Lagrange recupera o polinômio e, portanto,
o termo independente. Com `k-1` pontos, resta um grau de liberdade: para
**qualquer** valor do segredo existe exatamente um polinômio compatível.

## Por que GF(256) e não aritmética comum

Em GF(256) cada byte é um elemento do corpo, toda operação é fechada (byte
entra, byte sai) e a divisão é exata. Com inteiros comuns haveria overflow,
frações e viés estatístico — e viés vaza informação, que é exatamente o que
o esquema promete não fazer.

x = 0 nunca é um quinhão: é onde mora o próprio segredo.
"""

from __future__ import annotations

import os

from .errors import ValidationError

# Tabelas de log/antilog de GF(256) com o polinômio 0x11B (o do AES).
# Multiplicar vira somar logaritmos, o que é mais rápido e — o que importa
# mais aqui — tem tempo previsível, sem ramificação dependente do dado.
_EXP = [0] * 512
_LOG = [0] * 256


def _montar_tabelas() -> None:
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        # x = x * 3 em GF(256): (x << 1) ^ x, reduzido pelo polinômio.
        x ^= (x << 1) ^ (0x11B if x & 0x80 else 0)
        x &= 0xFF
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_montar_tabelas()

LIMIAR_MINIMO = 2
QUINHOES_MAXIMO = 255  # x vai de 1 a 255; x = 0 é o segredo


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("divisão por zero em GF(256)")
    if a == 0:
        return 0
    return _EXP[_LOG[a] + 255 - _LOG[b]]


def _avaliar(coeficientes: list[int], x: int) -> int:
    """Avalia o polinômio em x por Horner. coeficientes[0] é o termo livre."""
    resultado = 0
    for coeficiente in reversed(coeficientes):
        resultado = _mul(resultado, x) ^ coeficiente
    return resultado


def dividir(segredo: bytes, *, limiar: int, quinhoes: int) -> list[bytes]:
    """Divide `segredo` em `quinhoes` partes; `limiar` delas o reconstroem.

    Cada quinhão devolvido é `bytes([x]) + valores`, com x em 1..quinhoes.
    O índice vai junto porque a interpolação precisa saber de qual ponto
    cada valor veio — guardá-lo separado só criaria chance de desencontro.
    """
    if not segredo:
        raise ValidationError("Não há segredo para dividir.")
    if limiar < LIMIAR_MINIMO:
        raise ValidationError("O limiar deve ser de ao menos 2 pessoas.")
    if quinhoes < limiar:
        raise ValidationError(
            "Não dá para exigir mais pessoas do que o número de quinhões: "
            "o cofre ficaria impossível de abrir."
        )
    if quinhoes > QUINHOES_MAXIMO:
        raise ValidationError(f"No máximo {QUINHOES_MAXIMO} quinhões.")

    saida = [bytearray([x]) for x in range(1, quinhoes + 1)]

    for byte in segredo:
        # Termo livre = o byte do segredo; os demais coeficientes, aleatórios.
        coeficientes = [byte] + list(os.urandom(limiar - 1))
        for indice, x in enumerate(range(1, quinhoes + 1)):
            saida[indice].append(_avaliar(coeficientes, x))

    return [bytes(q) for q in saida]


def combinar(quinhoes: list[bytes]) -> bytes:
    """Reconstrói o segredo a partir de `limiar` quinhões (ou mais).

    Não há como verificar se o resultado está certo: com quinhões errados a
    interpolação devolve bytes plausíveis em vez de falhar. Quem chama precisa
    validar o resultado por fora — aqui, tentando desembrulhar a DEK, que é
    autenticada e falha de verdade.
    """
    if len(quinhoes) < LIMIAR_MINIMO:
        raise ValidationError("São necessários ao menos 2 quinhões.")

    indices: list[int] = []
    corpos: list[bytes] = []
    for quinhao in quinhoes:
        if len(quinhao) < 2:
            raise ValidationError("Quinhão malformado.")
        indice, corpo = quinhao[0], quinhao[1:]
        if indice == 0:
            raise ValidationError("Índice 0 é inválido: é onde mora o segredo.")
        if indice in indices:
            raise ValidationError(
                "Dois quinhões com o mesmo índice. Um deles é cópia do outro, "
                "e cópias não somam para o quórum."
            )
        indices.append(indice)
        corpos.append(corpo)

    tamanho = len(corpos[0])
    if any(len(c) != tamanho for c in corpos):
        raise ValidationError("Os quinhões têm tamanhos diferentes.")

    segredo = bytearray()
    for posicao in range(tamanho):
        # Interpolação de Lagrange avaliada em x = 0.
        acumulado = 0
        for i, xi in enumerate(indices):
            numerador, denominador = 1, 1
            for j, xj in enumerate(indices):
                if i == j:
                    continue
                numerador = _mul(numerador, xj)
                denominador = _mul(denominador, xi ^ xj)
            acumulado ^= _mul(corpos[i][posicao], _div(numerador, denominador))
        segredo.append(acumulado)

    return bytes(segredo)
