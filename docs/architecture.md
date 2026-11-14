# Architecture

LedgerCore is a modular monolith. One application and one PostgreSQL database keep
origination and its schedule in a single transaction. Synchronous FastAPI routes run
SQLAlchemy sessions in worker threads; each request owns a fresh session. There is no
network service boundary within the domain and no background worker in Phase 1.

| Module | Responsibility |
| --- | --- |
| `api` | Routes, response codes, transaction boundaries, sanitized constraint errors |
| `schemas` | Pydantic v2 input and output contracts, strict financial integers |
| `services` | Origination and pure Decimal schedule/money functions |
| `models` | SQLAlchemy relational entities and constraints |
| `db` | Environment configuration, engine/session factory |
| `accounting` | Protocol for future posting; no implementation |
| `security` | Role preparation and explicit authentication limitation |
| `jobs` | Future job boundary; no scheduler |
| `migrations` | Versioned schema, seeded products and journal guards |

The database is the authority. No process memory, derived balance column, or product
lookup can replace persisted financial records. Loan origination snapshots annual nominal
rate, method, frequency, currency, principal, tenure, first due date and schedule algorithm
version (`v1`). Persisted schedules reference the immutable loan UUID. Keep old algorithm
implementations when introducing `v2`; do not regenerate historical schedules using an
updated product. No API allows editing loan terms or schedule rows.

## Tables and integrity

All business tables have UUID primary keys and timezone-aware creation timestamps.
FK deletion uses PostgreSQL's restrictive default, preventing cascading financial loss.
Dates represent contractual due/period dates; event times are timezone-aware timestamps.
Indexes cover lookup references, loan FKs, due-date ordering and event correlation.

| Table | Purpose and principal constraints |
| --- | --- |
| borrowers | Unique external reference, name and optional phone |
| loan_products | Unique product code; rate 0..1, INR, supported method/frequency |
| loans | Borrower/product FKs; unique external reference; snapshot terms; positive bounded principal; tenure 1..600; valid lifecycle status |
| repayment_schedules | Loan FK; unique `(loan_id, instalment_number)`; nonnegative bounded components; indexed loan/due date |
| repayments | Loan and optional idempotency-request FKs; unique `(source, external_event_id)`; positive bounded amount; `occurred_at` and `received_at` |
| repayment_allocations | Composite FKs tie repayment and schedule to the same loan; unique repayment/schedule/component; positive amount; penalty/interest/principal |
| idempotency_requests | Unique `(scope, key)`; request hash, pending/completed state, optional result and completion time |
| ledger_accounts | Unique code; account classification, INR; no balance column |
| ledger_journals | Loan and optional repayment/reversal FKs; unique event key, repayment journal and reversal target; partial unique loan index for disbursement; draft/posted consistency |
| ledger_entries | Journal/account FKs, positive bounded BIGINT amount, debit/credit direction |
| accrual_records | Loan, same-loan schedule and journal FKs; unique loan/schedule/kind/start/end; unique scheduled recognition per schedule; valid nonempty period |
| users | Unique external identity subject, supported role, active flag; no fake password/token system |
| audit_events | Optional actor FK, indexed action/entity/correlation, JSON metadata |

Migrations contain a frozen initial schema (no runtime `metadata.create_all`) and a second
revision for product seed data and PostgreSQL journal protections. Seed UUIDs are stable;
configuration changes afterward do not affect existing loans. Migrations do not seed
borrowers, users, repayments, accounts or posted journals.

Journal entry guards reject insert/update/delete affecting posted journals. A draft may
be assembled and then marked posted; the database requires at least two entries with
matching debit and credit totals before that transition. Posted journal updates/deletes
are rejected. A reversal is a separate journal referencing the original with a unique
target; original records remain intact. Reversal amounts, target posting state and
same-loan accounting linkage must be verified by the later posting service. This schema
preparation is not a completed ledger engine.

Phase 1 does not promise safety under concurrent financial posting. The guard checks
are not a replacement for serialized per-loan transactions and restricted DB write
permissions. Phase 2 must establish lock ordering and concurrency tests before exposing
posting. Direct privileged SQL can bypass application invariants; production roles and
immutable term/schedule permissions need review before deployment.

Cross-row principal equality is enforced by the deterministic schedule service and tested,
not by a SQL CHECK. Allocation totals, journal/event correspondence, reversal equality,
receivable sufficiency and overlapping overdue periods need service validation in later
phases. Accrual uniqueness blocks identical period identifiers, not arbitrary overlapping
intervals. Audit entries currently identify unauthenticated origination with a null actor;
only successful borrower/loan creation is audited. Full security/rejection audit belongs
to the authenticated phase, with minimized sensitive payload retention.

## Atomicity and future contracts

Routes wrap writes in `Session.begin()`. A failure rolls back borrower/loan, schedule and
audit records together. Reads close their sessions without retaining transactions.
The posting protocol accepts the caller's Session and must never commit independently.
Future financial transactions must authorize, lock the loan, validate/reuse idempotency,
calculate collectible amounts, write events/allocations/journals/entries/audit and commit
as one unit. Use DB uniqueness as a final safeguard, not as the entire replay strategy.
No posting or locking code is implemented yet.

Reference: [SQLAlchemy transaction context management](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
and [PostgreSQL trigger behavior](https://www.postgresql.org/docs/16/sql-createtrigger.html).
