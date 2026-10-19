"""Testes da configuração operacional.

O bloco que justifica o arquivo é `TestConfiguracaoMudaComportamento`:
configuração que não muda nada é decorativa, e decorativa é pior que
inexistente — alguém ajusta, acha que mudou algo, e só descobre o contrário
num incidente.

O outro ponto é o que a configuração **não** permite: enfraquecer o sistema.
Os limites recusam o valor absurdo e explicam por quê.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]


class TestLeitura:
    def test_qualquer_autenticado_le(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """O front precisa saber por quantos segundos mostrar um segredo."""
        resposta = client.get("/api/v1/configuracao", headers=autenticado)
        assert resposta.status_code == 200
        assert resposta.json()["segundos_segredo_visivel"] == 30

    def test_sem_autenticacao_nao_le(self, client: TestClient) -> None:
        assert client.get("/api/v1/configuracao").status_code == 401

    def test_limites_viajam_junto(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Para a tela mostrar a faixa sem duplicar os números — duplicados,
        divergem no primeiro ajuste."""
        limites = client.get("/api/v1/configuracao", headers=autenticado).json()[
            "limites"
        ]
        assert limites["segundos_segredo_visivel"] == [5, 300]
        assert limites["alerta_certificado_dias"] == [7, 180]


class TestEscrita:
    def test_sem_admin_nao_altera(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        resposta = client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"segundos_segredo_visivel": 60},
        )
        assert resposta.status_code == 403

    def test_altera_so_o_que_foi_enviado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        resposta = client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"segundos_segredo_visivel": 60},
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["segundos_segredo_visivel"] == 60
        assert corpo["custodia_horas_padrao"] == 4  # intocado

    def test_registra_antes_e_depois_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """"Configuração alterada" não permite revisar nada."""
        conceder(db_session, usuario, "admin", TODAS)
        client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"segundos_segredo_visivel": 90, "custodia_horas_padrao": 8},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "configuracao_alterada"
            )
        ).one()
        assert "30 -> 90" in evento.reason
        assert "4 -> 8" in evento.reason

    def test_alteracao_sem_mudanca_nao_polui_a_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"segundos_segredo_visivel": 30},  # já era 30
        )
        eventos = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "configuracao_alterada"
            )
        ).all()
        assert eventos == []

    def test_quem_alterou_fica_registrado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        corpo = client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"segundos_segredo_visivel": 45},
        ).json()
        assert corpo["atualizado_por"] == usuario.email


class TestLimitesProtegem:
    """A configuração não pode desligar a própria proteção."""

    def test_segredo_visivel_tempo_demais_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Segredo na tela por uma hora é segredo exposto a quem passar."""
        conceder(db_session, usuario, "admin", TODAS)
        assert client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"segundos_segredo_visivel": 3600},
        ).status_code == 422

    def test_segredo_visivel_tempo_de_menos_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        assert client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"segundos_segredo_visivel": 1},
        ).status_code == 422

    def test_alerta_de_certificado_longo_demais_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Alerta permanente é alerta ignorado."""
        conceder(db_session, usuario, "admin", TODAS)
        assert client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"alerta_certificado_dias": 365},
        ).status_code == 422

    def test_custodia_acima_de_trinta_dias_e_recusada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS)
        assert client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"custodia_horas_padrao": 2000},
        ).status_code == 422


class TestConfiguracaoMudaComportamento:
    """Configuração que não muda nada é decorativa — e decorativa é pior que
    inexistente, porque alguém ajusta e acha que mudou algo."""

    def test_faixa_de_alerta_muda_o_estado_do_certificado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS, nome_politica="p-admin")
        conceder(db_session, usuario, "certificados/*", TODAS, nome_politica="p-cert")

        agora = datetime.now(UTC)
        client.post(
            "/api/v1/certificados",
            headers=autenticado,
            json={
                "name": "meio-termo",
                "display_name": "meio.termo.com.br",
                "subject": "CN=meio.termo.com.br",
                "issuer": "CA",
                "not_before": (agora - timedelta(days=60)).isoformat(),
                "not_after": (agora + timedelta(days=50)).isoformat(),
            },
        )

        # Com a faixa padrão de 30 dias, 50 dias é "válido".
        lista = client.get("/api/v1/certificados", headers=autenticado).json()
        assert lista[0]["estado"] == "valido"

        # Ampliando a faixa para 60, o mesmo certificado passa a "vencendo".
        client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"alerta_certificado_dias": 60},
        )
        lista = client.get("/api/v1/certificados", headers=autenticado).json()
        assert lista[0]["estado"] == "vencendo"

    def test_prazo_padrao_de_custodia_e_usado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS, nome_politica="p-admin")
        conceder(
            db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-disp"
        )
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-cred")

        client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"custodia_horas_padrao": 12},
        )

        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv", "display_name": "Servidor"},
        )
        criada = client.post(
            "/api/v1/dispositivos/srv/credenciais",
            headers=autenticado,
            json={"name": "senha-root"},
        )
        retirada = client.post(
            f"/api/v1/credenciais/{criada.json()['id']}/retirar",
            headers=autenticado,
            json={"reason": "Manutenção"},  # sem informar horas
        )
        assert retirada.status_code == 200

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "credencial_retirada"
            )
        ).one()
        assert "Prazo de 12h" in evento.reason

    def test_prazo_informado_vence_o_padrao(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O padrão é padrão, não imposição."""
        conceder(db_session, usuario, "admin", TODAS, nome_politica="p-admin")
        conceder(
            db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-disp"
        )
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-cred")
        client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"custodia_horas_padrao": 12},
        )
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv", "display_name": "Servidor"},
        )
        criada = client.post(
            "/api/v1/dispositivos/srv/credenciais",
            headers=autenticado,
            json={"name": "senha-root"},
        )
        client.post(
            f"/api/v1/credenciais/{criada.json()['id']}/retirar",
            headers=autenticado,
            json={"reason": "Rápida", "hours": 2},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "credencial_retirada"
            )
        ).one()
        assert "Prazo de 2h" in evento.reason

    def test_limite_da_trilha_e_respeitado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "admin", TODAS, nome_politica="p-admin")
        conceder(db_session, usuario, "auditoria", TODAS, nome_politica="p-audit")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")

        for i in range(8):
            client.post(
                "/api/v1/cofres",
                headers=autenticado,
                json={"name": f"cofre-{i}", "display_name": f"Cofre {i}"},
            )

        client.put(
            "/api/v1/configuracao",
            headers=autenticado,
            json={"trilha_limite_padrao": 50},
        )
        trilha = client.get("/api/v1/auditoria", headers=autenticado).json()
        assert len(trilha["eventos"]) <= 50
