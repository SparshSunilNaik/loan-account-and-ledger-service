# Final independent verification

Reviewed against Phase 3 commit `e88025dc66525f7d29048f1bb1840fe1bedc66a4`.
The review uses recomputed evidence, executable contracts and a new PostgreSQL replay;
it does not treat a pre-existing `passed` flag as sufficient evidence.

| Review item | Evidence and result |
| --- | --- |
| Journal balance and reconciliation | Fresh 5000-request replay checks every posted journal, receipt cash/receivable effects and per-loan operational/reference balances. 9903 journals; debit and credit totals each 3641480368 paise; zero discrepancies. |
| Duplicate counts | Recounted actual response receipt IDs across all retained outcomes: 4510 distinct receipts and 330 duplicate responses. Input has 300 exact retries plus 30 labelled different-key source duplicates. |
| Out-of-order counts | Recomputed economic inversions among new accepted receipts by loan: all 250 intended delayed events. All-attempt high-water inversions, including retries, are reported separately as 550. |
| Opening-day penalty basis | Reviewed historical processing-date allocation/reversal query, strict due-date/disbursement eligibility, Decimal half-up and one-day uniqueness/zero-charge constraints. Fresh DB tests cover partial payments, delayed economic timestamps, reversal restoration, zero days and rollback. |
| Retry after timeout | Real loopback upstream response was consumed after commit, then hidden with an injected ReadTimeout. Retry returned the existing receipt/journal IDs with principal 9100 and interest 0; no extra receipt or repayment journal. |
| Parallel posting | Real PostgreSQL lock wait and 20-request suites retained. Separate live smoke: ten of twenty competing 1000-paise repayments accepted against 10000 principal, ten rejected; final principal zero. Concurrent job/payment tests preserve balanced accounting. |
| Roles | Newman asserts auditor mutation denials, officer audit-history denial and manager-only disbursement/reversal. No request role header overrides the active DB user's role. |
| History/immutability | All earlier tests retained: original schedules, loan terms, posted journals/entries, receipts/allocations, completed idempotency and audit are protected. |
| Source/evidence correspondence | Retained source hash recomputed from exact Phase 3 Git bytes. Current financial modules, migrations, pyproject and lock match. An AST comparison proves the replay change only replaces revision metadata and adds a Git-optional helper. Fresh financial and input hashes match retained evidence. |
| Secrets/configuration | Current Compose requires a runtime password. `.env.example` has an empty password and REPLACE_ME URI. A private ignored `.env` helper generates values locally and preserves existing files. No runtime environment, token, private key or DB directory is shipped. |
| Security claims | README, OpenAPI, Postman and write-up explicitly call X-Demo-User local impersonation. No production authentication, tenant ownership or deployment-hardening claim is made. |

The Postman collection is valid against the official vendored v2.1 schema and actually ran
with Newman 6.2.1: 33 requests and 50 assertions, zero failures. All 14 documented operations
are covered, plus public documentation routes. OpenAPI 3.1.0 was fetched from running
FastAPI, matched byte-equivalent parsed JSON in the application and passed
openapi-spec-validator 0.7.2. Generic financial response schemas remain generic rather
than hand-editing the export to promise undocumented types.

The concise write-up PDF was rendered and checked to contain exactly one page. Its
Markdown source is provided. The curl demo ran, including response comparison and actor/
journal audit verification. The full native PostgreSQL suite passed 396 tests; package
verification details and adjacent ZIP reports identify any separate extraction checks.

## Changes limited to final submission

The sole production Python change makes `source_base_commit` null if Git metadata or Git
itself is absent. This is necessary for the Git-free ZIP; it does not invent a revision.
The source digest and observed financial fingerprints remain available. Financial formulas,
allocation, locks, posting, accrual and role policy were not changed. Setup changes remove
the fixed local Compose password; the template now needs private configuration.

## Limits retained explicitly

- Docker is unavailable: native PostgreSQL 17.11 was used. Compose YAML/password/loopback
  structure was inspected, but image build, container startup and Compose interpolation
  were **not executed or claimed as validated**.
- Header identity is not authentication for untrusted clients. All demo users can read all
  loans; no borrower/tenant ownership filtering exists. Protected roles are enforced locally.
- Daily penalties use opening principal. Late catch-up does not change earlier receipt
  allocation; job-before-delivery order fixes the replay. A valid different concurrent order
  can change the principal-versus-penalty collection mix while preserving reconciliation.
- Only repayment reversals are supported. No general restatement, automatic closure,
  prepayment rebate or re-amortization is introduced.
- Postman/audit demo assertions inspect the first audit page; use a fresh demo DB or adjust
  auditOffset/paginate. Scripts create invented history and do not silently erase it.
- Existing TestClient/AnyIO and Newman transitive dependency deprecation warnings are
  reported; tests/assertions passed. No paid Postman account or cloud run was used.
- Secret-pattern inspection is a review aid, not a security certification. No active
  credentials were found; public demo subject names and explicit URI templates are intentional.
