"""Isolamento entre carteiras: um usuário não enxerga o que é do outro.

Estes testes nasceram de um bug real encontrado no navegador: o cache do
frontend servia ao segundo usuário os cofres do primeiro depois de uma troca
de conta. A correção foi no front, mas a garantia precisa estar aqui — se a
API devolver o conjunto errado, nenhum cuidado na tela salva.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import (
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    UserModel,
)

from .conftest import EMAIL, SENHA, conceder

SENHA_OUTRO = "senha-forte-da-ana-2026"
EMAIL_OUTRO = "ana@exemplo.com.br"
TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]


@pytest.fixture
def ana(db_session: Session) -> UserModel:
    """Usuária restrita: só o cofre contábil, e com um segredo negado nele."""
    politica = PolicyModel(name="so-contabil", description="")
    politica.rules = [
        PolicyRuleModel(path="cofres/contabil", capabilities=["read", "list"],
                        effect="allow"),
        PolicyRuleModel(path="cofres/contabil/*",
                        capabilities=["read", "list", "reveal"], effect="allow"),
        # Negação pontual: prova que deny derruba o allow mais amplo acima.
        PolicyRuleModel(path="cofres/contabil/segredos/token-sefaz",
                        capabilities=["reveal"], effect="deny"),
    ]
    papel = RoleModel(name="contadora")
    papel.policies.append(politica)

    usuaria = UserModel(
        id="u-ana", email=EMAIL_OUTRO, full_name="Ana Contadora",
        password_hash=Argon2PasswordHasher().hash(SENHA_OUTRO), is_active=True,
    )
    usuaria.roles.append(papel)
    db_session.add_all([politica, papel, usuaria])
    db_session.commit()
    return usuaria


def _entrar(client: TestClient, email: str, senha: str) -> dict[str, str]:
    resposta = client.post("/api/v1/auth/login", json={"email": email, "password": senha})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['tokens']['access_token']}"}


def _montar_cofres(client: TestClient, admin: dict[str, str]) -> None:
    for nome, titulo in (("contabil", "Contábil"), ("infraestrutura", "Infraestrutura")):
        client.post("/api/v1/cofres", headers=admin,
                    json={"name": nome, "display_name": titulo})
    client.post("/api/v1/cofres/contabil/segredos", headers=admin,
                json={"name": "dominio-escrita", "value": "valor-permitido"})
    client.post("/api/v1/cofres/contabil/segredos", headers=admin,
                json={"name": "token-sefaz", "value": "valor-negado"})
    client.post("/api/v1/cofres/infraestrutura/segredos", headers=admin,
                json={"name": "postgres-producao", "value": "valor-de-outro-cofre"})


class TestIsolamentoEntreUsuarios:
    def test_cada_token_devolve_a_propria_carteira(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        ana: UserModel, db_session: Session,
    ) -> None:
        """O teste central: dois tokens, dois conjuntos diferentes."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _montar_cofres(client, autenticado)

        do_admin = client.get("/api/v1/cofres", headers=autenticado).json()
        da_ana = client.get(
            "/api/v1/cofres", headers=_entrar(client, EMAIL_OUTRO, SENHA_OUTRO)
        ).json()

        assert {c["name"] for c in do_admin} == {"contabil", "infraestrutura"}
        assert {c["name"] for c in da_ana} == {"contabil"}

    def test_trocar_de_conta_na_mesma_sessao_nao_mistura(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        ana: UserModel, db_session: Session,
    ) -> None:
        """Foi exatamente aqui que o bug apareceu: sair e entrar com outra conta."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _montar_cofres(client, autenticado)

        assert len(client.get("/api/v1/cofres", headers=autenticado).json()) == 2

        da_ana = client.get(
            "/api/v1/cofres", headers=_entrar(client, EMAIL_OUTRO, SENHA_OUTRO)
        )
        assert len(da_ana.json()) == 1
        assert "infraestrutura" not in da_ana.text

    def test_cofre_alheio_nao_se_abre_nem_pelo_endereco_direto(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        ana: UserModel, db_session: Session,
    ) -> None:
        """Esconder na lista não basta: a rota direta também tem de negar."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _montar_cofres(client, autenticado)
        headers = _entrar(client, EMAIL_OUTRO, SENHA_OUTRO)

        listagem = client.get(
            "/api/v1/cofres/infraestrutura/segredos", headers=headers
        )
        assert listagem.status_code == 403

        revelacao = client.post(
            "/api/v1/cofres/infraestrutura/segredos/postgres-producao/revelar",
            headers=headers,
        )
        assert revelacao.status_code == 403
        assert "valor-de-outro-cofre" not in revelacao.text

    def test_negacao_pontual_vence_a_permissao_ampla(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        ana: UserModel, db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _montar_cofres(client, autenticado)
        headers = _entrar(client, EMAIL_OUTRO, SENHA_OUTRO)

        permitido = client.post(
            "/api/v1/cofres/contabil/segredos/dominio-escrita/revelar", headers=headers
        )
        assert permitido.status_code == 200
        assert permitido.json()["value"] == "valor-permitido"

        negado = client.post(
            "/api/v1/cofres/contabil/segredos/token-sefaz/revelar", headers=headers
        )
        assert negado.status_code == 403
        assert "valor-negado" not in negado.text

    def test_token_de_um_nao_vale_para_a_conta_do_outro(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        ana: UserModel,
    ) -> None:
        """O token carrega a identidade: /me responde pelo dono, não pelo último login."""
        headers_ana = _entrar(client, EMAIL_OUTRO, SENHA_OUTRO)

        assert client.get("/api/v1/auth/me", headers=autenticado).json()["email"] == EMAIL
        assert (
            client.get("/api/v1/auth/me", headers=headers_ana).json()["email"]
            == EMAIL_OUTRO
        )

    def test_auditoria_nao_revela_a_atividade_do_outro(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        ana: UserModel, db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _montar_cofres(client, autenticado)

        trilha = client.get(
            "/api/v1/auditoria", headers=_entrar(client, EMAIL_OUTRO, SENHA_OUTRO)
        ).json()
        assert trilha["escopo"] == "proprios"
        assert all(e["actor_label"] == EMAIL_OUTRO for e in trilha["eventos"])
        assert "infraestrutura" not in str(trilha["eventos"])
