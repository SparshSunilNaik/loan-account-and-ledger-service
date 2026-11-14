# LedgerCore - Loan Account & Ledger Service

A modular Python/FastAPI/PostgreSQL backend for loan origination, deterministic schedules,
double-entry posting, repayments, daily overdue penalties and a real 5000-delivery replay.
INR amounts are integer paise; calculations use Decimal. No authoritative cached balance
is stored. Phases 1-3 implement the engine; Phase 4 supplies the verified submission assets.

**Local demo only:** X-Demo-User impersonates a database-backed demo subject. It is not
production authentication. Keep the service on loopback. No frontend or cloud service is
required. See the [one-page technical summary](docs/technical_writeup.pdf).

## Start with native PostgreSQL (validated path)

Install uv and PostgreSQL 16+ and start your local database server. From this repository:

```sh
uv sync --frozen --python 3.12
createdb ledgercore
# Use your own local connection URI if authentication/port differs.
export DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/ledgercore
export DEMO_AUTH_ENABLED=true
uv run alembic upgrade head
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000
```

Migrations create the schema, three products, six accounts and the three demo subjects.
No seeding or schema creation occurs on application startup. This submission was tested
with Python 3.12.13 and native PostgreSQL 17.11. The validation cluster used a separate
local port; the commands above show the usual 5432 default.

## Alternative: Docker Compose

```sh
uv sync --frozen --python 3.12
uv run python scripts/init_local_env.py
docker compose up -d --wait db
uv run alembic upgrade head
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000
# Or run migrations and API in containers:
# docker compose up --build -d
```

The helper creates a private, ignored `.env` with a fresh local password and never
replaces an existing file. `.env.example` is a template, not a supplied credential.
Existing `.env` users must supply POSTGRES_PASSWORD before using the updated composition.
Compose binds ports to loopback; migration completion gates container API startup.
**Docker was unavailable during final validation; image build and Compose execution were
not tested.** `docker compose down -v` deletes its local database volume.

## Review and demonstrate

- [OpenAPI 3.1 export](docs/openapi.json), live [Swagger](http://127.0.0.1:8000/docs)
  and [OpenAPI](http://127.0.0.1:8000/openapi.json).
- [Postman collection](docs/postman/ledgercore.postman_collection.json),
  [environment](docs/postman/local.postman_environment.json) and [import/run guide](docs/postman/README.md).
- [Five-minute demo and actual curl commands](docs/demo.md):

```sh
BASE_URL=http://127.0.0.1:8000 sh scripts/demo.sh
```

| Demo subject | Permissions |
| --- | --- |
| demo-officer | Create borrowers/loans, post repayments, read demo financial records |
| demo-manager | Officer permissions plus disbursement, repayment reversal and audit history |
| demo-auditor | Read-only financial and audit access |

Roles come from active database users, never role headers. All demo users can read all
loans; tenant/borrower ownership scoping is not implemented. Health, Swagger, ReDoc and
OpenAPI are public. Missing/inactive/unauthorized subjects return 403; disabled demo auth
returns 503 on protected routes. Financial amounts reject float/string/bool coercions.

Implemented API: POST/GET borrowers; GET loan products; POST/GET loans; GET schedule;
POST disbursement; POST/GET repayments; GET ledger; GET balance; GET audit-events;
manager POST repayment-journal reversal; GET health. Exact paths and request contracts
are in OpenAPI and the collection. Expected validation/lifecycle errors use 400/403/404/409/422.

## Verify and replay

Use a PostgreSQL role with CREATE DATABASE for isolation. These tools create/drop only
their own randomly named databases; never clear a developer database.

```sh
# Adapt the URI to your own PostgreSQL role/port/password.
export TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/postgres
uv run pytest -q
uv run ruff check src migrations scripts tests
uv run ruff format --check src migrations scripts tests
uv lock --check
uv run alembic check
uv run python scripts/smoke_http.py --base-url http://127.0.0.1:8000
```

Without TEST_DATABASE_URL, real-database tests explicitly skip; that is not full validation.
The full suite includes real row-lock/concurrency cases and a 5000-request TCP HTTP replay;
allow roughly one to two minutes. Smoke/demo tools create invented history in the running
demo DB. One existing TestClient/AnyIO dependency deprecation warning may appear.

```sh
uv run ledgercore-generate --output /tmp/ledgercore-inputs
export REPLAY_ADMIN_DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/postgres
uv run ledgercore-replay --output artifacts/local-run-001
uv run ledgercore-accrue --business-date 2026-11-14 --catch-up
```

Replay output must be fresh/empty. It creates its own DB/server and submits all receipts
through HTTP. The generator uses seed 20261114, 250 invented borrowers, 400 loans, three
products and exactly 5000 deliveries. [Retained actual evidence](artifacts/phase3/replay_report.json):
4510 new receipts, 330 duplicate responses and 160 rejections; 250 intended out-of-order
accepted deliveries; 9903 balanced journals; zero reconciliation differences. The dataset,
independent manifest, every actual response and reconciliation are committed under
`artifacts/phase3/`. Simulation dates are fixed; actual server receipt timestamps are retained.

## Financial policies and submission

Penalties are 0.05% of opening unpaid overdue scheduled principal per UTC day, rounded
half-up independently. No interest/penalty compounding. Same-day principal payments affect
D+1. Zero-charge identities remain without journals. Catch-up uses historical processing
and reversal dates; late jobs never reallocate previous receipts. Run jobs before daily
repayments for a fixed processing order. [Job and cron invocation](docs/financial_rules.md#phase-3-daily-overdue-policy)
uses an explicit date; no resident scheduler is required.

Schedules stay immutable. Repayment collects recognized penalties, recognized interest,
due principal, then future principal. No future interest collection, automatic rebate or
re-amortization. GET balance reads posted receivables, not a future payoff quote. Only
repayment reversals are supported. Financial-history downgrades are not a live rollback plan.

- [Architecture](docs/architecture.md) · [Financial rules](docs/financial_rules.md) · [Implementation history](docs/implementation_plan.md)
- [Technical write-up](docs/technical_writeup.md) · [Independent review](docs/submission/review.md)
- [Final checklist](docs/submission/checklist.md) · [Final validation](docs/submission/verification.json)
- [Exact submission file list](docs/submission/included_files.txt)

```sh
uv run --with openapi-spec-validator==0.7.2 python scripts/verify_submission.py
uv run python scripts/build_submission.py
```

The ZIP and SHA-256/member manifest are generated under ignored `dist/`; the complete
contents remain in Git. No `.git`, `.venv`, database runtime files, `.env` or caches are
packaged. Replay works without Git; revision metadata is null in that case, with source
and financial fingerprints retained. Stop at Phase 4; remaining limitations are explicit
in the checklist and independent review.

## Final demo and submission package

[Recording script](demo.txt) is a complete 6:15 operator/narration guide, including safe local
preparation, actual Studio labels and a verified ₹100 loan / ₹10 repayment example.
[Demo verification](docs/submission/demo_verification.json) records the fresh disposable-database
Chrome rehearsal, PostgreSQL suite, frontend checks, live API and replay comparisons.
[Requirement review](docs/submission/finalization.md) lists the delivered backend scope and
limitations. Earlier verification files remain historical evidence.

The optional [LedgerCore Studio](frontend/README.md) source and screenshots are maintained on
GitHub separately from the backend-only ZIP. Use the full checkout for frontend recording;
the archive runs independently through FastAPI, Swagger, Postman and the curl demo.
The video itself still needs to be recorded. The technical write-up is unchanged.

Run `uv run python scripts/build_submission.py` to back up the previous ZIP and regenerate
`dist/ledgercore-submission.zip`, its exact inventory, member manifest and SHA-256 files.
Check them with `shasum -a 256 -c dist/SHA256SUMS`. Fresh-extraction validation is recorded in
adjacent `dist/zip_validation.json`. Archives/backups remain ignored local submission outputs;
committing source does not publish the ZIP or submit to an external portal.
