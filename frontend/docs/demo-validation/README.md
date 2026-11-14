# Recording rehearsal

These populated Chrome captures come from executing root `demo.txt` against a fresh disposable
PostgreSQL database. They are optional Studio evidence and are excluded from the backend ZIP.
The backend, migrations and retained replay files were not edited.

Reproduce after starting an isolated backend and Studio proxy:

```sh
cd frontend
STUDIO_URL=http://127.0.0.1:3003 node scripts/verify-demo.mjs
```

The command creates a new invented borrower/loan. Do not target a database whose financial
history you wish to keep untouched. Output defaults to `/tmp/ledgercore-demo-verification`;
set `DEMO_OUTPUT` to another directory. Chrome must be installed, or set `CHROME_EXECUTABLE`.
The verifier checks saved schedules, real payment allocations and ledger entries, exact retry,
409, 403, immutable receipt counts and auditor history access. No mock responses are used.
See `../../../docs/submission/demo_verification.json` for observed results.
