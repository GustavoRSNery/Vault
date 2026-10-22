"""Panorama por domínio: os números que abrem cada aba do painel.

O que se protege aqui, em ordem de gravidade:

1. **Vazamento por contagem.** Um número que some recursos que a pessoa não
   pode ver revela a existência deles. "Você tem acesso a 0 certificados, mas
   existem 7" é exatamente o que a busca evita ao varrer só o alcançável.
2. **Número que desmente a tela.** As contagens precisam bater com o que as
   listagens devolvem; se divergirem, o painel vira a fonte de uma dúvida
   em vez de uma resposta.
3. **Segredo no corpo.** O panorama nunca carrega valor — só contagens e, no
   máximo, o nome de algo que o usuário já pode listar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.db.models import UserModel

from .conftest import conceder


def _tudo(db_session: Session, usuario: UserModel) -> None:
    """Dá ao usuário acesso de leitura e escrita a todos os domínios."""
    # Com curinga: a política vale para os FILHOS do caminho, que é onde os
    # recursos moram (`certificados/web`, não `certificados`).
    for i, caminho in enumerate(
        [
            "cofres",
            "cofres/*",
            "dispositivos/*",
            "credenciais/*",
            "certificados/*",
            "chaves-api/*",
        ]
    ):
        conceder(
            db_session,
            usuario,
            caminho,
            ["read", "list", "create", "update", "delete", "reveal"],
            nome_politica=f"politica-{i}",
        )


def _cria_certificado(client: TestClient, headers, nome: str, dias: int):
    agora = datetime.now(UTC)
    return client.post(
        "/api/v1/certificados",
        headers=headers,
        json={
            "name": nome,
            "display_name": f"{nome}.exemplo.com.br",
            "subject": f"CN={nome}.exemplo.com.br",
            "issuer": "Let's Encrypt",
            "not_before": (agora - timedelta(days=60)).isoformat(),
            "not_after": (agora + timedelta(days=dias)).isoformat(),
        },
    )


def test_sem_permissao_tudo_zera_em_vez_de_dar_erro(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Quem não vê nada recebe zeros — não um 403 nem um número de outro.

    Zerar é o comportamento certo: o painel é a primeira tela depois do
    login, e falhar nela faria parecer que o sistema está quebrado quando o
    que falta é permissão.
    """
    corpo = client.get("/api/v1/panorama", headers=autenticado).json()

    assert corpo["cofres"]["total"] == 0
    assert corpo["credenciais"]["total"] == 0
    assert corpo["certificados"]["total"] == 0
    assert corpo["chaves"]["total"] == 0
    assert corpo["dispositivos"]["total"] == 0


def test_contagem_nao_vaza_o_que_o_usuario_nao_ve(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """O número conta o alcançável, não o acervo.

    Aqui existem DOIS certificados no banco e o usuário só enxerga um. Se a
    contagem dissesse 2, ela denunciaria a existência do outro.
    """
    conceder(db_session, usuario, "certificados/*", ["read", "list", "create"])
    assert _cria_certificado(client, autenticado, "meu", 90).status_code == 201

    # O segundo é criado por um admin e fica FORA do alcance do usuário: a
    # política concedida acima cobre `certificados`, então restringimos pelo
    # caminho específico com um deny.
    conceder(
        db_session,
        usuario,
        "certificados/oculto",
        ["read", "list"],
        efeito="deny",
        nome_politica="politica-nega-oculto",
    )
    assert _cria_certificado(client, autenticado, "oculto", 30).status_code == 201

    corpo = client.get("/api/v1/panorama", headers=autenticado).json()

    assert corpo["certificados"]["total"] == 1, "só o alcançável entra na conta"
    bruto = client.get("/api/v1/panorama", headers=autenticado).text
    assert "oculto" not in bruto, "nem o nome do que está fora pode aparecer"


def test_certificados_separam_vencido_de_vencendo(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Vencido e vencendo são situações diferentes e contam separado.

    Somá-los esconderia o que já quebrou dentro do que ainda dá para
    resolver — e é o vencido que derruba conexão TLS agora.
    """
    conceder(db_session, usuario, "certificados/*", ["read", "list", "create"])
    _cria_certificado(client, autenticado, "vencido", -5)
    _cria_certificado(client, autenticado, "vencendo", 10)
    _cria_certificado(client, autenticado, "tranquilo", 300)

    cert = client.get("/api/v1/panorama", headers=autenticado).json()["certificados"]

    assert cert["total"] == 3
    assert cert["vencidos"] == 1
    assert cert["vencendo"] == 1
    assert cert["validos"] == 1
    # As três parcelas fecham o total: nenhuma situação fica sem contar.
    assert cert["vencidos"] + cert["vencendo"] + cert["validos"] == cert["total"]
    # O mais próximo de vencer é o que se olha antes de renovar — e é o
    # "vencendo", não o já vencido.
    assert cert["proximo_nome"] == "vencendo.exemplo.com.br"
    assert cert["proximo_dias"] is not None and cert["proximo_dias"] <= 10


def test_credenciais_contam_custodia_e_rotacao(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Credencial nunca rotacionada pode ainda ser a senha de fábrica."""
    _tudo(db_session, usuario)
    client.post(
        "/api/v1/dispositivos",
        headers=autenticado,
        json={"name": "fw", "display_name": "Firewall", "kind": "firewall"},
    )
    criada = client.post(
        "/api/v1/dispositivos/fw/credenciais",
        headers=autenticado,
        json={"name": "senha-admin", "username": "admin", "rotation_days": 90},
    )
    assert criada.status_code == 201, criada.text

    cred = client.get("/api/v1/panorama", headers=autenticado).json()["credenciais"]

    assert cred["total"] == 1
    assert cred["nunca_rotacionadas"] == 1, "acabou de ser criada, nunca rotacionou"
    assert cred["em_custodia"] == 0


def test_cofres_contam_segredos_e_lixeira_separados(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Segredo na lixeira não conta como segredo ativo.

    Somá-los inflaria o acervo com o que foi deliberadamente descartado.
    """
    _tudo(db_session, usuario)
    client.post(
        "/api/v1/cofres",
        headers=autenticado,
        json={"name": "producao", "display_name": "Produção"},
    )
    for nome in ("senha-a", "senha-b"):
        resposta = client.post(
            "/api/v1/cofres/producao/segredos",
            headers=autenticado,
            json={"name": nome, "value": "v", "kind": "senha"},
        )
        assert resposta.status_code in (200, 201), resposta.text

    antes = client.get("/api/v1/panorama", headers=autenticado).json()["cofres"]
    assert antes["total"] == 1
    assert antes["segredos"] == 2
    assert antes["na_lixeira"] == 0

    client.delete("/api/v1/cofres/producao/segredos/senha-b", headers=autenticado)

    depois = client.get("/api/v1/panorama", headers=autenticado).json()["cofres"]
    assert depois["segredos"] == 1, "o apagado sai da contagem de ativos"
    assert depois["na_lixeira"] == 1, "e aparece na lixeira"


def test_panorama_nao_carrega_valor_de_segredo(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """A prova direta: o valor gravado não aparece em lugar nenhum do corpo."""
    _tudo(db_session, usuario)
    client.post(
        "/api/v1/cofres",
        headers=autenticado,
        json={"name": "cofre", "display_name": "Cofre"},
    )
    client.post(
        "/api/v1/cofres/cofre/segredos",
        headers=autenticado,
        json={"name": "root", "value": "SENHA-QUE-NAO-PODE-VAZAR-9912", "kind": "senha"},
    )

    bruto = client.get("/api/v1/panorama", headers=autenticado).text

    assert "SENHA-QUE-NAO-PODE-VAZAR-9912" not in bruto
    assert '"value"' not in bruto


def test_sem_token_e_recusado(client: TestClient) -> None:
    """O panorama descreve o acervo; anônimo não descreve nada."""
    assert client.get("/api/v1/panorama").status_code in (401, 403)


def test_cofre_fora_do_alcance_nao_entra_na_contagem(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """A contagem de cofres conta o alcançável, não o acervo.

    O mesmo princípio dos certificados, exercitado no domínio de cofres —
    que é onde os segredos moram, e portanto onde o vazamento por contagem
    doeria mais.
    """
    _tudo(db_session, usuario)
    for nome in ("meu", "alheio"):
        resposta = client.post(
            "/api/v1/cofres",
            headers=autenticado,
            json={"name": nome, "display_name": nome.title()},
        )
        assert resposta.status_code == 201, resposta.text

    antes = client.get("/api/v1/panorama", headers=autenticado).json()["cofres"]
    assert antes["total"] == 2

    # Tira o alcance de um deles: deny vence allow, sempre.
    conceder(
        db_session,
        usuario,
        "cofres/alheio",
        ["read", "list"],
        efeito="deny",
        nome_politica="politica-nega-alheio",
    )

    depois = client.get("/api/v1/panorama", headers=autenticado).json()["cofres"]
    assert depois["total"] == 1, "o cofre negado sai da contagem"
    bruto = client.get("/api/v1/panorama", headers=autenticado).text
    assert "alheio" not in bruto, "nem o nome do que está fora pode aparecer"


def test_segredo_de_cofre_negado_nao_entra_na_contagem(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Contar segredos de um cofre inalcançável revelaria o tamanho dele."""
    _tudo(db_session, usuario)
    client.post(
        "/api/v1/cofres",
        headers=autenticado,
        json={"name": "restrito", "display_name": "Restrito"},
    )
    for nome in ("a", "b", "c"):
        client.post(
            "/api/v1/cofres/restrito/segredos",
            headers=autenticado,
            json={"name": f"senha-{nome}", "value": "v", "kind": "senha"},
        )

    assert (
        client.get("/api/v1/panorama", headers=autenticado).json()["cofres"]["segredos"]
        == 3
    )

    conceder(
        db_session,
        usuario,
        "cofres/restrito",
        ["read", "list"],
        efeito="deny",
        nome_politica="politica-nega-restrito",
    )

    cofres = client.get("/api/v1/panorama", headers=autenticado).json()["cofres"]
    assert cofres["total"] == 0
    assert cofres["segredos"] == 0, "sem o cofre, os segredos dele também somem"


def test_vencido_e_vencendo_nao_se_confundem(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Trocar um estado pelo outro tem de quebrar algo.

    O teste anterior media as três parcelas juntas e, com um de cada, a soma
    fechava mesmo se os rótulos trocassem de lugar. Aqui as quantidades são
    diferentes de propósito: dois vencidos e um vencendo só batem se cada
    estado for contado pelo que é.
    """
    conceder(db_session, usuario, "certificados/*", ["read", "list", "create"])
    _cria_certificado(client, autenticado, "morto-um", -40)
    _cria_certificado(client, autenticado, "morto-dois", -5)
    _cria_certificado(client, autenticado, "quase", 10)

    cert = client.get("/api/v1/panorama", headers=autenticado).json()["certificados"]

    assert cert["vencidos"] == 2
    assert cert["vencendo"] == 1
    assert cert["validos"] == 0
    # E o "próximo a vencer" é o que ainda vale, não o mais antigo dos mortos.
    assert cert["proximo_nome"] == "quase.exemplo.com.br"


def test_faixas_de_vencimento_nao_contam_o_mesmo_duas_vezes(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Faixas acumulativas inflariam o gráfico.

    "Vence em 30 dias" e "vence em 90" descrevem o mesmo certificado se as
    faixas forem lidas como tetos independentes. Cada item tem de cair numa
    faixa só, e a soma tem de fechar o total — senão o gráfico mostra mais
    itens do que existem.
    """
    conceder(db_session, usuario, "certificados/*", ["read", "list", "create"])
    # Um em cada faixa, mais um já vencido.
    _cria_certificado(client, autenticado, "morto", -3)
    _cria_certificado(client, autenticado, "urgente", 4)
    _cria_certificado(client, autenticado, "mes", 20)
    _cria_certificado(client, autenticado, "trimestre", 60)
    _cria_certificado(client, autenticado, "folgado", 300)

    cert = client.get("/api/v1/panorama", headers=autenticado).json()["certificados"]
    faixas = cert["por_vencimento"]

    assert sum(f["quantas"] for f in faixas) == cert["total"] == 5, (
        "as faixas somam o total: nenhum item fica de fora nem conta duas vezes"
    )
    por_rotulo = {f["rotulo"]: f["quantas"] for f in faixas}
    assert por_rotulo["Vencido"] == 1
    assert por_rotulo["7 dias"] == 1
    assert por_rotulo["30 dias"] == 1
    assert por_rotulo["90 dias"] == 1
    assert por_rotulo["Depois"] == 1
    # As duas primeiras faixas são as que exigem ação agora.
    criticas = [f["rotulo"] for f in faixas if f["critica"]]
    assert criticas == ["Vencido", "7 dias"]


def test_credencial_nunca_rotacionada_cai_na_pior_faixa(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Nunca rotacionada é o pior caso, não um caso sem dado.

    Deixá-la fora do gráfico esconderia justamente o que mais importa: uma
    senha que pode ainda ser a de fábrica.
    """
    _tudo(db_session, usuario)
    client.post(
        "/api/v1/dispositivos",
        headers=autenticado,
        json={"name": "sw", "display_name": "Switch", "kind": "switch"},
    )
    client.post(
        "/api/v1/dispositivos/sw/credenciais",
        headers=autenticado,
        json={"name": "senha-sw", "username": "admin", "rotation_days": 90},
    )

    cred = client.get("/api/v1/panorama", headers=autenticado).json()["credenciais"]
    faixas = {f["rotulo"]: f["quantas"] for f in cred["por_rotacao"]}

    assert faixas["Mais de 180d"] == 1, "nunca rotacionada vai para a pior faixa"
    assert sum(f["quantas"] for f in cred["por_rotacao"]) == cred["total"]


def test_chave_revogada_sai_do_grafico_de_vencimento(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Revogada não tem vencimento futuro a planejar.

    O gráfico responde "quando as chaves que estão em uso vão expirar". Uma
    revogada empilharia o passado sobre o que vem, e levaria alguém a
    programar a troca de uma chave que já saiu de circulação.
    """
    _tudo(db_session, usuario)

    def criar(nome: str, dias: int):
        return client.post(
            "/api/v1/chaves-api",
            headers=autenticado,
            json={
                "name": nome,
                "display_name": nome,
                "servico": "SEFAZ",
                "responsavel": "fiscal@exemplo.com.br",
                # O cadastro recebe o PRAZO, não a data: a data de
                # vencimento é derivada no servidor, para não depender do
                # relógio de quem chama.
                "dias_de_validade": dias,
            },
        )

    assert criar("viva", 20).status_code == 201
    assert criar("morta", 25).status_code == 201
    client.post("/api/v1/chaves-api/morta/revogar", headers=autenticado)

    chaves = client.get("/api/v1/panorama", headers=autenticado).json()["chaves"]

    assert chaves["total"] == 2
    assert chaves["ativas"] == 1
    assert chaves["revogadas"] == 1
    # Só a viva entra no gráfico: a soma das faixas conta as ATIVAS com
    # vencimento, não o acervo inteiro.
    assert sum(f["quantas"] for f in chaves["por_vencimento"]) == 1
    por_rotulo = {f["rotulo"]: f["quantas"] for f in chaves["por_vencimento"]}
    assert por_rotulo["30 dias"] == 1
