"""Rotas de integração (webhooks).

O que estes testes protegem na borda HTTP:

- **O segredo de assinatura aparece uma vez.** No cadastro e na rotação, e
  nunca mais. Repeti-lo numa listagem o espalharia por log de proxy,
  histórico de navegador e captura de tela de quem só conferia uma URL.
- **A listagem de entregas não traz o corpo do evento.** O corpo carrega
  caminhos de segredos; exibi-lo entregaria isso a quem só queria saber se
  a entrega passou.
- **http simples é recusado.** A assinatura prova a origem, não esconde o
  conteúdo — e no conteúdo vão caminhos de segredos.
- **Rotacionar invalida o segredo anterior na hora.**
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]


def _criar(client: TestClient, headers: dict[str, str], **extra):  # noqa: ANN003
    corpo = {
        "name": "siem",
        "display_name": "SIEM corporativo",
        "url": "https://siem.exemplo.com.br/hooks/vault",
        **extra,
    }
    return client.post("/api/v1/integracoes", headers=headers, json=corpo)


class TestCadastro:
    def test_cadastra_e_devolve_o_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db_session, usuario, "integracoes/*", TODAS, nome_politica="p-i2")

        resposta = _criar(client, autenticado, eventos=["segredo.*"])

        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["segredo"].startswith("whsec_")
        assert "não será mostrado de novo" in corpo["aviso"]
        assert corpo["eventos"] == ["segredo.*"]

    def test_o_segredo_nao_volta_na_listagem(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A invariante central desta tela."""
        conceder(db_session, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db_session, usuario, "integracoes/*", TODAS, nome_politica="p-i2")
        segredo = _criar(client, autenticado).json()["segredo"]

        listagem = client.get("/api/v1/integracoes", headers=autenticado)

        assert segredo not in listagem.text
        assert "whsec_" not in listagem.text

    def test_http_simples_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db_session, usuario, "integracoes/*", TODAS, nome_politica="p-i2")

        resposta = _criar(client, autenticado, url="http://siem.exemplo.com.br/h")

        assert resposta.status_code == 422

    def test_sem_permissao_nao_cadastra(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)

        assert _criar(client, autenticado).status_code == 403

    def test_lista_de_eventos_disponiveis(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """A tela precisa saber o que dá para assinar."""
        resposta = client.get("/api/v1/integracoes/eventos", headers=autenticado)

        assert resposta.status_code == 200
        eventos = resposta.json()
        assert "segredo.revelado" in eventos
        assert "certificado.vencendo" in eventos


class TestRotacao:
    def test_rotacionar_troca_o_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db_session, usuario, "integracoes/*", TODAS, nome_politica="p-i2")
        antigo = _criar(client, autenticado).json()["segredo"]

        resposta = client.post(
            "/api/v1/integracoes/siem/rotacionar-segredo", headers=autenticado
        )

        assert resposta.status_code == 200
        novo = resposta.json()["segredo"]
        assert novo != antigo
        assert novo.startswith("whsec_")
        assert "as entregas falharão" in resposta.json()["aviso"]

    def test_rotacao_fica_na_trilha_sem_o_valor(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A trilha é lida por mais gente do que quem administra
        integrações — o segredo não pode entrar no motivo do evento."""
        conceder(db_session, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db_session, usuario, "integracoes/*", TODAS, nome_politica="p-i2")
        _criar(client, autenticado)
        novo = client.post(
            "/api/v1/integracoes/siem/rotacionar-segredo", headers=autenticado
        ).json()["segredo"]

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "integracao_segredo_rotacionado"
            )
        ).one()

        assert novo not in evento.reason
        assert "deixou de valer" in evento.reason


class TestCicloDeVida:
    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session,
    ) -> None:
        conceder(db, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db, usuario, "integracoes/*", TODAS, nome_politica="p-i2")
        _criar(client, headers)

    def test_pausar_e_reativar(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        self._preparar(client, autenticado, usuario, db_session)

        pausado = client.post("/api/v1/integracoes/siem/pausar", headers=autenticado)
        assert pausado.json()["estado"] == "pausado"

        ativo = client.post("/api/v1/integracoes/siem/reativar", headers=autenticado)
        assert ativo.json()["estado"] == "ativo"

    def test_atualizar_recusa_http(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A revalidação no PUT: sem ela, dava para degradar o destino
        depois de cadastrá-lo corretamente."""
        self._preparar(client, autenticado, usuario, db_session)

        resposta = client.put(
            "/api/v1/integracoes/siem",
            headers=autenticado,
            json={"url": "http://inseguro.exemplo.com.br/h"},
        )

        assert resposta.status_code == 422

    def test_excluir(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        self._preparar(client, autenticado, usuario, db_session)

        assert client.delete(
            "/api/v1/integracoes/siem", headers=autenticado
        ).status_code == 204
        assert client.get("/api/v1/integracoes", headers=autenticado).json() == []


class TestEntrega:
    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session,
    ) -> str:
        conceder(db, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db, usuario, "integracoes/*", TODAS, nome_politica="p-i2")
        return _criar(client, headers).json()["segredo"]

    def test_testar_entrega_na_hora(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Quem acabou de cadastrar quer saber agora se funcionou."""
        self._preparar(client, autenticado, usuario, db_session)

        resposta = client.post("/api/v1/integracoes/siem/testar", headers=autenticado)

        assert resposta.status_code == 200
        assert resposta.json()["entregues"] == 1
        assert resposta.json()["entregador"] == "ensaio"

    def test_teste_ignora_o_filtro_de_eventos(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Um teste que não chega porque o destino não assina `teste.ping`
        não testa nada."""
        conceder(db_session, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db_session, usuario, "integracoes/*", TODAS, nome_politica="p-i2")
        _criar(client, autenticado, eventos=["cofre.selado"])

        resposta = client.post("/api/v1/integracoes/siem/testar", headers=autenticado)

        assert resposta.json()["entregues"] == 1

    def test_entregas_nao_trazem_o_corpo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O corpo carrega caminhos de segredos."""
        self._preparar(client, autenticado, usuario, db_session)
        client.post("/api/v1/integracoes/siem/testar", headers=autenticado)

        entregas = client.get(
            "/api/v1/integracoes/siem/entregas", headers=autenticado
        ).json()

        assert len(entregas) == 1
        assert "corpo" not in entregas[0]
        assert entregas[0]["estado"] == "entregue"
        # O `webhook-id` fica visível: é o que o destino usa para deduplicar,
        # e é por ele que alguém cruza os dois lados numa investigação.
        assert entregas[0]["id_evento"]

    def test_despachar_fila_vazia(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        self._preparar(client, autenticado, usuario, db_session)

        resposta = client.post("/api/v1/integracoes/despachar", headers=autenticado)

        assert resposta.status_code == 200
        assert resposta.json()["tentadas"] == 0

    def test_destino_pausado_nao_recebe_no_despacho(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        self._preparar(client, autenticado, usuario, db_session)
        client.post("/api/v1/integracoes/siem/testar", headers=autenticado)
        client.post("/api/v1/integracoes/siem/pausar", headers=autenticado)

        resposta = client.post("/api/v1/integracoes/despachar", headers=autenticado)

        assert resposta.json()["tentadas"] == 0


class TestEventosReais:
    """A prova de que a integração integra: um evento de verdade vira webhook.

    Até aqui os testes cobriam o canal (assinatura, fila, reentrega). Este
    cobre a ligação: revelar um segredo no cofre precisa chegar ao destino
    que assina `segredo.*` — senão o sistema teria uma tela de integrações
    bonita que não publica nada.
    """

    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session,
    ) -> None:
        conceder(db, usuario, "integracoes", TODAS, nome_politica="p-i")
        conceder(db, usuario, "integracoes/*", TODAS, nome_politica="p-i2")
        conceder(db, usuario, "cofres/*", TODAS, nome_politica="p-c")
        conceder(db, usuario, "cofres", TODAS, nome_politica="p-c2")

    def test_revelar_segredo_vira_webhook(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        self._preparar(client, autenticado, usuario, db_session)
        _criar(client, autenticado, eventos=["segredo.*"])

        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "infra", "display_name": "Infra"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": "nao-pode-vazar-4471", "kind": "senha"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos/senha-root/revelar", headers=autenticado
        )

        despacho = client.post("/api/v1/integracoes/despachar", headers=autenticado)

        assert despacho.status_code == 200
        assert despacho.json()["entregues"] >= 1

        tipos = [
            e["tipo"]
            for e in client.get(
                "/api/v1/integracoes/siem/entregas", headers=autenticado
            ).json()
        ]
        assert "segredo.revelado" in tipos

    def test_o_webhook_nao_leva_o_valor_do_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A invariante que mais importa nesta ligação: o evento diz *que*
        um segredo foi revelado e *qual*, nunca o valor."""
        from app.infrastructure.db.models import EntregaWebhookModel
        from sqlalchemy import select as _select

        self._preparar(client, autenticado, usuario, db_session)
        _criar(client, autenticado, eventos=["segredo.*"])

        valor = "senha-super-secreta-que-nao-pode-vazar-9913"
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "infra", "display_name": "Infra"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": valor, "kind": "senha"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos/senha-root/revelar", headers=autenticado
        )
        client.post("/api/v1/integracoes/despachar", headers=autenticado)

        # O corpo assinado, lido direto do banco: é o que de fato sairia.
        corpos = db_session.scalars(
            _select(EntregaWebhookModel.corpo)
        ).all()

        assert corpos, "nenhuma entrega foi enfileirada"
        for corpo in corpos:
            assert valor not in corpo
        # E o caminho está lá, que é o que o destino precisa.
        assert any("senha-root" in c for c in corpos)

    def test_destino_novo_nao_recebe_o_historico(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Um destino recém-cadastrado não deve receber de uma vez todo o
        histórico do cofre — seria uma enxurrada de eventos antigos que
        ninguém pediu, e os mais sensíveis entre eles."""
        self._preparar(client, autenticado, usuario, db_session)

        # Movimento ANTES de existir destino.
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "infra", "display_name": "Infra"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos",
            headers=autenticado,
            json={"name": "antigo", "value": "valor-antigo", "kind": "senha"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos/antigo/revelar", headers=autenticado
        )

        _criar(client, autenticado, eventos=["segredo.*"])
        client.post("/api/v1/integracoes/despachar", headers=autenticado)

        entregas = client.get(
            "/api/v1/integracoes/siem/entregas", headers=autenticado
        ).json()

        assert entregas == [], "o destino novo recebeu eventos anteriores a ele"

    def test_evento_sem_assinante_nao_enfileira(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """E o marcador avança assim mesmo, senão o sistema reprocessaria os
        mesmos eventos ignorados para sempre."""
        self._preparar(client, autenticado, usuario, db_session)
        _criar(client, autenticado, eventos=["cofre.selado"])

        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "infra", "display_name": "Infra"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos",
            headers=autenticado,
            json={"name": "s1", "value": "v", "kind": "senha"},
        )
        client.post("/api/v1/cofres/infra/segredos/s1/revelar", headers=autenticado)

        primeiro = client.post("/api/v1/integracoes/despachar", headers=autenticado)
        segundo = client.post("/api/v1/integracoes/despachar", headers=autenticado)

        assert primeiro.json()["tentadas"] == 0
        assert segundo.json()["tentadas"] == 0
