"""Testes da trilha de auditoria.

Os testes que importam são os de adulteração: eles simulam um atacante com
escrita no banco alterando, removendo ou reordenando eventos, e exigem que a
verificação acuse. Um teste que só confirma "a cadeia válida passa" não
provaria nada sobre a detecção.
"""

import dataclasses

from app.domain.audit.events import (
    GENESIS_HASH,
    AuditAction,
    AuditEvent,
    AuditOutcome,
    ChainAnchor,
    append,
    verify_chain,
)


def _evento(acao: AuditAction = AuditAction.SECRET_REVEALED, alvo: str = "cofres/x") -> AuditEvent:
    return AuditEvent(
        action=acao,
        actor_id="u1",
        actor_label="ana.souza@exemplo.com.br",
        target_path=alvo,
    )


def _cadeia(tamanho: int = 5) -> list[AuditEvent]:
    eventos: list[AuditEvent] = []
    for i in range(tamanho):
        append(eventos, _evento(alvo=f"cofres/x/segredos/s{i}"))
    return eventos


class TestChaining:
    def test_primeiro_evento_aponta_para_genesis(self) -> None:
        eventos: list[AuditEvent] = []
        primeiro = append(eventos, _evento())
        assert primeiro.sequence == 0
        assert primeiro.previous_hash == GENESIS_HASH

    def test_evento_seguinte_aponta_para_o_anterior(self) -> None:
        eventos: list[AuditEvent] = []
        primeiro = append(eventos, _evento())
        segundo = append(eventos, _evento())
        assert segundo.sequence == 1
        assert segundo.previous_hash == primeiro.fingerprint()

    def test_cadeia_integra_nao_acusa_quebra(self) -> None:
        assert verify_chain(_cadeia()) == []

    def test_cadeia_vazia_e_integra(self) -> None:
        assert verify_chain([]) == []

    def test_fingerprint_e_deterministico(self) -> None:
        evento = _evento()
        assert evento.fingerprint() == evento.fingerprint()

    def test_eventos_diferentes_tem_hash_diferente(self) -> None:
        a = _evento(alvo="cofres/a")
        b = _evento(alvo="cofres/b")
        assert a.fingerprint() != b.fingerprint()


class TestTamperDetection:
    """Cada teste aqui é um ataque concreto à trilha."""

    def test_alterar_o_alvo_de_um_evento_quebra_a_cadeia(self) -> None:
        eventos = _cadeia()
        # Atacante reescreve o alvo do evento 2 para esconder o que acessou.
        eventos[2] = dataclasses.replace(eventos[2], target_path="cofres/inocente")
        quebras = verify_chain(eventos)
        assert quebras, "a adulteração do alvo passou despercebida"
        assert any(q.sequence == 3 for q in quebras), "a quebra deveria aparecer no elo seguinte"

    def test_alterar_o_ator_quebra_a_cadeia(self) -> None:
        eventos = _cadeia()
        eventos[1] = dataclasses.replace(eventos[1], actor_label="outro@exemplo.com.br")
        assert verify_chain(eventos), "a troca de ator passou despercebida"

    def test_alterar_o_desfecho_quebra_a_cadeia(self) -> None:
        eventos = _cadeia()
        eventos[0] = dataclasses.replace(eventos[0], outcome=AuditOutcome.FAILURE)
        assert verify_chain(eventos), "a troca de desfecho passou despercebida"

    def test_remover_um_evento_do_meio_quebra_a_cadeia(self) -> None:
        eventos = _cadeia()
        del eventos[2]
        quebras = verify_chain(eventos)
        assert quebras, "a remoção de um evento passou despercebida"

    def test_reordenar_eventos_quebra_a_cadeia(self) -> None:
        eventos = _cadeia()
        eventos[1], eventos[3] = eventos[3], eventos[1]
        assert verify_chain(eventos), "a reordenação passou despercebida"

    def test_truncar_o_fim_nao_e_detectavel_pela_cadeia(self) -> None:
        """Limite conhecido e documentado: cortar o FIM mantém a cadeia coerente.

        Quem apaga os últimos eventos não deixa rastro na própria trilha. É o
        motivo de a exportação externa (SIEM) estar no desenho: só um registro
        fora da máquina detecta truncamento.
        """
        eventos = _cadeia()
        del eventos[-1]
        assert verify_chain(eventos) == []

    def test_a_varredura_reporta_todas_as_quebras(self) -> None:
        """Um relatório que para na primeira quebra esconde o resto do estrago."""
        eventos = _cadeia(6)
        eventos[1] = dataclasses.replace(eventos[1], target_path="x")
        eventos[4] = dataclasses.replace(eventos[4], target_path="y")
        quebras = verify_chain(eventos)
        sequencias = {q.sequence for q in quebras}
        assert len(sequencias) >= 2, f"esperava quebras em dois pontos, veio {sequencias}"

    def test_a_quebra_descreve_o_problema_em_portugues(self) -> None:
        eventos = _cadeia()
        eventos[1] = dataclasses.replace(eventos[1], target_path="x")
        quebras = verify_chain(eventos)
        assert any("alterada" in q.detail or "Sequência" in q.detail for q in quebras)


class TestNoSecretLeak:
    def test_metadata_vazia_por_padrao(self) -> None:
        """A trilha é lida por mais gente do que o segredo: nada de valor aqui."""
        assert _evento().metadata == {}


def _recosturar(eventos: list[AuditEvent], posicao: int, novo_alvo: str) -> list[AuditEvent]:
    """Simula o atacante caprichado: altera um evento e refaz todos os elos seguintes."""
    atacada = list(eventos)
    atacada[posicao] = dataclasses.replace(atacada[posicao], target_path=novo_alvo)
    for i in range(posicao + 1, len(atacada)):
        atacada[i] = dataclasses.replace(atacada[i], previous_hash=atacada[i - 1].fingerprint())
    return atacada


class TestAnchoredVerification:
    """A cadeia sozinha não basta: quem recostura os elos produz trilha coerente.

    Estes testes fixam o limite real da auditoria e a defesa contra ele.
    """

    def test_recostura_completa_engana_a_cadeia_sozinha(self) -> None:
        """Limite conhecido: sem âncora externa, a reescrita coerente passa."""
        eventos = _cadeia()
        atacada = _recosturar(eventos, 2, "APAGUEI-MEU-RASTRO")
        assert verify_chain(atacada) == []

    def test_ancora_externa_detecta_a_recostura(self) -> None:
        """A defesa: um hash registrado fora do banco denuncia a reescrita."""
        eventos = _cadeia()
        ancora = ChainAnchor(sequence=2, fingerprint=eventos[2].fingerprint())
        atacada = _recosturar(eventos, 2, "APAGUEI-MEU-RASTRO")
        quebras = verify_chain(atacada, anchors=[ancora])
        assert quebras, "a recostura passou mesmo com âncora externa"
        assert any(q.sequence == 2 for q in quebras)
        assert any("registro externo" in q.detail for q in quebras)

    def test_ancora_detecta_evento_sumido(self) -> None:
        eventos = _cadeia()
        ancora = ChainAnchor(sequence=4, fingerprint=eventos[4].fingerprint())
        del eventos[4]
        quebras = verify_chain(eventos, anchors=[ancora])
        assert any("sumiu da trilha" in q.detail for q in quebras)

    def test_ancora_valida_nao_acusa_cadeia_integra(self) -> None:
        eventos = _cadeia()
        ancoras = [ChainAnchor(sequence=i, fingerprint=e.fingerprint()) for i, e in enumerate(eventos)]
        assert verify_chain(eventos, anchors=ancoras) == []

    def test_verificacao_sem_ancora_continua_funcionando(self) -> None:
        assert verify_chain(_cadeia()) == []


class TestTimestampCanonicalization:
    """Regressão: o fingerprint não pode depender do dialeto do banco.

    O SQLite devolve datetime SEM timezone; o Postgres, COM. Se o hash usar
    `isoformat()` direto, o mesmo evento produz hashes diferentes nos dois
    bancos e a trilha falha na verificação após um round-trip. A suíte roda
    em SQLite e produção roda em Postgres — exatamente o par que esconde isso.
    """

    def test_ingenuo_e_consciente_no_mesmo_instante_tem_o_mesmo_hash(self) -> None:
        from datetime import UTC, datetime

        consciente = datetime(2026, 10, 17, 14, 32, 10, 123456, tzinfo=UTC)
        ingenuo = datetime(2026, 10, 17, 14, 32, 10, 123456)  # como o SQLite devolve

        com_tz = AuditEvent(
            action=AuditAction.SECRET_REVEALED, actor_id="u1", actor_label="g",
            target_path="cofres/x", occurred_at=consciente, id="fixo",
        )
        sem_tz = AuditEvent(
            action=AuditAction.SECRET_REVEALED, actor_id="u1", actor_label="g",
            target_path="cofres/x", occurred_at=ingenuo, id="fixo",
        )
        assert com_tz.fingerprint() == sem_tz.fingerprint()

    def test_fuso_diferente_no_mesmo_instante_tem_o_mesmo_hash(self) -> None:
        """Um driver que devolva -03:00 não pode mudar o hash."""
        from datetime import UTC, datetime, timedelta, timezone

        utc = datetime(2026, 10, 17, 17, 0, 0, tzinfo=UTC)
        brasilia = utc.astimezone(timezone(timedelta(hours=-3)))

        a = AuditEvent(action=AuditAction.LOGIN_SUCCESS, actor_id="u1", actor_label="g",
                       target_path="auth", occurred_at=utc, id="fixo")
        b = AuditEvent(action=AuditAction.LOGIN_SUCCESS, actor_id="u1", actor_label="g",
                       target_path="auth", occurred_at=brasilia, id="fixo")
        assert a.fingerprint() == b.fingerprint()

    def test_instantes_diferentes_continuam_com_hashes_diferentes(self) -> None:
        """A normalização não pode achatar tempos distintos no mesmo hash."""
        from datetime import UTC, datetime

        base = datetime(2026, 10, 17, 14, 32, 10, 123456, tzinfo=UTC)
        depois = datetime(2026, 10, 17, 14, 32, 10, 123457, tzinfo=UTC)

        a = AuditEvent(action=AuditAction.LOGIN_SUCCESS, actor_id="u1", actor_label="g",
                       target_path="auth", occurred_at=base, id="fixo")
        b = AuditEvent(action=AuditAction.LOGIN_SUCCESS, actor_id="u1", actor_label="g",
                       target_path="auth", occurred_at=depois, id="fixo")
        assert a.fingerprint() != b.fingerprint()
