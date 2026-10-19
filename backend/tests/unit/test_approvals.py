"""Testes do domínio de aprovações.

As invariantes aqui protegem o fluxo de acesso temporário de virar
formalidade: quem pede não aprova, decisão não se refaz, e concessão sem
prazo não existe.

O bloco mais importante é `TestDecide`, que fixa a ordem da composição:
`deny` das políticas vence concessão temporária. Compor as duas fontes com
um OR ingênuo deixaria uma aprovação de emergência furar uma proibição
deliberada — o oposto do que "negação vence" existe para garantir.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.access.policy import Capability, Effect, Policy, PolicyRule, evaluate
from app.domain.approvals.entities import (
    HORAS_MAXIMAS,
    AccessRequest,
    RequestStatus,
    decide,
    grants_access,
)
from app.domain.shared.errors import ConflictError, ValidationError
from app.domain.shared.value_objects import PolicyPath, Slug

AGORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _pedido(**kwargs) -> AccessRequest:  # noqa: ANN003
    base = {
        "requester_id": "u1",
        "requester_label": "ana@exemplo.com.br",
        "path": PolicyPath("cofres/contabil/segredos/token-sefaz"),
        "capabilities": frozenset({Capability.REVEAL}),
        "reason": "Preciso emitir a guia hoje",
        "hours": 4,
    }
    return AccessRequest(**{**base, **kwargs})


class TestCriacao:
    def test_nasce_pendente(self) -> None:
        p = _pedido()
        assert p.is_pending is True
        assert p.status is RequestStatus.PENDING
        assert p.granted_until is None
        assert p.is_active(AGORA) is False

    def test_justificativa_e_obrigatoria(self) -> None:
        with pytest.raises(ValidationError):
            _pedido(reason="   ")

    def test_sem_capacidade_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            _pedido(capabilities=frozenset())

    def test_janela_minima_de_uma_hora(self) -> None:
        with pytest.raises(ValidationError):
            _pedido(hours=0)

    def test_acima_do_teto_manda_editar_a_politica(self) -> None:
        """Mais de 30 dias não é temporário: é permanente disfarçado."""
        with pytest.raises(ValidationError, match="política"):
            _pedido(hours=HORAS_MAXIMAS + 1)

    def test_no_teto_ainda_e_aceito(self) -> None:
        assert _pedido(hours=HORAS_MAXIMAS).hours == HORAS_MAXIMAS


class TestDecisao:
    def test_quem_pede_nao_aprova(self) -> None:
        """Auto-aprovação transformaria o fluxo inteiro em formalidade."""
        p = _pedido(requester_id="u1")
        with pytest.raises(ConflictError, match="própria solicitação"):
            p.approve("u1", "ana@exemplo.com.br", now=AGORA)
        assert p.is_pending is True

    def test_quem_pede_tambem_nao_nega_a_si(self) -> None:
        p = _pedido(requester_id="u1")
        with pytest.raises(ConflictError):
            p.deny("u1", "ana@exemplo.com.br", now=AGORA)

    def test_aprovacao_abre_a_janela(self) -> None:
        p = _pedido(hours=4)
        p.approve("u2", "bruno@exemplo.com.br", "Ok para hoje", now=AGORA)
        assert p.status is RequestStatus.APPROVED
        assert p.granted_until == AGORA + timedelta(hours=4)
        assert p.is_active(AGORA) is True
        assert p.decided_by_label == "bruno@exemplo.com.br"

    def test_prazo_conta_da_aprovacao_e_nao_do_pedido(self) -> None:
        """Pedido parado dois dias na fila não nasce com a janela gasta."""
        p = _pedido(hours=4, created_at=AGORA - timedelta(days=2))
        p.approve("u2", "bruno", now=AGORA)
        assert p.granted_until == AGORA + timedelta(hours=4)
        assert p.hours_remaining(AGORA) == 4.0

    def test_negacao_nao_concede_nada(self) -> None:
        p = _pedido()
        p.deny("u2", "bruno", "Use o processo normal", now=AGORA)
        assert p.status is RequestStatus.DENIED
        assert p.granted_until is None
        assert p.is_active(AGORA) is False

    def test_decisao_e_terminal(self) -> None:
        """Pedir de novo é outra solicitação, com outro registro."""
        p = _pedido()
        p.deny("u2", "bruno", now=AGORA)
        with pytest.raises(ConflictError, match="já está"):
            p.approve("u3", "carla", now=AGORA)
        assert p.status is RequestStatus.DENIED

    def test_aprovada_nao_se_aprova_de_novo(self) -> None:
        p = _pedido()
        p.approve("u2", "bruno", now=AGORA)
        with pytest.raises(ConflictError):
            p.approve("u3", "carla", now=AGORA)


class TestJanelaDeTempo:
    def test_expira_sozinha(self) -> None:
        """O ponto do acesso temporário: ninguém precisa lembrar de remover."""
        p = _pedido(hours=4)
        p.approve("u2", "bruno", now=AGORA)
        assert p.is_active(AGORA + timedelta(hours=3, minutes=59)) is True
        assert p.is_active(AGORA + timedelta(hours=4, seconds=1)) is False

    def test_horas_restantes_somem_apos_o_prazo(self) -> None:
        p = _pedido(hours=4)
        p.approve("u2", "bruno", now=AGORA)
        assert p.hours_remaining(AGORA + timedelta(hours=1)) == 3.0
        assert p.hours_remaining(AGORA + timedelta(hours=5)) is None

    def test_revogar_fecha_antes_do_prazo(self) -> None:
        p = _pedido(hours=48)
        p.approve("u2", "bruno", now=AGORA)
        p.revoke(now=AGORA + timedelta(hours=1))
        assert p.status is RequestStatus.REVOKED
        assert p.is_active(AGORA + timedelta(hours=2)) is False

    def test_revogar_preserva_o_registro(self) -> None:
        """Fica como revogada, não como se nunca tivesse sido aprovada."""
        p = _pedido()
        p.approve("u2", "bruno", "Aprovado", now=AGORA)
        p.revoke(now=AGORA)
        assert p.decided_by_label == "bruno"
        assert p.decision_note == "Aprovado"
        assert p.decided_at == AGORA

    def test_so_aprovada_se_revoga(self) -> None:
        p = _pedido()
        with pytest.raises(ConflictError):
            p.revoke(now=AGORA)


class TestConcessaoNaAvaliacao:
    def test_concede_dentro_do_escopo_e_do_prazo(self) -> None:
        p = _pedido(
            path=PolicyPath("cofres/contabil/*"),
            capabilities=frozenset({Capability.REVEAL}),
        )
        p.approve("u2", "bruno", now=AGORA)
        alvo = PolicyPath("cofres/contabil/segredos/token-sefaz")

        assert grants_access([p], alvo, Capability.REVEAL, AGORA) is p
        # Fora da capacidade pedida.
        assert grants_access([p], alvo, Capability.DELETE, AGORA) is None
        # Fora do prazo.
        assert (
            grants_access([p], alvo, Capability.REVEAL, AGORA + timedelta(hours=5))
            is None
        )

    def test_pendente_nao_concede(self) -> None:
        p = _pedido(path=PolicyPath("cofres/contabil/*"))
        alvo = PolicyPath("cofres/contabil/segredos/x")
        assert grants_access([p], alvo, Capability.REVEAL, AGORA) is None

    def test_respeita_fronteira_de_segmento(self) -> None:
        """"cofres/conta" não pode cobrir "cofres/contabil" nem via concessão."""
        p = _pedido(path=PolicyPath("cofres/conta"))
        p.approve("u2", "bruno", now=AGORA)
        alvo = PolicyPath("cofres/contabil")
        assert grants_access([p], alvo, Capability.REVEAL, AGORA) is None

    def test_concessao_nao_fura_negacao_explicita(self) -> None:
        """A invariante central da composição com o RBAC.

        A concessão SOMA ao que as políticas permitem; ela não derruba um
        `deny`. Se furasse, uma aprovação de emergência contornaria uma
        proibição deliberada — o oposto do que "negação vence" existe para
        garantir. Quem precisa furar o deny altera a política, que é revisada.
        """
        alvo = PolicyPath("cofres/contabil/segredos/token-sefaz")
        politicas = [
            Policy(
                name=Slug("contabil"),
                rules=[
                    PolicyRule(
                        path=PolicyPath("cofres/contabil/*"),
                        capabilities=frozenset({Capability.REVEAL}),
                    ),
                    PolicyRule(
                        path=alvo,
                        capabilities=frozenset({Capability.REVEAL}),
                        effect=Effect.DENY,
                    ),
                ],
            )
        ]
        concessao = _pedido(path=alvo, capabilities=frozenset({Capability.REVEAL}))
        concessao.approve("u2", "bruno", now=AGORA)

        # A concessão existe e cobre exatamente este caminho...
        assert grants_access([concessao], alvo, Capability.REVEAL, AGORA) is concessao

        # ...e ainda assim o acesso é negado, porque o deny vem primeiro.
        permitido, motivo = decide(
            politicas, [concessao], alvo, Capability.REVEAL, AGORA
        )
        assert permitido is False
        assert "não é contornada por concessão" in motivo


class TestDecide:
    """A composição das duas fontes, na ordem que importa."""

    def test_deny_vence_mesmo_com_concessao_ativa(self) -> None:
        alvo = PolicyPath("cofres/rh/segredos/folha")
        politicas = [
            Policy(
                name=Slug("bloqueio"),
                rules=[
                    PolicyRule(
                        path=PolicyPath("cofres/rh/*"),
                        capabilities=frozenset({Capability.REVEAL}),
                        effect=Effect.DENY,
                    )
                ],
            )
        ]
        concessao = _pedido(path=PolicyPath("cofres/rh/*"))
        concessao.approve("u2", "bruno", now=AGORA)

        permitido, _ = decide(politicas, [concessao], alvo, Capability.REVEAL, AGORA)
        assert permitido is False

    def test_politica_permite_sem_precisar_de_concessao(self) -> None:
        alvo = PolicyPath("cofres/contabil/segredos/x")
        politicas = [
            Policy(
                name=Slug("leitura"),
                rules=[
                    PolicyRule(
                        path=PolicyPath("cofres/contabil/*"),
                        capabilities=frozenset({Capability.REVEAL}),
                    )
                ],
            )
        ]
        permitido, motivo = decide(politicas, [], alvo, Capability.REVEAL, AGORA)
        assert permitido is True
        assert "políticas" in motivo

    def test_concessao_permite_o_que_a_politica_nao_permitia(self) -> None:
        """O caso de uso que justifica o fluxo inteiro existir."""
        alvo = PolicyPath("cofres/contabil/segredos/token-sefaz")
        assert decide([], [], alvo, Capability.REVEAL, AGORA)[0] is False

        concessao = _pedido(path=alvo, capabilities=frozenset({Capability.REVEAL}))
        concessao.approve("u2", "bruno@exemplo.com.br", now=AGORA)

        permitido, motivo = decide([], [concessao], alvo, Capability.REVEAL, AGORA)
        assert permitido is True
        assert "bruno@exemplo.com.br" in motivo
        assert "expira em" in motivo

    def test_concessao_vencida_nao_permite_mais(self) -> None:
        alvo = PolicyPath("cofres/contabil/segredos/token-sefaz")
        concessao = _pedido(path=alvo, hours=4)
        concessao.approve("u2", "bruno", now=AGORA)

        depois = AGORA + timedelta(hours=5)
        permitido, motivo = decide([], [concessao], alvo, Capability.REVEAL, depois)
        assert permitido is False
        assert "Nenhuma política ou concessão" in motivo

    def test_concessao_revogada_nao_permite_mais(self) -> None:
        alvo = PolicyPath("cofres/contabil/segredos/token-sefaz")
        concessao = _pedido(path=alvo, hours=48)
        concessao.approve("u2", "bruno", now=AGORA)
        concessao.revoke(now=AGORA + timedelta(hours=1))

        permitido, _ = decide(
            [], [concessao], alvo, Capability.REVEAL, AGORA + timedelta(hours=2)
        )
        assert permitido is False

    def test_sem_nada_nega_por_padrao(self) -> None:
        permitido, motivo = decide(
            [], [], PolicyPath("cofres/x"), Capability.READ, AGORA
        )
        assert permitido is False
        assert "Nenhuma" in motivo
