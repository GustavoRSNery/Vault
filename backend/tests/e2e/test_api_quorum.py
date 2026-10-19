"""Testes da selagem com quórum pela API.

O teste mais importante é `test_desselar_simples_nao_contorna_o_quorum`: sem
ele, quem tem ADMIN abriria o cofre pela rota antiga e o quórum não conteria
exatamente quem ele existe para conter.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
PORTADORES = ["ana@exemplo.com.br", "bruno@exemplo.com.br", "carla@exemplo.com.br"]


def _cofre(client: TestClient, headers: dict[str, str]) -> None:
    client.post(
        "/api/v1/cofres",
        headers=headers,
        json={"name": "contabil", "display_name": "Contábil"},
    )
    client.post(
        "/api/v1/cofres/contabil/segredos",
        headers=headers,
        json={"name": "token-sefaz", "value": "valor-secreto-2026"},
    )


def _selar(
    client: TestClient, headers: dict[str, str], limiar: int = 2
) -> list[str]:
    resposta = client.post(
        "/api/v1/cofres/contabil/selar-com-quorum",
        headers=headers,
        json={"portadores": PORTADORES, "limiar": limiar},
    )
    assert resposta.status_code == 200, resposta.text
    return [q["valor"] for q in resposta.json()["quinhoes"]]


class TestSelagem:
    def test_emite_quinhoes_uma_unica_vez(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)

        resposta = client.post(
            "/api/v1/cofres/contabil/selar-com-quorum",
            headers=autenticado,
            json={"portadores": PORTADORES, "limiar": 2},
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert len(corpo["quinhoes"]) == 3
        assert corpo["cofre"]["state"] == "selado"
        assert "uma única vez" in corpo["aviso"]

        # O selo é consultável, mas os quinhões não voltam nunca mais.
        selo = client.get("/api/v1/cofres/contabil/selo", headers=autenticado)
        assert selo.json()["limiar"] == 2
        # A consulta do selo não devolve os valores — só quantos e de quem.
        # (`total_quinhoes` contém a palavra, então a asserção é sobre os
        # VALORES, que são o que importa não vazar.)
        assert "valor" not in selo.json()
        for quinhao in corpo["quinhoes"]:
            assert quinhao["valor"] not in selo.text

    def test_limiar_de_um_e_recusado_pela_api(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)

        resposta = client.post(
            "/api/v1/cofres/contabil/selar-com-quorum",
            headers=autenticado,
            json={"portadores": PORTADORES, "limiar": 1},
        )
        assert resposta.status_code == 422

    def test_segunda_selagem_e_recusada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Dois conjuntos de quinhões válidos: o segundo abriria o cofre sem
        que os portadores do primeiro soubessem."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        _selar(client, autenticado)

        repetida = client.post(
            "/api/v1/cofres/contabil/selar-com-quorum",
            headers=autenticado,
            json={"portadores": PORTADORES, "limiar": 2},
        )
        assert repetida.status_code == 409

    def test_sem_admin_nao_sela(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", ["read", "list", "create"])
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "contabil", "display_name": "Contábil"},
        )
        resposta = client.post(
            "/api/v1/cofres/contabil/selar-com-quorum",
            headers=autenticado,
            json={"portadores": PORTADORES, "limiar": 2},
        )
        assert resposta.status_code == 403


class TestTravaDoQuorum:
    def test_desselar_simples_nao_contorna_o_quorum(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O teste que justifica o mecanismo.

        Quem tem ADMIN não pode abrir pela rota antiga um cofre que exige
        quórum — senão o quórum não conteria quem ele existe para conter.
        """
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        _selar(client, autenticado)

        resposta = client.post("/api/v1/cofres/contabil/desselar", headers=autenticado)
        assert resposta.status_code == 403
        assert "quinhões" in resposta.text

        # E o cofre continua fechado de verdade.
        revelar = client.post(
            "/api/v1/cofres/contabil/segredos/token-sefaz/revelar", headers=autenticado
        )
        assert revelar.status_code == 423

    def test_tentativa_de_contornar_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        _selar(client, autenticado)
        client.post("/api/v1/cofres/contabil/desselar", headers=autenticado)

        evento = db_session.scalars(
            select(AuditEventModel).where(AuditEventModel.action == "acesso_negado")
        ).all()[-1]
        assert "sem quórum" in evento.reason


class TestDesselagem:
    def test_o_limiar_exato_abre(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        quinhoes = _selar(client, autenticado, limiar=2)

        resposta = client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": quinhoes[:2]},
        )
        assert resposta.status_code == 200
        assert resposta.json()["state"] == "ativo"

        # E agora o segredo é legível de novo.
        revelar = client.post(
            "/api/v1/cofres/contabil/segredos/token-sefaz/revelar", headers=autenticado
        )
        assert revelar.status_code == 200
        assert revelar.json()["value"] == "valor-secreto-2026"

    def test_abaixo_do_limiar_nao_abre(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        quinhoes = _selar(client, autenticado, limiar=3)

        resposta = client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": quinhoes[:2]},
        )
        assert resposta.status_code == 409
        assert client.get(
            "/api/v1/cofres/contabil/selo", headers=autenticado
        ).json() is not None

    def test_quinhoes_forjados_nao_abrem(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        quinhoes = _selar(client, autenticado, limiar=2)

        forjado = "01" + "ab" * ((len(quinhoes[0]) - 2) // 2)
        resposta = client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": [forjado, quinhoes[1]]},
        )
        assert resposta.status_code == 409

    def test_tentativa_frustrada_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """É o evento que mais interessa numa revisão."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        quinhoes = _selar(client, autenticado, limiar=3)
        client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": quinhoes[:2]},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(AuditEventModel.action == "acesso_negado")
        ).all()[-1]
        assert "Quórum não atingido" in evento.reason

    def test_selo_usado_nao_abre_de_novo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Os quinhões valem para uma abertura: reusar exige selar de novo."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        quinhoes = _selar(client, autenticado, limiar=2)
        client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": quinhoes[:2]},
        )

        de_novo = client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": quinhoes[:2]},
        )
        assert de_novo.status_code == 409
        assert "não tem selo" in de_novo.text

    def test_abertura_registra_quantos_quinhoes(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        quinhoes = _selar(client, autenticado, limiar=2)
        client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": quinhoes[:2]},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(AuditEventModel.action == "cofre_desselado")
        ).one()
        assert "Quórum atingido" in evento.reason
        # Jamais o quinhão em si.
        for quinhao in quinhoes:
            assert quinhao not in evento.reason

    def test_sem_selo_ativo_a_rota_recusa(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)

        resposta = client.post(
            "/api/v1/cofres/contabil/desselar-com-quorum",
            headers=autenticado,
            json={"quinhoes": ["0100", "0200"]},
        )
        assert resposta.status_code == 409


class TestConsultaDoSelo:
    def test_sem_selo_devolve_nulo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        assert client.get(
            "/api/v1/cofres/contabil/selo", headers=autenticado
        ).json() is None

    def test_mostra_quem_precisa_ser_chamado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Não é segredo: esconder só atrapalha quem organiza a cerimônia."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        _cofre(client, autenticado)
        _selar(client, autenticado, limiar=2)

        selo = client.get("/api/v1/cofres/contabil/selo", headers=autenticado).json()
        assert selo["limiar"] == 2
        assert selo["total_quinhoes"] == 3
        assert selo["portadores"] == PORTADORES

    def test_sem_read_nao_consulta(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-tudo")
        _cofre(client, autenticado)
        _selar(client, autenticado)

        from app.infrastructure.crypto.passwords import Argon2PasswordHasher

        outro = UserModel(
            id="uq", email="ze@exemplo.com.br", full_name="Zé",
            password_hash=Argon2PasswordHasher().hash("senha-forte-do-ze-2026"),
            is_active=True,
        )
        db_session.add(outro)
        db_session.commit()
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "ze@exemplo.com.br", "password": "senha-forte-do-ze-2026"},
        )
        dele = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}

        assert client.get(
            "/api/v1/cofres/contabil/selo", headers=dele
        ).status_code == 403
