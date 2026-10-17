"""Testes de criptografia.

O que precisa ficar provado:
1. O ciclo cifra→decifra devolve o valor original.
2. O texto cifrado NÃO contém o valor em claro (vazamento por descuido).
3. Adulterar qualquer parte faz a decifragem FALHAR, não devolver lixo.
4. Cifrar o mesmo valor duas vezes dá resultados diferentes (sem ECB-like).
"""

import dataclasses

import pytest

from app.domain.shared.errors import ValidationError
from app.infrastructure.crypto.envelope import (
    EnvelopeCryptoService,
    LocalKeyProvider,
)
from app.infrastructure.crypto.passwords import Argon2PasswordHasher

SEGREDO = "senha-do-root-producao-2026"


@pytest.fixture
def cripto() -> EnvelopeCryptoService:
    return EnvelopeCryptoService(LocalKeyProvider.generate())


class TestRoundTrip:
    def test_cifra_e_decifra_devolve_o_original(self, cripto: EnvelopeCryptoService) -> None:
        assert cripto.decrypt(cripto.encrypt(SEGREDO)) == SEGREDO

    def test_valor_com_acento_e_simbolo_sobrevive(self, cripto: EnvelopeCryptoService) -> None:
        valor = "Ação&Çedilha—ümlaut•2026"
        assert cripto.decrypt(cripto.encrypt(valor)) == valor

    def test_valor_longo_sobrevive(self, cripto: EnvelopeCryptoService) -> None:
        valor = "x" * 10_000
        assert cripto.decrypt(cripto.encrypt(valor)) == valor

    def test_valor_vazio_e_recusado(self, cripto: EnvelopeCryptoService) -> None:
        with pytest.raises(ValidationError):
            cripto.encrypt("")


class TestNoPlaintextLeak:
    def test_texto_cifrado_nao_contem_o_valor(self, cripto: EnvelopeCryptoService) -> None:
        """Se isto falhar, o segredo está legível no banco."""
        cifrado = cripto.encrypt(SEGREDO)
        assert SEGREDO.encode("utf-8") not in cifrado.ciphertext
        assert SEGREDO.encode("utf-8") not in cifrado.wrapped_dek

    def test_cifrar_duas_vezes_da_resultados_diferentes(
        self, cripto: EnvelopeCryptoService
    ) -> None:
        """Nonce novo a cada cifragem: senhas iguais não viram cifras iguais."""
        a, b = cripto.encrypt(SEGREDO), cripto.encrypt(SEGREDO)
        assert a.ciphertext != b.ciphertext
        assert a.nonce != b.nonce
        assert cripto.decrypt(a) == cripto.decrypt(b) == SEGREDO

    def test_cada_segredo_recebe_uma_dek_propria(self, cripto: EnvelopeCryptoService) -> None:
        a, b = cripto.encrypt(SEGREDO), cripto.encrypt(SEGREDO)
        assert a.wrapped_dek != b.wrapped_dek


class TestTamperDetection:
    """GCM é autenticado: adulteração deve FALHAR, nunca devolver lixo."""

    def test_adulterar_o_texto_cifrado_falha(self, cripto: EnvelopeCryptoService) -> None:
        cifrado = cripto.encrypt(SEGREDO)
        corrompido = bytearray(cifrado.ciphertext)
        corrompido[0] ^= 0xFF
        alvo = dataclasses.replace(cifrado, ciphertext=bytes(corrompido))
        with pytest.raises(ValidationError, match="adulterado"):
            cripto.decrypt(alvo)

    def test_adulterar_o_nonce_falha(self, cripto: EnvelopeCryptoService) -> None:
        cifrado = cripto.encrypt(SEGREDO)
        trocado = bytes(12) if cifrado.nonce != bytes(12) else b"\x01" * 12
        with pytest.raises(ValidationError):
            cripto.decrypt(dataclasses.replace(cifrado, nonce=trocado))

    def test_adulterar_a_dek_protegida_falha(self, cripto: EnvelopeCryptoService) -> None:
        cifrado = cripto.encrypt(SEGREDO)
        corrompido = bytearray(cifrado.wrapped_dek)
        corrompido[-1] ^= 0xFF
        alvo = dataclasses.replace(cifrado, wrapped_dek=bytes(corrompido))
        with pytest.raises(ValidationError):
            cripto.decrypt(alvo)

    def test_chave_mestra_errada_falha(self) -> None:
        """Um cofre não abre com a chave de outro."""
        cifrado = EnvelopeCryptoService(LocalKeyProvider.generate()).encrypt(SEGREDO)
        outro = EnvelopeCryptoService(LocalKeyProvider.generate())
        with pytest.raises(ValidationError):
            outro.decrypt(cifrado)

    def test_trocar_dek_entre_segredos_falha(self, cripto: EnvelopeCryptoService) -> None:
        """Pegar a DEK de um segredo e usá-la noutro não abre nada."""
        a, b = cripto.encrypt("segredo-a"), cripto.encrypt("segredo-b")
        hibrido = dataclasses.replace(a, wrapped_dek=b.wrapped_dek)
        with pytest.raises(ValidationError):
            cripto.decrypt(hibrido)


class TestKeyProvider:
    def test_chave_mestra_com_tamanho_errado_e_recusada(self) -> None:
        with pytest.raises(ValidationError):
            LocalKeyProvider(b"curta-demais")

    def test_dek_protegida_malformada_e_recusada(self) -> None:
        with pytest.raises(ValidationError):
            LocalKeyProvider.generate().unwrap(b"curto")

    def test_wrap_e_unwrap_sao_inversos(self) -> None:
        provedor = LocalKeyProvider.generate()
        dek = b"k" * 32
        assert provedor.unwrap(provedor.wrap(dek)) == dek

    def test_wrap_do_mesmo_dek_varia(self) -> None:
        provedor = LocalKeyProvider.generate()
        dek = b"k" * 32
        assert provedor.wrap(dek) != provedor.wrap(dek)


class TestPasswordHasher:
    def test_senha_correta_verifica(self) -> None:
        h = Argon2PasswordHasher()
        assert h.verify("minha-senha-forte", h.hash("minha-senha-forte"))

    def test_senha_errada_nao_verifica(self) -> None:
        h = Argon2PasswordHasher()
        assert not h.verify("errada", h.hash("minha-senha-forte"))

    def test_hash_nao_contem_a_senha(self) -> None:
        h = Argon2PasswordHasher()
        assert "minha-senha-forte" not in h.hash("minha-senha-forte")

    def test_hashes_da_mesma_senha_diferem(self) -> None:
        """Salt por hash: duas contas com a mesma senha não se denunciam."""
        h = Argon2PasswordHasher()
        assert h.hash("igual") != h.hash("igual")

    def test_hash_corrompido_nao_levanta(self) -> None:
        """Registro corrompido vira 'senha errada', não erro 500."""
        assert not Argon2PasswordHasher().verify("x", "nao-e-um-hash-argon2")

    def test_hash_corrompido_pede_rehash(self) -> None:
        assert Argon2PasswordHasher().needs_rehash("nao-e-um-hash")
