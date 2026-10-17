"""Hash de senha com Argon2id.

Argon2id resiste a ataque por GPU e por canal lateral — é a recomendação
atual da OWASP para senha de login. Os parâmetros abaixo são os padrões da
biblioteca, que já miram ~50ms por verificação em hardware de servidor.
"""

from __future__ import annotations

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


class Argon2PasswordHasher:
    """Implementa a porta PasswordHasher."""

    def __init__(self) -> None:
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, stored_hash: str) -> bool:
        """Devolve False em vez de levantar: quem chama trata como 'senha errada'.

        Hash malformado também vira False — um registro corrompido não deve
        virar exceção no meio do login e revelar detalhe interno ao atacante.
        """
        try:
            return self._hasher.verify(stored_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        """True quando os parâmetros mudaram: rehash no próximo login bem-sucedido."""
        try:
            return self._hasher.check_needs_rehash(stored_hash)
        except InvalidHashError:
            return True
