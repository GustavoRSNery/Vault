"""Testes da selagem com quórum.

O que estes testes protegem:

- **Limiar 1 é recusado.** Selar com quórum de uma pessoa é teatro: quem sela
  desela sozinho, que é exatamente o que o mecanismo existe para impedir.
- **O token não é guardado**, só o hash. Um dump do banco não pode entregar
  o que abre o cofre.
- **Quinhões errados não abrem**, e Shamir sozinho não detecta isso —
  reconstrói bytes plausíveis. A verificação pelo hash é a que vale.
- **Portador repetido é recusado**: a mesma pessoa com dois quinhões reduz o
  quórum real sem ninguém perceber.
"""

from __future__ import annotations

import hashlib
import itertools

import pytest

from app.domain.shared.errors import ConflictError, ValidationError
from app.domain.vaults.quorum import (
    QUINHOES_MAXIMO,
    SeloComQuorum,
    desselar_com_quorum,
    selar_com_quorum,
)

PORTADORES = ["ana@exemplo.com.br", "bruno@exemplo.com.br", "carla@exemplo.com.br"]


class TestSelagem:
    def test_emite_um_quinhao_por_portador(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")

        assert len(quinhoes) == 3
        assert [q.portador for q in quinhoes] == PORTADORES
        assert selo.limiar == 2
        assert selo.total_quinhoes == 3

    def test_o_token_nao_fica_no_selo(self) -> None:
        """Só o hash. Um dump do banco não pode abrir o cofre."""
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")

        token = desselar_com_quorum(selo, [quinhoes[0].valor, quinhoes[1].valor])

        # O repr é o que apareceria num log ou traceback.
        assert token.hex() not in repr(selo)
        assert selo.token_hash == hashlib.sha256(token).hexdigest()
        # E o selo não tem nenhum campo guardando o token em claro.
        campos = [str(getattr(selo, f)) for f in selo.__slots__]
        assert all(token.hex() not in valor for valor in campos)

    def test_quinhao_mascara_o_valor_no_repr(self) -> None:
        """Um traceback não pode imprimir o quinhão."""
        _, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        assert quinhoes[0].valor not in repr(quinhoes[0])
        assert "***" in repr(quinhoes[0])

    def test_duas_selagens_dao_tokens_diferentes(self) -> None:
        a, _ = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        b, _ = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        assert a.token_hash != b.token_hash

    def test_limiar_de_um_e_recusado(self) -> None:
        """Quem sela desela sozinho — o mecanismo não protegeria de nada."""
        with pytest.raises(ValidationError, match="2 pessoas"):
            selar_com_quorum("v1", PORTADORES, limiar=1, selado_por="ana")

    def test_limiar_maior_que_portadores_e_recusado(self) -> None:
        with pytest.raises(ValidationError, match="impossível"):
            selar_com_quorum("v1", PORTADORES, limiar=4, selado_por="ana")

    def test_portador_repetido_e_recusado(self) -> None:
        """A mesma pessoa com dois quinhões reduz o quórum real."""
        with pytest.raises(ValidationError, match="repetido"):
            selar_com_quorum(
                "v1", ["ana@x.com", "ana@x.com", "bruno@x.com"],
                limiar=2, selado_por="ana",
            )

    def test_sem_portadores_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            selar_com_quorum("v1", [], limiar=2, selado_por="ana")

    def test_acima_do_maximo_de_quinhoes(self) -> None:
        """Cofre que não abre não é seguro: a cerimônia tem limite prático."""
        muitos = [f"pessoa{i}@exemplo.com.br" for i in range(QUINHOES_MAXIMO + 1)]
        with pytest.raises(ValidationError, match="impraticável"):
            selar_com_quorum("v1", muitos, limiar=2, selado_por="ana")


class TestDesselagem:
    def test_o_limiar_exato_abre(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        token = desselar_com_quorum(selo, [quinhoes[0].valor, quinhoes[1].valor])
        assert selo.confere(token)

    def test_qualquer_combinacao_do_limiar_abre(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        for par in itertools.combinations(quinhoes, 2):
            token = desselar_com_quorum(selo, [q.valor for q in par])
            assert selo.confere(token)

    def test_mais_que_o_limiar_tambem_abre(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        token = desselar_com_quorum(selo, [q.valor for q in quinhoes])
        assert selo.confere(token)

    def test_abaixo_do_limiar_e_recusado(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=3, selado_por="ana")
        with pytest.raises(ConflictError, match="3 quinhões"):
            desselar_com_quorum(selo, [quinhoes[0].valor, quinhoes[1].valor])

    def test_quinhoes_de_outra_selagem_nao_abrem(self) -> None:
        """O caso que Shamir sozinho NÃO detecta: ele reconstrói bytes
        plausíveis em vez de falhar. Quem pega é a conferência do hash."""
        selo, _ = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        _, outros = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")

        with pytest.raises(ConflictError, match="não abrem este cofre"):
            desselar_com_quorum(selo, [outros[0].valor, outros[1].valor])

    def test_mistura_de_selagens_nao_abre(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        _, outros = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")

        with pytest.raises(ConflictError):
            desselar_com_quorum(selo, [quinhoes[0].valor, outros[1].valor])

    def test_quinhao_adulterado_nao_abre(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        adulterado = quinhoes[0].valor[:-2] + ("00" if quinhoes[0].valor[-2:] != "00" else "ff")

        with pytest.raises(ConflictError):
            desselar_com_quorum(selo, [adulterado, quinhoes[1].valor])

    def test_quinhao_repetido_nao_completa_o_quorum(self) -> None:
        """Apresentar o mesmo duas vezes não substitui a segunda pessoa."""
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        with pytest.raises(ValidationError, match="mesmo índice"):
            desselar_com_quorum(selo, [quinhoes[0].valor, quinhoes[0].valor])

    def test_formato_invalido_e_recusado(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        with pytest.raises(ValidationError, match="formato"):
            desselar_com_quorum(selo, ["nao-e-hexadecimal", quinhoes[1].valor])

    def test_espacos_em_volta_sao_tolerados(self) -> None:
        """Quem cola de um e-mail traz espaço junto; recusar seria rudeza."""
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        token = desselar_com_quorum(
            selo, [f"  {quinhoes[0].valor} ", f"\n{quinhoes[1].valor}\t"]
        )
        assert selo.confere(token)

    def test_a_mensagem_de_erro_nao_aponta_o_quinhao_errado(self) -> None:
        """Dizer "o terceiro está errado" ajudaria quem tenta adivinhar."""
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        _, outros = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")

        with pytest.raises(ConflictError) as erro:
            desselar_com_quorum(selo, [quinhoes[0].valor, outros[1].valor])

        mensagem = str(erro.value)
        assert "1" not in mensagem.replace("Confira", "")  # sem índice culpado
        assert "quinhões" in mensagem


class TestConferenciaDoToken:
    def test_token_certo_confere(self) -> None:
        selo, quinhoes = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        token = desselar_com_quorum(selo, [quinhoes[0].valor, quinhoes[1].valor])
        assert selo.confere(token) is True

    def test_token_errado_nao_confere(self) -> None:
        selo, _ = selar_com_quorum("v1", PORTADORES, limiar=2, selado_por="ana")
        assert selo.confere(b"x" * 32) is False

    def test_hash_malformado_e_recusado_na_construcao(self) -> None:
        with pytest.raises(ValidationError, match="64 caracteres"):
            SeloComQuorum(
                vault_id="v1", limiar=2, total_quinhoes=3, token_hash="curto"
            )


class TestInvariantesDoSelo:
    """A entidade valida a si mesma, não só o caminho de criação.

    Importa porque o repositório reconstrói o selo ao ler do banco, sem passar
    por `selar_com_quorum`. Um registro adulterado no banco (limiar 1) voltaria
    como um selo que não protege nada — e a guarda aqui é a última linha.

    Descoberto por um mutante que sobreviveu: os testes só exercitavam a
    validação através de `selar_com_quorum`, onde o Shamir barra antes de o
    selo ser construído.
    """

    HASH = "a" * 64

    def test_limiar_um_e_recusado_na_entidade(self) -> None:
        with pytest.raises(ValidationError, match="2 pessoas"):
            SeloComQuorum(
                vault_id="v1", limiar=1, total_quinhoes=3, token_hash=self.HASH
            )

    def test_limiar_zero_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            SeloComQuorum(
                vault_id="v1", limiar=0, total_quinhoes=3, token_hash=self.HASH
            )

    def test_limiar_maior_que_total_e_recusado_na_entidade(self) -> None:
        with pytest.raises(ValidationError, match="impossível"):
            SeloComQuorum(
                vault_id="v1", limiar=5, total_quinhoes=3, token_hash=self.HASH
            )

    def test_acima_do_maximo_e_recusado_na_entidade(self) -> None:
        with pytest.raises(ValidationError, match="impraticável"):
            SeloComQuorum(
                vault_id="v1",
                limiar=2,
                total_quinhoes=QUINHOES_MAXIMO + 1,
                token_hash=self.HASH,
            )

    def test_configuracao_valida_e_aceita(self) -> None:
        selo = SeloComQuorum(
            vault_id="v1", limiar=2, total_quinhoes=3, token_hash=self.HASH
        )
        assert selo.limiar == 2
