# Conectar os adaptadores externos

Tudo o que depende de serviço de fora está atrás de uma **porta** (`Protocol`
em `app/application/ports/`). O domínio e as rotas não conhecem nenhuma
tecnologia; conectar é escrever uma classe que satisfaz a porta e trocar uma
linha em `app/api/deps.py`.

Nenhum destes itens bloqueia o resto do sistema: cada um tem um adaptador
local que funciona hoje e **declara suas próprias limitações**, em vez de
fingir uma garantia que o ambiente não tem.

---

## 1. Exportação da trilha para SIEM

**Porta:** `app/application/ports/siem.py` → `SiemExporter`
**Hoje:** `JsonlExporter` (arquivo local, `inviolavel = False`)
**Injeção:** `get_siem_exporter` em `deps.py`

A âncora da auditoria só vale se o destino for **inviolável pela aplicação**.
Se o Vault puder reescrever o que exportou, um atacante com o Vault na mão
reescreve os dois lados e a âncora não prova nada.

Por isso a porta tem só `append` — sem update, sem delete. Nenhuma
implementação deve oferecê-los.

### O que falta

| Destino | O que precisa |
| --- | --- |
| Splunk HEC | token do HTTP Event Collector, URL do coletor |
| CloudWatch Logs | log group com retenção, credencial com `PutLogEvents` |
| S3 com Object Lock | bucket em modo COMPLIANCE, credencial **sem** `DeleteObject` |

```python
class SplunkExporter:
    nome = "splunk-hec"
    inviolavel = True          # só marque True se o destino for mesmo WORM

    def append(self, linhas: list[str]) -> int:
        ...                     # POST para /services/collector/event
```

Depois, em `deps.py`:

```python
def get_siem_exporter(settings) -> SiemExporter:
    if settings.siem_tipo == "splunk":
        return SplunkExporter(settings.splunk_url, settings.splunk_token)
    return JsonlExporter(settings.audit_export_path)
```

**Atenção ao `inviolavel`.** Ele não é cosmético: a API devolve esse valor e a
tela mostra o aviso correspondente. Marcá-lo `True` num destino que a
aplicação pode reescrever é anunciar prova onde há só registro.

---

## 2. Captura de sessão por proxy

**Porta:** `app/application/ports/sessions.py` → `CapturaDeSessao`
**Hoje:** `CapturaManual` (`captura_automatica = False`)
**Esqueleto:** `ProxySsh` em `infrastructure/sessions/adapters.py`
**Injeção:** `get_captura` em `deps.py` (`VAULT_SESSAO_CAPTURA=proxy-ssh`)

### O que falta

1. **Servidor SSH intermediário** — a pessoa acessa o proxy, não o alvo.
   `asyncssh` resolve; o proxy precisa de um par de chaves próprio.
2. **Um pty por sessão**, lendo os dois sentidos do canal. Entrada e saída
   viram `EventoCapturado` com `tipo` `"entrada"` e `"saida"`.
3. **Credencial do alvo vinda do cofre**, injetada pelo proxy sem passar pela
   pessoa — esse é o ponto: a senha nunca chega a quem usa.

```python
def coletar(self, sessao_id: str) -> list[EventoCapturado]:
    return [
        EventoCapturado(
            deslocamento_ms=int((agora - inicio) * 1000),
            tipo="saida",
            conteudo=bloco.decode("utf-8", "replace"),
        )
        for agora, bloco in self._buffer.pop(sessao_id, [])
    ]
```

O `deslocamento_ms` é **relativo ao início da sessão**, não um horário — é o
que permite reproduzir sem depender de relógio, e importar gravação feita
offline.

**Não devolva lista vazia em silêncio se a captura estiver quebrada.** Os
métodos do esqueleto levantam `NotImplementedError` de propósito: um stub
silencioso viraria "a gravação está ligada" numa auditoria, e descobrir que
não estava é a pior hora para descobrir.

---

## 3. Armazenamento de gravações

**Porta:** `app/application/ports/sessions.py` → `ArmazenamentoDeGravacao`
**Hoje:** `ArmazenamentoLocal` (`imutavel = False`)
**Esqueleto:** `ArmazenamentoS3`
**Injeção:** `get_gravacoes` (`VAULT_SESSAO_ARMAZENAMENTO=s3`)

### O que falta

1. Bucket com **Object Lock em modo COMPLIANCE** e retenção definida. Sem
   isso, `imutavel = True` estaria mentindo.
2. Credencial com `PutObject` e **sem** `DeleteObject`: a aplicação não deve
   conseguir apagar o que gravou.
3. `boto3` — já vem no extra `kms` (`pip install -e ".[kms]"`).

```python
def guardar(self, sessao_id: str, conteudo: bytes) -> str:
    chave = f"{self._prefixo}{sessao_id}.jsonl"
    self._s3().put_object(
        Bucket=self._bucket, Key=chave, Body=conteudo,
        ObjectLockMode="COMPLIANCE",
        ObjectLockRetainUntilDate=datetime.now(UTC) + timedelta(days=1825),
    )
    return chave
```

O formato é **JSON Lines**, uma linha `[ms, tipo, conteúdo]` por evento — o
mesmo do asciicast v2, para que a gravação possa ser reproduzida por
ferramentas que já existem, em vez de depender para sempre do player deste
sistema.

---

## 4. Envio de e-mail

**Porta:** ainda não existe. É o que falta para recuperação de senha, convite
de usuário e regras de notificação.

Quando for criar, siga o mesmo padrão: um `Protocol` em `ports/`, um
adaptador local que escreve num arquivo (para desenvolvimento ver o conteúdo
sem enviar nada), e o de produção atrás da mesma interface.

A porta deveria ter **só** `enviar(destino, assunto, corpo) -> str`. Resistir
a acrescentar "enviar em massa" ou "template" nela: isso é da camada de
aplicação, e uma porta que cresce vira acoplamento disfarçado.

---

## Chave-mestra (já conectável)

**Porta:** `app/application/ports/keys.py` → `KeyProvider`
**Hoje:** `LocalKeyProvider` (chave em memória)
**Pronto:** `KmsKeyProvider` — implementado, falta só a credencial AWS.

```bash
pip install -e ".[kms]"
export VAULT_KMS_KEY_ID=alias/vault-prod
export VAULT_KMS_REGION=sa-east-1
```

Produção **recusa subir** sem `VAULT_KMS_KEY_ID`: configuração que funciona
com a chave no processo é pior que uma que falha ao subir, porque o erro só
apareceria no vazamento.

---

## Como verificar que um adaptador novo está certo

```python
from app.application.ports.sessions import CapturaDeSessao
assert isinstance(MeuAdaptador(), CapturaDeSessao)
```

As portas são `runtime_checkable`: o `isinstance` confere os métodos. Ele
**não** confere assinaturas — para isso, rode a suíte com o adaptador
injetado, que é o que os testes de `test_api_sessoes.py` fazem com
`dependency_overrides`.
