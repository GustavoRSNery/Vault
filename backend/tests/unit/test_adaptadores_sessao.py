"""Testes dos adaptadores de produção da gravação de sessão.

O que estes testes protegem, e que os e2e não alcançam: o `ProxySsh` e o
`ArmazenamentoS3` são construídos direto aqui, sem passar pela API. É onde
vivem as regras que importam — a fila por sessão, a recusa de sobrescrita, e
a conferência do Object Lock antes de afirmar imutabilidade.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.application.ports.sessions import ArmazenamentoDeGravacao, CapturaDeSessao
from app.domain.shared.errors import ValidationError
from app.infrastructure.sessions.adapters import ArmazenamentoS3, ProxySsh

# ----------------------------------------------------------------- ProxySsh


class TestProxySshContrato:
    def test_cumpre_a_porta_de_captura(self) -> None:
        assert isinstance(ProxySsh("proxy.local"), CapturaDeSessao)

    def test_declara_captura_automatica(self) -> None:
        """Ao contrário do manual: aqui o sistema observa, não anota."""
        assert ProxySsh("proxy.local").captura_automatica is True

    def test_nome_identifica_o_host(self) -> None:
        assert ProxySsh("bastion-01").nome == "proxy-ssh:bastion-01"

    def test_nome_sem_host_diz_que_falta_configurar(self) -> None:
        """Nome honesto: numa sessão gravada, 'nao-configurado' é pista."""
        assert ProxySsh().nome == "proxy-ssh:nao-configurado"


class TestProxySshFila:
    def test_abrir_exige_alvo(self) -> None:
        with pytest.raises(ValidationError, match="alvo"):
            ProxySsh("p").abrir("s1", "   ")

    def test_coletar_drena_a_fila(self) -> None:
        """Segunda coleta vem vazia: o que saiu não volta."""
        proxy = ProxySsh("p")
        proxy.abrir("s1", "servidor-01")
        proxy.registrar("s1", ProxySsh.ENTRADA, "ls -la\n")
        proxy.registrar("s1", ProxySsh.SAIDA, "total 0\n")

        primeira = proxy.coletar("s1")
        assert [e.conteudo for e in primeira] == ["ls -la\n", "total 0\n"]
        assert [e.tipo for e in primeira] == ["i", "o"]
        assert proxy.coletar("s1") == []

    def test_coletar_sessao_desconhecida_e_vazio(self) -> None:
        """Coleta é chamada em laço; não pode explodir por sessão já fechada."""
        assert ProxySsh("p").coletar("inexistente") == []

    def test_registrar_sem_sessao_aberta_levanta(self) -> None:
        """Evento sem sessão seria lacuna silenciosa na gravação.

        Este é o teste que impede alguém de "consertar" o registrar para
        descartar em silêncio: engolir o evento produziria buraco na linha do
        tempo sem nenhum aviso.
        """
        with pytest.raises(ValidationError, match="não está aberta"):
            ProxySsh("p").registrar("fantasma", ProxySsh.SAIDA, "x")

    def test_filas_nao_se_misturam_entre_sessoes(self) -> None:
        """Duas pessoas na mesma máquina são duas gravações distintas."""
        proxy = ProxySsh("p")
        proxy.abrir("s1", "servidor-01")
        proxy.abrir("s2", "servidor-01")
        proxy.registrar("s1", ProxySsh.ENTRADA, "da-s1")
        proxy.registrar("s2", ProxySsh.ENTRADA, "da-s2")

        assert [e.conteudo for e in proxy.coletar("s1")] == ["da-s1"]
        assert [e.conteudo for e in proxy.coletar("s2")] == ["da-s2"]

    def test_deslocamento_cresce_e_comeca_perto_de_zero(self) -> None:
        """A linha do tempo começa quando a sessão abriu, não na coleta."""
        proxy = ProxySsh("p")
        proxy.abrir("s1", "servidor-01")
        proxy.registrar("s1", ProxySsh.SAIDA, "primeiro")
        proxy.registrar("s1", ProxySsh.SAIDA, "segundo")

        eventos = proxy.coletar("s1")
        assert eventos[0].deslocamento_ms < 1000
        assert eventos[1].deslocamento_ms >= eventos[0].deslocamento_ms

    def test_fechar_limpa_e_nao_levanta_duas_vezes(self) -> None:
        proxy = ProxySsh("p")
        proxy.abrir("s1", "servidor-01")
        proxy.registrar("s1", ProxySsh.SAIDA, "x")
        proxy.fechar("s1")

        assert proxy.coletar("s1") == []
        proxy.fechar("s1")  # idempotente: encerramento repetido é normal

    def test_fechar_descarta_pendentes_sem_coleta(self) -> None:
        proxy = ProxySsh("p")
        proxy.abrir("s1", "servidor-01")
        proxy.registrar("s1", ProxySsh.SAIDA, "x")
        assert proxy.pendentes("s1") == 1
        proxy.fechar("s1")
        assert proxy.pendentes("s1") == 0


class TestProxySshCredencial:
    def test_sem_buscador_recusa_em_vez_de_pedir_senha(self) -> None:
        """O ponto do cofre é a senha não passar pela pessoa.

        Cair para "digite a senha do servidor" derrotaria o propósito
        justamente no caminho que existe para protegê-lo.
        """
        with pytest.raises(ValidationError, match="passar pela pessoa"):
            ProxySsh("p").credencial_do_alvo("servidor-01")

    def test_credencial_vem_do_cofre_pelo_alvo(self) -> None:
        chamadas: list[str] = []

        def buscar(alvo: str) -> tuple[str, str]:
            chamadas.append(alvo)
            return ("root", "senha-do-cofre")

        proxy = ProxySsh("p", buscar_credencial=buscar)
        assert proxy.credencial_do_alvo("servidor-01") == ("root", "senha-do-cofre")
        assert chamadas == ["servidor-01"]


# ----------------------------------------------------------- ArmazenamentoS3


class S3Falso:
    """Cliente S3 de teste. Guarda em dicionário e imita o Object Lock."""

    def __init__(
        self,
        *,
        lock: str | None = "COMPLIANCE",
        versionado: bool = True,
        bucket_existe: bool = True,
    ) -> None:
        self.objetos: dict[str, bytes] = {}
        self._lock = lock
        self._versionado = versionado
        self._bucket_existe = bucket_existe
        self.deletes = 0

    def head_bucket(self, Bucket: str) -> dict[str, Any]:  # noqa: N803
        if not self._bucket_existe:
            raise _ErroS3Error("NoSuchBucket")
        return {}

    def get_object_lock_configuration(self, Bucket: str) -> dict[str, Any]:  # noqa: N803
        if self._lock is None:
            raise _ErroS3Error("ObjectLockConfigurationNotFoundError")
        return {
            "ObjectLockConfiguration": {
                "ObjectLockEnabled": "Enabled",
                "Rule": {"DefaultRetention": {"Mode": self._lock, "Days": 2555}},
            }
        }

    def get_bucket_versioning(self, Bucket: str) -> dict[str, Any]:  # noqa: N803
        return {"Status": "Enabled"} if self._versionado else {}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        chave = kwargs["Key"]
        if kwargs.get("IfNoneMatch") == "*" and chave in self.objetos:
            raise _ErroS3Error("PreconditionFailed")
        self.objetos[chave] = kwargs["Body"]
        return {}

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if Key not in self.objetos:
            raise _ErroS3Error("NoSuchKey")
        return {"Body": _Corpo(self.objetos[Key])}

    def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        self.deletes += 1
        return {}


class _ErroS3Error(Exception):
    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.response = {"Error": {"Code": codigo}}


class _Corpo:
    def __init__(self, dados: bytes) -> None:
        self._dados = dados

    def read(self) -> bytes:
        return self._dados


def _s3(**kwargs: Any) -> tuple[ArmazenamentoS3, S3Falso]:
    cliente = S3Falso(**kwargs)
    return ArmazenamentoS3("vault-gravacoes", client=cliente), cliente


class TestArmazenamentoS3Contrato:
    def test_cumpre_a_porta(self) -> None:
        armazem, _ = _s3()
        assert isinstance(armazem, ArmazenamentoDeGravacao)

    def test_bucket_vazio_recusa_na_construcao(self) -> None:
        """Descobrir no fim da sessão perderia a gravação."""
        with pytest.raises(ValidationError, match="bucket"):
            ArmazenamentoS3("", client=S3Falso())

    def test_nome_identifica_o_bucket(self) -> None:
        armazem, _ = _s3()
        assert armazem.nome == "s3:vault-gravacoes"


class TestArmazenamentoS3Imutabilidade:
    def test_compliance_e_imutavel(self) -> None:
        armazem, _ = _s3(lock="COMPLIANCE")
        assert armazem.imutavel is True

    def test_governance_nao_e_imutavel(self) -> None:
        """GOVERNANCE é contornável por quem tem a permissão de bypass.

        "Imutável, menos para alguns" não é a garantia que a palavra promete
        numa auditoria.
        """
        armazem, _ = _s3(lock="GOVERNANCE")
        assert armazem.imutavel is False

    def test_sem_object_lock_nao_e_imutavel(self) -> None:
        """O teste que o esqueleto não tinha.

        Ele devolvia True fixo: um bucket sem lock aceita PutObject igual e
        nada falha, então a aplicação anunciaria prova para algo apagável.
        """
        armazem, _ = _s3(lock=None)
        assert armazem.imutavel is False

    def test_confere_uma_vez_e_guarda(self) -> None:
        """Configuração de bucket não muda a cada gravação."""
        armazem, cliente = _s3()
        chamadas = {"n": 0}
        original = cliente.get_object_lock_configuration

        def contando(Bucket: str) -> dict[str, Any]:  # noqa: N803
            chamadas["n"] += 1
            return original(Bucket=Bucket)

        cliente.get_object_lock_configuration = contando  # type: ignore[method-assign]
        assert armazem.imutavel is True
        assert armazem.imutavel is True
        assert chamadas["n"] == 1


class TestArmazenamentoS3Gravacao:
    def test_guardar_e_ler_fecham(self) -> None:
        armazem, _ = _s3()
        referencia = armazem.guardar("sessao-1", b'[0,"o","ola"]')
        assert armazem.ler(referencia) == b'[0,"o","ola"]'

    def test_chave_usa_o_prefixo_com_barra(self) -> None:
        armazem, cliente = _s3()
        referencia = armazem.guardar("sessao-1", b"x")
        assert referencia == "sessoes/sessao-1.jsonl"
        assert "sessoes/sessao-1.jsonl" in cliente.objetos

    def test_prefixo_sem_barra_nao_cola_no_id(self) -> None:
        """Sem a barra, "sessoes" + "abc" viraria "sessoesabc.jsonl"."""
        armazem = ArmazenamentoS3("b", prefixo="gravacoes", client=S3Falso())
        assert armazem.guardar("abc", b"x") == "gravacoes/abc.jsonl"

    def test_nao_sobrescreve_gravacao_existente(self) -> None:
        """Gravação é prova: regravar a mesma sessão é recusado."""
        armazem, _ = _s3()
        armazem.guardar("sessao-1", b"primeira")
        with pytest.raises(ValidationError, match="é prova"):
            armazem.guardar("sessao-1", b"segunda")

    def test_a_primeira_gravacao_sobrevive_a_tentativa(self) -> None:
        armazem, _ = _s3()
        armazem.guardar("sessao-1", b"primeira")
        with pytest.raises(ValidationError):
            armazem.guardar("sessao-1", b"segunda")
        assert armazem.ler("sessoes/sessao-1.jsonl") == b"primeira"

    def test_ler_inexistente_levanta_validacao(self) -> None:
        armazem, _ = _s3()
        with pytest.raises(ValidationError, match="não encontrada"):
            armazem.ler("sessoes/nao-existe.jsonl")

    def test_nunca_chama_delete(self) -> None:
        """A disciplina do adaptador, verificada.

        O Object Lock é a garantia de verdade, mas um delete aqui criaria
        delete-marker e a gravação sairia da listagem.
        """
        armazem, cliente = _s3()
        armazem.guardar("sessao-1", b"x")
        armazem.ler("sessoes/sessao-1.jsonl")
        armazem.verificar_bucket()
        assert cliente.deletes == 0


class TestArmazenamentoS3Verificacao:
    def test_bucket_correto_nao_tem_problema(self) -> None:
        armazem, _ = _s3()
        assert armazem.verificar_bucket() == []

    def test_bucket_inacessivel_e_o_unico_problema_relatado(self) -> None:
        """Sem bucket, o resto não tem como ser verificado."""
        armazem, _ = _s3(bucket_existe=False)
        problemas = armazem.verificar_bucket()
        assert len(problemas) == 1
        assert "inacessível" in problemas[0]

    def test_sem_lock_avisa_que_nao_serve_como_prova(self) -> None:
        armazem, _ = _s3(lock=None)
        problemas = armazem.verificar_bucket()
        assert any("não servem como prova" in p for p in problemas)

    def test_versionamento_desligado_e_problema(self) -> None:
        armazem, _ = _s3(versionado=False)
        problemas = armazem.verificar_bucket()
        assert any("versionamento desligado" in p for p in problemas)
