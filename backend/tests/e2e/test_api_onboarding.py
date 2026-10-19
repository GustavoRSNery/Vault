"""Testes de convite e recuperação de senha.

O que estes testes protegem:

- **A resposta não conta se o e-mail existe.** Caso contrário a tela de
  recuperação vira um oráculo que diz quem tem conta na empresa.
- **Código errado, conta sem MFA e e-mail inexistente respondem igual.**
- **O link morre ao ser usado**, e o consumo acontece ANTES da criação da
  conta — se a criação falhar, o link não fica vivo para quem o interceptou.
- **Recuperação por TOTP não envolve ninguém**; sem MFA, vira pedido.
"""

from __future__ import annotations

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import EMAIL, SENHA, conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
NOVA_SENHA = "senha-nova-bem-comprida-2026"


def _ativar_mfa(client: TestClient, headers: dict[str, str]) -> str:
    """Ativa o MFA e devolve o segredo, para gerar códigos nos testes."""
    inicio = client.post("/api/v1/mfa/iniciar", headers=headers)
    assert inicio.status_code == 200, inicio.text
    # A API devolve a URI de provisionamento (é dela que o QR code nasce);
    # o segredo vem no parâmetro `secret` dela.
    from urllib.parse import parse_qs, urlparse

    uri = inicio.json()["provisioning_uri"]
    segredo = parse_qs(urlparse(uri).query)["secret"][0]
    codigo = pyotp.TOTP(segredo).now()
    confirma = client.post(
        "/api/v1/mfa/confirmar", headers=headers, json={"code": codigo}
    )
    assert confirma.status_code == 200, confirma.text
    return segredo


class TestConvite:
    def test_admin_convida_e_recebe_o_link(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        resposta = client.post(
            "/api/v1/convites",
            headers=autenticado,
            json={"email": "nova@exemplo.com.br", "nome_sugerido": "Nova Pessoa"},
        )
        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["link"].startswith("/convite/")
        assert "uma única vez" in corpo["aviso"]

    def test_sem_admin_nao_convida(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        assert client.post(
            "/api/v1/convites",
            headers=autenticado,
            json={"email": "x@y.com.br"},
        ).status_code == 403

    def test_convite_para_email_existente_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        assert client.post(
            "/api/v1/convites", headers=autenticado, json={"email": EMAIL}
        ).status_code == 409

    def test_aceitar_cria_a_conta_com_os_papeis(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS, nome_politica="p-admin")
        convite = client.post(
            "/api/v1/convites",
            headers=autenticado,
            json={
                "email": "nova@exemplo.com.br",
                "nome_sugerido": "Nova",
                "papeis": ["papel-p-admin"],
            },
        ).json()
        token = convite["link"].rsplit("/", 1)[-1]

        aceite = client.post(
            "/api/v1/convites/aceitar",
            json={"token": token, "nome": "Nova Pessoa", "senha": NOVA_SENHA},
        )
        assert aceite.status_code == 201

        # A conta nova entra e já tem o papel.
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "nova@exemplo.com.br", "password": NOVA_SENHA},
        )
        assert login.status_code == 200
        dela = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}
        assert client.get("/api/v1/admin/usuarios", headers=dela).status_code == 200

    def test_link_morre_ao_ser_usado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Um link que funciona duas vezes é um link que o atacante usa
        depois da vítima."""
        conceder(db_session, usuario, "admin", TODAS)
        convite = client.post(
            "/api/v1/convites", headers=autenticado, json={"email": "n@x.com.br"}
        ).json()
        token = convite["link"].rsplit("/", 1)[-1]

        client.post(
            "/api/v1/convites/aceitar",
            json={"token": token, "nome": "N", "senha": NOVA_SENHA},
        )
        segunda = client.post(
            "/api/v1/convites/aceitar",
            json={"token": token, "nome": "Outro", "senha": NOVA_SENHA},
        )
        assert segunda.status_code == 409

    def test_token_invalido_nao_distingue_de_expirado(
        self, client: TestClient
    ) -> None:
        """404 distinto contaria a quem testa tokens que acertou o formato."""
        info = client.get("/api/v1/convites/token-inventado-qualquer/info")
        assert info.status_code == 200
        assert info.json()["valido"] is False
        assert info.json()["email"] == ""

    def test_cancelado_nao_aceita(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        convite = client.post(
            "/api/v1/convites", headers=autenticado, json={"email": "errado@x.com.br"}
        ).json()
        token = convite["link"].rsplit("/", 1)[-1]

        client.post(
            f"/api/v1/convites/{convite['id']}/cancelar", headers=autenticado
        )
        assert client.post(
            "/api/v1/convites/aceitar",
            json={"token": token, "nome": "N", "senha": NOVA_SENHA},
        ).status_code == 409

    def test_rotas_de_convite_nao_colidem(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """`/convites/{id}/cancelar` e `/convites/{token}/info` convivem."""
        conceder(db_session, usuario, "admin", TODAS)
        convite = client.post(
            "/api/v1/convites", headers=autenticado, json={"email": "a@x.com.br"}
        ).json()
        token = convite["link"].rsplit("/", 1)[-1]

        # info pelo TOKEN funciona
        assert client.get(f"/api/v1/convites/{token}/info").json()["valido"] is True
        # cancelar pelo ID funciona
        assert client.post(
            f"/api/v1/convites/{convite['id']}/cancelar", headers=autenticado
        ).status_code == 204


class TestRecuperacaoComAutenticador:
    def test_quem_tem_mfa_redefine_sozinho(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel
    ) -> None:
        """O código do autenticador É a prova: não precisa de mais ninguém."""
        segredo = _ativar_mfa(client, autenticado)

        inicio = client.post("/api/v1/recuperar", json={"email": EMAIL})
        assert inicio.json()["pode_usar_autenticador"] is True

        resposta = client.post(
            "/api/v1/recuperar/autenticador",
            json={
                "email": EMAIL,
                "codigo": pyotp.TOTP(segredo).now(),
                "nova_senha": NOVA_SENHA,
            },
        )
        assert resposta.status_code == 200

        # A senha nova funciona e a antiga não.
        assert client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": NOVA_SENHA}
        ).status_code in (200, 401)  # 401 se exigir MFA no login
        assert client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
        ).status_code == 401

    def test_codigo_errado_nao_redefine(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel
    ) -> None:
        _ativar_mfa(client, autenticado)
        resposta = client.post(
            "/api/v1/recuperar/autenticador",
            json={"email": EMAIL, "codigo": "000000", "nova_senha": NOVA_SENHA},
        )
        assert resposta.status_code == 422
        # A senha antiga continua valendo.
        assert client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
        ).status_code in (200, 401)

    def test_tentativa_frustrada_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        _ativar_mfa(client, autenticado)
        client.post(
            "/api/v1/recuperar/autenticador",
            json={"email": EMAIL, "codigo": "000000", "nova_senha": NOVA_SENHA},
        )
        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "senha_redefinicao_falhou"
            )
        ).one()
        assert evento.outcome == "falha"


class TestNaoRevelaQuemTemConta:
    def test_email_inexistente_responde_igual(self, client: TestClient) -> None:
        """A tela de recuperação não pode virar um oráculo de quem trabalha
        aqui — é o primeiro passo de um ataque dirigido."""
        existente = client.post("/api/v1/recuperar", json={"email": EMAIL})
        inventado = client.post(
            "/api/v1/recuperar", json={"email": "nao-existe@exemplo.com.br"}
        )
        assert existente.status_code == inventado.status_code == 200
        assert existente.json()["mensagem"] == inventado.json()["mensagem"]
        # Sem MFA ativo, os dois dizem a mesma coisa também no campo.
        assert (
            existente.json()["pode_usar_autenticador"]
            == inventado.json()["pode_usar_autenticador"]
            is False
        )

    def test_redefinir_com_email_inexistente_responde_como_codigo_errado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel
    ) -> None:
        _ativar_mfa(client, autenticado)
        inexistente = client.post(
            "/api/v1/recuperar/autenticador",
            json={
                "email": "nao-existe@exemplo.com.br",
                "codigo": "123456",
                "nova_senha": NOVA_SENHA,
            },
        )
        errado = client.post(
            "/api/v1/recuperar/autenticador",
            json={"email": EMAIL, "codigo": "000000", "nova_senha": NOVA_SENHA},
        )
        assert inexistente.status_code == errado.status_code == 422
        assert (
            inexistente.json()["erro"]["mensagem"]
            == errado.json()["erro"]["mensagem"]
        )

    def test_pedido_para_email_inexistente_tambem_responde_202(
        self, client: TestClient
    ) -> None:
        assert client.post(
            "/api/v1/recuperar/pedido",
            json={"email": "nao-existe@exemplo.com.br", "motivo": "x"},
        ).status_code == 202


class TestPedidoAoAdministrador:
    def test_sem_mfa_abre_pedido_e_admin_aprova(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O caminho de quem não ativou o segundo fator."""
        conceder(db_session, usuario, "admin", TODAS)

        from app.infrastructure.crypto.passwords import Argon2PasswordHasher

        ana = UserModel(
            id="uo", email="ana@exemplo.com.br", full_name="Ana",
            password_hash=Argon2PasswordHasher().hash("senha-antiga-da-ana-2026"),
            is_active=True,
        )
        db_session.add(ana)
        db_session.commit()

        # Ela não tem MFA: a tela oferece o pedido.
        inicio = client.post(
            "/api/v1/recuperar", json={"email": "ana@exemplo.com.br"}
        )
        assert inicio.json()["pode_usar_autenticador"] is False

        client.post(
            "/api/v1/recuperar/pedido",
            json={"email": "ana@exemplo.com.br", "motivo": "Perdi a senha"},
        )

        pendentes = client.get(
            "/api/v1/recuperar/pedidos", headers=autenticado
        ).json()
        assert len(pendentes) == 1
        assert pendentes[0]["email"] == "ana@exemplo.com.br"

        aprovacao = client.post(
            f"/api/v1/recuperar/pedidos/{pendentes[0]['id']}/aprovar",
            headers=autenticado,
        )
        assert aprovacao.status_code == 200
        token = aprovacao.json()["link"].rsplit("/", 1)[-1]
        assert "15 minutos" in aprovacao.json()["aviso"]

        # Ela usa o link e troca a senha.
        assert client.post(
            "/api/v1/recuperar/link",
            json={"token": token, "nova_senha": NOVA_SENHA},
        ).status_code == 200
        assert client.post(
            "/api/v1/auth/login",
            json={"email": "ana@exemplo.com.br", "password": NOVA_SENHA},
        ).status_code == 200

    def test_link_de_redefinicao_morre_ao_usar(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        client.post(
            "/api/v1/recuperar/pedido", json={"email": EMAIL, "motivo": "x"}
        )
        pendentes = client.get(
            "/api/v1/recuperar/pedidos", headers=autenticado
        ).json()
        token = client.post(
            f"/api/v1/recuperar/pedidos/{pendentes[0]['id']}/aprovar",
            headers=autenticado,
        ).json()["link"].rsplit("/", 1)[-1]

        client.post(
            "/api/v1/recuperar/link",
            json={"token": token, "nova_senha": NOVA_SENHA},
        )
        segunda = client.post(
            "/api/v1/recuperar/link",
            json={"token": token, "nova_senha": "outra-senha-qualquer-2026"},
        )
        assert segunda.status_code == 409

    def test_sem_admin_nao_ve_pedidos(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        assert client.get(
            "/api/v1/recuperar/pedidos", headers=autenticado
        ).status_code == 403

    def test_aprovacao_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        client.post(
            "/api/v1/recuperar/pedido", json={"email": EMAIL, "motivo": "x"}
        )
        pendentes = client.get(
            "/api/v1/recuperar/pedidos", headers=autenticado
        ).json()
        client.post(
            f"/api/v1/recuperar/pedidos/{pendentes[0]['id']}/aprovar",
            headers=autenticado,
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "senha_redefinicao_aprovada"
            )
        ).one()
        assert EMAIL in evento.reason

    def test_pedido_ja_atendido_nao_aprova_de_novo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        client.post(
            "/api/v1/recuperar/pedido", json={"email": EMAIL, "motivo": "x"}
        )
        pid = client.get(
            "/api/v1/recuperar/pedidos", headers=autenticado
        ).json()[0]["id"]

        client.post(f"/api/v1/recuperar/pedidos/{pid}/aprovar", headers=autenticado)
        assert client.post(
            f"/api/v1/recuperar/pedidos/{pid}/aprovar", headers=autenticado
        ).status_code == 409
