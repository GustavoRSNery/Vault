"""Testes da busca global e da central de alertas.

A busca é uma superfície de vazamento fácil de errar: o jeito simples é
varrer tudo e filtrar na tela, e aí quem lê a resposta da API descobre o que
existe fora do seu alcance. Pior ainda seria casar pelo valor do segredo —
por tentativa e erro, qualquer um extrairia a senha caractere a caractere.

Os alertas têm o mesmo risco: um feed que lista a pendência alheia conta ao
usuário o que ele não pode ver.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import UserModel

from .conftest import conceder

ANA_EMAIL = "ana@exemplo.com.br"
ANA_SENHA = "senha-forte-da-ana-2026"

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
SENHA_SECRETA = "zxq-valor-super-secreto-9981"


def _ana(db: Session) -> UserModel:
    user = UserModel(
        id="ub",
        email=ANA_EMAIL,
        full_name="Ana Souza",
        password_hash=Argon2PasswordHasher().hash(ANA_SENHA),
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _login(client: TestClient, email: str, senha: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _cenario(client: TestClient, headers: dict[str, str]) -> None:
    """Dois cofres, dois segredos, um dispositivo e um certificado."""
    for nome, visivel in [("contabil", "Contábil"), ("infraestrutura", "Infra")]:
        client.post(
            "/api/v1/cofres",
            headers=headers,
            json={"name": nome, "display_name": visivel},
        )
    client.post(
        "/api/v1/cofres/contabil/segredos",
        headers=headers,
        json={
            "name": "token-sefaz",
            "value": SENHA_SECRETA,
            "description": "Token de consulta da SEFAZ",
        },
    )
    client.post(
        "/api/v1/cofres/infraestrutura/segredos",
        headers=headers,
        json={
            "name": "senha-postgres",
            "value": "outra-senha-qualquer",
            "description": "Banco de produção",
        },
    )
    client.post(
        "/api/v1/dispositivos",
        headers=headers,
        json={"name": "fw-matriz", "display_name": "Firewall Matriz", "address": "10.0.0.1"},
    )
    agora = datetime.now(UTC)
    client.post(
        "/api/v1/certificados",
        headers=headers,
        json={
            "name": "api-rede",
            "display_name": "api.exemplo.com.br",
            "subject": "CN=api.exemplo.com.br",
            "issuer": "Let's Encrypt",
            "not_before": (agora - timedelta(days=60)).isoformat(),
            "not_after": (agora + timedelta(days=10)).isoformat(),
        },
    )


class TestBusca:
    def test_encontra_nos_varios_tipos(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p3")
        conceder(db_session, usuario, "certificados/*", TODAS, nome_politica="p4")
        _cenario(client, autenticado)

        achados = client.get("/api/v1/busca?termo=sefaz", headers=autenticado)
        assert achados.status_code == 200
        assert [r["tipo"] for r in achados.json()["resultados"]] == ["segredo"]

        rede = client.get("/api/v1/busca?termo=rede", headers=autenticado)
        assert "certificado" in [r["tipo"] for r in rede.json()["resultados"]]

        firewall = client.get("/api/v1/busca?termo=firewall", headers=autenticado)
        assert "dispositivo" in [r["tipo"] for r in firewall.json()["resultados"]]

    def test_nao_encontra_pelo_valor_do_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Casar por conteúdo permitiria extrair a senha por tentativa e erro."""
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        _cenario(client, autenticado)

        achados = client.get(
            f"/api/v1/busca?termo={SENHA_SECRETA[:12]}", headers=autenticado
        )
        assert achados.status_code == 200
        assert achados.json()["total"] == 0
        assert SENHA_SECRETA not in achados.text

    def test_nao_revela_o_que_esta_fora_do_alcance(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Zero resultados não pode significar algo diferente de "não existe"."""
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        _cenario(client, autenticado)

        ana = _ana(db_session)
        conceder(
            db_session, ana, "cofres/contabil", ["read", "list"],
            nome_politica="p-ana",
        )
        conceder(
            db_session, ana, "cofres/contabil/*", ["read", "list"],
            nome_politica="p-ana2",
        )
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        # Ela acha o que é dela.
        seus = client.get("/api/v1/busca?termo=sefaz", headers=dela)
        assert seus.json()["total"] == 1

        # E não acha o que não é. A asserção é sobre os RESULTADOS: o corpo
        # ecoa o termo buscado, então procurar a palavra no texto cru acusaria
        # o próprio eco como vazamento.
        alheios = client.get("/api/v1/busca?termo=postgres", headers=dela)
        assert alheios.json()["total"] == 0
        assert alheios.json()["resultados"] == []
        assert "Infra" not in alheios.text

    def test_termo_curto_e_recusado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Uma letra devolveria quase o acervo inteiro."""
        assert client.get("/api/v1/busca?termo=a", headers=autenticado).status_code == 422

    def test_busca_e_insensivel_a_caixa(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        _cenario(client, autenticado)

        assert client.get("/api/v1/busca?termo=SEFAZ", headers=autenticado).json()[
            "total"
        ] == 1


class TestAlertas:
    def test_certificado_vencendo_vira_alerta(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p3")
        conceder(db_session, usuario, "certificados/*", TODAS, nome_politica="p4")
        _cenario(client, autenticado)

        alertas = client.get("/api/v1/alertas", headers=autenticado)
        assert alertas.status_code == 200
        categorias = [i["categoria"] for i in alertas.json()["itens"]]
        assert "Certificado" in categorias

    def test_cofre_selado_vira_alerta_alto(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        _cenario(client, autenticado)
        client.post("/api/v1/cofres/contabil/selar", headers=autenticado)

        alertas = client.get("/api/v1/alertas", headers=autenticado).json()
        selado = [i for i in alertas["itens"] if i["categoria"] == "Cofre"]
        assert len(selado) == 1
        assert selado[0]["severidade"] == "alta"

    def test_alertas_ordenam_por_severidade(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        conceder(db_session, usuario, "certificados/*", TODAS, nome_politica="p4")
        _cenario(client, autenticado)
        client.post("/api/v1/cofres/contabil/selar", headers=autenticado)

        itens = client.get("/api/v1/alertas", headers=autenticado).json()["itens"]
        ordem = {"alta": 0, "media": 1, "baixa": 2}
        severidades = [ordem[i["severidade"]] for i in itens]
        assert severidades == sorted(severidades)

    def test_nao_lista_pendencia_que_o_usuario_nao_ve(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Feed que conta a pendência alheia revela o que não se pode ver."""
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        conceder(db_session, usuario, "certificados/*", TODAS, nome_politica="p4")
        _cenario(client, autenticado)
        client.post("/api/v1/cofres/infraestrutura/selar", headers=autenticado)

        ana = _ana(db_session)
        conceder(
            db_session, ana, "cofres/contabil", ["read", "list"],
            nome_politica="p-ana",
        )
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        alertas = client.get("/api/v1/alertas", headers=dela).json()
        assert alertas["total"] == 0
        assert "Infra" not in str(alertas)
        assert "api.rede" not in str(alertas)

    def test_acesso_temporario_ativo_aparece_como_baixa(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        _cenario(client, autenticado)

        ana = _ana(db_session)
        dela = _login(client, ANA_EMAIL, ANA_SENHA)
        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/contabil/segredos/token-sefaz",
                "capabilities": ["reveal"],
                "reason": "Emissão de guia",
                "hours": 4,
            },
        )
        client.post(
            f"/api/v1/solicitacoes/{pedido.json()['id']}/aprovar",
            headers=autenticado,
            json={},
        )

        alertas = client.get("/api/v1/alertas", headers=dela).json()
        temporarios = [
            i for i in alertas["itens"] if i["categoria"] == "Acesso temporário"
        ]
        assert len(temporarios) == 1
        assert temporarios[0]["severidade"] == "baixa"

    def test_pedido_pendente_aparece_para_quem_decide(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres", TODAS, nome_politica="p1")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p2")
        _cenario(client, autenticado)

        ana = _ana(db_session)
        dela = _login(client, ANA_EMAIL, ANA_SENHA)
        client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/contabil/segredos/token-sefaz",
                "capabilities": ["reveal"],
                "reason": "Emissão de guia",
                "hours": 4,
            },
        )

        alertas = client.get("/api/v1/alertas", headers=autenticado).json()
        aprovacoes = [i for i in alertas["itens"] if i["categoria"] == "Aprovação"]
        assert len(aprovacoes) == 1
        assert ANA_EMAIL in aprovacoes[0]["titulo"]

        # E não aparece para quem pediu.
        dela_alertas = client.get("/api/v1/alertas", headers=dela).json()
        assert all(i["categoria"] != "Aprovação" for i in dela_alertas["itens"])
