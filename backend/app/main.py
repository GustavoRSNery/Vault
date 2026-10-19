"""Aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.errors import domain_error_handler, unexpected_error_handler
from .api.v1 import admin, audit, auth, inventory, mfa, vaults
from .config import get_settings
from .domain.shared.errors import DomainError


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Vault de Senhas",
        description="Cofre corporativo de senhas, segredos e credenciais.",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Erro de domínio vira resposta HTTP num lugar só; qualquer outra exceção
    # vira 500 genérico, sem traceback no corpo.
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(mfa.router, prefix="/api/v1")
    app.include_router(vaults.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(inventory.router, prefix="/api/v1")

    @app.get("/saude", tags=["Infraestrutura"], summary="Verificação de saúde")
    def saude() -> dict[str, str]:
        return {"status": "ok", "ambiente": settings.environment}

    return app


app = create_app()
