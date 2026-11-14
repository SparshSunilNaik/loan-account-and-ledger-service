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

Phase 2 excluded disbursement/recognition reversal, automatic closure, overdue jobs and
replay. Phase 3 extends its posting contracts below; real identity and production deployment
remain outside this assignment phase.

## Phase 3 — delivered

Phase 3 implements explicit dated daily penalties on opening unpaid scheduled principal,
with immutable zero-day identities, safe historical catch-up, per-loan locking, rollback
and resumable CLI batches. Scheduled interest still uses the existing once-only service.
The generator and independent manifest specify the fixed 5000-delivery simulation; the
runner initializes an isolated PostgreSQL database and submits every delivery through real
HTTP, retaining actual outcomes and three-way reconciliation. Tests retain Phase 1/2 and
add concurrent accrual, reversals, failures, deterministic generation and the full replay.

The implemented synthetic dataset contract is:

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
  phase as artifacts; source/event uniqueness, occurred/received times, scoped idempotency,
  correlation audit and stable external references provide the foundations.

Phase 1/2 did not generate these records. Phase 3 now includes actual executed artifacts
under artifacts/phase3, and reports observed results separately from independent expected
outcomes. No frontend or subsequent phase was started. Remaining production concerns and
reversal limits are documented for review; stop at Phase 3.
