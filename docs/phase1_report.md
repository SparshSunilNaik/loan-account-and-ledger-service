# Phase 1 validation report

Validated locally on 14 November 2026 with Python 3.12.13, uv 0.11.8 and real PostgreSQL
17.11. PostgreSQL 16+ is supported; Compose specifies 16.13. The empty GitHub repository
was cloned into the supplied workspace. Phase 2 work has not been implemented.

## Results

- Full PostgreSQL run: **315 passed, 0 failed, 0 skipped**.
- Unit/default run without `TEST_DATABASE_URL`: **268 passed, 47 skipped, 0 failed**.
  Skips explicitly identify unavailable database test configuration.
- One third-party deprecation warning: Starlette TestClient references AnyIO's deprecated
  `anyio.abc.BlockingPortal` alias. No test warnings were hidden.
- Fresh isolated PostgreSQL database: upgrade to head, metadata comparison, downgrade to
  base, empty-business-schema assertion and re-upgrade all passed.
- Persistent disposable development database: `alembic upgrade head` and `alembic check`
  passed; no ORM schema drift detected.
- Ruff formatting and lint passed. uv lock consistency passed.
- Live Uvicorn HTTP smoke passed for health, docs, OpenAPI, product listing, borrower
  creation/retrieval, loan creation/retrieval and two-instalment schedule retrieval.
- Compose YAML parsed successfully. **Docker is not installed**, so image build,
  Compose dependency startup and PostgreSQL 16 container execution were not tested.
  This limitation does not affect the successful native PostgreSQL 17 checks.

Initial test runs caught excessive bounds on intermediate interest/EMI, a mistyped annual
example expectation, test sessions incorrectly shared between requests and date coercion
from numeric timestamps. These were corrected before the final validation. The final full
run has no known test failures. A report-generation shell command also failed after a
loop variable changed zsh's command lookup path; rerunning in a fresh shell with a safe
variable name corrected it without changing application code.

## Commands executed

Commands ran from the repository root. The temporary PostgreSQL directory was created
with `mktemp` outside Git; it contains no production data and used loopback-only trust
access. It is stopped after validation. The HTTP smoke server was also stopped.

```sh
git clone https://github.com/SparshSunilNaik/loan-account-and-ledger-service.git .
uv init --bare --python 3.12
uv add fastapi 'uvicorn[standard]' 'sqlalchemy>=2.0,<3' 'psycopg[binary]>=3' alembic pydantic-settings
uv add --dev pytest httpx ruff
uv sync --python 3.12
initdb -D "$TEMP_PG_DIR" -A trust --no-locale -E UTF8
pg_ctl -D "$TEMP_PG_DIR" -l "$TEMP_PG_DIR/server.log" -o '-h 127.0.0.1 -p 55432' start
createdb -h 127.0.0.1 -p 55432 ledgercore_dev
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_dev uv run alembic revision --autogenerate -m 'initial relational schema'
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_dev uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_dev uv run alembic check
uv run ruff check --fix .
uv run ruff format .
uv run ruff format --check .
uv run ruff check .
uv lock --check
TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/postgres uv run pytest -q --tb=short
uv run pytest -q --tb=short
DATABASE_URL=postgresql+psycopg://127.0.0.1:55432/ledgercore_dev uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 58000
git diff --check
```

An inline `uv run python` script used httpx against the live server, asserted HTTP statuses
and the independently specified schedule `[(4975,100),(5025,50)]`, and parsed Compose with
PyYAML. The PostgreSQL test fixture executes Alembic upgrade/check/downgrade/upgrade itself.
The final Git commit, push result and working-tree status are reported in the handoff;
the commit cannot contain its own SHA.

## Design and review

All 13 requested tables, seven API paths, two schedule methods and three seeded products
are present. See architecture for a table-by-table constraint inventory; the financial
rules document contains formulas, independent numerical examples, calendar policy and
rounding decisions. No balance fields, fake authentication, posting implementation,
accrual runner or synthetic replay is included.

Before Phase 2, confirm illustrative rates and bounds, component-first versus
instalment-first allocation, collectibility/prepayment, overdue charge basis, recognition
policy, exact reversal rules, identity/role enforcement and per-loan serialization.
Database guards are preparation, not a concurrency-safe posting implementation.
Synthetic requirements (250 borrowers, 400 loans, 5,000 deliveries, seed 20261114) are
specified in the implementation plan, with separate expected and actual replay results.

## Files created

```text
.dockerignore
.env.example
.gitignore
.python-version
Dockerfile
README.md
alembic.ini
docker-compose.yml
docs/architecture.md
docs/financial_rules.md
docs/implementation_plan.md
docs/phase1_report.md
migrations/env.py
migrations/script.py.mako
migrations/versions/0002_products_and_journal_guards.py
migrations/versions/3b4f5702cf1f_initial_relational_schema.py
pyproject.toml
src/ledgercore/__init__.py
src/ledgercore/accounting/__init__.py
src/ledgercore/accounting/contracts.py
src/ledgercore/api/__init__.py
src/ledgercore/api/routes.py
src/ledgercore/db/__init__.py
src/ledgercore/db/session.py
src/ledgercore/jobs/README.md
src/ledgercore/jobs/__init__.py
src/ledgercore/main.py
src/ledgercore/models/__init__.py
src/ledgercore/models/entities.py
src/ledgercore/schemas/__init__.py
src/ledgercore/schemas/api.py
src/ledgercore/security/README.md
src/ledgercore/security/__init__.py
src/ledgercore/services/__init__.py
src/ledgercore/services/money.py
src/ledgercore/services/origination.py
src/ledgercore/services/schedules.py
tests/conftest.py
tests/test_api.py
tests/test_database.py
tests/test_schedules.py
uv.lock
```
