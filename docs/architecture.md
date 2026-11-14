# Architecture

LedgerCore is a modular monolith with one FastAPI application and one PostgreSQL database.
Routes own transactions, schemas validate contracts, domain/accounting services implement
financial behavior, ORM models describe records, and database/security/jobs modules keep
infrastructure boundaries explicit. Synchronous routes execute in worker threads. Each
request has its own SQLAlchemy Session; financial connections explicitly use UTC and
READ COMMITTED. No in-memory financial lock or authoritative cached balance exists.

## Financial operation boundary

1. A dependency authenticates the active database demo subject and authorizes its role in
   a short transaction. It returns an immutable actor snapshot and closes that transaction.
   Denials commit a minimal audit event before returning 403.
2. The route begins the financial transaction. The posting service locks the loan with
   SELECT FOR UPDATE before reading financial state or resolving idempotency.
3. The service resolves scoped idempotency and source-event identity, recognizes eligible
   scheduled interest, validates posted receivables, calculates allocations and posts a
   balanced journal. Successful audit and stored response participate in the same transaction.
4. Only the route commits. Any failure rolls back recognition, receipt, allocations,
   journal, entries, idempotency and successful-mutation audit together.

The posting functions in `accounting/posting.py` receive the caller's Session and never
commit. `accounting/contracts.py` exposes their implemented contracts. Scheduled recognition
is independently callable under an authorized caller-owned transaction; repayments invoke
it inside their transaction. The explicit Phase 3 job invokes it before daily overdue evaluation; no resident scheduler is needed.

Uniqueness/deadlock/serialization races roll back the entire attempt and retry up to three
times in a new transaction. At READ COMMITTED, the winner's committed key or event is then
visible. Lifecycle and payload conflicts return sanitized 409 responses. A loan lock
serializes all supported writes for that loan; cross-loan key/event races are caught by
unique constraints. Ordinary reads do not take financial write locks.

PostgreSQL documents the row lock and isolation semantics used here:
[explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html) and
[READ COMMITTED consistency checks](https://www.postgresql.org/docs/16/applevel-consistency.html).

## Data model

All 13 business tables retain UUID primary keys and timezone-aware creation timestamps.
FK deletion is restrictive. Loan FKs, stable references, schedule ordering and correlation
fields are indexed. Dates are contractual/processing dates; timestamps identify instants.

| Table | Responsibility and constraints |
| --- | --- |
| borrowers | Unique external reference; borrower details |
| loan_products | Unique product code; supported frequency/method, bounded annual rate, INR |
| loans | Borrower/product FKs; unique reference; immutable principal, terms and algorithm snapshot; bounded tenure and principal; operational status |
| repayment_schedules | Unique loan/instalment; nonnegative principal/interest; immutable rows; stable loan FK |
| repayments | Positive bounded receipt; unique source/event; original idempotency link; occurred/received timestamps; explicit business date and canonical request hash; immutable |
| repayment_allocations | Same-loan composite FKs for receipt and schedule; unique receipt/schedule/component; positive amounts; immutable historical allocation |
| idempotency_requests | Unique actor/operation scope plus key; hash, original 201 response/body and completion; completed results immutable |
| ledger_accounts | Six seeded account codes, classification and INR; immutable chart; no balances |
| ledger_journals | Unique event key, receipt journal and reversal target; one disbursement per loan; consistent draft/posted timestamp; explicit processing date and economic effective timestamp |
| ledger_entries | Positive paise, debit/credit; account/journal FKs; optional schedule and original recognized receivable entry links |
| accrual_records | Unique scheduled recognition per schedule; unique loan/schedule/kind/start/end; same-loan schedule FK and unique journal (nullable only for zero-charge daily penalties); immutable daily basis/rate and one-day identities |
| users | Unique external subject, database role and active flag; three explicit demo subjects; no tokens or password imitation |
| audit_events | Actor, UTC creation timestamp, action, entity, correlation and minimized before/after/journal metadata; immutable |

The original two migrations are unchanged. `cf6472690571` adds business dates, request hashes,
ledger schedule/origin links, account/demo-user seed data and the reserved penalty journal
kind. Legacy timestamps are backfilled to UTC dates under transactional DDL locks. Existing
receipts lack canonical hashes and are rejected for automated source-event reuse pending
reconciliation. `0004` strengthens history, linkage, reversal and journal mutation guards.
Seed accounts/users remain on intermediate downgrade to preserve referenced history; full
base downgrade removes all tables. Financial-history downgrades are not supported rollback
procedures and may correctly fail on incompatible data.

## Authority and reconciliation

Receivable balances are sums of posted ledger entry debits minus credits, including
reversal entries. Draft journals never contribute. GET balance performs one aggregate
query and has no recognition side effects. It describes current posted receivables, not
a historical view or a later-day payoff quote.

Recognized interest/penalty debit entries are receivable lots. Collection credits link
back to the original debit; reversal debits retain that same origin. Lot outstanding is
computed from posted entries, sorted by effective date, contractual due date/instalment,
creation timestamp and entry UUID. Contractual tie-breaking keeps same-day charge allocation
reproducible across fresh database UUIDs. The database validates same-loan/same-account/same-schedule origin linkage.
This preserves oldest recognized allocation even when several charges share one schedule.

Principal was recognized as a whole at disbursement. Per-schedule active principal
allocations provide collection capacity, never the authoritative financial balance.
They exclude receipts whose journals have a posted reversal. Before posting, the service
checks every capacity is nonnegative and the sum matches ledger principal. Per-schedule
capacity caps and loan locking prevent over-allocation. No original schedule is rewritten.

## Immutability and reversal boundary

Draft entries are flushed before the posted transition. PostgreSQL requires at least two
entries and equal debit/credit totals. Entry mutation guards lock the journal row, reject
changes to posted entries, and prevent adding entries after posting. Posted journals,
receipts, allocations, schedule rows, account definitions, completed idempotency responses
and audit rows cannot be edited through ordinary SQL. Financial loan terms are frozen;
operational status can change. These guards do not protect against a privileged owner
who disables triggers, and are not a production database-permission design.

Only posted repayment journals may be reversed. Service and database enforce the same
loan, exact opposite entry multiset including schedule/origin links, unique original
journal, and no reversal chain. Receipts and allocations stay intact for audit. Current
receipt status is derived from a posted reversal, and active principal capacities exclude
that receipt. Later repayments remain effective. Retrying the original request returns
its historical accepted response; it cannot undo the reversal or receive money again.
Disbursement and recognition reversal are rejected until their lifecycle rules exist.

## Security and limits

`DEMO_AUTH_ENABLED` defaults false. Local setup explicitly enables database-backed header
impersonation. Roles never come from client headers. This is not production authentication;
there is no tenant, officer-assignment or borrower ownership filtering. All three roles
can read all demo loans; only managers/auditors can read audit history. Denied requests
store no monetary payload or unrecognized subject value. A production version needs real
identity verification, least-privilege DB users, retention rules and deployment hardening.

Cross-row schedule principal equality is enforced by origination and tested. Aggregate
allocation limits are enforced by serialized posting services with ledger reconciliation;
privileged raw inserts bypass that service contract. There is no public low-level journal,
low-level penalty-generation, recognition-job, historical balance, or replay HTTP API.
Accrual and replay are explicit local CLI operations. No loan is marked
closed merely because today's posted receivables reach zero: future contractual interest
may still become due. Account and receivable policy details are in the financial rules.


## Phase 3 daily accrual boundary

Migration 0005 extends accrual records with immutable opening principal basis and daily
rate, permits a null journal for zero-charge days, and introduces overdue_penalty kind.
A daily-penalty CHECK requires one half-open UTC day, the fixed 0.0005 rate, a bounded
basis and positive-charge/journal consistency. The existing unique loan/schedule/kind/
start/end constraint plus one-day intervals excludes duplicate and overlapping periods
for this kind. A trigger checks overdue eligibility, rounding and posted same-loan journal
linkage. Existing scheduled-interest identities and posted history remain intact.

`jobs/accrual.py` locks each loan before examining history. The entire loan's missing-day
catch-up, interest recognition, penalty journals, zero evaluations and job audit commit in
one caller-owned transaction. The batch coordinator commits each loan independently,
reports failures, retries uniqueness/deadlock conflicts and resumes by querying existing
period identities. There is no financial cache or in-memory safety lock.

Before accrual, current scheduled-principal capacities must reconcile with posted ledger
principal; inconsistent history fails before recognition or charges. Malformed receivable
lots retain fail-closed validation during deterministic ordering.

Daily opening basis is contractual schedule principal minus principal allocations processed
before that UTC date, with a reversal restoring principal only after its processing date.
The service reconstructs history rather than applying current capacity to past dates.
Business-date validation also consults immutable daily evaluations, including zero-charge
days, preventing later backdated operations from invalidating already evaluated history.
Same-date repayments/reversals affect the next day's opening balance. Existing exact retry
behavior is unchanged because deduplication precedes new-operation date validation.

The job and HTTP repayment path serialize on the same PostgreSQL loan row. Financial
safety does not require a scheduler. As in Phase 2, repayment collects recognized penalties;
a job that runs after a receipt does not retroactively change that receipt's allocation.
Concurrent orders can therefore produce different valid principal-versus-penalty collection
mixes. The replay fixes order by accruing before each day's deliveries. Every charge uses
the same historical opening basis regardless of when catch-up evaluates that date.

## Phase 3 simulation and independent verification

`simulation/generate.py` uses a fixed seed/UTC timeline, invented subjects and UUIDv5 logical
identifiers. Inputs and their ordering are reproducible. Server UUIDs are mapped to source
IDs in an explicit artifact; no client-chosen database primary-key shortcut was added.
The API keeps real receipt/audit timestamps, while every delivery retains a separate
simulated arrival time and explicit business date.

`simulation/reference.py` is a separate chronological specification using Decimal annuity
math and its own principal capacities/receivable lots. It imports no production posting,
schedule, ORM or job implementation. It generates intended statuses, canonical identities,
allocations, daily expected totals and per-loan final state before any API submission.

`simulation/replay.py` creates its own PostgreSQL database, migrates it and starts a real
loopback Uvicorn process. All borrower/loan/disbursement setup and all 5,000 repayment
attempts go through HTTP. Only accrual jobs use the documented service transaction boundary.
The runner records actual responses for successful, duplicate and rejected deliveries.
It compares observed allocations to reference expectations using instalment numbers,
checks the API balances, reruns accrual for idempotence and invokes independent raw-record
reconciliation. Cleanup stops its own server and drops only its own random database.

`simulation/reconcile.py` checks all journals and receipt cash/receivable effects, each
historical penalty basis/rounding, immutable schedule principal, active allocation caps,
and ledger-versus-operational-versus-reference balances. It does not call the production
balance calculator. Monetary totals are integer paise. Only timing metadata uses floats.
A normalized financial digest excludes generated DB UUIDs and real timestamps; inputs
have their own SHA-256 digest. Source and dependency versions accompany actual run results.
