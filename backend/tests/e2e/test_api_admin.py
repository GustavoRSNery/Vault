"""Testes das rotas de administração: pessoas, papéis e políticas.

O que cada bloco protege, e que falharia em silêncio:

- a área de administração não se abre para quem não tem ADMIN, e a tentativa
  negada deixa rastro (um painel aberto por engano não avisa ninguém);
- ninguém se desativa a si mesmo e deixa o sistema sem administrador;
- reiniciar MFA descarta o segredo, não apenas o booleano — reativar não pode
  reaproveitar material que saiu junto com o aparelho perdido;
- a simulação de política responde pelo mesmo motor que decide em produção;
- alterar política registra o antes e o depois, porque é mexer em acesso de
  gente e a revisão não pode depender de reconstruir o estado.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import EMAIL, SENHA, conceder

OUTRO_EMAIL = "ana@exemplo.com.br"
OUTRA_SENHA = "senha-forte-da-ana-2026"


def _outro_usuario(db: Session, *, mfa: bool = False) -> UserModel:
    user = UserModel(
        id="u2",
        email=OUTRO_EMAIL,
        full_name="Ana Souza",
        password_hash=Argon2PasswordHasher().hash(OUTRA_SENHA),
        is_active=True,
        mfa_enabled=mfa,
        mfa_secret_ciphertext=b"cifrado" if mfa else None,
        mfa_secret_nonce=b"n" * 12 if mfa else None,
        mfa_secret_wrapped_dek=b"dek" if mfa else None,
        mfa_key_id="local" if mfa else None,
    )
    db.add(user)
    db.commit()
    return user


class TestPortaDaAdministracao:
    def test_sem_admin_recebe_403_em_todas_as_rotas(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Permissão ampla em cofres não abre a administração."""
        conceder(db_session, usuario, "cofres/*", ["read", "reveal", "list", "admin"])

        for metodo, rota in [
            ("get", "/api/v1/admin/usuarios"),
            ("get", "/api/v1/admin/papeis"),
            ("get", "/api/v1/admin/politicas"),
        ]:
            resposta = getattr(client, metodo)(rota, headers=autenticado)
            assert resposta.status_code == 403, f"{rota}: {resposta.text}"

    def test_tentativa_negada_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Negativa sem rastro é o que interessa a quem sonda permissões."""
        client.get("/api/v1/admin/usuarios", headers=autenticado)

        eventos = db_session.scalars(
            select(AuditEventModel).where(AuditEventModel.action == "acesso_negado")
        ).all()
        assert len(eventos) == 1
        assert eventos[0].target_path == "admin"
        assert eventos[0].outcome == "falha"
        assert "listar usuários" in eventos[0].reason

    def test_com_admin_entra(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", ["admin"])
        resposta = client.get("/api/v1/admin/usuarios", headers=autenticado)
        assert resposta.status_code == 200
        assert [u["email"] for u in resposta.json()] == [EMAIL]


class TestContas:
    def test_desativar_a_propria_conta_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Senão o sistema fica sem administrador e só o banco recupera."""
        conceder(db_session, usuario, "admin", ["admin"])

        resposta = client.post(
            f"/api/v1/admin/usuarios/{usuario.id}/desativar", headers=autenticado
        )
        assert resposta.status_code == 422
        db_session.refresh(usuario)
        assert usuario.is_active is True

    def test_desativar_outro_invalida_o_acesso_dele(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Token continua válido criptograficamente; a conta é que não vale."""
        conceder(db_session, usuario, "admin", ["admin"])
        outro = _outro_usuario(db_session)

        login = client.post(
            "/api/v1/auth/login", json={"email": OUTRO_EMAIL, "password": OUTRA_SENHA}
        )
        token_dela = login.json()["tokens"]["access_token"]
        cabecalho_dela = {"Authorization": f"Bearer {token_dela}"}
        assert client.get("/api/v1/auth/me", headers=cabecalho_dela).status_code == 200

        desativar = client.post(
            f"/api/v1/admin/usuarios/{outro.id}/desativar", headers=autenticado
        )
        assert desativar.status_code == 200
        assert desativar.json()["is_active"] is False

        # O token dela não vale mais, mesmo sem ter expirado.
        assert client.get("/api/v1/auth/me", headers=cabecalho_dela).status_code == 401

    def test_reiniciar_mfa_descarta_o_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Zerar só o booleano deixaria o segredo vazado ainda válido."""
        conceder(db_session, usuario, "admin", ["admin"])
        outro = _outro_usuario(db_session, mfa=True)

        resposta = client.post(
            f"/api/v1/admin/usuarios/{outro.id}/reiniciar-mfa", headers=autenticado
        )
        assert resposta.status_code == 200
        assert resposta.json()["mfa_enabled"] is False

        db_session.refresh(outro)
        assert outro.mfa_secret_ciphertext is None
        assert outro.mfa_secret_nonce is None
        assert outro.mfa_secret_wrapped_dek is None
        assert outro.mfa_key_id is None

    def test_papeis_substituem_e_a_trilha_diz_o_que_saiu(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")
        conceder(
            db_session, usuario, "cofres/contabil", ["read"], nome_politica="p-contabil"
        )
        assert sorted(r.name for r in usuario.roles) == [
            "papel-p-admin",
            "papel-p-contabil",
        ]

        resposta = client.put(
            f"/api/v1/admin/usuarios/{usuario.id}/papeis",
            headers=autenticado,
            json={"roles": ["papel-p-admin"]},
        )
        assert resposta.status_code == 200
        assert resposta.json()["roles"] == ["papel-p-admin"]

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "usuario_papeis_alterados"
            )
        ).one()
        # O que saiu tem de estar legível na trilha, não só "houve alteração".
        assert "papel-p-contabil" in evento.reason

    def test_papel_inexistente_nao_apaga_os_atuais(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")

        resposta = client.put(
            f"/api/v1/admin/usuarios/{usuario.id}/papeis",
            headers=autenticado,
            json={"roles": ["papel-que-nao-existe"]},
        )
        assert resposta.status_code == 404
        db_session.refresh(usuario)
        assert sorted(r.name for r in usuario.roles) == ["papel-p-admin"]


class TestPoliticas:
    def test_listar_mostra_regras_e_quem_as_carrega(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")

        resposta = client.get("/api/v1/admin/politicas", headers=autenticado)
        assert resposta.status_code == 200
        politica = next(p for p in resposta.json() if p["name"] == "p-admin")
        assert politica["rules"] == [
            {"path": "admin", "capabilities": ["admin"], "effect": "allow"}
        ]
        assert politica["roles"] == ["papel-p-admin"]

    def test_simular_usa_o_motor_de_producao_e_nao_grava(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Negação vence, e a simulação precisa dizer isso antes de salvar."""
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")

        regras = [
            {"path": "cofres/*", "capabilities": ["reveal"], "effect": "allow"},
            {
                "path": "cofres/contabil/segredos/token-sefaz",
                "capabilities": ["reveal"],
                "effect": "deny",
            },
        ]

        negado = client.post(
            "/api/v1/admin/politicas/simular",
            headers=autenticado,
            json={
                "path": "cofres/contabil/segredos/token-sefaz",
                "capability": "reveal",
                "rules": regras,
            },
        )
        assert negado.status_code == 200
        assert negado.json()["permitido"] is False
        assert "Negado" in negado.json()["motivo"]

        permitido = client.post(
            "/api/v1/admin/politicas/simular",
            headers=autenticado,
            json={
                "path": "cofres/contabil/segredos/outro",
                "capability": "reveal",
                "rules": regras,
            },
        )
        assert permitido.json()["permitido"] is True

        # Simular não cria política nenhuma.
        listagem = client.get("/api/v1/admin/politicas", headers=autenticado)
        assert all(p["name"] != "simulacao" for p in listagem.json())

    def test_simulacao_respeita_fronteira_de_segmento(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """`cofres/conta` não pode cobrir `cofres/contabil` por prefixo de texto."""
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")

        resposta = client.post(
            "/api/v1/admin/politicas/simular",
            headers=autenticado,
            json={
                "path": "cofres/contabil",
                "capability": "read",
                "rules": [
                    {"path": "cofres/conta", "capabilities": ["read"], "effect": "allow"}
                ],
            },
        )
        assert resposta.json()["permitido"] is False

    def test_substituir_regras_registra_antes_e_depois(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")
        conceder(
            db_session, usuario, "cofres/contabil", ["read"], nome_politica="p-alvo"
        )

        resposta = client.put(
            "/api/v1/admin/politicas/p-alvo/regras",
            headers=autenticado,
            json={
                "rules": [
                    {
                        "path": "cofres/contabil/*",
                        "capabilities": ["read", "list"],
                        "effect": "allow",
                    }
                ]
            },
        )
        assert resposta.status_code == 200
        assert resposta.json()["rules"] == [
            {
                "path": "cofres/contabil/*",
                "capabilities": ["list", "read"],
                "effect": "allow",
            }
        ]

        evento = db_session.scalars(
            select(AuditEventModel).where(AuditEventModel.action == "politica_alterada")
        ).one()
        assert "Antes:" in evento.reason and "Depois:" in evento.reason
        assert "cofres/contabil(read)" in evento.reason

    def test_substituir_por_lista_vazia_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Política sem regra não é "sem acesso": é política inválida."""
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")
        conceder(
            db_session, usuario, "cofres/contabil", ["read"], nome_politica="p-alvo"
        )

        resposta = client.put(
            "/api/v1/admin/politicas/p-alvo/regras",
            headers=autenticado,
            json={"rules": []},
        )
        assert resposta.status_code == 422

        # A política continua valendo como antes.
        atual = client.get("/api/v1/admin/politicas/p-alvo", headers=autenticado)
        assert atual.json()["rules"] == [
            {"path": "cofres/contabil", "capabilities": ["read"], "effect": "allow"}
        ]

    def test_alterar_politica_muda_o_acesso_de_verdade(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O teste que amarra o editor ao efeito: negar aqui fecha a porta lá."""
        conceder(db_session, usuario, "admin", ["admin"], nome_politica="p-admin")
        conceder(
            db_session,
            usuario,
            "cofres/*",
            ["read", "reveal", "create", "list"],
            nome_politica="p-cofres",
        )
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "contabil", "display_name": "Contábil"},
        )
        client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=autenticado,
            json={"name": "token-sefaz", "value": "valor-secreto-2026"},
        )
        assert (
            client.post(
                "/api/v1/cofres/contabil/segredos/token-sefaz/revelar",
                headers=autenticado,
            ).status_code
            == 200
        )

        client.put(
            "/api/v1/admin/politicas/p-cofres/regras",
            headers=autenticado,
            json={
                "rules": [
                    {
                        "path": "cofres/*",
                        "capabilities": ["read", "reveal", "create", "list"],
                        "effect": "allow",
                    },
                    {
                        "path": "cofres/contabil/segredos/token-sefaz",
                        "capabilities": ["reveal"],
                        "effect": "deny",
                    },
                ]
            },
        )

        negado = client.post(
            "/api/v1/cofres/contabil/segredos/token-sefaz/revelar", headers=autenticado
        )
        assert negado.status_code == 403
        # E o resto do cofre segue acessível: a negativa foi pontual.
        assert (
            client.get(
                "/api/v1/cofres/contabil/segredos", headers=autenticado
            ).status_code
            == 200
        )
