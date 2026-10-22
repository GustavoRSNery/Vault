"""Origem e consumo da sessão: de onde partiu e o que usou.

São duas perguntas diferentes que a revisão faz sobre a mesma sessão:

- **De onde?** Qual máquina abriu. O IP não basta: muda, se repete atrás de
  NAT e não distingue duas pessoas na mesma rede.
- **Com o quê?** Qual credencial ou chave foi usada para entrar.

A invariante que estes testes protegem: **o consumo guarda o nome e o
caminho, nunca o valor.** Saber que a sessão usou
`cofres/infra/segredos/senha-root` responde à auditoria sem revelar nada —
quem quiser o valor passa pela rota de revelar, que registra evento próprio.
Um campo de valor aqui transformaria a lista de sessões num despejo de
segredos que ninguém consegue auditar depois.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.db.models import UserModel

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
SENHA_REAL = "senha-root-que-nao-pode-vazar-8812"


def _abrir(client: TestClient, headers: dict[str, str], **extra):  # noqa: ANN003
    corpo = {"tipo": "ssh", "alvo": "srv-contabil", "motivo": "manutencao", **extra}
    return client.post("/api/v1/sessoes", headers=headers, json=corpo)


class TestOrigemDaSessao:
    def test_identifica_a_maquina_de_origem(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = _abrir(
            client,
            autenticado,
            origem_hostname="NOTE-CONTABIL-07",
            origem_dispositivo="note-contabil-07",
        )

        assert resposta.status_code == 201
        origem = resposta.json()["origem"]
        assert origem["hostname"] == "NOTE-CONTABIL-07"
        assert origem["dispositivo_name"] == "note-contabil-07"
        assert origem["identificada"] is True
        # A tela mostra o mais específico: o dispositivo do inventário.
        assert origem["descricao"] == "note-contabil-07"

    def test_sem_hostname_cai_para_o_ip(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Pior resolução, mas ainda uma resposta — melhor que "desconhecido"
        tendo o dado à mão."""
        resposta = _abrir(client, autenticado)

        origem = resposta.json()["origem"]
        assert origem["hostname"] == ""
        # O IP do cliente de teste entra como origem.
        assert origem["descricao"] == origem["ip_address"] or (
            origem["descricao"] == "origem não identificada"
        )

    def test_hostname_vence_o_ip_na_descricao(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = _abrir(client, autenticado, origem_hostname="DESKTOP-FISCAL")

        assert resposta.json()["origem"]["descricao"] == "DESKTOP-FISCAL"

    def test_user_agent_vem_do_servidor(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """O cliente não dita o próprio user-agent no corpo: o valor
        registrado é o mesmo que a auditoria viu."""
        resposta = client.post(
            "/api/v1/sessoes",
            headers={**autenticado, "User-Agent": "VaultCliente/1.2"},
            json={
                "tipo": "ssh",
                "alvo": "srv",
                "motivo": "manutencao",
                "origem_hostname": "PC-01",
            },
        )

        assert resposta.json()["origem"]["user_agent"] == "VaultCliente/1.2"

    def test_origem_sobrevive_a_releitura(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        criada = _abrir(client, autenticado, origem_hostname="PC-TESOURARIA")

        relida = client.get(
            f"/api/v1/sessoes/{criada.json()['id']}", headers=autenticado
        )

        assert relida.json()["origem"]["hostname"] == "PC-TESOURARIA"


class TestConsumoDaSessao:
    def test_identifica_credencial_usada(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = _abrir(
            client,
            autenticado,
            consumo_tipo="credencial",
            consumo_nome="senha-root",
            consumo_pertence_a="Servidor Contábil",
            segredo_path="cofres/infra/segredos/senha-root",
        )

        assert resposta.status_code == 201
        consumo = resposta.json()["consumo"]
        assert consumo["tipo"] == "credencial"
        assert consumo["nome"] == "senha-root"
        assert consumo["caminho"] == "cofres/infra/segredos/senha-root"
        assert consumo["saiu_do_cofre"] is True
        assert consumo["descricao"] == "Credencial: senha-root (Servidor Contábil)"

    def test_identifica_chave_de_api_usada(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """O caso que o usuário pediu: distinguir consumo de chave de API."""
        resposta = _abrir(
            client,
            autenticado,
            tipo="web",
            alvo="api.sefaz.gov.br",
            consumo_tipo="chave_api",
            consumo_nome="SEFAZ NF-e",
            consumo_pertence_a="SEFAZ",
        )

        consumo = resposta.json()["consumo"]
        assert consumo["tipo"] == "chave_api"
        assert consumo["descricao"] == "Chave de API: SEFAZ NF-e (SEFAZ)"
        assert consumo["saiu_do_cofre"] is True

    def test_credencial_propria_nao_saiu_do_cofre(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Distinção que muda a leitura da revisão: entrar com o que a
        pessoa sabe não é o mesmo que tirar um segredo guardado."""
        resposta = _abrir(client, autenticado, consumo_tipo="propria", consumo_nome="-")

        consumo = resposta.json()["consumo"]
        assert consumo["saiu_do_cofre"] is False
        assert consumo["descricao"] == "Credencial da própria pessoa"

    def test_consumo_identificado_exige_nome(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Registro sem nome não responde à pergunta da auditoria."""
        resposta = _abrir(client, autenticado, consumo_tipo="credencial")

        assert resposta.status_code == 422

    def test_sem_declarar_fica_nao_identificado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """O padrão é honesto: não sabemos, e a tela diz isso."""
        consumo = _abrir(client, autenticado).json()["consumo"]

        assert consumo["tipo"] == "nao_identificado"
        assert consumo["descricao"] == "Não identificado"
        assert consumo["saiu_do_cofre"] is False


class TestOValorNuncaAparece:
    """A invariante central desta leva."""

    def test_sessao_nunca_traz_valor_de_segredo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O caminho identifica o segredo; o valor continua só no cofre."""
        conceder(db_session, usuario, "cofres/*", TODAS)
        client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": "infra", "display_name": "Infra"},
        )
        client.post(
            "/api/v1/cofres/infra/segredos",
            headers=autenticado,
            json={"name": "senha-root", "value": SENHA_REAL, "kind": "senha"},
        )

        criada = _abrir(
            client,
            autenticado,
            consumo_tipo="credencial",
            consumo_nome="senha-root",
            segredo_path="cofres/infra/segredos/senha-root",
        )

        # Nem na criação, nem na listagem, nem no detalhe.
        assert SENHA_REAL not in criada.text
        assert SENHA_REAL not in client.get(
            "/api/v1/sessoes", headers=autenticado
        ).text
        assert SENHA_REAL not in client.get(
            f"/api/v1/sessoes/{criada.json()['id']}", headers=autenticado
        ).text

        # E o caminho está lá, que é o que a auditoria precisa.
        assert (
            criada.json()["consumo"]["caminho"]
            == "cofres/infra/segredos/senha-root"
        )

    def test_listagem_traz_origem_e_consumo(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """A tela precisa dos dois campos sem abrir cada sessão."""
        _abrir(
            client,
            autenticado,
            origem_hostname="PC-FISCAL",
            consumo_tipo="chave_api",
            consumo_nome="SEFAZ NF-e",
        )

        lista = client.get("/api/v1/sessoes", headers=autenticado).json()
        sessao = lista[0] if isinstance(lista, list) else lista["items"][0]

        assert sessao["origem"]["descricao"] == "PC-FISCAL"
        assert sessao["consumo"]["nome"] == "SEFAZ NF-e"
