"""Erros de domínio.

Nenhum deles conhece HTTP: a camada de API mapeia cada tipo para um status.
Mensagens em português, voltadas ao usuário final, sem vazar detalhe interno.
"""


class DomainError(Exception):
    """Raiz de todo erro de regra de negócio."""

    code: str = "erro_de_dominio"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    """Dado de entrada viola uma invariante do domínio."""

    code = "validacao"


class NotFoundError(DomainError):
    """Recurso não existe, ou o solicitante não pode saber que existe."""

    code = "nao_encontrado"


class PermissionDeniedError(DomainError):
    """A política negou a operação."""

    code = "permissao_negada"


class ConflictError(DomainError):
    """Estado atual do recurso é incompatível com a operação."""

    code = "conflito"


class SealedError(DomainError):
    """O cofre está selado: nenhuma operação de leitura ou escrita de segredo."""

    code = "selado"

    def __init__(self, message: str = "O cofre está selado.") -> None:
        super().__init__(message)


class AuthenticationError(DomainError):
    """Credenciais inválidas ou sessão expirada."""

    code = "nao_autenticado"
