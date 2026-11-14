# Final submission checklist

## Code and evidence

- [x] Continue from the completed Phase 3 commit; preserve all financial policies.
- [x] Retain source, five migrations, generator, accrual CLI and all existing tests.
- [x] Include invented 250-borrower/400-loan/5000-delivery inputs and actual outcomes.
- [x] Recount retained outcomes and compare a new real PostgreSQL HTTP replay.
- [x] Verify journal/receivable reconciliation, daily basis, duplicates and out-of-order events.
- [x] Review row locks, twenty-way competing payments, role restrictions and immutability.
- [x] Test a committed repayment response lost to an injected client timeout.

## Reviewer assets

- [x] Export running FastAPI OpenAPI 3.1.0 and validate it without hand-edited contracts.
- [x] Verify complete Postman v2.1 operation coverage and official schema conformance.
- [x] Run Newman: 33 requests, 50 assertions, zero failures.
- [x] Provide a local environment with role/ID/key variables and no secrets.
- [x] Run the actual curl workflow with capture, identical retry, ledger, balance and audit.
- [x] Provide one-page PDF and Markdown technical write-up.
- [x] Simplify native and Compose instructions; remove the supplied Compose password.

## Validation and packaging

- [x] Repository full PostgreSQL suite: 396 passed, zero failed/skipped (83.74 seconds).
- [x] Ruff lint/format, lock consistency, Alembic drift and live HTTP smoke pass.
- [x] Keep Docker/Compose execution explicitly unverified: Docker unavailable.
- [x] Generate the ZIP from allowlisted source/evidence directories.
- [x] Check archive members/CRC/SHA-256 against exact included files.
- [x] Exclude `.git`, `.venv`, `.env`, DB files, private-key files, caches and logs.
- [x] Make Git revision optional for archive replay; include a no-Git regression test.

Build outputs are deliberately ignored in Git: `dist/ledgercore-submission.zip` and
`dist/ledgercore-submission.manifest.json`. [included_files.txt](included_files.txt) records
the exact source members. The adjacent `dist/zip_validation.json` records the separate
Git-free extraction run after packaging. Its results are generated, not assumed here.

[verification.json](verification.json) records observed repository checks and replay
metrics; [review.md](review.md) gives the independent review and explicit limitations.
Complete source and contents are committed; the generated ZIP is not committed. The final
commit SHA and ZIP size/hash are reported in the handoff and external archive manifest,
avoiding a self-referential commit or ZIP hash inside its own contents. Stop after Phase 4.
