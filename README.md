# LedgerCore — Loan Account & Ledger Service

LedgerCore is a local financial backend for loan origination, contractual schedules,
double-entry posting, repayment allocation, daily overdue penalties, and deterministic event
replay. It was built as a take-home assignment with an emphasis on exact monetary arithmetic,
database transaction boundaries, and evidence that can be independently inspected.

The FastAPI backend runs independently. [LedgerCore Studio](frontend/README.md) is an optional
Next.js interface for manually exploring the same API and financial records.

## Key capabilities

- Flat-rate weekly/monthly and reducing-balance monthly schedules with exact principal totals.
- Integer-paise storage and `Decimal` calculations with `ROUND_HALF_UP` to one paisa.
- Balanced, immutable journals for disbursement, interest recognition, penalties and repayment.
- Ledger-derived receivables; no mutable cached balance is the financial authority.
- Penalty, interest, due-principal and future-principal repayment allocation.
- Scoped idempotency keys, source-event deduplication and timeout-after-commit recovery.
- PostgreSQL row locks and atomic caller-owned financial transactions.
- Database-backed demo roles, audit events and controlled repayment-journal reversal.
- Deterministic generator and actual 5,000-delivery HTTP replay with reconciliation artifacts.

## Architecture and technology stack

LedgerCore is a modular monolith. FastAPI routes own transaction boundaries; Pydantic v2
defines API contracts; domain and accounting services implement policy; SQLAlchemy 2 maps the
PostgreSQL schema; and Alembic applies versioned migrations. The 13 business tables cover
borrowers, products, loans, immutable schedules, receipts and allocations, idempotency,
accounts, journals and entries, accruals, users and audit events.

| Layer | Technology |
| --- | --- |
| API and validation | Python 3.12+, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL 16+, SQLAlchemy 2, psycopg 3, Alembic |
| Backend quality | pytest, HTTPX, Ruff, uv |
| Optional Studio | Next.js App Router, TypeScript, React, Tailwind CSS, TanStack Query |
| Local packaging | Dockerfile and Docker Compose configuration (not execution-verified) |

The detailed design is documented in [architecture.md](docs/architecture.md) and
[financial_rules.md](docs/financial_rules.md).

## Repository structure

```text
src/ledgercore/       FastAPI routes, schemas, services, accounting, jobs and simulation
migrations/           Alembic configuration and five schema revisions
tests/                Backend unit, PostgreSQL integration, concurrency and replay tests
artifacts/phase3/      Deterministic inputs, all 5,000 outcomes and reconciliation evidence
docs/                 Architecture, policies, OpenAPI, Postman and submission evidence
frontend/             Optional LedgerCore Studio source and browser tests
scripts/              Environment, smoke-test, demo and verification utilities
demo.txt              5–7 minute recording script
```

## Prerequisites

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 or newer; the test role must be able to create temporary databases
- Node.js 22.12 or newer and npm for Studio
- Optional: Chrome or Playwright Chromium for browser tests

The validated path uses native PostgreSQL on loopback. Adapt connection URIs to your local
role, password and port. Never commit `.env` files or use real customer data.

## Backend setup and execution

```sh
git clone https://github.com/SparshSunilNaik/loan-account-and-ledger-service.git
cd loan-account-and-ledger-service
uv sync --frozen --python 3.12

# Create once; skip this command if the database already exists.
createdb ledgercore
export DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/ledgercore
export DEMO_AUTH_ENABLED=true

uv run alembic upgrade head
uv run alembic check
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000
```

Verify the service with `curl -fsS http://127.0.0.1:8000/health`. Migrations seed three loan
products, six ledger accounts and `demo-officer`, `demo-manager`, and `demo-auditor` users.
`X-Demo-User` is development-only impersonation; it is not production authentication.

An alternative Compose configuration is included. Generate a private ignored environment
with `uv run python scripts/init_local_env.py`, then use `docker compose up --build`. Docker was
unavailable during final verification, so image and Compose execution are not claimed as tested.
Do not run `docker compose down -v` unless deleting that Compose database is intentional.

## Frontend Studio setup (optional)

Keep the backend running, then open a second terminal:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open <http://127.0.0.1:3000>. The Next.js server proxies its allowlisted API requests to
`BACKEND_URL`, which defaults to `http://127.0.0.1:8000`. Studio retains the selected local
loan, supports Light/Dark/System themes, and exposes the real schedule, receipts, journals,
balances and audit records. It does not invent portfolio statistics or financial balances.

## API documentation and Postman

With FastAPI running:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Live schema: <http://127.0.0.1:8000/openapi.json>
- Committed [OpenAPI 3.1 specification](docs/openapi.json)
- [Postman collection](docs/postman/ledgercore.postman_collection.json),
  [local environment](docs/postman/local.postman_environment.json), and
  [run guide](docs/postman/README.md)

The API supports borrower and loan origination, schedule reads, disbursement, repayment,
ledger/balance reads, audit reads and manager-controlled repayment reversal. Exact request and
response contracts are authoritative in OpenAPI.

## Synthetic dataset and replay

The committed [Phase 3 artifacts](artifacts/phase3/) use seed `20261114`: 250 invented
borrowers, 400 loans, three products and exactly 5,000 delivery attempts. The retained run
observed 4,510 new repayments, 330 duplicate responses, 160 rejections, 250 accepted
out-of-order events and 9,903 posted journals. Debits and credits were each 3,641,480,368
paise, with zero unbalanced journals and no reported principal, interest or penalty differences.

Generate inputs or execute a new isolated replay with fresh output paths:

```sh
uv run ledgercore-generate --output /tmp/ledgercore-inputs-new
export REPLAY_ADMIN_DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/postgres
uv run ledgercore-replay --output /tmp/ledgercore-replay-new
```

The replay creates and drops its own random database and submits deliveries through HTTP.
The output directory must be absent or empty. Retained evidence is never overwritten.

## Testing and verification

Backend validation requires a PostgreSQL administration database:

```sh
export TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/postgres
uv sync --frozen --python 3.12
uv run pytest -q
uv run ruff check src migrations scripts tests
uv run ruff format --check src migrations scripts tests
uv lock --check
uv run --with openapi-spec-validator==0.7.2 python scripts/verify_submission.py
```

Frontend validation, with PostgreSQL, FastAPI and Studio running:

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

The final cleanup validation passed 398 backend tests, 36 frontend unit/component tests and
22 live Chrome workflow tests; the two offline-state browser tests also passed separately.
The backend suite uses real PostgreSQL and includes a complete 5,000-request replay. One
Starlette/AnyIO deprecation warning remains in the test dependency stack.

## Demo video instructions

[demo.txt](demo.txt) is a complete 6:15 operator and narration script. It uses an invented
₹100 reducing-balance loan and a ₹10 partial repayment, then demonstrates allocation,
double-entry posting, exact retry, a 409 payload conflict, auditor denial, audit history and
the retained replay results. Use a fresh recording database as instructed; do not reset an
existing database merely to repeat the video.

The shorter curl-based walkthrough remains in [docs/demo.md](docs/demo.md) and can be run with:

```sh
BASE_URL=http://127.0.0.1:8000 sh scripts/demo.sh
```

## Design decisions and limitations

- Contractual schedules remain unchanged after posting; receivables and receipts are distinct.
- Monthly dates retain the original day where possible and clamp invalid month-end dates.
- Repayment allocation is penalties, recognized interest, due principal, then future principal.
- Daily penalty is 0.05% of opening unpaid overdue scheduled principal without compounding.
- A zero posted balance is not automatically a payoff quote or a closed-loan decision.
- Demo authentication does not verify identity or enforce tenant/borrower ownership.
- Only repayment journals support reversal; disbursement and recognition reversals are rejected.
- Docker/Compose was not tested in the final environment; native PostgreSQL was.

A realistic next step is verified OIDC identity with tenant-scoped authorization and
least-privilege database roles, followed by deployment and recovery testing.

## Submission deliverables

- [Overleaf-ready LaTeX technical write-up](docs/technical_writeup.tex)
- Existing [Markdown summary](docs/technical_writeup.md) and PDF (retained pending owner update)
- [Architecture](docs/architecture.md), [financial policy](docs/financial_rules.md), and
  [implementation history](docs/implementation_plan.md)
- [OpenAPI](docs/openapi.json) and [Postman assets](docs/postman/)
- [Automated tests](tests/) and optional [Studio tests](frontend/tests/)
- [Generator and replay implementation](src/ledgercore/simulation/) with
  [actual replay evidence](artifacts/phase3/)
- [Demonstration script](demo.txt)

No final repository ZIP is generated or committed by this cleanup. The existing
`docs/technical_writeup.pdf` is intentionally unchanged so the author can edit the LaTeX in
Overleaf and add the final exported PDF separately.
