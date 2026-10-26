"""Provas do `ArmazenamentoS3` contra S3 de verdade.

**Por que este arquivo existe, tendo os testes com cliente falso.** O falso
prova que o adaptador chama o que deve chamar; não prova que o S3 responde
como o adaptador supõe. Três coisas só aparecem contra o serviço real:

1. `IfNoneMatch="*"` de fato recusa a sobrescrita — e com qual código de erro,
   que é o que o `except` precisa reconhecer;
2. `get_object_lock_configuration` devolve a estrutura que `_conferir_object_lock`
   navega;
3. o Object Lock em COMPLIANCE recusa o `DELETE` da versão. Essa é a
   garantia inteira do armazenamento: se ela não vale, `imutavel = True` é
   uma frase bonita e nada mais.

Os testes são ignorados sem `VAULT_TEST_S3_ENDPOINT`. Para rodar:

    docker run -d --name vault_localstack -p 4566:4566 \
        -e SERVICES=s3,kms localstack/localstack:3
    VAULT_TEST_S3_ENDPOINT=http://localhost:4566 pytest tests/integration/test_s3_localstack.py
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from app.domain.shared.errors import ValidationError
from app.infrastructure.sessions.adapters import ArmazenamentoS3, serializar

ENDPOINT = os.getenv("VAULT_TEST_S3_ENDPOINT")

pytestmark = pytest.mark.skipif(
    not ENDPOINT,
    reason="Defina VAULT_TEST_S3_ENDPOINT (ex.: LocalStack em http://localhost:4566).",
)

BUCKET_COM_LOCK = "vault-teste-com-lock"
BUCKET_SEM_LOCK = "vault-teste-sem-lock"


@pytest.fixture(scope="module")
def s3() -> Any:
    boto3 = pytest.importorskip("boto3", reason="extra `kms` não instalado")
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture(scope="module")
def buckets(s3: Any) -> Iterator[None]:
    """Cria os dois buckets: um com Object Lock em COMPLIANCE, outro sem.

    O par é o ponto: é comparando os dois que se prova que `imutavel` olha o
    bucket em vez de responder `True` por otimismo.
    """
    from botocore.exceptions import ClientError

    def criar(nome: str, com_lock: bool) -> None:
        try:
            if com_lock:
                s3.create_bucket(Bucket=nome, ObjectLockEnabledForBucket=True)
            else:
                s3.create_bucket(Bucket=nome)
        except ClientError as erro:
            if erro.response["Error"]["Code"] not in (
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            ):
                raise
        if com_lock:
            s3.put_object_lock_configuration(
                Bucket=nome,
                ObjectLockConfiguration={
                    "ObjectLockEnabled": "Enabled",
                    "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 1}},
                },
            )

    criar(BUCKET_COM_LOCK, True)
    criar(BUCKET_SEM_LOCK, False)
    yield


@pytest.fixture
def armazem(s3: Any, buckets: None) -> ArmazenamentoS3:
    return ArmazenamentoS3(BUCKET_COM_LOCK, client=s3)


def _sessao_id() -> str:
    # Id novo por teste: o Object Lock impede limpar o que foi gravado, então
    # reusar o id faria o segundo teste colidir com o primeiro.
    return f"t-{uuid.uuid4().hex[:12]}"


class TestImutabilidadeReal:
    def test_bucket_com_compliance_e_imutavel(self, armazem: ArmazenamentoS3) -> None:
        assert armazem.imutavel is True

    def test_bucket_sem_object_lock_nao_e_imutavel(
        self, s3: Any, buckets: None
    ) -> None:
        """A prova de que `imutavel` olha o bucket, e não devolve True fixo."""
        assert ArmazenamentoS3(BUCKET_SEM_LOCK, client=s3).imutavel is False

    def test_object_lock_recusa_apagar_a_versao(
        self, s3: Any, armazem: ArmazenamentoS3
    ) -> None:
        """A garantia inteira do armazenamento, verificada no serviço.

        Sem isto, tudo o mais é promessa: um bucket que aceita DELETE guarda
        gravação que pode desaparecer, e gravação que desaparece não é prova.
        """
        from botocore.exceptions import ClientError

        referencia = armazem.guardar(_sessao_id(), b'[0,"o","x"]')
        versao = s3.head_object(Bucket=BUCKET_COM_LOCK, Key=referencia)["VersionId"]

        with pytest.raises(ClientError) as erro:
            s3.delete_object(
                Bucket=BUCKET_COM_LOCK, Key=referencia, VersionId=versao
            )
        assert erro.value.response["Error"]["Code"] in ("AccessDenied", "InvalidRequest")

        # E segue legível depois da tentativa.
        assert armazem.ler(referencia) == b'[0,"o","x"]'

    def test_verificar_bucket_acusa_a_falta_do_lock(
        self, s3: Any, buckets: None
    ) -> None:
        problemas = ArmazenamentoS3(BUCKET_SEM_LOCK, client=s3).verificar_bucket()
        assert any("não servem como prova" in p for p in problemas)

    def test_verificar_bucket_nao_acha_problema_no_correto(
        self, armazem: ArmazenamentoS3
    ) -> None:
        assert armazem.verificar_bucket() == []


class TestGravacaoReal:
    def test_guardar_e_ler_fecham_com_gravacao_de_verdade(
        self, armazem: ArmazenamentoS3
    ) -> None:
        conteudo = serializar(
            [(0, "o", "$ "), (1200, "i", "whoami\n"), (1250, "o", "root\n")]
        )
        referencia = armazem.guardar(_sessao_id(), conteudo)
        assert armazem.ler(referencia) == conteudo

    def test_sobrescrita_recusada_pelo_servico(self, armazem: ArmazenamentoS3) -> None:
        """`IfNoneMatch` contra o S3 real — e o código de erro que ele devolve.

        É o teste que o cliente falso não pode dar: o falso devolve o erro que
        eu mandei ele devolver.
        """
        sessao = _sessao_id()
        armazem.guardar(sessao, b"primeira")
        with pytest.raises(ValidationError, match="é prova"):
            armazem.guardar(sessao, b"segunda")

    def test_a_primeira_gravacao_sobrevive_a_tentativa(
        self, armazem: ArmazenamentoS3
    ) -> None:
        sessao = _sessao_id()
        referencia = armazem.guardar(sessao, b"primeira")
        with pytest.raises(ValidationError):
            armazem.guardar(sessao, b"segunda")
        assert armazem.ler(referencia) == b"primeira"

    def test_ler_inexistente_levanta_validacao(
        self, armazem: ArmazenamentoS3
    ) -> None:
        with pytest.raises(ValidationError, match="não encontrada"):
            armazem.ler("sessoes/nao-existe-mesmo.jsonl")


class TestKmsReal:
    """O `KmsKeyProvider` contra um KMS de verdade.

    O cliente falso não prova que o `CiphertextBlob` real desembrulha, nem que
    o alias resolve: ele devolve o que foi programado para devolver.
    """

    @pytest.fixture
    def kms(self) -> Any:
        boto3 = pytest.importorskip("boto3", reason="extra `kms` não instalado")
        cliente = boto3.client(
            "kms",
            endpoint_url=ENDPOINT,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        alias = "alias/vault-teste-kek"
        try:
            cliente.describe_key(KeyId=alias)
        except Exception:  # noqa: BLE001 — primeira execução: a chave não existe
            chave = cliente.create_key(Description="KEK de teste")
            cliente.create_alias(
                AliasName=alias, TargetKeyId=chave["KeyMetadata"]["KeyId"]
            )
        return cliente

    def test_ciclo_completo_no_kms(self, kms: Any) -> None:
        from app.infrastructure.crypto.kms import KmsKeyProvider

        provedor = KmsKeyProvider("alias/vault-teste-kek", client=kms)
        dek, protegida = provedor.generate_dek()

        assert len(dek) == 32
        # A DEK em claro não pode aparecer no blob protegido — se aparecesse,
        # o banco guardaria a chave ao lado do que ela cifra.
        assert dek not in protegida
        assert provedor.unwrap(protegida) == dek

    def test_envelope_inteiro_sobre_o_kms(self, kms: Any) -> None:
        from app.infrastructure.crypto.envelope import EnvelopeCryptoService
        from app.infrastructure.crypto.kms import KmsKeyProvider

        servico = EnvelopeCryptoService(
            KmsKeyProvider("alias/vault-teste-kek", client=kms)
        )
        segredo = "senha-do-servidor-de-producao-123!@#"
        cifrado = servico.encrypt(segredo)

        assert segredo.encode() not in cifrado.ciphertext
        assert servico.decrypt(cifrado) == segredo

    def test_blob_adulterado_e_recusado(self, kms: Any) -> None:
        """Recusa, em vez de devolver lixo que viraria "senha" na tela."""
        from app.infrastructure.crypto.kms import KmsKeyProvider

        provedor = KmsKeyProvider("alias/vault-teste-kek", client=kms)
        _, protegida = provedor.generate_dek()
        adulterado = bytearray(protegida)
        adulterado[-1] ^= 0xFF

        with pytest.raises(ValidationError, match="não pôde ser desprotegida"):
            provedor.unwrap(bytes(adulterado))
