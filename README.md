# Vault de Senhas

Cofre corporativo de senhas, segredos e credenciais. Backend em FastAPI com
clean architecture, frontend em React, segredos protegidos por envelope
AES-256-GCM e trilha de auditoria encadeada por hash.

Construído a partir dos documentos de arquitetura, do inventário de 57 telas e
do design system do projeto.

## Estado atual

**49 das 57 telas** do inventário de arquitetura, **66 endpoints**, **527
testes** — verdes em SQLite e em Postgres real, validados com o sistema no ar
e conferidos no navegador.

`python docs/mapa_telas.py` imprime o cruzamento tela a tela.

| Entregue | Em aberto |
| --- | --- |
| Login (Argon2id) e MFA por TOTP, com cadastro em duas etapas | Recuperação de senha e convite (dependem de envio de e-mail) |
| Cofres, segredos versionados, histórico, lixeira com restauração | — |
| RBAC por caminho, negação com precedência, **editor com simulador** | — |
| **Pessoas, papéis e políticas** pela interface | Grupos como entidade própria |
| **Dispositivos, credenciais com rotação e custódia exclusiva** | Rotação automática (hoje é registro manual) |
| **Certificados com faixas de expiração** | Upload do arquivo do certificado |
| **Solicitações de acesso temporário**, com concessão que caduca sozinha | — |
| **Busca global** e **central de alertas**, ambas filtradas por permissão | Regras de notificação (dependem de canal de envio) |
| Trilha de auditoria encadeada, **exportada e ancorada** | Destino inviolável de verdade (hoje é arquivo local) |
| Selar e desselar cofre, **com quórum Shamir** | — |

| **Acesso de máquina para RPAs** (AppRole, leases, consumo, **rotação pelo robô**) | — |

Fora do escopo entregue: gravação de sessão e integrações (SES, WhatsApp,
LDAP) são fase 3.

### Ambiente de demonstração

`python -m app.tools.popular_demo` cria 3 cofres, 7 segredos e dois usuários
com carteiras diferentes. O segundo (`contador@exemplo.com.br`) existe para
tornar o RBAC visível na interface: ele enxerga apenas o cofre Contábil e tem
a revelação de um segredo específico negada por política, mesmo tendo
permissão ampla no cofre.

## Como rodar

### Com Docker (recomendado)

```bash
docker compose up -d --build
```

Pronto: **http://vault.local**. O banco é criado, o administrador e os dados
de demonstração entram sozinhos, e os passos são idempotentes — subir de novo
não duplica nada.

`vault.local` exige uma linha no arquivo `hosts` (PowerShell **como
administrador**):

```powershell
Add-Content C:\Windows\System32\drivers\etc\hosts "127.0.0.1 vault.local"
```

Sem isso, **http://vault.localhost** atende ao mesmo lugar e resolve sozinho
em qualquer máquina — é o que mantém `docker compose up` suficiente numa
instalação nova.

| Serviço | Endereço | O que é |
| --- | --- | --- |
| web | http://vault.local (ou http://vault.localhost) | a aplicação (nginx servindo o build + proxy da API) |
| api | http://localhost:8777/docs | a API e sua documentação interativa |
| db | localhost:55432 | Postgres (porta alta para não colidir com outro na máquina) |

Para popular o inventário de demonstração (dispositivos, credenciais em
vários estados de rotação e certificados vencendo):

```bash
docker compose exec api python -m app.tools.popular_inventario
```

Acessos de demonstração:

- `ana.souza@exemplo.com.br` / `SenhaForteDeDev2026` — administrador
- `contador@exemplo.com.br` / `SenhaDoContador2026` — carteira limitada

O navegador fala só com um host: o nginx encaminha `/api/` para a API no
mesmo lugar, então não há CORS nem endereço de backend embutido no bundle.

### Sem Docker

Requisitos: Python 3.12+, Node 20+.

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python

cp .env.example .env
./.venv/Scripts/python.exe -m app.tools.gerar_chave     # cole a saída no .env
./.venv/Scripts/python.exe -m app.tools.criar_admin voce@empresa.com.br SuaSenhaForte

./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8777 --reload
```

Documentação interativa da API em `http://127.0.0.1:8777/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173, com proxy para o backend
```

### Testes

```bash
cd backend
./.venv/Scripts/python.exe -m pytest tests/ -q

# Mesma suíte no dialeto de produção (ver "Postgres", abaixo):
VAULT_TEST_DATABASE_URL=postgresql+psycopg://user:senha@localhost:5432/vault_test \
  ./.venv/Scripts/python.exe -m pytest tests/ -q
```

### Revisão adversarial

A suíte exercita o código isoladamente. Com o sistema no ar, este script
tenta **furar** as garantias — escalada de privilégio, reescrita da própria
política, concessão temporária contra `deny`, auto-aprovação, roubo de
custódia, busca como vetor de descoberta, enumeração de usuário pelo tempo
de resposta, token de conta desativada e vazamento na trilha:

```bash
docker compose up -d
python scripts/revisao_seguranca.py
```

## Decisões de segurança

As escolhas abaixo não são óbvias e têm custo; estão aqui para que ninguém as
desfaça sem saber o que elas protegiam.

**Envelope encryption.** Cada segredo recebe uma chave de dados (DEK) própria,
protegida pela chave-mestra (KEK). A KEK nunca cifra dado diretamente, então
rotacioná-la não exige reescrever todos os segredos.

A diferença entre os dois provedores de KEK não é de implementação, é de
**modelo de ameaça**. Com `LocalKeyProvider`, quem lê o processo lê a chave e
decifra o cofre inteiro offline. Com o KMS, a chave-mestra nunca entra no
processo: ele embrulha e desembrulha a DEK do lado dele. Então um dump do
banco sozinho não vale nada, cada desproteção vira linha no CloudTrail (dá
para detectar um cofre sendo drenado), e revogar acesso é mudar política, sem
tocar nos dados.

Por isso a fronteira é `wrap`/`unwrap` e não "me dê a chave" — a segunda forma
não teria como ser implementada pelo KMS.

```bash
pip install -e ".[kms]"
export VAULT_KMS_KEY_ID=alias/vault-prod
export VAULT_KMS_REGION=sa-east-1
```

**Produção recusa subir sem KMS.** `environment=production` sem
`VAULT_KMS_KEY_ID` é erro de configuração, não detalhe: uma configuração que
"funciona" com a chave no processo é pior que uma que falha ao subir, porque
o erro só apareceria no vazamento.

**Rotação de KEK.** É o que o envelope torna barato:

```bash
python -m app.tools.rotacionar_kek --conferir
python -m app.tools.rotacionar_kek --nova-chave <base64>
python -m app.tools.rotacionar_kek --kms <arn-ou-alias>
```

Desembrulha cada DEK com a chave antiga e reembrulha com a nova; **o texto
cifrado dos segredos não é tocado**. O `key_id` gravado em cada versão vem da
impressão digital do material da chave, não de um nome — assim "já
rotacionado" é uma afirmação verdadeira, e a operação é retomável se for
interrompida.

**Negação vence.** Na avaliação de política, uma regra `deny` derruba qualquer
`allow`, por mais específico que seja. É o que torna a revogação confiável:
uma política de negação fecha o acesso sem auditar todas as concessões
existentes. O caminho casa por segmento, nunca por prefixo de texto — senão
`cofres/conta` cobriria `cofres/contabil`.

**`REVEAL` é separado de `READ`.** Ver que um segredo existe não é ver seu
valor. Listar nunca devolve o valor, e revelar é `POST`, não `GET`: `GET`
entraria em log de acesso, histórico do navegador e cache de proxy.

**Negativa também é auditada.** Toda tentativa negada vira evento, e as rotas
commitam a trilha antes de propagar o erro — sem isso o rollback da requisição
apagaria o registro. Tentativa negada sem rastro é exatamente o que interessa a
quem está sondando permissões.

**Login uniforme em mensagem e em tempo.** E-mail inexistente, senha errada e
conta inativa respondem igual. Quando o e-mail não existe, ainda assim se
verifica uma senha contra um hash descartável — gerado em tempo de execução,
para nunca ficar desatualizado e devolver rápido demais. Sem isso o tempo de
resposta denunciaria o que a mensagem esconde.

**Tokens em memória no front.** `localStorage` é legível por qualquer script na
página, e um único XSS entregaria a sessão. O custo é recarregar a aba exigir
novo login; num cofre de senhas o troco compensa.

**O cache é zerado a cada troca de sessão.** Encontrado validando no navegador:
sem isso, o React Query servia ao próximo usuário os cofres do anterior. A API
sempre respondeu certo, mas exibir o nome de um cofre alheio já revela que ele
existe a quem não deveria saber. O `AuthContext` limpa ao sair e ao entrar —
as duas pontas, porque a troca de conta nem sempre passa por um logout.

**Segredo nasce mascarado.** Revelar é ação explícita, o valor some sozinho em
30 s, e copiar não exibe nada na tela. O `__repr__` dos objetos que carregam
valor em claro é sobrescrito, para que um traceback não imprima senha em log.

**Concessão temporária soma, nunca subtrai.** Um acesso aprovado vale ao lado
das políticas, com prazo, e caduca sozinho — ninguém precisa lembrar de
remover, que é como acesso temporário vira permanente. Mas um `deny` explícito
não é contornado por concessão: a ordem em `decide` é negação → política →
concessão → nega por padrão. Compor as duas fontes com um OR deixaria uma
aprovação de emergência furar uma proibição deliberada. Quem precisa furar o
`deny` altera a política, que é revisada.

**Quem pede não decide**, nem tendo `APPROVE` no caminho. Auto-aprovação
transforma o fluxo inteiro em formalidade. E a decisão é terminal: pedir de
novo é outro registro, com outro rastro.

**Custódia de credencial é exclusiva.** Se duas pessoas retiram a mesma
credencial, as duas trocam a senha e a segunda invalida a da primeira sem que
ninguém perceba. A regra está no domínio e um índice parcial no banco a apoia,
porque sob concorrência o domínio só perceberia na leitura seguinte.

**Credencial nunca rotacionada conta como atrasada.** É o pior caso — pode
ainda ser a senha de fábrica — e tratá-la como "sem informação" a esconderia
justamente do relatório que existe para encontrá-la.

**A busca varre só o permitido.** Zero resultados não pode significar coisa
diferente de "não existe" para quem não tem acesso, senão a busca vira um mapa
do que está fora do alcance. E o valor do segredo nunca entra na comparação:
casar por conteúdo permitiria extraí-lo por tentativa e erro.

**Alertas são derivados, não gravados.** Alerta persistido precisa ser apagado
quando a causa some; esquecer disso produz alarme falso, que é pior do que
painel vazio.

**Quórum para desselar.** Selar sem quórum é frágil: quem sela desela
sozinho, e um administrador comprometido abre o cofre na mesma sessão. Com
quórum, a abertura exige `k` de `n` pessoas (Shamir sobre GF(256)).

O que os quinhões protegem é um **token de desselagem**, não a chave-mestra.
Partir a KEK seria a escolha óbvia e é a errada: no KMS ela não existe neste
processo para ser partida, e com chave local toda rotação invalidaria os
quinhões já distribuídos. Com token independente, selar e rotacionar não se
atrapalham.

Só o **hash** do token é guardado. Quem apresenta `k` quinhões reconstrói o
token, o hash confere, o cofre abre — sem que o sistema tenha o token em lugar
nenhum. Pelo mesmo motivo de senha ser hash: um dump do banco não abre nada.

Os quinhões aparecem **uma única vez**, na resposta da selagem, e não são
persistidos. Se todos forem perdidos, o cofre não abre mais; é a funcionalidade,
não um defeito, e a tela avisa antes.

A rota de desselagem simples **recusa** um cofre com quórum ativo — deixar
passar tornaria o mecanismo contornável por quem já tem `ADMIN`, ou seja, por
exatamente quem ele existe para conter.

**Acesso de máquina sem senha eterna.** Um RPA precisa ler segredos às 3 da
manhã, sem ninguém para digitar senha. A saída ruim é embutir credencial no
código — que vaza no repositório, fica no histórico do git e nunca é
rotacionada porque ninguém lembra que está lá.

AppRole separa `role_id` (identifica, público, pode ir no código) de
`secret_id` (autentica, segredo, revogável). Trocar a credencial não exige
alterar o robô, e um `role_id` vazado sozinho não autentica nada.

A autenticação devolve um **lease** curto, com escopo **congelado** no momento
da emissão: ampliar a política depois não amplia um lease já emitido, senão um
robô autenticado escalaria privilégio sem reautenticar. O teto é 12h — além
disso deixa de ser empréstimo.

A aplicação recebe política pelo mesmo mecanismo das pessoas (via papel), para
que o editor de políticas valha para os dois, em vez de haver um sistema de
permissão paralelo que ninguém revisa. E o lease carrega as **negações** junto
do escopo: um `allow` amplo não engole um `deny` específico, senão a máquina
teria mais acesso que a pessoa a quem a mesma política se aplica.

**O que a configuração não permite.** A tela de Configurações ajusta prazos
operacionais — tempo de exibição de um segredo, custódia padrão, faixa de
alerta de certificado. Ficam fora, no código: quórum mínimo de 2 pessoas,
teto de 12h do acesso de máquina, tamanhos de chave e nonce.

A pergunta que separa os dois grupos é se o pior valor possível enfraquece a
segurança. Configuração que permite desligar a própria proteção é pior que
configuração nenhuma: dá impressão de flexibilidade e entrega um sistema que
se desarma na primeira pressa.

Cada alteração registra o antes e o depois na trilha — "configuração
alterada" não permitiria revisar nada, e mudança silenciosa de prazo é
exatamente o que uma auditoria procura.

## Limites conhecidos da auditoria

A cadeia de hash detecta adulteração **preguiçosa**: alterar, remover ou
reordenar um evento sem recalcular os elos seguintes quebra a verificação na
hora.

Ela **não** detecta, sozinha, duas coisas:

1. **Recostura completa.** Quem altera um evento e recalcula todos os hashes
   seguintes produz uma cadeia internamente coerente. Verificar a lista contra
   ela mesma sempre aprova esse caso.
2. **Truncamento do fim.** Apagar os últimos eventos deixa a cadeia válida.

A defesa dos dois é a mesma: a **âncora externa** (`ChainAnchor`) — um par
sequência+hash registrado num destino que a aplicação não pode reescrever.
`POST /auditoria/exportar` envia os eventos pendentes e grava a âncora na
última sequência do lote, nesta ordem: **primeiro envia, só então ancora.**
Inverter criaria âncora para evento que nunca saiu, e a verificação acusaria
fraude onde houve falha de rede.

A prova de que funciona é executável:

```bash
docker compose cp scripts/prova_ancora.py api:/tmp/prova_ancora.py
docker compose exec -e PYTHONPATH=/app -w /app api python /tmp/prova_ancora.py
```

Ela altera um evento em memória, recostura todos os elos seguintes e mostra o
resultado: **0 quebras** sem âncora (a cadeia confere contra si mesma) e
**quebras** com âncora.

O que ainda falta é o destino: hoje a exportação grava um arquivo local, que
**não é inviolável** — quem tem o disco reescreve os dois lados. A API diz isso
na resposta (`destino_inviolavel: false`) e a tela mostra o aviso, em vez de
anunciar garantia que o ambiente não tem. Em produção, troque o destino em
`get_siem_exporter` por Splunk HEC, CloudWatch ou bucket com Object Lock: o
caso de uso só conhece a porta `SiemExporter`, então é uma linha.

## Postgres

A suíte roda em SQLite por padrão, e produção usa Postgres. Essa diferença já
produziu um bug real neste projeto: o SQLite devolve `datetime` sem timezone e
o Postgres com, e o hash da auditoria mudava conforme o banco — a trilha
falharia na verificação em produção. O carimbo é normalizado antes do hash e há
teste de regressão, mas a lição fica: **ao mexer em SQL ou em tipo de coluna,
rode a suíte com `VAULT_TEST_DATABASE_URL` apontando para um Postgres.**

As FKs também são ligadas explicitamente nos testes (`PRAGMA foreign_keys=ON`),
porque no SQLite elas vêm desligadas e um teste de integridade referencial
passaria aqui e quebraria lá.

## Estrutura

```
backend/app/
  domain/           Python puro: entidades e regras, sem FastAPI nem ORM
    access/         políticas e avaliação (negação vence)
    approvals/      solicitações, concessões temporárias e a composição
    audit/          trilha encadeada por hash e âncoras externas
    inventory/      dispositivos, credenciais com custódia, certificados
    vaults/         cofres e segredos versionados
  application/      casos de uso (1 arquivo = 1 caso) e portas
  infrastructure/   SQLAlchemy, cripto, auth — implementa as portas
  api/              routers finos: validam, chamam o caso de uso, mapeiam erro
frontend/src/
  shared/ui/        design system (tokens do próprio sistema de design)
  shared/api/       cliente HTTP com refresh automático
  features/         auth, dashboard, vaults, secrets, admin, inventory,
                    approvals, search
docs/
  inventario-telas.md   as 57 telas, transcritas do documento de arquitetura
  mapa_telas.py         cruza o inventário com o que existe hoje
```

A dependência aponta sempre para dentro: `api → application → domain`. O
domínio não importa nada de fora, e é por isso que ele é testável sem banco,
sem rede e sem framework.
