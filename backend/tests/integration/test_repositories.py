"""Testes de integração dos repositórios, contra banco real.

O que se prova aqui e não dá para provar com mock:
- as constraints existem e disparam (nome duplicado, versão duplicada);
- o ciclo entidade→banco→entidade preserva tudo, inclusive bytes;
- o segredo cifrado chega ao banco cifrado — e não há valor em claro nele.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.access.policy import Capability, Effect, Policy, PolicyRule
from app.domain.audit.events import AuditAction, AuditEvent, verify_chain
from app.domain.shared.errors import ConflictError, NotFoundError
from app.domain.shared.value_objects import PolicyPath, Slug
from app.domain.vaults.entities import Secret, SecretKind, Vault
from app.infrastructure.crypto.envelope import EnvelopeCryptoService
from app.infrastructure.db.models import SecretVersionModel
from app.infrastructure.db.repositories import (
    AuditRepository,
    PolicyRepository,
    SecretRepository,
    VaultRepository,
)

SENHA_REAL = "senha-do-root-em-producao-2026"


def _cofre(nome: str = "contabil") -> Vault:
    return Vault(name=Slug(nome), display_name="Contábil")


class TestVaultRepository:
    def test_grava_e_recupera_preservando_campos(self, session: Session) -> None:
        repo = VaultRepository(session)
        original = Vault(name=Slug("rh"), display_name="RH", description="Cofre do RH")
        repo.add(original)

        recuperado = repo.get_by_name(Slug("rh"))
        assert recuperado.id == original.id
        assert recuperado.display_name == "RH"
        assert recuperado.description == "Cofre do RH"
        assert recuperado.state == original.state

    def test_cofre_inexistente_levanta_not_found(self, session: Session) -> None:
        with pytest.raises(NotFoundError):
            VaultRepository(session).get_by_name(Slug("nao-existe"))

    def test_nome_duplicado_e_conflito(self, session: Session) -> None:
        repo = VaultRepository(session)
        repo.add(_cofre())
        with pytest.raises(ConflictError):
            repo.add(Vault(name=Slug("contabil"), display_name="Outro"))

    def test_selagem_persiste(self, session: Session) -> None:
        repo = VaultRepository(session)
        cofre = repo.add(_cofre())
        cofre.seal()
        repo.save_state(cofre)

        assert repo.get_by_name(Slug("contabil")).is_sealed

    def test_lista_ordenada_por_nome(self, session: Session) -> None:
        repo = VaultRepository(session)
        for nome in ("rh", "contabil", "fiscal"):
            repo.add(Vault(name=Slug(nome), display_name=nome.upper()))
        assert [str(v.name) for v in repo.list_all()] == ["contabil", "fiscal", "rh"]


class TestSecretRepository:
    def test_segredo_chega_cifrado_ao_banco(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        """O teste que mais importa: o banco não pode conter a senha legível."""
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        cofre = vault_repo.add(_cofre())

        segredo = Secret(name=Slug("senha-root"), vault_id=cofre.id, kind=SecretKind.PASSWORD)
        segredo.add_version(crypto.encrypt(SENHA_REAL), created_by="u1")
        secret_repo.add(segredo)
        session.flush()

        linha = session.scalar(select(SecretVersionModel))
        assert linha is not None
        assert SENHA_REAL.encode("utf-8") not in linha.ciphertext
        assert SENHA_REAL.encode("utf-8") not in linha.wrapped_dek

    def test_ciclo_completo_devolve_o_valor_original(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        cofre = vault_repo.add(_cofre())

        segredo = Secret(name=Slug("senha-root"), vault_id=cofre.id)
        segredo.add_version(crypto.encrypt(SENHA_REAL), created_by="u1")
        secret_repo.add(segredo)

        recuperado = secret_repo.get_in_vault(cofre.id, Slug("senha-root"))
        assert crypto.decrypt(recuperado.current_version.value) == SENHA_REAL

    def test_bytes_sobrevivem_ao_banco_sem_corrupcao(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        """Bytes com zeros e alto bit: se o driver mexer, a decifragem falha."""
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        cofre = vault_repo.add(_cofre())
        cifrado = crypto.encrypt("valor\x00com\xffbytes\x00estranhos")

        segredo = Secret(name=Slug("binario"), vault_id=cofre.id)
        segredo.add_version(cifrado, created_by="u1")
        secret_repo.add(segredo)

        lido = secret_repo.get_in_vault(cofre.id, Slug("binario")).current_version.value
        assert lido.ciphertext == cifrado.ciphertext
        assert lido.nonce == cifrado.nonce
        assert lido.wrapped_dek == cifrado.wrapped_dek

    def test_nome_duplicado_no_mesmo_cofre_e_conflito(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        cofre = vault_repo.add(_cofre())

        a = Secret(name=Slug("dup"), vault_id=cofre.id)
        a.add_version(crypto.encrypt("a"), created_by="u1")
        secret_repo.add(a)

        b = Secret(name=Slug("dup"), vault_id=cofre.id)
        b.add_version(crypto.encrypt("b"), created_by="u1")
        with pytest.raises(ConflictError):
            secret_repo.add(b)

    def test_mesmo_nome_em_cofres_diferentes_e_permitido(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        c1 = vault_repo.add(Vault(name=Slug("c1"), display_name="C1"))
        c2 = vault_repo.add(Vault(name=Slug("c2"), display_name="C2"))

        for cofre in (c1, c2):
            s = Secret(name=Slug("senha-root"), vault_id=cofre.id)
            s.add_version(crypto.encrypt("x"), created_by="u1")
            secret_repo.add(s)

        assert secret_repo.get_in_vault(c1.id, Slug("senha-root")).vault_id == c1.id
        assert secret_repo.get_in_vault(c2.id, Slug("senha-root")).vault_id == c2.id

    def test_versao_duplicada_viola_constraint(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        """A constraint é a última linha de defesa do histórico."""
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        cofre = vault_repo.add(_cofre())
        segredo = Secret(name=Slug("s"), vault_id=cofre.id)
        v1 = segredo.add_version(crypto.encrypt("a"), created_by="u1")
        secret_repo.add(segredo)

        session.add(
            SecretVersionModel(
                secret_id=segredo.id,
                version=v1.version,  # mesma versão de novo
                ciphertext=b"x",
                nonce=b"n" * 12,
                wrapped_dek=b"d",
                key_id="k",
                created_by="u1",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()

    def test_versoes_voltam_em_ordem(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        cofre = vault_repo.add(_cofre())
        segredo = Secret(name=Slug("s"), vault_id=cofre.id)
        for texto in ("v1", "v2", "v3"):
            segredo.add_version(crypto.encrypt(texto), created_by="u1")
        secret_repo.add(segredo)

        lido = secret_repo.get_in_vault(cofre.id, Slug("s"))
        assert [v.version for v in lido.versions] == [1, 2, 3]
        assert crypto.decrypt(lido.current_version.value) == "v3"
        assert crypto.decrypt(lido.version_at(1).value) == "v1"

    def test_lixeira_some_da_listagem_mas_e_recuperavel(
        self, session: Session, crypto: EnvelopeCryptoService
    ) -> None:
        vault_repo, secret_repo = VaultRepository(session), SecretRepository(session)
        cofre = vault_repo.add(_cofre())
        segredo = Secret(name=Slug("s"), vault_id=cofre.id)
        segredo.add_version(crypto.encrypt("x"), created_by="u1")
        secret_repo.add(segredo)

        segredo.soft_delete()
        secret_repo.save_trash_state(segredo)

        assert secret_repo.list_in_vault(cofre.id) == []
        na_lixeira = secret_repo.list_in_vault(cofre.id, include_deleted=True)
        assert len(na_lixeira) == 1
        assert na_lixeira[0].is_deleted


class TestPolicyRepository:
    def test_politica_sobrevive_ao_ciclo_com_capacidades(self, session: Session) -> None:
        repo = PolicyRepository(session)
        politica = Policy(
            name=Slug("leitura-contabil"),
            rules=[
                PolicyRule(
                    path=PolicyPath("cofres/contabil/*"),
                    capabilities=frozenset({Capability.READ, Capability.LIST}),
                ),
                PolicyRule(
                    path=PolicyPath("cofres/contabil/segredos/raiz"),
                    capabilities=frozenset({Capability.REVEAL}),
                    effect=Effect.DENY,
                ),
            ],
        )
        repo.add(politica)
        session.flush()

        from app.infrastructure.db.models import PolicyModel

        model = session.scalar(select(PolicyModel))
        assert model is not None
        assert len(model.rules) == 2
        efeitos = {r.effect for r in model.rules}
        assert efeitos == {"allow", "deny"}


class TestAuditRepository:
    def test_cadeia_persistida_continua_integra(self, session: Session) -> None:
        repo = AuditRepository(session)
        for i in range(5):
            repo.append(
                AuditEvent(
                    action=AuditAction.SECRET_REVEALED,
                    actor_id="u1",
                    actor_label="ana.souza@exemplo.com.br",
                    target_path=f"cofres/x/segredos/s{i}",
                )
            )
        assert verify_chain(repo.list_chain()) == []

    def test_sequencia_comeca_em_zero_e_avanca(self, session: Session) -> None:
        repo = AuditRepository(session)
        a = repo.append(AuditEvent(action=AuditAction.LOGIN_SUCCESS, actor_id="u1",
                                   actor_label="g", target_path="auth"))
        b = repo.append(AuditEvent(action=AuditAction.LOGOUT, actor_id="u1",
                                   actor_label="g", target_path="auth"))
        assert (a.sequence, b.sequence) == (0, 1)
        assert b.previous_hash == a.fingerprint()

    def test_sequencia_duplicada_viola_constraint(self, session: Session) -> None:
        """Sob concorrência, dois processos não podem ocupar a mesma posição."""
        from app.infrastructure.db.models import AuditEventModel

        repo = AuditRepository(session)
        repo.append(AuditEvent(action=AuditAction.LOGIN_SUCCESS, actor_id="u1",
                               actor_label="g", target_path="auth"))
        session.add(
            AuditEventModel(
                sequence=0,  # posição já ocupada
                previous_hash="0" * 64,
                action="login_sucesso",
                actor_label="g",
                target_path="auth",
                event_metadata={},
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()

    def test_adulteracao_no_banco_e_detectada(self, session: Session) -> None:
        """Simula quem tem UPDATE no banco: a verificação precisa acusar."""
        repo = AuditRepository(session)
        for i in range(4):
            repo.append(AuditEvent(action=AuditAction.SECRET_REVEALED, actor_id="u1",
                                   actor_label="g", target_path=f"cofres/x/s{i}"))
        session.flush()

        session.execute(
            text("UPDATE auditoria_eventos SET target_path = :novo WHERE sequence = 1"),
            {"novo": "cofres/inocente"},
        )
        session.flush()
        session.expire_all()

        assert verify_chain(repo.list_chain()), "a adulteração direta no banco passou"

    def test_ancora_persistida_pega_recostura(self, session: Session) -> None:
        repo = AuditRepository(session)
        eventos = [
            repo.append(AuditEvent(action=AuditAction.SECRET_REVEALED, actor_id="u1",
                                   actor_label="g", target_path=f"cofres/x/s{i}"))
            for i in range(4)
        ]
        from app.domain.audit.events import ChainAnchor

        repo.add_anchor(ChainAnchor(sequence=2, fingerprint=eventos[2].fingerprint()), "siem")
        session.flush()

        assert verify_chain(repo.list_chain(), anchors=repo.anchors()) == []
