"""Testes de cofres e segredos.

O foco é a invariante do selo e a imutabilidade das versões: são elas que
impedem que um cofre fechado continue entregando segredo e que um histórico
seja reescrito.
"""

import pytest

from app.domain.shared.errors import ConflictError, SealedError, ValidationError
from app.domain.shared.value_objects import Slug
from app.domain.vaults.entities import (
    EncryptedValue,
    Secret,
    SecretKind,
    Vault,
    VaultState,
)


def _valor(texto: bytes = b"cifrado") -> EncryptedValue:
    return EncryptedValue(
        ciphertext=texto,
        nonce=b"x" * 12,
        wrapped_dek=b"dek-protegida",
        key_id="kms-key-1",
    )


def _cofre(nome: str = "contabil") -> Vault:
    return Vault(name=Slug(nome), display_name="Contábil")


class TestEncryptedValue:
    def test_nonce_com_tamanho_errado_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            EncryptedValue(ciphertext=b"c", nonce=b"curto", wrapped_dek=b"d", key_id="k")

    def test_ciphertext_vazio_e_recusado(self) -> None:
        with pytest.raises(ValidationError):
            EncryptedValue(ciphertext=b"", nonce=b"x" * 12, wrapped_dek=b"d", key_id="k")


class TestVaultSeal:
    def test_cofre_nasce_ativo(self) -> None:
        assert _cofre().state is VaultState.ACTIVE

    def test_cofre_selado_recusa_uso(self) -> None:
        cofre = _cofre()
        cofre.seal()
        with pytest.raises(SealedError):
            cofre.ensure_usable()

    def test_cofre_ativo_permite_uso(self) -> None:
        _cofre().ensure_usable()  # não levanta

    def test_desselar_devolve_o_uso(self) -> None:
        cofre = _cofre()
        cofre.seal()
        cofre.unseal()
        cofre.ensure_usable()

    def test_selar_duas_vezes_e_conflito(self) -> None:
        cofre = _cofre()
        cofre.seal()
        with pytest.raises(ConflictError):
            cofre.seal()

    def test_desselar_cofre_ativo_e_conflito(self) -> None:
        with pytest.raises(ConflictError):
            _cofre().unseal()

    def test_mensagem_do_selo_nomeia_o_cofre(self) -> None:
        cofre = _cofre()
        cofre.seal()
        with pytest.raises(SealedError, match="Contábil"):
            cofre.ensure_usable()


class TestVaultPaths:
    def test_caminho_do_cofre(self) -> None:
        assert str(_cofre().path) == "cofres/contabil"

    def test_caminho_do_segredo(self) -> None:
        caminho = _cofre().secret_path(Slug("senha-root"))
        assert str(caminho) == "cofres/contabil/segredos/senha-root"


class TestSecretVersioning:
    def test_primeira_versao_e_um(self) -> None:
        s = Secret(name=Slug("senha-root"), vault_id="v1", kind=SecretKind.PASSWORD)
        v = s.add_version(_valor(), created_by="u1")
        assert v.version == 1

    def test_versoes_incrementam(self) -> None:
        s = Secret(name=Slug("senha-root"), vault_id="v1")
        s.add_version(_valor(b"a"), created_by="u1")
        s.add_version(_valor(b"b"), created_by="u1")
        terceira = s.add_version(_valor(b"c"), created_by="u1")
        assert terceira.version == 3
        assert s.current_version.version == 3

    def test_versao_antiga_permanece_intacta(self) -> None:
        """O histórico não é reescrito: a v1 continua com o valor original."""
        s = Secret(name=Slug("senha-root"), vault_id="v1")
        s.add_version(_valor(b"original"), created_by="u1")
        s.add_version(_valor(b"nova"), created_by="u1")
        assert s.version_at(1).value.ciphertext == b"original"
        assert s.current_version.value.ciphertext == b"nova"

    def test_segredo_sem_versao_nao_tem_atual(self) -> None:
        s = Secret(name=Slug("vazio"), vault_id="v1")
        with pytest.raises(ConflictError):
            _ = s.current_version

    def test_versao_inexistente_e_conflito(self) -> None:
        s = Secret(name=Slug("senha-root"), vault_id="v1")
        s.add_version(_valor(), created_by="u1")
        with pytest.raises(ConflictError):
            s.version_at(99)


class TestSecretTrash:
    def test_lixeira_marca_sem_apagar_versoes(self) -> None:
        s = Secret(name=Slug("senha-root"), vault_id="v1")
        s.add_version(_valor(), created_by="u1")
        s.soft_delete()
        assert s.is_deleted
        assert len(s.versions) == 1  # recuperável

    def test_segredo_na_lixeira_recusa_nova_versao(self) -> None:
        s = Secret(name=Slug("senha-root"), vault_id="v1")
        s.add_version(_valor(), created_by="u1")
        s.soft_delete()
        with pytest.raises(ConflictError):
            s.add_version(_valor(b"nova"), created_by="u1")

    def test_restaurar_devolve_a_escrita(self) -> None:
        s = Secret(name=Slug("senha-root"), vault_id="v1")
        s.add_version(_valor(), created_by="u1")
        s.soft_delete()
        s.restore()
        assert not s.is_deleted
        s.add_version(_valor(b"nova"), created_by="u1")

    def test_restaurar_segredo_ativo_e_conflito(self) -> None:
        s = Secret(name=Slug("senha-root"), vault_id="v1")
        with pytest.raises(ConflictError):
            s.restore()
