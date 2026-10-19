"""Testes do domínio de inventário.

Cada bloco protege uma invariante que, quebrada, não dá erro na hora — só
aparece como incidente depois: duas pessoas trocando a mesma senha, credencial
de fábrica fora do relatório, certificado "válido" no dia em que venceu.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.inventory.entities import (
    DIAS_DE_ALERTA,
    Certificate,
    CertificateState,
    Checkout,
    Credential,
    CredentialStatus,
    Device,
    DeviceKind,
)
from app.domain.shared.errors import ConflictError, ValidationError
from app.domain.shared.value_objects import Slug

AGORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _credencial(**kwargs) -> Credential:  # noqa: ANN003
    base = {"name": Slug("senha-root"), "device_id": "d1"}
    return Credential(**{**base, **kwargs})


class TestDevice:
    def test_caminho_de_politica(self) -> None:
        d = Device(name=Slug("fw-matriz"), display_name="Firewall Matriz")
        assert str(d.path) == "dispositivos/fw-matriz"

    def test_tags_normalizam_e_deduplicam(self) -> None:
        """Tag duplicada ou com caixa diferente só polui o filtro da tela."""
        d = Device(
            name=Slug("srv-01"),
            display_name="Servidor 01",
            tags=["Produção", " produção ", "crítico", ""],
        )
        assert d.tags == ["crítico", "produção"]

    def test_nome_visivel_e_obrigatorio(self) -> None:
        with pytest.raises(ValidationError):
            Device(name=Slug("srv-01"), display_name="   ")

    def test_tipo_padrao_e_outro(self) -> None:
        d = Device(name=Slug("x"), display_name="X")
        assert d.kind is DeviceKind.OTHER


class TestRotacao:
    def test_nunca_rotacionada_conta_como_atrasada(self) -> None:
        """Senha de fábrica é o pior caso: não pode ficar fora do relatório."""
        c = _credencial(last_rotated_at=None)
        assert c.is_overdue(AGORA) is True
        assert c.due_at is None

    def test_dentro_do_prazo_nao_esta_atrasada(self) -> None:
        c = _credencial(rotation_days=90, last_rotated_at=AGORA - timedelta(days=10))
        assert c.is_overdue(AGORA) is False
        assert c.days_until_due(AGORA) == 80

    def test_um_dia_depois_do_prazo_esta_atrasada(self) -> None:
        c = _credencial(rotation_days=90, last_rotated_at=AGORA - timedelta(days=91))
        assert c.is_overdue(AGORA) is True

    def test_exatamente_no_prazo_ainda_nao_esta_atrasada(self) -> None:
        """A fronteira é estrita: vence quando passa, não quando chega."""
        c = _credencial(rotation_days=90, last_rotated_at=AGORA - timedelta(days=90))
        assert c.is_overdue(AGORA) is False

    def test_prazo_zero_desliga_a_rotacao(self) -> None:
        """Zero quer dizer "não rotaciona" — e isso é dito, não inferido."""
        c = _credencial(rotation_days=0, last_rotated_at=None)
        assert c.rotation_disabled is True
        assert c.is_overdue(AGORA) is False
        assert c.due_at is None
        assert c.days_until_due(AGORA) is None

    def test_marcar_rotacao_zera_o_atraso(self) -> None:
        c = _credencial(rotation_days=30, last_rotated_at=AGORA - timedelta(days=60))
        assert c.is_overdue(AGORA) is True
        c.mark_rotated(AGORA)
        assert c.is_overdue(AGORA) is False

    def test_prazo_negativo_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            _credencial(rotation_days=-1)

    def test_aposentada_nao_rotaciona(self) -> None:
        c = _credencial()
        c.retire()
        with pytest.raises(ConflictError):
            c.mark_rotated(AGORA)


class TestCustodia:
    def test_retirada_registra_prazo_e_motivo(self) -> None:
        c = _credencial()
        retirada = c.check_out("u1", "Ana", "Troca de senha do roteador", hours=4)
        assert retirada.is_open is True
        assert c.status is CredentialStatus.CHECKED_OUT
        assert c.open_checkout is retirada

    def test_dois_checkouts_simultaneos_sao_recusados(self) -> None:
        """A invariante central: se duas pessoas levam a mesma credencial,
        as duas trocam a senha e a segunda invalida a da primeira."""
        c = _credencial()
        c.check_out("u1", "Ana", "Manutenção", hours=4)
        with pytest.raises(ConflictError, match="Ana"):
            c.check_out("u2", "Bruno", "Também preciso", hours=4)

    def test_devolver_libera_para_o_proximo(self) -> None:
        c = _credencial()
        c.check_out("u1", "Ana", "Manutenção", hours=4)
        c.check_in("u1")
        assert c.status is CredentialStatus.ACTIVE
        assert c.open_checkout is None
        c.check_out("u2", "Bruno", "Agora sim", hours=2)
        assert c.open_checkout is not None

    def test_terceiro_nao_devolve_credencial_alheia(self) -> None:
        c = _credencial()
        c.check_out("u1", "Ana", "Manutenção", hours=4)
        with pytest.raises(ConflictError, match="Ana"):
            c.check_in("u2")

    def test_administrador_forca_a_devolucao(self) -> None:
        """Caso real: quem retirou saiu de férias com a credencial na mão."""
        c = _credencial()
        c.check_out("u1", "Ana", "Manutenção", hours=4)
        devolvida = c.check_in("u2", force=True)
        assert devolvida.is_open is False
        assert c.status is CredentialStatus.ACTIVE

    def test_devolver_sem_custodia_e_conflito(self) -> None:
        c = _credencial()
        with pytest.raises(ConflictError):
            c.check_in("u1")

    def test_justificativa_e_obrigatoria(self) -> None:
        c = _credencial()
        with pytest.raises(ValidationError):
            c.check_out("u1", "Ana", "   ", hours=4)

    def test_prazo_fora_da_faixa_e_recusado(self) -> None:
        c = _credencial()
        with pytest.raises(ValidationError):
            c.check_out("u1", "Ana", "Manutenção", hours=0)
        with pytest.raises(ValidationError):
            c.check_out("u1", "Ana", "Manutenção", hours=721)

    def test_atraso_se_mede_pelo_prazo(self) -> None:
        retirada = Checkout(
            credential_id="c1",
            user_id="u1",
            user_label="Ana",
            reason="Manutenção",
            due_at=AGORA + timedelta(hours=2),
            taken_at=AGORA,
        )
        assert retirada.is_late(AGORA + timedelta(hours=1)) is False
        assert retirada.is_late(AGORA + timedelta(hours=3)) is True

    def test_devolvida_nunca_esta_em_atraso(self) -> None:
        """Atraso é dívida aberta: depois de devolver, não há o que cobrar."""
        retirada = Checkout(
            credential_id="c1",
            user_id="u1",
            user_label="Ana",
            reason="Manutenção",
            due_at=AGORA + timedelta(hours=2),
            taken_at=AGORA,
        )
        retirada.give_back(AGORA + timedelta(hours=5))
        assert retirada.is_late(AGORA + timedelta(days=30)) is False

    def test_devolver_duas_vezes_e_conflito(self) -> None:
        retirada = Checkout(
            credential_id="c1",
            user_id="u1",
            user_label="Ana",
            reason="Manutenção",
            due_at=AGORA + timedelta(hours=2),
            taken_at=AGORA,
        )
        retirada.give_back()
        with pytest.raises(ConflictError):
            retirada.give_back()

    def test_prazo_no_passado_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            Checkout(
                credential_id="c1",
                user_id="u1",
                user_label="Ana",
                reason="Manutenção",
                due_at=AGORA - timedelta(hours=1),
                taken_at=AGORA,
            )

    def test_aposentar_com_credencial_na_mao_de_alguem(self) -> None:
        c = _credencial()
        c.check_out("u1", "Ana", "Manutenção", hours=4)
        with pytest.raises(ConflictError, match="Devolva"):
            c.retire()

    def test_aposentada_nao_e_retirada(self) -> None:
        c = _credencial()
        c.retire()
        with pytest.raises(ConflictError):
            c.check_out("u1", "Ana", "Manutenção", hours=4)


class TestCertificados:
    def _cert(self, dias_restantes: int) -> Certificate:
        return Certificate(
            name=Slug("api-rede"),
            display_name="api.exemplo.com.br",
            subject="CN=api.exemplo.com.br",
            issuer="Let's Encrypt",
            not_before=AGORA - timedelta(days=60),
            not_after=AGORA + timedelta(days=dias_restantes),
        )

    def test_valido_fora_da_faixa_de_alerta(self) -> None:
        cert = self._cert(dias_restantes=DIAS_DE_ALERTA + 10)
        assert cert.state(AGORA) is CertificateState.VALID
        assert cert.is_expired(AGORA) is False

    def test_vencendo_dentro_da_faixa(self) -> None:
        cert = self._cert(dias_restantes=DIAS_DE_ALERTA - 1)
        assert cert.state(AGORA) is CertificateState.EXPIRING

    def test_na_borda_da_faixa_ja_alerta(self) -> None:
        cert = self._cert(dias_restantes=DIAS_DE_ALERTA)
        assert cert.state(AGORA) is CertificateState.EXPIRING

    def test_no_instante_do_vencimento_ja_esta_vencido(self) -> None:
        """"Válido até" não inclui o instante em que vence."""
        cert = self._cert(dias_restantes=0)
        cert.not_after = AGORA
        assert cert.state(AGORA) is CertificateState.EXPIRED
        assert cert.is_expired(AGORA) is True

    def test_vencido_e_terminal(self) -> None:
        cert = self._cert(dias_restantes=-1)
        assert cert.state(AGORA) is CertificateState.EXPIRED

    def test_dias_restantes(self) -> None:
        cert = self._cert(dias_restantes=45)
        assert cert.days_remaining(AGORA) == 45

    def test_validade_invertida_e_recusada(self) -> None:
        with pytest.raises(ValidationError):
            Certificate(
                name=Slug("x"),
                display_name="x",
                subject="CN=x",
                issuer="CA",
                not_before=AGORA,
                not_after=AGORA - timedelta(days=1),
            )

    def test_titular_e_obrigatorio(self) -> None:
        with pytest.raises(ValidationError):
            Certificate(
                name=Slug("x"),
                display_name="x",
                subject="  ",
                issuer="CA",
                not_before=AGORA - timedelta(days=1),
                not_after=AGORA + timedelta(days=1),
            )

    def test_caminho_de_politica(self) -> None:
        assert str(self._cert(10).path) == "certificados/api-rede"
