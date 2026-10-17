"""Fixtures dos testes de integração.

O banco padrão é SQLite em memória, por ser rápido e não exigir serviço no ar.
Mas SQLite e Postgres divergem em pontos que já derrubaram produção — tipos,
comparação de texto, isolamento, e principalmente o comportamento de FK, que
no SQLite vem DESLIGADO por padrão.

Por isso: as FKs são ligadas explicitamente abaixo, e a mesma suíte roda
contra Postgres quando VAULT_TEST_DATABASE_URL estiver definida.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.crypto.envelope import EnvelopeCryptoService, LocalKeyProvider
from app.infrastructure.db.models import Base

# Aponte para um Postgres real para rodar a suíte no dialeto de produção:
#   VAULT_TEST_DATABASE_URL=postgresql+psycopg://user:senha@localhost:5432/vault_test
POSTGRES_URL = os.getenv("VAULT_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    if POSTGRES_URL:
        eng = create_engine(POSTGRES_URL, future=True)
    else:
        eng = create_engine("sqlite+pysqlite:///:memory:", future=True)

        # SQLite ignora FK por padrão: sem isto, um teste de integridade
        # referencial passaria aqui e quebraria em Postgres.
        @event.listens_for(eng, "connect")
        def _enable_fk(dbapi_connection, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Sessão isolada por teste: tudo roda numa transação que sofre rollback.

    Nenhum teste enxerga o que outro escreveu, mesmo com o banco compartilhado.
    """
    connection = engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(bind=connection, future=True)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def crypto() -> EnvelopeCryptoService:
    return EnvelopeCryptoService(LocalKeyProvider.generate())


@pytest.fixture
def is_postgres() -> bool:
    return bool(POSTGRES_URL)
