"""Tradução de erro de domínio para resposta HTTP.

Um lugar só, porque o mapeamento carrega decisão de segurança: NotFound e
PermissionDenied respondem ambos 404 quando o recurso é um segredo, para que
a resposta não revele a existência de um cofre a quem não pode vê-lo.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from ..domain.shared.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    SealedError,
    ValidationError,
)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    ValidationError: 422,
    AuthenticationError: 401,
    PermissionDeniedError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    SealedError: 423,  # Locked: o recurso existe mas está fechado
}


def status_for(error: DomainError) -> int:
    for error_type, status in _STATUS_BY_ERROR.items():
        if isinstance(error, error_type):
            return status
    return 400


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Resposta uniforme: código estável para a máquina, mensagem para a pessoa."""
    assert isinstance(exc, DomainError)
    return JSONResponse(
        status_code=status_for(exc),
        content={"erro": {"codigo": exc.code, "mensagem": exc.message}},
    )


async def unexpected_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Erro não previsto: resposta genérica.

    Detalhe de exceção não sai para o cliente — num produto de segurança, um
    traceback vazado é mapa para o atacante. O log interno guarda o resto.
    """
    return JSONResponse(
        status_code=500,
        content={
            "erro": {
                "codigo": "erro_interno",
                "mensagem": "Não foi possível concluir a operação.",
            }
        },
    )
