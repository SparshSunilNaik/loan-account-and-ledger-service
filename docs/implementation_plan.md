# Implementation plan

## Phase 1 — delivered

1. Inspect repository/tooling, establish uv package, module boundaries and local setup.
2. Define relational schema and frozen Alembic migrations; seed three configurable products.
3. Implement bounded paise utilities and deterministic flat/reducing schedules.
4. Expose borrower/product/loan/schedule/health APIs with strict input validation.
5. Validate mathematical examples, boundary invariants and real PostgreSQL integration.
6. Review financial semantics, document assumptions, lint/format, commit and push.

Phase 1 excluded repayment/disbursement posting, concurrency control, synthetic replay
and accrual job execution. Its prepared tables/contracts are extended in Phase 2 below.

## Phase 2 — delivered

Phase 2 implements database-backed development identity and RBAC, six ledger accounts,
one-time manager disbursement, independently callable due scheduled interest recognition,
atomic repayments, source/scoped-key idempotency, loan-row serialization, ledger-derived
balances and operationally consistent repayment reversals. The Phase 2 request supersedes
the earlier policy questions: future principal is collectible, future interest is not,
and early payment retains original contractual interest without rebate/re-amortization.

Tests cover live PostgreSQL migrations and Phase 1 data preservation, 20 simultaneous
repayment deliveries, shared-source/key races across loans, real row-lock waits, injected
rollback failures, authorization/audit identity and exact reversal invariants. Original
schedule tests are retained. The local header mechanism is explicitly development-only.

No disbursement/recognition reversal, automatic closure, scheduled overdue job or synthetic
replay is delivered. Subsequent phases must preserve posted history and existing retry
contracts, define any overdue-charge policy, and replace demo identity before deployment.

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
