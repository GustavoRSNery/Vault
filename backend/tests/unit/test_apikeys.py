"""Testes do domínio de chaves de API.

O que estes testes protegem:

- **Serviço e responsável são obrigatórios.** Chave sem serviço é chave que
  ninguém sabe o que quebra ao revogar; sem dono, é chave que ninguém revoga.
- **O formato determina o campo.** `X-API-Key` e `Bearer` não são
  intercambiáveis, e quem pega a chave precisa saber qual é.
- **A expiração é calculada, não marcada.** Depender de um job para refletir
  o vencimento faria o painel mentir enquanto o job não roda.
- **`como_usar` nunca contém o valor.**
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.apikeys.entities import (
    DIAS_DE_ALERTA,
    AmbienteDaChave,
    ChaveDeApi,
    EstadoDaChave,
    FormatoDaChave,
    expirar_vencidas,
)
from app.domain.shared.errors import ConflictError, ValidationError
from app.domain.shared.value_objects import Slug

AGORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _chave(**kwargs) -> ChaveDeApi:  # noqa: ANN003
    base = {
        "name": Slug("sefaz-nfe"),
        "display_name": "SEFAZ NF-e",
        "servico": "SEFAZ",
        "responsavel": "fiscal@exemplo.com.br",
    }
    return ChaveDeApi(**{**base, **kwargs})


class TestCadastro:
    def test_nasce_ativa_em_producao(self) -> None:
        c = _chave()
        assert c.esta_ativa is True
        assert c.ambiente is AmbienteDaChave.PRODUCAO

    def test_servico_e_obrigatorio(self) -> None:
        """Sem serviço, ninguém sabe o que quebra ao revogar."""
        with pytest.raises(ValidationError, match="serviço"):
            _chave(servico="  ")

    def test_responsavel_e_obrigatorio(self) -> None:
        with pytest.raises(ValidationError, match="responsável"):
            _chave(responsavel="")

    def test_nome_visivel_e_obrigatorio(self) -> None:
        with pytest.raises(ValidationError):
            _chave(display_name="   ")

    def test_caminho_de_politica(self) -> None:
        assert str(_chave().path) == "chaves-api/sefaz-nfe"

    def test_lugares_de_uso_normalizam(self) -> None:
        """Lugar repetido só polui o relatório."""
        c = _chave(usada_em=["rpa-fiscal", " rpa-fiscal ", "etl-notas", ""])
        assert c.usada_em == ["etl-notas", "rpa-fiscal"]


class TestFormato:
    def test_cabecalho_exige_o_nome_do_campo(self) -> None:
        """Sem ele, quem pegar a chave não sabe como enviá-la."""
        with pytest.raises(ValidationError, match="cabeçalho"):
            _chave(formato=FormatoDaChave.CABECALHO, nome_do_campo="")

    def test_query_exige_o_nome_do_campo(self) -> None:
        with pytest.raises(ValidationError):
            _chave(formato=FormatoDaChave.QUERY, nome_do_campo="  ")

    def test_bearer_nao_exige_campo(self) -> None:
        assert _chave(formato=FormatoDaChave.BEARER).nome_do_campo == ""

    def test_como_usar_monta_a_instrucao(self) -> None:
        assert _chave().como_usar() == "Authorization: Bearer <valor>"
        assert (
            _chave(
                formato=FormatoDaChave.CABECALHO, nome_do_campo="X-API-Key"
            ).como_usar()
            == "X-API-Key: <valor>"
        )
        assert (
            _chave(formato=FormatoDaChave.QUERY, nome_do_campo="api_key").como_usar()
            == "?api_key=<valor>"
        )

    def test_como_usar_nunca_traz_o_valor(self) -> None:
        """A instrução é pública; o valor exige revelar o segredo no cofre."""
        valor_real = "sk_live_abc123SEGREDO"
        for formato in FormatoDaChave:
            c = _chave(
                formato=formato,
                nome_do_campo="X-Key",
                # Mesmo que alguém tenha colocado o valor num campo errado,
                # a instrução não pode ecoá-lo.
                escopo=valor_real,
            )
            instrucao = c.como_usar()
            assert valor_real not in instrucao
            # E a instrução sempre aponta onde o valor entra, em vez de
            # deixar quem lê adivinhar.
            assert "<" in instrucao or "documentação" in instrucao


class TestValidade:
    def test_sem_validade_nao_vence(self) -> None:
        c = _chave()
        assert c.dias_para_vencer(AGORA) is None
        assert c.vencendo(now=AGORA) is False
        assert c.situacao(AGORA) is EstadoDaChave.ATIVA

    def test_dentro_do_prazo(self) -> None:
        c = _chave(expira_em=AGORA + timedelta(days=90))
        assert c.dias_para_vencer(AGORA) == 90
        assert c.vencendo(now=AGORA) is False

    def test_dentro_da_faixa_de_alerta(self) -> None:
        c = _chave(expira_em=AGORA + timedelta(days=DIAS_DE_ALERTA - 1))
        assert c.vencendo(now=AGORA) is True

    def test_expirada_e_calculada_nao_marcada(self) -> None:
        """Depender de job faria o painel mentir enquanto ele não roda."""
        c = _chave(expira_em=AGORA + timedelta(days=1))
        assert c.situacao(AGORA) is EstadoDaChave.ATIVA
        assert c.situacao(AGORA + timedelta(days=2)) is EstadoDaChave.EXPIRADA
        # E o campo persistido continua "ativa" até alguém persistir a mudança.
        assert c.estado is EstadoDaChave.ATIVA

    def test_revogada_vence_sobre_expirada(self) -> None:
        """Revogar é decisão; expirar é relógio. A decisão manda."""
        c = _chave(expira_em=AGORA + timedelta(days=1))
        c.revogar(AGORA)
        assert c.situacao(AGORA + timedelta(days=30)) is EstadoDaChave.REVOGADA

    def test_revogada_nao_tem_dias(self) -> None:
        c = _chave(expira_em=AGORA + timedelta(days=30))
        c.revogar(AGORA)
        assert c.dias_para_vencer(AGORA) is None

    def test_revogar_duas_vezes_e_conflito(self) -> None:
        c = _chave()
        c.revogar(AGORA)
        with pytest.raises(ConflictError):
            c.revogar(AGORA)

    def test_expirar_vencidas_so_mexe_nas_vencidas(self) -> None:
        viva = _chave(name=Slug("viva"), expira_em=AGORA + timedelta(days=10))
        vencida = _chave(name=Slug("vencida"), expira_em=AGORA - timedelta(days=1))
        sem_prazo = _chave(name=Slug("sem-prazo"))

        mudaram = expirar_vencidas([viva, vencida, sem_prazo], AGORA)
        assert mudaram == [vencida]
        assert vencida.estado is EstadoDaChave.EXPIRADA
        assert viva.estado is EstadoDaChave.ATIVA
        assert sem_prazo.estado is EstadoDaChave.ATIVA
