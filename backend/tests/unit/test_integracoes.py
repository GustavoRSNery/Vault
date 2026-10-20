"""Webhooks no padrão Standard Webhooks.

A especificação existe porque quatro coisas quebram uma integração caseira, e
cada classe aqui protege uma delas:

1. **Autenticidade** — sem assinatura, quem descobre a URL injeta eventos.
2. **Repetição** — sem o timestamp assinado, um evento capturado hoje é
   reenviado amanhã.
3. **Entrega** — sem reentrega com backoff, a primeira falha de rede perde o
   evento.
4. **Duplicata** — sem id estável entre tentativas, o destino não tem como
   descartar o que já processou.

Referência: https://github.com/standard-webhooks/standard-webhooks
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.integrations.entities import (
    ESPERAS,
    FALHAS_PARA_DESLIGAR,
    PREFIXO_SEGREDO,
    TOLERANCIA_SEGUNDOS,
    Destino,
    Entrega,
    EstadoDaEntrega,
    EstadoDoDestino,
    assinar,
    conferir,
    gerar_segredo,
    montar_corpo,
)
from app.domain.shared.errors import ValidationError
from app.domain.shared.value_objects import Slug

AGORA = datetime.now(UTC)
CORPO = '{"type":"segredo.revelado","timestamp":"2026-10-20T00:00:00+00:00","data":{}}'


def _destino(**extra) -> Destino:  # noqa: ANN003
    campos = {
        "name": Slug("siem"),
        "display_name": "SIEM",
        "url": "https://siem.exemplo.com.br/hooks/vault",
        **extra,
    }
    return Destino(**campos)


class TestSegredo:
    def test_formato_da_especificacao(self) -> None:
        """`whsec_` + base64. O prefixo existe para que varredura de
        credencial vazada reconheça o segredo num log ou num repositório."""
        segredo = gerar_segredo()

        assert segredo.startswith(PREFIXO_SEGREDO)
        bruto = base64.b64decode(segredo[len(PREFIXO_SEGREDO):])
        # A especificação pede de 24 a 64 bytes aleatórios.
        assert 24 <= len(bruto) <= 64

    def test_cada_segredo_e_unico(self) -> None:
        assert gerar_segredo() != gerar_segredo()

    def test_rotacionar_troca_e_devolve(self) -> None:
        """Devolve porque é a única vez que o valor aparece."""
        destino = _destino()
        antigo = destino.segredo

        novo = destino.rotacionar_segredo()

        assert novo != antigo
        assert destino.segredo == novo


class TestAssinatura:
    def test_assina_id_timestamp_e_corpo(self) -> None:
        """A mensagem assinada é `id.timestamp.corpo`, conforme a spec."""
        segredo = gerar_segredo()
        ts = int(AGORA.timestamp())

        assinatura = assinar(segredo, id_evento="evt_1", timestamp=ts, corpo=CORPO)

        # Reproduz o cálculo à mão: se a implementação mudar de esquema, isto
        # falha — é o ponto de ancoragem na especificação.
        chave = base64.b64decode(segredo[len(PREFIXO_SEGREDO):])
        esperado = base64.b64encode(
            hmac.new(chave, f"evt_1.{ts}.{CORPO}".encode(), hashlib.sha256).digest()
        ).decode()
        assert assinatura == f"v1,{esperado}"

    def test_prefixo_v1(self) -> None:
        """`v1` é HMAC-SHA256; `v1a` seria ed25519."""
        assinatura = assinar(
            gerar_segredo(), id_evento="e", timestamp=1, corpo=CORPO
        )
        assert assinatura.startswith("v1,")

    def test_id_com_ponto_e_recusado(self) -> None:
        """O ponto separa os campos da mensagem assinada.

        Um id com ponto moveria a fronteira entre id, timestamp e corpo — e
        dois eventos diferentes poderiam produzir a mesma mensagem assinada.
        """
        with pytest.raises(ValidationError):
            assinar(gerar_segredo(), id_evento="evt.1", timestamp=1, corpo=CORPO)

    def test_confere_a_propria_assinatura(self) -> None:
        segredo = gerar_segredo()
        ts = int(AGORA.timestamp())
        assinatura = assinar(segredo, id_evento="e1", timestamp=ts, corpo=CORPO)

        assert conferir(
            segredo,
            id_evento="e1",
            timestamp=ts,
            corpo=CORPO,
            assinatura_recebida=assinatura,
            agora=AGORA,
        )

    def test_um_byte_a_mais_no_corpo_invalida(self) -> None:
        """A razão de guardar o corpo exatamente como foi assinado."""
        segredo = gerar_segredo()
        ts = int(AGORA.timestamp())
        assinatura = assinar(segredo, id_evento="e1", timestamp=ts, corpo=CORPO)

        assert not conferir(
            segredo,
            id_evento="e1",
            timestamp=ts,
            corpo=CORPO + " ",
            assinatura_recebida=assinatura,
            agora=AGORA,
        )

    def test_outro_segredo_nao_confere(self) -> None:
        ts = int(AGORA.timestamp())
        assinatura = assinar(gerar_segredo(), id_evento="e", timestamp=ts, corpo=CORPO)

        assert not conferir(
            gerar_segredo(),
            id_evento="e",
            timestamp=ts,
            corpo=CORPO,
            assinatura_recebida=assinatura,
            agora=AGORA,
        )

    def test_varias_assinaturas_durante_rotacao(self) -> None:
        """O cabeçalho aceita assinaturas separadas por espaço: é como a
        rotação de segredo acontece sem derrubar entregas em voo."""
        antigo, novo = gerar_segredo(), gerar_segredo()
        ts = int(AGORA.timestamp())
        cabecalho = " ".join(
            [
                assinar(antigo, id_evento="e", timestamp=ts, corpo=CORPO),
                assinar(novo, id_evento="e", timestamp=ts, corpo=CORPO),
            ]
        )

        for segredo in (antigo, novo):
            assert conferir(
                segredo,
                id_evento="e",
                timestamp=ts,
                corpo=CORPO,
                assinatura_recebida=cabecalho,
                agora=AGORA,
            )

    def test_comparacao_em_tempo_constante(self) -> None:
        """Comparar com `==` vazaria, pelo tempo de resposta, quantos bytes
        iniciais o atacante acertou. O teste é estrutural porque a diferença
        é temporal, não funcional — nenhuma asserção de valor a pegaria."""
        import inspect

        from app.domain.integrations import entities

        fonte = inspect.getsource(entities.conferir)
        assert "compare_digest" in fonte


class TestRepeticao:
    def test_fora_da_janela_e_recusado(self) -> None:
        """O evento legítimo de ontem não vale hoje."""
        segredo = gerar_segredo()
        velho = AGORA - timedelta(seconds=TOLERANCIA_SEGUNDOS + 60)
        ts = int(velho.timestamp())
        assinatura = assinar(segredo, id_evento="e", timestamp=ts, corpo=CORPO)

        assert not conferir(
            segredo,
            id_evento="e",
            timestamp=ts,
            corpo=CORPO,
            assinatura_recebida=assinatura,
            agora=AGORA,
        )

    def test_dentro_da_janela_passa(self) -> None:
        segredo = gerar_segredo()
        recente = AGORA - timedelta(seconds=TOLERANCIA_SEGUNDOS - 30)
        ts = int(recente.timestamp())
        assinatura = assinar(segredo, id_evento="e", timestamp=ts, corpo=CORPO)

        assert conferir(
            segredo,
            id_evento="e",
            timestamp=ts,
            corpo=CORPO,
            assinatura_recebida=assinatura,
            agora=AGORA,
        )

    def test_timestamp_no_futuro_tambem_e_recusado(self) -> None:
        """Relógio adiantado do outro lado não deve virar janela maior."""
        segredo = gerar_segredo()
        futuro = AGORA + timedelta(seconds=TOLERANCIA_SEGUNDOS + 60)
        ts = int(futuro.timestamp())
        assinatura = assinar(segredo, id_evento="e", timestamp=ts, corpo=CORPO)

        assert not conferir(
            segredo,
            id_evento="e",
            timestamp=ts,
            corpo=CORPO,
            assinatura_recebida=assinatura,
            agora=AGORA,
        )


class TestCorpo:
    def test_formato_recomendado(self) -> None:
        corpo = montar_corpo("segredo.revelado", {"caminho": "cofres/x"}, agora=AGORA)
        lido = json.loads(corpo)

        assert lido["type"] == "segredo.revelado"
        assert lido["data"] == {"caminho": "cofres/x"}
        assert lido["timestamp"] == AGORA.isoformat()

    def test_corpo_e_texto_e_nao_dicionario(self) -> None:
        """Devolve texto porque o que é assinado tem de ser o que é enviado.

        Se o domínio devolvesse dicionário, alguém reserializaria antes de
        enviar e os bytes mudariam — a assinatura do outro lado falharia por
        um motivo invisível no código.
        """
        assert isinstance(montar_corpo("x.y", {}), str)

    def test_acento_nao_vira_escape(self) -> None:
        """`ensure_ascii=False`: o destino lê o texto como foi escrito."""
        corpo = montar_corpo("x.y", {"motivo": "Manutenção programada"})
        assert "Manutenção" in corpo


class TestDestino:
    def test_http_simples_e_recusado(self) -> None:
        """A assinatura prova a origem; não esconde o conteúdo. E no
        conteúdo vão caminhos de segredos."""
        with pytest.raises(ValidationError):
            _destino(url="http://siem.exemplo.com.br/hook")

    def test_lista_vazia_quer_dizer_todos(self) -> None:
        """O padrão menos surpreendente para quem acabou de cadastrar."""
        destino = _destino()
        assert destino.interessa("segredo.revelado")
        assert destino.interessa("cofre.selado")

    def test_filtro_exato(self) -> None:
        destino = _destino(eventos=["segredo.revelado"])
        assert destino.interessa("segredo.revelado")
        assert not destino.interessa("segredo.criado")

    def test_curinga_casa_a_familia(self) -> None:
        """`segredo.*` deixa o destino assinar eventos que ainda não existem."""
        destino = _destino(eventos=["segredo.*"])
        assert destino.interessa("segredo.revelado")
        assert destino.interessa("segredo.excluido")
        assert not destino.interessa("cofre.selado")

    def test_falhas_seguidas_desligam(self) -> None:
        """Endpoint quebrado que ninguém conserta viraria fila infinita."""
        destino = _destino()
        for _ in range(FALHAS_PARA_DESLIGAR):
            destino.registrar_falha("timeout")

        assert destino.estado is EstadoDoDestino.DESLIGADO

    def test_sucesso_zera_o_contador(self) -> None:
        """Falha isolada não pode acumular rumo ao desligamento."""
        destino = _destino()
        for _ in range(FALHAS_PARA_DESLIGAR - 1):
            destino.registrar_falha("timeout")

        destino.registrar_sucesso()

        assert destino.falhas_seguidas == 0
        assert destino.estado is EstadoDoDestino.ATIVO
        assert destino.ultimo_erro == ""

    def test_reativar_limpa_o_historico(self) -> None:
        destino = _destino()
        destino.desligar("410 Gone")

        destino.reativar()

        assert destino.estado is EstadoDoDestino.ATIVO
        assert destino.falhas_seguidas == 0


class TestEntrega:
    def test_id_do_evento_nao_muda_entre_tentativas(self) -> None:
        """É a chave de idempotência do destino. Trocar a cada tentativa
        faria o destino processar o mesmo evento várias vezes — exatamente o
        que o campo existe para evitar."""
        entrega = Entrega(destino_id="d1", tipo="segredo.revelado", corpo=CORPO)
        original = entrega.id_evento

        entrega.marcar_falha("timeout", agora=AGORA)
        entrega.marcar_falha("timeout", agora=AGORA)

        assert entrega.id_evento == original

    def test_espera_cresce_a_cada_falha(self) -> None:
        entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)

        entrega.marcar_falha("1", agora=AGORA)
        primeira = entrega.proxima_em
        entrega.marcar_falha("2", agora=AGORA)
        segunda = entrega.proxima_em

        assert segunda > primeira

    def test_jitter_nunca_adianta(self) -> None:
        """O jitter espalha as reentregas para que mil falhas simultâneas não
        voltem juntas e derrubem o destino na hora em que ele sobe. Mas só
        atrasa: adiantar não ajudaria ninguém.

        Exercita a **terceira** falha de propósito. Na primeira a base é de 5
        segundos, e `int(5 * 0.2 * x)` arredonda para zero — o jitter nem
        atua ali, e um teste ancorado nessa tentativa passaria mesmo com a
        conta invertida. Descoberto por mutação: trocar `+` por `-` não
        quebrava nada.
        """
        for _ in range(30):
            entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)
            entrega.marcar_falha("1", agora=AGORA)
            entrega.marcar_falha("2", agora=AGORA)
            entrega.marcar_falha("3", agora=AGORA)

            base = ESPERAS[entrega.tentativas]
            espera = (entrega.proxima_em - AGORA).total_seconds()
            assert espera >= base, "o jitter adiantou a reentrega"
            assert espera <= base * 1.2, "o jitter passou de 20%"

    def test_jitter_de_fato_varia(self) -> None:
        """Se o jitter sempre devolvesse o mesmo valor, mil entregas que
        falharam juntas voltariam juntas — que é exatamente o que ele existe
        para evitar. Uma constante passaria no teste acima."""
        esperas = set()
        for _ in range(60):
            entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)
            for n in range(4):
                entrega.marcar_falha(str(n), agora=AGORA)
            esperas.add((entrega.proxima_em - AGORA).total_seconds())

        assert len(esperas) > 1, "o jitter não variou em 60 tentativas"

    def test_retry_after_vence_o_cronograma(self) -> None:
        """O destino pediu um tempo; respeitar é mais eficaz que insistir."""
        entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)

        entrega.marcar_falha("429", status=429, agora=AGORA, retry_after=120)

        assert entrega.proxima_em == AGORA + timedelta(seconds=120)

    def test_desiste_depois_de_esgotar(self) -> None:
        entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)
        for _ in range(len(ESPERAS)):
            entrega.marcar_falha("erro", agora=AGORA)

        assert entrega.estado is EstadoDaEntrega.DESISTIU
        assert not entrega.pronta(AGORA + timedelta(days=30))

    def test_entregue_nao_volta_para_a_fila(self) -> None:
        entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)
        entrega.marcar_entregue(200, agora=AGORA)

        assert entrega.estado is EstadoDaEntrega.ENTREGUE
        assert not entrega.pronta(AGORA + timedelta(days=1))

    def test_pronta_so_depois_da_espera(self) -> None:
        entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)
        entrega.marcar_falha("erro", agora=AGORA, retry_after=300)

        assert not entrega.pronta(AGORA + timedelta(seconds=299))
        assert entrega.pronta(AGORA + timedelta(seconds=301))

    def test_corpo_guardado_e_o_assinado(self) -> None:
        """Reconstruir o corpo na reentrega produziria bytes diferentes e uma
        assinatura que não confere — o erro clássico desta especificação."""
        entrega = Entrega(destino_id="d1", tipo="x.y", corpo=CORPO)
        segredo = gerar_segredo()
        ts = int(AGORA.timestamp())
        assinatura = assinar(
            segredo, id_evento=entrega.id_evento, timestamp=ts, corpo=entrega.corpo
        )

        entrega.marcar_falha("timeout", agora=AGORA)

        # Depois da falha, o corpo guardado ainda produz a mesma assinatura.
        assert conferir(
            segredo,
            id_evento=entrega.id_evento,
            timestamp=ts,
            corpo=entrega.corpo,
            assinatura_recebida=assinatura,
            agora=AGORA,
        )


class TestAdaptadores:
    def test_ensaio_registra_sem_enviar(self) -> None:
        from app.infrastructure.integrations.entregadores import EntregadorDeEnsaio

        entregador = EntregadorDeEnsaio()
        resultado = entregador.entregar(
            url="https://x.exemplo.com.br/h",
            corpo=CORPO,
            cabecalhos={"webhook-id": "e1"},
        )

        assert resultado.sucesso
        assert entregador.enviadas[0]["corpo"] == CORPO
        assert entregador.enviadas[0]["cabecalhos"]["webhook-id"] == "e1"

    def test_ambos_satisfazem_a_porta(self) -> None:
        """A exigência de ports and adapters: trocar a implementação não
        pode exigir mudar o domínio."""
        from app.application.ports.webhooks import EntregadorDeWebhook
        from app.infrastructure.integrations.entregadores import (
            EntregadorDeEnsaio,
            EntregadorHttp,
        )

        assert isinstance(EntregadorDeEnsaio(), EntregadorDeWebhook)
        assert isinstance(EntregadorHttp(), EntregadorDeWebhook)

    def test_retry_after_invalido_e_ignorado(self) -> None:
        """Data HTTP depende do relógio do destino; no passado agendaria
        reentrega imediata em laço."""
        from app.infrastructure.integrations.entregadores import _ler_retry_after

        assert _ler_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None
        assert _ler_retry_after(None) is None
        assert _ler_retry_after("120") == 120

    def test_retry_after_tem_teto(self) -> None:
        """Um destino que pede uma semana desligaria a integração em
        silêncio."""
        from app.infrastructure.integrations.entregadores import _ler_retry_after

        assert _ler_retry_after("999999") == 86_400


class TestTraducaoDeStatus:
    """Como o adaptador HTTP traduz a resposta do destino.

    É o adaptador que vai para produção, e a tradução decide se a entrega
    volta para a fila ou desliga o destino. Testado com uma resposta
    fabricada em vez de servidor de mentira: o que importa aqui é a decisão,
    não o transporte.
    """

    def _resposta(self, status: int, headers: dict | None = None):  # noqa: ANN202
        class RespostaFalsa:
            status_code = status
            headers = {}

        r = RespostaFalsa()
        r.headers = headers or {}
        return r

    def _entregar_com(self, resposta):  # noqa: ANN001, ANN202
        """Chama o adaptador com o httpx substituído."""
        import sys
        import types

        from app.infrastructure.integrations.entregadores import EntregadorHttp

        falso = types.ModuleType("httpx")
        falso.post = lambda *a, **k: resposta  # noqa: ARG005
        original = sys.modules.get("httpx")
        sys.modules["httpx"] = falso
        try:
            return EntregadorHttp().entregar(
                url="https://x.exemplo.com.br/h", corpo="{}", cabecalhos={}
            )
        finally:
            if original is not None:
                sys.modules["httpx"] = original
            else:
                del sys.modules["httpx"]

    def test_2xx_e_sucesso(self) -> None:
        resultado = self._entregar_com(self._resposta(204))

        assert resultado.sucesso
        assert resultado.status == 204

    def test_410_desliga_o_destino(self) -> None:
        """O destino declarou que não existe mais; insistir enche a fila."""
        resultado = self._entregar_com(self._resposta(410))

        assert not resultado.sucesso
        assert resultado.desativar_destino

    def test_5xx_reenvia_sem_desligar(self) -> None:
        """Destino no ar e quebrado: volta para a fila."""
        resultado = self._entregar_com(self._resposta(503))

        assert not resultado.sucesso
        assert not resultado.desativar_destino

    def test_429_reenvia_e_respeita_retry_after(self) -> None:
        """Pedido de calma, não erro permanente."""
        resultado = self._entregar_com(
            self._resposta(429, {"retry-after": "120"})
        )

        assert not resultado.desativar_destino
        assert resultado.retry_after == 120

    def test_400_e_permanente(self) -> None:
        """Pedido malformado: reenviar repetiria o mesmo erro, e insistir
        gastaria a fila com o que nunca vai passar."""
        resultado = self._entregar_com(self._resposta(400))

        assert not resultado.sucesso
        assert resultado.desativar_destino

    def test_falha_de_rede_nao_levanta(self) -> None:
        """Exceção aqui obrigaria cada chamador a repetir o mesmo `try` e a
        inventar sua própria tradução de erro."""
        import sys
        import types

        from app.infrastructure.integrations.entregadores import EntregadorHttp

        def explode(*_args, **_kwargs):
            raise OSError("conexão recusada")

        falso = types.ModuleType("httpx")
        falso.post = explode
        original = sys.modules.get("httpx")
        sys.modules["httpx"] = falso
        try:
            resultado = EntregadorHttp().entregar(
                url="https://x.exemplo.com.br/h", corpo="{}", cabecalhos={}
            )
        finally:
            if original is not None:
                sys.modules["httpx"] = original
            else:
                del sys.modules["httpx"]

        assert not resultado.sucesso
        assert resultado.status is None, "sem resposta é diferente de erro HTTP"
        assert "recusada" in resultado.erro

    def test_nao_segue_redirecionamento(self) -> None:
        """Seguir levaria o evento assinado — com caminhos de segredos —
        para um host que não é o cadastrado. A especificação manda tratar
        3xx como falha."""
        import inspect

        from app.infrastructure.integrations import entregadores

        fonte = inspect.getsource(entregadores.EntregadorHttp.entregar)
        assert "follow_redirects=False" in fonte

    def test_envia_o_corpo_sem_reserializar(self) -> None:
        """`content=` e não `json=`: o corpo já foi assinado byte a byte, e
        deixar o cliente reserializar invalidaria a assinatura."""
        import inspect

        from app.infrastructure.integrations import entregadores

        fonte = inspect.getsource(entregadores.EntregadorHttp.entregar)
        # Só as linhas de código: `json=` aparece no comentário que explica
        # justamente por que ele não é usado.
        codigo = [
            linha for linha in fonte.splitlines()
            if not linha.strip().startswith("#")
        ]
        assert any("content=" in linha for linha in codigo)
        assert not any("json=" in linha for linha in codigo)
