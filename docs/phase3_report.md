# Phase 3 delivery and observed validation

Continued from `2fb90c1275e0ddf0138ae611018aeea0a748689e`. Architecture, financial
rules, models, migrations, posting code, tests and the Phase 2 report were read before
implementation. Work stops after Phase 3; there is no frontend or subsequent phase.

Validated locally on 14 November 2026 with Python 3.12.13, uv 0.11.8 and PostgreSQL 17.11
(Homebrew, macOS). All financial tests and replay used real PostgreSQL. There is no SQLite,
paid API, external model or cloud dependency.

## Delivered changes

- Explicit UTC-date accrual CLI, one transaction and row lock per loan, whole-loan rollback,
  conflict retry, resumable catch-up and a documented cron-compatible invocation.
- Simple daily 0.05% penalties on historical opening unpaid scheduled principal. No
  compounding or interest/penalty basis; only dates after due date and disbursement qualify.
- Daily half-up rounding, immutable zero-charge identities without journals, unique one-day
  periods, stored basis/rate and database checks. Existing once-only scheduled recognition
  is reused and never counted as overdue interest.
- Stable invented input generation and an independent chronological Decimal reference book.
- Isolated-database replay through an actual Uvicorn TCP HTTP server, complete observed
  delivery outcomes, three-way reconciliation and reproducibility metadata.
- Adversarial tests and retained actual artifacts under `artifacts/phase3/`.

No financial balance cache, original schedule edits, relaxed RBAC, client-selected production
roles, repayment-row insertion shortcut, or mutable journal shortcut was introduced.

## Actual dataset and submissions

The retained run is `artifacts/phase3/replay_report.json`; the separate expectation manifest
was generated before execution. Input source UUIDs are stable; actual API-assigned UUIDs
are mapped explicitly in `identity_map.json`.

| Population/category | Generated | Submitted/observed |
| --- | ---: | ---: |
| Invented borrowers | 250 | 250 created through HTTP |
| Invented loans | 400 | 400 created and disbursed through HTTP |
| Existing loan products | 3 | 3 observed in database/API |
| Ordinary deliveries | 4200 | 4200 |
| Exact duplicate deliveries | 300 | 300 |
| Out-of-order deliveries | 250 | 250 |
| Partial/overpayment scenarios | 150 | 150 |
| Invalid/unauthorized scenarios | 100 | 100 |
| All repayment deliveries | **5000** | **5000 actual HTTP attempts** |

Seed: **20261114**. Arrival/business-date simulation: **2026-11-01 through 2026-11-14 UTC**.
Loan principals range from INR 25000 to INR 150000. Weekly disbursement is October 27 with
first due November 3; monthly disbursements are October 4/5 with first due November 4/5.
All borrower names are explicitly invented and no phone/email/personal data was sourced.

## Actual replay outcomes

| Observed behavior | Count |
| --- | ---: |
| New accepted repayments | **4510** |
| Duplicate successful responses, no new receipt | **330** |
| Overpayment rejected, HTTP 400 | **60** |
| Auditor mutation denied, HTTP 403 | **25** |
| Idempotency collision, HTTP 409 | **25** |
| Invalid zero/negative amount, HTTP 422 | **50** |
| Total | **5000** |

There were 4840 HTTP 201 responses, comprising 4510 new receipts and 330 duplicates.
The required 300 exact retries preserve their original financial identity, payload and
key. The additional 30 duplicates are explicitly labelled source duplicates of partial
payments under new keys within the 150 partial/overpayment scenarios (60 new partials,
60 overpayments, 30 source aliases). Delivery count is not receipt count.

All **250 intended out-of-order new accepted events** demonstrated older economic
occurred_at after newer accepted activity on the same loan. Including old exact retries,
there were **550 economic inversions across all attempts** relative to accepted history.
New financial operations used nondecreasing loan business dates; delayed events retained
their original economic timestamps. Exact retries retained original processing dates and
returned historical successful responses as required by Phase 2.

Every actual status, behavior, canonical response and allocation matched the independent
manifest. No expected result was substituted for an observed response.

## Journal and receivable reconciliation

| Actual metric | Result |
| --- | ---: |
| Posted journals | **9903** |
| Total debits (paise) | **3641480368** |
| Total credits (paise) | **3641480368** |
| Unbalanced journals | **0** |
| Daily penalty evaluations | **4537** |
| Zero-charge days without a journal | **78** |
| Incorrect historical penalty bases/rounding | **0** |
| Loans with principal reconciliation differences | **0** |
| Loans with interest reconciliation differences | **0** |
| Loans with penalty reconciliation differences | **0** |
| API balance/reference mismatches | **0** |
| Delivery expectation mismatches | **0** |

Reconciliation independently checks every accepted receipt's cash/receivable journal,
allocation totals and individual scheduled-principal caps. It reconstructs each day's
basis from processing-date receipt/reversal history and verifies charges with exact integer
half-up arithmetic, separately from the production Decimal calculation. Posted ledger,
operational allocation/accrual records and the independent reference state agree for all
400 loans. Scheduled interest never appears as additional overdue interest. Rerunning the
final catch-up across all loans produced **no new financial, accrual or audit records**.

The detailed per-loan results and errors/difference lists are in
`artifacts/phase3/reconciliation_report.json`; all difference/error lists are empty.

## Tests and commands actually run

- Full suite, including every retained Phase 1/2 test and the real 5000-request replay:
  **390 passed, 0 failed, 0 skipped**, in **85.05 seconds** on the final run.
- Default run without TEST_DATABASE_URL: **283 passed, 107 explicitly skipped, 0 failed**.
  This default run alone is not full validation.
- 28 additional tests cover independent generation, daily rounding/precision, historical
  catch-up, partial payments, zero-day identities, reversals, overlap rejection, job failure/
  resume, rollback and concurrent repayment/two-accrual transactions, plus the full replay.
- Ruff lint and formatting, uv lock/frozen dependency consistency, fresh migration,
  downgrade/empty-schema/re-upgrade, populated upgrade preservation and Alembic schema
  comparison passed. The original Phase 1/2 migrations were not changed.
- Live Phase 2 HTTP smoke passed on Phase 3: 20 competing repayments yielded ten accepted,
  ten rejected, zero remaining principal and balanced journals; retry, RBAC, recognition,
  audit and reversal assertions passed.
- Live accrual CLI on those separate smoke loans created eligible positive/zero days; a
  second invocation returned zero evaluations, charges and recognition. No failures occurred.
- A manual tool interrupt of the smoke server produced a shutdown-only event-loop error.
  A subsequent controlled server run passed all requests and SIGTERM shutdown with no
  traceback; replay-managed subprocess cleanup also completed.
- One pre-existing upstream Starlette TestClient/AnyIO deprecation warning remains;
  warnings were not hidden. A Ruff fixture-import warning during development was corrected
  by moving the reusable committed-session fixture into conftest before full validation.
  Final defensive review also restored rejection of malformed schedule-less receivable lots
  and added a ledger-principal reconciliation check before accrual, with regression coverage.

Principal executed commands (temporary PostgreSQL files live outside the repository):

```sh
uv sync
initdb -D "$TEMP_PG_DIR" -A trust --no-locale -E UTF8
pg_ctl -D "$TEMP_PG_DIR" -l "$TEMP_PG_DIR/server.log" -o '-h 127.0.0.1 -p 55432' start
createdb -h 127.0.0.1 -p 55432 ledgercore_phase3_dev
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_phase3_dev uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_phase3_dev uv run alembic check
uv run python -m ledgercore.simulation.generate --output /tmp/ledgercore-phase3-dataset
REPLAY_ADMIN_DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/postgres uv run python -m ledgercore.simulation.replay --output /tmp/ledgercore-phase3-first-replay
REPLAY_TEST_OUTPUT=artifacts/phase3 TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/postgres uv run pytest -q --tb=short
uv run pytest -q --tb=short
uv run ruff check .
uv run ruff format --check .
uv lock --check
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_phase3_dev DEMO_AUTH_ENABLED=true uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 58000
uv run python scripts/smoke_http.py --base-url http://127.0.0.1:58000
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_phase3_dev uv run ledgercore-accrue --business-date 2026-02-03 --catch-up
# Same CLI invocation was repeated to verify a no-op.
git diff --check
```

The full suite was run three times with retained outputs, with the earlier verified output moved
outside the repository before the final run. Alembic and replay also ran on fresh isolated
random databases inside the tests. An inline comparison verified retained source/input
hashes and normalized outcomes across four independent executed HTTP replays.

## Runtime and reproducibility

The final retained replay took **80.354 seconds**, including fresh DB migration, HTTP setup,
dated jobs, all 5000 attempts, reconciliation and rerun checks. Its full suite took 85.05
seconds. Earlier independently executed replays took 87.598, 72.643 and 73.86 seconds. All have
the same delivery-input hash and normalized observed financial hash; the earliest setup
dates were refined before the final run to give one-period first due dates, without
changing any delivery identity, overdue eligibility or monetary outcome. Final defensive
checks also left healthy replay outcomes unchanged.

The fixed input SHA-256 and normalized actual financial SHA-256 are recorded in the replay
report and `reproducibility_check.json`. The final report's source digest matches the
executed Python/migration/pyproject/lock files. It also records Python, PostgreSQL, library
versions, platform, actual start/end timestamps, transport and parent Git SHA. API UUIDs,
server receipt/audit timestamps, attempted-at times and runtimes deliberately remain actual
observations and vary between runs; the system does not fabricate those timestamps.

## Limits and review points

- There are **no known unresolved reconciliation or failing-test issues** in the executed
  scenarios. These checks establish the documented assignment policy, not production readiness.
- Opening-balance daily penalties are an explicit policy choice. Same-day principal payments
  affect the following day. Late catch-up posts historical economic charges at the current
  processing date and never reallocates previously accepted receipts. Concurrent job/payment
  orders serialize safely but can change the valid principal-versus-penalty collection mix;
  the replay fixes job-before-deliveries ordering for reproducibility.
- Zero-charge evaluations also constrain backdated financial processing so later reversals
  cannot invalidate evaluated history. There is no general restatement engine.
- Logical input IDs are deterministic; API UUIDs are mapped, not forced through an added
  privileged primary-key API. Real server receipt time is distinct from simulated arrival.
- Authentication remains explicitly demo-only. Production identity, least-privilege DB
  roles, ownership scoping, service identity, real bank settlement and automatic closure
  are not implemented. Only repayment reversals are supported.
- Docker is unavailable; image build/Compose startup were not validated. All database and
  concurrency results used native real PostgreSQL 17.11, not a substitute backend.
- Retained artifacts contain invented data and actual review evidence. PostgreSQL runtime
  files, local environments, logs and credentials are not committed. Downgrade with daily
  accrual history is intentionally unsupported rather than deleting immutable history.

The finished commit, push result and working-tree status are reported in the handoff;
a commit cannot include its own SHA. Work stops after Phase 3 for review.

## Files changed

```text
.dockerignore
.gitignore
README.md
artifacts/phase3/borrowers.json
artifacts/phase3/events.jsonl
artifacts/phase3/identity_map.json
artifacts/phase3/loans.json
artifacts/phase3/products.json
artifacts/phase3/reconciliation_report.json
artifacts/phase3/replay_outcomes.jsonl
artifacts/phase3/replay_report.json
artifacts/phase3/reproducibility_check.json
artifacts/phase3/scenario_manifest.json
docs/architecture.md
docs/financial_rules.md
docs/implementation_plan.md
docs/phase3_report.md
migrations/versions/0005_daily_penalty.py
pyproject.toml
src/ledgercore/accounting/posting.py
src/ledgercore/jobs/README.md
src/ledgercore/jobs/accrual.py
src/ledgercore/main.py
src/ledgercore/models/entities.py
src/ledgercore/simulation/__init__.py
src/ledgercore/simulation/generate.py
src/ledgercore/simulation/reconcile.py
src/ledgercore/simulation/reference.py
src/ledgercore/simulation/replay.py
tests/conftest.py
tests/test_accrual.py
tests/test_api.py
tests/test_concurrency.py
tests/test_simulation.py
uv.lock
```
