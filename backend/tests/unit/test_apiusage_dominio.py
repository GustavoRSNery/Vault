"""Domínio da governança de API: classificação de origem e do resultado.

A classificação de origem é a regra que decide o que entra no relatório.
Errar para o lado de esconder cria um consumidor invisível — que é o
contrário do que a tela existe para mostrar.
"""

from __future__ import annotations

import pytest

from app.domain.apiusage.entities import (
    AGENTE_MAXIMO,
    CAMINHO_MAXIMO,
    ChamadaDeApi,
    Origem,
    Resultado,
    registrar_chamada,
)
from app.domain.shared.errors import ValidationError

ORIGENS_DA_TELA = ("http://localhost:5173", "https://vault.empresa.com.br")


def _classificar(**kwargs):
    base = {
        "tem_lease": False,
        "origin": None,
        "sec_fetch_site": None,
        "origens_da_tela": ORIGENS_DA_TELA,
    }
    base.update(kwargs)
    return Origem.classificar(**base)


class TestClassificacaoDeOrigem:
    def test_tela_exige_origin_conhecido_e_same_origin(self):
        assert (
            _classificar(
                origin="http://localhost:5173", sec_fetch_site="same-origin"
            )
            is Origem.TELA
        )

    def test_origin_conhecido_sem_sec_fetch_nao_e_tela(self):
        # curl manda o Origin que quiser, mas não produz Sec-Fetch-Site:
        # esse cabeçalho é posto pelo navegador. Sem ele, é consumo de fora
        # e tem de aparecer no relatório.
        assert (
            _classificar(origin="http://localhost:5173", sec_fetch_site=None)
            is Origem.EXTERNA
        )

    def test_sem_origin_mas_same_origin_e_tela(self):
        """O caso NORMAL de produção: front e API no mesmo host.

        O navegador omite `Origin` em GET same-origin. Exigi-lo fazia toda a
        navegação da interface entrar no relatório como externa — foi um bug
        real, visto na tela com o sistema no ar, e não uma hipótese.
        """
        assert (
            _classificar(origin=None, sec_fetch_site="same-origin") is Origem.TELA
        )

    def test_sem_origin_e_sem_sec_fetch_continua_externa(self):
        # Um script não manda nenhum dos dois. A ausência de `Origin`
        # sozinha não pode abrir a porta de saída do relatório.
        assert _classificar(origin=None, sec_fetch_site=None) is Origem.EXTERNA

    def test_sec_fetch_de_outro_site_nao_e_tela(self):
        assert (
            _classificar(
                origin="http://localhost:5173", sec_fetch_site="cross-site"
            )
            is Origem.EXTERNA
        )

    def test_origin_desconhecido_nao_e_tela(self):
        assert (
            _classificar(
                origin="https://site-de-fora.com", sec_fetch_site="same-origin"
            )
            is Origem.EXTERNA
        )

    def test_lease_vence_qualquer_cabecalho_de_tela(self):
        # Um RPA autenticado é consumo de máquina mesmo que os cabeçalhos
        # imitem a interface. Sem esta precedência, bastaria forjar dois
        # cabeçalhos para um robô sumir do relatório.
        assert (
            _classificar(
                tem_lease=True,
                origin="http://localhost:5173",
                sec_fetch_site="same-origin",
            )
            is Origem.APLICACAO
        )

    def test_sem_nenhum_cabecalho_e_externa(self):
        assert _classificar() is Origem.EXTERNA

    def test_origin_declarado_fora_da_lista_e_externa_mesmo_com_sec_fetch(self):
        # Quando o `Origin` VEM, ele tem de bater com a lista configurada.
        # Sem essa conferência, uma página de outro host que conseguisse
        # emitir same-origin sairia do relatório.
        assert (
            Origem.classificar(
                tem_lease=False,
                origin="https://site-de-fora.com",
                sec_fetch_site="same-origin",
                origens_da_tela=ORIGENS_DA_TELA,
            )
            is Origem.EXTERNA
        )
        # E com a lista vazia, um `Origin` declarado nunca passa.
        assert (
            Origem.classificar(
                tem_lease=False,
                origin="http://localhost:5173",
                sec_fetch_site="same-origin",
                origens_da_tela=(),
            )
            is Origem.EXTERNA
        )


class TestResultado:
    @pytest.mark.parametrize(
        "status,esperado",
        [
            (200, Resultado.OK),
            (201, Resultado.OK),
            (204, Resultado.OK),
            (301, Resultado.REDIRECIONADO),
            (400, Resultado.INVALIDO),
            (401, Resultado.RECUSADO),
            (403, Resultado.RECUSADO),
            (404, Resultado.INVALIDO),
            (422, Resultado.INVALIDO),
            (500, Resultado.ERRO),
            (503, Resultado.ERRO),
        ],
    )
    def test_faixa_do_status(self, status, esperado):
        assert Resultado.da_resposta(status) is esperado

    def test_recusado_e_separado_dos_demais_quatro_centos(self):
        # 401/403 contam "quem tentou sem poder"; 404/422 contam "quem errou
        # a chamada". Juntá-los faria um cliente mal configurado parecer
        # tentativa de acesso indevido.
        assert Resultado.da_resposta(403) is not Resultado.da_resposta(404)


class TestRegistroDaChamada:
    def test_deriva_resultado_do_status(self):
        c = registrar_chamada(
            metodo="get", caminho="/api/v1/cofres", status=403,
            origem=Origem.EXTERNA, duracao_ms=12,
        )
        assert c.resultado is Resultado.RECUSADO
        assert c.metodo == "GET"

    def test_trunca_caminho_longo_em_vez_de_recusar(self):
        # A chamada já aconteceu. Recusar o registro faria justamente a
        # requisição anômala — URL gigante — não aparecer em lugar nenhum.
        c = registrar_chamada(
            metodo="GET", caminho="/api/v1/" + "a" * 900, status=404,
            origem=Origem.EXTERNA, duracao_ms=1,
        )
        assert len(c.caminho) == CAMINHO_MAXIMO

    def test_trunca_agente_longo(self):
        c = registrar_chamada(
            metodo="GET", caminho="/api/v1/cofres", status=200,
            origem=Origem.EXTERNA, duracao_ms=1, agente="x" * 900,
        )
        assert len(c.agente) == AGENTE_MAXIMO

    def test_chamada_sem_identidade_e_anonima(self):
        c = registrar_chamada(
            metodo="POST", caminho="/api/v1/auth/login", status=401,
            origem=Origem.EXTERNA, duracao_ms=80,
        )
        assert c.anonima is True
        assert c.quem == "anônimo"

    def test_rotulo_prefere_aplicacao(self):
        c = registrar_chamada(
            metodo="GET", caminho="/api/v1/maquina/segredo", status=200,
            origem=Origem.APLICACAO, duracao_ms=9,
            aplicacao_id="app-1", aplicacao_nome="Robô da folha",
        )
        assert c.quem == "Robô da folha"
        assert c.anonima is False

    def test_nao_aceita_aplicacao_e_pessoa_juntas(self):
        # Duas identidades na mesma linha significa que o adaptador
        # misturou os caminhos de autenticação, e o registro deixa de
        # responder "quem chamou".
        with pytest.raises(ValidationError):
            ChamadaDeApi(
                id="x", recebida_em=None, metodo="GET", caminho="/api/v1/x",  # type: ignore[arg-type]
                status=200, resultado=Resultado.OK, origem=Origem.EXTERNA,
                aplicacao_id="app-1", aplicacao_nome="App",
                usuario_id="user-1", usuario_email="a@b.com",
                ip="", agente="", duracao_ms=1, bytes_recebidos=0,
            )

    def test_recusa_duracao_negativa(self):
        with pytest.raises(ValidationError):
            registrar_chamada(
                metodo="GET", caminho="/api/v1/x", status=200,
                origem=Origem.EXTERNA, duracao_ms=-1,
            )

    def test_recusa_metodo_vazio(self):
        with pytest.raises(ValidationError):
            registrar_chamada(
                metodo="", caminho="/api/v1/x", status=200,
                origem=Origem.EXTERNA, duracao_ms=1,
            )


class TestCorpoNaoEArmazenado:
    def test_entidade_nao_tem_campo_para_o_corpo(self):
        """O corpo não entra no domínio — nem como campo opcional.

        Isto é a restrição que o usuário pediu, verificada na estrutura e
        não só por convenção: enquanto não existir campo, nenhum adaptador
        futuro pode passar a gravar conteúdo de requisição sem alterar a
        entidade de propósito, o que torna a mudança visível em revisão.
        """
        campos = set(ChamadaDeApi.__slots__)
        proibidos = {"corpo", "body", "payload", "conteudo", "dados", "request_body"}
        assert campos & proibidos == set()

    def test_guarda_apenas_o_tamanho(self):
        c = registrar_chamada(
            metodo="POST", caminho="/api/v1/cofres/rh/segredos", status=201,
            origem=Origem.APLICACAO, duracao_ms=87, bytes_recebidos=412,
            aplicacao_id="app-1", aplicacao_nome="Robô",
        )
        assert c.bytes_recebidos == 412
