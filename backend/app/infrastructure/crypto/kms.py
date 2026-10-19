"""Provedor de chave-mestra apoiado no AWS KMS.

A chave-mestra **nunca entra neste processo**. O KMS embrulha e desembrulha a
DEK do lado dele, e o que trafega é só a DEK protegida. Três consequências
práticas que justificam a complexidade:

1. Um dump do banco, sozinho, não decifra nada — falta a KEK, que não está
   em lugar nenhum da aplicação.
2. Toda desproteção de DEK vira uma linha no CloudTrail. Dá para detectar
   leitura em massa, que é o sinal de um cofre sendo drenado.
3. Revogar o acesso é mudar a política do KMS, sem tocar nos dados cifrados.

O custo é latência e dependência de rede: cada revelação de segredo vira uma
chamada à AWS. Por isso `encrypt` usa `generate_data_key`, que devolve a DEK
em claro e protegida numa só chamada, em vez de gerar local e embrulhar
depois — metade das idas à rede.

boto3 é importado dentro dos métodos de propósito: quem roda local não precisa
ter a dependência instalada.
"""

from __future__ import annotations

from typing import Any

from ...domain.shared.errors import ValidationError

DEK_BITS = 256


class KmsKeyProvider:
    """Embrulha e desembrulha DEKs no AWS KMS.

    `key_id` é o ARN ou alias da KEK. Guardá-lo junto de cada segredo é o que
    torna a rotação possível: o KMS resolve o alias para a versão corrente ao
    cifrar, mas ao decifrar usa o material que de fato embrulhou aquela DEK.
    """

    def __init__(
        self,
        key_id: str,
        *,
        region: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not key_id.strip():
            raise ValidationError("O identificador da chave do KMS é obrigatório.")
        self._key_id = key_id
        self._region = region
        # Injetável para teste; em produção é criado na primeira chamada.
        self._client = client

    @property
    def key_id(self) -> str:
        return self._key_id

    def _kms(self) -> Any:
        if self._client is None:
            import boto3  # import tardio: só quem usa KMS precisa da dependência

            self._client = boto3.client("kms", region_name=self._region)
        return self._client

    def generate_dek(self) -> tuple[bytes, bytes]:
        """Gera uma DEK já protegida, numa única chamada.

        Devolve (dek_em_claro, dek_protegida). A DEK em claro cifra o segredo
        aqui no processo e deve ser descartada logo depois; só a protegida é
        persistida.
        """
        resposta = self._kms().generate_data_key(
            KeyId=self._key_id, NumberOfBytes=DEK_BITS // 8
        )
        return resposta["Plaintext"], resposta["CiphertextBlob"]

    def wrap(self, dek: bytes) -> bytes:
        """Protege uma DEK já existente.

        Usado na rotação de KEK e por quem gerou a DEK localmente. No caminho
        normal, `generate_dek` é preferível: faz as duas coisas numa chamada.
        """
        resposta = self._kms().encrypt(KeyId=self._key_id, Plaintext=dek)
        return resposta["CiphertextBlob"]

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        """Desembrulha a DEK no KMS.

        Não passa `KeyId`: o blob do KMS já identifica a chave que o produziu,
        e forçar um KeyId faria a decifragem falhar depois de uma rotação —
        justamente quando ela precisa funcionar.
        """
        try:
            resposta = self._kms().decrypt(CiphertextBlob=wrapped_dek)
        except Exception as exc:  # noqa: BLE001 — boto3 levanta ClientError
            raise ValidationError(
                "A chave de dados não pôde ser desprotegida pelo KMS: "
                "chave errada, sem permissão, ou dado adulterado."
            ) from exc
        return resposta["Plaintext"]
