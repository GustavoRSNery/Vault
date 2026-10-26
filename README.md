<div align="center">

# 🔐 Vault de Senhas

**Cofre corporativo de senhas, segredos e credenciais**

Criptografia de envelope AES-256-GCM · RBAC por caminho · trilha de auditoria encadeada · acesso de máquina para RPAs

[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Testes](https://img.shields.io/badge/testes-1096%20verdes-brightgreen)](#-qualidade)

[Começar](#-começar-em-3-minutos) · [Funcionalidades](#-o-que-ele-faz) · [Arquitetura](#-arquitetura) · [API](#-api) · [English](README.en.md)

</div>

---

## 📸 O sistema

<div align="center">

### Painel — o estado do cofre de relance

<img src="docs/img/painel.jpg" alt="Painel com contagens de segredos, credenciais e certificados, e a lista do que precisa de atenção" width="100%">

</div>

<table>
<tr>
<td width="50%">

### Credenciais com rotação e custódia

<img src="docs/img/credenciais.jpg" alt="Lista de credenciais mostrando prazo de rotação e quem está com cada uma">

Quem retira uma credencial fica com ela até devolver. Evita duas pessoas trocarem a mesma senha ao mesmo tempo.

</td>
<td width="50%">

### Trilha de auditoria encadeada

<img src="docs/img/auditoria.jpg" alt="Trilha de auditoria mostrando cadeia íntegra e eventos registrados">

Cada evento guarda a marca do anterior. Alterar um registro do meio rompe a corrente, e a tela mostra onde.

</td>
</tr>
<tr>
<td width="50%">

### Políticas por caminho, com `deny` vencendo

<img src="docs/img/politicas.jpg" alt="Políticas de acesso com regras allow e deny por caminho">

Uma regra `deny` derruba qualquer `allow`, por mais específico que seja — é o que torna a revogação confiável.

</td>
<td width="50%">

### Governança da API

<img src="docs/img/consumo-api.jpg" alt="Tela de consumo da API mostrando quem chama, quantas recusadas e as rotas">

Quem consome a API de fora, em quais rotas e com que resultado. As chamadas da própria interface ficam fora.

</td>
</tr>
</table>

<div align="center">

### Tutoriais embutidos em cada tela

<img src="docs/img/tour.jpg" alt="Tour guiado explicando que a tela de credenciais não guarda a senha" width="85%">

</div>

---

## 🚀 Começar em 3 minutos

**Pré-requisito:** [Docker](https://docs.docker.com/get-docker/) com Compose.

```bash
git clone https://github.com/GustavoRSNery/Vault.git
cd Vault
docker compose up -d --build
```

Três containers sobem: Postgres, API e interface. Aguarde o healthcheck (~30 s) e crie seu administrador:

```bash
docker compose exec api python -m app.tools.criar_admin voce@empresa.com.br "SuaSenhaForte2026"
```

Abra **http://localhost:8080** e entre.

### Com dados de exemplo

Para ver o sistema povoado em vez de telas vazias:

```bash
docker compose exec -T db psql -U vault -d vault < dados-demo/vault_demo.sql
```

Traz 5 cofres, 8 credenciais, 4 certificados, 8 dispositivos e 454 eventos de auditoria — todos fictícios. Detalhes em [`dados-demo/LEIA-ME.md`](dados-demo/LEIA-ME.md).

> ⚠️ O dump **substitui** o que estiver no banco. Rode antes de cadastrar coisas suas.

### Portas

| Serviço | URL |
| --- | --- |
| Interface | http://localhost:8080 |
| API | http://localhost:8777 |
| Documentação interativa | http://localhost:8777/docs |
| Postgres | `localhost:55432` |

---

## 🎯 O que ele faz

### Guarda segredos sem que a aplicação possa lê-los sozinha

Cada segredo é cifrado com uma chave própria (DEK), e essa chave é cifrada por uma chave-mestra (KEK) — **criptografia de envelope**. Em produção a KEK vive no AWS KMS e **nunca entra no processo**: o KMS embrulha e desembrulha do lado dele.

A configuração **recusa subir em produção sem KMS**. Com a chave em memória, quem ler o processo decifra o cofre inteiro offline — aceitável em desenvolvimento, inaceitável com senha real de gente.

### Controla quem pode o quê, por caminho

```
cofres/contabil/*                      allow   list, read
cofres/contabil/segredos/token-sefaz   deny    reveal
```

`deny` vence `allow`, por mais específico que o `allow` seja. Sem essa precedência, revogar acesso viraria caça a regras espalhadas.

### Registra tudo, de forma verificável

A trilha é **append-only e encadeada por hash**: cada evento carrega a marca do anterior. Apagar ou alterar um registro no meio rompe a corrente, e a verificação mostra onde.

> **Sobre o alcance dessa garantia:** a cadeia prova que ninguém adulterou *sem recosturar*. Quem controla a aplicação poderia refazer a corrente inteira. A **âncora externa** — um registro num destino que o Vault não pode alterar — é o que fecha essa brecha, e a tela diz quanto da trilha está ancorada.

### Dá acesso temporário, que caduca sozinho

Em vez de acesso permanente a tudo, a pessoa **pede** quando precisa, por um prazo. Vencido, cai sozinho — ninguém precisa lembrar de remover.

### Atende robôs sem conta de pessoa

RPAs se autenticam por **AppRole** (`role_id` público + `secret_id` secreto) e recebem um *lease* curto. O escopo é **congelado na emissão**: alterar a política depois não amplia um lease já emitido.

### Grava sessões SSH

Um proxy intermedeia o acesso: o cliente conecta com a senha *do proxy*, que busca a credencial do alvo no cofre e conecta por fora. **A senha do alvo nunca passa por quem acessa.** Tudo o que foi digitado fica gravado, com linha do tempo.

### Audita quem consome a API

Registra as chamadas que chegam de fora — aplicações, robôs e scripts — com rota, resultado, latência e origem. As chamadas da própria interface ficam de fora, senão seriam a maioria.

> **O corpo das requisições não é guardado.** Nem no banco, nem em memória: o middleware não lê o fluxo de entrada. Uma chamada que cria segredo carrega a senha no corpo, e guardá-la num log a deixaria em claro fora do cofre.

---

## 🏗️ Arquitetura

### Camadas

```
api  →  application  →  domain
                     ↖  infrastructure (implementa as portas)
```

O **domínio não conhece** FastAPI, SQLAlchemy, AWS nem React. Ele define *portas* (`Protocol`), e a infraestrutura as implementa. Trocar de banco, de SIEM ou de armazenamento é trocar um adaptador.

### O que está atrás de uma porta

| Porta | Adaptador local | Produção |
| --- | --- | --- |
| Chave-mestra | Chave em memória | AWS KMS |
| Trilha externa | Arquivo JSONL | SIEM, bucket append-only |
| Gravação de sessão | Disco local | S3 com Object Lock |
| Captura de sessão | Registro manual | Proxy SSH (`asyncssh`) |
| Webhooks | Ensaio (não envia) | HTTP com assinatura |

Como conectar cada um: [`docs/conectar-adaptadores.md`](docs/conectar-adaptadores.md).

### Stack

| Camada | Tecnologias |
| --- | --- |
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · Argon2id · `cryptography` · `asyncssh` |
| **Frontend** | React 18 · TypeScript 5.7 · Vite · TanStack Query · CSS próprio (sem framework) |
| **Dados** | PostgreSQL 16 (SQLite nos testes) |
| **Infra** | Docker Compose · nginx |

---

## 🔌 API

**121 endpoints** em 103 rotas. Documentação interativa em `/docs` com os containers no ar.

```bash
# 1. Autentica
TOKEN=$(curl -s -X POST localhost:8777/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"voce@empresa.com.br","password":"SuaSenha"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['tokens']['access_token'])")

# 2. Lista os cofres que seu token alcança
curl -s localhost:8777/api/v1/cofres -H "Authorization: Bearer $TOKEN"
```

A filtragem é **no servidor**: cofre sem permissão não aparece na resposta.

Cada tela tem um botão **"Ver pela API"** que mostra os endpoints equivalentes com o `curl` pronto para copiar.

### Acesso de máquina

```bash
# O robô se autentica e recebe um lease curto
curl -s -X POST localhost:8777/api/v1/maquina/autenticar \
  -H 'Content-Type: application/json' \
  -d '{"role_id":"...","secret_id":"..."}'

# E lê o segredo com o token do lease
curl -s -X POST localhost:8777/api/v1/maquina/segredo \
  -H "Authorization: Bearer $LEASE" \
  -H 'Content-Type: application/json' \
  -d '{"cofre":"rh","segredo":"portal-folha"}'
```

---

## ✅ Qualidade

| | |
| --- | --- |
| **Backend** | 1.000 testes (988 passam, 12 dependem de serviço externo) |
| **Frontend** | 96 testes |
| **Dialetos** | A suíte roda em SQLite **e** em Postgres real |
| **Tipos** | `mypy --strict` |
| **Lint** | `ruff` · `eslint --max-warnings 0` |

```bash
# Backend
cd backend && pytest tests/ -q

# Backend no dialeto Postgres (pega divergências que o SQLite esconde)
VAULT_TEST_DATABASE_URL="postgresql+psycopg://vault:vault_local_dev@localhost:55432/vault_test" \
  pytest tests/ -q

# Frontend
cd frontend && npm test
```

> **Por que rodar nos dois dialetos:** SQLite aceita SQL que o Postgres recusa, e o contrário também. Uma divergência já causou incidente neste projeto — daí o gate duplo.

---

## 📚 Documentação

| Documento | O que cobre |
| --- | --- |
| [`docs/conectar-adaptadores.md`](docs/conectar-adaptadores.md) | Ligar KMS, SIEM, S3 e proxy SSH em produção |
| [`docs/governanca-da-api.md`](docs/governanca-da-api.md) | Como o consumo externo é registrado, e por quanto tempo |
| [`docs/inventario-telas.md`](docs/inventario-telas.md) | As telas do sistema, uma a uma |
| [`docs/notas-de-implementacao.md`](docs/notas-de-implementacao.md) | Decisões de implementação em detalhe |
| [`dados-demo/LEIA-ME.md`](dados-demo/LEIA-ME.md) | Restaurar e regenerar os dados de exemplo |
| [`DIARIO.md`](DIARIO.md) | O porquê de cada decisão, e os erros do caminho |

---

## ⚠️ Antes de usar em produção

Este projeto roda completo em ambiente local. Para uso real, três pontos **não são opcionais**:

1. **KMS** — sem ele a chave-mestra fica em memória, e quem ler o processo decifra tudo. A configuração já recusa subir em produção sem `VAULT_KMS_KEY_ID`.
2. **Trilha ancorada fora** — o arquivo local prova o fluxo, não a inviolabilidade. Aponte para um destino que a aplicação não possa reescrever.
3. **Segredos fora do repositório** — `VAULT_JWT_SECRET` e as credenciais do banco vêm do ambiente ou de um gerenciador, nunca de arquivo versionado.

As chaves no `docker-compose.yml` são **de desenvolvimento, públicas e conhecidas**. Nunca as use fora da sua máquina.

---

## 📄 Licença

[MIT](LICENSE) — use, modifique e distribua à vontade.

<div align="center">
<sub>Os dados de exemplo, nomes e certificados deste repositório são fictícios.</sub>
</div>
