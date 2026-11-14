# LedgerCore — Loan Account & Ledger Service

Phase 3: a local financial backend with borrower registration, loan origination,
deterministic schedules, disbursement, scheduled interest recognition, repayments,
ledger-derived receivables, idempotency, PostgreSQL locking, controlled repayment reversal,
daily overdue penalties and deterministic 5,000-delivery HTTP replay.
Python 3.12+, FastAPI/Pydantic v2, SQLAlchemy 2.x, PostgreSQL 16+, psycopg 3 and Alembic.
INR amounts are integer paise; financial calculations use Decimal.

**Development only.** `X-Demo-User` selects a database-backed demo identity; it is not
proof of identity. Authentication is disabled unless `DEMO_AUTH_ENABLED=true`. Keep the
service on loopback. There is no production authentication, frontend, automatic interest
rebate or re-amortization. Accrual runs explicitly; no resident scheduler is required.

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
[Phase 2 validation](docs/phase2_report.md) and [Phase 3 validation](docs/phase3_report.md).


## Daily overdue accrual

From the repository root, with DATABASE_URL configured in `.env`:

```sh
uv run ledgercore-accrue --business-date 2026-11-14 --catch-up
# Scope a local demo to one already-disbursed loan:
uv run ledgercore-accrue --business-date 2026-11-14 --catch-up --loan-id LOAN_UUID
# Or use the composition's database configuration (Docker execution is environment-dependent):
docker compose run --rm api /app/.venv/bin/ledgercore-accrue --business-date 2026-11-14 --catch-up
```

The job recognizes due contractual interest exactly once through the existing service.
For each UTC day **after** a schedule's due date and after disbursement, it charges
`ROUND_HALF_UP(opening_unpaid_scheduled_principal_paise × 0.0005)`. Repayments processed on
D reduce the basis from D+1. Interest and penalties never form the penalty basis. A daily
zero charge retains an immutable evaluation identity without a journal. Catch-up derives
historical principal from processing-day allocations and reversals, including delayed
receipts; it never uses today's balance for every past day.

With `--catch-up`, every missing eligible day is evaluated. Without it, only the explicit
business date is evaluated. The default horizon is 3,660 days; a larger history requires
an explicit `--max-days` bound. There is one transaction and loan-row lock per loan.
Failures roll back that entire loan, return in `failures`, and cause exit status 1; other
loans may commit. Rerunning resumes missing work and does not duplicate charges. No job
changes old receipts or reallocates historical payments. Penalties are collected once
recognized; run the job before daily repayment processing when a fixed order is desired.

A cron-compatible example (replace repository and uv paths, configure `.env`):

```cron
5 0 * * * cd /absolute/path/to/repository && /absolute/path/to/uv run ledgercore-accrue --business-date "$(date -u +\%F)" --catch-up >> /tmp/ledgercore-accrual.log 2>&1
```

`date -u` supplies the explicit UTC day. This is a documented invocation, not an installed
cron task. CLI calls use the active database manager job identity. Production service
identity and least-privilege permissions remain outside this local demo.

## Deterministic data and real HTTP replay

The data is invented: 250 borrowers, 400 loans, the existing three products and exactly
5,000 delivery events, seed **20261114**, simulation November 1–14, 2026 UTC. Weekly first
periods begin October 27; monthly periods begin October 4/5, with first due dates November
3/4/5. Amounts range from INR 25,000 to INR 150,000. There are no real names, phones or emails.

```sh
# Optional: inspect deterministic inputs and independent expectations without a DB.
uv run ledgercore-generate --output /tmp/ledgercore-generated-inputs
# Requires a local PostgreSQL role with CREATE DATABASE; output must be fresh/empty.
REPLAY_ADMIN_DATABASE_URL=postgresql+psycopg://ledgercore:ledgercore_local@localhost:5432/postgres \
  uv run ledgercore-replay --output artifacts/local-run-001
```

The runner creates a randomly named isolated database, migrates it, starts Uvicorn on a
free loopback port, initializes borrowers/loans/disbursements through HTTP, invokes the
accrual service before each simulation day's deliveries and sends every repayment through
HTTP. It reads PostgreSQL for reconciliation, then stops its server and drops only its own
database. It never clears a developer database or directly inserts repayment rows.
Unexpected outcomes produce a nonzero exit with observed artifacts retained.

| Required category | Count | Subtypes |
| --- | --- | --- |
| Ordinary | 4,200 | New valid deliveries |
| Exact duplicates | 300 | Same original financial payload and key, later delivery time |
| Out of order | 250 | Older economic timestamps after newer accepted events on the same loan |
| Partial/overpayment | 150 | 60 new partials, 60 excessive amounts, 30 separately identified source duplicates of partials |
| Invalid/unauthorized | 100 | 25 zero, 25 negative, 25 auditor mutations, 25 idempotency collisions |

`artifacts/phase3/` contains an **executed** validation run. See its reports for observed
outcomes; generated expectations alone are not evidence of successful posting. Outputs:

- `borrowers.json`, `loans.json`, `products.json`, `events.jsonl`: reproducible invented inputs.
- `scenario_manifest.json`: separate independent Decimal reference expectations, including
  per-delivery allocations and final per-loan principal, interest and penalty totals.
- `identity_map.json`: stable source UUIDv5 IDs mapped to actual API-assigned UUIDs.
- `replay_outcomes.jsonl`: every attempted delivery, status and actual response, including rejections.
- `replay_report.json`: observed counts, timing, environment, hashes and validation results.
- `reconciliation_report.json`: every journal/receipt check, historical daily bases and
  per-loan ledger/operational/reference comparisons.
- `reproducibility_check.json`: comparison of independent executed runs.

The simulation clock is expressed by explicit business dates and input arrival timestamps.
The API retains real server `received_at` and audit timestamps; those are not forged.
Exact retries preserve their original business date, while new delayed deliveries use the
simulated receipt date and retain their old `occurred_at`. Source logical IDs and input
ordering are stable. API-generated UUIDs, real wall-clock timestamps and runtimes vary;
normalized financial hashes exclude those fields. Input files are byte-reproducible.

## Full Phase 3 verification

```sh
TEST_DATABASE_URL=postgresql+psycopg://ledgercore:ledgercore_local@localhost:5432/postgres \
  uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv lock --check
uv run alembic check
```

The full suite includes the existing Phase 1/2 tests, accrual rollback/concurrency tests,
generator/reference checks and an actual 5,000-request TCP HTTP replay in its own database.
Allow roughly one to two minutes locally. Without TEST_DATABASE_URL, all real-database
cases explicitly skip. By default replay test artifacts live in pytest's temporary folder;
set `REPLAY_TEST_OUTPUT` to a fresh directory to retain that particular test run. The
checked-in `artifacts/phase3` was retained this way. Database files and server logs are
not committed; retained files contain invented inputs and reviewable observed results only.
