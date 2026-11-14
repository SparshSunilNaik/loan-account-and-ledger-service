# LedgerCore - Technical Summary

A local-demo modular monolith built with Python 3.12+, FastAPI, Pydantic v2,
SQLAlchemy 2.x, Alembic and PostgreSQL. The database is authoritative; no external
financial service or AI model is required.

## Data model and precision

Thirteen relational tables separate borrowers, configurable products, loans, immutable
schedules, receipts, allocations, idempotency, accounts, journals, entries, accruals,
users and audit events. Loans snapshot terms and schedule version so product changes
cannot alter history. INR amounts use BIGINT integer paise; intermediate calculations
use Decimal and ROUND_HALF_UP. Strict inputs reject floats, booleans and invalid bounds.

## Schedule mathematics

Rates are annual nominal fractions: 12% is 0.12. Weekly conversion divides by 52;
monthly conversion divides by 12. Flat interest is P * annual_rate * n / periods_per_year.
Reducing EMI is P * r * (1+r)^n / ((1+r)^n - 1), with P/n at zero interest.
Deterministic final adjustments preserve total principal exactly. Monthly dates clamp
from the original date, so January 31 becomes February 28 and then March 31.
Schedules record contractual obligations, not payments or recognized receivables.

## Accounting and daily penalties

Disbursement debits principal receivable and credits cash. Due interest debits interest
receivable and credits income once. Repayment debits cash and credits recognized
penalties, interest, then due/future principal. Every posted journal balances and is
immutable; current balances sum posted entries, including controlled repayment reversals.
An explicit dated job charges 0.05% of opening unpaid overdue scheduled principal per
day, without compounding. Same-day principal payments affect the following day.
Zero-charge evaluations retain identities without journals; late catch-up never rewrites receipts.

## Transactions, retries and concurrency

Authorization precedes one caller-owned transaction and a PostgreSQL SELECT FOR UPDATE
loan lock. Receipt, recognition, allocations, journal, entries, idempotency result and
audit commit together. Actor-scoped keys store canonical hashes and original successful
responses; mismatched payloads conflict. Source/event uniqueness independently deduplicates.
A committed response lost to the client is safely retryable. Real PostgreSQL concurrency
tests include twenty competing repayments; only collectible amounts succeed, with no
principal over-allocation. No Python financial lock or cached authoritative balance is used.

## Executed replay evidence

Seed 20261114 generated 250 invented borrowers, 400 loans and exactly 5000 HTTP deliveries.
Observed outcomes: 4510 new receipts, 330 duplicate responses, 60 overpayments rejected,
50 invalid amounts, 25 authorization denials and 25 idempotency collisions. The duplicate
count includes 300 exact retries and 30 separately labelled source aliases. All 250
intended out-of-order accepted events were observed. Independent reconciliation verified
9903 balanced journals, equal debits/credits of 3641480368 paise, and zero principal,
interest or penalty differences. Expectations were generated separately from actual API results.

## One improvement with more time

Replace X-Demo-User impersonation with verified OIDC identity and explicit loan/tenant
ownership checks, backed by least-privilege database roles. Current database-backed role
checks are useful for local demonstrations but do not establish production identity.
