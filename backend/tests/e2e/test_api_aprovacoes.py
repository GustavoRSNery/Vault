"""Testes do fluxo de solicitação de acesso, de ponta a ponta.

O teste que justifica o arquivo é
`test_ciclo_completo_concede_acesso_real`: sem ele, o fluxo poderia aprovar
solicitações e não conceder nada — um botão que registra intenção e não muda
o mundo. Aqui a mesma chamada que dava 403 passa a dar 200 depois da
aprovação, e volta a dar 403 quando a concessão é revogada.

O segundo mais importante é `test_concessao_nao_fura_deny_pela_api`: a
precedência da negação precisa valer no HTTP, não só no domínio.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import EMAIL, SENHA, conceder

ANA_EMAIL = "ana@exemplo.com.br"
ANA_SENHA = "senha-forte-da-ana-2026"

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
SEGREDO = "valor-do-token-sefaz-2026"


def _ana(db: Session) -> UserModel:
    user = UserModel(
        id="ua",
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


def _cofre_com_segredo(client: TestClient, headers: dict[str, str]) -> None:
    client.post(
        "/api/v1/cofres",
        headers=headers,
        json={"name": "contabil", "display_name": "Contábil"},
    )
    client.post(
        "/api/v1/cofres/contabil/segredos",
        headers=headers,
        json={"name": "token-sefaz", "value": SEGREDO},
    )


class TestCicloCompleto:
    def test_ciclo_completo_concede_acesso_real(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Pedir → aprovar → revelar → revogar → não revelar mais.

        Sem este teste, o fluxo poderia aprovar e não conceder nada.
        """
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-admin")
        _cofre_com_segredo(client, autenticado)

        ana = _ana(db_session)
        # Ana só enxerga o cofre; revelar, não.
        conceder(
            db_session, ana, "cofres/contabil/*", ["read", "list"],
            nome_politica="p-ana",
        )
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        rota = "/api/v1/cofres/contabil/segredos/token-sefaz/revelar"
        assert client.post(rota, headers=dela).status_code == 403

        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/contabil/segredos/token-sefaz",
                "capabilities": ["reveal"],
                "reason": "Preciso emitir a guia de hoje",
                "hours": 4,
            },
        )
        assert pedido.status_code == 201
        assert pedido.json()["status"] == "pendente"
        assert pedido.json()["ativa"] is False
        pedido_id = pedido.json()["id"]

        # Pedir não concede nada por si.
        assert client.post(rota, headers=dela).status_code == 403

        aprovacao = client.post(
            f"/api/v1/solicitacoes/{pedido_id}/aprovar",
            headers=autenticado,
            json={"note": "Ok até o fim do dia"},
        )
        assert aprovacao.status_code == 200
        assert aprovacao.json()["status"] == "aprovada"
        assert aprovacao.json()["ativa"] is True

        # A MESMA chamada que dava 403 agora entrega o valor.
        revelado = client.post(rota, headers=dela)
        assert revelado.status_code == 200
        assert revelado.json()["value"] == SEGREDO

        revogacao = client.post(
            f"/api/v1/solicitacoes/{pedido_id}/revogar", headers=autenticado
        )
        assert revogacao.status_code == 200
        assert revogacao.json()["status"] == "revogada"

        # E fecha na hora.
        assert client.post(rota, headers=dela).status_code == 403

    def test_revelacao_por_concessao_fica_marcada_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Um REVEAL fora da política habitual é o que a revisão procura."""
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-admin")
        _cofre_com_segredo(client, autenticado)

        ana = _ana(db_session)
        conceder(
            db_session, ana, "cofres/contabil/*", ["read", "list"],
            nome_politica="p-ana",
        )
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/contabil/segredos/token-sefaz",
                "capabilities": ["reveal"],
                "reason": "Emissão de guia",
                "hours": 2,
            },
        )
        client.post(
            f"/api/v1/solicitacoes/{pedido.json()['id']}/aprovar",
            headers=autenticado,
            json={},
        )
        client.post(
            "/api/v1/cofres/contabil/segredos/token-sefaz/revelar", headers=dela
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "segredo_revelado",
                AuditEventModel.actor_label == ANA_EMAIL,
            )
        ).one()
        assert "concessão temporária" in evento.reason
        assert EMAIL in evento.reason  # quem aprovou
        assert SEGREDO not in evento.reason  # jamais o valor


class TestPrecedenciaDaNegacao:
    def test_concessao_nao_fura_deny_pela_api(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A precedência da negação precisa valer no HTTP, não só no domínio."""
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-admin")
        _cofre_com_segredo(client, autenticado)

        ana = _ana(db_session)
        conceder(
            db_session, ana, "cofres/contabil/*", ["read", "list", "reveal"],
            nome_politica="p-ana",
        )
        conceder(
            db_session, ana, "cofres/contabil/segredos/token-sefaz", ["reveal"],
            efeito="deny", nome_politica="p-ana-deny",
        )
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        rota = "/api/v1/cofres/contabil/segredos/token-sefaz/revelar"
        assert client.post(rota, headers=dela).status_code == 403

        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/contabil/segredos/token-sefaz",
                "capabilities": ["reveal"],
                "reason": "Urgente",
                "hours": 4,
            },
        )
        aprovacao = client.post(
            f"/api/v1/solicitacoes/{pedido.json()['id']}/aprovar",
            headers=autenticado,
            json={},
        )
        assert aprovacao.status_code == 200
        assert aprovacao.json()["ativa"] is True

        # Aprovada e ativa — e ainda assim negada, porque o deny vem primeiro.
        negado = client.post(rota, headers=dela)
        assert negado.status_code == 403

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "acesso_negado",
                AuditEventModel.actor_label == ANA_EMAIL,
            )
        ).all()[-1]
        assert "não é contornada por concessão" in evento.reason


class TestDecisao:
    def test_quem_pede_nao_aprova_nem_com_permissao(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Ter APPROVE não autoriza decidir o próprio pedido."""
        conceder(db_session, usuario, "cofres/*", TODAS)

        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=autenticado,
            json={
                "path": "cofres/contabil/segredos/x",
                "capabilities": ["reveal"],
                "reason": "Meu próprio pedido",
                "hours": 4,
            },
        )
        resposta = client.post(
            f"/api/v1/solicitacoes/{pedido.json()['id']}/aprovar",
            headers=autenticado,
            json={},
        )
        assert resposta.status_code == 409

    def test_sem_approve_nao_decide(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-admin")
        ana = _ana(db_session)
        conceder(
            db_session, ana, "cofres/contabil/*", ["read", "list"],
            nome_politica="p-ana",
        )
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=autenticado,
            json={
                "path": "cofres/contabil/segredos/x",
                "capabilities": ["reveal"],
                "reason": "Pedido do admin",
                "hours": 4,
            },
        )
        # Ana não tem APPROVE neste caminho.
        resposta = client.post(
            f"/api/v1/solicitacoes/{pedido.json()['id']}/aprovar",
            headers=dela,
            json={},
        )
        assert resposta.status_code == 403

    def test_decisao_nao_se_refaz(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-admin")
        ana = _ana(db_session)
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/contabil/segredos/x",
                "capabilities": ["reveal"],
                "reason": "Pedido",
                "hours": 4,
            },
        )
        pid = pedido.json()["id"]
        assert (
            client.post(
                f"/api/v1/solicitacoes/{pid}/negar", headers=autenticado, json={}
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/solicitacoes/{pid}/aprovar", headers=autenticado, json={}
            ).status_code
            == 409
        )

    def test_quem_pediu_devolve_o_proprio_acesso(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Devolver cedo nunca é risco; exigir aprovador faria durar mais."""
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-admin")
        ana = _ana(db_session)
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        pedido = client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/contabil/segredos/x",
                "capabilities": ["reveal"],
                "reason": "Pedido",
                "hours": 48,
            },
        )
        pid = pedido.json()["id"]
        client.post(
            f"/api/v1/solicitacoes/{pid}/aprovar", headers=autenticado, json={}
        )

        devolvida = client.post(f"/api/v1/solicitacoes/{pid}/revogar", headers=dela)
        assert devolvida.status_code == 200
        assert devolvida.json()["status"] == "revogada"


class TestFila:
    def test_fila_mostra_so_o_que_cabe_a_quem_olha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(
            db_session, usuario, "cofres/contabil/*", TODAS, nome_politica="p-cont"
        )
        ana = _ana(db_session)
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        for caminho in [
            "cofres/contabil/segredos/a",
            "cofres/infraestrutura/segredos/b",
        ]:
            client.post(
                "/api/v1/solicitacoes",
                headers=dela,
                json={
                    "path": caminho,
                    "capabilities": ["reveal"],
                    "reason": "Pedido",
                    "hours": 4,
                },
            )

        fila = client.get("/api/v1/solicitacoes/fila", headers=autenticado)
        assert fila.status_code == 200
        assert [p["path"] for p in fila.json()] == ["cofres/contabil/segredos/a"]

    def test_fila_nao_mostra_o_proprio_pedido(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Não adianta listar o que a decisão vai recusar."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        client.post(
            "/api/v1/solicitacoes",
            headers=autenticado,
            json={
                "path": "cofres/contabil/segredos/x",
                "capabilities": ["reveal"],
                "reason": "Meu pedido",
                "hours": 4,
            },
        )
        fila = client.get("/api/v1/solicitacoes/fila", headers=autenticado)
        assert fila.json() == []

    def test_minhas_solicitacoes_lista_so_as_minhas(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-admin")
        ana = _ana(db_session)
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/a/segredos/x",
                "capabilities": ["reveal"],
                "reason": "Da Ana",
                "hours": 4,
            },
        )
        client.post(
            "/api/v1/solicitacoes",
            headers=autenticado,
            json={
                "path": "cofres/b/segredos/y",
                "capabilities": ["reveal"],
                "reason": "Do admin",
                "hours": 4,
            },
        )

        minhas = client.get("/api/v1/solicitacoes", headers=dela)
        assert [p["reason"] for p in minhas.json()] == ["Da Ana"]
        assert "Do admin" not in minhas.text


class TestLimites:
    def test_acima_de_30_dias_manda_editar_a_politica(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        resposta = client.post(
            "/api/v1/solicitacoes",
            headers=autenticado,
            json={
                "path": "cofres/contabil/segredos/x",
                "capabilities": ["reveal"],
                "reason": "Quero para sempre",
                "hours": 721,
            },
        )
        assert resposta.status_code == 422

    def test_pedir_nao_exige_permissao_no_caminho(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Negar o pedido de quem não tem acesso tornaria o fluxo inútil."""
        ana = _ana(db_session)
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        resposta = client.post(
            "/api/v1/solicitacoes",
            headers=dela,
            json={
                "path": "cofres/secreto/segredos/tudo",
                "capabilities": ["reveal"],
                "reason": "Não tenho acesso nenhum, por isso peço",
                "hours": 4,
            },
        )
        assert resposta.status_code == 201


class TestAprovarEmLote:
    """Aprovar vários de uma vez é conveniência, não atalho.

    Cada pedido do lote passa pela mesma checagem de permissão e pela mesma
    regra de domínio da aprovação individual, e gera o seu próprio evento de
    auditoria — um evento único de "lote aprovado" esconderia *o que* foi
    concedido.
    """

    def _tres_pedidos(
        self, client: TestClient, db_session: Session, usuario: UserModel
    ) -> tuple[list[str], dict[str, str]]:
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-dono")
        _cofre_com_segredo(client, _login(client, EMAIL, SENHA))
        ana = _ana(db_session)
        conceder(
            db_session, ana, "cofres/contabil/*", ["read", "list"],
            nome_politica="p-ana",
        )
        dela = _login(client, ANA_EMAIL, ANA_SENHA)

        ids = []
        for i in range(3):
            pedido = client.post(
                "/api/v1/solicitacoes",
                headers=dela,
                json={
                    "path": "cofres/contabil/segredos/token-sefaz",
                    "capabilities": ["reveal"],
                    "reason": f"Guia {i}",
                    "hours": 4,
                },
            )
            assert pedido.status_code == 201, pedido.text
            ids.append(pedido.json()["id"])
        return ids, dela

    def test_aprova_todos_e_relata_cada_um(
        self, client: TestClient, db_session: Session, usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        ids, _ = self._tres_pedidos(client, db_session, usuario)

        resposta = client.post(
            "/api/v1/solicitacoes/aprovar-em-lote",
            headers=autenticado,
            json={"ids": ids, "note": "Aprovado em lote"},
        )

        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert corpo["aprovadas"] == 3
        assert corpo["recusadas"] == 0
        # O relatório cobre todos os ids enviados: aprovar 3 e devolver 2
        # resultados deixaria o terceiro sem explicação.
        assert {r["id"] for r in corpo["resultados"]} == set(ids)
        assert all(r["aprovada"] for r in corpo["resultados"])

    def test_cada_aprovacao_gera_seu_evento(
        self, client: TestClient, db_session: Session, usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """Um evento só de "lote" esconderia o que foi concedido."""
        conceder(db_session, usuario, "auditoria", ["admin"], nome_politica="p-aud")
        ids, _ = self._tres_pedidos(client, db_session, usuario)

        client.post(
            "/api/v1/solicitacoes/aprovar-em-lote",
            headers=autenticado,
            json={"ids": ids},
        )

        trilha = client.get("/api/v1/auditoria", headers=autenticado).json()["eventos"]
        aprovacoes = [e for e in trilha if e["action"] == "acesso_aprovado"]
        assert len(aprovacoes) == 3, "um evento por pedido, não um pelo lote"

    def test_falha_de_um_nao_derruba_os_outros(
        self, client: TestClient, db_session: Session, usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """Pedido já decidido entra como recusado, e os demais seguem."""
        ids, _ = self._tres_pedidos(client, db_session, usuario)
        # Decide o primeiro antes do lote.
        primeira = client.post(
            f"/api/v1/solicitacoes/{ids[0]}/aprovar",
            headers=autenticado,
            json={"note": ""},
        )
        assert primeira.status_code == 200, primeira.text
        assert primeira.json()["status"] == "aprovada", primeira.json()

        resposta = client.post(
            "/api/v1/solicitacoes/aprovar-em-lote",
            headers=autenticado,
            json={"ids": ids},
        )

        corpo = resposta.json()
        assert corpo["aprovadas"] == 2
        assert corpo["recusadas"] == 1
        recusado = next(r for r in corpo["resultados"] if not r["aprovada"])
        assert recusado["id"] == ids[0]
        # A razão aparece: "aprovado 2 de 3" sem dizer por quê seria pior que
        # não ter o botão.
        assert recusado["erro"]

    def test_id_repetido_aprova_uma_vez_so(
        self, client: TestClient, db_session: Session, usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """A tela pode mandar duplicata sem aprovar duas vezes."""
        ids, _ = self._tres_pedidos(client, db_session, usuario)

        corpo = client.post(
            "/api/v1/solicitacoes/aprovar-em-lote",
            headers=autenticado,
            json={"ids": [ids[0], ids[0], ids[1]]},
        ).json()

        assert corpo["aprovadas"] == 2
        assert corpo["recusadas"] == 0
        assert len(corpo["resultados"]) == 2

    def test_sem_permissao_nenhum_e_aprovado(
        self, client: TestClient, db_session: Session, usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """O lote não é caminho lateral para quem não pode aprovar."""
        ids, dela = self._tres_pedidos(client, db_session, usuario)

        # A própria Ana, que só tem read/list, tenta aprovar os pedidos dela.
        corpo = client.post(
            "/api/v1/solicitacoes/aprovar-em-lote", headers=dela, json={"ids": ids}
        ).json()

        assert corpo["aprovadas"] == 0
        assert corpo["recusadas"] == 3
        fila = client.get("/api/v1/solicitacoes/fila", headers=autenticado).json()
        assert all(p["status"] == "pendente" for p in fila)

    def test_lote_vazio_e_recusado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.post(
            "/api/v1/solicitacoes/aprovar-em-lote",
            headers=autenticado,
            json={"ids": []},
        )
        assert resposta.status_code == 422
