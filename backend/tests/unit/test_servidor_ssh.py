"""Testes do servidor SSH de sessões.

`separar_host_e_porta` tem testes próprios porque a falta dela foi um bug
real: `asyncssh.connect("servidor:2222")` não reclama — trata tudo como nome
de host, tenta a porta 22 e falha com "não foi possível conectar". A mensagem
manda investigar rede e firewall quando a causa era a porta ignorada.
"""

from __future__ import annotations

import pytest

from app.domain.shared.errors import ValidationError
from app.infrastructure.sessions.servidor import (
    PORTA_SSH_PADRAO,
    Credenciais,
    separar_host_e_porta,
)


class TestSepararHostEPorta:
    def test_sem_porta_usa_a_padrao(self) -> None:
        assert separar_host_e_porta("servidor-01") == ("servidor-01", 22)

    def test_porta_explicita(self) -> None:
        """O bug: isto devolvia ('servidor-01:2222', 22) antes."""
        assert separar_host_e_porta("servidor-01:2222") == ("servidor-01", 2222)

    def test_fqdn_com_porta(self) -> None:
        assert separar_host_e_porta("srv.exemplo.com.br:2200") == (
            "srv.exemplo.com.br",
            2200,
        )

    def test_ipv4_com_porta(self) -> None:
        assert separar_host_e_porta("10.0.0.5:22") == ("10.0.0.5", 22)

    def test_espacos_em_volta_sao_ignorados(self) -> None:
        assert separar_host_e_porta("  servidor-01:2222  ") == ("servidor-01", 2222)

    def test_ipv6_entre_colchetes_com_porta(self) -> None:
        assert separar_host_e_porta("[::1]:2222") == ("::1", 2222)

    def test_ipv6_entre_colchetes_sem_porta(self) -> None:
        assert separar_host_e_porta("[fe80::1]") == ("fe80::1", PORTA_SSH_PADRAO)

    def test_ipv6_sem_colchetes_e_tratado_como_host(self) -> None:
        """`::1:2222` é ambíguo: pode ser endereço que termina em :2222.

        Sem colchetes não há como separar, então o endereço inteiro é o host
        e a porta é a padrão — em vez de arrancar um pedaço do endereço e
        conectar no lugar errado.
        """
        assert separar_host_e_porta("fe80::1") == ("fe80::1", PORTA_SSH_PADRAO)

    def test_porta_nao_numerica_levanta(self) -> None:
        """Melhor recusar que conectar na 22 silenciosamente."""
        with pytest.raises(ValidationError, match="porta inválida"):
            separar_host_e_porta("servidor-01:ssh")

    def test_porta_zero_levanta(self) -> None:
        with pytest.raises(ValidationError, match="fora da faixa"):
            separar_host_e_porta("servidor-01:0")

    def test_porta_acima_do_maximo_levanta(self) -> None:
        with pytest.raises(ValidationError, match="fora da faixa"):
            separar_host_e_porta("servidor-01:70000")

    def test_porta_negativa_levanta(self) -> None:
        with pytest.raises(ValidationError, match="fora da faixa"):
            separar_host_e_porta("servidor-01:-1")


class TestCredenciais:
    def test_guarda_o_que_a_autenticacao_estabeleceu(self) -> None:
        dados = Credenciais(
            usuario_id="u-1", alvo="servidor-01:2222", usuario_no_alvo="root"
        )
        assert dados.usuario_id == "u-1"
        assert dados.alvo == "servidor-01:2222"
        assert dados.usuario_no_alvo == "root"

    def test_e_imutavel(self) -> None:
        """Identidade de sessão não se reescreve depois de estabelecida."""
        dados = Credenciais(usuario_id="u-1", alvo="a", usuario_no_alvo="root")
        with pytest.raises((AttributeError, TypeError)):
            dados.usuario_id = "outro"  # type: ignore[misc]
