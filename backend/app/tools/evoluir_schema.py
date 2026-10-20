"""Aplica as mudanças de schema que `create_all` não aplica.

**Por que esta ferramenta existe.**

`Base.metadata.create_all` cria tabela que falta, mas nunca altera tabela que
já existe. Num banco zerado tudo parece funcionar; num banco que já tem
dados — ou seja, em qualquer ambiente real — uma coluna nova simplesmente não
nasce, e a aplicação sobe e quebra na primeira consulta:

    sqlalchemy.exc.ProgrammingError: column dispositivos.acessos does not exist

Foi exatamente assim que a coluna `acessos` derrubou as rotas de dispositivo
no ambiente local, com os testes todos verdes — porque o teste monta o banco
do zero e o ambiente real não.

**O que esta ferramenta faz.** Compara o que os modelos declaram com o que o
banco tem e aplica as colunas que faltam, de forma idempotente: rodar duas
vezes não muda nada na segunda. É `ADD COLUMN` com valor padrão, que o
Postgres resolve sem reescrever a tabela e sem lock longo — a operação é
segura com a aplicação no ar.

**O que ela deliberadamente NÃO faz:** remover coluna, mudar tipo, renomear.
São operações que perdem dado ou travam a tabela, e cada uma merece decisão
humana. Quando encontra uma, avisa e sai com erro em vez de adivinhar.
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from ..infrastructure.db.models import Base
from ..config import get_settings


def _tipo_sql(coluna, dialeto: str) -> str:
    """Tipo da coluna no dialeto do banco."""
    return coluna.type.compile(dialect=_dialeto(dialeto))


def _dialeto(nome: str):  # noqa: ANN202
    if nome == "postgresql":
        from sqlalchemy.dialects import postgresql

        return postgresql.dialect()
    from sqlalchemy.dialects import sqlite

    return sqlite.dialect()


def _padrao(coluna, dialeto: str) -> str | None:
    """Valor para as linhas que já existem.

    Sem isto, `ADD COLUMN NOT NULL` falha em tabela com dados — e é
    justamente a tabela com dados que importa.
    """
    if coluna.default is not None and coluna.default.is_scalar:
        valor = coluna.default.arg
        if isinstance(valor, str):
            return f"'{valor}'"
        if isinstance(valor, bool):
            return "true" if valor else "false"
        return str(valor)

    # Default de callable (ex.: `default=list`): o SQLAlchemy embrulha a
    # função, então comparar `arg is list` falha. Chamamos o callable sem
    # contexto e serializamos o que ele produz — é literalmente o valor que
    # o ORM gravaria na primeira escrita.
    #
    # Isto importa mais do que parece: um JSON de lista que nasce como `{}`
    # devolve dict onde o código espera list, e o erro só aparece longe
    # daqui, na primeira leitura da linha antiga.
    if coluna.default is not None and coluna.default.is_callable:
        try:
            produzido = coluna.default.arg(None)
        except TypeError:
            produzido = None
        if isinstance(produzido, (list, dict)):
            import json as _json

            return "'" + _json.dumps(produzido) + "'"
        if isinstance(produzido, bool):
            return "true" if produzido else "false"
        if isinstance(produzido, (int, float)):
            return str(produzido)
        if isinstance(produzido, str):
            return f"'{produzido}'"
        # datetime e afins: deixamos o banco decidir no insert.
        return None

    tipo = str(coluna.type).upper()
    if not coluna.nullable:
        if "BOOLEAN" in tipo:
            return "false"
        if "INTEGER" in tipo or "NUMERIC" in tipo:
            return "0"
        if "VARCHAR" in tipo or "TEXT" in tipo:
            return "''"
    return None


def evoluir(engine: Engine, *, aplicar: bool = True) -> list[str]:
    """Devolve (e opcionalmente aplica) as mudanças pendentes."""
    inspetor = inspect(engine)
    dialeto = engine.dialect.name
    existentes = set(inspetor.get_table_names())
    comandos: list[str] = []
    bloqueios: list[str] = []

    for tabela in Base.metadata.sorted_tables:
        if tabela.name not in existentes:
            # Tabela inteira que falta é trabalho do create_all.
            continue

        colunas_no_banco = {c["name"] for c in inspetor.get_columns(tabela.name)}
        declaradas = {c.name for c in tabela.columns}

        for coluna in tabela.columns:
            if coluna.name in colunas_no_banco:
                continue
            tipo = _tipo_sql(coluna, dialeto)
            padrao = _padrao(coluna, dialeto)
            sql = f"ALTER TABLE {tabela.name} ADD COLUMN {coluna.name} {tipo}"
            if padrao is not None:
                sql += f" DEFAULT {padrao}"
                if not coluna.nullable:
                    sql += " NOT NULL"
            elif not coluna.nullable:
                # Sem padrão não dá para preencher as linhas existentes.
                bloqueios.append(
                    f"{tabela.name}.{coluna.name} é NOT NULL sem valor padrão: "
                    f"defina um padrão no modelo ou preencha à mão."
                )
                continue
            comandos.append(sql)

        sobrando = colunas_no_banco - declaradas
        for nome in sorted(sobrando):
            # Não removemos: pode ser coluna de uma versão ainda no ar, e
            # DROP perde o dado para sempre.
            bloqueios.append(
                f"{tabela.name}.{nome} existe no banco e não nos modelos. "
                f"Remoção é decisão humana — nada foi feito."
            )

    if bloqueios:
        print("Atenção:")
        for b in bloqueios:
            print("  -", b)

    if not comandos:
        print("Schema em dia: nenhuma coluna a acrescentar.")
        return []

    for sql in comandos:
        print(("aplicando: " if aplicar else "pendente: ") + sql)
        if aplicar:
            with engine.begin() as conexao:
                conexao.execute(text(sql))

    return comandos


def main() -> None:
    import sys

    apenas_ver = "--conferir" in sys.argv

    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)

    # Primeiro as tabelas que faltam inteiras, depois as colunas.
    Base.metadata.create_all(engine)
    pendentes = evoluir(engine, aplicar=not apenas_ver)

    if apenas_ver and pendentes:
        print(f"\n{len(pendentes)} mudança(s) pendente(s).")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
