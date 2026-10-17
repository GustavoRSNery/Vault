# Vault de Senhas

Cofre corporativo de senhas, segredos e credenciais. Backend em FastAPI com
clean architecture, frontend em React, segredos protegidos por envelope
AES-256-GCM e trilha de auditoria encadeada por hash.

Construído a partir dos documentos de arquitetura, do inventário de 57 telas e
do design system do projeto.

## Estado atual — Fase 1 (Fundação)

| Entregue | Em aberto |
| --- | --- |
| Autenticação com senha (Argon2id) e MFA por TOTP | Telas de cadastro e recuperação |
| Cofres, segredos versionados, lixeira | Rotação automática, custódia/check-out |
| RBAC por caminho, com negação tendo precedência | Editor de políticas na interface |
| Trilha de auditoria encadeada + âncora externa | Exportação para SIEM |
| Selo do cofre (seal/unseal) no domínio | Selagem via KMS e quórum Shamir |
| API REST e telas de login, dashboard e cofres | As demais 52 telas do inventário |

**158 testes** (81 unitários, 52 de integração, 25 end-to-end), validados
também com o sistema no ar.

## Como rodar

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

## Decisões de segurança

As escolhas abaixo não são óbvias e têm custo; estão aqui para que ninguém as
desfaça sem saber o que elas protegiam.

**Envelope encryption.** Cada segredo recebe uma chave de dados (DEK) própria,
protegida pela chave-mestra (KEK). A KEK nunca cifra dado diretamente, então
rotacioná-la não exige reescrever todos os segredos. Em produção a KEK vive no
KMS; em desenvolvimento, uma chave local atrás da mesma interface.

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

**Segredo nasce mascarado.** Revelar é ação explícita, o valor some sozinho em
30 s, e copiar não exibe nada na tela. O `__repr__` dos objetos que carregam
valor em claro é sobrescrito, para que um traceback não imprima senha em log.

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
sequência+hash registrado num destino que a aplicação não pode reescrever
(SIEM, bucket somente-anexação). `verify_chain(eventos, anchors=...)` pega a
recostura. A exportação periódica que alimenta essas âncoras é trabalho da
fase 3 e **ainda não está implementada**: até lá, a garantia é parcial.

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
  application/      casos de uso (1 arquivo = 1 caso) e portas
  infrastructure/   SQLAlchemy, cripto, auth — implementa as portas
  api/              routers finos: validam, chamam o caso de uso, mapeiam erro
frontend/src/
  shared/ui/        design system (tokens do próprio sistema de design)
  shared/api/       cliente HTTP com refresh automático
  features/         auth, dashboard, vaults, secrets
docs/
  inventario-telas.md   as 57 telas, transcritas do documento de arquitetura
```

A dependência aponta sempre para dentro: `api → application → domain`. O
domínio não importa nada de fora, e é por isso que ele é testável sem banco,
sem rede e sem framework.
