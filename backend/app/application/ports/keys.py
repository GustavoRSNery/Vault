"""Porta do provedor de chave-mestra (KEK).

A diferença entre os dois provedores não é de implementação, é de **modelo de
ameaça**:

- `LocalKeyProvider` tem a KEK em memória. Quem lê o processo, lê a chave, e
  então decifra todo o cofre offline. Serve para desenvolvimento.
- `KmsKeyProvider` nunca vê a KEK. Ele manda a DEK para o KMS embrulhar e
  desembrulhar, e a chave-mestra jamais sai de lá. Quem compromete a aplicação
  consegue pedir ao KMS que desembrulhe — mas cada pedido fica no CloudTrail,
  o acesso pode ser revogado sem tocar nos dados, e um dump do banco sozinho
  não vale nada.

É por isso que `wrap`/`unwrap` é a fronteira, e não "me dê a chave": a segunda
forma não teria como ser implementada pelo KMS.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class KeyProvider(Protocol):
    """Protege e desprotege a chave de dados (DEK) de cada segredo."""

    @property
    def key_id(self) -> str:
        """Identifica a KEK usada.

        Fica gravado junto do segredo para que a rotação seja possível: com o
        `key_id` dá para saber qual material desembrulha qual DEK, e reembrulhar
        progressivamente sem reescrever o texto cifrado.
        """
        ...

    def wrap(self, dek: bytes) -> bytes:
        """Protege a DEK com a KEK."""
        ...

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        """Recupera a DEK. Levanta ValidationError se o material não confere."""
        ...
