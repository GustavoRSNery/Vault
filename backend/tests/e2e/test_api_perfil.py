"""Testes das rotas do próprio perfil.

O que estes testes protegem acima de tudo: **trocar senha e e-mail exige a
senha atual**. Sem isso, um token de acesso roubado viraria tomada definitiva
da conta — o atacante troca as duas coisas e tranca a pessoa fora do próprio
cofre. É a diferença entre "acesso temporário" e "perda da conta".
"""

from __future__ import annotations

import base64
import zlib

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import EMAIL, SENHA

PERFIL = "/api/v1/perfil"


# ------------------------------------------------------------------ fixtures


def _png(largura: int = 1, altura: int = 1, lixo: bytes = b"") -> str:
    """Um PNG real, pequeno, como data URI.

    Construído byte a byte em vez de embutir um base64 opaco: assim o teste
    diz o que é a imagem, e `lixo` permite inflá-la para testar o limite de
    tamanho sem depender de um arquivo externo.
    """

    def chunk(tipo: bytes, dados: bytes) -> bytes:
        return (
            len(dados).to_bytes(4, "big")
            + tipo
            + dados
            + zlib.crc32(tipo + dados).to_bytes(4, "big")
        )

    ihdr = (
        largura.to_bytes(4, "big")
        + altura.to_bytes(4, "big")
        + bytes([8, 2, 0, 0, 0])
    )
    corpo = zlib.compress(b"\x00" + b"\xff\x00\x00" * largura)
    bruto = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", corpo)
        + (chunk(b"teXt", lixo) if lixo else b"")
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(bruto).decode()


def _eventos(db: Session, acao: str) -> list[AuditEventModel]:
    return (
        db.query(AuditEventModel)
        .filter(AuditEventModel.action == acao)
        .order_by(AuditEventModel.sequence)
        .all()
    )


# -------------------------------------------------------------------- leitura


class TestLerPerfil:
    def test_devolve_meus_dados(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.get(PERFIL, headers=autenticado)
        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert corpo["email"] == EMAIL
        assert corpo["full_name"] == "Ana Souza"
        assert corpo["apelido"] == ""
        assert corpo["foto"] == ""

    def test_sem_token_e_401(self, client: TestClient) -> None:
        assert client.get(PERFIL).status_code == 401


# ------------------------------------------------------- edição cosmética


class TestEditarPerfil:
    def test_troca_nome(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        resposta = client.put(
            PERFIL, headers=autenticado, json={"full_name": "Ana Souza Nery"}
        )
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["full_name"] == "Ana Souza Nery"
        # Relê do banco: resposta certa com banco errado já aconteceu
        # neste projeto três vezes.
        db_session.expire_all()
        assert db_session.get(UserModel, "u1").full_name == "Ana Souza Nery"

    def test_define_e_limpa_apelido(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        client.put(PERFIL, headers=autenticado, json={"apelido": "Gu"})
        db_session.expire_all()
        assert db_session.get(UserModel, "u1").apelido == "Gu"

        # String vazia LIMPA; é o que distingue de `None` ("não mexer").
        client.put(PERFIL, headers=autenticado, json={"apelido": ""})
        db_session.expire_all()
        assert db_session.get(UserModel, "u1").apelido == ""

    def test_campo_ausente_nao_mexe_no_valor(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """`None` é "não mexer" — sem isso, editar o nome apagaria o apelido."""
        client.put(PERFIL, headers=autenticado, json={"apelido": "Gu"})
        client.put(PERFIL, headers=autenticado, json={"full_name": "Outro Nome"})
        db_session.expire_all()
        user = db_session.get(UserModel, "u1")
        assert user.full_name == "Outro Nome"
        assert user.apelido == "Gu"

    def test_nome_em_branco_e_recusado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """O nome identifica na trilha; em branco deixaria evento anônimo."""
        resposta = client.put(PERFIL, headers=autenticado, json={"full_name": "   "})
        assert resposta.status_code == 422, resposta.text

    def test_nao_exige_senha(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Dado cosmético: o pior que um token roubado faz é vandalismo."""
        resposta = client.put(PERFIL, headers=autenticado, json={"apelido": "X"})
        assert resposta.status_code == 200

    def test_trilha_guarda_o_valor_anterior(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """"Perfil alterado" sozinho não responde "qual era o nome antes"."""
        client.put(PERFIL, headers=autenticado, json={"full_name": "Ana Souza Nery"})
        eventos = _eventos(db_session, "perfil_alterado")
        assert len(eventos) == 1
        assert "Ana Souza" in eventos[0].reason
        assert "Ana Souza Nery" in eventos[0].reason

    def test_sem_mudanca_nao_gera_evento(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """Salvar sem mexer em nada não é alteração: poluiria a trilha."""
        client.put(PERFIL, headers=autenticado, json={"full_name": "Ana Souza"})
        assert _eventos(db_session, "perfil_alterado") == []


# ----------------------------------------------------------------------- foto


class TestFoto:
    def test_aceita_png(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        resposta = client.put(PERFIL, headers=autenticado, json={"foto": _png()})
        assert resposta.status_code == 200, resposta.text
        db_session.expire_all()
        assert db_session.get(UserModel, "u1").foto.startswith("data:image/png")

    def test_remove_foto_com_string_vazia(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        client.put(PERFIL, headers=autenticado, json={"foto": _png()})
        client.put(PERFIL, headers=autenticado, json={"foto": ""})
        db_session.expire_all()
        assert db_session.get(UserModel, "u1").foto == ""

    def test_recusa_svg(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """SVG carrega script: seria XSS armazenado com cara de foto.

        Este é o teste que impede alguém de "acrescentar SVG porque é leve".
        """
        svg = base64.b64encode(
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        ).decode()
        resposta = client.put(
            PERFIL,
            headers=autenticado,
            json={"foto": f"data:image/svg+xml;base64,{svg}"},
        )
        assert resposta.status_code == 422, resposta.text
        assert "svg" in resposta.text.lower()

    def test_recusa_conteudo_que_mente_o_tipo(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Cabeçalho diz PNG, bytes dizem outra coisa.

        Sem conferir a assinatura, o campo viraria um lugar para guardar
        conteúdo arbitrário com rótulo de imagem.
        """
        falso = base64.b64encode(b"<html><script>alert(1)</script></html>").decode()
        resposta = client.put(
            PERFIL, headers=autenticado, json={"foto": f"data:image/png;base64,{falso}"}
        )
        assert resposta.status_code == 422, resposta.text
        assert "não parece" in resposta.text or "nao parece" in resposta.text

    def test_recusa_base64_invalido(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.put(
            PERFIL, headers=autenticado, json={"foto": "data:image/png;base64,$$$"}
        )
        assert resposta.status_code == 422

    def test_recusa_sem_data_uri(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.put(
            PERFIL, headers=autenticado, json={"foto": "https://exemplo.com/foto.png"}
        )
        assert resposta.status_code == 422

    def test_recusa_foto_grande(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """A foto viaja em toda resposta de perfil: megabytes pesam na tela."""
        grande = _png(lixo=b"A" * (600 * 1024))
        resposta = client.put(PERFIL, headers=autenticado, json={"foto": grande})
        assert resposta.status_code == 422, resposta.text
        assert "KB" in resposta.text

    def test_trilha_nao_guarda_o_conteudo_da_foto(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """Centenas de KB de base64 por evento inflariam a trilha."""
        client.put(PERFIL, headers=autenticado, json={"foto": _png()})
        eventos = _eventos(db_session, "perfil_alterado")
        assert len(eventos) == 1
        assert "base64" not in eventos[0].reason
        assert "foto trocada" in eventos[0].reason


# -------------------------------------------------------------------- e-mail


class TestTrocarEmail:
    def test_troca_com_senha_correta(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        resposta = client.put(
            f"{PERFIL}/email",
            headers=autenticado,
            json={"novo_email": "novo@empresa.com.br", "senha_atual": SENHA},
        )
        assert resposta.status_code == 200, resposta.text
        db_session.expire_all()
        assert db_session.get(UserModel, "u1").email == "novo@empresa.com.br"

    def test_sem_senha_correta_e_401(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """O teste central: token roubado não troca o e-mail."""
        resposta = client.put(
            f"{PERFIL}/email",
            headers=autenticado,
            json={"novo_email": "ladrao@exemplo.com", "senha_atual": "chute"},
        )
        assert resposta.status_code == 401, resposta.text
        db_session.expire_all()
        assert db_session.get(UserModel, "u1").email == EMAIL

    def test_tentativa_recusada_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """Tentativa de tomada de conta é o evento que mais importa ver."""
        client.put(
            f"{PERFIL}/email",
            headers=autenticado,
            json={"novo_email": "ladrao@exemplo.com", "senha_atual": "chute"},
        )
        eventos = _eventos(db_session, "perfil_email_alterado")
        assert len(eventos) == 1
        assert eventos[0].outcome == "falha"

    def test_trilha_guarda_o_email_antigo(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """Sem ele, a trilha de ontem aponta para endereço que não existe mais."""
        client.put(
            f"{PERFIL}/email",
            headers=autenticado,
            json={"novo_email": "novo@empresa.com.br", "senha_atual": SENHA},
        )
        eventos = _eventos(db_session, "perfil_email_alterado")
        assert len(eventos) == 1
        assert EMAIL in eventos[0].reason
        assert "novo@empresa.com.br" in eventos[0].reason

    def test_email_de_outra_conta_e_conflito(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        from app.infrastructure.crypto.passwords import Argon2PasswordHasher

        db_session.add(
            UserModel(
                id="u2",
                email="outra@empresa.com.br",
                full_name="Outra Pessoa",
                password_hash=Argon2PasswordHasher().hash("x" * 14),
                is_active=True,
            )
        )
        db_session.commit()

        resposta = client.put(
            f"{PERFIL}/email",
            headers=autenticado,
            json={"novo_email": "outra@empresa.com.br", "senha_atual": SENHA},
        )
        assert resposta.status_code == 409, resposta.text

    def test_login_passa_a_usar_o_email_novo(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Prova que a troca mexeu na identidade de login de verdade."""
        client.put(
            f"{PERFIL}/email",
            headers=autenticado,
            json={"novo_email": "novo@empresa.com.br", "senha_atual": SENHA},
        )
        antigo = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
        )
        assert antigo.status_code == 401
        novo = client.post(
            "/api/v1/auth/login",
            json={"email": "novo@empresa.com.br", "password": SENHA},
        )
        assert novo.status_code == 200, novo.text


# --------------------------------------------------------------------- senha


class TestTrocarSenha:
    def test_troca_com_senha_atual_correta(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        nova = "senha-nova-bem-longa-123"
        resposta = client.put(
            f"{PERFIL}/senha",
            headers=autenticado,
            json={"senha_atual": SENHA, "nova_senha": nova},
        )
        assert resposta.status_code == 204, resposta.text

        # A prova real: a senha nova entra e a antiga não.
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": EMAIL, "password": nova}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
            ).status_code
            == 401
        )

    def test_senha_atual_errada_e_401(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """O teste central: token roubado não troca a senha."""
        resposta = client.put(
            f"{PERFIL}/senha",
            headers=autenticado,
            json={"senha_atual": "chute", "nova_senha": "outra-senha-longa-123"},
        )
        assert resposta.status_code == 401, resposta.text
        # A senha antiga continua valendo: nada foi trocado.
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
            ).status_code
            == 200
        )

    def test_senha_curta_e_recusada(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.put(
            f"{PERFIL}/senha",
            headers=autenticado,
            json={"senha_atual": SENHA, "nova_senha": "curta"},
        )
        assert resposta.status_code == 422

    def test_senha_igual_a_atual_e_recusada(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Trocar por ela mesma dá impressão de rotação sem rotacionar nada."""
        resposta = client.put(
            f"{PERFIL}/senha",
            headers=autenticado,
            json={"senha_atual": SENHA, "nova_senha": SENHA},
        )
        assert resposta.status_code == 422, resposta.text

    def test_trilha_nao_guarda_a_senha_nem_seu_tamanho(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """Quem lê a trilha não deve ganhar vantagem sobre a senha."""
        nova = "senha-nova-bem-longa-123"
        client.put(
            f"{PERFIL}/senha",
            headers=autenticado,
            json={"senha_atual": SENHA, "nova_senha": nova},
        )
        eventos = _eventos(db_session, "perfil_senha_alterada")
        assert len(eventos) == 1
        texto = (eventos[0].reason or "") + (eventos[0].target_path or "")
        assert nova not in texto
        assert SENHA not in texto
        assert str(len(nova)) not in texto

    def test_tentativa_recusada_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        client.put(
            f"{PERFIL}/senha",
            headers=autenticado,
            json={"senha_atual": "chute", "nova_senha": "outra-senha-longa-123"},
        )
        eventos = _eventos(db_session, "perfil_senha_alterada")
        assert len(eventos) == 1
        assert eventos[0].outcome == "falha"


# ------------------------------------------------- isolamento entre contas


class TestIsolamento:
    def test_nenhuma_rota_aceita_id_de_outra_pessoa(
        self, client: TestClient, autenticado: dict[str, str], db_session: Session
    ) -> None:
        """O alvo vem do token, sempre.

        Não há parâmetro de id em rota nenhuma deste módulo — é o que impede
        que um bug de autorização vire edição de conta alheia. Este teste
        falha se alguém acrescentar a rota `/perfil/{id}`.
        """
        from app.infrastructure.crypto.passwords import Argon2PasswordHasher

        db_session.add(
            UserModel(
                id="u2",
                email="outra@empresa.com.br",
                full_name="Outra Pessoa",
                password_hash=Argon2PasswordHasher().hash("x" * 14),
                is_active=True,
            )
        )
        db_session.commit()

        tentativas = (
            client.put(
                f"{PERFIL}/u2", headers=autenticado, json={"full_name": "Invadido"}
            ),
            client.get(f"{PERFIL}/u2", headers=autenticado),
            client.put(
                f"{PERFIL}/u2/senha",
                headers=autenticado,
                json={"senha_atual": SENHA, "nova_senha": "tomada-de-conta-123"},
            ),
        )
        for resposta in tentativas:
            assert resposta.status_code in (404, 405), (
                f"{resposta.request.method} {resposta.request.url.path} respondeu "
                f"{resposta.status_code}: existe rota aceitando id de outra pessoa"
            )

        db_session.expire_all()
        assert db_session.get(UserModel, "u2").full_name == "Outra Pessoa"
