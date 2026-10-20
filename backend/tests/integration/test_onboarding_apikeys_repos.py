"""Repositórios de convites, pedidos de redefinição e chaves de API.

Estes testes existem por causa de três divergências entre SQLite e Postgres
que já custaram incidente neste projeto e que um teste "feliz" não revela:

1. **`DateTime(timezone=True)` devolve datetime ingênuo no SQLite** e com
   fuso no Postgres. O domínio recusa datetime ingênuo, então a volta do
   banco quebrava num dialeto só.

2. **Ordenação de NULL.** `ORDER BY expira_em` coloca NULL por último no
   Postgres e primeiro no SQLite. `ChaveApiRepository.list_all` ordena "pelo
   que vence primeiro, sem prazo no fim" — se a cláusula `IS NULL` sumisse,
   a lista inverteria em produção e não aqui.

3. **Coluna JSON.** `acessos` e `usada_em` são JSON; lista vazia, acento e
   ordem de chaves se comportam diferente nos dois drivers.

Rode a suíte nos dois dialetos ao mexer nestas colunas:
    VAULT_TEST_DATABASE_URL=postgresql+psycopg://... pytest tests/
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.apikeys.entities import (
    AmbienteDaChave,
    ChaveDeApi,
    EstadoDaChave,
    FormatoDaChave,
)
from app.domain.inventory.entities import (
    AcessoRemoto,
    Device,
    DeviceKind,
    MetodoDeAcesso,
)
from app.domain.onboarding.entities import (
    Convite,
    EstadoDoConvite,
    PedidoDeRedefinicao,
    TipoDeConvite,
    gerar_token,
)
from app.domain.shared.errors import NotFoundError
from app.domain.shared.value_objects import Email, Slug
from app.infrastructure.db.repositories import (
    ChaveApiRepository,
    ConviteRepository,
    DeviceRepository,
    PedidoRedefinicaoRepository,
)

AGORA = datetime.now(UTC)


def _chave(nome: str, *, expira_em: datetime | None, **extra) -> ChaveDeApi:  # noqa: ANN003
    return ChaveDeApi(
        name=Slug(nome),
        display_name=nome.upper(),
        servico="SEFAZ",
        responsavel="fiscal@exemplo.com.br",
        expira_em=expira_em,
        **extra,
    )


class TestChaveApiRepositorio:
    def test_datas_voltam_com_fuso(self, session: Session) -> None:
        """A regressão nº 1: sem fuso, `situacao()` explode ao comparar."""
        repo = ChaveApiRepository(session)
        repo.add(_chave("sefaz-nfe", expira_em=AGORA + timedelta(days=45)))

        lida = repo.get_by_name(Slug("sefaz-nfe"))

        assert lida.expira_em is not None
        assert lida.expira_em.tzinfo is not None
        assert lida.created_at.tzinfo is not None
        # A comparação que quebrava: exercita de fato, não só o atributo.
        assert lida.situacao() is EstadoDaChave.ATIVA

    def test_sem_prazo_vai_para_o_fim_da_lista(self, session: Session) -> None:
        """A regressão nº 2: NULL ordena ao contrário nos dois dialetos.

        A promessa da tela é "o que vence primeiro aparece primeiro". Se a
        chave sem prazo subir para o topo, quem abre a lista vê como urgente
        justamente a que não tem prazo nenhum.
        """
        repo = ChaveApiRepository(session)
        repo.add(_chave("sem-prazo", expira_em=None))
        repo.add(_chave("vence-tarde", expira_em=AGORA + timedelta(days=200)))
        repo.add(_chave("vence-cedo", expira_em=AGORA + timedelta(days=5)))

        nomes = [str(c.name) for c in repo.list_all()]

        assert nomes == ["vence-cedo", "vence-tarde", "sem-prazo"]

    def test_expirada_continua_legivel(self, session: Session) -> None:
        """Chave vencida não some: a auditoria quer saber que existiu."""
        repo = ChaveApiRepository(session)
        repo.add(_chave("velha", expira_em=AGORA - timedelta(days=3)))

        lida = repo.get_by_name(Slug("velha"))

        assert lida.situacao() is EstadoDaChave.EXPIRADA

    def test_revogada_vence_o_relogio(self, session: Session) -> None:
        """Decisão humana vence prazo: revogada não vira "expirada" depois."""
        repo = ChaveApiRepository(session)
        chave = _chave("revogada", expira_em=AGORA - timedelta(days=1))
        chave.estado = EstadoDaChave.REVOGADA
        repo.add(chave)

        assert repo.get_by_name(Slug("revogada")).situacao() is EstadoDaChave.REVOGADA

    def test_lista_json_sobrevive_a_ida_e_volta(self, session: Session) -> None:
        """A regressão nº 3: JSON com acento e lista vazia nos dois drivers."""
        repo = ChaveApiRepository(session)
        repo.add(
            _chave(
                "com-uso",
                expira_em=None,
                usada_em=["rpa-fiscal", "integração-notas"],
                ambiente=AmbienteDaChave.HOMOLOGACAO,
                formato=FormatoDaChave.CABECALHO,
                nome_do_campo="X-API-Key",
                escopo="Consulta de NF-e",
            )
        )
        repo.add(_chave("sem-uso", expira_em=None))

        com_uso = repo.get_by_name(Slug("com-uso"))
        sem_uso = repo.get_by_name(Slug("sem-uso"))

        assert com_uso.usada_em == ["integração-notas", "rpa-fiscal"]
        assert com_uso.ambiente is AmbienteDaChave.HOMOLOGACAO
        assert com_uso.formato is FormatoDaChave.CABECALHO
        assert com_uso.como_usar() == "X-API-Key: <valor>"
        # Lista vazia tem que voltar lista, não None.
        assert sem_uso.usada_em == []

    def test_excluir_remove_so_a_chave(self, session: Session) -> None:
        repo = ChaveApiRepository(session)
        repo.add(_chave("a", expira_em=None))
        repo.add(_chave("b", expira_em=None))

        repo.delete(repo.get_by_name(Slug("a")).id)

        assert [str(c.name) for c in repo.list_all()] == ["b"]
        with pytest.raises(NotFoundError):
            repo.get_by_name(Slug("a"))


class TestConviteRepositorio:
    def test_busca_por_token_usa_o_hash(self, session: Session) -> None:
        repo = ConviteRepository(session)
        token, token_hash = gerar_token()
        repo.add(
            Convite(
                email=Email("novo@exemplo.com.br"),
                tipo=TipoDeConvite.NOVO_USUARIO,
                token_hash=token_hash,
                expira_em=AGORA + timedelta(days=7),
            )
        )

        achado = repo.por_token(token)

        assert achado is not None
        assert str(achado.email) == "novo@exemplo.com.br"
        # O token cru nunca foi gravado.
        assert achado.token_hash != token
        assert achado.confere(token) is True

    def test_token_errado_nao_acha(self, session: Session) -> None:
        repo = ConviteRepository(session)
        _, token_hash = gerar_token()
        repo.add(
            Convite(
                email=Email("novo@exemplo.com.br"),
                tipo=TipoDeConvite.NOVO_USUARIO,
                token_hash=token_hash,
                expira_em=AGORA + timedelta(days=7),
            )
        )

        outro, _ = gerar_token()
        assert repo.por_token(outro) is None

    def test_datas_voltam_com_fuso(self, session: Session) -> None:
        """Sem fuso, `expirou()` compara ingênuo com aware e explode."""
        repo = ConviteRepository(session)
        token, token_hash = gerar_token()
        repo.add(
            Convite(
                email=Email("novo@exemplo.com.br"),
                tipo=TipoDeConvite.NOVO_USUARIO,
                token_hash=token_hash,
                expira_em=AGORA + timedelta(days=7),
            )
        )

        lido = repo.por_token(token)

        assert lido is not None
        assert lido.expira_em.tzinfo is not None
        assert lido.criado_em.tzinfo is not None
        assert lido.esta_valido() is True

    def test_consumido_nao_volta_como_pendente(self, session: Session) -> None:
        """Um link que funciona duas vezes é um link que o atacante usa
        depois da vítima — o estado precisa atravessar o banco."""
        repo = ConviteRepository(session)
        token, token_hash = gerar_token()
        convite = Convite(
            email=Email("novo@exemplo.com.br"),
            tipo=TipoDeConvite.NOVO_USUARIO,
            token_hash=token_hash,
            expira_em=AGORA + timedelta(days=7),
        )
        repo.add(convite)

        convite.consumir()
        repo.save(convite)

        relido = repo.por_token(token)
        assert relido is not None
        assert relido.estado is EstadoDoConvite.USADO
        assert relido.usado_em is not None
        assert relido.usado_em.tzinfo is not None
        assert repo.pendentes() == []

    def test_pendentes_traz_so_pendente(self, session: Session) -> None:
        repo = ConviteRepository(session)
        for email in ("a@exemplo.com.br", "b@exemplo.com.br"):
            _, token_hash = gerar_token()
            repo.add(
                Convite(
                    email=Email(email),
                    tipo=TipoDeConvite.NOVO_USUARIO,
                    token_hash=token_hash,
                    expira_em=AGORA + timedelta(days=7),
                )
            )
        cancelado = repo.pendentes()[0]
        cancelado.cancelar()
        repo.save(cancelado)

        assert len(repo.pendentes()) == 1


class TestPedidoRedefinicaoRepositorio:
    def test_pendentes_e_atendimento(self, session: Session) -> None:
        repo = PedidoRedefinicaoRepository(session)
        pedido = PedidoDeRedefinicao(
            email=Email("sem-mfa@exemplo.com.br"),
            motivo="Perdi o celular",
            ip_address="10.0.0.9",
        )
        repo.add(pedido)

        assert len(repo.pendentes()) == 1

        pedido.atender("admin@exemplo.com.br")
        repo.save(pedido)

        assert repo.pendentes() == []
        relido = repo.get(pedido.id)
        assert relido.atendido is True
        assert relido.atendido_por == "admin@exemplo.com.br"
        assert relido.atendido_em is not None
        assert relido.atendido_em.tzinfo is not None
        assert relido.criado_em.tzinfo is not None


class TestAcessoRemotoPersistido:
    def test_acessos_sobrevivem_a_ida_e_volta(self, session: Session) -> None:
        """Coluna JSON: o identificador do AnyDesk tem espaços, e a porta é
        int ou None — os dois drivers precisam devolver igual."""
        repo = DeviceRepository(session)
        repo.add(
            Device(
                name=Slug("srv-contabil"),
                display_name="Servidor Contábil",
                kind=DeviceKind.SERVER,
                address="10.0.1.20",
                acessos=[
                    AcessoRemoto(
                        metodo=MetodoDeAcesso.RDP,
                        identificador="10.0.1.20",
                        porta=3390,
                        usuario_sugerido="administrador",
                    ),
                    AcessoRemoto(
                        metodo=MetodoDeAcesso.ANYDESK,
                        identificador="123 456 789",
                    ),
                ],
            )
        )

        lido = repo.get_by_name(Slug("srv-contabil"))

        assert len(lido.acessos) == 2
        rdp, anydesk = lido.acessos
        assert rdp.metodo is MetodoDeAcesso.RDP
        assert rdp.porta == 3390
        assert rdp.usuario_sugerido == "administrador"
        assert rdp.suporta_arquivo_rdp is True
        # O identificador volta exatamente como entrou: é o que a pessoa dita
        # no telefone, então um espaço a menos já atrapalha.
        assert anydesk.identificador == "123 456 789"
        assert anydesk.porta is None

    def test_dispositivo_sem_acesso_volta_lista_vazia(self, session: Session) -> None:
        repo = DeviceRepository(session)
        repo.add(
            Device(
                name=Slug("sem-acesso"),
                display_name="Sem acesso",
                kind=DeviceKind.OTHER,
            )
        )

        assert repo.get_by_name(Slug("sem-acesso")).acessos == []

    def test_substituir_acessos_nao_acumula(self, session: Session) -> None:
        """É substituição, não merge: um acesso órfão apontaria para uma
        máquina que já não é alcançada por ali."""
        repo = DeviceRepository(session)
        d = repo.add(
            Device(
                name=Slug("srv"),
                display_name="Servidor",
                acessos=[
                    AcessoRemoto(metodo=MetodoDeAcesso.RDP, identificador="10.0.0.1")
                ],
            )
        )

        repo.save_acessos(
            d.id,
            [AcessoRemoto(metodo=MetodoDeAcesso.ANYDESK, identificador="999 888 777")],
        )

        acessos = repo.get_by_name(Slug("srv")).acessos
        assert len(acessos) == 1
        assert acessos[0].metodo is MetodoDeAcesso.ANYDESK
