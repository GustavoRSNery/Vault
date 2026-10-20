"""Publicação e despacho de webhooks.

A prova central: **o que o Vault assina é exatamente o que o destino
consegue verificar.** Um teste que só checasse "assinou" passaria mesmo com
os dois lados em desacordo; aqui o teste faz o papel do destino e confere.

As outras invariantes:

- Publicar **não faz rede**. Se fizesse, revelar um segredo passaria a
  depender de um servidor de terceiro estar no ar.
- O timestamp do cabeçalho é o **do envio**, não o da criação. Usar o da
  criação faria toda reentrega chegar fora da janela e ser recusada — a
  integração pareceria quebrada justamente quando a reentrega funcionasse.
- Destino desligado não gasta tentativa da entrega.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.webhooks import (
    cabecalhos_de,
    despachar,
    publicar,
)
from app.application.ports.webhooks import ResultadoDaEntrega
from app.domain.integrations.entities import (
    EstadoDaEntrega,
    EstadoDoDestino,
    Destino,
    conferir,
)
from app.domain.shared.value_objects import Slug
from app.infrastructure.integrations.entregadores import EntregadorDeEnsaio

AGORA = datetime.now(UTC)


def _destino(nome: str = "siem", **extra) -> Destino:  # noqa: ANN003
    return Destino(
        name=Slug(nome),
        display_name=nome.upper(),
        url=f"https://{nome}.exemplo.com.br/hooks",
        **extra,
    )


class EntregadorQueFalha:
    """Simula um destino fora do ar."""

    def __init__(self, resultado: ResultadoDaEntrega) -> None:
        self._resultado = resultado
        self.chamadas = 0

    @property
    def nome(self) -> str:
        return "falho"

    def entregar(self, **_kwargs) -> ResultadoDaEntrega:  # noqa: ANN003
        self.chamadas += 1
        return self._resultado


class TestPublicar:
    def test_enfileira_para_quem_assina(self) -> None:
        interessado = _destino("siem", eventos=["segredo.*"])
        alheio = _destino("chat", eventos=["cofre.selado"])

        fila = publicar(
            "segredo.revelado", {"caminho": "x"}, destinos=[interessado, alheio]
        )

        assert len(fila) == 1
        assert fila[0].destino_id == interessado.id

    def test_destino_desligado_nao_recebe(self) -> None:
        desligado = _destino("siem", estado=EstadoDoDestino.DESLIGADO)

        assert publicar("segredo.revelado", {}, destinos=[desligado]) == []

    def test_mesmo_corpo_para_todos(self) -> None:
        """É o mesmo evento: remontar por destino geraria timestamps
        ligeiramente diferentes para o que aconteceu no mesmo instante."""
        a, b = _destino("a"), _destino("b")

        fila = publicar("segredo.revelado", {"x": 1}, destinos=[a, b], agora=AGORA)

        assert len({e.corpo for e in fila}) == 1

    def test_ids_de_evento_sao_distintos(self) -> None:
        """Mesmo evento, entregas distintas: cada destino tem sua própria
        chave de idempotência, senão um destino descartaria o evento porque
        o *outro* já o recebeu."""
        a, b = _destino("a"), _destino("b")

        fila = publicar("segredo.revelado", {}, destinos=[a, b])

        assert fila[0].id_evento != fila[1].id_evento

    def test_publicar_nao_faz_rede(self) -> None:
        """Nenhum entregador é sequer recebido como parâmetro — a garantia é
        estrutural, não uma promessa no comentário."""
        import inspect

        from app.application.services import webhooks

        assinatura = inspect.signature(webhooks.publicar)
        assert "entregador" not in assinatura.parameters


class TestAssinaturaCruzada:
    def test_o_destino_consegue_verificar(self) -> None:
        """A prova que importa: assinar e conferir combinam de verdade."""
        destino = _destino()
        fila = publicar("segredo.revelado", {"caminho": "cofres/x"}, destinos=[destino])
        entregador = EntregadorDeEnsaio()

        despachar(fila, {destino.id: destino}, entregador, agora=AGORA)

        enviada = entregador.enviadas[0]
        cab = enviada["cabecalhos"]
        assert conferir(
            destino.segredo,
            id_evento=cab["webhook-id"],
            timestamp=int(cab["webhook-timestamp"]),
            corpo=enviada["corpo"],
            assinatura_recebida=cab["webhook-signature"],
            agora=AGORA,
        )

    def test_os_tres_cabecalhos_da_especificacao(self) -> None:
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino])

        cab = cabecalhos_de(fila[0], destino, AGORA)

        assert set(cab) == {"webhook-id", "webhook-timestamp", "webhook-signature"}

    def test_timestamp_e_o_do_envio(self) -> None:
        """Numa reentrega dois dias depois, usar o instante da criação faria
        o destino recusar por estar fora da janela."""
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino], agora=AGORA)
        depois = AGORA + timedelta(days=2)

        cab = cabecalhos_de(fila[0], destino, depois)

        assert int(cab["webhook-timestamp"]) == int(depois.timestamp())
        # E o destino aceita, porque o relógio dele também avançou.
        assert conferir(
            destino.segredo,
            id_evento=cab["webhook-id"],
            timestamp=int(cab["webhook-timestamp"]),
            corpo=fila[0].corpo,
            assinatura_recebida=cab["webhook-signature"],
            agora=depois,
        )

    def test_webhook_id_nao_muda_entre_tentativas(self) -> None:
        """É a chave de idempotência do destino."""
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino])
        entrega = fila[0]

        primeiro = cabecalhos_de(entrega, destino, AGORA)["webhook-id"]
        entrega.marcar_falha("timeout", agora=AGORA)
        segundo = cabecalhos_de(entrega, destino, AGORA)["webhook-id"]

        assert primeiro == segundo


class TestDespachar:
    def test_sucesso_marca_entregue(self) -> None:
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino])

        resumo, entregas, _ = despachar(
            fila, {destino.id: destino}, EntregadorDeEnsaio(), agora=AGORA
        )

        assert resumo.entregues == 1
        assert entregas[0].estado is EstadoDaEntrega.ENTREGUE

    def test_falha_reagenda(self) -> None:
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino], agora=AGORA)
        entregador = EntregadorQueFalha(
            ResultadoDaEntrega(sucesso=False, status=503, erro="indisponível")
        )

        resumo, entregas, _ = despachar(
            fila, {destino.id: destino}, entregador, agora=AGORA
        )

        assert resumo.falhadas == 1
        assert entregas[0].estado is EstadoDaEntrega.FALHOU
        assert entregas[0].proxima_em > AGORA

    def test_410_desliga_o_destino(self) -> None:
        """O destino declarou que não existe mais; insistir enche a fila."""
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino])
        entregador = EntregadorQueFalha(
            ResultadoDaEntrega(
                sucesso=False, status=410, erro="Gone", desativar_destino=True
            )
        )

        resumo, _, destinos = despachar(
            fila, {destino.id: destino}, entregador, agora=AGORA
        )

        assert destinos[0].estado is EstadoDoDestino.DESLIGADO
        assert resumo.destinos_desligados == 1

    def test_retry_after_e_respeitado(self) -> None:
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino], agora=AGORA)
        entregador = EntregadorQueFalha(
            ResultadoDaEntrega(
                sucesso=False, status=429, erro="devagar", retry_after=600
            )
        )

        _, entregas, _ = despachar(
            fila, {destino.id: destino}, entregador, agora=AGORA
        )

        assert entregas[0].proxima_em == AGORA + timedelta(seconds=600)

    def test_destino_desligado_nao_gasta_tentativa(self) -> None:
        """Desligado entre o enfileiramento e o despacho: a entrega espera,
        em vez de queimar uma das tentativas contra um destino inativo."""
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino])
        destino.desligar("manutenção")
        entregador = EntregadorDeEnsaio()

        resumo, entregas, _ = despachar(
            fila, {destino.id: destino}, entregador, agora=AGORA
        )

        assert resumo.tentadas == 0
        assert entregador.enviadas == []
        assert entregas[0].tentativas == 0

    def test_destino_sumido_nao_quebra(self) -> None:
        """Destino removido depois do enfileiramento."""
        destino = _destino()
        fila = publicar("x.y", {}, destinos=[destino])

        resumo, _, _ = despachar(fila, {}, EntregadorDeEnsaio(), agora=AGORA)

        assert resumo.tentadas == 0

    def test_corpo_vai_byte_a_byte(self) -> None:
        """Reserializar mudaria os bytes e quebraria a assinatura — é o erro
        mais comum desta especificação."""
        destino = _destino()
        fila = publicar("x.y", {"acento": "Manutenção"}, destinos=[destino])
        entregador = EntregadorDeEnsaio()

        despachar(fila, {destino.id: destino}, entregador, agora=AGORA)

        assert entregador.enviadas[0]["corpo"] == fila[0].corpo
        assert "Manutenção" in entregador.enviadas[0]["corpo"]


class TestPonteComATrilha:
    """A trilha é a fonte dos eventos publicados.

    Um segundo registro paralelo divergiria dela no primeiro erro de
    escrita; a `sequence` já é monotônica e única, então serve de marcador
    de leitura sem estado próprio.
    """

    def test_o_mapa_so_cita_acoes_que_existem(self) -> None:
        """Erro que falha em silêncio: um nome de ação escrito à mão que não
        corresponde a nenhuma `AuditAction` nunca casa, e a integração
        simplesmente não recebe aquele evento — sem erro, sem aviso.
        Aconteceu com três nomes na primeira versão deste mapa.
        """
        from app.application.services.webhooks import ACAO_PARA_EVENTO
        from app.domain.audit.events import AuditAction

        reais = {str(a) for a in AuditAction}
        inexistentes = sorted(a for a in ACAO_PARA_EVENTO if a not in reais)

        assert inexistentes == [], f"ações que não existem na trilha: {inexistentes}"

    def test_os_tipos_publicados_estao_no_enum(self) -> None:
        """O nome publicado é contrato com quem assina: um tipo fora do enum
        não apareceria na lista que a tela oferece para assinar."""
        from app.application.services.webhooks import ACAO_PARA_EVENTO
        from app.domain.integrations.entities import TipoDeEvento

        tipos = {str(t) for t in TipoDeEvento}
        fora = sorted({v for v in ACAO_PARA_EVENTO.values() if v not in tipos})

        assert fora == [], f"tipos fora do enum: {fora}"

    def test_enfileira_so_o_que_tem_destino_interessado(self) -> None:
        from app.application.services.webhooks import enfileirar_da_trilha
        from app.domain.audit.events import AuditAction, AuditEvent, AuditOutcome

        evento = AuditEvent(
            action=AuditAction.SECRET_REVEALED,
            actor_id="u1",
            actor_label="ana@exemplo.com.br",
            target_path="cofres/infra/segredos/senha-root",
            outcome=AuditOutcome.SUCCESS,
            sequence=42,
        )
        interessado = _destino("siem", eventos=["segredo.*"])
        alheio = _destino("chat", eventos=["cofre.selado"])

        fila, maior = enfileirar_da_trilha([evento], [interessado, alheio])

        assert len(fila) == 1
        assert fila[0].destino_id == interessado.id
        assert maior == 42

    def test_marcador_avanca_mesmo_sem_assinante(self) -> None:
        """Avançar só quando há assinante faria o sistema reprocessar os
        mesmos eventos ignorados para sempre."""
        from app.application.services.webhooks import enfileirar_da_trilha
        from app.domain.audit.events import AuditAction, AuditEvent, AuditOutcome

        # `login_sucesso` não está no mapa: ninguém assina.
        evento = AuditEvent(
            action=AuditAction.LOGIN_SUCCESS,
            actor_id="u1",
            actor_label="ana@exemplo.com.br",
            target_path="auth",
            outcome=AuditOutcome.SUCCESS,
            sequence=99,
        )

        fila, maior = enfileirar_da_trilha([evento], [_destino()])

        assert fila == []
        assert maior == 99

    def test_o_dado_publicado_nao_tem_valor_de_segredo(self) -> None:
        """A trilha também não guarda o valor — mas o teste fixa a regra
        para que acrescentar um campo aqui exija decisão consciente."""
        from app.application.services.webhooks import dados_do_evento
        from app.domain.audit.events import AuditAction, AuditEvent, AuditOutcome

        evento = AuditEvent(
            action=AuditAction.SECRET_REVEALED,
            actor_id="u1",
            actor_label="ana@exemplo.com.br",
            target_path="cofres/infra/segredos/senha-root",
            outcome=AuditOutcome.SUCCESS,
            sequence=1,
        )

        dados = dados_do_evento(evento)

        assert dados["alvo"] == "cofres/infra/segredos/senha-root"
        assert not any(
            chave in dados for chave in ("valor", "value", "senha", "secret")
        )
