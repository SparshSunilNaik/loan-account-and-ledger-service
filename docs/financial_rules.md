# Financial rules and calculation policy

## Scope and units

INR only. One rupee is 100 paise. Monetary columns are PostgreSQL BIGINT, Python amounts
are integers, and all intermediate financial arithmetic uses Decimal with a local
precision of 50 digits. Binary floats are rejected by the calculator. JSON rates are
strings; ORM rates are NUMERIC(12,10). Rounding is ROUND_HALF_UP to a whole paisa.

Origination principal is 1..100,000,000,000 paise (INR 100 crore), tenure is 1..600
periods, annual nominal rate is 0..1 inclusive (0%..100%). These are proposed engineering
bounds, not credit eligibility rules. Each stored component/event/entry is bounded by
100,000,000,000 paise. Schedule totals and intermediate EMI amounts can exceed the
principal bound; rounding utilities allow nonnegative signed BIGINT values. The
rupees-to-paise convenience utility enforces the origination bound. Negative and
nonfinite values are invalid even if they would round to zero. The API accepts paise
only. First due dates must fall in 1900..2100; later contractual dates may extend beyond
2100. Backdated schedules are allowed for deterministic historical scenarios.

## Configurable products

| Code | Name | Annual nominal rate | Method | Frequency | Periodic rate |
| --- | --- | --- | --- | --- | --- |
| WEEKLY_GROUP | Weekly Group Loan | 0.24 (24%) | Flat | Weekly | 0.24 / 52 |
| PERSONAL_EMI | Personal EMI Loan | 0.12 (12%) | Reducing balance | Monthly | 0.12 / 12 |
| SMALL_BUSINESS | Small Business Loan | 0.18 (18%) | Flat | Monthly | 0.18 / 12 |

These are illustrative assignment defaults, not market offers or regulatory APRs.
Rates are fractional annual nominal rates, never percentages stored as whole numbers.
No actual/365 day count, effective annual conversion, fees, holiday calendar or taxes
are applied. Weekly always divides by 52, monthly by 12, including leap years.
Products are configurable in the database; a product management API is outside Phase 1.
Loans copy terms once at origination. Product deactivation prevents new origination.

## Schedule version v1

Let P be principal in paise, n the number of instalments, a the annual rate and m the
number of periods/year. r = a/m. Input `first_due_date` is instalment 1; there is no
implicit disbursement date or stub interest period.

Weekly dates advance by seven days. Monthly dates are calculated from the original
first due date and clamped to the target month's last valid day. January 31 → February
28 (29 in leap years) → March 31. February 28 → March 28; there is no automatic
end-of-month promotion. All instalments have monotonically increasing dates.

For flat rate:

```text
total_interest_paise = half_up(P × a × n / m)
regular_principal = floor(P / n)
regular_interest = floor(total_interest_paise / n)
```

The first n−1 rows use those components. The final row receives all remaining principal
and interest. Flooring distributes indivisible integer amounts; ROUND_HALF_UP applies
to computed monetary amounts before distribution. This deliberate remainder policy avoids
negative final components when principal is smaller than the number of periods.

For reducing balance:

```text
EMI = P × r × (1+r)^n / ((1+r)^n − 1)
EMI = P / n when r = 0
regular_payment_paise = half_up(EMI)
interest_i = half_up(remaining_principal_paise × r)
principal_i = min(remaining_principal_paise, max(0, regular_payment_paise − interest_i))
```

Interest is computed on the rounded remaining principal. The final principal component
is exactly the remaining principal, with interest computed on that balance. The final
payment can therefore differ from the regular EMI; this is not a balloon agreement.
At extremely small principals rounding can produce zero components or early principal
exhaustion. Remaining zero rows are retained to preserve contractual row count. No
negative amortization is introduced by rounding. This is a paise-based amortization
policy; carrying unrounded balances would produce different interest totals.

The sum of principal must equal P exactly, every component is nonnegative, and there
are exactly n rows. These invariants hold for zero rates as well. A schedule is not
recomputed on GET and is not altered by payments or product changes.

## Independent examples

- Flat monthly: INR 1,000 (100,000 paise), 12%, 3 months. Interest = 100000 × .12 ×
  3/12 = 3000 paise. Principal rows 33333, 33333, 33334; interest 1000 each.
- Flat weekly: INR 520, 26%, 4 weeks. Interest = 52000 × .26 × 4/52 = 1040 paise;
  each row principal 13000, interest 260.
- Reducing: INR 100, annual 12%, two months. EMI = 10000 × .01 × 1.0201 / .0201
  = 5075.124378… paise, rounded 5075. First interest 100, principal 4975; remaining
  principal 5025. Final interest 50, final payment 5075. Total principal 10000.
  Annual 52% over two weekly periods gives the same 1% periodic calculation.
- Reducing annual: INR 12,000, 12%, 12 months. Rounded regular EMI 106619 paise;
  first principal 94619, interest 12000. Final principal 105558, interest 1056;
  total interest 79423. Eleven regular payments plus final 106614 = 1279423 paise.
- Zero interest: 100 paise / 3 periods → principal 33, 33, 34, no interest.
- Non-divisible interest: 101 paise at 20%, flat, three months → rounded interest
  5 paise, distributed 1, 1, 3. Principal 33, 33, 35.
- Half-paisa conversion: Decimal rupees `1.005` → 101 paise.

## Scheduled amounts, receivables and receipts

Schedules are immutable contractual expectations. Principal becomes a financial receivable
only when disbursement posts. Contractual interest becomes a receivable and income only
when recognized on or after its due date under an explicit processing business date.
Accepted receipts represent actual money and have separate economic occurred_at and
server received_at timestamps. Failed or duplicate deliveries are not new receipts.

All current balances are calculated from posted ledger entries, including reversals.
There is no authoritative balance column. GET balance never performs recognition and is
not a future payoff quote. Repayment recognizes eligible due interest before validating
collectibility. A repayment larger than principal + recognized interest + recognized
penalties is rejected atomically; unrecognized future interest is excluded.

## Phase 2 accounting

The immutable chart contains CASH, LOAN_PRINCIPAL_RECEIVABLE, INTEREST_RECEIVABLE,
INTEREST_INCOME, PENALTY_RECEIVABLE and PENALTY_INCOME. Receivables/cash are asset
accounts; the two income accounts are income. All entries use positive integer paise
with an explicit direction. Every posted journal contains at least two entries and
matching debit/credit totals. Cash is a demo settlement account, not a bank integration.
Per-loan cash can be credit-net following disbursement; no cash funding check is modeled.

| Operation | Debit | Credit |
| --- | --- | --- |
| Disbursement | Loan principal receivable | Cash |
| Due scheduled interest recognition | Interest receivable | Interest income |
| Repayment | Cash | Allocated principal, interest and penalty receivables |
| Supported repayment reversal | Exact opposite original entries | Exact opposite original entries |

Example: principal 10000 paise, monthly 12%, two instalments (principal 4975/5025,
interest 100/50). Disbursement debits principal receivable 10000 and credits cash 10000.
On January 31, recognition debits interest receivable 100 and credits interest income 100.
A 1000-paise receipt debits cash 1000, credits interest receivable 100, and credits principal
receivable 900. Remaining posted principal is 9100 and interest 0. Reversal credits cash
1000 and debits interest 100 and principal 900; original journals remain unchanged.

## UTC processing dates and recognition

Financial requests explicitly provide business_date as a calendar date interpreted in
UTC. It is never inferred from a local timezone or occurred_at. Database connections
return timestamps in UTC. occurred_at requires a timezone and is normalized to UTC before
hashing; its UTC date must be on or before business_date. Out-of-order economic arrivals
are allowed at the current processing date, without retroactive allocation recalculation.
Future simulation dates are allowed in this development assignment, relative to which
due eligibility is evaluated; this is not a wall-clock scheduling service.

New financial operations cannot move backward before an existing posted journal's
business_date. Exact key/event retries and reversal-target retries return their original
result before that check, so a lost HTTP response remains retryable after later activity.
This policy avoids using later recognized receivables in an earlier processing day.

recognize_scheduled_interest(session, loan_id, business_date, actor_id, correlation_id)
is independently callable by an authorized caller inside one Session.begin() transaction.
It obtains the loan lock and recognizes every positive scheduled interest row with
due_date <= business_date that has not already been recorded. The accrual identity is
schedule/kind with half-open period [due_date,due_date+1 day); that day is a recognition
identity, not a day-count computation. A unique schedule recognition index prevents
repeats. Economic effective_at is the due date at UTC midnight; business_date records
when processing happened. No future row is recognized and zero interest is a no-op,
without an empty journal or zero entries. Phase 3 adds a separate principal-only daily overdue penalty job, described below.

Prepaid principal does not change original contractual interest. Even after all principal
is paid, later scheduled interest still becomes due and collectible in this assignment.
A loan remains operationally disbursed; automatic closure is not implemented.

## Repayment allocation and prepayment

1. Pay oldest recognized penalty receivable lots first.
2. Pay oldest recognized interest receivable lots next.
3. Pay oldest due unpaid principal (due date, then instalment number).
4. Apply the remainder to future principal in the same contractual order.

Recognized lots are ordered by original economic effective timestamp, creation timestamp,
and entry UUID. Credits reference the original debit so later collections/reversals keep
lot identity. Multiple lots for one schedule are aggregated into one operational allocation
per receipt/schedule/component while preserving distinct journal credits.

Principal capacity is original scheduled principal minus active, unreversed receipt
allocations for that schedule. Each capacity and the aggregate are checked against the
ledger under the loan lock. A prepayment settling future principal therefore reduces later
collection capacity, without mutating schedule rows. Reject zero/negative/excessive amounts;
never collect future interest. No automatic interest rebate or re-amortization applies.

## Idempotency and atomicity

Repayment POST requires Idempotency-Key (1..200 identifier characters). The unique scope
is database actor UUID + repayment operation; the key is global across that actor's loans.
A canonical SHA-256 hash includes loan UUID, integer amount, normalized source/event,
normalized UTC occurred_at and business_date. Correlation and key are excluded.

Same key/hash returns the original successful 201 and body. Different hash returns 409.
Source + external_event_id is globally unique: the identical canonical request under a
new key returns the same original result, stores that key as an alias and never posts
again. A mismatched source payload or different loan returns 409. Equivalent timezone
offsets normalize to the same instant. Only successful results are retained; rejected
requests roll back their pending key and can be corrected/resubmitted.

Receipt, allocations, auto-recognition, journal, entries, idempotency result and successful
audit commit together. Posting services never commit. Authorization precedes the financial
transaction, then SELECT FOR UPDATE locks the loan, then identity/deduplication is resolved.
Uniqueness/deadlock/serialization conflicts retry the whole transaction at most three
times before a sanitized 409. Different loans can run in parallel while DB uniqueness
handles shared key/source races. There is no Python lock for financial safety.

## Controlled reversal

Managers may reverse only posted repayment journals. Disbursement, recognition and reversal
journals are unsupported targets (409); a journal on another loan is absent (404). A new
balanced journal must contain exactly opposite entries, with identical account/amount/
schedule/receivable origin, and reference the original exactly once. Database checks
also enforce this at posting. Reversing a reversal is unsupported.

Reversal is idempotent by original journal UUID: subsequent valid requests return the
existing reversal, with the first committed reason and business date retained. Receipt
and allocation rows remain immutable. GET receipts derives current reversed status;
active collection capacity excludes reversed receipts. Other payments stay effective.
Original successful idempotency responses are historical facts and remain unchanged;
retrying a reversed event returns that response and never reinstates the receipt.

A loan can be disbursed only once, enforced by both the service and partial unique index.
No disbursement reversal is exposed and reversing any journal cannot authorize a second
disbursement. Financial mutations are audited with actor, UTC time, correlation,
before/after state and journal references. Denied role attempts commit minimized audit
metadata separately; they do not mutate financial state.

## Phase 3 daily overdue policy

The fixed simple daily penalty rate is **0.05% = Decimal("0.0005")**. For each schedule and
eligible UTC date D, charge ROUND_HALF_UP(opening unpaid scheduled principal × 0.0005)
paise. Eligibility starts strictly after the contractual due date and strictly after the
loan's disbursement business date. No charge is levied before funds were disbursed.
Each schedule/day is rounded independently; rounded daily charges are then summed.
Interest and previous penalties never enter the basis and penalties do not compound.

Opening principal for D subtracts principal allocations with receipt business_date < D.
A posted repayment reversal restores its principal from the day after the reversal's
business date. Economic occurred_at is not a basis restatement date. Same-day payments
and reversals influence D+1, so accrual versus receipt lock acquisition cannot change
D's opening charge. Catch-up reconstructs each day's actual processing history, rather
than charging all historical dates on today's principal.

Examples: 4975 paise overdue principal produces 2 paise/day (2.4875 rounded half-up).
1000 produces 1 (0.5 rounds up); 999 produces 0. After a payment reduces a 4975-paise
schedule to 975, the following day's charge is 0, while the payment date retains its
opening-day charge. Reversing that payment restores the basis only from the next date.

Each evaluation stores loan/schedule/overdue_penalty/[D,D+1), opening basis, fixed rate
and rounded amount. Positive charges debit PENALTY_RECEIVABLE and credit PENALTY_INCOME,
with schedule-tagged recognized lots. Zero charges keep the evaluation record and have
no financial journal. One-day period constraints and unique identities prohibit duplicate
or overlapping days; all evaluations are immutable. Their latest date also participates
in the loan's new-operation business-date floor, including zero-charge history.

Catch-up journals have business_date equal to the explicit processing target and economic
effective_at equal to the evaluated day's UTC midnight. No earlier journal or receipt is
edited. Existing scheduled interest is recognized through the original recognition service
exactly once and is never recognized again as a penalty or overdue interest amount.

The CLI defaults to the explicit day only; --catch-up fills every missing eligible day,
including zero-basis days. A failed loan rolls back all of its new evaluations, journals,
entries, recognition and audit. Other loans may commit; rerun resumes missing work. The
same loan lock as repayment/reversal protects concurrent execution. The default maximum
catch-up horizon is 3660 days; longer histories need an explicit larger bound.

Repayments continue to collect only recognized penalties. If the job is late, a previous
receipt is not reallocated when catch-up posts additional penalties. Run accrual before
daily deliveries for a fixed processing order, as the replay does. Concurrent orders are
serialized and financially valid but can yield a different mix of principal and penalty
collected; this is explicit rather than a retroactive rewrite of immutable receipts.

## Replay interpretation

The generated manifest is an independent expectation, not an observed result. The runner
records actual HTTP results and reads database effects. There are exactly 5000 deliveries,
not 5000 receipts. Exact duplicate financial payloads preserve their original business
dates while later delivery IDs/arrival times differ. Source aliases are separately labelled.
New delayed events retain economic occurred_at and use their simulated receipt business
date. Canonical request/key semantics from Phase 2 remain unchanged.

The simulation uses invented source UUIDs and fixed dates. Actual API UUIDs and server
receipt/audit times are retained as observed and mapped separately. Financial reproducibility
compares normalized actual allocations, final balances and journal totals; it does not
claim real wall-clock timestamps are byte-identical between independent runs.

## Remaining limits

No automatic interest rebate, re-amortization, real bank settlement, multi-currency,
backdated restatement or general journal adjustment is implemented. Reversals remain
restricted to repayments. Production identity, ownership scoping and database permissions
need a separate design. These are assignment policies, not regulatory guidance.
