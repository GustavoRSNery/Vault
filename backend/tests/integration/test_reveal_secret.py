"""Testes do caso de uso mais sensível: revelar um segredo.

Cada teste aqui corresponde a uma forma de o sistema falhar de modo grave:
entregar segredo a quem não pode, entregar de cofre selado, entregar sem
deixar rastro, ou deixar o valor vazar para log.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.application.vaults.reveal_secret import (
    RevealSecret,
    RevealSecretCommand,
    RevealedSecret,
)
from app.domain.access.policy import Capability, Effect, Policy, PolicyRule
from app.domain.audit.events import AuditAction, AuditOutcome
from app.domain.shared.errors import PermissionDeniedError, SealedError
from app.domain.shared.value_objects import PolicyPath, Slug
from app.domain.vaults.entities import Secret, Vault
from app.infrastructure.crypto.envelope import EnvelopeCryptoService
from app.infrastructure.db.models import PolicyModel, RoleModel, UserModel
from app.infrastructure.db.repositories import (
    AuditRepository,
    PolicyRepository,
    SecretRepository,
    VaultRepository,
)

SENHA = "senha-do-root-2026"


def _montar(session: Session, crypto: EnvelopeCryptoService, *, capacidades, efeito=Effect.ALLOW,
            caminho="cofres/contabil/*"):
    """Cria usuário com papel+política, um cofre e um segredo cifrado."""
    vaults, secrets = VaultRepository(session), SecretRepository(session)
    policies, audit = PolicyRepository(session), AuditRepository(session)

    cofre = vaults.add(Vault(name=Slug("contabil"), display_name="Contábil"))
    segredo = Secret(name=Slug("senha-root"), vault_id=cofre.id)
    segredo.add_version(crypto.encrypt(SENHA), created_by="u1")
    secrets.add(segredo)

    politica = Policy(
        name=Slug("acesso-contabil"),
        rules=[PolicyRule(path=PolicyPath(caminho),
                          capabilities=frozenset(capacidades), effect=efeito)],
    )
    policies.add(politica)
    session.flush()

    usuario = UserModel(id="u1", email="ana.souza@exemplo.com.br", full_name="Ana Souza",
                        password_hash="x")
    papel = RoleModel(id="r1", name="contador")
    papel.policies.append(session.get(PolicyModel, politica.id))
    usuario.roles.append(papel)
    session.add(usuario)
    session.flush()

    caso = RevealSecret(vaults, secrets, policies, audit, crypto)
    return caso, cofre, audit


def _comando() -> RevealSecretCommand:
    return RevealSecretCommand(
        actor_id="u1",
        actor_label="ana.souza@exemplo.com.br",
        vault_name="contabil",
        secret_name="senha-root",
        ip_address="10.0.0.5",
        user_agent="Mozilla/5.0",
    )


class TestRevealHappyPath:
    def test_com_permissao_devolve_o_valor(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        caso, _, _ = _montar(session, crypto, capacidades={Capability.REVEAL})
        assert caso.execute(_comando()).value == SENHA

    def test_revelacao_gera_evento_de_auditoria(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        caso, _, audit = _montar(session, crypto, capacidades={Capability.REVEAL})
        caso.execute(_comando())

        eventos = audit.list_chain()
        assert len(eventos) == 1
        evento = eventos[0]
        assert evento.action is AuditAction.SECRET_REVEALED
        assert evento.outcome is AuditOutcome.SUCCESS
        assert evento.actor_id == "u1"
        assert evento.target_path == "cofres/contabil/segredos/senha-root"
        assert evento.ip_address == "10.0.0.5"

    def test_auditoria_nao_guarda_o_valor(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        """A trilha é lida por mais gente do que o segredo."""
        caso, _, audit = _montar(session, crypto, capacidades={Capability.REVEAL})
        caso.execute(_comando())

        evento = audit.list_chain()[0]
        assert SENHA not in str(evento.metadata)
        assert SENHA not in evento.reason
        assert SENHA not in evento.target_path


class TestRevealDenied:
    def test_sem_capacidade_reveal_e_negado(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        """READ não basta: ver que existe não é ver o valor."""
        caso, _, _ = _montar(session, crypto, capacidades={Capability.READ, Capability.LIST})
        with pytest.raises(PermissionDeniedError):
            caso.execute(_comando())

    def test_negacao_tambem_gera_auditoria(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        """Tentativa negada sem registro é o que o atacante quer."""
        caso, _, audit = _montar(session, crypto, capacidades={Capability.READ})
        with pytest.raises(PermissionDeniedError):
            caso.execute(_comando())

        eventos = audit.list_chain()
        assert len(eventos) == 1
        assert eventos[0].action is AuditAction.ACCESS_DENIED
        assert eventos[0].outcome is AuditOutcome.FAILURE

    def test_politica_deny_derruba_allow(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        caso, _, _ = _montar(session, crypto, capacidades={Capability.REVEAL},
                             efeito=Effect.DENY)
        with pytest.raises(PermissionDeniedError):
            caso.execute(_comando())

    def test_caminho_de_outro_cofre_nao_concede(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        caso, _, _ = _montar(session, crypto, capacidades={Capability.REVEAL},
                             caminho="cofres/rh/*")
        with pytest.raises(PermissionDeniedError):
            caso.execute(_comando())


class TestRevealSealed:
    def test_cofre_selado_recusa_mesmo_com_permissao(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        caso, cofre, _ = _montar(session, crypto, capacidades={Capability.REVEAL})
        vaults = VaultRepository(session)
        cofre.seal()
        vaults.save_state(cofre)

        with pytest.raises(SealedError):
            caso.execute(_comando())


class TestNoLeakInRepr:
    def test_repr_mascara_o_valor(self) -> None:
        """Um traceback não pode imprimir a senha no log de produção."""
        revelado = RevealedSecret(
            secret_id="s1", secret_name="senha-root", version=3, value=SENHA
        )
        assert SENHA not in repr(revelado)
        assert "***" in repr(revelado)

    def test_valor_continua_acessivel_pelo_atributo(self) -> None:
        revelado = RevealedSecret(
            secret_id="s1", secret_name="senha-root", version=3, value=SENHA
        )
        assert revelado.value == SENHA

    def test_formatacao_em_f_string_tambem_mascara(self) -> None:
        """f'{obj!r}' e str(lista_de_objs) passam pelo __repr__."""
        revelado = RevealedSecret(
            secret_id="s1", secret_name="senha-root", version=3, value=SENHA
        )
        assert SENHA not in f"{revelado!r}"
        assert SENHA not in str([revelado])
