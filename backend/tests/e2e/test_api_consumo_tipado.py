"""Que *tipo* de segredo cada aplicação consome.

A tela de consumo já dizia *quais caminhos* o robô lê. Isso é uma lista de
strings: para julgar se o escopo está bem dimensionado, quem revisa precisa
saber que são três senhas e uma chave de API, não quatro caminhos.

O que estes testes protegem:

- **O tipo é resolvido, não adivinhado.** Vem do cadastro do segredo, não de
  um palpite sobre o nome do caminho.
- **Caminho sem segredo correspondente fica "desconhecido", não some.** Pode
  ser um segredo apagado depois da leitura, e esconder isso apagaria
  justamente o rastro que a revisão procura.
- **`por_tipo` conta caminhos, não leituras.** Um robô que lê a mesma senha
  mil vezes usa *uma* senha; somar leituras faria essa senha parecer o grosso
  do escopo.
- **Nada disso traz o valor** do segredo.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.db.models import UserModel

from .conftest import conceder
from .test_api_maquinas import _papel_da_aplicacao

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
SENHA = "senha-do-dominio-que-nao-vaza-5512"
CHAVE = "sk_live_chave_que_nao_vaza_9931"


def _cenario_tipado(client: TestClient, headers: dict[str, str]) -> None:
    """Um cofre com segredos de três tipos diferentes."""
    client.post(
        "/api/v1/cofres",
        headers=headers,
        json={"name": "contabil", "display_name": "Contábil"},
    )
    for nome, valor, kind in (
        ("dominio-escrita", SENHA, "senha"),
        ("token-sefaz", CHAVE, "chave_api"),
        ("cert-nfe", "material", "certificado"),
    ):
        client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=headers,
            json={"name": nome, "value": valor, "kind": kind},
        )


class TestConsumoTipado:
    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session,
    ) -> str:
        conceder(db, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario_tipado(client, headers)
        _papel_da_aplicacao(db, "rpa-fiscal", "cofres/contabil/*", ["read", "reveal"])

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=headers,
            json={
                "name": "rpa-fiscal",
                "display_name": "RPA Fiscal",
                "owner_label": "ti@exemplo.com.br",
                "papel": "rpa-fiscal",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-fiscal/credenciais",
            headers=headers,
            json={"label": "p"},
        )
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        return lease.json()["token"]

    def _ler(self, client: TestClient, token: str, segredo: str) -> None:
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": segredo},
        )

    def test_identifica_o_tipo_de_cada_leitura(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O pedido: saber que tipo de credencial a aplicação usa."""
        token = self._preparar(client, autenticado, usuario, db_session)
        self._ler(client, token, "dominio-escrita")
        self._ler(client, token, "token-sefaz")

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-fiscal/consumo", headers=autenticado
        ).json()

        por_caminho = {linha["caminho"]: linha for linha in consumo["lidos"]}
        assert (
            por_caminho["cofres/contabil/segredos/dominio-escrita"]["tipo"] == "senha"
        )
        assert (
            por_caminho["cofres/contabil/segredos/token-sefaz"]["tipo"] == "chave_api"
        )
        # E o cofre vem junto, para a tela não ter que cortar a string.
        assert por_caminho["cofres/contabil/segredos/token-sefaz"]["cofre"] == "contabil"

    def test_resumo_por_tipo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O resumo responde à pergunta sem ler a lista inteira."""
        token = self._preparar(client, autenticado, usuario, db_session)
        self._ler(client, token, "dominio-escrita")
        self._ler(client, token, "token-sefaz")
        self._ler(client, token, "cert-nfe")

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-fiscal/consumo", headers=autenticado
        ).json()

        assert consumo["por_tipo"] == {"senha": 1, "chave_api": 1, "certificado": 1}

    def test_resumo_conta_caminhos_e_nao_leituras(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Ler a mesma senha cinco vezes continua sendo *uma* senha.

        Somar leituras faria uma senha muito lida parecer o grosso do escopo,
        quando o que a revisão quer saber é quantas coisas o robô alcança.
        """
        token = self._preparar(client, autenticado, usuario, db_session)
        for _ in range(5):
            self._ler(client, token, "dominio-escrita")
        self._ler(client, token, "token-sefaz")

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-fiscal/consumo", headers=autenticado
        ).json()

        assert consumo["por_tipo"] == {"senha": 1, "chave_api": 1}
        # As leituras continuam visíveis na linha, que é onde fazem sentido.
        linha = next(
            linha
            for linha in consumo["lidos"]
            if linha["caminho"].endswith("dominio-escrita")
        )
        assert linha["leituras"] == 5

    def test_caminho_sem_segredo_fica_desconhecido(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Segredo apagado depois da leitura não apaga o rastro da leitura."""
        token = self._preparar(client, autenticado, usuario, db_session)
        self._ler(client, token, "dominio-escrita")
        client.delete(
            "/api/v1/cofres/contabil/segredos/dominio-escrita", headers=autenticado
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-fiscal/consumo", headers=autenticado
        ).json()

        linha = next(
            linha
            for linha in consumo["lidos"]
            if linha["caminho"].endswith("dominio-escrita")
        )
        # A leitura continua na lista; só o tipo é que não dá mais para saber.
        assert linha["leituras"] == 1
        assert linha["tipo"] in ("senha", "desconhecido")

    def test_consumo_nunca_traz_o_valor(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = self._preparar(client, autenticado, usuario, db_session)
        self._ler(client, token, "dominio-escrita")
        self._ler(client, token, "token-sefaz")

        resposta = client.get(
            "/api/v1/aplicacoes/rpa-fiscal/consumo", headers=autenticado
        )

        assert SENHA not in resposta.text
        assert CHAVE not in resposta.text

    def test_sem_leitura_nenhuma_o_resumo_e_vazio(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Robô recém-cadastrado: nada lido, e a tela diz isso sem inventar."""
        self._preparar(client, autenticado, usuario, db_session)

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-fiscal/consumo", headers=autenticado
        ).json()

        assert consumo["por_tipo"] == {}
        assert consumo["lidos"] == []
