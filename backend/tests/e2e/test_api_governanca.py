"""Governança da API: o que é registrado, o que não é, e quem pode ver.

Os dois comportamentos que mais importam aqui:

1. **A tela do próprio Vault não entra no relatório.** Era o recorte pedido:
   governar o consumo de fora, não o sistema conversando consigo mesmo.
2. **O corpo da requisição não é guardado em lugar nenhum.** Uma chamada que
   cria segredo carrega a senha; se ela aparecesse na tabela de uso, estaria
   em claro, fora do cofre e fora da cifragem de envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.apiusage.entities import Origem, registrar_chamada
from app.infrastructure.db.apiusage_repo import RegistroDeUsoSql
from app.infrastructure.db.models import ChamadaApiModel, UserModel

from .conftest import EMAIL, SENHA, conceder

BASE = "/api/v1/api-uso"


@pytest.fixture
def token(client: TestClient, usuario: UserModel) -> str:
    resposta = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
    )
    assert resposta.status_code == 200
    return resposta.json()["tokens"]["access_token"]


@pytest.fixture
def admin(db_session: Session, usuario: UserModel) -> UserModel:
    conceder(db_session, usuario, "auditoria", ["admin"], nome_politica="audit-admin")
    return usuario


def _semear(db: Session, quantas: int = 3, **kwargs) -> None:
    """Põe chamadas no registro sem passar pela rede."""
    registro = RegistroDeUsoSql(db)
    base = {
        "metodo": "GET",
        "caminho": "/api/v1/maquina/segredo",
        "status": 200,
        "origem": Origem.APLICACAO,
        "duracao_ms": 10,
        "aplicacao_id": "app-1",
        "aplicacao_nome": "Robô da folha",
    }
    base.update(kwargs)
    for _ in range(quantas):
        registro.registrar(registrar_chamada(**base))


def _so_semeadas(linhas: list[dict]) -> list[dict]:
    """Descarta o que o próprio teste gerou ao se autenticar.

    O login da fixture `token` passa pelo middleware e vira registro, como
    qualquer chamada externa — é o comportamento correto. Contar "tudo o
    que está na tabela" misturaria esse ruído com o que o teste semeou, e
    os números passariam a depender de quantas vezes a fixture rodou.
    """
    return [linha for linha in linhas if not linha["caminho"].startswith("/api/v1/auth/")]


class TestPermissao:
    def test_sem_token_nao_entra(self, client: TestClient):
        assert client.get(f"{BASE}/panorama").status_code == 401
        assert client.get(f"{BASE}/chamadas").status_code == 401

    def test_sem_admin_de_auditoria_e_recusado(
        self, client: TestClient, token: str, usuario: UserModel
    ):
        # O relatório mostra IP, agente e padrão de consumo de cada
        # integração: é mapa de superfície de ataque para quem não deveria.
        resposta = client.get(
            f"{BASE}/panorama", headers={"Authorization": f"Bearer {token}"}
        )
        assert resposta.status_code == 403

    def test_a_negativa_fica_na_trilha(
        self, client: TestClient, token: str, usuario: UserModel, db_session: Session
    ):
        from app.infrastructure.db.models import AuditEventModel

        client.get(f"{BASE}/panorama", headers={"Authorization": f"Bearer {token}"})
        eventos = (
            db_session.query(AuditEventModel)
            .filter(AuditEventModel.action == "acesso_negado")
            .all()
        )
        # Sem o commit antes do raise, o rollback levaria o evento embora e
        # a tentativa não deixaria rastro.
        assert len(eventos) >= 1

    def test_com_admin_responde(
        self, client: TestClient, token: str, admin: UserModel
    ):
        resposta = client.get(
            f"{BASE}/panorama", headers={"Authorization": f"Bearer {token}"}
        )
        assert resposta.status_code == 200


class TestPanorama:
    def test_agrega_por_consumidor(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 5)
        corpo = client.get(
            f"{BASE}/panorama", headers={"Authorization": f"Bearer {token}"}
        ).json()

        nossos = [c for c in corpo["consumidores"] if c["rotulo"] == "Robô da folha"]
        assert len(nossos) == 1
        assert nossos[0]["chamadas"] == 5

    def test_resumo_bate_com_a_lista(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 4)
        _semear(db_session, 2, aplicacao_id="app-2", aplicacao_nome="Robô do backup")
        corpo = client.get(
            f"{BASE}/panorama", headers={"Authorization": f"Bearer {token}"}
        ).json()

        # O número do topo tem de ser a soma do que está logo abaixo. Dois
        # recortes que se pretendem iguais divergem assim que alguém mexe em
        # um filtro e esquece do outro.
        soma = sum(c["chamadas"] for c in corpo["consumidores"])
        assert corpo["resumo"]["chamadas"] == soma
        assert corpo["resumo"]["consumidores"] == len(corpo["consumidores"])

    def test_conta_recusadas_separado(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 3)
        _semear(db_session, 2, status=403)
        corpo = client.get(
            f"{BASE}/panorama", headers={"Authorization": f"Bearer {token}"}
        ).json()
        nosso = [c for c in corpo["consumidores"] if c["rotulo"] == "Robô da folha"][0]
        assert nosso["chamadas"] == 5
        assert nosso["recusadas"] == 2

    def test_agrega_por_rota(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 3, caminho="/api/v1/cofres")
        _semear(db_session, 1, caminho="/api/v1/credenciais")
        corpo = client.get(
            f"{BASE}/panorama", headers={"Authorization": f"Bearer {token}"}
        ).json()
        rotas = {r["caminho"]: r["chamadas"] for r in corpo["rotas"]}
        assert rotas["/api/v1/cofres"] == 3
        assert rotas["/api/v1/credenciais"] == 1


class TestRecorteDaTela:
    def test_chamadas_da_tela_nao_aparecem(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        """Uma linha de origem `tela` é filtrada mesmo se chegar ao banco.

        A exclusão vale na gravação (o middleware não registra) e na
        consulta. A segunda é a que este teste prova: se um registro entrar
        por outro caminho — importação, classificação errada —, ele ainda
        assim não polui o relatório.
        """
        _semear(db_session, 4, origem=Origem.TELA, aplicacao_id=None,
                aplicacao_nome="", usuario_email="ana.souza@exemplo.com.br")
        _semear(db_session, 2)

        linhas = _so_semeadas(
            client.get(
                f"{BASE}/chamadas", headers={"Authorization": f"Bearer {token}"}
            ).json()
        )
        assert len(linhas) == 2
        assert all(linha["origem"] != "tela" for linha in linhas)

    def test_middleware_nao_registra_chamada_da_interface(
        self, client: TestClient, db_session: Session, usuario: UserModel
    ):
        """Requisição com a cara da tela não entra no banco.

        Pela rede, com os cabeçalhos que o navegador manda: `Origin`
        conhecido e `Sec-Fetch-Site: same-origin`. É o recorte pedido —
        governar o consumo de fora, não o sistema falando consigo mesmo.
        """
        client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": SENHA},
            headers={
                "origin": "http://localhost:5173",
                "sec-fetch-site": "same-origin",
            },
        )
        assert db_session.query(ChamadaApiModel).count() == 0

    def test_interface_same_origin_sem_origin_tambem_fica_de_fora(
        self, client: TestClient, db_session: Session, usuario: UserModel
    ):
        """Produção: front e API no mesmo host, sem cabeçalho `Origin`.

        O navegador omite `Origin` em GET same-origin, então este é o caso
        comum e não a exceção. Exigi-lo fazia toda a navegação da interface
        entrar no relatório — bug visto na tela, com o sistema no ar.
        """
        client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": SENHA},
            headers={"sec-fetch-site": "same-origin"},
        )
        assert db_session.query(ChamadaApiModel).count() == 0

    def test_middleware_registra_a_mesma_chamada_vinda_de_fora(
        self, client: TestClient, db_session: Session, usuario: UserModel
    ):
        """A mesma rota, sem os cabeçalhos do navegador, é registrada.

        Par do teste acima: os dois juntos mostram que o que decide é a
        origem, e não a rota — se fosse a rota, um robô chamando `/login`
        também sumiria.
        """
        client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": SENHA},
            headers={"user-agent": "python-requests/2.31"},
        )
        linhas = db_session.query(ChamadaApiModel).all()
        assert len(linhas) == 1
        assert linhas[0].origem == "externa"
        assert linhas[0].caminho == "/api/v1/auth/login"
        assert linhas[0].agente == "python-requests/2.31"

    def test_origin_forjado_sem_navegador_ainda_e_registrado(
        self, client: TestClient, db_session: Session, usuario: UserModel
    ):
        """Mandar `Origin` na mão não basta para sair do relatório.

        `Sec-Fetch-Site` é preenchido pelo navegador e não por quem escreve
        a requisição. Exigir os dois é o que impede um script de se
        disfarçar de interface e sumir da governança.
        """
        client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": SENHA},
            headers={"origin": "http://localhost:5173", "user-agent": "curl/8.0"},
        )
        assert db_session.query(ChamadaApiModel).count() == 1

    def test_listagem_tambem_esconde_a_tela(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 3, origem=Origem.TELA, aplicacao_id=None, aplicacao_nome="")
        _semear(db_session, 1)
        linhas = _so_semeadas(
            client.get(
                f"{BASE}/chamadas", headers={"Authorization": f"Bearer {token}"}
            ).json()
        )
        assert len(linhas) == 1
        assert linhas[0]["origem"] == "aplicacao"


class TestFiltros:
    def test_filtra_por_origem(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 2)
        _semear(db_session, 3, origem=Origem.EXTERNA, aplicacao_id=None,
                aplicacao_nome="", ip="10.0.0.9")
        linhas = _so_semeadas(
            client.get(
                f"{BASE}/chamadas?origem=externa",
                headers={"Authorization": f"Bearer {token}"},
            ).json()
        )
        assert len(linhas) == 3
        assert all(linha["origem"] == "externa" for linha in linhas)

    def test_filtra_por_resultado(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 2)
        _semear(db_session, 4, status=401)
        linhas = client.get(
            f"{BASE}/chamadas?resultado=recusado",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        assert len(linhas) == 4

    def test_filtra_por_aplicacao(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        _semear(db_session, 2, aplicacao_id="app-1", aplicacao_nome="A")
        _semear(db_session, 5, aplicacao_id="app-2", aplicacao_nome="B")
        linhas = client.get(
            f"{BASE}/chamadas?aplicacao=app-2",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        assert len(linhas) == 5

    def test_periodo_exclui_o_que_e_antigo(
        self, client: TestClient, token: str, admin: UserModel, db_session: Session
    ):
        antigo = datetime.now(UTC) - timedelta(days=30)
        _semear(db_session, 3, quando=antigo)
        _semear(db_session, 2)
        linhas = _so_semeadas(
            client.get(
                f"{BASE}/chamadas?dias=7",
                headers={"Authorization": f"Bearer {token}"},
            ).json()
        )
        assert len(linhas) == 2

    def test_dias_fora_da_faixa_e_recusado(
        self, client: TestClient, token: str, admin: UserModel
    ):
        assert (
            client.get(
                f"{BASE}/panorama?dias=400",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            == 422
        )


class TestCorpoNaoVazaParaOBanco:
    def test_tabela_nao_tem_coluna_de_corpo(self):
        """A restrição vale na estrutura do banco, não só no domínio.

        Verificar a tabela e não só a entidade fecha o caminho de alguém
        acrescentar a coluna "só para depurar" e popular por SQL direto.
        """
        colunas = set(ChamadaApiModel.__table__.columns.keys())
        proibidas = {"corpo", "body", "payload", "conteudo", "request_body", "dados"}
        assert colunas & proibidas == set()

    def test_post_com_senha_no_corpo_nao_deixa_a_senha_no_registro(
        self, client: TestClient, db_session: Session, usuario: UserModel
    ):
        """Uma chamada de login traz a senha no corpo. Nada dela pode sobrar.

        Vai pela rede de verdade, com o middleware no caminho, e depois
        varre **todas** as colunas de texto do que foi registrado. Procurar
        a senha coluna a coluna, em vez de só conferir que não há campo
        `corpo`, pega também o caso de ela acabar no caminho ou no agente.
        """
        senha_marcada = "senha-que-nao-pode-vazar-9z"
        client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": senha_marcada},
            headers={"user-agent": "curl/8.0"},
        )

        linhas = db_session.query(ChamadaApiModel).all()
        # Sem esta asserção o teste passa varrendo tabela vazia, provando
        # nada. Já aconteceu: o middleware gravava no banco das settings
        # reais em vez do banco injetado, e a varredura não via linha
        # nenhuma enquanto a asserção seguinte seguia verde.
        assert linhas, "nada foi registrado: a varredura abaixo seria vazia"

        for linha in linhas:
            for coluna in linha.__table__.columns:
                valor = getattr(linha, coluna.name)
                if isinstance(valor, str):
                    assert senha_marcada not in valor, f"senha vazou em {coluna.name}"


class TestExpurgo:
    def test_apaga_o_que_passou_da_retencao(self, db_session: Session):
        registro = RegistroDeUsoSql(db_session)
        _semear(db_session, 3, quando=datetime.now(UTC) - timedelta(days=120))
        _semear(db_session, 2)

        apagadas = registro.expurgar(datetime.now(UTC) - timedelta(days=90))
        assert apagadas == 3
        assert db_session.query(ChamadaApiModel).count() == 2

    def test_expurgo_sem_nada_antigo_nao_apaga(self, db_session: Session):
        registro = RegistroDeUsoSql(db_session)
        _semear(db_session, 2)
        assert registro.expurgar(datetime.now(UTC) - timedelta(days=90)) == 0
        assert db_session.query(ChamadaApiModel).count() == 2
