"""Fixtures dos testes end-to-end: a API inteira, contra banco real."""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.config import Settings, get_settings
from app.infrastructure.crypto.envelope import EnvelopeCryptoService, LocalKeyProvider
from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import (
    Base,
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    UserModel,
)
from app.main import create_app

CHAVE_TESTE = base64.b64encode(b"k" * 32).decode()
JWT_TESTE = "segredo-de-teste-com-mais-de-trinta-e-dois-bytes"
SENHA = "senha-forte-do-ana.souza-2026"
EMAIL = "ana.souza@exemplo.com.br"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        master_key_b64=CHAVE_TESTE,
        jwt_secret=JWT_TESTE,
    )


@pytest.fixture
def db_session(settings: Settings) -> Iterator[Session]:
    # StaticPool é obrigatório aqui: ":memory:" cria um banco NOVO por conexão,
    # então o create_all e a sessão da requisição cairiam em bancos distintos
    # ("no such table"). Com StaticPool todos compartilham a mesma conexão.
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def app(settings: Settings, db_session: Session) -> FastAPI:
    """App com a sessão de teste injetada no lugar da real."""
    application = create_app()

    def _override_db() -> Iterator[Session]:
        # Commit de verdade: os testes conferem o que ficou gravado.
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    application.dependency_overrides[get_db] = _override_db
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False para que o handler de 500 responda como
    # responderia em produção, em vez de o erro subir para o teste.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def crypto(settings: Settings) -> EnvelopeCryptoService:
    return EnvelopeCryptoService(LocalKeyProvider(settings.master_key))


@pytest.fixture
def usuario(db_session: Session) -> UserModel:
    user = UserModel(
        id="u1", email=EMAIL, full_name="Ana Souza",
        password_hash=Argon2PasswordHasher().hash(SENHA), is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def conceder(
    db: Session,
    user: UserModel,
    caminho: str,
    capacidades: list[str],
    efeito: str = "allow",
    nome_politica: str = "politica-teste",
) -> None:
    """Dá ao usuário um papel com uma política. Usado pelos testes de RBAC."""
    politica = PolicyModel(name=nome_politica, description="")
    politica.rules = [
        PolicyRuleModel(path=caminho, capabilities=capacidades, effect=efeito)
    ]
    papel = RoleModel(name=f"papel-{nome_politica}")
    papel.policies.append(politica)
    user.roles.append(papel)
    db.add_all([politica, papel])
    db.commit()


@pytest.fixture
def autenticado(client, usuario: UserModel) -> dict[str, str]:
    """Cabeçalho Authorization de um usuário logado."""
    resposta = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA}
    )
    assert resposta.status_code == 200, resposta.text
    token = resposta.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
