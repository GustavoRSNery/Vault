"""Testes de chaves de API, acesso remoto e exportação.

O que estes testes protegem:

- **Nenhuma exportação carrega valor de segredo.** Um "exportar tudo" que
  incluísse a chave privada transformaria um clique de conveniência num
  vazamento.
- **O arquivo .rdp não contém senha.** Senha em arquivo é senha no disco de
  quem baixou, fora do cofre e fora da auditoria.
- **Todo acesso remoto vira evento**, inclusive os que o sistema não
  intermedia — senão a trilha teria um buraco justamente nos acessos
  informais, que são os que mais importam numa revisão.
- **Excluir o governo não apaga o segredo.**
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEventModel, UserModel

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
VALOR_SECRETO = "sk_live_NUNCA_DEVE_VAZAR_9981"


class TestChavesDeApi:
    def _criar(
        self, client: TestClient, headers: dict[str, str], **extra
    ):  # noqa: ANN003
        corpo = {
            "name": "sefaz-nfe",
            "display_name": "SEFAZ NF-e",
            "servico": "SEFAZ",
            "responsavel": "fiscal@exemplo.com.br",
            **extra,
        }
        return client.post("/api/v1/chaves-api", headers=headers, json=corpo)

    def test_cadastra_com_governo_completo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        resposta = self._criar(
            client,
            autenticado,
            ambiente="homologacao",
            formato="cabecalho",
            nome_do_campo="X-API-Key",
            escopo="Consulta de NF-e",
            usada_em=["rpa-fiscal", "etl-notas"],
            dias_de_validade=90,
        )
        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["como_usar"] == "X-API-Key: <valor>"
        assert corpo["dias_para_vencer"] in (89, 90)
        assert corpo["usada_em"] == ["etl-notas", "rpa-fiscal"]

    def test_servico_sem_responsavel_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        assert self._criar(
            client, autenticado, responsavel=""
        ).status_code == 422

    def test_formato_cabecalho_sem_campo_e_recusado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Sem o nome do campo, quem pega a chave não sabe como enviá-la."""
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        assert self._criar(
            client, autenticado, formato="cabecalho", nome_do_campo=""
        ).status_code == 422

    def test_alterar_vencimento_pela_edicao(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Bug achado com o sistema no ar: o PUT ignorava `expira_em`.

        O formulário de edição enviava a data, o schema não declarava o campo
        e o Pydantic o descartava em silêncio — a chave ficava "sem
        vencimento" para sempre. É o oposto do que esta tela existe para
        fazer: o prazo é justamente o que some quando a chave mora numa
        planilha.
        """
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        self._criar(client, autenticado)

        prazo = datetime.now(UTC) + timedelta(days=45)
        resposta = client.put(
            "/api/v1/chaves-api/sefaz-nfe",
            headers=autenticado,
            json={"expira_em": prazo.isoformat()},
        )

        assert resposta.status_code == 200
        assert resposta.json()["dias_para_vencer"] in (44, 45)
        # E persiste: releitura, não só o eco da resposta.
        relida = client.get("/api/v1/chaves-api/sefaz-nfe", headers=autenticado)
        assert relida.json()["expira_em"] is not None

    def test_limpar_vencimento_com_nulo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """`null` significa "sem vencimento", não "não mandei".

        Com `exclude_none` o pedido de limpar o prazo sumia junto com os
        campos ausentes, e não havia como tornar permanente uma chave que
        passou a ser.
        """
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        self._criar(client, autenticado, dias_de_validade=90)

        resposta = client.put(
            "/api/v1/chaves-api/sefaz-nfe",
            headers=autenticado,
            json={"expira_em": None},
        )

        assert resposta.status_code == 200
        assert resposta.json()["expira_em"] is None
        assert resposta.json()["dias_para_vencer"] is None

    def test_omitir_campo_nao_apaga_o_vencimento(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O outro lado da moeda: editar só o responsável não pode zerar o
        prazo de quem já tinha um."""
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        self._criar(client, autenticado, dias_de_validade=90)

        resposta = client.put(
            "/api/v1/chaves-api/sefaz-nfe",
            headers=autenticado,
            json={"responsavel": "outro@exemplo.com.br"},
        )

        assert resposta.json()["responsavel"] == "outro@exemplo.com.br"
        assert resposta.json()["expira_em"] is not None

    def test_revogar_nao_apaga(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A auditoria quer saber que a chave existiu."""
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        self._criar(client, autenticado)

        revogada = client.post(
            "/api/v1/chaves-api/sefaz-nfe/revogar", headers=autenticado
        )
        assert revogada.json()["situacao"] == "revogada"
        # Continua na listagem.
        assert len(client.get("/api/v1/chaves-api", headers=autenticado).json()) == 1

    def test_excluir_nao_apaga_o_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Um clique não pode remover a chave e o rastro ao mesmo tempo."""
        conceder(db_session, usuario, "chaves-api/*", TODAS, nome_politica="p-ch")
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cof")
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "apis", "display_name": "APIs"},
        )
        client.post(
            "/api/v1/cofres/apis/segredos",
            headers=autenticado,
            json={"name": "sefaz", "value": VALOR_SECRETO, "kind": "chave_api"},
        )
        self._criar(client, autenticado, vault_name="apis", secret_name="sefaz")

        client.delete("/api/v1/chaves-api/sefaz-nfe", headers=autenticado)

        # O segredo continua no cofre.
        revelado = client.post(
            "/api/v1/cofres/apis/segredos/sefaz/revelar", headers=autenticado
        )
        assert revelado.status_code == 200
        assert revelado.json()["value"] == VALOR_SECRETO

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "chave_api_excluida"
            )
        ).one()
        assert "não foi apagado" in evento.reason

    def test_listagem_nao_traz_valor(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "chaves-api/*", TODAS)
        self._criar(client, autenticado)
        corpo = client.get("/api/v1/chaves-api", headers=autenticado).text
        assert "value" not in corpo
        assert VALOR_SECRETO not in corpo

    def test_sem_permissao_nao_ve(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        assert self._criar(client, autenticado).status_code == 403


class TestAcessoRemoto:
    def _dispositivo(self, client: TestClient, headers: dict[str, str]) -> None:
        client.post(
            "/api/v1/dispositivos",
            headers=headers,
            json={
                "name": "srv-contabil",
                "display_name": "Servidor Contábil",
                "address": "10.0.1.20",
            },
        )

    def test_define_acessos_visiveis(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Os identificadores são dados comuns: dizem onde a máquina está,
        não como entrar nela."""
        conceder(db_session, usuario, "dispositivos/*", TODAS)
        self._dispositivo(client, autenticado)

        resposta = client.put(
            "/api/v1/dispositivos/srv-contabil/acessos",
            headers=autenticado,
            json={
                "acessos": [
                    {
                        "metodo": "rdp",
                        "identificador": "10.0.1.20",
                        "usuario_sugerido": "administrador",
                    },
                    {"metodo": "anydesk", "identificador": "123 456 789"},
                    {"metodo": "google_remote", "identificador": "srv-contabil"},
                ]
            },
        )
        assert resposta.status_code == 200
        acessos = {a["metodo"]: a for a in resposta.json()["acessos"]}

        # Visíveis, não mascarados.
        assert acessos["anydesk"]["identificador"] == "123 456 789"
        # A tela sabe o que oferecer sem deduzir pelo nome.
        assert acessos["rdp"]["suporta_arquivo_rdp"] is True
        assert acessos["google_remote"]["link"] is not None
        assert acessos["anydesk"]["link"] is None

    def test_metodo_repetido_e_removido(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Dois RDPs confundem: qual dos dois é o certo?"""
        conceder(db_session, usuario, "dispositivos/*", TODAS)
        self._dispositivo(client, autenticado)

        resposta = client.put(
            "/api/v1/dispositivos/srv-contabil/acessos",
            headers=autenticado,
            json={
                "acessos": [
                    {"metodo": "rdp", "identificador": "10.0.1.20"},
                    {"metodo": "rdp", "identificador": "10.0.1.99"},
                ]
            },
        )
        acessos = resposta.json()["acessos"]
        assert len(acessos) == 1
        assert acessos[0]["identificador"] == "10.0.1.20"

    def test_arquivo_rdp_nao_contem_senha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A invariante central: senha em arquivo é senha fora do cofre."""
        conceder(db_session, usuario, "dispositivos/*", TODAS)
        self._dispositivo(client, autenticado)
        client.put(
            "/api/v1/dispositivos/srv-contabil/acessos",
            headers=autenticado,
            json={
                "acessos": [
                    {
                        "metodo": "rdp",
                        "identificador": "10.0.1.20",
                        "usuario_sugerido": "administrador",
                    }
                ]
            },
        )

        arquivo = client.get(
            "/api/v1/dispositivos/srv-contabil/rdp", headers=autenticado
        )
        assert arquivo.status_code == 200
        conteudo = arquivo.text.lower()
        assert "password" not in conteudo
        assert "10.0.1.20" in conteudo
        assert "prompt for credentials:i:1" in conteudo
        assert "srv-contabil.rdp" in arquivo.headers["content-disposition"]

    def test_baixar_rdp_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Saber quem abriu conexão com qual máquina é metade do valor."""
        conceder(db_session, usuario, "dispositivos/*", TODAS)
        self._dispositivo(client, autenticado)
        client.put(
            "/api/v1/dispositivos/srv-contabil/acessos",
            headers=autenticado,
            json={"acessos": [{"metodo": "rdp", "identificador": "10.0.1.20"}]},
        )
        client.get("/api/v1/dispositivos/srv-contabil/rdp", headers=autenticado)

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "acesso_remoto_iniciado"
            )
        ).one()
        assert "10.0.1.20" in evento.reason

    def test_sem_rdp_cadastrado_recusa(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", TODAS)
        self._dispositivo(client, autenticado)
        assert client.get(
            "/api/v1/dispositivos/srv-contabil/rdp", headers=autenticado
        ).status_code == 404

    def test_acesso_externo_pode_ser_registrado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """AnyDesk acontece fora daqui: sem este registro, a trilha teria um
        buraco nos acessos mais informais."""
        conceder(db_session, usuario, "dispositivos/*", TODAS)
        self._dispositivo(client, autenticado)

        resposta = client.post(
            "/api/v1/dispositivos/srv-contabil/acesso-registrado?metodo=anydesk",
            headers=autenticado,
        )
        assert resposta.status_code == 204

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "acesso_remoto_iniciado"
            )
        ).one()
        assert "anydesk" in evento.reason


class TestExportacao:
    def test_certificado_exporta_sem_chave_privada(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "certificados/*", TODAS)
        agora = datetime.now(UTC)
        client.post(
            "/api/v1/certificados",
            headers=autenticado,
            json={
                "name": "api-rede",
                "display_name": "api.exemplo.com.br",
                "subject": "CN=api.exemplo.com.br",
                "issuer": "Let's Encrypt",
                "not_before": (agora - timedelta(days=30)).isoformat(),
                "not_after": (agora + timedelta(days=60)).isoformat(),
            },
        )

        exportado = client.get(
            "/api/v1/certificados/api-rede/exportar", headers=autenticado
        )
        assert exportado.status_code == 200
        corpo = exportado.json()
        assert corpo["emissor"] == "Let's Encrypt"
        assert "chave privada não é exportada" in corpo["observacao"]
        # Nenhum campo que pudesse conter material criptográfico.
        assert not any(
            k in corpo for k in ("chave", "private_key", "valor", "value")
        )

    def test_exportar_certificado_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "certificados/*", TODAS)
        agora = datetime.now(UTC)
        client.post(
            "/api/v1/certificados",
            headers=autenticado,
            json={
                "name": "c1", "display_name": "c1", "subject": "CN=c1",
                "issuer": "CA",
                "not_before": (agora - timedelta(days=1)).isoformat(),
                "not_after": (agora + timedelta(days=60)).isoformat(),
            },
        )
        client.get("/api/v1/certificados/c1/exportar", headers=autenticado)

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "certificado_exportado"
            )
        ).one()
        assert "sem chave privada" in evento.reason

    def test_excluir_certificado(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "certificados/*", TODAS)
        agora = datetime.now(UTC)
        client.post(
            "/api/v1/certificados",
            headers=autenticado,
            json={
                "name": "velho", "display_name": "velho", "subject": "CN=v",
                "issuer": "CA",
                "not_before": (agora - timedelta(days=400)).isoformat(),
                "not_after": (agora - timedelta(days=30)).isoformat(),
            },
        )
        assert client.delete(
            "/api/v1/certificados/velho", headers=autenticado
        ).status_code == 204
        assert client.get(
            "/api/v1/certificados", headers=autenticado
        ).json() == []

    def test_credencial_exporta_sem_o_valor(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O valor sai pela rota de revelar, uma por vez, com auditoria."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv", "display_name": "Servidor", "address": "10.0.0.5"},
        )
        criada = client.post(
            "/api/v1/dispositivos/srv/credenciais",
            headers=autenticado,
            json={"name": "senha-root", "username": "root", "rotation_days": 60},
        )

        exportado = client.get(
            f"/api/v1/credenciais/{criada.json()['id']}/exportar",
            headers=autenticado,
        )
        assert exportado.status_code == 200
        corpo = exportado.json()
        assert corpo["usuario"] == "root"
        assert corpo["rotacao_dias"] == 60
        assert corpo["dispositivo"] == "Servidor"
        assert "não é exportado" in corpo["observacao"]
        assert not any(k in corpo for k in ("senha", "valor", "value", "password"))

    def test_sem_permissao_nao_exporta(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "certificados/*", TODAS, nome_politica="p-tudo")
        agora = datetime.now(UTC)
        client.post(
            "/api/v1/certificados",
            headers=autenticado,
            json={
                "name": "c1", "display_name": "c1", "subject": "CN=c1",
                "issuer": "CA",
                "not_before": (agora - timedelta(days=1)).isoformat(),
                "not_after": (agora + timedelta(days=60)).isoformat(),
            },
        )

        from app.infrastructure.crypto.passwords import Argon2PasswordHasher

        outro = UserModel(
            id="ux", email="ze@exemplo.com.br", full_name="Zé",
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
            "/api/v1/certificados/c1/exportar", headers=dele
        ).status_code == 403
