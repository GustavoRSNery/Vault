"""Testes das rotas de inventário: dispositivos, credenciais e certificados.

O que estes testes protegem:

- a custódia é exclusiva através da API, não só no domínio — duas pessoas
  retirando a mesma credencial trocariam a senha em paralelo;
- devolução forçada exige ADMIN, senão a exclusividade não valeria nada;
- o caminho de política é separado do cofre: quem acompanha vencimento de
  certificado não ganha permissão de revelar senha por tabela;
- a listagem filtra no servidor — devolver tudo e esconder na tela deixaria
  os nomes legíveis para quem lesse a resposta da API;
- conflito de custódia vira evento: diz quem tentou pegar o que estava na mão
  de outra pessoa.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import conceder

OUTRO_EMAIL = "bruno@exemplo.com.br"
OUTRA_SENHA = "senha-forte-do-bruno-2026"

GESTAO = ["read", "list", "create", "update"]


def _segundo_usuario(db: Session) -> UserModel:
    user = UserModel(
        id="u9",
        email=OUTRO_EMAIL,
        full_name="Bruno Lima",
        password_hash=Argon2PasswordHasher().hash(OUTRA_SENHA),
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _login(client: TestClient, email: str, senha: str) -> dict[str, str]:
    resposta = client.post(
        "/api/v1/auth/login", json={"email": email, "password": senha}
    )
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['tokens']['access_token']}"}


def _dispositivo_com_credencial(
    client: TestClient, headers: dict[str, str]
) -> str:
    client.post(
        "/api/v1/dispositivos",
        headers=headers,
        json={
            "name": "fw-matriz",
            "display_name": "Firewall Matriz",
            "kind": "firewall",
            "address": "10.0.0.1",
            "tags": ["Produção", "crítico"],
        },
    )
    criada = client.post(
        "/api/v1/dispositivos/fw-matriz/credenciais",
        headers=headers,
        json={"name": "senha-admin", "username": "admin", "rotation_days": 90},
    )
    assert criada.status_code == 201, criada.text
    return criada.json()["id"]


class TestDispositivos:
    def test_cadastrar_normaliza_tags(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", GESTAO)
        resposta = client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={
                "name": "srv-01",
                "display_name": "Servidor 01",
                "kind": "servidor",
                "tags": ["Produção", " produção ", "Crítico"],
            },
        )
        assert resposta.status_code == 201
        assert resposta.json()["tags"] == ["crítico", "produção"]

    def test_sem_create_recebe_403_e_audita(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", ["read", "list"])
        resposta = client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv-01", "display_name": "Servidor 01"},
        )
        assert resposta.status_code == 403

        evento = db_session.scalars(
            select(AuditEventModel).where(AuditEventModel.action == "acesso_negado")
        ).one()
        assert evento.target_path == "dispositivos/srv-01"

    def test_permissao_de_cofre_nao_abre_dispositivo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Caminhos separados: acesso total a cofres não entrega o inventário."""
        conceder(
            db_session, usuario, "cofres/*",
            ["read", "reveal", "create", "update", "delete", "list", "admin"],
        )
        resposta = client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv-01", "display_name": "Servidor 01"},
        )
        assert resposta.status_code == 403

    def test_listagem_filtra_no_servidor(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O nome do que não se pode ver não aparece nem no corpo da resposta."""
        conceder(
            db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-tudo"
        )
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "fw-matriz", "display_name": "Firewall Matriz"},
        )
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv-rh", "display_name": "Servidor RH"},
        )

        bruno = _segundo_usuario(db_session)
        conceder(
            db_session, bruno, "dispositivos/fw-matriz", ["read", "list"],
            nome_politica="p-bruno",
        )
        dele = _login(client, OUTRO_EMAIL, OUTRA_SENHA)

        resposta = client.get("/api/v1/dispositivos", headers=dele)
        assert resposta.status_code == 200
        assert [d["name"] for d in resposta.json()] == ["fw-matriz"]
        assert "srv-rh" not in resposta.text
        assert "Servidor RH" not in resposta.text


class TestCustodia:
    def test_retirada_marca_em_custodia(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        cid = _dispositivo_com_credencial(client, autenticado)

        resposta = client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=autenticado,
            json={"reason": "Troca de senha programada", "hours": 4},
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["status"] == "em_custodia"
        assert corpo["custodia_aberta"]["reason"] == "Troca de senha programada"
        assert corpo["custodia_aberta"]["returned_at"] is None

    def test_segunda_retirada_e_recusada_pela_api(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A invariante que importa: duas pessoas não levam a mesma credencial."""
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        cid = _dispositivo_com_credencial(client, autenticado)
        client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=autenticado,
            json={"reason": "Primeira retirada", "hours": 4},
        )

        bruno = _segundo_usuario(db_session)
        conceder(
            db_session, bruno, "credenciais/*", GESTAO, nome_politica="p-bruno"
        )
        dele = _login(client, OUTRO_EMAIL, OUTRA_SENHA)

        segunda = client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=dele,
            json={"reason": "Também preciso", "hours": 2},
        )
        assert segunda.status_code == 409

    def test_conflito_de_custodia_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        cid = _dispositivo_com_credencial(client, autenticado)
        client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=autenticado,
            json={"reason": "Primeira", "hours": 4},
        )

        bruno = _segundo_usuario(db_session)
        conceder(
            db_session, bruno, "credenciais/*", GESTAO, nome_politica="p-bruno"
        )
        dele = _login(client, OUTRO_EMAIL, OUTRA_SENHA)
        client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=dele,
            json={"reason": "Segunda", "hours": 2},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "credencial_retirada_negada"
            )
        ).one()
        assert evento.actor_label == OUTRO_EMAIL
        assert evento.outcome == "falha"

    def test_terceiro_nao_devolve_sem_admin(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        cid = _dispositivo_com_credencial(client, autenticado)
        client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=autenticado,
            json={"reason": "Minha retirada", "hours": 4},
        )

        bruno = _segundo_usuario(db_session)
        conceder(
            db_session, bruno, "credenciais/*", GESTAO, nome_politica="p-bruno"
        )
        dele = _login(client, OUTRO_EMAIL, OUTRA_SENHA)

        # Sem force: o domínio recusa porque não foi ele que retirou.
        assert (
            client.post(
                f"/api/v1/credenciais/{cid}/devolver", headers=dele, json={}
            ).status_code
            == 409
        )
        # Com force, mas sem ADMIN: a política recusa.
        assert (
            client.post(
                f"/api/v1/credenciais/{cid}/devolver",
                headers=dele,
                json={"force": True},
            ).status_code
            == 403
        )

    def test_administrador_forca_devolucao_e_a_trilha_diz_de_quem(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Caso real: quem retirou saiu de férias com a credencial."""
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(
            db_session, usuario, "credenciais/*", [*GESTAO, "admin"],
            nome_politica="p-c",
        )
        cid = _dispositivo_com_credencial(client, autenticado)

        bruno = _segundo_usuario(db_session)
        conceder(
            db_session, bruno, "credenciais/*", GESTAO, nome_politica="p-bruno"
        )
        dele = _login(client, OUTRO_EMAIL, OUTRA_SENHA)
        client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=dele,
            json={"reason": "Retirada do Bruno", "hours": 4},
        )

        forcada = client.post(
            f"/api/v1/credenciais/{cid}/devolver",
            headers=autenticado,
            json={"force": True},
        )
        assert forcada.status_code == 200
        assert forcada.json()["status"] == "ativa"
        assert forcada.json()["custodia_aberta"] is None
        # O histórico preserva a retirada: devolver não apaga o fato.
        assert len(forcada.json()["historico"]) == 1
        assert forcada.json()["historico"][0]["returned_at"] is not None

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "credencial_devolvida"
            )
        ).one()
        assert OUTRO_EMAIL in evento.reason

    def test_retirar_exige_update_e_nao_apenas_read(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Retirar é assumir responsabilidade por trocar, não só consultar."""
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(
            db_session, usuario, "credenciais/*", ["read", "list", "create"],
            nome_politica="p-c",
        )
        cid = _dispositivo_com_credencial(client, autenticado)

        resposta = client.post(
            f"/api/v1/credenciais/{cid}/retirar",
            headers=autenticado,
            json={"reason": "Tentativa", "hours": 4},
        )
        assert resposta.status_code == 403


class TestRotacao:
    def test_credencial_nova_nasce_atrasada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Nunca rotacionada é o pior caso e não pode sair do relatório."""
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        _dispositivo_com_credencial(client, autenticado)

        lista = client.get("/api/v1/credenciais", headers=autenticado)
        credencial = lista.json()[0]
        assert credencial["atrasada"] is True
        assert credencial["last_rotated_at"] is None
        assert credencial["due_at"] is None

    def test_registrar_rotacao_zera_o_atraso(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        cid = _dispositivo_com_credencial(client, autenticado)

        resposta = client.post(
            f"/api/v1/credenciais/{cid}/rotacionar", headers=autenticado
        )
        assert resposta.status_code == 200
        assert resposta.json()["atrasada"] is False
        assert resposta.json()["last_rotated_at"] is not None
        # Faixa, nao valor exato: a API calcula contra o relogio real e
        # 90 dias cheios truncam para 89 quando passa um instante da rotacao.
        assert resposta.json()["dias_para_vencer"] in (89, 90)

    def test_prazo_zero_nunca_fica_atrasada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv-01", "display_name": "Servidor 01"},
        )
        criada = client.post(
            "/api/v1/dispositivos/srv-01/credenciais",
            headers=autenticado,
            json={"name": "chave-perpetua", "rotation_days": 0},
        )
        assert criada.json()["atrasada"] is False
        assert criada.json()["due_at"] is None

    def test_nome_repetido_no_mesmo_dispositivo_e_conflito(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", GESTAO, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", GESTAO, nome_politica="p-c")
        _dispositivo_com_credencial(client, autenticado)

        repetida = client.post(
            "/api/v1/dispositivos/fw-matriz/credenciais",
            headers=autenticado,
            json={"name": "senha-admin"},
        )
        assert repetida.status_code == 409


class TestCertificados:
    def _criar(
        self, client: TestClient, headers: dict[str, str], nome: str, dias: int
    ):
        agora = datetime.now(UTC)
        return client.post(
            "/api/v1/certificados",
            headers=headers,
            json={
                "name": nome,
                "display_name": f"{nome}.exemplo.com.br",
                "subject": f"CN={nome}.exemplo.com.br",
                "issuer": "Let's Encrypt",
                "not_before": (agora - timedelta(days=60)).isoformat(),
                "not_after": (agora + timedelta(days=dias)).isoformat(),
            },
        )

    def test_estado_acompanha_a_validade(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "certificados/*", GESTAO)

        assert self._criar(client, autenticado, "longe", 120).json()["estado"] == "valido"
        assert self._criar(client, autenticado, "perto", 10).json()["estado"] == "vencendo"
        assert (
            self._criar(client, autenticado, "venceu", -1).json()["estado"] == "vencido"
        )

    def test_listagem_ordena_pelo_que_vence_primeiro(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "certificados/*", GESTAO)
        self._criar(client, autenticado, "longe", 200)
        self._criar(client, autenticado, "perto", 5)
        self._criar(client, autenticado, "medio", 60)

        lista = client.get("/api/v1/certificados", headers=autenticado)
        assert [c["name"] for c in lista.json()] == ["perto", "medio", "longe"]

    def test_validade_invertida_e_recusada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "certificados/*", GESTAO)
        agora = datetime.now(UTC)
        resposta = client.post(
            "/api/v1/certificados",
            headers=autenticado,
            json={
                "name": "invertido",
                "display_name": "x",
                "subject": "CN=x",
                "issuer": "CA",
                "not_before": agora.isoformat(),
                "not_after": (agora - timedelta(days=1)).isoformat(),
            },
        )
        assert resposta.status_code == 422

    def test_ver_certificado_nao_da_acesso_a_cofre(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Quem acompanha vencimento não ganha permissão de revelar senha."""
        conceder(db_session, usuario, "certificados/*", GESTAO)
        self._criar(client, autenticado, "api", 30)

        assert client.get("/api/v1/certificados", headers=autenticado).status_code == 200
        assert client.get("/api/v1/cofres", headers=autenticado).json() == []
