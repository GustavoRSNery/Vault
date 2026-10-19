"""Testes das rotas de sessão gravada.

O que estes testes protegem:

- **Ninguém escreve na gravação alheia.** Seria a forma mais simples de forjar
  um registro, e destruiria o valor da gravação como prova.
- **Ver gravação alheia vira evento.** Quem revisa também é revisado — senão
  a tela de gravações é uma janela para a atividade dos outros sem rastro.
- **Derrubar exige ADMIN e justificativa.**
- **A gravação é arquivada ANTES de a sessão ser marcada como encerrada.** O
  inverso perderia a gravação em silêncio numa falha de arquivamento.
- **A origem da captura é declarada.** "Gravação completa" e "o que a pessoa
  anotou" não podem parecer a mesma coisa numa auditoria.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_gravacoes
from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import AuditEventModel, UserModel
from app.infrastructure.sessions.adapters import ArmazenamentoLocal

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
ANA_EMAIL = "ana@exemplo.com.br"
ANA_SENHA = "senha-forte-da-ana-2026"


@pytest.fixture
def gravacoes(tmp_path: Path) -> ArmazenamentoLocal:
    return ArmazenamentoLocal(tmp_path / "gravacoes")


@pytest.fixture
def client_gravando(app: FastAPI, gravacoes: ArmazenamentoLocal) -> TestClient:
    app.dependency_overrides[get_gravacoes] = lambda: gravacoes
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _ana(db: Session) -> UserModel:
    user = UserModel(
        id="us",
        email=ANA_EMAIL,
        full_name="Ana",
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


def _abrir(client: TestClient, headers: dict[str, str], alvo: str = "srv-producao") -> str:
    resposta = client.post(
        "/api/v1/sessoes",
        headers=headers,
        json={"tipo": "ssh", "alvo": alvo, "motivo": "Manutenção programada"},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


class TestCicloDaSessao:
    def test_abrir_registrar_encerrar(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        gravacoes: ArmazenamentoLocal,
    ) -> None:
        sessao_id = _abrir(client_gravando, autenticado)

        for ms, texto in [(0, "whoami"), (1200, "ls -la"), (3400, "exit")]:
            resposta = client_gravando.post(
                f"/api/v1/sessoes/{sessao_id}/eventos",
                headers=autenticado,
                json={"deslocamento_ms": ms, "tipo": "entrada", "conteudo": texto},
            )
            assert resposta.status_code == 204

        encerrada = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/encerrar",
            headers=autenticado,
            json={"motivo": "Terminei"},
        )
        assert encerrada.status_code == 200
        assert encerrada.json()["estado"] == "encerrada"
        assert encerrada.json()["eventos"] == 3

        # A gravação foi de fato arquivada.
        assert (gravacoes._pasta / f"{sessao_id}.jsonl").exists()

    def test_sessao_encerrada_nao_aceita_evento(
        self, client_gravando: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Gravação que muda não prova nada."""
        sessao_id = _abrir(client_gravando, autenticado)
        client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/encerrar", headers=autenticado, json={}
        )

        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/eventos",
            headers=autenticado,
            json={"deslocamento_ms": 10, "tipo": "entrada", "conteudo": "tarde"},
        )
        assert resposta.status_code == 409

    def test_evento_fora_de_ordem_e_recusado(
        self, client_gravando: TestClient, autenticado: dict[str, str]
    ) -> None:
        sessao_id = _abrir(client_gravando, autenticado)
        client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/eventos",
            headers=autenticado,
            json={"deslocamento_ms": 5000, "tipo": "entrada", "conteudo": "a"},
        )
        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/eventos",
            headers=autenticado,
            json={"deslocamento_ms": 100, "tipo": "entrada", "conteudo": "b"},
        )
        assert resposta.status_code == 422

    def test_abrir_vira_evento_de_auditoria(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        _abrir(client_gravando, autenticado, alvo="pg-producao")
        evento = db_session.scalars(
            select(AuditEventModel).where(AuditEventModel.action == "sessao_aberta")
        ).one()
        assert "pg-producao" in evento.reason


class TestNinguemEscreveNaGravacaoAlheia:
    def test_terceiro_nao_registra_evento(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        """Seria a forma mais simples de forjar um registro."""
        sessao_id = _abrir(client_gravando, autenticado)
        _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)

        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/eventos",
            headers=dela,
            json={"deslocamento_ms": 0, "tipo": "entrada", "conteudo": "forjado"},
        )
        assert resposta.status_code == 403
        assert "não prova nada" in resposta.text

    def test_nem_administrador_escreve_na_alheia(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        """ADMIN permite derrubar e revisar, não escrever."""
        conceder(db_session, usuario, "sessoes", TODAS)
        ana = _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)
        sessao_id = _abrir(client_gravando, dela)

        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/eventos",
            headers=autenticado,
            json={"deslocamento_ms": 0, "tipo": "entrada", "conteudo": "forjado"},
        )
        assert resposta.status_code == 403

    def test_terceiro_nao_encerra_sessao_alheia(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        sessao_id = _abrir(client_gravando, autenticado)
        _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)

        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/encerrar", headers=dela, json={}
        )
        assert resposta.status_code == 403
        assert "derrubada" in resposta.text


class TestDerrubar:
    def test_sem_admin_nao_derruba(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        sessao_id = _abrir(client_gravando, autenticado)
        _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)

        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/derrubar",
            headers=dela,
            json={"motivo": "Quero"},
        )
        assert resposta.status_code == 403

    def test_sem_motivo_e_recusado(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        """É interromper o trabalho de alguém: a trilha precisa do porquê."""
        conceder(db_session, usuario, "sessoes", TODAS)
        ana = _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)
        sessao_id = _abrir(client_gravando, dela)

        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/derrubar",
            headers=autenticado,
            json={"motivo": ""},
        )
        assert resposta.status_code == 422

    def test_admin_derruba_e_a_trilha_diz_de_quem(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "sessoes", TODAS)
        ana = _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)
        sessao_id = _abrir(client_gravando, dela)

        resposta = client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/derrubar",
            headers=autenticado,
            json={"motivo": "Acesso fora do horário"},
        )
        assert resposta.status_code == 200
        assert resposta.json()["estado"] == "derrubada"

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "sessao_derrubada"
            )
        ).one()
        assert ANA_EMAIL in evento.reason
        assert "fora do horário" in evento.reason

    def test_derrubada_tem_estado_distinto_de_encerrada(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        """Numa revisão, "terminou" e "foi interrompida" são perguntas
        diferentes."""
        conceder(db_session, usuario, "sessoes", TODAS)
        ana = _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)

        normal = _abrir(client_gravando, dela, alvo="a")
        client_gravando.post(
            f"/api/v1/sessoes/{normal}/encerrar", headers=dela, json={}
        )
        forcada = _abrir(client_gravando, dela, alvo="b")
        client_gravando.post(
            f"/api/v1/sessoes/{forcada}/derrubar",
            headers=autenticado,
            json={"motivo": "Suspeita"},
        )

        historico = client_gravando.get(
            "/api/v1/sessoes/gravacoes", headers=autenticado
        ).json()
        estados = {s["alvo"]: s["estado"] for s in historico}
        assert estados == {"a": "encerrada", "b": "derrubada"}


class TestPrivacidade:
    def test_cada_um_ve_as_proprias(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        _abrir(client_gravando, autenticado, alvo="do-admin")
        _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)
        _abrir(client_gravando, dela, alvo="da-ana")

        ativas = client_gravando.get("/api/v1/sessoes", headers=dela).json()
        assert [s["alvo"] for s in ativas] == ["da-ana"]
        assert "do-admin" not in str(ativas)

    def test_admin_ve_todas(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "sessoes", TODAS)
        _abrir(client_gravando, autenticado, alvo="do-admin")
        _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)
        _abrir(client_gravando, dela, alvo="da-ana")

        ativas = client_gravando.get("/api/v1/sessoes", headers=autenticado).json()
        assert {s["alvo"] for s in ativas} == {"do-admin", "da-ana"}

    def test_ver_gravacao_alheia_vira_evento(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        """Quem revisa também é revisado."""
        conceder(db_session, usuario, "sessoes", TODAS)
        ana = _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)
        sessao_id = _abrir(client_gravando, dela)
        client_gravando.post(
            f"/api/v1/sessoes/{sessao_id}/encerrar", headers=dela, json={}
        )

        client_gravando.get(f"/api/v1/sessoes/{sessao_id}", headers=autenticado)

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "sessao_reproduzida"
            )
        ).one()
        assert ANA_EMAIL in evento.reason

    def test_ver_a_propria_nao_polui_a_trilha(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        """Registrar cada vez que alguém abre a própria gravação encheria a
        trilha de ruído, e ruído esconde o que importa."""
        sessao_id = _abrir(client_gravando, autenticado)
        client_gravando.get(f"/api/v1/sessoes/{sessao_id}", headers=autenticado)

        eventos = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "sessao_reproduzida"
            )
        ).all()
        assert eventos == []

    def test_sem_permissao_nao_abre_gravacao_alheia(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        sessao_id = _abrir(client_gravando, autenticado)
        _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)

        resposta = client_gravando.get(
            f"/api/v1/sessoes/{sessao_id}", headers=dela
        )
        assert resposta.status_code == 403

        negado = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "acesso_negado",
                AuditEventModel.actor_label == ANA_EMAIL,
            )
        ).all()
        assert len(negado) == 1


class TestPlayerEBusca:
    def _com_gravacao(
        self, client: TestClient, headers: dict[str, str]
    ) -> str:
        sessao_id = _abrir(client, headers)
        eventos = [
            (0, "entrada", "ssh srv-producao"),
            (900, "saida", "Welcome to srv-producao"),
            (2100, "entrada", "sudo systemctl restart postgres"),
            (3000, "saida", "Job for postgresql.service failed"),
        ]
        for ms, tipo, texto in eventos:
            client.post(
                f"/api/v1/sessoes/{sessao_id}/eventos",
                headers=headers,
                json={"deslocamento_ms": ms, "tipo": tipo, "conteudo": texto},
            )
        return sessao_id

    def test_linha_do_tempo_vem_ordenada(
        self, client_gravando: TestClient, autenticado: dict[str, str]
    ) -> None:
        sessao_id = self._com_gravacao(client_gravando, autenticado)
        detalhe = client_gravando.get(
            f"/api/v1/sessoes/{sessao_id}", headers=autenticado
        ).json()

        linha = detalhe["linha_do_tempo"]
        assert [e["deslocamento_ms"] for e in linha] == [0, 900, 2100, 3000]
        assert linha[1]["tipo"] == "saida"

    def test_busca_encontra_dentro_da_gravacao(
        self, client_gravando: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Ninguém assiste três horas de sessão para achar um comando."""
        sessao_id = self._com_gravacao(client_gravando, autenticado)
        achados = client_gravando.get(
            f"/api/v1/sessoes/{sessao_id}/busca?termo=postgres",
            headers=autenticado,
        ).json()

        assert len(achados) == 2
        assert achados[0]["deslocamento_ms"] == 2100

    def test_busca_em_gravacao_alheia_e_recusada(
        self, client_gravando: TestClient, autenticado: dict[str, str],
        db_session: Session,
    ) -> None:
        sessao_id = self._com_gravacao(client_gravando, autenticado)
        _ana(db_session)
        dela = _login(client_gravando, ANA_EMAIL, ANA_SENHA)

        assert client_gravando.get(
            f"/api/v1/sessoes/{sessao_id}/busca?termo=postgres", headers=dela
        ).status_code == 403

    def test_historico_pesquisavel_por_alvo(
        self, client_gravando: TestClient, autenticado: dict[str, str]
    ) -> None:
        for alvo in ["pg-producao", "fw-matriz", "pg-homologacao"]:
            sid = _abrir(client_gravando, autenticado, alvo=alvo)
            client_gravando.post(
                f"/api/v1/sessoes/{sid}/encerrar", headers=autenticado, json={}
            )

        achadas = client_gravando.get(
            "/api/v1/sessoes/gravacoes?termo=pg-", headers=autenticado
        ).json()
        assert {s["alvo"] for s in achadas} == {"pg-producao", "pg-homologacao"}


class TestHonestidadeDaCaptura:
    def test_declara_que_a_captura_e_manual(
        self, client_gravando: TestClient, autenticado: dict[str, str]
    ) -> None:
        """"Gravação completa" e "o que a pessoa anotou" não podem parecer a
        mesma coisa numa auditoria."""
        sessao_id = _abrir(client_gravando, autenticado)
        detalhe = client_gravando.get(
            f"/api/v1/sessoes/{sessao_id}", headers=autenticado
        ).json()

        assert detalhe["captura_automatica"] is False
        assert detalhe["capturado_por"] == "manual"
        assert "não capturada" in detalhe["aviso"]

    def test_gravacao_nao_se_sobrescreve(
        self, gravacoes: ArmazenamentoLocal
    ) -> None:
        """Gravação é prova: escrever por cima seria apagar o que aconteceu."""
        from app.domain.shared.errors import ValidationError

        gravacoes.guardar("s1", b"original")
        with pytest.raises(ValidationError, match="prova"):
            gravacoes.guardar("s1", b"adulterado")
        assert gravacoes.ler("s1.jsonl") == b"original"

    def test_armazenamento_local_declara_que_nao_e_imutavel(
        self, gravacoes: ArmazenamentoLocal
    ) -> None:
        assert gravacoes.imutavel is False
