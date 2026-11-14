# Implementation plan

## Phase 1 — delivered

1. Inspect repository/tooling, establish uv package, module boundaries and local setup.
2. Define relational schema and frozen Alembic migrations; seed three configurable products.
3. Implement bounded paise utilities and deterministic flat/reducing schedules.
4. Expose borrower/product/loan/schedule/health APIs with strict input validation.
5. Validate mathematical examples, boundary invariants and real PostgreSQL integration.
6. Review financial semantics, document assumptions, lint/format, commit and push.

No repayment or disbursement posting, concurrency control, synthetic replay or accrual
job execution is included. Prepared tables and protocols are contracts for later work.

## Phase 2 — proposed, requires policy review

Introduce explicit demo authentication and role checks (loan_officer, manager, auditor).
Define account chart and posted receivable queries. Implement atomic, serialized one-time
disbursement, repayment validation/allocation, idempotent event handling, immutable journals
and exact reversals. Test rollback, concurrent mutation, overpayment and authorization
failures on PostgreSQL. Decide collectibility and allocation precedence first.

## Later — accrual and replay

Implement scheduled recognition separately from any approved overdue charge. Use unique
period identity and validate nonoverlapping intervals. Add late-arrival correction and
reconciliation policies and scheduled execution only after accounting semantics are settled.

The future synthetic dataset contract is:

- Exactly 250 synthetic borrowers, 400 loans and the three products.
- Exactly **5,000 repayment delivery events**, not 5,000 successful receipt rows.
- Deterministic seed **20261114**, stable borrower/loan/event identifiers and fixed clock.
- Duplicates, out-of-order arrivals, partial payments, overpayments, invalid amounts and
  authorization failures. Some deliveries must leave no repayment or journal row.
- A scenario manifest describes seed, counts, canonical IDs, economic timestamp, delivery
  sequence, actor/role, source event ID, idempotency key, payload and expected outcome.
- Track expected HTTP status, deduplicated receipt identity, expected allocation and journal
  effects, and the reason for each rejected delivery. An exact duplicate shares source
  identity; a different-payload key collision is a separate scenario.
- Replay submits every event through the real API and records actual status/body and
  persisted database effects. Compare actual results against the independent manifest;
  never present generated expectations as observed behavior.
- Store every delivery outcome in a replay artifact or future delivery table, separate
  from `repayments`, which represents accepted receipts. Add that structure in the replay
  phase; current source/event uniqueness, occurred/received times, scoped idempotency,
  correlation audit and stable external references provide the foundations.

No borrowers/loans/events, replay manifest, seed runner or claimed replay results have been
generated in Phase 1. Future work must check dataset totals and independence of expected
outcomes, including authorization failures before monetary state mutation.
