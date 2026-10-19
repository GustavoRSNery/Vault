"""Testes da exportação da trilha e da ancoragem.

O que estes testes protegem:

- **A ordem envio → âncora.** Ancorar antes de enviar criaria âncora para
  evento que nunca saiu: a verificação cobraria um registro externo
  inexistente e acusaria fraude onde houve falha de rede.
- **A retomada.** Exportar duas vezes seguidas não pode reenviar o que já
  saiu, e o evento de sequência 0 não pode ficar de fora para sempre.
- **O efeito real.** Depois de ancorar, uma recostura completa da cadeia
  passa a ser detectada — que é a única razão de tudo isto existir.
- **Nenhum valor de segredo na linha exportada.**
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.application.audit.export_chain import ExportChain
from app.domain.audit.events import (
    AuditAction,
    AuditEvent,
    AuditOutcome,
    verify_chain,
)
from app.infrastructure.audit.exporters import JsonlExporter
from app.infrastructure.db.repositories import AuditRepository


class ExportadorQueFalha:
    """Destino que recusa tudo, para provar que a âncora não é gravada."""

    nome = "destino-indisponivel"
    inviolavel = True

    def append(self, linhas: list[str]) -> int:
        raise ConnectionError("SIEM fora do ar")


class ExportadorEmMemoria:
    """Destino somente-anexação em memória, para inspecionar o enviado."""

    def __init__(self, *, inviolavel: bool = True) -> None:
        self.linhas: list[str] = []
        self.chamadas = 0
        self._inviolavel = inviolavel

    @property
    def nome(self) -> str:
        return "memoria"

    @property
    def inviolavel(self) -> bool:
        return self._inviolavel

    def append(self, linhas: list[str]) -> int:
        self.chamadas += 1
        self.linhas.extend(linhas)
        return len(linhas)


def _evento(acao: AuditAction, alvo: str, motivo: str = "") -> AuditEvent:
    return AuditEvent(
        action=acao,
        actor_id="u1",
        actor_label="ana@exemplo.com.br",
        target_path=alvo,
        outcome=AuditOutcome.SUCCESS,
        reason=motivo,
    )


@pytest.fixture
def trilha(session: Session) -> AuditRepository:
    repo = AuditRepository(session)
    repo.append(_evento(AuditAction.LOGIN_SUCCESS, "sessoes/ana"))
    repo.append(_evento(AuditAction.VAULT_CREATED, "cofres/contabil"))
    repo.append(_evento(AuditAction.SECRET_REVEALED, "cofres/contabil/segredos/x"))
    session.flush()
    return repo


class TestExportacao:
    def test_primeira_exportacao_leva_tudo_inclusive_a_sequencia_zero(
        self, trilha: AuditRepository
    ) -> None:
        """Com retomada em 0 em vez de -1, o primeiro evento ficaria de fora."""
        destino = ExportadorEmMemoria()
        resultado = ExportChain(trilha, destino).execute()

        assert resultado.exportados == 3
        assert len(destino.linhas) == 3
        sequencias = [json.loads(l)["sequence"] for l in destino.linhas]
        assert sequencias == [0, 1, 2]

    def test_ancora_fica_na_ultima_sequencia_do_lote(
        self, trilha: AuditRepository
    ) -> None:
        """Uma âncora basta: o encadeamento cobre todo o trecho anterior."""
        destino = ExportadorEmMemoria()
        resultado = ExportChain(trilha, destino).execute()

        ancoras = trilha.anchors()
        assert len(ancoras) == 1
        assert ancoras[0].sequence == 2
        assert resultado.ancora_sequencia == 2
        assert ancoras[0].fingerprint == trilha.list_chain()[2].fingerprint()

    def test_segunda_exportacao_sem_novidade_nao_faz_nada(
        self, trilha: AuditRepository
    ) -> None:
        destino = ExportadorEmMemoria()
        ExportChain(trilha, destino).execute()

        resultado = ExportChain(trilha, destino).execute()
        assert resultado.exportados == 0
        assert resultado.houve_trabalho is False
        assert destino.chamadas == 1  # não bateu no destino de novo
        assert len(trilha.anchors()) == 1  # nem criou âncora redundante

    def test_exportacao_incremental_leva_so_o_novo(
        self, trilha: AuditRepository, session: Session
    ) -> None:
        destino = ExportadorEmMemoria()
        ExportChain(trilha, destino).execute()

        trilha.append(_evento(AuditAction.SECRET_DELETED, "cofres/contabil/segredos/x"))
        session.flush()

        resultado = ExportChain(trilha, destino).execute()
        assert resultado.exportados == 1
        assert len(destino.linhas) == 4
        assert json.loads(destino.linhas[-1])["sequence"] == 3
        assert [a.sequence for a in trilha.anchors()] == [2, 3]

    def test_falha_no_destino_nao_grava_ancora(
        self, trilha: AuditRepository
    ) -> None:
        """A invariante da ordem: âncora sem envio acusaria fraude inexistente."""
        with pytest.raises(ConnectionError):
            ExportChain(trilha, ExportadorQueFalha()).execute()

        assert trilha.anchors() == []

    def test_falha_nao_impede_exportar_depois(
        self, trilha: AuditRepository
    ) -> None:
        """Nada fica marcado como exportado quando o envio falhou."""
        with pytest.raises(ConnectionError):
            ExportChain(trilha, ExportadorQueFalha()).execute()

        destino = ExportadorEmMemoria()
        resultado = ExportChain(trilha, destino).execute()
        assert resultado.exportados == 3

    def test_resultado_declara_se_o_destino_e_inviolavel(
        self, trilha: AuditRepository
    ) -> None:
        """A tela não pode anunciar garantia que o ambiente não tem."""
        fraco = ExportChain(trilha, ExportadorEmMemoria(inviolavel=False)).execute()
        assert fraco.destino_inviolavel is False

    def test_linha_exportada_carrega_o_hash(
        self, trilha: AuditRepository
    ) -> None:
        """Sem o fingerprint, o registro externo é cópia, não prova."""
        destino = ExportadorEmMemoria()
        ExportChain(trilha, destino).execute()

        linha = json.loads(destino.linhas[0])
        assert len(linha["fingerprint"]) == 64
        assert linha["fingerprint"] == trilha.list_chain()[0].fingerprint()
        assert "previous_hash" in linha

    def test_linha_exportada_nao_leva_valor_de_segredo(
        self, trilha: AuditRepository, session: Session
    ) -> None:
        trilha.append(
            _evento(
                AuditAction.SECRET_REVEALED,
                "cofres/contabil/segredos/token",
                motivo="Permitido por concessão temporária.",
            )
        )
        session.flush()

        destino = ExportadorEmMemoria()
        ExportChain(trilha, destino).execute()
        tudo = "\n".join(destino.linhas)
        # Os campos exportados são fechados: nada de "value", "plaintext" etc.
        for linha in destino.linhas:
            assert set(json.loads(linha)) == {
                "sequence", "id", "action", "actor_id", "actor_label",
                "target_path", "outcome", "reason", "ip_address",
                "occurred_at", "previous_hash", "fingerprint",
            }
        assert "value" not in tudo


class TestEfeitoNaVerificacao:
    def test_ancora_detecta_recostura_completa(
        self, trilha: AuditRepository, session: Session
    ) -> None:
        """A razão de tudo isto existir.

        Sem âncora, uma cadeia recosturada por inteiro é internamente coerente
        e passa na verificação. Com âncora, não passa.
        """
        ExportChain(trilha, ExportadorEmMemoria()).execute()
        eventos = trilha.list_chain()
        ancoras = trilha.anchors()
        assert verify_chain(eventos, anchors=ancoras) == []

        # O atacante altera um evento e recostura todos os hashes seguintes.
        adulterados = list(eventos)
        from dataclasses import replace

        adulterados[1] = replace(adulterados[1], target_path="cofres/outro")
        for i in range(2, len(adulterados)):
            adulterados[i] = replace(
                adulterados[i], previous_hash=adulterados[i - 1].fingerprint()
            )

        # Internamente coerente: sem âncora, passa.
        assert verify_chain(adulterados) == []
        # Com a âncora externa, não passa.
        quebras = verify_chain(adulterados, anchors=ancoras)
        assert quebras != []
        assert quebras[0].sequence == 2

    def test_ancora_detecta_truncamento_do_fim(
        self, trilha: AuditRepository
    ) -> None:
        """Apagar os últimos eventos deixa a cadeia válida — a âncora pega."""
        ExportChain(trilha, ExportadorEmMemoria()).execute()
        ancoras = trilha.anchors()

        truncada = trilha.list_chain()[:-1]
        assert verify_chain(truncada) == []
        assert verify_chain(truncada, anchors=ancoras) != []


class TestJsonlExporter:
    def test_grava_uma_linha_por_evento(
        self, trilha: AuditRepository, tmp_path: Path
    ) -> None:
        destino = JsonlExporter(tmp_path / "trilha.jsonl")
        ExportChain(trilha, destino).execute()

        linhas = destino.caminho.read_text(encoding="utf-8").strip().splitlines()
        assert len(linhas) == 3
        assert json.loads(linhas[0])["sequence"] == 0

    def test_append_nao_trunca_o_que_ja_existia(
        self, trilha: AuditRepository, session: Session, tmp_path: Path
    ) -> None:
        """Modo "w" apagaria justamente o histórico que se quer preservar."""
        destino = JsonlExporter(tmp_path / "trilha.jsonl")
        ExportChain(trilha, destino).execute()

        trilha.append(_evento(AuditAction.LOGOUT, "sessoes/ana"))
        session.flush()
        ExportChain(trilha, destino).execute()

        linhas = destino.caminho.read_text(encoding="utf-8").strip().splitlines()
        assert len(linhas) == 4

    def test_declara_que_nao_e_inviolavel(self, tmp_path: Path) -> None:
        """Arquivo no mesmo host é editável pela aplicação, e isso é dito."""
        assert JsonlExporter(tmp_path / "x.jsonl").inviolavel is False

    def test_cria_a_pasta_se_nao_existir(
        self, trilha: AuditRepository, tmp_path: Path
    ) -> None:
        destino = JsonlExporter(tmp_path / "nova" / "pasta" / "trilha.jsonl")
        ExportChain(trilha, destino).execute()
        assert destino.caminho.exists()
