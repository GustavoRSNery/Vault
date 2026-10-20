"""Evolução de schema em banco que já tem dados.

**O incidente que originou estes testes.** A coluna `dispositivos.acessos`
foi declarada nos modelos, a suíte inteira ficou verde e a API subiu
quebrada no ambiente local:

    psycopg.errors.UndefinedColumn: column dispositivos.acessos does not exist

A causa não é a coluna: é que `create_all` cria tabela que falta e **nunca
altera tabela que já existe**. Os testes montam o banco do zero a cada
execução, então nenhum deles podia ver o problema — o verde era real e
inútil ao mesmo tempo.

Estes testes partem do estado que importa: uma tabela que já existe, sem a
coluna, **com linha dentro**. É a única configuração em que o bug aparece.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import Engine, inspect, text

from app.tools.evoluir_schema import evoluir


@pytest.fixture
def tabela_defasada(engine: Engine) -> Engine:
    """Simula o banco de ontem: a tabela existe, a coluna nova não.

    A linha pré-existente é o ponto: `ADD COLUMN NOT NULL` sem valor padrão
    falha justamente quando há dados, que é sempre o caso em produção.
    """
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE dispositivos DROP COLUMN acessos"))
        conexao.execute(
            text(
                "INSERT INTO dispositivos "
                "(id, name, display_name, kind, address, tags, description, "
                " is_active, created_at) "
                "VALUES ('d-velho', 'srv-velho', 'Servidor Velho', 'servidor', "
                "'10.0.0.1', '[]', '', true, CURRENT_TIMESTAMP)"
            )
        )
    yield engine
    # O fixture de sessão dá rollback, mas DDL não participa da transação:
    # devolvemos a coluna à mão para não contaminar os outros testes.
    with engine.begin() as conexao:
        colunas = {c["name"] for c in inspect(engine).get_columns("dispositivos")}
        if "acessos" not in colunas:
            conexao.execute(
                text(
                    "ALTER TABLE dispositivos ADD COLUMN acessos JSON "
                    "DEFAULT '[]' NOT NULL"
                )
            )
        conexao.execute(text("DELETE FROM dispositivos WHERE id = 'd-velho'"))


class TestEvoluirSchema:
    def test_acrescenta_coluna_que_falta(self, tabela_defasada: Engine) -> None:
        """O caso do incidente, reproduzido."""
        antes = {c["name"] for c in inspect(tabela_defasada).get_columns("dispositivos")}
        assert "acessos" not in antes

        aplicados = evoluir(tabela_defasada)

        depois = {c["name"] for c in inspect(tabela_defasada).get_columns("dispositivos")}
        assert "acessos" in depois
        assert any("acessos" in sql for sql in aplicados)

    def test_linha_existente_recebe_lista_vazia(self, tabela_defasada: Engine) -> None:
        """O erro que o `DEFAULT` errado causaria.

        Se a coluna nascesse com `'{}'`, a linha antiga devolveria dict onde
        o código espera list — e o estouro aconteceria longe daqui, na
        primeira leitura. `[]` é o que o ORM gravaria numa inserção nova.
        """
        evoluir(tabela_defasada)

        with tabela_defasada.begin() as conexao:
            valor = conexao.execute(
                text("SELECT acessos FROM dispositivos WHERE id = 'd-velho'")
            ).scalar_one()

        # O driver pode devolver já decodificado ou como texto.
        decodificado = json.loads(valor) if isinstance(valor, str) else valor
        assert decodificado == []
        assert isinstance(decodificado, list)

    def test_rodar_duas_vezes_nao_muda_nada(self, tabela_defasada: Engine) -> None:
        """Idempotência: o boot roda isto toda vez que o container sobe."""
        primeira = evoluir(tabela_defasada)
        segunda = evoluir(tabela_defasada)

        assert primeira != []
        assert segunda == []

    def test_conferir_nao_altera_o_banco(self, tabela_defasada: Engine) -> None:
        """`--conferir` precisa ser seguro de rodar contra produção."""
        pendentes = evoluir(tabela_defasada, aplicar=False)

        assert pendentes != []
        colunas = {c["name"] for c in inspect(tabela_defasada).get_columns("dispositivos")}
        assert "acessos" not in colunas

    def test_schema_em_dia_nao_gera_comando(self, engine: Engine) -> None:
        """O caso comum: nada a fazer, e a ferramenta não inventa trabalho."""
        assert evoluir(engine) == []
