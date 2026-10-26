<div align="center">

# 🔐 Vault de Senhas

**Corporate vault for passwords, secrets and credentials**

AES-256-GCM envelope encryption · path-based RBAC · hash-chained audit trail · machine access for RPAs

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-1096%20passing-brightgreen)](#-quality)

[Get started](#-get-started-in-3-minutes) · [Features](#-what-it-does) · [Architecture](#-architecture) · [API](#-api) · [Português](README.md)

</div>

> **Note:** the interface and the seed data are in **Brazilian Portuguese**. This document describes the project in English; the running application is not translated.

---

## 📸 The system

<div align="center">

### Dashboard — the vault at a glance

<img src="docs/img/painel.jpg" alt="Dashboard showing counts of secrets, credentials and certificates, plus what needs attention" width="100%">

</div>

<table>
<tr>
<td width="50%">

### Credentials with rotation and check-out

<img src="docs/img/credenciais.jpg" alt="Credential list showing rotation deadlines and who currently holds each one">

Whoever checks a credential out keeps it until they return it. This prevents two people rotating the same password at once.

</td>
<td width="50%">

### Hash-chained audit trail

<img src="docs/img/auditoria.jpg" alt="Audit trail showing an intact chain and recorded events">

Every event carries the previous one's fingerprint. Altering a record in the middle breaks the chain, and the screen shows where.

</td>
</tr>
<tr>
<td width="50%">

### Path-based policies, `deny` wins

<img src="docs/img/politicas.jpg" alt="Access policies with allow and deny rules per path">

A `deny` rule overrides any `allow`, however specific — that is what makes revocation trustworthy.

</td>
<td width="50%">

### API governance

<img src="docs/img/consumo-api.jpg" alt="API usage screen showing callers, rejected calls and routes">

Who consumes the API from outside, on which routes and with what result. Calls from the app's own UI are excluded.

</td>
</tr>
</table>

<div align="center">

### Built-in walkthroughs on every screen

<img src="docs/img/tour.jpg" alt="Guided tour explaining that the credentials screen does not store the password" width="85%">

</div>

---

## 🚀 Get started in 3 minutes

**Requirement:** [Docker](https://docs.docker.com/get-docker/) with Compose.

```bash
git clone https://github.com/GustavoRSNery/Vault.git
cd Vault
docker compose up -d --build
```

Three containers start: Postgres, the API and the UI. Wait for the healthcheck (~30 s) and create your admin:

```bash
docker compose exec api python -m app.tools.criar_admin you@company.com "YourStrongPassword2026"
```

Open **http://localhost:8080** and sign in.

### With sample data

To see the system populated instead of empty screens:

```bash
docker compose exec -T db psql -U vault -d vault < dados-demo/vault_demo.sql
```

It brings 5 vaults, 8 credentials, 4 certificates, 8 devices and 454 audit events — all fictional. Details in [`dados-demo/LEIA-ME.md`](dados-demo/LEIA-ME.md).

> ⚠️ The dump **replaces** whatever is in the database. Run it before adding your own data.

### Ports

| Service | URL |
| --- | --- |
| UI | http://localhost:8080 |
| API | http://localhost:8777 |
| Interactive docs | http://localhost:8777/docs |
| Postgres | `localhost:55432` |

---

## 🎯 What it does

### Stores secrets the application cannot read on its own

Each secret is encrypted with its own key (DEK), and that key is encrypted by a master key (KEK) — **envelope encryption**. In production the KEK lives in AWS KMS and **never enters the process**: KMS wraps and unwraps on its side.

The configuration **refuses to boot in production without KMS**. With the key in memory, anyone who reads the process can decrypt the whole vault offline — acceptable in development, unacceptable with real people's passwords.

### Controls who can do what, by path

```
cofres/contabil/*                      allow   list, read
cofres/contabil/segredos/token-sefaz   deny    reveal
```

`deny` beats `allow`, however specific the `allow` is. Without that precedence, revoking access would mean hunting down scattered rules.

### Records everything, verifiably

The trail is **append-only and hash-chained**: every event carries the previous one's fingerprint. Deleting or altering a record in the middle breaks the chain, and verification shows where.

> **On the reach of that guarantee:** the chain proves nobody tampered *without re-stitching it*. Whoever controls the application could rebuild the whole chain. The **external anchor** — a record in a destination the Vault cannot alter — closes that gap, and the screen states how much of the trail is anchored.

### Grants temporary access that expires by itself

Instead of permanent access to everything, people **request** access when they need it, for a set period. Once it expires it drops on its own — nobody has to remember to remove it.

### Serves robots without human accounts

RPAs authenticate via **AppRole** (public `role_id` + secret `secret_id`) and receive a short-lived lease. The scope is **frozen at issuance**: changing the policy afterwards does not widen a lease already granted.

### Records SSH sessions

A proxy mediates access: the client connects with the *proxy's* password, and the proxy fetches the target credential from the vault and connects outward. **The target's password never passes through the person accessing it.** Everything typed is recorded with a timeline.

### Audits who consumes the API

Records calls arriving from outside — applications, robots and scripts — with route, result, latency and origin. Calls from the app's own UI are excluded, or they would drown out everything else.

> **Request bodies are never stored.** Not in the database, not in memory: the middleware does not read the input stream. A call that creates a secret carries the password in its body, and logging it would leave it in plaintext outside the vault.

---

## 🏗️ Architecture

### Layers

```
api  →  application  →  domain
                     ↖  infrastructure (implements the ports)
```

The **domain knows nothing** about FastAPI, SQLAlchemy, AWS or React. It defines *ports* (`Protocol`), and infrastructure implements them. Swapping database, SIEM or storage means swapping an adapter.

### What sits behind a port

| Port | Local adapter | Production |
| --- | --- | --- |
| Master key | In-memory key | AWS KMS |
| External trail | JSONL file | SIEM, append-only bucket |
| Session recording | Local disk | S3 with Object Lock |
| Session capture | Manual entry | SSH proxy (`asyncssh`) |
| Webhooks | Dry-run (sends nothing) | Signed HTTP |

How to wire each one: [`docs/conectar-adaptadores.md`](docs/conectar-adaptadores.md) *(in Portuguese)*.

### Stack

| Layer | Technologies |
| --- | --- |
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · Argon2id · `cryptography` · `asyncssh` |
| **Frontend** | React 18 · TypeScript 5.7 · Vite · TanStack Query · hand-written CSS (no framework) |
| **Data** | PostgreSQL 16 (SQLite in tests) |
| **Infra** | Docker Compose · nginx |

---

## 🔌 API

**121 endpoints** across 103 routes. Interactive docs at `/docs` once the containers are up.

```bash
# 1. Authenticate
TOKEN=$(curl -s -X POST localhost:8777/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@company.com","password":"YourPassword"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['tokens']['access_token'])")

# 2. List the vaults your token can reach
curl -s localhost:8777/api/v1/cofres -H "Authorization: Bearer $TOKEN"
```

Filtering happens **server-side**: a vault you lack permission for never appears in the response.

Every screen has a **"Ver pela API"** (View via API) button showing the equivalent endpoints with ready-to-copy `curl`.

### Machine access

```bash
# The robot authenticates and receives a short lease
curl -s -X POST localhost:8777/api/v1/maquina/autenticar \
  -H 'Content-Type: application/json' \
  -d '{"role_id":"...","secret_id":"..."}'

# And reads the secret with the lease token
curl -s -X POST localhost:8777/api/v1/maquina/segredo \
  -H "Authorization: Bearer $LEASE" \
  -H 'Content-Type: application/json' \
  -d '{"cofre":"rh","segredo":"portal-folha"}'
```

---

## ✅ Quality

| | |
| --- | --- |
| **Backend** | 1,000 tests (988 passing, 12 require external services) |
| **Frontend** | 96 tests |
| **Dialects** | The suite runs on SQLite **and** on real Postgres |
| **Types** | `mypy --strict` |
| **Lint** | `ruff` · `eslint --max-warnings 0` |

```bash
# Backend
cd backend && pytest tests/ -q

# Backend on the Postgres dialect (catches divergences SQLite hides)
VAULT_TEST_DATABASE_URL="postgresql+psycopg://vault:vault_local_dev@localhost:55432/vault_test" \
  pytest tests/ -q

# Frontend
cd frontend && npm test
```

> **Why both dialects:** SQLite accepts SQL that Postgres rejects, and vice versa. One such divergence already caused an incident in this project — hence the double gate.

---

## 📚 Documentation

All documents are in Portuguese.

| Document | Covers |
| --- | --- |
| [`docs/conectar-adaptadores.md`](docs/conectar-adaptadores.md) | Wiring KMS, SIEM, S3 and the SSH proxy in production |
| [`docs/governanca-da-api.md`](docs/governanca-da-api.md) | How external usage is recorded, and for how long |
| [`docs/inventario-telas.md`](docs/inventario-telas.md) | The system's screens, one by one |
| [`docs/notas-de-implementacao.md`](docs/notas-de-implementacao.md) | Implementation decisions in detail |
| [`dados-demo/LEIA-ME.md`](dados-demo/LEIA-ME.md) | Restoring and regenerating the sample data |
| [`DIARIO.md`](DIARIO.md) | The reasoning behind each decision, and the mistakes along the way |

---

## ⚠️ Before using in production

This project runs end to end locally. For real use, three points are **not optional**:

1. **KMS** — without it the master key sits in memory, and anyone who reads the process decrypts everything. The configuration already refuses to boot in production without `VAULT_KMS_KEY_ID`.
2. **Externally anchored trail** — the local file proves the flow, not immutability. Point it at a destination the application cannot rewrite.
3. **Secrets outside the repository** — `VAULT_JWT_SECRET` and the database credentials come from the environment or a secrets manager, never from a versioned file.

The keys in `docker-compose.yml` are **development values, public and well known**. Never use them outside your own machine.

---

## 📄 License

[MIT](LICENSE) — use, modify and distribute freely.

<div align="center">
<sub>All sample data, names and certificates in this repository are fictional.</sub>
</div>
