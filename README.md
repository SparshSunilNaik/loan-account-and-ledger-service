# LedgerCore — Loan Account & Ledger Service

Phase 1 of a modular financial backend: borrower registration, configurable loan products,
loan origination and deterministic repayment schedules. Python 3.12+, FastAPI/Pydantic v2,
SQLAlchemy 2.x, PostgreSQL 16+, psycopg 3 and Alembic. INR amounts are integer paise.

This is a local development service with **no authentication yet**. Keep it on loopback.
No repayment, disbursement, reversal or accrual execution endpoint exists. An originated
loan and its schedule do not imply funds have been disbursed. There are no balance fields.

## Start locally

Install [uv](https://docs.astral.sh/uv/) and Docker with Compose. Clone this repository,
then run from its root:

```sh
cp .env.example .env
uv sync --frozen --python 3.12
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000 --reload
```

The checked-in credentials are public, local-only placeholders; never reuse them in a
shared environment. `.env`, virtual environments, PostgreSQL data and caches are ignored.
Compose binds PostgreSQL and the API to loopback. Wait for the DB health check before
migrating (`docker compose ps`). `uv` can install Python 3.12 if it is unavailable.

Alternatively run all services in containers; migration completion gates API startup:

```sh
docker compose up --build -d
```

With an existing PostgreSQL 16+ installation, create a dedicated database and set
`DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DATABASE` in `.env`.
Alembic, the application and tests use psycopg, not SQLite. Schema creation and product
seeding happen only through migrations, never during server startup.

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Health (checks DB connectivity): http://127.0.0.1:8000/health

## Try the API

```sh
curl -s -X POST http://127.0.0.1:8000/borrowers \
  -H 'Content-Type: application/json' \
  -d '{"external_reference":"BORROWER-001","full_name":"Asha Rao","phone":"+919876543210"}'
curl -s http://127.0.0.1:8000/loan-products
```

Use the returned borrower UUID and a product UUID in:

```sh
curl -s -X POST http://127.0.0.1:8000/loans \
  -H 'Content-Type: application/json' \
  -d '{"external_reference":"LOAN-001","borrower_id":"BORROWER_UUID","product_id":"PRODUCT_UUID","principal_paise":100000,"tenure_periods":12,"first_due_date":"2026-12-31"}'
curl -s http://127.0.0.1:8000/loans/LOAN_UUID
curl -s http://127.0.0.1:8000/loans/LOAN_UUID/schedule
```

| Method | Path | Result |
| --- | --- | --- |
| POST | `/borrowers` | 201; creates borrower and audit event |
| GET | `/borrowers/{id}` | 200; 404 if absent |
| GET | `/loan-products` | Three seeded products, including active flag |
| POST | `/loans` | 201; snapshots terms, writes full schedule and audit event atomically |
| GET | `/loans/{id}` | Origination facts and snapshotted terms |
| GET | `/loans/{id}/schedule` | Rows in instalment order with stable loan UUID |
| GET | `/health` | 200 when DB responds, 503 on DB connection/query failure |

Malformed UUIDs, forbidden extra fields, invalid amounts, inactive/missing product or
borrower references return 422. Missing resources on GET return 404. Duplicate external
references return 409; financial inputs cannot override product rates. Amounts and tenure
must be JSON integers (not booleans, floats or strings). Annual rates serialize as decimal
strings, such as `"0.1200000000"`. No rate floats are accepted by the schedule calculator.

## Verify

```sh
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
# Full suite: local PostgreSQL role must be allowed to CREATE DATABASE.
TEST_DATABASE_URL=postgresql+psycopg://ledgercore:ledgercore_local@localhost:5432/postgres \
  uv run pytest -q
uv run alembic check
```

Without `TEST_DATABASE_URL`, integration tests are **explicitly skipped**; that is not a
full validation. Each full run creates a randomly named database, migrates to head,
checks ORM/schema parity, downgrades to base, asserts removal of all business tables,
then migrates again. Tests use rollback-isolated transactions and per-request sessions;
the fixture drops its temporary database on completion. Never point tests at an
untrusted/shared PostgreSQL server. No existing database is truncated.

The tests include independent flat and EMI examples, 240 boundary combinations,
zero rates, calendar dates, rounding, strict API validation, snapshots, atomicity,
FK integrity, uniqueness and posted-journal guards. Runtime PostgreSQL files stay
outside the repository. A third-party TestClient/AnyIO deprecation warning may appear.

`docker compose down` retains database data. `docker compose down -v` **deletes local
database data**. Alembic downgrades are destructive and intended for disposable development
or test databases, not production rollback procedures.

See [architecture](docs/architecture.md), [financial policies](docs/financial_rules.md),
[phase plan](docs/implementation_plan.md) and [validation report](docs/phase1_report.md).
