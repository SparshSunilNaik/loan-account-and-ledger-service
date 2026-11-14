# Phase 2 delivery and validation

Continued from `3143757c9cac9e3a53e30bcd9d08499dcfb855d5`. Validated locally on
14 November 2026 with Python 3.12.13, uv 0.11.8 and real PostgreSQL 17.11.
Phase 1 documentation, migrations and all existing tests were read before implementation.
No Phase 3 replay, synthetic dataset, scheduled overdue job or penalty generator was built.

## Implemented behavior

- Six-account immutable chart, balanced posted journals and ledger-derived receivables.
- One-time manager disbursement with atomic loan status/journal/audit.
- Independently callable due scheduled interest recognition, unique per schedule; invoked
  inside repayment processing before allocation. Explicit UTC business dates and no future
  interest collection. Zero-interest recognition is a no-op, not a zero-entry journal.
- Penalty/interest recognized-lot FIFO, due principal then future principal, with per-schedule
  and aggregate principal capacity checks under a PostgreSQL loan-row lock.
- Canonical request hash, actor/operation key scope, source-event deduplication and stored
  original 201 responses. Retries after a committed response is lost never post again.
- Separate caller-owned atomic transactions; whole-operation retries for uniqueness,
  deadlock and serialization races; sanitized client conflicts.
- Database-backed demo subjects, role authorization and actor/correlation audit. Identity
  headers are development impersonation only; demo mode is disabled by default.
- Exact repayment journal reversals, preserving original receipt/allocation/journal history,
  deriving current reversed status and restoring operational capacity and ledger balances.
- Stronger database guards for journal entry races, origin/schedule linkage, immutable loan
  terms/schedules/receipts/allocations/chart/audit and completed idempotency snapshots.

New endpoints are POST loan disbursement, POST/GET loan repayments, GET loan ledger,
GET loan balance, GET audit-events, and POST loan journal reversal (repayments only).
Existing endpoints remain available with the explicitly required role protection.
See README for exact paths, request contracts, roles and status codes.

## Accounting example (paise)

A 10000-paise principal loan at annual 12%, two monthly periods, first due January 31:

| Journal | Debit | Credit |
| --- | --- | --- |
| Disbursement | LOAN_PRINCIPAL_RECEIVABLE 10000 | CASH 10000 |
| January interest | INTEREST_RECEIVABLE 100 | INTEREST_INCOME 100 |
| Repayment of 1000 | CASH 1000 | INTEREST_RECEIVABLE 100; LOAN_PRINCIPAL_RECEIVABLE 900 |
| Repayment reversal | INTEREST_RECEIVABLE 100; LOAN_PRINCIPAL_RECEIVABLE 900 | CASH 1000 |

Principal/interest are 9100/0 after repayment and 10000/100 after reversal. Contractual
schedule rows stay unchanged. Future February interest of 50 is not recognized in January.
This flow was verified through both tests and live HTTP.

## Automated test results

- Full Phase 1 + Phase 2 suite: **362 passed, 0 failed, 0 skipped**.
- Default run without TEST_DATABASE_URL: **268 passed, 94 skipped, 0 failed**. Integration
  skips are explicit; this default run alone is not full validation.
- The 315 Phase 1 tests remain, with fixture authentication, seeded-account reuse, new
  migration head and expanded OpenAPI assertions adapted to the authorized Phase 2 change.
- 47 added tests cover posting, recognition, prepayment, deduplication, RBAC, UTC audit,
  exact reversal, immutability, injected rollback and concurrency/migration behavior.
- One pre-existing dependency warning remains: Starlette TestClient references the
  deprecated AnyIO BlockingPortal alias. Warnings are not suppressed.

Fresh PostgreSQL migration, schema comparison, base downgrade/empty-schema assertion and
re-upgrade passed. A separate populated Phase 1 origination upgrade retained schedule UUIDs,
principal, interest and loan status. Original Phase 1 migrations were not edited.

Early validation caught a UUID parameter cast in seed SQL, host-local timestamp rendering
and a missing import in an added concurrency test. These were corrected before the final
passing run. Final Ruff lint/format and uv lock/frozen synchronization checks passed.

## Parallel request results

Concurrency tests launch independent committed SQLAlchemy sessions through parallel HTTP
requests against real PostgreSQL; startup barriers synchronize requests, not financial writes.

| Scenario | Observed outcome |
| --- | --- |
| Two receipts of 6000, principal 10000 before due | One 201, one 400; principal 4000 |
| Twenty receipts of 1000 before due | Ten 201, ten 400; principal 0 |
| Twenty receipts of 1000 on first due date | Ten 201, ten 400; principal 100; interest recognized exactly once and collected |
| Twenty identical deliveries, same key | Twenty identical 201 responses; one receipt/journal/key |
| Twenty identical source events, distinct keys | Twenty identical 201 responses; one receipt/journal; twenty successful key aliases |
| Shared source event across two loans | One 201, one sanitized 409; combined principal 19000 |
| Shared actor/key across two loans | One 201, one sanitized 409; combined principal 19000 |
| Concurrent disbursements | One 201, one 409; one disbursement |
| Concurrent reversal retries | Two identical 200 responses; one reversal and one restoration |
| Externally held loan row lock | HTTP posting observed waiting in pg_stat_activity until real PostgreSQL lock release |

All checked journals balanced and individual/aggregate principal allocations stayed within
contractual limits. Lost-response retry tests return the original successful body/status;
different canonical payloads conflict. Same-key and source aliases after reversal retain
the historical response without reinstating or duplicating the receipt.

## Live HTTP and commands

The committed `scripts/smoke_http.py` was run against an actual Uvicorn server on loopback,
using a fresh migrated database. It verified docs/OpenAPI, missing identity denial,
origination/disbursement, twenty competing repayments, current balances, journal balance,
recognition, retry/key conflict/source deduplication, auditor mutation denial, actor audit,
overpayment rejection and idempotent manager reversal. All assertions passed.

Live twenty-request result: **10 accepted, 10 rejected, final principal 0**. A final direct
SQL reconciliation found **zero unbalanced posted journals**. Alembic found no schema drift
after live mutations. The smoke server and temporary native PostgreSQL cluster were stopped.

Principal validation commands actually executed:

```sh
uv sync
uv sync --frozen
uv lock --check
initdb -D "$TEMP_PG_DIR" -A trust --no-locale -E UTF8
pg_ctl -D "$TEMP_PG_DIR" -l "$TEMP_PG_DIR/server.log" -o '-h 127.0.0.1 -p 55432' start
createdb -h 127.0.0.1 -p 55432 ledgercore_phase2_verified
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_phase2_verified uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_phase2_verified uv run alembic check
TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/postgres uv run pytest -q --tb=short
uv run pytest -q --tb=short
uv run ruff check --fix .
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_phase2_verified DEMO_AUTH_ENABLED=true uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 58000
uv run python scripts/smoke_http.py --base-url http://127.0.0.1:58000
git diff --check
```

Additional inline Python parsed Compose YAML and queried live journal reconciliation.
The pytest database fixture executes Alembic upgrade/check/downgrade/upgrade. Git commit,
push, remote SHA and working-tree status are reported in the handoff; a commit cannot
include its own SHA.

## Remaining limitations

- Docker is unavailable. Compose YAML and the demo flag parsed correctly, but image build,
  Compose startup and PostgreSQL 16 container execution were **not tested**. Native real
  PostgreSQL 17 validation succeeded; there is no SQLite substitution.
- Header identity is not production authentication. All demo users can read all loans;
  production identity, ownership scoping and least-privilege database permissions are absent.
- Only repayment reversals are supported. Disbursement/recognition reversals and reversal
  chains are rejected. No automatic loan closure is performed.
- Prepayment keeps original contractual interest; no rebate or re-amortization applies.
- No overdue-charge generation, scheduled job, synthetic replay or historical restatement.
  GET balance reads current posted receivables and never recognizes due interest itself.
- Aggregate allocation correctness depends on the serialized posting service contract;
  privileged raw inserts can bypass cross-row operational rules. Corrupt/legacy unmatched
  receivables fail reconciliation rather than being silently allocated.
- Phase 2 history is not safe to downgrade to Phase 1 in a live database. The tested
  downgrade/re-upgrade loop uses disposable databases.

## Files changed

```text
.env.example
README.md
docker-compose.yml
docs/architecture.md
docs/financial_rules.md
docs/implementation_plan.md
docs/phase2_report.md
migrations/env.py
migrations/versions/0004_posting_guards.py
migrations/versions/cf6472690571_financial_posting_identities_and_demo_.py
pyproject.toml
scripts/smoke_http.py
src/ledgercore/accounting/contracts.py
src/ledgercore/accounting/posting.py
src/ledgercore/api/financial.py
src/ledgercore/api/routes.py
src/ledgercore/db/session.py
src/ledgercore/jobs/README.md
src/ledgercore/main.py
src/ledgercore/models/entities.py
src/ledgercore/schemas/financial.py
src/ledgercore/security/README.md
src/ledgercore/security/demo.py
src/ledgercore/services/origination.py
tests/conftest.py
tests/test_api.py
tests/test_concurrency.py
tests/test_database.py
tests/test_posting.py
uv.lock
```
