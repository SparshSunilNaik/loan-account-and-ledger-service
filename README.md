# LedgerCore — Loan Account & Ledger Service

## Project overview

LedgerCore is a local loan-servicing backend for origination, contractual repayment
schedules, disbursement, collections, overdue penalties, and double-entry accounting. The
database is authoritative for financial records: schedules describe contractual amounts,
while current receivables are calculated from posted ledger entries.

The FastAPI service runs independently. [LedgerCore Studio](frontend/README.md) is an optional
Next.js interface for creating loans, recording repayments, and tracing receipts through
allocations and journals.

## Features

- Weekly and monthly flat-rate schedules and monthly reducing-balance EMI schedules.
- INR stored as integer paise with `Decimal` calculations and `ROUND_HALF_UP` rounding.
- Immutable, balanced journals for disbursement, interest, penalties, repayment and supported
  repayment reversals.
- Repayment allocation to recognized penalties, recognized interest, due principal, then
  future principal.
- Scoped idempotency keys, canonical request fingerprints and source-event deduplication.
- Atomic PostgreSQL transactions, per-loan row locking and timeout-after-commit recovery.
- Daily non-compounding overdue penalties with deterministic UTC business dates.
- Database-backed demo roles and immutable audit events.
- Deterministic synthetic data generation, HTTP replay and independent reconciliation.

## Technology stack

| Area              | Technology                                                             |
| ----------------- | ---------------------------------------------------------------------- |
| Backend           | Python 3.12+, FastAPI, Pydantic v2                                     |
| Database          | PostgreSQL 16+, SQLAlchemy 2, psycopg 3, Alembic                       |
| Backend tooling   | uv, pytest, HTTPX, Ruff                                                |
| Optional frontend | Next.js App Router, TypeScript, React, Tailwind CSS, TanStack Query    |
| Local deployment  | Native processes; Dockerfile and Docker Compose configuration included |

## Architecture

The backend is a modular monolith. Routes own transaction boundaries; schemas validate API
contracts; domain and accounting services implement financial policy; ORM models describe
the relational schema; and database, security, job, and simulation modules isolate
infrastructure concerns.

Thirteen business tables cover borrowers, products, loans, immutable schedules, repayments,
allocations, idempotency records, ledger accounts, journals, entries, accrual records, demo
users, and audit events. Loans snapshot their financial terms at origination. Financial
mutations lock the loan row and commit recognition, receipt, allocations, journal entries,
idempotency response and audit as one transaction. No mutable balance column is authoritative.

## Repository structure

```text
src/ledgercore/       API, schemas, services, accounting, jobs and simulation
migrations/           Alembic environment and five schema revisions
tests/                Unit, PostgreSQL integration, concurrency and replay tests
frontend/             Optional LedgerCore Studio source and browser tests
artifacts/             Deterministic replay inputs, outcomes and reconciliation evidence
openapi/               Committed OpenAPI 3.1 specification
postman/               Collection, environment, schema, license and instructions
scripts/               Local setup, verification, smoke and demonstration utilities
demo.txt               Recording script using the real Studio and API
```

## Installation and setup

Prerequisites are Python 3.12+, [uv](https://docs.astral.sh/uv/), and PostgreSQL 16+.
Node.js 22.12+ and npm are required only for Studio.

```sh
git clone https://github.com/SparshSunilNaik/loan-account-and-ledger-service.git
cd loan-account-and-ledger-service
uv sync --frozen --python 3.12

# Create once; skip if it already exists.
createdb ledgercore
export DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/ledgercore
export DEMO_AUTH_ENABLED=true

uv run alembic upgrade head
uv run alembic check
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000
```

Check the service with `curl -fsS http://127.0.0.1:8000/health`. Migrations seed three loan
products, six ledger accounts and the `demo-officer`, `demo-manager`, and `demo-auditor`
subjects. `X-Demo-User` is development-only impersonation and must not be treated as
production authentication.

To run Studio in another terminal:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open <http://127.0.0.1:3000>. `BACKEND_URL` defaults to
`http://127.0.0.1:8000` and is read only by the Next.js server.

Docker configuration is included as an alternative. Generate a private ignored `.env` with
`uv run python scripts/init_local_env.py`, then run `docker compose up --build`. Docker was
unavailable during final validation, so Compose execution is not claimed as tested.

## API endpoints and documentation

The main endpoints are:

| Method        | Path                                        | Purpose                       |
| ------------- | ------------------------------------------- | ----------------------------- |
| `GET`         | `/health`                                   | Service and database health   |
| `POST`, `GET` | `/borrowers`, `/borrowers/{id}`             | Create and read borrowers     |
| `GET`         | `/loan-products`                            | Read configured products      |
| `POST`, `GET` | `/loans`, `/loans/{id}`                     | Originate and read loans      |
| `GET`         | `/loans/{id}/schedule`                      | Read contractual instalments  |
| `POST`        | `/loans/{id}/disburse`                      | Manager-only disbursement     |
| `POST`, `GET` | `/loans/{id}/repayments`                    | Post and inspect receipts     |
| `GET`         | `/loans/{id}/ledger`, `/loans/{id}/balance` | Read journals and receivables |
| `POST`        | `/loans/{id}/journals/{journal_id}/reverse` | Reverse a repayment journal   |
| `GET`         | `/audit-events`                             | Manager/auditor audit history |

With the API running, Swagger is available at <http://127.0.0.1:8000/docs> and ReDoc at
<http://127.0.0.1:8000/redoc>. The committed [OpenAPI specification](openapi/openapi.json) and
[Postman assets](postman/README.md) provide portable API documentation and executable checks.

## Synthetic dataset and replay

The retained evidence under `artifacts/` contains 250 invented borrowers, 400 loans,
three products and exactly 5,000 repayment delivery attempts generated with seed `20261114`.
The observed run recorded 4,510 new repayments, 330 duplicate responses, 160 rejected
deliveries, 250 accepted out-of-order events and 9,903 posted journals. Total debits and
credits were each 3,641,480,368 paise, with zero unbalanced journals and no reported
principal, interest or penalty reconciliation differences.

Generate inputs and execute a new isolated replay with fresh output directories:

```sh
uv run ledgercore-generate --output /tmp/ledgercore-inputs-new
export REPLAY_ADMIN_DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/postgres
uv run ledgercore-replay --output /tmp/ledgercore-replay-new
```

The replay creates and drops its own randomly named database and submits delivery events
through HTTP. Never point its output at the retained evidence directory.

## Testing

The PostgreSQL role used for backend tests must be able to create temporary databases.

```sh
export TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/postgres
uv sync --frozen --python 3.12
uv run pytest -q
uv run ruff check src migrations scripts tests
uv run ruff format --check src migrations scripts tests
uv lock --check
uv run --with openapi-spec-validator==0.7.2 --with jsonschema==4.25.1 \
  python scripts/verify_submission.py
```

Frontend checks require PostgreSQL, FastAPI and Studio to be running:

```sh
cd frontend
npm ci
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
npm run test:e2e
```

The most recent validation passed 398 backend tests, 36 frontend unit/component tests, 22
live Chrome workflow tests and two offline-state browser tests. The backend suite includes
real PostgreSQL concurrency cases and a complete 5,000-request replay. One dependency-level
Starlette/AnyIO deprecation warning remains.

## Limitations

- Demo header authentication does not verify identity or provide tenant, borrower-ownership,
  or officer-assignment isolation.
- Only repayment journals support reversal; disbursement and recognition reversals are
  intentionally rejected.
- Current receivables are ledger-derived but are not automatically a future payoff quote.
- Studio uses browser-known loan references because the backend has no portfolio search API.
- Docker/Compose execution was not verified in the final environment; native PostgreSQL was.
