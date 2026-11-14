# LedgerCore Studio: product UX rebuild

**Local app:** http://127.0.0.1:3000/loans. **Backend:** http://127.0.0.1:8000.
Both services are kept in labelled persistent Terminal sessions for manual review.
No commit or push was made.

## What changed, and why

The organizing object is now a **loan account**, not a collection of API tools.

| Before                                           | Now                                                                       |
| ------------------------------------------------ | ------------------------------------------------------------------------- |
| Seven equally weighted navigation entries        | Loans, New loan, Activity, Testing                                        |
| Technical references dominate account headers    | Borrower name, actual product, readable account reference                 |
| Origination is one long form                     | Borrower → loan terms → actual saved schedule                             |
| Repayment is a separate laboratory               | Record repayment in the account side sheet                                |
| Posting evidence requires finding another screen | Allocation explanation and actual journal appear immediately              |
| Retry context belongs to a page                  | Selected account and frozen request follow the operator, including reload |
| A technical input starts discovery               | Filter browser-known borrower names; import a loan URL once when needed   |
| Midnight operator console                        | Warm-neutral light account workspace with locally served IBM Plex Sans    |

The [pre-implementation plan](design-plan.md) contains the usability audit, three prioritized
journeys, navigation map, four wireframes, compact tokens and design critique. Its selected
principles are recorded in [the master system](../../design-system/ledgercore-studio/MASTER.md).

### Navigation

```
Loans /loans
  Account /loans/{id}
    Schedule | Repayments | Ledger | History
    Record repayment (side sheet) → allocations + actual journal
    Disburse (appropriate status + manager)
New loan /new-loan
  Borrower → Loan terms → Review saved schedule → Open account
Activity /activity
  Selected-account Journals | Repayments | authorized Global audit log
Testing /testing
  Inherited request checks | Guided demo
```

All four destinations share the working account selector. Old URLs redirect to the appropriate
new destination. UUIDs, request keys and raw bodies remain inspectable as advanced evidence,
without becoming prerequisites for the normal servicing flow.

## Design skills: actual installation and use

- [UI UX Pro Max official source](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill):
  `npx --yes ui-ux-pro-max-cli init --ai codex` succeeded in `frontend/`, CLI **2.15.0**.
  The installed skill and search datasets live in `.agents/skills/ui-ux-pro-max/`.
- [Anthropic frontend-design, exact requested revision](https://github.com/anthropics/claude-plugins-official/blob/b5b01ac4f889fec0c4c6bb89f27ca7c8574473f6/plugins/frontend-design/skills/frontend-design/SKILL.md):
  successfully installed manually with the Codex skill installer into
  `.agents/skills/frontend-design/`. Its bytes matched the downloaded pinned source.
  This is **not** a claim that a native Claude plugin was installed in Codex.
- Both installed instruction files were read and applied directly during this task. Codex
  can discover the project-local skills when working from this frontend project in a new turn.
  [Integration metadata](skills/integration.json) records command, version and pinned-source hash.
- The design-system CLI ran for banking/fintech, forms, financial tables, developer tooling
  and Next.js. Broad marketing/crypto output was rejected; a narrower banking retry confirmed
  relevant typography and restrained enterprise structure. The actual form/table/a11y rules
  were reviewed for fit. No marketing template, crypto colors, GSAP, bulk financial edit,
  server-actions migration or external AI service was adopted.

The chosen direction is an account folio: porcelain/white surfaces, deep ink, restrained teal,
readable type and tabular amounts. Its characteristic feature is the **actual money movement**
after payment. No speculative KPI, decorative progress number or fake portfolio is shown.
One polished light theme is delivered; dark mode is deferred.

## Before and after: real Chrome captures

The before images were captured from the running old interface before application edits.
The after images come from real interactions with the optimized production build and actual
FastAPI/PostgreSQL responses. Each viewport run creates an invented borrower and loan through
UI forms. It posts one repayment, returns through the known-loan list, then exercises retries.
Mobile captures show the actual viewport; desktop/laptop captures can include the full page.

| Previous interface            | Capture                          |
| ----------------------------- | -------------------------------- |
| Operations home               | [Before](before/loans.png)       |
| Origination workspace         | [Before](before/new-loan.png)    |
| Populated loan account        | [Before](before/loan-detail.png) |
| Separate repayment laboratory | [Before](before/testing.png)     |
| Audit screen                  | [Before](before/activity.png)    |

| Actual workflow state             | 1440px                                   | 1024px                                   | 390px                                   |
| --------------------------------- | ---------------------------------------- | ---------------------------------------- | --------------------------------------- |
| Populated Loans, name filter      | [View](after/1440/loans.png)             | [View](after/1024/loans.png)             | [View](after/390/loans.png)             |
| Entered loan terms                | [View](after/1440/new-loan-terms.png)    | [View](after/1024/new-loan-terms.png)    | [View](after/390/new-loan-terms.png)    |
| Actual saved schedule             | [View](after/1440/saved-schedule.png)    | [View](after/1024/saved-schedule.png)    | [View](after/390/saved-schedule.png)    |
| Disbursed loan account            | [View](after/1440/loan-account.png)      | [View](after/1024/loan-account.png)      | [View](after/390/loan-account.png)      |
| Repayment receipt and allocations | [View](after/1440/repayment-result.png)  | [View](after/1024/repayment-result.png)  | [View](after/390/repayment-result.png)  |
| Immediately selected journal      | [View](after/1440/posted-journal.png)    | [View](after/1024/posted-journal.png)    | [View](after/390/posted-journal.png)    |
| Same account's repayment history  | [View](after/1440/repayment-history.png) | [View](after/1024/repayment-history.png) | [View](after/390/repayment-history.png) |
| Inherited request and useful 409  | [View](after/1440/testing-conflict.png)  | [View](after/1024/testing-conflict.png)  | [View](after/390/testing-conflict.png)  |
| Selected-account Activity         | [View](after/1440/activity.png)          | [View](after/1024/activity.png)          | [View](after/390/activity.png)          |
| Related actual audit events       | [View](after/1440/loan-history.png)      | [View](after/1024/loan-history.png)      | [View](after/390/loan-history.png)      |

Also: [completed guided demo](after/guided-demo.png), [actual offline state](after/backend-offline.png).
Screenshots show real generated IDs and synthetic borrower names, not visual fixtures or mocks.
No existing database was reset, and no original repayment was inserted directly into SQL.

## Hands-on UX evaluation

| Journey                                   | Observed interaction                                                                                                                                                 | Context / unnecessary entry                                                                                         |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| A: originate → disburse → repay → inspect | Create invented borrower, choose product/terms, inspect saved schedule, open account, change demo subject for disbursement, record ₹10 in sheet, select its posting  | Zero loan-ID or key entry. Two task destinations: New loan then Account. Repayment and journal stay inside Account. |
| B: return → state → schedule → repayments | Open Loans, filter by borrower name, reopen account, read ₹91 principal, navigate record tabs with keyboard, reload and retain selection                             | Zero ID entry; the same working account survives tab changes, navigation and reload.                                |
| C: post → retry → one receipt → collision | From the recorded payment, open Testing, use inherited request, retry, alias under a different key, check exactly one receipt, modify payload under the original key | Zero ID/key entry. Real HTTP 409 explains recovery; original identity remains available.                            |

All three journeys were completed at **1440, 1024 and 390px**. At every width the independent
₹100/12%-nominal/two-period case yielded a ₹10 receipt, ₹1 recognized interest paid and ₹9
principal settled: actual principal receivable **9,100 paise**, interest **0**, penalties **0**.
Retry and source alias reused the original receipt/journal. The changed-payload attempt left
that same one receipt and the same ledger-derived balances.

Keyboard evaluation exercised amount-field autofocus in the repayment sheet, Radix record-tab
arrow navigation, Escape dismissal, audit drawer dismissal and focus on validation failure.
The page-width checks cover all five distinct main/account layouts at all three widths; the
payment result sheet is also checked for local overflow. No document overflow or runtime
JavaScript errors were observed in the passing journey cases.

### Screenshot critique and changes made during evaluation

- The first new Ledger view repeated full technical entry tables. It now leads with a compact
  account/debit/credit payment table and keeps the full journal register collapsed below.
- On mobile, the Next development indicator blocked the bottom Loans control. The documented
  `devIndicators: false` setting removes that obstruction without suppressing runtime errors.
- The first mobile origination pass stacked all product options and repeated a large summary.
  Mobile now uses a native product selector with actual rate/method text and a compact borrower
  summary; desktop retains the useful direct product comparison.
- The import affordance initially still asked users to extract an ID. It now accepts the whole
  account URL, resolving only its ID against the configured local API, never fetching an
  arbitrary pasted remote URL.
- Test assertions were corrected to wait for route completion before reload and to distinguish
  the application's error summary from Next's independent route-announcer alert.

## Functional validation and practical limits

See [validation.json](validation.json) for final executed check counts and environment metadata.
The browser tests retained the financial protection checks while adopting the new user journeys:
manager-only single disbursement, auditor mutation denial, exact monetary validation, balanced
journals, atomic overpayment rejection, audit actor attribution, same-key collision and source
identity deduplication. The lost-response case lets the real API commit, drops its HTTP response,
reloads the app, edits the visible amount and retries the frozen request; one original receipt
remains. No backend success response is fabricated.

The unavailable-backend test uses a second temporary Next instance targeting an unused local
port. Its real proxy connection fails with HTTP 503. The user's main FastAPI service stays up.
The temporary server is stopped after validation. Native PostgreSQL 16.15 is used, not SQLite.
No Docker or full backend pytest rerun is claimed for this frontend task.

Remaining limitations are explicit:

- Discovery is limited to the current tab/session's 12 most recent references and exact link/ID
  lookup. A short external reference cannot be searched on the server. The separately documented
  [minimal read-only listing proposal](proposed-loan-discovery-api.md) is **not implemented**.
- Loan History matches up to the first 5,000 global audit records and reports the scan boundary;
  Activity offers real pagination. An all-history-per-loan API is absent.
- Preview means **actual saved schedule review after creation**, without disbursement. There is
  no pretend pre-creation schedule endpoint or new financial calculation in the frontend.
- Latest prepared requests are stored in session storage for recovery. They are instructions,
  not proof of payment. Before/after reads are separate observations, not a single atomic read.
- Origination lacks repayment-style idempotency. Uncertain creation outcomes need inspection
  before another attempt; backend behavior has not been changed to conceal that limitation.
- Demo authentication is not production-ready; there is no new reversal/job execution UI.
- Physical devices, Safari/Firefox and full assistive-technology certification remain unverified.
  This is a complete light theme, not an untested theme toggle.

All backend code, migrations, monetary/accounting policies, original submission ZIP and technical
write-up remain unchanged. The existing API client, exact money utilities, proxy and generated
contracts are preserved. [Exact changed files](changed-files.txt) includes the requested local
skill assets and licensed font as well as application, tests, design evidence and docs.

Startup commands are in [frontend/README.md](../../README.md). Nothing has been committed or pushed.
