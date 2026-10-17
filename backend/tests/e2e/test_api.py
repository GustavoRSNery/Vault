"""Testes end-to-end da API.

Aqui se prova o que só aparece com a pilha inteira montada: status HTTP
corretos, RBAC aplicado na borda, auditoria sobrevivendo ao rollback da
requisição e segredo não vazando em resposta de erro.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import EMAIL, SENHA, conceder

SEGREDO_REAL = "senha-do-root-producao-2026"


class TestSaude:
    def test_saude_responde(self, client: TestClient) -> None:
        resposta = client.get("/saude")
        assert resposta.status_code == 200
        assert resposta.json()["status"] == "ok"


class TestLoginEndpoint:
    def test_login_devolve_tokens(self, client: TestClient, usuario: UserModel) -> None:
        resposta = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["mfa_required"] is False
        assert corpo["tokens"]["token_type"] == "bearer"
        assert corpo["tokens"]["access_token"]

    def test_senha_errada_da_401(self, client: TestClient, usuario: UserModel) -> None:
        resposta = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "errada"}
        )
        assert resposta.status_code == 401
        assert resposta.json()["erro"]["codigo"] == "nao_autenticado"

    def test_email_inexistente_responde_igual(
        self, client: TestClient, usuario: UserModel
    ) -> None:
        """Mesmo status E mesma mensagem: nada distingue os dois casos."""
        errada = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "errada"}
        )
        inexistente = client.post(
            "/api/v1/auth/login",
            json={"email": "ninguem@exemplo.com.br", "password": SENHA},
        )
        assert errada.status_code == inexistente.status_code == 401
        assert errada.json() == inexistente.json()

    def test_email_malformado_da_422(self, client: TestClient) -> None:
        resposta = client.post(
            "/api/v1/auth/login", json={"email": "nao-e-email", "password": "x"}
        )
        assert resposta.status_code == 422

    def test_resposta_de_erro_nao_contem_a_senha(
        self, client: TestClient, usuario: UserModel
    ) -> None:
        resposta = client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": "minha-senha-tentada"},
        )
        assert "minha-senha-tentada" not in resposta.text


class TestMe:
    def test_me_com_token_valido(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.get("/api/v1/auth/me", headers=autenticado)
        assert resposta.status_code == 200
        assert resposta.json()["email"] == EMAIL

    def test_me_sem_token_da_401(self, client: TestClient) -> None:
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_com_token_invalido_da_401(self, client: TestClient) -> None:
        resposta = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer lixo.nao.e.jwt"}
        )
        assert resposta.status_code == 401

    def test_esquema_errado_da_401(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        token = autenticado["Authorization"].split(" ")[1]
        resposta = client.get("/api/v1/auth/me", headers={"Authorization": f"Basic {token}"})
        assert resposta.status_code == 401

    def test_conta_desativada_perde_acesso_na_hora(
        self,
        client: TestClient,
        autenticado: dict[str, str],
        usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O token continua válido; a conta, não. O acesso deve cair na hora."""
        assert client.get("/api/v1/auth/me", headers=autenticado).status_code == 200

        usuario.is_active = False
        db_session.commit()

        assert client.get("/api/v1/auth/me", headers=autenticado).status_code == 401


class TestRefresh:
    def test_refresh_devolve_novo_par(
        self, client: TestClient, usuario: UserModel
    ) -> None:
        login = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
        ).json()
        resposta = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login["tokens"]["refresh_token"]},
        )
        assert resposta.status_code == 200
        assert resposta.json()["access_token"]

    def test_access_token_nao_serve_como_refresh(
        self, client: TestClient, usuario: UserModel
    ) -> None:
        """Confusão de tipo: o acesso não pode renovar a si mesmo."""
        login = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
        ).json()
        resposta = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login["tokens"]["access_token"]},
        )
        assert resposta.status_code == 401


class TestVaultRbac:
    def test_sem_politica_nao_ve_cofre_nenhum(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", ["create"])
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "contabil", "display_name": "Contábil"},
        )
        # Pode criar, mas não tem LIST nem READ: a lista vem vazia.
        resposta = client.get("/api/v1/cofres", headers=autenticado)
        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_criar_cofre_sem_permissao_da_403(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "proibido", "display_name": "Proibido"},
        )
        assert resposta.status_code == 403
        assert resposta.json()["erro"]["codigo"] == "permissao_negada"

    def test_criar_e_listar_com_permissao(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", ["create", "list", "read"])
        criacao = client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "contabil", "display_name": "Contábil"},
        )
        assert criacao.status_code == 201
        assert criacao.json()["state"] == "ativo"

        listagem = client.get("/api/v1/cofres", headers=autenticado)
        assert [c["name"] for c in listagem.json()] == ["contabil"]

    def test_cofre_duplicado_da_409(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", ["create", "list"])
        corpo = {"name": "contabil", "display_name": "Contábil"}
        assert client.post("/api/v1/cofres", headers=autenticado, json=corpo).status_code == 201
        segunda = client.post("/api/v1/cofres", headers=autenticado, json=corpo)
        assert segunda.status_code == 409

    def test_nome_invalido_da_422(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", ["create"])
        resposta = client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "Nome Com Espaço", "display_name": "X"},
        )
        assert resposta.status_code == 422


class TestSecretLifecycle:
    def _preparar(self, client, autenticado, usuario, db_session, capacidades):
        conceder(db_session, usuario, "cofres/*", capacidades)
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "contabil", "display_name": "Contábil"},
        )

    def test_criar_e_revelar_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        self._preparar(client, autenticado, usuario, db_session,
                       ["create", "list", "read", "reveal"])

        criacao = client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": SEGREDO_REAL, "kind": "senha"},
        )
        assert criacao.status_code == 201
        assert criacao.json()["current_version"] == 1

        revelacao = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )
        assert revelacao.status_code == 200
        assert revelacao.json()["value"] == SEGREDO_REAL

    def test_listar_nao_devolve_o_valor(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Listar não é revelar: o valor não pode aparecer no índice."""
        self._preparar(client, autenticado, usuario, db_session,
                       ["create", "list", "read", "reveal"])
        client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": SEGREDO_REAL},
        )

        listagem = client.get("/api/v1/cofres/contabil/segredos", headers=autenticado)
        assert listagem.status_code == 200
        assert SEGREDO_REAL not in listagem.text

    def test_revelar_sem_capacidade_da_403(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """READ e LIST não bastam para revelar."""
        self._preparar(client, autenticado, usuario, db_session,
                       ["create", "list", "read"])
        client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": SEGREDO_REAL},
        )

        revelacao = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )
        assert revelacao.status_code == 403
        assert SEGREDO_REAL not in revelacao.text

    def test_revelar_segredo_inexistente_da_404(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        self._preparar(client, autenticado, usuario, db_session,
                       ["create", "list", "read", "reveal"])
        resposta = client.post(
            "/api/v1/cofres/contabil/segredos/nao-existe/revelar", headers=autenticado
        )
        assert resposta.status_code == 404


class TestAuditSurvivesRollback:
    """A negação faz a requisição falhar — o registro dela não pode falhar junto."""

    def test_revelacao_negada_fica_registrada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", ["create", "list", "read"])
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "contabil", "display_name": "Contábil"},
        )
        client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": SEGREDO_REAL},
        )

        antes = db_session.scalars(select(AuditEventModel)).all()
        negada = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )
        assert negada.status_code == 403

        db_session.expire_all()
        depois = db_session.scalars(select(AuditEventModel)).all()
        assert len(depois) > len(antes), (
            "a tentativa negada não deixou rastro: o rollback apagou a auditoria"
        )
        assert depois[-1].action == "acesso_negado"
        assert depois[-1].outcome == "falha"

    def test_criacao_negada_fica_registrada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        negada = client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "proibido", "display_name": "Proibido"},
        )
        assert negada.status_code == 403

        db_session.expire_all()
        eventos = db_session.scalars(select(AuditEventModel)).all()
        assert any(e.action == "acesso_negado" for e in eventos)

    def test_auditoria_nunca_contem_o_valor_do_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*",
                 ["create", "list", "read", "reveal"])
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "contabil", "display_name": "Contábil"},
        )
        client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": SEGREDO_REAL},
        )
        client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )

        db_session.expire_all()
        for evento in db_session.scalars(select(AuditEventModel)).all():
            assert SEGREDO_REAL not in str(evento.event_metadata)
            assert SEGREDO_REAL not in evento.reason
            assert SEGREDO_REAL not in evento.target_path
