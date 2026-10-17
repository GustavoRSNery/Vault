"""Porta de criptografia.

A aplicação nunca fala com o KMS diretamente: fala com esta interface. Em
produção o adaptador é o AWS KMS; em desenvolvimento, uma chave-mestra local.
Trocar um pelo outro não toca em nenhum caso de uso.
"""

from __future__ import annotations

from typing import Protocol

from ...domain.vaults.entities import EncryptedValue


class CryptoService(Protocol):
    """Cifra e decifra segredos usando envelope encryption.

    Envelope: cada segredo recebe sua própria chave de dados (DEK), e a DEK é
    protegida pela chave-mestra (KEK). Assim a chave-mestra nunca cifra dado
    diretamente e pode ser rotacionada sem reescrever todos os segredos.
    """

    def encrypt(self, plaintext: str) -> EncryptedValue:
        """Cifra um valor em claro. O retorno nunca contém o valor original."""
        ...

    def decrypt(self, value: EncryptedValue) -> str:
        """Decifra. Só a camada de aplicação chama, e sempre registra auditoria."""
        ...


class PasswordHasher(Protocol):
    """Hash de senha de usuário. Separado do CryptoService de propósito:
    senha de login se verifica, segredo de cofre se recupera."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, stored_hash: str) -> bool: ...

    def needs_rehash(self, stored_hash: str) -> bool: ...
