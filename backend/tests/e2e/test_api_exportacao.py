"""Testes da rota de exportação da trilha.

O que importa aqui é o efeito visível: antes de exportar, a tela de
integridade avisa que a garantia é parcial; depois, o aviso muda e passa a
dizer quanto da trilha está de fato ancorado.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_siem_exporter
from app.infrastructure.audit.exporters import JsonlExporter
from app.infrastructure.db.models import UserModel

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]


@pytest.fixture
def destino(tmp_path: Path) -> JsonlExporter:
    return JsonlExporter(tmp_path / "trilha.jsonl")


@pytest.fixture
def client_com_destino(
    app: FastAPI, destino: JsonlExporter
) -> TestClient:
    app.dependency_overrides[get_siem_exporter] = lambda: destino
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestExportacao:
    def test_sem_admin_na_auditoria_recebe_403(
        self, client_com_destino: TestClient, usuario: UserModel, db_session: Session
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        login = client_com_destino.post(
            "/api/v1/auth/login",
            json={"email": usuario.email, "password": "senha-forte-do-ana.souza-2026"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }
        assert (
            client_com_destino.post(
                "/api/v1/auditoria/exportar", headers=headers
            ).status_code
            == 403
        )

    def test_exportar_cria_ancora_e_muda_o_aviso(
        self, client_com_destino: TestClient, usuario: UserModel,
        db_session: Session, destino: JsonlExporter,
    ) -> None:
        """O efeito que justifica a funcionalidade inteira."""
        conceder(db_session, usuario, "auditoria", TODAS, nome_politica="p-audit")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        login = client_com_destino.post(
            "/api/v1/auth/login",
            json={"email": usuario.email, "password": "senha-forte-do-ana.souza-2026"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }
        client_com_destino.post(
            "/api/v1/cofres",
            headers=headers,
            json={"name": "contabil", "display_name": "Contábil"},
        )

        antes = client_com_destino.get(
            "/api/v1/auditoria/integridade", headers=headers
        ).json()
        assert antes["ancoras_conferidas"] == 0
        assert antes["eventos_ancorados"] == 0
        assert "Nenhuma âncora externa" in antes["aviso"]

        exportacao = client_com_destino.post(
            "/api/v1/auditoria/exportar", headers=headers
        )
        assert exportacao.status_code == 200
        corpo = exportacao.json()
        assert corpo["exportados"] > 0
        assert corpo["ancora_sequencia"] is not None
        assert destino.caminho.exists()

        depois = client_com_destino.get(
            "/api/v1/auditoria/integridade", headers=headers
        ).json()
        assert depois["integra"] is True
        assert depois["ancoras_conferidas"] == 1
        assert depois["eventos_ancorados"] > 0
        assert "Nenhuma âncora externa" not in (depois["aviso"] or "")

    def test_aviso_declara_o_trecho_ainda_nao_ancorado(
        self, client_com_destino: TestClient, usuario: UserModel, db_session: Session
    ) -> None:
        """Honestidade sobre o alcance: o que veio depois da âncora é fraco."""
        conceder(db_session, usuario, "auditoria", TODAS, nome_politica="p-audit")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        login = client_com_destino.post(
            "/api/v1/auth/login",
            json={"email": usuario.email, "password": "senha-forte-do-ana.souza-2026"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }

        client_com_destino.post("/api/v1/auditoria/exportar", headers=headers)
        # Atividade depois da âncora.
        client_com_destino.post(
            "/api/v1/cofres",
            headers=headers,
            json={"name": "rh", "display_name": "RH"},
        )

        integridade = client_com_destino.get(
            "/api/v1/auditoria/integridade", headers=headers
        ).json()
        assert integridade["ancoras_conferidas"] == 1
        assert "após a última âncora" in integridade["aviso"]

    def test_exportacao_vira_evento_da_trilha(
        self, client_com_destino: TestClient, usuario: UserModel, db_session: Session
    ) -> None:
        conceder(db_session, usuario, "auditoria", TODAS, nome_politica="p-audit")
        login = client_com_destino.post(
            "/api/v1/auth/login",
            json={"email": usuario.email, "password": "senha-forte-do-ana.souza-2026"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }
        client_com_destino.post("/api/v1/auditoria/exportar", headers=headers)

        trilha = client_com_destino.get(
            "/api/v1/auditoria?limite=20", headers=headers
        ).json()
        acoes = [e["action"] for e in trilha["eventos"]]
        assert "trilha_exportada" in acoes

    def test_exportacao_converge_e_nao_se_auto_alimenta(
        self, client_com_destino: TestClient, usuario: UserModel, db_session: Session
    ) -> None:
        """A exportação precisa parar sozinha num sistema ocioso.

        Se toda exportação virasse evento, o evento gerado agora seria a
        pendência da próxima rodada, que geraria outro — para sempre. Uma
        exportação agendada a cada 5 minutos encheria a trilha sozinha, sem
        nenhuma atividade de usuário. Este teste exige a convergência.
        """
        conceder(db_session, usuario, "auditoria", TODAS, nome_politica="p-audit")
        login = client_com_destino.post(
            "/api/v1/auth/login",
            json={"email": usuario.email, "password": "senha-forte-do-ana.souza-2026"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }

        # 1ª: leva o login e registra a si mesma.
        primeira = client_com_destino.post(
            "/api/v1/auditoria/exportar", headers=headers
        ).json()
        assert primeira["exportados"] > 0

        # 2ª: leva só o registro da 1ª — e NÃO se registra, senão o ciclo
        # nunca fecharia.
        segunda = client_com_destino.post(
            "/api/v1/auditoria/exportar", headers=headers
        ).json()
        assert segunda["exportados"] == 1

        # 3ª em diante: nada. O sistema está em repouso e a trilha também.
        for _ in range(3):
            rodada = client_com_destino.post(
                "/api/v1/auditoria/exportar", headers=headers
            ).json()
            assert rodada["exportados"] == 0
            assert rodada["ancora_sequencia"] is None

        # E a trilha tem UM evento de exportação, não cinco.
        trilha = client_com_destino.get(
            "/api/v1/auditoria?limite=50", headers=headers
        ).json()
        exportacoes = [
            e for e in trilha["eventos"] if e["action"] == "trilha_exportada"
        ]
        assert len(exportacoes) == 1

    def test_atividade_nova_volta_a_gerar_registro(
        self, client_com_destino: TestClient, usuario: UserModel, db_session: Session
    ) -> None:
        """Convergir não pode virar "parou de registrar para sempre"."""
        conceder(db_session, usuario, "auditoria", TODAS, nome_politica="p-audit")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        login = client_com_destino.post(
            "/api/v1/auth/login",
            json={"email": usuario.email, "password": "senha-forte-do-ana.souza-2026"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }
        for _ in range(3):
            client_com_destino.post("/api/v1/auditoria/exportar", headers=headers)

        # Atividade real volta a acontecer.
        client_com_destino.post(
            "/api/v1/cofres",
            headers=headers,
            json={"name": "novo", "display_name": "Novo"},
        )
        rodada = client_com_destino.post(
            "/api/v1/auditoria/exportar", headers=headers
        ).json()
        assert rodada["exportados"] >= 1

        trilha = client_com_destino.get(
            "/api/v1/auditoria?limite=50", headers=headers
        ).json()
        exportacoes = [
            e for e in trilha["eventos"] if e["action"] == "trilha_exportada"
        ]
        assert len(exportacoes) == 2

    def test_avisa_que_o_destino_local_nao_e_inviolavel(
        self, client_com_destino: TestClient, usuario: UserModel, db_session: Session
    ) -> None:
        """A tela não pode anunciar garantia que o ambiente não tem."""
        conceder(db_session, usuario, "auditoria", TODAS, nome_politica="p-audit")
        login = client_com_destino.post(
            "/api/v1/auth/login",
            json={"email": usuario.email, "password": "senha-forte-do-ana.souza-2026"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }
        corpo = client_com_destino.post(
            "/api/v1/auditoria/exportar", headers=headers
        ).json()
        assert corpo["destino_inviolavel"] is False
        assert "não é inviolável" in corpo["aviso"]
