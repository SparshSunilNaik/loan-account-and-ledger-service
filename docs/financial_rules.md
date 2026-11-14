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

A schedule records contractual future principal/interest, not recognized income, a
posted asset balance, money already disbursed, or money received. Financial receivables
will be derived from posted balanced journal entries. Payment receipts will record actual
accepted money, its economic `occurred_at` and server `received_at`. Repayment deliveries
can repeat or fail; deliveries and successful receipts are different populations.
No financial receivable or collectible outstanding field is exposed in Phase 1.

## Proposed posting policies — deferred implementation

1. Allocate to penalties, then interest, then principal. Within each component class,
   process oldest due instalments first (due date, then instalment number). Confirm this
   precedence before Phase 2; instalment-first priority would produce different results.
2. Reject any overpayment beyond collectible outstanding amounts. What future principal
   is collectible before maturity and any prepayment/rebate rules need approval before
   implementing this comparison. Do not substitute scheduled lifetime interest for an
   immediately payable receivable.
3. Posted journals and their entries cannot be silently edited. Use a new balanced
   reversal journal referencing the original and preserving the audit trail. Phase 2
   must enforce exact opposite entries, posted target and same-loan linkage.
4. A loan can be disbursed only once. A unique loan disbursement index is already present;
   a reversal does not permit a second disbursement under this proposed policy.
5. Serialize concurrent financial mutations for one loan (e.g. transaction-scoped row
   locking). Define lock ordering and concurrency tests in Phase 2. Phase 1 has no locks.
6. Recognize scheduled interest once per schedule row. An overdue job must not accrue the
   same scheduled interest again. Any distinct overdue charge requires an approved basis,
   rate, period boundaries and income/receivable accounts; none is calculated yet.
7. Overdue records use schedule/kind/start/end identity, with half-open periods [start,end).
   Exact repeats are constrained now; overlapping periods need later validation. A late
   arrival must not silently change already recognized interest.
8. All financial transactions are atomic: event, allocation, journal, entries, idempotency
   result and audit must commit or roll back together. Phase 1 origination is atomic.
9. Idempotency keys are scoped to authenticated principal/operation; store a canonical
   request hash. Same key/same request reuses the outcome; same key/different request
   conflicts. Source event IDs provide a separate duplicate check. Phase 1 only prepares
   these records and unique constraints.

Confirm penalties, prepayment, recognition timing, journal chart of accounts, late-arrival
corrections and role permissions before implementing subsequent phases. No policy here
claims production accounting or regulatory compliance.
