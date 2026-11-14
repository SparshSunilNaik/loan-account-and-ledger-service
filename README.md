# LedgerCore — Loan Account & Ledger Service

Phase 2: a local financial backend with borrower registration, loan origination,
deterministic schedules, disbursement, scheduled interest recognition, repayments,
ledger-derived receivables, idempotency, PostgreSQL locking and controlled repayment reversal.
Python 3.12+, FastAPI/Pydantic v2, SQLAlchemy 2.x, PostgreSQL 16+, psycopg 3 and Alembic.
INR amounts are integer paise; financial calculations use Decimal.

**Development only.** `X-Demo-User` selects a database-backed demo identity; it is not
proof of identity. Authentication is disabled unless `DEMO_AUTH_ENABLED=true`. Keep the
service on loopback. No production authentication, synthetic replay, scheduled overdue
accrual, penalty generator, automatic interest rebate or re-amortization is included.

## Start locally

Install [uv](https://docs.astral.sh/uv/) and Docker with Compose, then run from the root:

```sh
cp .env.example .env
uv sync --frozen --python 3.12
docker compose up -d db
# Wait for the database health check: docker compose ps
uv run alembic upgrade head
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000 --reload
```

Or run `docker compose up --build -d`; migration completion gates API startup. Compose
binds both services to loopback and explicitly enables demo authentication for the API.
The checked-in database credentials are local placeholders. Never reuse them elsewhere.
`.env`, environments and runtime data are ignored. Production identity and deployment
hardening are outside this take-home phase.

With native PostgreSQL 16+, create a dedicated database and put
`DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DATABASE` and
`DEMO_AUTH_ENABLED=true` in `.env`. Schema, six ledger accounts, three products and three
demo users are installed through migrations, never at application startup. Existing
Phase 1 loan terms and schedules survive upgrade. Original migrations remain unchanged.

- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Health: http://127.0.0.1:8000/health (public, checks DB connectivity)

## Demo identities

| X-Demo-User | Database role | Permissions |
| --- | --- | --- |
| demo-officer | loan_officer | Create borrowers/loans, post repayments, read all demo loans/financial records |
| demo-manager | manager | Officer permissions plus disbursement, repayment reversal, audit history |
| demo-auditor | auditor | Read loan/financial records and audit history; no mutations |

Roles cannot be selected with headers. Missing, unknown or inactive users and denied
roles return 403; disabled demo authentication returns 503. Health, Swagger and OpenAPI
are public. This demo has no per-borrower or tenant ownership restrictions.

## API

All paths below except health require a demo identity.

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/borrowers` | 201; borrower and actor audit |
| GET | `/borrowers/{id}` | Borrower details |
| GET | `/loan-products` | Three configurable products |
| POST | `/loans` | 201; immutable terms and full schedule, atomic audit |
| GET | `/loans/{id}` | Origination facts; no cached financial balance |
| GET | `/loans/{id}/schedule` | Original schedule, unchanged by payments |
| POST | `/loans/{id}/disburse` | 201; manager-only, one disbursement |
| POST | `/loans/{id}/repayments` | 201; requires Idempotency-Key; successful retries return original body/status |
| GET | `/loans/{id}/repayments` | Receipts, historical allocations and current posted/reversed status |
| GET | `/loans/{id}/ledger` | Posted journals and entries, including reversals |
| GET | `/loans/{id}/balance` | Posted principal/interest/penalty receivables, computed from entries |
| GET | `/audit-events?limit=100&offset=0` | Manager/auditor history, bounded pagination |
| POST | `/loans/{id}/journals/{journal_id}/reverse` | Manager-only repayment reversal; 200, idempotent by original journal |
| GET | `/health` | 200 if DB responds, 503 otherwise |

Financial mutations require an explicit `business_date` (`YYYY-MM-DD`). Due interest is
recognized through that UTC business date before repayment allocation. Dates may simulate
historical processing, but cannot precede a previously posted operation on the loan.
`occurred_at` is a timezone-aware economic timestamp; its UTC date cannot follow the
business date. It may be older than other arrivals. No historical balance endpoint exists.
GET balance is a read of **currently posted** receivables: it does not recognize additional
due interest and is not a payoff quote for an arbitrary later date.

Repayments allocate oldest recognized penalties, oldest recognized interest, oldest due
unpaid principal, then future principal. Future interest is never collected. Early principal
payment keeps the contractual schedule and future interest intact. Loan status stays
`disbursed` even when current receivables are zero because future interest may remain.

Malformed inputs return 422, overpayments 400, denied roles 403, absent resources 404,
and lifecycle/idempotency/date/constraint conflicts 409. Financial amounts/tenure require
JSON integers; booleans, floats and strings are rejected. Annual rates serialize as Decimal
strings. Optional `X-Correlation-ID` accepts 1..100 safe identifier characters and is echoed;
a generated UUID is used otherwise. Invalid correlation IDs return 400.

## Example flow

```sh
curl -s -X POST http://127.0.0.1:8000/borrowers \
  -H 'X-Demo-User: demo-officer' -H 'Content-Type: application/json' \
  -d '{"external_reference":"BORROWER-001","full_name":"Asha Rao"}'
# Substitute the borrower UUID returned above.
curl -s -X POST http://127.0.0.1:8000/loans \
  -H 'X-Demo-User: demo-officer' -H 'Content-Type: application/json' \
  -d '{"external_reference":"LOAN-001","borrower_id":"BORROWER_UUID","product_id":"00000000-0000-0000-0000-000000000002","principal_paise":10000,"tenure_periods":2,"first_due_date":"2026-01-31"}'
curl -s -X POST http://127.0.0.1:8000/loans/LOAN_UUID/disburse \
  -H 'X-Demo-User: demo-manager' -H 'Content-Type: application/json' \
  -d '{"business_date":"2026-01-01"}'
curl -s -X POST http://127.0.0.1:8000/loans/LOAN_UUID/repayments \
  -H 'X-Demo-User: demo-officer' -H 'Content-Type: application/json' -H 'Idempotency-Key: receipt-001' \
  -d '{"amount_paise":1000,"source":"manual-demo","external_event_id":"BANK-001","occurred_at":"2026-01-31T10:00:00Z","business_date":"2026-01-31"}'
curl -s http://127.0.0.1:8000/loans/LOAN_UUID/balance -H 'X-Demo-User: demo-auditor'
# Substitute the repayment journal UUID, not the disbursement or recognition journal.
curl -s -X POST http://127.0.0.1:8000/loans/LOAN_UUID/journals/JOURNAL_UUID/reverse \
  -H 'X-Demo-User: demo-manager' -H 'Content-Type: application/json' \
  -d '{"business_date":"2026-01-31","reason":"Bank settlement reversed"}'
```

The repayment example recognizes 100 paise of interest, collects it and applies 900 paise
to principal. Balance becomes principal 9100, interest 0. Reversal restores principal
10000 and interest 100. Same-key or same-source-event retries after reversal return the
historical successful receipt response and never re-post it; GET receipts shows `reversed`.

## Verify

```sh
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv lock --check
uv run pytest -q
TEST_DATABASE_URL=postgresql+psycopg://ledgercore:ledgercore_local@localhost:5432/postgres \
  uv run pytest -q
uv run alembic check
# Against a running local server backed by a DISPOSABLE demo database:
uv run python scripts/smoke_http.py --base-url http://127.0.0.1:8000
```

Without `TEST_DATABASE_URL`, PostgreSQL tests explicitly skip; that is not full validation.
The test role needs CREATE DATABASE. Tests create random disposable databases, run real
migrations (including downgrade/re-upgrade and a populated Phase 1 upgrade), and drop only
the databases they create. Ordinary tests roll back their data. Concurrency tests use
separate disposable databases and independent committed sessions per HTTP request.
The live smoke script creates two demo loans and financial history; it does not delete them.
Twenty-request overlap/duplicate tests and observed PostgreSQL lock waits verify the actual
locking behavior. One upstream TestClient/AnyIO deprecation warning may be emitted.

`docker compose down` retains data. `docker compose down -v` deletes the local database.
Downgrades are destructive and intended for disposable databases; Phase 2 history is not
safe to downgrade in place to a version without its reversal and allocation semantics.

See [architecture](docs/architecture.md), [financial policy](docs/financial_rules.md),
[phase plan](docs/implementation_plan.md), [Phase 1 validation](docs/phase1_report.md)
and [Phase 2 validation](docs/phase2_report.md).
