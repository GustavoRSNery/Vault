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

## 2. Captura de sessão por proxy — ✅ IMPLEMENTADO (26/10/2026)

**Porta:** `app/application/ports/sessions.py` → `CapturaDeSessao`
**Padrão:** `CapturaManual` (`captura_automatica = False`)
**Produção:** `ProxySsh` + `ServidorDeSessoes` (`infrastructure/sessions/`)
**Injeção:** `get_captura` em `deps.py` (`VAULT_SESSAO_CAPTURA=proxy-ssh`)

Provado fim a fim contra SSH real: o cliente conecta no proxy com a senha
*dele*, o proxy busca a credencial do alvo no cofre, conecta por fora e
grava os dois sentidos. A senha do alvo nunca passa por quem acessa.

### Para ligar

**1. Instalar o extra:**

```bash
pip install -e ".[ssh]"      # asyncssh
```

**2. Gerar a chave de host, em arquivo:**

```bash
ssh-keygen -t ed25519 -f /etc/vault/chave_host_proxy -N ''
```

Chave gerada a cada boot faz **todo** cliente ver o aviso de *host key
changed* — o mesmo aviso de um ataque man-in-the-middle. As pessoas
aprendem a ignorá-lo, que é o pior resultado possível. `iniciar()` recusa
subir sem o arquivo.

**3. Subir o servidor**, passando os casos de uso que ele não conhece:

```python
servidor = ServidorDeSessoes(
    ProxySsh("0.0.0.0", 2222, buscar_credencial=credencial_do_cofre),
    autenticar=autenticar_no_vault,   # (usuario, senha) -> id | None
    abrir_sessao=abrir_com_rbac,      # (usuario_id, alvo) -> sessao_id
    fechar_sessao=fechar_e_guardar,
    porta=2222,
    chave_do_host="/etc/vault/chave_host_proxy",
)
await servidor.iniciar()
```

A pessoa acessa `ssh usuario@alvo@proxy -p 2222` — o formato dos bastion
hosts, feio e universal: qualquer cliente `ssh` chega sem configuração.

**4. Fechar o alvo:** o servidor-alvo deve aceitar conexão **só** de onde o
proxy roda. Sem isso, quem souber a credencial pula o proxy e a gravação
tem um buraco exatamente no caso de quem não quer ser gravado.

### O que o proxy recusa, e por quê

Encaminhamento de porta, reverso, SFTP/SCP e comando sem pty. São canais
que ele **não grava**; deixá-los passar daria sessão gravada pela metade — e
numa auditoria a gravação parcial é pior que nenhuma, porque parece
completa. Recusar é visível.

### A ordem que importa

A sessão é aberta (e o RBAC aplicado) **antes** de conectar ao alvo.
Conectar primeiro abriria acesso a quem a política depois recusaria, e
fechar a conexão não desfaz o que já foi digitado.

---

## 3. Armazenamento de gravações — ✅ IMPLEMENTADO (26/10/2026)

**Porta:** `app/application/ports/sessions.py` → `ArmazenamentoDeGravacao`
**Padrão:** `ArmazenamentoLocal` (`imutavel = False`, e diz isso)
**Produção:** `ArmazenamentoS3`
**Injeção:** `get_gravacoes` (`VAULT_SESSAO_ARMAZENAMENTO=s3`)

Provado contra S3 real com Object Lock: a sobrescrita é recusada, o DELETE
da versão é recusado, e bucket **sem** lock reporta `imutavel=False`.

### Para ligar

**1. Bucket com Object Lock em COMPLIANCE:**

```bash
aws s3api create-bucket --bucket vault-gravacoes --object-lock-enabled-for-bucket
aws s3api put-object-lock-configuration --bucket vault-gravacoes \
  --object-lock-configuration \
  'ObjectLockEnabled=Enabled,Rule={DefaultRetention={Mode=COMPLIANCE,Days=2555}}'
```

**COMPLIANCE, não GOVERNANCE.** Em GOVERNANCE, quem tiver
`BypassGovernanceRetention` apaga — e `imutavel` devolve `False` de
propósito nesse caso, porque "imutável, menos para alguns" não é a garantia
que a palavra promete numa auditoria.

**2. Credencial com `PutObject`/`GetObject` e sem `DeleteObject`.** Defesa
em profundidade: o adaptador nunca chama delete, mas se um dia alguém
acrescentar, a permissão recusa.

**3. `boto3`** — vem no extra `kms` (`pip install -e ".[kms]"`).

**4. Conferir ao subir:**

```python
problemas = armazenamento.verificar_bucket()
if problemas:
    raise RuntimeError("; ".join(problemas))
```

Melhor descobrir que o bucket não tem lock ao subir do que ao procurar a
gravação de um incidente.

### Como validar sem AWS

```bash
docker run -d --name vault_localstack -p 4566:4566 \
    -e SERVICES=s3,kms localstack/localstack:3
VAULT_TEST_S3_ENDPOINT=http://localhost:4566 \
    pytest tests/integration/test_s3_localstack.py
```

12 testes, incluindo o que prova que o Object Lock recusa o DELETE. Sem a
variável eles são ignorados, não falham.

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
