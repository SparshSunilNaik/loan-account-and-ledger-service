# Submission finalization review

This addendum reviews the Phase 1–4 requirements supplied in the conversation against the actual backend deliverables. No separate original employer brief was available, so any additional employer upload/video instructions still need owner review. The optional `frontend/` application is outside the backend submission and excluded from the ZIP.

## Requirements and actual deliverables

| Requirement | Delivered evidence |
| --- | --- |
| Reproducible Python 3.12+ / FastAPI / Pydantic 2 / SQLAlchemy 2 / psycopg 3 backend | `pyproject.toml`, `uv.lock`, `.python-version`, `src/ledgercore/`, README startup commands |
| PostgreSQL schema and migration history | 13 relational tables in `src/ledgercore/models/entities.py`; five revision files under `migrations/versions/`; fresh upgrade, drift check and controlled downgrade/re-upgrade covered by PostgreSQL tests |
| Exact INR calculations and schedules | Integer paise, Decimal, half-up calculations; weekly/monthly flat and reducing schedules; independent numerical examples in `tests/test_schedules.py` |
| Atomic accounting, idempotency, concurrency and roles | Posting/accounting services, database protections, caller-session transactions, row locks, scoped request/source identities, immutable history, demo-user roles and audit; tests include 20 competing payments and post-commit timeout recovery |
| Scheduled interest and daily overdue penalties | Deterministic recognition, opening-day principal basis, daily period uniqueness and zero-charge identities; CLI and cron-compatible instructions; real PostgreSQL tests |
| Required synthetic inputs and 5,000 deliveries | `artifacts/phase3/`: 250 borrowers, 400 loans, three products, 5,000 delivery inputs, independent scenario manifest, all actual responses, replay and reconciliation reports |
| Executable generator/replay | `src/ledgercore/simulation/`, installed generator/replay CLIs and tests; retained inputs and fresh replay financial fingerprints independently compared |
| API specification and client collection | `docs/openapi.json` (3.1.0), Postman collection/environment, vendored official schema and guide; 14 operations covered, 33 live requests / 50 assertions rerun successfully |
| Automated tests and local setup | Full backend tests; README, Alembic configuration, Dockerfile/Compose, private environment helper and safe example configuration |
| One-page technical write-up | Existing `docs/technical_writeup.md` and one-page `docs/technical_writeup.pdf`, preserved byte-for-byte; not rewritten |
| End-to-end demo | Existing `docs/demo.md` and executable `scripts/demo.sh`; actual curl workflow rerun on an isolated disposable database |
| User's new video script | Root `demo.txt`: authored 6:15 recording script, actual UI steps, narration, preparation and verified figures. Fresh Chrome rehearsal evidence in `demo_verification.json`; the owner still records the video. |
| Exact package inventory / integrity | `docs/submission/included_files.txt`, external ZIP/member manifest, per-member SHA-256 list and `dist/SHA256SUMS`; old verified ZIP backed up before rebuilding |
| Fresh archive usability | External `dist/zip_validation.json` records actual extraction/install/test results for the exact archive hash, avoiding a self-referential hash inside the ZIP |

## Preservation and current checks

All financial source, migrations, retained Phase 3 artifacts, `pyproject.toml`, `uv.lock` and both technical write-up files are preserved against a before-task SHA-256 snapshot. The source/evidence verifier also recomputes the exact Phase 3 Git source fingerprint and validates its documented Git-optional replay-metadata exception. Production accounting and calculation logic is not modified by this finalization.

Latest native PostgreSQL 16.15 / Python 3.12.13 and Chrome verification is recorded in [demo_verification.json](demo_verification.json). [finalization.json](finalization.json) is the earlier packaging refresh, including its then-missing-script status. Earlier Phase 4 reports remain historical; their PostgreSQL 17.11 environment and durations are not relabelled as the current run. Current replay: 4,510 new receipts, 330 duplicate responses, 160 rejections, 250 unique delayed arrivals, 9,903 balanced journals, debit/credit totals each 3,641,480,368 paise and zero reconciliation differences. All 5,000 deliveries were submitted through the actual HTTP API in an isolated database.

Repository-wide Ruff initially encountered the optional frontend's third-party design-skill Python files. Current repository backend checks explicitly target `src migrations scripts tests`; the backend-only extraction can use the original `ruff check .` command. No third-party frontend skill or financial/dependency source was edited to conceal that issue.

## Remaining submission risks

- `demo.txt` is delivered and its actions rehearsed. The owner must still record the 5–7 minute video and check any separate employer upload instructions.
- Docker is unavailable; Compose startup/image build are not executed or claimed. Native PostgreSQL was tested.
- `X-Demo-User` is development-only impersonation. There is no production authentication or tenant/borrower ownership filtering. Only repayment reversals are supported. Some financial response OpenAPI schemas remain generic.
- Existing daily opening-principal and late-accrual ordering policies remain unchanged. Posted receivables are not future payoff quotes. No automatic rebate, closure or re-amortization is introduced.
- Existing TestClient/AnyIO and Newman dependency warnings do not constitute passing checks; their actual run results are recorded separately.
- The generated ZIP and backups are ignored local artifacts, not GitHub downloads. Final commit and remote verification are reported in the handoff and external archive manifest. No external portal submission is performed.

## Package and verify

```sh
uv run python scripts/build_submission.py
shasum -a 256 -c dist/SHA256SUMS
# Unzip into a new directory outside the repository, then:
uv sync --frozen --python 3.12
export TEST_DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/postgres
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The builder automatically preserves an existing ZIP and adjacent evidence under `dist/backups/` **before replacing the inventory or archive**. ZIP bytes are deterministic for fixed source bytes. The external manifest provides SHA-256 for every included file; `ledgercore-submission.files.sha256` can be checked from the extracted root. The archive and checksum files are ignored build outputs, not a reason to commit the ZIP.
