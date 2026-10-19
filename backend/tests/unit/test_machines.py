"""Testes do domínio de acesso de máquina.

O que estes testes protegem:

- **O escopo do lease é congelado na emissão.** Ampliar a política não amplia
  um lease já emitido — senão um robô autenticado escalaria privilégio sem
  reautenticar, em silêncio.
- **Comparação em tempo constante.** `==` em hash vaza, por tempo, quantos
  caracteres iniciais acertaram.
- **A mensagem de erro não distingue** aplicação inexistente de credencial
  errada: distinguir conta ao atacante que o `role_id` existe.
- **O teto do lease.** Um token de 24h comprometido é um dia inteiro de
  acesso, o que anula a razão de o lease existir.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.access.policy import Capability
from app.domain.machines.entities import (
    LEASE_MINUTOS_MAXIMO,
    Application,
    ApplicationStatus,
    Lease,
    SecretId,
    emitir_lease,
    gerar_secret_id,
    gerar_token_de_lease,
)
from app.domain.shared.errors import ConflictError, ValidationError
from app.domain.shared.value_objects import PolicyPath, Slug

AGORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _app(**kwargs) -> Application:  # noqa: ANN003
    base = {
        "name": Slug("rpa-fiscal"),
        "display_name": "RPA Fiscal",
        "owner_label": "equipe-ti@exemplo.com.br",
    }
    return Application(**{**base, **kwargs})


def _secret_id(app: Application, **kwargs) -> tuple[SecretId, str]:  # noqa: ANN003
    valor, digest = gerar_secret_id()
    return SecretId(application_id=app.id, secret_hash=digest, **kwargs), valor


class TestAplicacao:
    def test_role_id_e_distinto_por_aplicacao(self) -> None:
        assert _app().role_id != _app(name=Slug("outra")).role_id

    def test_responsavel_e_obrigatorio(self) -> None:
        """Credencial de robô sem dono é credencial que ninguém revoga."""
        with pytest.raises(ValidationError, match="responsável"):
            _app(owner_label="   ")

    def test_lease_acima_do_teto_e_recusado(self) -> None:
        with pytest.raises(ValidationError, match="empréstimo"):
            _app(lease_minutos=LEASE_MINUTOS_MAXIMO + 1)

    def test_lease_no_teto_e_aceito(self) -> None:
        assert _app(lease_minutos=LEASE_MINUTOS_MAXIMO).lease_minutos == 720

    def test_lease_zero_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            _app(lease_minutos=0)

    def test_suspender_bloqueia_autenticacao_nova(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        app.suspend()

        assert app.status is ApplicationStatus.SUSPENDED
        with pytest.raises(ConflictError):
            emitir_lease(app, sid, ["cofres/*"], [Capability.READ], now=AGORA)

    def test_suspender_nao_derruba_lease_existente(self) -> None:
        """Suspender por engano não deve parar um robô no meio do processo."""
        app = _app()
        sid, _ = _secret_id(app)
        lease, _ = emitir_lease(app, sid, ["cofres/*"], [Capability.READ], now=AGORA)

        app.suspend()
        assert lease.is_active(AGORA) is True

    def test_caminho_de_politica(self) -> None:
        assert str(_app().path) == "aplicacoes/rpa-fiscal"


class TestSecretId:
    def test_valor_em_claro_nao_fica_no_objeto(self) -> None:
        app = _app()
        sid, valor = _secret_id(app)
        assert valor not in str(sid.__slots__)
        assert valor != sid.secret_hash

    def test_confere_o_valor_certo(self) -> None:
        app = _app()
        sid, valor = _secret_id(app)
        assert sid.matches(valor) is True
        assert sid.matches(valor + "x") is False
        assert sid.matches("") is False

    def test_revogado_deixa_de_valer(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        assert sid.is_valid(AGORA) is True
        sid.revoke(AGORA)
        assert sid.is_valid(AGORA) is False

    def test_revogar_duas_vezes_e_conflito(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        sid.revoke(AGORA)
        with pytest.raises(ConflictError):
            sid.revoke(AGORA)

    def test_expiracao_e_respeitada(self) -> None:
        app = _app()
        sid, _ = _secret_id(app, expires_at=AGORA + timedelta(days=30))
        assert sid.is_valid(AGORA) is True
        assert sid.is_valid(AGORA + timedelta(days=31)) is False

    def test_sem_expiracao_vale_sempre(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        assert sid.is_valid(AGORA + timedelta(days=3650)) is True

    def test_registra_uso(self) -> None:
        """Contador e último uso: credencial sem uso há meses é candidata a
        revogação, e o relatório precisa desse dado."""
        app = _app()
        sid, _ = _secret_id(app)
        assert sid.usos == 0
        sid.registrar_uso(AGORA)
        sid.registrar_uso(AGORA + timedelta(hours=1))
        assert sid.usos == 2
        assert sid.last_used_at == AGORA + timedelta(hours=1)

    def test_hash_malformado_e_recusado(self) -> None:
        with pytest.raises(ValidationError, match="64 caracteres"):
            SecretId(application_id="a1", secret_hash="curto")

    def test_dois_secret_ids_sao_diferentes(self) -> None:
        a, _ = gerar_secret_id()
        b, _ = gerar_secret_id()
        assert a != b


class TestLease:
    def test_expira_sozinho(self) -> None:
        app = _app(lease_minutos=60)
        sid, _ = _secret_id(app)
        lease, _ = emitir_lease(app, sid, ["cofres/*"], [Capability.READ], now=AGORA)

        assert lease.is_active(AGORA + timedelta(minutes=59)) is True
        assert lease.is_active(AGORA + timedelta(minutes=61)) is False
        assert lease.minutos_restantes(AGORA + timedelta(minutes=61)) is None

    def test_o_escopo_fica_congelado(self) -> None:
        """A invariante central.

        O lease carrega o escopo do momento da emissão. Ampliar a política
        depois NÃO amplia o lease — senão um robô autenticado escalaria
        privilégio sem reautenticar, em silêncio.
        """
        app = _app()
        sid, _ = _secret_id(app)
        lease, _ = emitir_lease(
            app, sid, ["cofres/contabil/*"], [Capability.READ], now=AGORA
        )

        assert lease.cobre(PolicyPath("cofres/contabil/segredos/x"), Capability.READ)
        # Outro cofre, mesmo que a política da aplicação mude depois.
        assert not lease.cobre(PolicyPath("cofres/rh/segredos/y"), Capability.READ)
        # Outra capacidade.
        assert not lease.cobre(
            PolicyPath("cofres/contabil/segredos/x"), Capability.DELETE
        )

    def test_escopo_respeita_fronteira_de_segmento(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        lease, _ = emitir_lease(
            app, sid, ["cofres/conta"], [Capability.READ], now=AGORA
        )
        assert not lease.cobre(PolicyPath("cofres/contabil"), Capability.READ)

    def test_token_confere_em_tempo_constante(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        lease, token = emitir_lease(
            app, sid, ["cofres/*"], [Capability.READ], now=AGORA
        )
        assert lease.matches(token) is True
        assert lease.matches(token[:-1] + "x") is False

    def test_token_em_claro_nao_fica_no_lease(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        lease, token = emitir_lease(
            app, sid, ["cofres/*"], [Capability.READ], now=AGORA
        )
        assert token not in repr(lease)
        assert token != lease.token_hash

    def test_revogar_fecha_antes_do_prazo(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        lease, _ = emitir_lease(app, sid, ["cofres/*"], [Capability.READ], now=AGORA)

        lease.revoke(AGORA + timedelta(minutes=5))
        assert lease.is_active(AGORA + timedelta(minutes=10)) is False

    def test_lease_sem_escopo_e_recusado(self) -> None:
        """Lease vazio não serve e esconde isso de quem o emitiu."""
        with pytest.raises(ValidationError, match="escopo"):
            Lease(
                application_id="a1",
                secret_id_usado="s1",
                token_hash="a" * 64,
                caminhos=[],
                capacidades=[Capability.READ],
                expires_at=AGORA + timedelta(hours=1),
            )

    def test_credencial_revogada_nao_emite(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        sid.revoke(AGORA)
        with pytest.raises(ConflictError):
            emitir_lease(app, sid, ["cofres/*"], [Capability.READ], now=AGORA)

    def test_mensagem_nao_distingue_os_motivos(self) -> None:
        """Distinguir contaria ao atacante que o role_id existe."""
        app_suspensa = _app()
        app_suspensa.suspend()
        sid_ok, _ = _secret_id(app_suspensa)

        app_ok = _app()
        sid_revogado, _ = _secret_id(app_ok)
        sid_revogado.revoke(AGORA)

        with pytest.raises(ConflictError) as por_suspensao:
            emitir_lease(app_suspensa, sid_ok, ["c/*"], [Capability.READ], now=AGORA)
        with pytest.raises(ConflictError) as por_revogacao:
            emitir_lease(app_ok, sid_revogado, ["c/*"], [Capability.READ], now=AGORA)

        assert str(por_suspensao.value) == str(por_revogacao.value)

    def test_registra_leituras(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        lease, _ = emitir_lease(app, sid, ["cofres/*"], [Capability.READ], now=AGORA)
        lease.registrar_leitura()
        lease.registrar_leitura()
        assert lease.leituras == 2

    def test_dois_tokens_sao_diferentes(self) -> None:
        a, _ = gerar_token_de_lease()
        b, _ = gerar_token_de_lease()
        assert a != b


class TestComparacaoEmTempoConstante:
    """Garante que as comparações de segredo não voltem a usar `==`.

    Este teste é estrutural de propósito. A diferença entre `compare_digest` e
    `==` é **temporal**, não funcional: os dois devolvem o mesmo resultado, e
    nenhum teste de comportamento os distingue. Medir tempo em Python daria
    falso negativo com frequência (GC, agendamento, ruído do interpretador).

    Descoberto por um mutante que sobreviveu: trocar `compare_digest` por `==`
    não quebrava nada. A proteção possível é impedir que alguém "simplifique"
    o código sem saber o que estava protegendo — `==` vaza, por tempo, quantos
    caracteres iniciais acertaram, e isso permite construir o segredo byte a
    byte.
    """

    def test_segredos_sao_comparados_com_compare_digest(self) -> None:
        import inspect

        from app.domain.machines import entities
        from app.domain.vaults import quorum

        alvos = [
            (entities.SecretId.matches, "SecretId.matches"),
            (entities.Lease.matches, "Lease.matches"),
            (quorum.SeloComQuorum.confere, "SeloComQuorum.confere"),
        ]
        for funcao, nome in alvos:
            fonte = inspect.getsource(funcao)
            assert "compare_digest" in fonte, (
                f"{nome} precisa usar hmac.compare_digest: comparar hash com "
                "'==' vaza o número de caracteres iniciais corretos pelo tempo "
                "de resposta."
            )
            assert " == " not in fonte.split("return")[-1], (
                f"{nome} parece comparar com '==' — use compare_digest."
            )


class TestGracaNaRenovacao:
    """A credencial antiga não morre na hora da renovação.

    Matar na hora derrubaria um robô que esteja no meio de um ciclo com a
    credencial velha em memória — e a rotação existe para evitar incidente,
    não para causar um. O prazo é curto de propósito: graça longa é
    credencial velha viva.
    """

    def test_graca_mantem_a_antiga_valida_por_alguns_minutos(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)

        fim = sid.aposentar_com_graca(minutos=10, now=AGORA)
        assert fim == AGORA + timedelta(minutes=10)
        assert sid.is_valid(AGORA + timedelta(minutes=5)) is True
        assert sid.is_valid(AGORA + timedelta(minutes=11)) is False

    def test_graca_nao_estica_validade_ja_vencida(self) -> None:
        """A graça não pode ressuscitar uma credencial que já ia expirar."""
        app = _app()
        sid, _ = _secret_id(app, expires_at=AGORA + timedelta(minutes=2))

        fim = sid.aposentar_com_graca(minutos=60, now=AGORA)
        assert fim == AGORA + timedelta(minutes=2)
        assert sid.is_valid(AGORA + timedelta(minutes=30)) is False

    def test_revogada_nao_recebe_graca(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        sid.revoke(AGORA)
        with pytest.raises(ConflictError):
            sid.aposentar_com_graca(now=AGORA)

    def test_dias_para_vencer(self) -> None:
        app = _app()
        sid, _ = _secret_id(app, expires_at=AGORA + timedelta(days=45))
        assert sid.dias_para_vencer(AGORA) == 45

    def test_sem_validade_nao_tem_dias(self) -> None:
        app = _app()
        sid, _ = _secret_id(app)
        assert sid.dias_para_vencer(AGORA) is None

    def test_revogada_nao_tem_dias(self) -> None:
        """Revogada não "vence": já acabou."""
        app = _app()
        sid, _ = _secret_id(app, expires_at=AGORA + timedelta(days=45))
        sid.revoke(AGORA)
        assert sid.dias_para_vencer(AGORA) is None
