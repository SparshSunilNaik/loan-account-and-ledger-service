# Studio validation — 14 November 2026

Scope: new `frontend/` only, based on backend commit
`006fe0724a74cca8418c737ddb0b9bcb2f248a74`. No commit or push was performed.

## Environment actually used

- macOS 27.0.1, arm64; Node 26.13.1; npm 11.20.0.
- Next.js 16.4.6, TypeScript 5.9.3, React 19.3.1.
- Python 3.12.13; native PostgreSQL 17.11 (Homebrew), not SQLite or a database mock.
- Google Chrome 157.0.8103.52 driven by Playwright 1.65.1.
- A new temporary PostgreSQL cluster under `/tmp/ledgercore-studio-*`, loopback port 55432,
  database `ledgercore_studio`; FastAPI on 58000 and Next production server on 3000.
  Existing databases were not cleared. Only newly owned processes were stopped after validation;
  the temporary database files were preserved outside the repository.
- Docker and Compose were not used or validated in this frontend task.

## Executed checks and results

| Check                                                                           | Observed result                                                                              |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `npm ci`                                                                        | Successful lockfile installation                                                             |
| `npm run types:generate`                                                        | Successful; regeneration produced identical generated type bytes                             |
| `npm run lint`                                                                  | Passed, no lint warnings/errors                                                              |
| `npm run typecheck`                                                             | Passed                                                                                       |
| `npm run format:check`                                                          | Passed                                                                                       |
| `npm test`                                                                      | **30 passed**, four unit/component files, zero failed/skipped                                |
| `npm run build`                                                                 | Successful optimized production build, all seven UI routes and proxy compiled                |
| `npm audit`                                                                     | Zero reported vulnerabilities with locked dependencies                                       |
| `uv run alembic upgrade head` against new PostgreSQL                            | Passed, revision `0005`                                                                      |
| `uv run alembic check`                                                          | Passed: no new upgrade operations detected                                                   |
| Normal `npm run test:e2e` against production Next and real FastAPI/PostgreSQL   | **4 passed**, zero failed/skipped                                                            |
| `STUDIO_OFFLINE=1 npm run test:e2e` with owned FastAPI process actually stopped | **1 passed**, zero failed/skipped                                                            |
| `uv run python scripts/smoke_http.py --base-url http://127.0.0.1:58000`         | Existing live backend smoke passed, including source deduplication, RBAC, audit and reversal |

Browser tests were executed with
`CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'`.
The final online suite took about four seconds; the offline suite took under one second.
No full backend pytest rerun is claimed: this task ran the frontend suites, real HTTP
integration/browser workflows, migrations check and the existing backend live smoke tool.

The initial browser run exposed a legitimate same-origin mutation rejection caused by
Next's normalized internal route URL. The proxy now validates a loopback Host and compares
that origin with the browser Origin. Subsequent real-browser suites passed. An exploratory
ESLint 10 update was rejected because bundled plugins declared incompatible peers; the
final dependency uses compatible ESLint 9.39.5. npm emits its deprecation warning and an
optional fsevents script notice; neither is a failed lint/build/test. The minimatch tooling
override is documented in the README, with zero npm-audit findings observed.

## Workflows actually verified

1. Overview live backend/product responses; no invented portfolio statistics.
2. UI borrower creation, product selection, exact ₹100 loan creation and returned schedule.
3. Officer disbursement control disabled; manager disbursement succeeds.
4. A real ₹10 partial repayment on 31 January 2026 recognizes ₹1 due interest atomically.
5. Exact retry returns the existing receipt and journal, with unchanged observed counts.
6. Same key with a different amount yields actual HTTP 409.
7. Auditor mutation attempt yields actual HTTP 403.
8. Valid but excessive repayment yields actual HTTP 400; subsequent reads still show one
   receipt and the same three journals on the tested loan.
9. Independent known example: principal receivable **9,100 paise**, interest **0**, penalty
   **0**, one repayment and three balanced journals. Each journal's debits and credits
   were independently summed from the HTTP response using integer arithmetic.
10. Loan receipt and origination tabs, grouped ledger/account rendering and actual audit
    pagination; officer audit access denied, auditor access accepted.
11. Guided flow performs origination, schedule fetch, disbursement, recognition/repayment,
    identical retry, financial inspection and matching audit scan through actual APIs.
12. At 390px width, accessible mobile navigation opens/closes and workspace has no page
    horizontal overflow. Overview/workspace screenshots were also visually inspected.
13. Proxy rejects unsupported routes, arbitrary demo subjects and cross-origin mutations.
14. Response loss after commit: Playwright forwards a real repayment to FastAPI, confirms
    201 from that actual upstream call, then deliberately aborts delivery to the browser.
    Studio reports no HTTP response, retains the frozen request and retries it even after
    the visible amount changes to ₹20. The database/API still contains exactly **one ₹10
    receipt** with the original ID. No fake backend success body was substituted.
15. With the owned FastAPI service stopped, proxy returns its explicit HTTP 503 marker and
    Chrome renders backend-unavailable errors. No fake offline response was injected.

The existing live smoke tool also launched **20 overlapping requests** with independent
API operations: **10 accepted, 10 rejected**, final principal **0**, balanced journals.
This is an additional backend observation, not an invented frontend portfolio statistic.

## Screenshots and source inventory

Actual browser captures: [overview](screenshots/overview.png),
[mobile workspace](screenshots/mobile-workspace.png), [repayment lab](screenshots/repayment-lab.png),
[ledger](screenshots/ledger.png), [audit](screenshots/audit.png),
[walkthrough](screenshots/walkthrough.png), [backend offline](screenshots/backend-offline.png).
Generated UUIDs and timestamps in these captures belong to invented local test records.
An exact list of new deliverable files is in [files.txt](files.txt). Dependencies, build
output, reports, traces and caches are ignored and are not deliverable source files.

## Original submission integrity

`git diff --name-only` was empty: all existing tracked files stayed unchanged.
Only new files below `frontend/` were present in the working tree.
SHA-256 comparisons before/after implementation matched:

| Original artifact                                  | SHA-256                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------ |
| `dist/ledgercore-submission.zip` (1,756,907 bytes) | `c7cc915c01f0759147672b3f949632d057df046f8da4f3c842edcf7621463798` |
| `docs/technical_writeup.md`                        | `377f0a815a02a821d1341f70a78d9dea8a66071a5dd18a4480bf2802bc307922` |
| `docs/technical_writeup.pdf`                       | `10af49122b9153a780fe5bfa43a56a98432c57f98e0dda78a80fdf5b83eb3e16` |

Studio remains local-only, uses development impersonation, has no authoritative balance
calculation, and cannot run accrual jobs or reset a database. Snapshot observations are
not atomic across GET endpoints. No production-security, cross-browser or full accessibility
certification is claimed. No publication, commit or push was performed.
