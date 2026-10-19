"""Testes do provedor de chave-mestra apoiado no KMS.

Usam um KMS simulado — o objetivo não é testar a AWS, é fixar o **contrato**
que o adaptador assume sobre ela. Dois pontos valem mais que os outros:

- `unwrap` **não** envia KeyId. O blob do KMS já identifica a chave que o
  produziu; forçar um KeyId faria a decifragem falhar depois de uma rotação,
  justamente quando ela precisa funcionar.
- `encrypt` usa `generate_data_key`, que devolve a DEK em claro e protegida
  numa só chamada. Gerar local e embrulhar depois dobraria as idas à rede em
  cada segredo criado.
"""

from __future__ import annotations

import os

import pytest

from app.application.ports.keys import KeyProvider
from app.domain.shared.errors import ValidationError
from app.infrastructure.crypto.envelope import EnvelopeCryptoService, LocalKeyProvider
from app.infrastructure.crypto.kms import KmsKeyProvider


class KmsFalso:
    """KMS simulado: 'embrulha' com XOR e registra o que foi chamado.

    O XOR não é criptografia — é só reversível o bastante para o teste. O que
    importa aqui é o protocolo das chamadas, não a força do algoritmo.
    """

    def __init__(self, material: bytes = b"\x5a" * 32) -> None:
        self.material = material
        self.chamadas: list[tuple[str, dict]] = []
        self.falhar_decrypt = False

    def _xor(self, dados: bytes) -> bytes:
        return bytes(b ^ self.material[i % len(self.material)] for i, b in enumerate(dados))

    def generate_data_key(self, **kwargs) -> dict:  # noqa: ANN003
        self.chamadas.append(("generate_data_key", kwargs))
        dek = os.urandom(kwargs.get("NumberOfBytes", 32))
        return {"Plaintext": dek, "CiphertextBlob": self._xor(dek)}

    def encrypt(self, **kwargs) -> dict:  # noqa: ANN003
        self.chamadas.append(("encrypt", kwargs))
        return {"CiphertextBlob": self._xor(kwargs["Plaintext"])}

    def decrypt(self, **kwargs) -> dict:  # noqa: ANN003
        self.chamadas.append(("decrypt", kwargs))
        if self.falhar_decrypt:
            raise RuntimeError("AccessDeniedException")
        return {"Plaintext": self._xor(kwargs["CiphertextBlob"])}


class TestContratoComOKms:
    def test_satisfaz_a_porta(self) -> None:
        assert isinstance(KmsKeyProvider("alias/vault", client=KmsFalso()), KeyProvider)

    def test_wrap_e_unwrap_sao_simetricos(self) -> None:
        provedor = KmsKeyProvider("alias/vault", client=KmsFalso())
        dek = os.urandom(32)
        assert provedor.unwrap(provedor.wrap(dek)) == dek

    def test_unwrap_nao_envia_key_id(self) -> None:
        """Forçar KeyId quebraria a decifragem depois de uma rotação de KEK."""
        kms = KmsFalso()
        provedor = KmsKeyProvider("alias/vault", client=kms)
        provedor.unwrap(provedor.wrap(os.urandom(32)))

        decrypts = [args for nome, args in kms.chamadas if nome == "decrypt"]
        assert len(decrypts) == 1
        assert "KeyId" not in decrypts[0]

    def test_wrap_envia_o_key_id(self) -> None:
        """Ao proteger, a chave é escolhida por nós — e é o alias corrente."""
        kms = KmsFalso()
        KmsKeyProvider("alias/vault-prod", client=kms).wrap(os.urandom(32))

        encrypts = [args for nome, args in kms.chamadas if nome == "encrypt"]
        assert encrypts[0]["KeyId"] == "alias/vault-prod"

    def test_generate_dek_devolve_o_par(self) -> None:
        kms = KmsFalso()
        provedor = KmsKeyProvider("alias/vault", client=kms)
        dek, protegida = provedor.generate_dek()

        assert len(dek) == 32
        assert dek != protegida
        assert provedor.unwrap(protegida) == dek

    def test_generate_dek_pede_256_bits(self) -> None:
        kms = KmsFalso()
        KmsKeyProvider("alias/vault", client=kms).generate_dek()
        _, args = kms.chamadas[0]
        assert args["NumberOfBytes"] == 32

    def test_falha_do_kms_vira_erro_de_dominio(self) -> None:
        """A aplicação não deve vazar ClientError da AWS para cima."""
        kms = KmsFalso()
        provedor = KmsKeyProvider("alias/vault", client=kms)
        protegida = provedor.wrap(os.urandom(32))

        kms.falhar_decrypt = True
        with pytest.raises(ValidationError, match="KMS"):
            provedor.unwrap(protegida)

    def test_key_id_vazio_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            KmsKeyProvider("   ", client=KmsFalso())


class TestEnvelopeComKms:
    def test_cifra_e_decifra_pelo_kms(self) -> None:
        servico = EnvelopeCryptoService(
            KmsKeyProvider("alias/vault", client=KmsFalso())
        )
        cifrado = servico.encrypt("senha-do-roteador-2026")
        assert servico.decrypt(cifrado) == "senha-do-roteador-2026"

    def test_valor_em_claro_nao_sobra_no_cifrado(self) -> None:
        servico = EnvelopeCryptoService(
            KmsKeyProvider("alias/vault", client=KmsFalso())
        )
        cifrado = servico.encrypt("senha-do-roteador-2026")
        assert b"senha" not in cifrado.ciphertext
        assert b"senha" not in cifrado.wrapped_dek

    def test_usa_generate_data_key_e_nao_duas_chamadas(self) -> None:
        """Gerar local e embrulhar depois dobraria a latência por segredo."""
        kms = KmsFalso()
        servico = EnvelopeCryptoService(KmsKeyProvider("alias/vault", client=kms))
        servico.encrypt("segredo")

        nomes = [nome for nome, _ in kms.chamadas]
        assert nomes == ["generate_data_key"]

    def test_key_id_fica_gravado_no_segredo(self) -> None:
        """Sem ele, a rotação de KEK não saberia o que reembrulhar."""
        servico = EnvelopeCryptoService(
            KmsKeyProvider("arn:aws:kms:sa-east-1:123:key/abc", client=KmsFalso())
        )
        assert servico.encrypt("x").key_id == "arn:aws:kms:sa-east-1:123:key/abc"

    def test_cada_segredo_recebe_dek_propria(self) -> None:
        """DEK reutilizada tornaria um vazamento em muitos."""
        servico = EnvelopeCryptoService(
            KmsKeyProvider("alias/vault", client=KmsFalso())
        )
        a = servico.encrypt("mesmo-valor")
        b = servico.encrypt("mesmo-valor")
        assert a.wrapped_dek != b.wrapped_dek
        assert a.ciphertext != b.ciphertext


class TestRotacaoDeKek:
    def test_dek_reembrulhada_decifra_o_mesmo_texto(self) -> None:
        """A razão de existir do envelope.

        Rotacionar a KEK reescreve apenas as DEKs; o texto cifrado de cada
        segredo fica intacto. Sem envelope, trocar a chave-mestra exigiria
        decifrar e recifrar todos os segredos — caro e arriscado.
        """
        antiga = LocalKeyProvider.generate(key_id="kek-2025")
        nova = LocalKeyProvider.generate(key_id="kek-2026")

        servico_antigo = EnvelopeCryptoService(antiga)
        cifrado = servico_antigo.encrypt("senha-que-nao-muda")

        # Rotação: desembrulha com a antiga, reembrulha com a nova.
        dek = antiga.unwrap(cifrado.wrapped_dek)
        from dataclasses import replace

        rotacionado = replace(
            cifrado, wrapped_dek=nova.wrap(dek), key_id=nova.key_id
        )

        # O texto cifrado é o MESMO — não foi reescrito.
        assert rotacionado.ciphertext == cifrado.ciphertext
        # E continua legível, agora pela chave nova.
        assert EnvelopeCryptoService(nova).decrypt(rotacionado) == "senha-que-nao-muda"

    def test_chave_errada_nao_decifra(self) -> None:
        outra = LocalKeyProvider.generate(key_id="outra")
        cifrado = EnvelopeCryptoService(LocalKeyProvider.generate()).encrypt("x")

        with pytest.raises(ValidationError):
            EnvelopeCryptoService(outra).decrypt(cifrado)


class TestSelecaoDoProvedor:
    """Qual provedor a configuração escolhe, e o que ela recusa."""

    def _settings(self, **kwargs):  # noqa: ANN003, ANN202
        from app.config import Settings

        base = {
            "master_key_b64": "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=",  # 32 bytes
            "jwt_secret": "segredo-de-teste-com-mais-de-trinta-e-dois-bytes",
        }
        return Settings(**{**base, **kwargs})

    def test_sem_kms_usa_a_chave_local(self) -> None:
        s = self._settings(environment="development")
        assert s.usa_kms is False

    def test_com_kms_key_id_usa_o_kms(self) -> None:
        s = self._settings(environment="development", kms_key_id="alias/vault")
        assert s.usa_kms is True

    def test_producao_sem_kms_nao_sobe(self) -> None:
        """Configuração que funciona com a chave errada é pior que uma que
        falha ao subir: o erro só apareceria no vazamento."""
        with pytest.raises(ValueError, match="VAULT_KMS_KEY_ID"):
            self._settings(environment="production")

    def test_producao_com_kms_sobe(self) -> None:
        s = self._settings(environment="production", kms_key_id="alias/vault-prod")
        assert s.usa_kms is True

    def test_espaco_em_branco_nao_conta_como_kms(self) -> None:
        """'   ' passaria num `if` ingênuo e deixaria produção sem KMS."""
        with pytest.raises(ValueError, match="VAULT_KMS_KEY_ID"):
            self._settings(environment="production", kms_key_id="   ")


class TestIdentificadorDaChave:
    """Regressão de um bug real encontrado rotacionando no ambiente.

    O identificador era derivado do NOME (`local-dev` -> `local-dev-2`), então
    rotacionar de volta para a chave anterior produzia de novo `local-dev-2`.
    A checagem de "já rotacionado" então PULAVA registros que estavam
    protegidos por outra chave — e eles ficariam ilegíveis depois da troca.

    Derivar do material torna a afirmação verdadeira: mesmo identificador
    significa mesma chave.
    """

    def test_chaves_diferentes_tem_ids_diferentes(self) -> None:
        from app.tools.rotacionar_kek import _id_da_chave

        assert _id_da_chave(b"a" * 32) != _id_da_chave(b"b" * 32)

    def test_a_mesma_chave_tem_sempre_o_mesmo_id(self) -> None:
        """Sem isto, retomar uma rotação interrompida refaria tudo."""
        from app.tools.rotacionar_kek import _id_da_chave

        assert _id_da_chave(b"k" * 32) == _id_da_chave(b"k" * 32)

    def test_ida_e_volta_nao_colide(self) -> None:
        """O cenário exato do bug: A -> B -> A."""
        from app.tools.rotacionar_kek import _id_da_chave

        a, b = b"chave-a" + b"\x00" * 25, b"chave-b" + b"\x00" * 25
        ids = [_id_da_chave(a), _id_da_chave(b), _id_da_chave(a)]
        assert ids[0] == ids[2]  # voltar para A recupera o id de A
        assert ids[0] != ids[1]  # e A nunca se confunde com B

    def test_id_nao_revela_a_chave(self) -> None:
        """É identificador, não segredo — mas também não vaza material."""
        from app.tools.rotacionar_kek import _id_da_chave

        material = b"material-super-secreto-de-32-byt"
        identificador = _id_da_chave(material)
        assert material.hex() not in identificador
        assert len(identificador) < 30
