"""Série e rankings do painel.

O que se protege aqui, em ordem de gravidade:

1. **Vazamento lateral.** O ranking "quem mais acessa" mostra a atividade dos
   colegas. A tela de auditoria exige ADMIN para isso; se o painel não
   exigisse, seria a porta lateral para o que a trilha tranca pela porta da
   frente.
2. **Eixo que mente.** Dia sem evento precisa sair como zero, não sumir: um
   eixo X que pula de terça para sexta sugere continuidade que não houve.
3. **Divergência entre dialetos.** O dia tem de sair igual no SQLite e no
   Postgres, independentemente da timezone da conexão.

Nota sobre a contagem: a fixture `autenticado` faz login de verdade, e login
grava `login_sucesso` na trilha. Os testes medem o **acréscimo** sobre a
leitura inicial em vez de fixar números absolutos — ancorar no absoluto
quebraria no dia em que a fixture passasse a gravar mais um evento, sem que
nada de real tivesse mudado.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from app.infrastructure.db.models import UserModel
from app.infrastructure.db.repositories import AuditRepository

from .conftest import conceder


def _evento(
    acao: AuditAction,
    quando: datetime,
    *,
    ator: str = "ana.souza@exemplo.com.br",
    caminho: str = "cofre/producao/senha-root",
    desfecho: AuditOutcome = AuditOutcome.SUCCESS,
) -> AuditEvent:
    return AuditEvent(
        action=acao,
        actor_id="u1",
        actor_label=ator,
        target_path=caminho,
        outcome=desfecho,
        occurred_at=quando,
    )


def test_dia_sem_evento_vira_zero_e_nao_some(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """A série cobre a janela inteira, com buraco explícito."""
    antes = client.get("/api/v1/metricas/serie?dias=3", headers=autenticado).json()
    base_hoje = antes["serie"][-1]["sucesso"]

    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    # Hoje e anteontem têm evento; ontem não tem nenhum.
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora))
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora - timedelta(days=2)))
    db_session.commit()

    resposta = client.get("/api/v1/metricas/serie?dias=3", headers=autenticado)
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()

    serie = corpo["serie"]
    assert len(serie) == 3, "a janela pedida sai inteira, com os dias vazios"
    # O dia do meio é o que importa: ficou zero e continuou na série.
    assert serie[0]["sucesso"] == 1, "anteontem recebeu o evento plantado"
    assert serie[1]["sucesso"] == 0, "ontem não teve evento e saiu como zero"
    assert serie[2]["sucesso"] == base_hoje + 1
    # Os dias saem em ordem e sem salto: é o que sustenta o eixo X.
    dias = [p["dia"] for p in serie]
    assert dias == sorted(dias)
    # Dois dias com evento: hoje (login da fixture + o plantado) e anteontem.
    # Ontem ficou de fora da contagem, que é o ponto: ele aparece na série
    # como zero sem ser contado como "dia com dado".
    assert corpo["dias_com_dado"] == 2
    assert corpo["total"] == antes["total"] + 2, "os dois eventos plantados entraram"


def test_negado_nao_entra_em_sucesso(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """A crista vermelha é o sinal mais importante do gráfico."""
    antes = client.get("/api/v1/metricas/serie?dias=1", headers=autenticado).json()
    base = antes["serie"][-1]

    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora))
    audit.append(
        _evento(AuditAction.ACCESS_DENIED, agora, desfecho=AuditOutcome.FAILURE)
    )
    audit.append(
        _evento(AuditAction.LOGIN_FAILURE, agora, desfecho=AuditOutcome.FAILURE)
    )
    db_session.commit()

    corpo = client.get(
        "/api/v1/metricas/serie?dias=1", headers=autenticado
    ).json()
    hoje = corpo["serie"][-1]

    assert hoje["sucesso"] == base["sucesso"] + 1
    assert hoje["negado"] == base["negado"] + 1, "negado não foi somado ao sucesso"
    assert hoje["falha_login"] == base["falha_login"] + 1
    # As três faixas fecham o total: nenhuma categoria é silenciada.
    assert corpo["total"] == hoje["sucesso"] + hoje["negado"] + hoje["falha_login"]


def test_sem_admin_nao_ve_ranking_dos_colegas(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Sem ADMIN em `auditoria`, os rankings saem vazios e a tela sabe disso."""
    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora, ator="colega@exemplo.com.br"))
    db_session.commit()

    corpo = client.get("/api/v1/metricas/serie", headers=autenticado).json()

    assert corpo["restrito"] is True
    assert corpo["por_ator"] == []
    assert corpo["por_caminho"] == []
    # A prova que importa: o nome do colega não aparece em lugar nenhum do
    # corpo, nem num campo que eu tenha esquecido de inspecionar acima.
    bruto = client.get("/api/v1/metricas/serie", headers=autenticado).text
    assert "colega@exemplo.com.br" not in bruto


def test_com_admin_ve_ranking_ordenado(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Com ADMIN os rankings saem, do mais ativo ao menos."""
    conceder(db_session, usuario, "auditoria", ["admin"])
    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    for _ in range(3):
        audit.append(_evento(AuditAction.SECRET_REVEALED, agora, ator="ana@exemplo.com.br"))
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora, ator="bruno@exemplo.com.br"))
    db_session.commit()

    corpo = client.get("/api/v1/metricas/serie", headers=autenticado).json()

    assert corpo["restrito"] is False
    assert [i["rotulo"] for i in corpo["por_ator"]] == [
        "ana@exemplo.com.br",
        "bruno@exemplo.com.br",
    ]
    assert [i["quantas"] for i in corpo["por_ator"]] == [3, 1]


def test_evento_de_madrugada_cai_no_dia_utc(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """O dia não pode depender da timezone de quem abriu a conexão.

    Um evento às 02:30 UTC cai no dia anterior se a data for extraída com a
    timezone de São Paulo. Agregar em Python sobre valores normalizados em
    UTC mantém a barra no mesmo lugar nos dois dialetos.
    """
    antes = client.get("/api/v1/metricas/serie?dias=2", headers=autenticado).json()
    base_hoje = antes["serie"][-1]["sucesso"]
    base_ontem = antes["serie"][0]["sucesso"]

    audit = AuditRepository(db_session)
    hoje = datetime.now(UTC).date()
    madrugada = datetime.combine(hoje, datetime.min.time(), tzinfo=UTC) + timedelta(
        hours=2, minutes=30
    )
    audit.append(_evento(AuditAction.SECRET_REVEALED, madrugada))
    db_session.commit()

    corpo = client.get("/api/v1/metricas/serie?dias=2", headers=autenticado).json()

    assert corpo["serie"][-1]["dia"] == hoje.isoformat(), "02:30 UTC é hoje, não ontem"
    assert corpo["serie"][-1]["sucesso"] == base_hoje + 1, "o evento caiu em HOJE"
    assert corpo["serie"][0]["sucesso"] == base_ontem, "ontem não foi contaminado"


def test_ranking_recusa_coluna_fora_do_mapa(db_session: Session) -> None:
    """Nome de coluna nunca é interpolado: seria injeção pela porta da frente."""
    audit = AuditRepository(db_session)
    with pytest.raises(ValueError, match="coluna nao permitida"):
        audit.ranking(
            "actor_label; DROP TABLE auditoria_eventos",
            acoes=(str(AuditAction.SECRET_REVEALED),),
            desde=datetime.now(UTC) - timedelta(days=1),
        )


def test_agregacao_usa_utc_mesmo_com_offset_local(db_session: Session) -> None:
    """O dia não pode mudar quando o banco devolve o valor em outro offset.

    O SQLite devolve datetime ingênuo; o Postgres devolve **convertido para a
    timezone da sessão**. Com a sessão em America/Sao_Paulo, um evento de
    02:30 UTC chega como 23:30 do dia anterior, e um `.date()` cru o jogaria
    na barra errada do gráfico.

    Este teste força esse formato na saída do banco — que é o que um teste
    contra SQLite jamais produziria sozinho — e exige o dia UTC.
    """
    from datetime import timezone

    audit = AuditRepository(db_session)
    madrugada_utc = datetime(2026, 10, 20, 2, 30, tzinfo=UTC)
    audit.append(_evento(AuditAction.SECRET_REVEALED, madrugada_utc))
    db_session.commit()

    sao_paulo = timezone(timedelta(hours=-3))
    original = audit._session.execute

    def _como_postgres_em_sao_paulo(*args, **kwargs):
        """Reentrega as linhas com o offset que o Postgres aplicaria."""
        linhas = original(*args, **kwargs).all()
        convertidas = []
        for linha in linhas:
            momento = linha.occurred_at
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=UTC)
            convertidas.append(
                _Linha(momento.astimezone(sao_paulo), linha.action, linha.outcome)
            )
        return _Resultado(convertidas)

    audit._session.execute = _como_postgres_em_sao_paulo  # type: ignore[method-assign]
    try:
        linhas = audit.serie_por_dia(desde=datetime(2026, 10, 1, tzinfo=UTC))
    finally:
        audit._session.execute = original  # type: ignore[method-assign]

    dias = {dia for dia, _, _, _ in linhas}
    assert date(2026, 10, 20) in dias, "02:30 UTC pertence ao dia 20"
    assert date(2026, 10, 19) not in dias, "o offset -03 não pode puxar para o dia 19"


class _Linha(NamedTuple):
    """As três colunas que `serie_por_dia` seleciona."""

    occurred_at: datetime
    action: str
    outcome: str


class _Resultado:
    """Mínimo do Result do SQLAlchemy que `serie_por_dia` consome."""

    def __init__(self, linhas):
        self._linhas = linhas

    def all(self):
        return self._linhas


def test_janela_comeca_no_dia_pedido_e_nao_um_antes(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """`dias=N` cobre N dias contando hoje, inclusive as duas pontas.

    Errar por um aqui é barato de escrever e caro de perceber: a série
    continua com N posições e o gráfico parece certo, mas a janela inteira
    anda um dia para trás e o evento de hoje some da ponta direita.
    """
    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    hoje = agora.date()
    # Um evento em cada extremo da janela de 3 dias.
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora))
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora - timedelta(days=2)))
    # E um FORA dela, que não pode entrar.
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora - timedelta(days=3)))
    db_session.commit()

    corpo = client.get("/api/v1/metricas/serie?dias=3", headers=autenticado).json()
    serie = corpo["serie"]

    assert serie[0]["dia"] == (hoje - timedelta(days=2)).isoformat()
    assert serie[-1]["dia"] == hoje.isoformat()
    assert serie[0]["sucesso"] == 1, "o dia mais antigo da janela entra inteiro"
    # O evento de 3 dias atrás ficou de fora: a janela não vazou para trás.
    assert all(p["dia"] != (hoje - timedelta(days=3)).isoformat() for p in serie)


def test_dias_com_dado_conta_so_dentro_da_janela(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """O contador acompanha o que a tela desenha, não o que a consulta trouxe.

    A tela usa esse número para dizer "3 dias de histórico" em vez de
    desenhar 30 posições vazias. Se ele contasse o balde cru, um evento fora
    da janela inflaria a legenda e ela desmentiria o próprio gráfico.
    """
    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora))
    # Bem fora da janela de 2 dias que será pedida.
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora - timedelta(days=20)))
    db_session.commit()

    corpo = client.get("/api/v1/metricas/serie?dias=2", headers=autenticado).json()

    com_evento = sum(
        1 for p in corpo["serie"] if p["sucesso"] or p["negado"] or p["falha_login"]
    )
    assert corpo["dias_com_dado"] == com_evento, (
        "o contador e a série têm de concordar"
    )
    assert corpo["dias_com_dado"] == 1, "o evento de 20 dias atrás não entra"


def test_ranking_empatado_nao_troca_de_ordem(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Empate resolve pelo nome, senão a ordem oscila entre recarregadas.

    `ORDER BY contagem DESC` sozinho não é estável: duas linhas empatadas
    podem sair em ordem diferente a cada execução, e o usuário veria o
    ranking "se mexendo" sem que nada tivesse acontecido.
    """
    conceder(db_session, usuario, "auditoria", ["admin"])
    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    # Três atores com exatamente a mesma contagem, inseridos fora de ordem.
    for ator in ("carla@exemplo.com.br", "ana@exemplo.com.br", "bruno@exemplo.com.br"):
        audit.append(_evento(AuditAction.SECRET_REVEALED, agora, ator=ator))
    db_session.commit()

    leituras = [
        [
            i["rotulo"]
            for i in client.get("/api/v1/metricas/serie", headers=autenticado).json()[
                "por_ator"
            ]
        ]
        for _ in range(3)
    ]

    assert leituras[0] == leituras[1] == leituras[2], "a ordem não pode oscilar"
    empatados = [r for r in leituras[0] if "@exemplo.com.br" in r and r != "ana.souza@exemplo.com.br"]
    assert empatados == sorted(empatados), "empate desempata por nome"


def test_evento_no_futuro_nao_infla_o_contador(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Relógio adiantado não pode fazer a legenda desmentir o gráfico.

    O filtro de data tem piso (`desde`) e não tem teto, então um evento
    gravado com data futura — máquina de robô com relógio adiantado, que é
    coisa que acontece — entra no balde da agregação. A série, porém, vai só
    até hoje e não o desenha. Contar o balde cru diria "4 dias de histórico"
    num gráfico que mostra 3.
    """
    audit = AuditRepository(db_session)
    agora = datetime.now(UTC)
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora))
    audit.append(_evento(AuditAction.SECRET_REVEALED, agora + timedelta(days=2)))
    db_session.commit()

    corpo = client.get("/api/v1/metricas/serie?dias=3", headers=autenticado).json()

    desenhados = sum(
        1 for p in corpo["serie"] if p["sucesso"] or p["negado"] or p["falha_login"]
    )
    assert corpo["dias_com_dado"] == desenhados
    assert corpo["dias_com_dado"] == 1, "o dia futuro não é desenhado nem contado"
    # E o total também ignora o futuro, pela mesma razão.
    assert corpo["total"] == sum(
        p["sucesso"] + p["negado"] + p["falha_login"] for p in corpo["serie"]
    )


def test_padrao_e_restritivo_so_admin_ve(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Instalação nova não mostra a atividade dos colegas a quem aprova.

    Quem só tem APPROVE é gestor, não administrador. Numa instalação recém
    criada ele não vê os rankings — ampliar é decisão consciente de quem
    opera, registrada na trilha.
    """
    conceder(db_session, usuario, "auditoria", ["approve"])

    corpo = client.get("/api/v1/metricas/serie", headers=autenticado).json()

    assert corpo["capacidade_exigida"] == "admin"
    assert corpo["restrito"] is True
    assert corpo["por_ator"] == []


def test_configurar_approve_libera_o_gestor(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Com a instalação configurada para `approve`, o gestor passa a ver."""
    conceder(db_session, usuario, "auditoria", ["approve"])
    # Precisa de ADMIN em `admin` para mexer na configuração — são permissões
    # distintas de propósito.
    conceder(db_session, usuario, "admin", ["admin"], nome_politica="politica-admin")

    audit = AuditRepository(db_session)
    audit.append(
        _evento(AuditAction.SECRET_REVEALED, datetime.now(UTC), ator="ana@exemplo.com.br")
    )
    db_session.commit()

    antes = client.get("/api/v1/metricas/serie", headers=autenticado).json()
    assert antes["restrito"] is True, "antes de configurar, o gestor não vê"

    resposta = client.put(
        "/api/v1/configuracao",
        json={"capacidade_do_ranking": "approve"},
        headers=autenticado,
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["capacidade_do_ranking"] == "approve"

    depois = client.get("/api/v1/metricas/serie", headers=autenticado).json()
    assert depois["capacidade_exigida"] == "approve"
    assert depois["restrito"] is False
    assert [i["rotulo"] for i in depois["por_ator"]] == ["ana@exemplo.com.br"]


def test_admin_ve_mesmo_quando_a_exigida_e_approve(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Quem administra a auditoria não é barrado por exigir-se APPROVE.

    O administrador já lê a trilha inteira pela tela de auditoria; recusar
    aqui só produziria a pergunta "por que o painel esconde o que a trilha
    mostra?".
    """
    conceder(db_session, usuario, "auditoria", ["admin"])
    conceder(db_session, usuario, "admin", ["admin"], nome_politica="politica-admin")

    client.put(
        "/api/v1/configuracao",
        json={"capacidade_do_ranking": "approve"},
        headers=autenticado,
    )

    corpo = client.get("/api/v1/metricas/serie", headers=autenticado).json()
    assert corpo["capacidade_exigida"] == "approve"
    assert corpo["restrito"] is False, "ADMIN passa mesmo exigindo-se APPROVE"


def test_capacidade_fora_da_lista_e_recusada(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """`read` ou `list` abririam a atividade dos colegas a quase todos.

    A lista é fechada justamente para que a configuração não possa desligar a
    própria proteção.
    """
    conceder(db_session, usuario, "admin", ["admin"], nome_politica="politica-admin")

    for invalida in ["read", "list", "reveal", "", "ADMIN "]:
        resposta = client.put(
            "/api/v1/configuracao",
            json={"capacidade_do_ranking": invalida},
            headers=autenticado,
        )
        assert resposta.status_code == 422, f"{invalida!r} deveria ser recusada"

    # E a configuração continua intacta depois das tentativas.
    atual = client.get("/api/v1/configuracao", headers=autenticado).json()
    assert atual["capacidade_do_ranking"] == "admin"


def test_mudanca_do_ranking_fica_na_trilha(
    client: TestClient, db_session: Session, usuario: UserModel, autenticado
) -> None:
    """Quem passou a ver a atividade dos colegas é o que uma auditoria revisa."""
    conceder(db_session, usuario, "admin", ["admin"], nome_politica="politica-admin")
    conceder(db_session, usuario, "auditoria", ["admin"])

    client.put(
        "/api/v1/configuracao",
        json={"capacidade_do_ranking": "approve"},
        headers=autenticado,
    )

    trilha = client.get("/api/v1/auditoria", headers=autenticado).json()["eventos"]
    alteracoes = [e for e in trilha if e["action"] == "configuracao_alterada"]
    assert alteracoes, "a mudança gerou evento"
    # O antes e o depois precisam estar no texto: "configuração alterada"
    # sozinho não permite revisar nada.
    assert any(
        "admin -> approve" in e["reason"] for e in alteracoes
    ), [e["reason"] for e in alteracoes]
