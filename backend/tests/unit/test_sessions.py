"""Testes do domínio de sessões gravadas.

As invariantes que importam:

- **A gravação é imutável depois de fechada.** Gravação que aceita evento
  tardio não prova nada, e é prova que ela existe para ser.
- **Eventos em ordem.** Deslocamento menor que o anterior tornaria a
  reprodução incoerente — e o player mostraria uma história que não aconteceu.
- **Derrubar exige justificativa.** É interromper o trabalho de alguém.
- **Dois tetos, por razões diferentes:** ociosidade pega a sessão esquecida
  aberta; duração absoluta pega quem mantém a sessão viva para não pedir
  acesso de novo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.sessions.entities import (
    DURACAO_MINUTOS_MAXIMO,
    OCIOSA_MINUTOS_MAXIMO,
    EstadoDaSessao,
    EventoDeSessao,
    MotivoDaSessao,
    Sessao,
    TipoDeEvento,
    TipoDeSessao,
    expirar_ociosas,
)
from app.domain.shared.errors import ConflictError, ValidationError

AGORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _sessao(**kwargs) -> Sessao:  # noqa: ANN003
    base = {
        "usuario_id": "u1",
        "usuario_label": "ana@exemplo.com.br",
        "tipo": TipoDeSessao.SSH,
        "alvo": "srv-producao",
        # O motivo é obrigatório e vem da lista fechada: sem ele a sessão
        # não é mensurável, e o domínio recusa.
        "motivo": str(MotivoDaSessao.MANUTENCAO),
        "iniciada_em": AGORA,
        "ultima_atividade_em": AGORA,
    }
    return Sessao(**{**base, **kwargs})


def _evento(ms: int, texto: str = "ls -la") -> EventoDeSessao:
    return EventoDeSessao(
        deslocamento_ms=ms, tipo=TipoDeEvento.ENTRADA, conteudo=texto
    )


class TestCriacao:
    def test_nasce_ativa(self) -> None:
        s = _sessao()
        assert s.esta_ativa is True
        assert s.estado is EstadoDaSessao.ATIVA
        assert s.eventos == []

    def test_alvo_e_obrigatorio(self) -> None:
        """Sessão sem alvo é registro que não responde pergunta nenhuma."""
        with pytest.raises(ValidationError, match="alvo"):
            _sessao(alvo="   ")

    def test_caminho_de_politica(self) -> None:
        s = _sessao()
        assert str(s.path) == f"sessoes/{s.id}"


class TestGravacao:
    def test_registra_eventos_em_ordem(self) -> None:
        s = _sessao()
        s.registrar(_evento(0, "whoami"), now=AGORA)
        s.registrar(_evento(1500, "ls"), now=AGORA + timedelta(seconds=2))
        assert [e.deslocamento_ms for e in s.eventos] == [0, 1500]

    def test_evento_fora_de_ordem_e_recusado(self) -> None:
        """Reprodução incoerente mostraria uma história que não aconteceu."""
        s = _sessao()
        s.registrar(_evento(2000), now=AGORA)
        with pytest.raises(ValidationError, match="fora de ordem"):
            s.registrar(_evento(1000), now=AGORA)

    def test_mesmo_deslocamento_e_aceito(self) -> None:
        """Entrada e saída simultâneas acontecem; recusar seria rigor inútil."""
        s = _sessao()
        s.registrar(_evento(500), now=AGORA)
        s.registrar(
            EventoDeSessao(
                deslocamento_ms=500, tipo=TipoDeEvento.SAIDA, conteudo="ok"
            ),
            now=AGORA,
        )
        assert len(s.eventos) == 2

    def test_deslocamento_negativo_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            EventoDeSessao(
                deslocamento_ms=-1, tipo=TipoDeEvento.ENTRADA, conteudo="x"
            )

    def test_registrar_atualiza_a_ultima_atividade(self) -> None:
        s = _sessao()
        depois = AGORA + timedelta(minutes=5)
        s.registrar(_evento(0), now=depois)
        assert s.ultima_atividade_em == depois


class TestImutabilidade:
    def test_encerrada_nao_aceita_evento(self) -> None:
        """A invariante central: gravação que muda não prova nada."""
        s = _sessao()
        s.registrar(_evento(0), now=AGORA)
        s.encerrar(por="ana", now=AGORA)

        with pytest.raises(ConflictError, match="não prova nada"):
            s.registrar(_evento(100), now=AGORA)

    def test_derrubada_nao_aceita_evento(self) -> None:
        s = _sessao()
        s.derrubar(por="admin", motivo="Suspeita", now=AGORA)
        with pytest.raises(ConflictError):
            s.registrar(_evento(0), now=AGORA)

    def test_expirada_nao_aceita_evento(self) -> None:
        s = _sessao()
        s.expirar(now=AGORA)
        with pytest.raises(ConflictError):
            s.registrar(_evento(0), now=AGORA)

    def test_encerrar_duas_vezes_e_conflito(self) -> None:
        s = _sessao()
        s.encerrar(por="ana", now=AGORA)
        with pytest.raises(ConflictError):
            s.encerrar(por="ana", now=AGORA)


class TestEncerramento:
    def test_encerrar_normal_marca_o_estado(self) -> None:
        s = _sessao()
        s.encerrar(por="ana@exemplo.com.br", motivo="Terminei", now=AGORA)
        assert s.estado is EstadoDaSessao.ENCERRADA
        assert s.encerrada_por == "ana@exemplo.com.br"
        assert s.encerrada_em == AGORA

    def test_derrubada_tem_estado_proprio(self) -> None:
        """"Terminou normalmente" e "foi interrompida" são perguntas
        diferentes numa revisão."""
        s = _sessao()
        s.derrubar(por="admin", motivo="Horário suspeito", now=AGORA)
        assert s.estado is EstadoDaSessao.DERRUBADA
        assert s.motivo_encerramento == "Horário suspeito"

    def test_derrubar_sem_motivo_e_recusado(self) -> None:
        """É interromper o trabalho de alguém: a trilha precisa do porquê."""
        s = _sessao()
        with pytest.raises(ValidationError, match="justificativa"):
            s.derrubar(por="admin", motivo="  ", now=AGORA)

    def test_encerrar_com_estado_ativo_e_recusado(self) -> None:
        s = _sessao()
        with pytest.raises(ValidationError, match="estado final"):
            s.encerrar(estado=EstadoDaSessao.ATIVA, now=AGORA)


class TestExpiracao:
    def test_ociosa_demais_deve_expirar(self) -> None:
        """Sessão esquecida aberta é acesso disponível para quem sentar."""
        s = _sessao()
        tarde = AGORA + timedelta(minutes=OCIOSA_MINUTOS_MAXIMO + 1)
        assert s.deveria_expirar(tarde) is True

    def test_ociosa_dentro_do_limite_nao_expira(self) -> None:
        s = _sessao()
        assert s.deveria_expirar(
            AGORA + timedelta(minutes=OCIOSA_MINUTOS_MAXIMO - 1)
        ) is False

    def test_atividade_renova_a_ociosidade(self) -> None:
        s = _sessao()
        meio = AGORA + timedelta(minutes=50)
        s.registrar(_evento(0), now=meio)
        # Sem a renovação, já teria expirado aos 61 min do início.
        assert s.deveria_expirar(meio + timedelta(minutes=30)) is False

    def test_duracao_absoluta_expira_mesmo_ativa(self) -> None:
        """Pega quem mantém a sessão viva para não pedir acesso de novo."""
        s = _sessao()
        # Atividade constante: a ociosidade nunca estoura.
        longe = AGORA + timedelta(minutes=DURACAO_MINUTOS_MAXIMO + 1)
        s.ultima_atividade_em = longe
        assert s.deveria_expirar(longe) is True

    def test_encerrada_nao_expira(self) -> None:
        s = _sessao()
        s.encerrar(por="ana", now=AGORA)
        assert s.deveria_expirar(AGORA + timedelta(days=30)) is False

    def test_expirar_ociosas_devolve_so_as_que_mudaram(self) -> None:
        ativa = _sessao()
        ativa.ultima_atividade_em = AGORA + timedelta(minutes=55)
        ociosa = _sessao()
        fechada = _sessao()
        fechada.encerrar(por="ana", now=AGORA)

        tarde = AGORA + timedelta(minutes=70)
        mudaram = expirar_ociosas([ativa, ociosa, fechada], tarde)

        assert mudaram == [ociosa]
        assert ociosa.estado is EstadoDaSessao.EXPIRADA
        assert ativa.esta_ativa is True


class TestLinhaDoTempoEBusca:
    def _com_eventos(self) -> Sessao:
        s = _sessao()
        s.registrar(_evento(0, "ssh srv-producao"), now=AGORA)
        s.registrar(
            EventoDeSessao(
                deslocamento_ms=800,
                tipo=TipoDeEvento.SAIDA,
                conteudo="Welcome to srv-producao",
            ),
            now=AGORA,
        )
        s.registrar(_evento(2500, "sudo systemctl restart postgres"), now=AGORA)
        return s

    def test_linha_do_tempo_preserva_ordem_e_tipo(self) -> None:
        linha = self._com_eventos().linha_do_tempo()
        assert [ms for ms, _, _ in linha] == [0, 800, 2500]
        assert linha[1][1] is TipoDeEvento.SAIDA

    def test_busca_encontra_por_conteudo(self) -> None:
        """Ninguém assiste três horas de sessão para achar um comando."""
        s = self._com_eventos()
        achados = s.buscar("postgres")
        assert len(achados) == 1
        assert "systemctl" in achados[0].conteudo

    def test_busca_e_insensivel_a_caixa(self) -> None:
        s = self._com_eventos()
        assert len(s.buscar("WELCOME")) == 1

    def test_busca_vazia_nao_devolve_tudo(self) -> None:
        """Termo vazio casando com tudo seria pior que não buscar."""
        s = self._com_eventos()
        assert s.buscar("   ") == []

    def test_duracao_usa_o_encerramento(self) -> None:
        s = _sessao()
        s.encerrar(por="ana", now=AGORA + timedelta(seconds=90))
        assert s.duracao_ms == 90_000


class TestMotivoLegado:
    """`legado=True` desliga a checagem da LISTA, e só ela.

    Sessões gravadas antes de a lista fechar têm motivo livre. Recusá-las na
    leitura derrubaria a listagem inteira por causa de um registro antigo —
    mas afrouxar demais transformaria "aceitar o passado" em "aceitar
    qualquer coisa", e a lista fechada perderia o sentido.

    Estes testes ficam no domínio de propósito: pela API o Pydantic recusa o
    valor antes, então um afrouxamento aqui passaria despercebido lá.
    """

    def test_motivo_fora_da_lista_e_recusado_na_criacao(self) -> None:
        with pytest.raises(ValidationError, match="não é uma opção"):
            _sessao(motivo="Conferencia do fechamento")

    def test_motivo_fora_da_lista_e_aceito_quando_legado(self) -> None:
        sessao = _sessao(motivo="Conferencia do fechamento", legado=True)
        # Chega como está: reescrever faria a trilha afirmar um motivo que
        # ninguém digitou.
        assert sessao.motivo == "Conferencia do fechamento"

    def test_legado_NAO_aceita_motivo_vazio(self) -> None:
        """A tolerância é só para a lista.

        Motivo em branco não é registro legado: é registro sem informação, e
        aceitá-lo deixaria entrar pelo repositório o que a criação recusa.
        """
        with pytest.raises(ValidationError, match="Informe o motivo"):
            _sessao(motivo="", legado=True)

    def test_legado_NAO_aceita_alvo_vazio(self) -> None:
        """Nenhuma outra regra do domínio é afetada por `legado`."""
        with pytest.raises(ValidationError, match="alvo"):
            _sessao(alvo="", legado=True)

    def test_motivo_valido_funciona_igual_com_legado(self) -> None:
        sessao = _sessao(motivo=str(MotivoDaSessao.INCIDENTE), legado=True)
        assert sessao.motivo == "incidente"

    def test_padrao_e_nao_legado(self) -> None:
        """Quem constrói sem dizer nada está criando, não lendo do banco."""
        assert _sessao().legado is False
