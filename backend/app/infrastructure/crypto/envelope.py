"""Envelope encryption com AES-256-GCM.

Cada segredo recebe uma DEK (chave de dados) nova, usada uma única vez. A DEK
é protegida pela KEK (chave-mestra) e guardada junto do texto cifrado. A KEK
nunca cifra dado diretamente — assim ela pode ser rotacionada reescrevendo
apenas as DEKs, não todos os segredos.

GCM é autenticado: adulterar o texto cifrado faz a decifragem FALHAR, em vez
de devolver lixo silenciosamente. É o que impede que um byte trocado no banco
vire uma senha diferente e plausível.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...application.ports.keys import KeyProvider
from ...domain.shared.errors import ValidationError
from ...domain.vaults.entities import EncryptedValue

NONCE_BYTES = 12   # tamanho padrão do GCM; não alterar sem migrar os dados
DEK_BYTES = 32     # AES-256


class LocalKeyProvider:
    """Chave-mestra em memória, para desenvolvimento e testes.

    NÃO use em produção: a KEK fica no processo. Em produção o provedor é o
    KMS, que nunca entrega a chave-mestra — ele embrulha e desembrulha a DEK
    do lado dele. A interface é a mesma, por isso a troca não toca no resto.
    """

    def __init__(self, master_key: bytes, key_id: str = "local-dev") -> None:
        if len(master_key) != DEK_BYTES:
            raise ValidationError("A chave-mestra deve ter 32 bytes.")
        self._master_key = master_key
        self.key_id = key_id

    @classmethod
    def generate(cls, key_id: str = "local-dev") -> LocalKeyProvider:
        return cls(AESGCM.generate_key(bit_length=256), key_id=key_id)

    def wrap(self, dek: bytes) -> bytes:
        """Protege a DEK com a KEK. O nonce vai junto, no início."""
        nonce = os.urandom(NONCE_BYTES)
        wrapped = AESGCM(self._master_key).encrypt(nonce, dek, None)
        return nonce + wrapped

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        if len(wrapped_dek) <= NONCE_BYTES:
            raise ValidationError("Chave de dados protegida malformada.")
        nonce, payload = wrapped_dek[:NONCE_BYTES], wrapped_dek[NONCE_BYTES:]
        try:
            return AESGCM(self._master_key).decrypt(nonce, payload, None)
        except InvalidTag as exc:
            raise ValidationError(
                "A chave de dados não pôde ser desprotegida: "
                "chave-mestra errada ou dado adulterado."
            ) from exc


class EnvelopeCryptoService:
    """Implementa a porta CryptoService sobre um provedor de chave-mestra.

    Aceita qualquer `KeyProvider`: a chave local de desenvolvimento ou o KMS.
    O tipo é a porta, não a implementação — senão trocar de provedor exigiria
    mexer aqui, que é exatamente o que a porta existe para evitar.
    """

    def __init__(self, key_provider: KeyProvider) -> None:
        self._keys = key_provider

    def encrypt(self, plaintext: str) -> EncryptedValue:
        if not plaintext:
            raise ValidationError("Não há valor para cifrar.")

        # O KMS gera a DEK já protegida numa única chamada; gerar local e
        # embrulhar depois custaria duas idas à rede por segredo criado.
        gerar = getattr(self._keys, "generate_dek", None)
        if gerar is not None:
            dek, wrapped_dek = gerar()
        else:
            dek = AESGCM.generate_key(bit_length=256)
            wrapped_dek = self._keys.wrap(dek)

        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), None)
        return EncryptedValue(
            ciphertext=ciphertext,
            nonce=nonce,
            wrapped_dek=wrapped_dek,
            key_id=self._keys.key_id,
        )

    def decrypt(self, value: EncryptedValue) -> str:
        dek = self._keys.unwrap(value.wrapped_dek)
        try:
            plaintext = AESGCM(dek).decrypt(value.nonce, value.ciphertext, None)
        except InvalidTag as exc:
            raise ValidationError(
                "O segredo não pôde ser decifrado: o dado foi adulterado."
            ) from exc
        return plaintext.decode("utf-8")
