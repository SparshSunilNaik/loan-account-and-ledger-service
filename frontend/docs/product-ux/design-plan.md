# Product rebuild: design plan (written before application changes)

## Usability audit

The prior live application separates a single servicing task into seven destinations.
Borrower/loan creation lives in a workspace, repayment in a laboratory, and accounting in
an inspector. A returning operator must remember which technical tool to use. Large UUID
inputs and HTTP terminology appear before borrower names. The existing selected-loan store
helps technically, but navigation does not communicate that context. A payment result does
not naturally lead to its accounting entry. Tables are readable yet dominate the journey;
repeated explanations and separators substitute for task hierarchy.

OpenAPI inspected: exact borrower lookup and loan lookup exist; loan listing/search and
portfolio aggregate endpoints do not. Financial receivables are exposed through `/balance`.
The ledger and repayment endpoints return all posted records for one loan. Audit pagination
is global; no per-loan audit filter exists. No new backend endpoint will be implemented.

## Three prioritized journeys

1. **Originate and service:** New loan → create borrower → select product/terms → create and
   review actual saved schedule → open account → manager disbursement → record repayment
   in a side sheet → see allocations and the actual posted journal without leaving account.
2. **Return and understand:** Loans → filter explicitly browser-known references/names →
   open account → read posted principal/interest/penalty → schedule → repayments. No UUID
   re-entry; one account context is retained through tabs and primary navigation.
3. **Verify an uncertain delivery:** Record repayment → Testing inherits selected account
   and frozen request → retry identical → compare actual receipt/journal identities →
   change payload under same key → useful conflict feedback and original evidence retained.

## Navigation map

- Loans `/loans`: browser-known account list, local filtering, explicit one-time exact-ID lookup.
  - `/loans/{id}`: borrower/product + posted state + Record repayment / appropriate Disburse.
    - Schedule, Repayments, Ledger, History. Tabs retain account and deep-link via query string.
    - Record repayment sheet: amount/time/date, generated technical identity, result + journal.
- New loan `/new-loan`: Borrower → Loan terms → actual schedule review → account.
- Activity `/activity`: selected-account journals and repayments; authorized global audit log.
- Testing `/testing`: advanced request checks, source-alias duplicate checks and guided demo.

Old URLs remain as compatibility entry points, without becoming primary navigation items.
The shell always names the selected reference and lets the operator switch to a visited loan.
Request keys are advanced details, not prerequisites for recording a normal payment.

## Low-fidelity wireframes

Loans (the workspace, not a portfolio dashboard):

```
[LedgerCore Studio] Loans | New loan | Activity | Testing   [Demo identity]
[Working account: Select / switch visited account]          [API connected]
Loans                                                    [New loan]
Known in this browser. Not the complete server portfolio.
[Filter known names or references]             [Open by reference]
Borrower / account         Product          Status         [Open]
Mira Sample / LC-…          Personal EMI     Disbursed       Open account
[Supported product terms, secondary disclosure]
```

Loan detail (primary object, actions in place):

```
[Back to loans]        Working account remains selected
Mira Sample                       [Disbursed] [Record repayment]
Personal EMI / LC-…                  [Disburse when appropriate]
Principal outstanding       Recognized interest        Penalties
₹…                          ₹…                         ₹…
[Schedule] [Repayments] [Ledger] [History]
Actual rows / records                         Repayment side sheet →
                                             Amount, payment time, date
                                             [Record repayment]
                                             Applied to interest/principal
                                             Actual posted journal [View]
```

New loan:

```
New loan                         Borrower → Loan terms → Schedule
[Borrower name] [Optional phone]    Context summary, no fake quote
[Continue with borrower]            Selected borrower and real product
--- next stage ---
[Product choices with actual rates] [Principal INR] [Periods] [First due]
[Create loan & review schedule]
--- success ---
Saved contractual schedule (actual API rows)   [Open loan account]
```

Testing:

```
Testing                    Working account: Mira Sample / LC-…
[Request checks] [Guided demo]
Last frozen delivery from account repayment, if available
[Retry identical] [Changed payload] [Source alias] [Auditor] [Overpayment]
Request editor (advanced)                  Actual result + IDs + before/after
```

## Compact design system: account folio

- Base: porcelain `#F6F7F4`, white `#FFFFFF`, ink `#172D36`, muted `#53656C`,
  teal `#126A70`, quiet sea tint `#E7F0EE`. Warm-neutral light; no clay/serif pastiche.
- IBM Plex Sans for the whole interface, locally served; system monospaced fallbacks only
  for optional technical references. Tabular figures use the UI face, not terminal typography.
- Scale: 32/26 page titles, 20 contextual headings, 16 body/forms, 14 table text, 12 metadata.
- Spacing: 4/8/12/16/24/32/48. Forms bounded around 600px, comfortable touch targets.
- Components: one primary action per task, restrained status tags, accessible Radix sheets,
  purposeful disclosure for technical details, focusable linked validation feedback.
- Tables: clear column roles, right-aligned exact amounts, local overflow on narrow screens,
  expandable accounting entries. Debit/credit words and balance checks do not depend on color.
- Memorable element: **money movement**, a plain-language explanation of actual repayment
  allocations followed by its actual accounting entry. Not a decorative dashboard metric.
- Mobile: four-item navigation, selected-account switcher, full-height repayment sheet,
  primary actions first and secondary detail disclosed. No app-wide horizontal overflow.

## Skill integration and critique

UI UX Pro Max was installed with `npx --yes ui-ux-pro-max-cli init --ai codex` into this
project's `.agents/skills/`. Anthropic frontend-design was installed manually with Codex's
skill installer at exact revision `b5b01ac4f889fec0c4c6bb89f27ca7c8574473f6`.

The recommendation CLI was run for banking/fintech, forms, tables, developer tooling and
Next.js. Its first broad result mixed marketing conversion patterns and crypto colors;
a narrower retry confirmed relevant banking minimalism and IBM Plex Sans. Marketing
layouts, gold/purple/dark palettes, blanket server-action migration, GSAP and bulk financial
mutations were rejected as irrelevant or conflicting with this brief. Verified principles
are adopted here; unverified recommendations are not treated as requirements.

Anthropic's exact-revision criteria drive critique: subject-specific account language;
no arbitrary eyebrows, decorative sequence markers, acid-dark styling or generic cream /
clay / serif combination; useful empty/error recovery; disclosure over explanation overload.
The operator sees a borrower and a task before implementation terms. The selected loan
and the submitted request identity are reused instead of entered again.

This direction is selected for implementation in this task without a confirmation pause,
as explicitly requested. Dark mode is deferred to finish and verify one coherent light theme.
