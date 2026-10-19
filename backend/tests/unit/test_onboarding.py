"""Testes de convites e recuperação de senha.

As invariantes:

- **O uso é terminal.** Um link que funciona duas vezes é um link que o
  atacante usa depois da vítima.
- **Só o hash é guardado.** Um dump do banco não pode entregar um link que
  redefine a senha de alguém.
- **Comparação em tempo constante.** `==` permitiria construir o token byte
  a byte pelo tempo de resposta.
- **Prazos diferentes por natureza.** Convite espera alguém voltar de férias;
  redefinição já está na mão de quem pediu.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.onboarding.entities import (
    CONVITE_DIAS_MAXIMO,
    REDEFINICAO_MINUTOS,
    Convite,
    EstadoDoConvite,
    PedidoDeRedefinicao,
    TipoDeConvite,
    criar_convite,
    criar_redefinicao,
    gerar_token,
)
from app.domain.shared.errors import ConflictError, ValidationError

AGORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


class TestCriacao:
    def test_convite_nasce_pendente_com_prazo_largo(self) -> None:
        convite, token = criar_convite(
            "nova@exemplo.com.br", "admin@exemplo.com.br", now=AGORA
        )
        assert convite.estado is EstadoDoConvite.PENDENTE
        assert convite.tipo is TipoDeConvite.NOVO_USUARIO
        assert convite.expira_em == AGORA + timedelta(days=7)
        assert len(token) > 30

    def test_redefinicao_tem_prazo_curto(self) -> None:
        """O link já está na mão de quem pediu: vivo por muito tempo, é uma
        senha esperando para ser trocada por outro."""
        convite, _ = criar_redefinicao("ana@exemplo.com.br", "sistema", now=AGORA)
        assert convite.expira_em == AGORA + timedelta(minutes=REDEFINICAO_MINUTOS)
        assert convite.tipo is TipoDeConvite.REDEFINICAO

    def test_prazo_absurdo_e_recusado(self) -> None:
        """Convite que dura meses é porta aberta que ninguém lembra de fechar."""
        with pytest.raises(ValidationError, match="porta aberta"):
            criar_convite("x@y.com.br", "admin", dias=CONVITE_DIAS_MAXIMO + 1)

    def test_prazo_zero_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            criar_convite("x@y.com.br", "admin", dias=0)

    def test_email_invalido_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            criar_convite("nao-e-email", "admin")

    def test_dois_convites_tem_tokens_diferentes(self) -> None:
        _, a = criar_convite("a@x.com.br", "admin")
        _, b = criar_convite("a@x.com.br", "admin")
        assert a != b

    def test_token_em_claro_nao_fica_no_convite(self) -> None:
        """Um dump do banco não pode entregar o link."""
        convite, token = criar_convite("a@x.com.br", "admin")
        assert token not in repr(convite)
        assert token != convite.token_hash


class TestUso:
    def test_token_certo_confere(self) -> None:
        convite, token = criar_convite("a@x.com.br", "admin", now=AGORA)
        assert convite.confere(token) is True
        assert convite.confere(token + "x") is False
        assert convite.confere("") is False

    def test_consumir_e_terminal(self) -> None:
        """Um link que funciona duas vezes é um link que o atacante usa
        depois da vítima."""
        convite, _ = criar_convite("a@x.com.br", "admin", now=AGORA)
        convite.consumir(now=AGORA)
        assert convite.estado is EstadoDoConvite.USADO

        with pytest.raises(ConflictError, match="já foi usado"):
            convite.consumir(now=AGORA)

    def test_expirado_nao_e_consumido(self) -> None:
        convite, _ = criar_redefinicao("a@x.com.br", "sistema", now=AGORA)
        tarde = AGORA + timedelta(minutes=REDEFINICAO_MINUTOS + 1)

        with pytest.raises(ConflictError, match="expirou"):
            convite.consumir(now=tarde)
        assert convite.estado is EstadoDoConvite.EXPIRADO

    def test_valido_dentro_do_prazo(self) -> None:
        convite, _ = criar_redefinicao("a@x.com.br", "sistema", now=AGORA)
        assert convite.esta_valido(AGORA + timedelta(minutes=10)) is True
        assert convite.esta_valido(AGORA + timedelta(minutes=20)) is False

    def test_cancelado_nao_e_consumido(self) -> None:
        """Para quando o convite foi mandado para o endereço errado."""
        convite, _ = criar_convite("errado@x.com.br", "admin", now=AGORA)
        convite.cancelar()

        with pytest.raises(ConflictError, match="cancelado"):
            convite.consumir(now=AGORA)

    def test_cancelar_usado_e_conflito(self) -> None:
        convite, _ = criar_convite("a@x.com.br", "admin", now=AGORA)
        convite.consumir(now=AGORA)
        with pytest.raises(ConflictError):
            convite.cancelar()

    def test_hash_malformado_e_recusado(self) -> None:
        with pytest.raises(ValidationError, match="64 caracteres"):
            Convite(
                email=__import__(
                    "app.domain.shared.value_objects", fromlist=["Email"]
                ).Email("a@x.com.br"),
                tipo=TipoDeConvite.NOVO_USUARIO,
                token_hash="curto",
                expira_em=AGORA + timedelta(days=1),
                criado_em=AGORA,
            )

    def test_prazo_no_passado_e_recusado(self) -> None:
        _, digest = gerar_token()
        from app.domain.shared.value_objects import Email

        with pytest.raises(ValidationError, match="futuro"):
            Convite(
                email=Email("a@x.com.br"),
                tipo=TipoDeConvite.NOVO_USUARIO,
                token_hash=digest,
                expira_em=AGORA - timedelta(minutes=1),
                criado_em=AGORA,
            )


class TestPedidoDeRedefinicao:
    def test_nasce_nao_atendido(self) -> None:
        pedido = PedidoDeRedefinicao(
            email=__import__(
                "app.domain.shared.value_objects", fromlist=["Email"]
            ).Email("ana@x.com.br"),
            motivo="Perdi o celular",
        )
        assert pedido.atendido is False

    def test_atender_registra_quem(self) -> None:
        from app.domain.shared.value_objects import Email

        pedido = PedidoDeRedefinicao(email=Email("ana@x.com.br"))
        pedido.atender("admin@x.com.br", now=AGORA)

        assert pedido.atendido is True
        assert pedido.atendido_por == "admin@x.com.br"
        assert pedido.atendido_em == AGORA

    def test_atender_duas_vezes_e_conflito(self) -> None:
        from app.domain.shared.value_objects import Email

        pedido = PedidoDeRedefinicao(email=Email("ana@x.com.br"))
        pedido.atender("admin", now=AGORA)
        with pytest.raises(ConflictError):
            pedido.atender("outro", now=AGORA)
