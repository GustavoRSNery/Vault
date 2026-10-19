"""Testes do motor de políticas.

A asserção que mais importa é a de negação: se ela falhar, uma revogação
não revoga nada e o sistema inteiro perde o controle de acesso.
"""

import pytest

from app.domain.access.policy import (
    Capability,
    Effect,
    Policy,
    PolicyRule,
    evaluate,
    explain,
)
from app.domain.shared.errors import ValidationError
from app.domain.shared.value_objects import PolicyPath, Slug


def _policy(name: str, *rules: PolicyRule) -> Policy:
    return Policy(name=Slug(name), rules=list(rules))


def _rule(path: str, *caps: Capability, effect: Effect = Effect.ALLOW) -> PolicyRule:
    return PolicyRule(path=PolicyPath(path), capabilities=frozenset(caps), effect=effect)


class TestPathMatching:
    def test_caminho_exato_casa(self) -> None:
        assert PolicyPath("cofres/contabil").matches(PolicyPath("cofres/contabil"))

    def test_caminho_diferente_nao_casa(self) -> None:
        assert not PolicyPath("cofres/contabil").matches(PolicyPath("cofres/rh"))

    def test_curinga_cobre_filhos(self) -> None:
        wildcard = PolicyPath("cofres/*")
        assert wildcard.matches(PolicyPath("cofres/contabil"))
        assert wildcard.matches(PolicyPath("cofres/contabil/segredos/1"))

    def test_curinga_nao_cobre_o_proprio_prefixo(self) -> None:
        # "cofres/*" fala sobre o conteúdo de cofres, não sobre o nó "cofres".
        assert not PolicyPath("cofres/*").matches(PolicyPath("cofres"))

    def test_prefixo_parcial_nao_casa_por_texto(self) -> None:
        # O bug clássico: comparar com startswith faria "conta" cobrir "contabil".
        assert not PolicyPath("cofres/conta/*").matches(PolicyPath("cofres/contabil/x"))

    def test_curinga_no_meio_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            PolicyPath("cofres/*/segredos")

    def test_curinga_parcial_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            PolicyPath("cofres/conta*")


class TestEvaluate:
    def test_sem_politica_nega(self) -> None:
        assert evaluate([], PolicyPath("cofres/x"), Capability.READ) is False

    def test_allow_simples_permite(self) -> None:
        policies = [_policy("leitura", _rule("cofres/contabil", Capability.READ))]
        assert evaluate(policies, PolicyPath("cofres/contabil"), Capability.READ) is True

    def test_capacidade_nao_concedida_e_negada(self) -> None:
        policies = [_policy("leitura", _rule("cofres/contabil", Capability.READ))]
        assert evaluate(policies, PolicyPath("cofres/contabil"), Capability.REVEAL) is False

    def test_deny_vence_allow_mais_especifico(self) -> None:
        """O teste decisivo: negação ampla derruba permissão específica."""
        policies = [
            _policy("ampla", _rule("cofres/contabil/segredo-raiz", Capability.REVEAL)),
            _policy("bloqueio", _rule("cofres/*", Capability.REVEAL, effect=Effect.DENY)),
        ]
        alvo = PolicyPath("cofres/contabil/segredo-raiz")
        assert evaluate(policies, alvo, Capability.REVEAL) is False

    def test_deny_vence_independente_da_ordem(self) -> None:
        deny = _policy("bloqueio", _rule("cofres/*", Capability.READ, effect=Effect.DENY))
        allow = _policy("leitura", _rule("cofres/rh", Capability.READ))
        alvo = PolicyPath("cofres/rh")
        assert evaluate([deny, allow], alvo, Capability.READ) is False
        assert evaluate([allow, deny], alvo, Capability.READ) is False

    def test_deny_de_outro_caminho_nao_afeta(self) -> None:
        policies = [
            _policy("leitura", _rule("cofres/rh", Capability.READ)),
            _policy("bloqueio", _rule("cofres/contabil/*", Capability.READ, effect=Effect.DENY)),
        ]
        assert evaluate(policies, PolicyPath("cofres/rh"), Capability.READ) is True


class TestExplain:
    def test_explica_negacao_nomeando_a_politica(self) -> None:
        policies = [
            _policy("leitura", _rule("cofres/rh", Capability.READ)),
            _policy("bloqueio", _rule("cofres/*", Capability.READ, effect=Effect.DENY)),
        ]
        permitido, motivo = explain(policies, PolicyPath("cofres/rh"), Capability.READ)
        assert permitido is False
        assert "bloqueio" in motivo

    def test_explica_ausencia_de_regra(self) -> None:
        permitido, motivo = explain([], PolicyPath("cofres/x"), Capability.READ)
        assert permitido is False
        assert "Nenhuma política" in motivo

    def test_sem_nomear_politica_cita_apenas_a_regra(self) -> None:
        """Modo usado pela simulação de um rascunho ainda não salvo.

        Ali a política não existe para quem edita: citar o nome interno faria a
        tela referir-se a algo que o usuário não reconhece. A decisão é a mesma;
        muda só como ela é dita.
        """
        policies = [
            _policy("rascunho", _rule("cofres/*", Capability.READ, effect=Effect.DENY)),
        ]
        permitido, motivo = explain(
            policies,
            PolicyPath("cofres/rh"),
            Capability.READ,
            nomear_politica=False,
        )
        assert permitido is False
        assert "rascunho" not in motivo
        assert "pela regra em cofres/*" in motivo

    def test_nomear_politica_nao_muda_a_decisao(self) -> None:
        """O rótulo é texto de interface e não pode mexer no veredito."""
        policies = [
            _policy("leitura", _rule("cofres/rh", Capability.READ)),
            _policy("bloqueio", _rule("cofres/*", Capability.READ, effect=Effect.DENY)),
        ]
        com, _ = explain(policies, PolicyPath("cofres/rh"), Capability.READ)
        sem, _ = explain(
            policies, PolicyPath("cofres/rh"), Capability.READ, nomear_politica=False
        )
        assert com == sem is False


class TestRuleValidation:
    def test_regra_sem_capacidade_e_recusada(self) -> None:
        with pytest.raises(ValidationError):
            PolicyRule(path=PolicyPath("cofres/x"), capabilities=frozenset())
