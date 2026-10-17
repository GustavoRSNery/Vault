"""Testes das rotas de gestão: versões, lixeira, selagem, MFA e auditoria.

Cada bloco cobre uma invariante que o produto promete e que, se quebrar,
quebra em silêncio: histórico que não se reescreve, lixeira que recupera,
selo que fecha de fato, MFA que não tranca o usuário para fora, e trilha
que não vaza a atividade alheia.
"""

from __future__ import annotations

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import UserModel

from .conftest import EMAIL, SENHA, conceder

SEGREDO_V1 = "senha-original-2026"
SEGREDO_V2 = "senha-rotacionada-2026"

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]


def _cofre_com_segredo(client: TestClient, headers: dict[str, str]) -> None:
    client.post("/api/v1/cofres", headers=headers,
                json={"name": "contabil", "display_name": "Contábil"})
    client.post("/api/v1/cofres/contabil/segredos", headers=headers,
                json={"name": "senha-root", "value": SEGREDO_V1})


class TestVersionamento:
    def test_nova_versao_incrementa_e_preserva_a_anterior(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)

        nova = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/versoes",
            headers=autenticado, json={"value": SEGREDO_V2},
        )
        assert nova.status_code == 201
        assert nova.json()["current_version"] == 2

        # Revelar devolve a versão corrente, não a antiga.
        revelado = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )
        assert revelado.json()["value"] == SEGREDO_V2
        assert revelado.json()["version"] == 2

    def test_historico_lista_versoes_sem_os_valores(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O histórico diz quando e por quem — nunca o quê."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)
        client.post("/api/v1/cofres/contabil/segredos/senha-root/versoes",
                    headers=autenticado, json={"value": SEGREDO_V2})

        historico = client.get(
            "/api/v1/cofres/contabil/segredos/senha-root/versoes", headers=autenticado
        )
        assert historico.status_code == 200
        versoes = historico.json()
        assert [v["version"] for v in versoes] == [2, 1]  # mais nova primeiro
        assert versoes[0]["is_current"] is True
        assert versoes[1]["is_current"] is False
        assert SEGREDO_V1 not in historico.text
        assert SEGREDO_V2 not in historico.text

    def test_nova_versao_sem_update_da_403(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*",
                 ["create", "list", "read", "reveal"])
        _cofre_com_segredo(client, autenticado)

        resposta = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/versoes",
            headers=autenticado, json={"value": SEGREDO_V2},
        )
        assert resposta.status_code == 403


class TestLixeira:
    def test_excluido_some_da_lista_e_aparece_na_lixeira(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)

        assert client.delete(
            "/api/v1/cofres/contabil/segredos/senha-root", headers=autenticado
        ).status_code == 200

        lista = client.get("/api/v1/cofres/contabil/segredos", headers=autenticado)
        assert lista.json() == []

        lixeira = client.get("/api/v1/cofres/contabil/lixeira", headers=autenticado)
        assert [s["name"] for s in lixeira.json()] == ["senha-root"]

    def test_restaurar_devolve_o_segredo_intacto(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Lixeira não destrói: o valor continua lá depois de voltar."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)
        client.delete("/api/v1/cofres/contabil/segredos/senha-root", headers=autenticado)

        restaurado = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/restaurar", headers=autenticado
        )
        assert restaurado.status_code == 200

        revelado = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )
        assert revelado.json()["value"] == SEGREDO_V1

    def test_excluir_sem_permissao_da_403(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*",
                 ["create", "list", "read", "reveal"])
        _cofre_com_segredo(client, autenticado)
        resposta = client.delete(
            "/api/v1/cofres/contabil/segredos/senha-root", headers=autenticado
        )
        assert resposta.status_code == 403


class TestSelagem:
    def test_cofre_selado_recusa_revelacao_com_423(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """423 Locked: o recurso existe, mas está fechado."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)

        assert client.post(
            "/api/v1/cofres/contabil/selar", headers=autenticado
        ).status_code == 200

        bloqueado = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )
        assert bloqueado.status_code == 423
        assert SEGREDO_V1 not in bloqueado.text

    def test_cofre_selado_recusa_escrita(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)
        client.post("/api/v1/cofres/contabil/selar", headers=autenticado)

        nova = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/versoes",
            headers=autenticado, json={"value": SEGREDO_V2},
        )
        assert nova.status_code == 423

    def test_desselar_devolve_o_acesso(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)
        client.post("/api/v1/cofres/contabil/selar", headers=autenticado)
        client.post("/api/v1/cofres/contabil/desselar", headers=autenticado)

        revelado = client.post(
            "/api/v1/cofres/contabil/segredos/senha-root/revelar", headers=autenticado
        )
        assert revelado.status_code == 200
        assert revelado.json()["value"] == SEGREDO_V1

    def test_selar_sem_admin_da_403(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*",
                 ["create", "list", "read", "reveal", "update", "delete"])
        _cofre_com_segredo(client, autenticado)
        assert client.post(
            "/api/v1/cofres/contabil/selar", headers=autenticado
        ).status_code == 403


class TestMfaEnrollment:
    def test_iniciar_nao_ativa_sozinho(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Ativar só depois de confirmar: senão o usuário se tranca para fora."""
        inicio = client.post("/api/v1/mfa/iniciar", headers=autenticado)
        assert inicio.status_code == 200
        assert inicio.json()["provisioning_uri"].startswith("otpauth://totp/")

        status = client.get("/api/v1/mfa/status", headers=autenticado)
        assert status.json()["mfa_enabled"] is False

    def test_confirmar_com_codigo_valido_ativa(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        uri = client.post("/api/v1/mfa/iniciar", headers=autenticado).json()[
            "provisioning_uri"
        ]
        segredo = pyotp.parse_uri(uri).secret  # type: ignore[attr-defined]
        codigo = pyotp.TOTP(segredo).now()

        confirmacao = client.post(
            "/api/v1/mfa/confirmar", headers=autenticado, json={"code": codigo}
        )
        assert confirmacao.status_code == 200
        assert confirmacao.json()["mfa_enabled"] is True

    def test_confirmar_com_codigo_errado_nao_ativa(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        client.post("/api/v1/mfa/iniciar", headers=autenticado)
        erro = client.post(
            "/api/v1/mfa/confirmar", headers=autenticado, json={"code": "000000"}
        )
        assert erro.status_code == 422
        assert client.get("/api/v1/mfa/status", headers=autenticado).json()[
            "mfa_enabled"
        ] is False

    def test_confirmar_sem_iniciar_e_recusado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.post(
            "/api/v1/mfa/confirmar", headers=autenticado, json={"code": "123456"}
        )
        assert resposta.status_code == 422

    def test_login_passa_a_exigir_o_codigo_depois_de_ativado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """O ciclo fecha: ativar MFA muda o login seguinte."""
        uri = client.post("/api/v1/mfa/iniciar", headers=autenticado).json()[
            "provisioning_uri"
        ]
        segredo = pyotp.parse_uri(uri).secret  # type: ignore[attr-defined]
        client.post("/api/v1/mfa/confirmar", headers=autenticado,
                    json={"code": pyotp.TOTP(segredo).now()})

        novo_login = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
        )
        assert novo_login.json()["mfa_required"] is True
        assert novo_login.json()["tokens"] is None


class TestAuditoriaApi:
    def test_sem_admin_ve_apenas_os_proprios_eventos(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A trilha não pode revelar a atividade dos colegas."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre_com_segredo(client, autenticado)

        outro = UserModel(id="u2", email="outro@exemplo.com.br", full_name="Outro",
                          password_hash="x", is_active=True)
        db_session.add(outro)
        db_session.commit()

        from app.domain.audit.events import AuditAction, AuditEvent
        from app.infrastructure.db.repositories import AuditRepository

        AuditRepository(db_session).append(
            AuditEvent(action=AuditAction.LOGIN_SUCCESS, actor_id="u2",
                       actor_label="outro@exemplo.com.br", target_path="auth/login")
        )
        db_session.commit()

        trilha = client.get("/api/v1/auditoria", headers=autenticado)
        assert trilha.status_code == 200
        assert trilha.json()["escopo"] == "proprios"
        assert all(
            e["actor_label"] != "outro@exemplo.com.br"
            for e in trilha.json()["eventos"]
        )

    def test_com_admin_ve_a_trilha_inteira(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "auditoria", ["admin"], nome_politica="auditor")
        trilha = client.get("/api/v1/auditoria", headers=autenticado)
        assert trilha.json()["escopo"] == "tudo"

    def test_eventos_vem_do_mais_recente_para_o_mais_antigo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        conceder(db_session, usuario, "auditoria", ["admin"], nome_politica="auditor")
        _cofre_com_segredo(client, autenticado)

        eventos = client.get("/api/v1/auditoria", headers=autenticado).json()["eventos"]
        sequencias = [e["sequence"] for e in eventos]
        assert sequencias == sorted(sequencias, reverse=True)

    def test_integridade_avisa_quando_nao_ha_ancora(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Selo verde sem âncora seria enganoso: a resposta tem de dizer isso."""
        conceder(db_session, usuario, "auditoria", ["admin"], nome_politica="auditor")
        resposta = client.get("/api/v1/auditoria/integridade", headers=autenticado)

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["integra"] is True
        assert corpo["ancoras_conferidas"] == 0
        assert corpo["aviso"] is not None
        assert "reescrita" in corpo["aviso"]

    def test_integridade_sem_admin_da_403(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        assert client.get(
            "/api/v1/auditoria/integridade", headers=autenticado
        ).status_code == 403

    def test_trilha_nunca_contem_valor_de_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        conceder(db_session, usuario, "auditoria", ["admin"], nome_politica="auditor")
        _cofre_com_segredo(client, autenticado)
        client.post("/api/v1/cofres/contabil/segredos/senha-root/revelar",
                    headers=autenticado)

        trilha = client.get("/api/v1/auditoria", headers=autenticado)
        assert SEGREDO_V1 not in trilha.text
