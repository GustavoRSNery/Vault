"""Testes do compartilhamento de segredo de Shamir.

O teste que justifica o arquivo é `test_abaixo_do_limiar_nao_revela_nada`:
a promessa do esquema não é que reconstruir com menos que o limiar seja
*difícil*, é que seja *impossível* — todos os segredos continuam igualmente
prováveis. Um teste que só verificasse "não reconstrói" passaria com uma
implementação que vaza metade dos bytes.
"""

from __future__ import annotations

import itertools

import pytest

from app.domain.shared.errors import ValidationError
from app.domain.shared.shamir import (
    LIMIAR_MINIMO,
    QUINHOES_MAXIMO,
    combinar,
    dividir,
)

SEGREDO = b"chave-mestra-de-32-bytes-exatos!"


class TestReconstrucao:
    def test_o_limiar_exato_reconstroi(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=3, quinhoes=5)
        assert combinar(quinhoes[:3]) == SEGREDO

    def test_qualquer_combinacao_do_limiar_serve(self) -> None:
        """"Quaisquer k" é literal: não há quinhões privilegiados."""
        quinhoes = dividir(SEGREDO, limiar=3, quinhoes=5)
        for escolhidos in itertools.combinations(quinhoes, 3):
            assert combinar(list(escolhidos)) == SEGREDO

    def test_mais_que_o_limiar_tambem_reconstroi(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=3, quinhoes=5)
        assert combinar(quinhoes) == SEGREDO
        assert combinar(quinhoes[:4]) == SEGREDO

    def test_ordem_dos_quinhoes_nao_importa(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=3, quinhoes=5)
        assert combinar(list(reversed(quinhoes[:3]))) == SEGREDO

    def test_limiar_de_dois(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=2, quinhoes=2)
        assert combinar(quinhoes) == SEGREDO

    def test_todos_precisam_estar_presentes_quando_k_igual_n(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=4, quinhoes=4)
        assert combinar(quinhoes) == SEGREDO

    def test_segredo_de_um_byte(self) -> None:
        assert combinar(dividir(b"\x00", limiar=2, quinhoes=3)[:2]) == b"\x00"

    def test_segredo_com_bytes_repetidos_e_nulos(self) -> None:
        """Byte 0 é o caso que uma implementação ingênua erra."""
        segredo = bytes(16) + b"\xff" * 16
        quinhoes = dividir(segredo, limiar=3, quinhoes=5)
        assert combinar(quinhoes[:3]) == segredo

    def test_percorre_todos_os_valores_de_byte(self) -> None:
        segredo = bytes(range(256))
        quinhoes = dividir(segredo, limiar=3, quinhoes=5)
        assert combinar(quinhoes[:3]) == segredo

    def test_quinhao_carrega_o_proprio_indice(self) -> None:
        """Guardar o índice separado criaria chance de desencontro."""
        quinhoes = dividir(SEGREDO, limiar=2, quinhoes=3)
        assert [q[0] for q in quinhoes] == [1, 2, 3]
        assert all(len(q) == len(SEGREDO) + 1 for q in quinhoes)


class TestSigilo:
    def test_abaixo_do_limiar_nao_revela_nada(self) -> None:
        """A promessa central do esquema.

        Com k-1 quinhões, para QUALQUER segredo candidato existe um conjunto
        de coeficientes compatível. Testamos a consequência observável: o
        resultado de combinar k-1 quinhões não tem relação com o segredo, e
        varia conforme o subconjunto — porque é um ponto arbitrário de um
        polinômio ainda indeterminado.
        """
        quinhoes = dividir(SEGREDO, limiar=3, quinhoes=5)

        resultados = {
            combinar(list(par)) for par in itertools.combinations(quinhoes, 2)
        }
        # Nenhum par reconstrói o segredo...
        assert SEGREDO not in resultados
        # ...e pares diferentes dão resultados diferentes, o que mostra que
        # não há convergência para nada: o grau de liberdade continua lá.
        assert len(resultados) > 1

    def test_nenhum_quinhao_contem_o_segredo(self) -> None:
        for limiar in (2, 3, 5):
            for quinhao in dividir(SEGREDO, limiar=limiar, quinhoes=5):
                assert SEGREDO not in quinhao
                # Nem um pedaço reconhecível dele.
                assert b"chave-mestra" not in quinhao

    def test_dividir_duas_vezes_da_quinhoes_diferentes(self) -> None:
        """Os coeficientes são sorteados: dois conjuntos nunca coincidem."""
        a = dividir(SEGREDO, limiar=3, quinhoes=5)
        b = dividir(SEGREDO, limiar=3, quinhoes=5)
        assert a != b
        # E ainda assim ambos reconstroem o mesmo segredo.
        assert combinar(a[:3]) == combinar(b[:3]) == SEGREDO

    def test_quinhoes_de_divisoes_distintas_nao_se_misturam(self) -> None:
        """Misturar conjuntos produz lixo, não o segredo — e não dá erro.

        É por isso que quem chama precisa validar o resultado por fora.
        """
        a = dividir(SEGREDO, limiar=3, quinhoes=5)
        b = dividir(SEGREDO, limiar=3, quinhoes=5)
        misturado = [a[0], a[1], b[2]]
        assert combinar(misturado) != SEGREDO


class TestValidacao:
    def test_limiar_maior_que_quinhoes_e_recusado(self) -> None:
        """O cofre ficaria impossível de abrir."""
        with pytest.raises(ValidationError, match="impossível"):
            dividir(SEGREDO, limiar=4, quinhoes=3)

    def test_limiar_de_um_e_recusado(self) -> None:
        """Limiar 1 é não ter quórum nenhum — e esconde isso do usuário."""
        with pytest.raises(ValidationError):
            dividir(SEGREDO, limiar=1, quinhoes=3)

    def test_segredo_vazio_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            dividir(b"", limiar=2, quinhoes=3)

    def test_acima_do_maximo_de_quinhoes(self) -> None:
        with pytest.raises(ValidationError):
            dividir(SEGREDO, limiar=2, quinhoes=QUINHOES_MAXIMO + 1)

    def test_poucos_quinhoes_para_combinar(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=3, quinhoes=5)
        with pytest.raises(ValidationError):
            combinar(quinhoes[:1])

    def test_quinhao_duplicado_nao_soma_para_o_quorum(self) -> None:
        """Entregar o mesmo quinhão duas vezes não substitui uma segunda
        pessoa — e passar em silêncio seria furar o quórum."""
        quinhoes = dividir(SEGREDO, limiar=3, quinhoes=5)
        with pytest.raises(ValidationError, match="mesmo índice"):
            combinar([quinhoes[0], quinhoes[0], quinhoes[1]])

    def test_indice_zero_e_recusado(self) -> None:
        """x = 0 é onde mora o segredo; aceitá-lo entregaria tudo."""
        quinhoes = dividir(SEGREDO, limiar=2, quinhoes=3)
        forjado = bytes([0]) + quinhoes[0][1:]
        with pytest.raises(ValidationError, match="Índice 0"):
            combinar([forjado, quinhoes[1]])

    def test_tamanhos_diferentes_sao_recusados(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=2, quinhoes=3)
        with pytest.raises(ValidationError, match="tamanhos"):
            combinar([quinhoes[0], quinhoes[1][:-5]])

    def test_quinhao_sem_corpo_e_recusado(self) -> None:
        quinhoes = dividir(SEGREDO, limiar=2, quinhoes=3)
        with pytest.raises(ValidationError, match="malformado"):
            combinar([bytes([1]), quinhoes[1]])

    def test_limiar_minimo_e_dois(self) -> None:
        assert LIMIAR_MINIMO == 2


def _mul_referencia(a: int, b: int) -> int:
    """Multiplicação russa em GF(2^8), polinômio 0x11B, sem tabelas.

    Implementação deliberadamente diferente da de produção (que usa tabelas
    de log): conferir uma contra a outra pega o erro que um teste de ida e
    volta não pegaria, porque dividir/combinar continuam coerentes entre si
    mesmo com a aritmética errada.
    """
    resultado = 0
    while b:
        if b & 1:
            resultado ^= a
        carry = a & 0x80
        a = (a << 1) & 0xFF
        if carry:
            a ^= 0x1B
        b >>= 1
    return resultado


class TestAritmeticaDoCorpo:
    def test_multiplicacao_confere_com_a_referencia(self) -> None:
        """Todos os 65.536 pares."""
        from app.domain.shared.shamir import _mul

        divergentes = [
            (a, b)
            for a in range(256)
            for b in range(256)
            if _mul(a, b) != _mul_referencia(a, b)
        ]
        assert divergentes == []

    def test_divisao_e_a_inversa_da_multiplicacao(self) -> None:
        from app.domain.shared.shamir import _div, _mul

        for a in range(0, 256, 5):
            for b in range(1, 256, 7):
                assert _div(_mul(a, b), b) == a

    def test_distributividade_sobre_xor(self) -> None:
        """A soma do corpo é XOR; sem distributividade a interpolação erra."""
        from app.domain.shared.shamir import _mul

        for a in range(1, 256, 11):
            for b in range(1, 256, 13):
                for c in range(1, 256, 17):
                    assert _mul(a, b ^ c) == (_mul(a, b) ^ _mul(a, c))

    def test_divisao_por_zero_levanta(self) -> None:
        from app.domain.shared.shamir import _div

        with pytest.raises(ZeroDivisionError):
            _div(5, 0)
