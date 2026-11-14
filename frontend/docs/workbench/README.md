# LedgerCore Workbench

A persistent financial workstation using the approved Precision Finance identity. **Loans, New loan, Activity, Testing** remain the four destinations. No backend financial policy, schema, migration, API contract, verified submission ZIP or technical write-up changed. No new dependency, commit or push.

## Before / after friction analysis

Before application edits, installed Chrome executed all three journeys against the approved production app and real native PostgreSQL/FastAPI. Afterward, the same script executed equivalent operations against the new production app. Each run originated a fresh invented borrower/loan, explicitly disbursed it, posted a partial repayment and checked real receipt/journal results. [Plan and audit](plan.md).

| Journey | Pointer clicks | URL changes (including tab query) | Maximum document overflow at 1440×900 | Automated elapsed |
| ------- | -------------- | --------------------------------- | ------------------------------------- | ----------------- |
| A       | 7 → 5          | 2 → 1                             | 801px → 0px                           | 1138 → 1044ms     |
| B       | 6 → 5          | 4 → 3                             | 1145px → 0px                          | 330 → 301ms       |
| C       | 3 → 3          | 1 → 0                             | 769px → 0px                           | 323 → 541ms       |

A = originate → disburse → partial repayment → inspect posting. B = return through known loans → repayment details → linked journal. C = exact retry → changed-payload conflict.

These are **actual automated pointer click events**, not estimated human mouse counts. Automation `fill` and `selectOption` operations are excluded from click counts; field entries are reported separately. A used **8 field entries before and after**; B used 1; C used none. Repeated entry of the same field and manual loan-ID entry were **zero in both versions**. No new improvement is claimed for UUID entry already eliminated by the previous UX.

Document scroll events were 2 → 0 for A, 1 → 0 for B and 1 → 0 for C. Internal table/inspector scrolling is intentionally permitted and not called document scrolling. The desktop test also checks that the ordinary three-entry repayment journal's balance row is actually inside the viewport, not merely present in the DOM.

One intentional URL change remains in A: the created loan opens at its durable account URL automatically so refresh restores the correct workspace. No separate Open account click is needed. B retains the two discovery/account transitions and updates the tab query without an RSC navigation. Receipt, journal and audit selection do not change the URL. C stays in the account instead of navigating to Testing.

### Timing provenance and limits

| Observation                                 | Before | After |
| ------------------------------------------- | ------ | ----- |
| A: fill/submit repayment to verified result | 484ms  | 429ms |
| A: inspect associated journal               | 61ms   | 33ms  |
| B: open repayment details                   | 21ms   | 38ms  |
| B: inspect linked journal                   | 117ms  | 29ms  |

These single local samples include browser automation, API latency and screenshot synchronization. They exclude human reading/typing time; cache, database size and background test load changed. They are **not a user study or statistically controlled performance benchmark**. Some individual timings and C's total elapsed time increased; this phase claims fewer navigation/scroll requirements, not uniform latency improvement. The original readout in B was an allocation JSON disclosure; the new inspector presents additional linked accounting data.

Raw evidence: [before JSON](before/measurements.json), [after JSON](after/measurements.json), [measurement script](../../scripts/measure-workbench.mjs). Both app versions ran as production builds on the same Mac and database, without resets. The original interface is no longer served; the script's before mode is retained for provenance, not to run against the current workbench.

## What changed

- **Persistent composition:** compact header, fixed loan identity/status/position, a main scrollable record region and an adjacent inspector at desktop/laptop widths. The document stays within a 900px viewport in measured ordinary journeys. Existing semantic theme tokens, typefaces and brand marks remain.
- **Contextual financial inspector:** select a repayment for allocation rows, its real journal and current backend receivables. Select a journal for actual debit/credit entries and its linked receipt where available. Selecting an audit action reveals actor, UTC timestamp, entity, correlation and available metadata. No fake historical balances: current receivables are explicitly labelled current, not a reconstruction at that posting time.
- **Repayment:** a non-modal adjacent panel on desktop and modal bottom sheet on mobile. It retains the amount/time/date while switching account panels. Successful results show actual HTTP outcome, receipt allocations, balanced journal and observed receivables; the summary refreshes from backend reads. No optimistic financial update or automatic submission.
- **Advanced delivery checks:** one summary action opens the same inspector's testing controls. Exact retry uses the frozen actor, amount, dates, source, event and key. **Modified-payload/source-alias tests require verification of the original receipt and journal first**, so an uncertain request cannot accidentally become a different payment. Unknown outcomes remain frozen after refresh. New repayment / Edit as new are explicit preparations, never silent retries under new keys. The separate Testing destination retains full overpayment and guided-demo behavior.
- **Origination:** compact progressive steps and desktop product comparison, with draft values preserved through client navigation and step changes. Confirmed creation automatically opens the saved account/schedule. A manager must still explicitly review the disbursement date and press Disburse loan. Return to New loan for New application after completing one.
- **Discovery:** the header selector can open a locally known account directly from Loans. The command palette searches session references/actions, not the database. Exact link/ID import remains optional and never recurs inside servicing workflows.

## Keyboard shortcuts

| Shortcut                      | Behavior                                                      |
| ----------------------------- | ------------------------------------------------------------- |
| ⌘K / Ctrl+K                   | Open commands and known session references                    |
| ↑ / ↓ / Enter / Escape        | Choose, open or dismiss a palette command                     |
| Alt+1 / Alt+2 / Alt+3 / Alt+4 | Schedule / Repayments / Ledger / History                      |
| Alt+P                         | Open repayment if current role and disbursement status permit |
| Alt+R                         | Refresh actual financial reads                                |

Alt shortcuts ignore text inputs, selects and editable content; physical key codes handle Mac Option-key variants. None submits a financial mutation. Palette creation/audit commands respect actor permissions; officer/auditor restrictions are explained. All backend requests remain independently authorized. Named scroll regions, native controls and visible focus remain keyboard operable.

## Populated screenshot evidence

All screenshots use real responses and invented local data. The 1440px and mobile cases below use Dark; the 1024px case uses Light. Full dual-theme regression captures are linked separately.

| State                                 | 1440×900                                   | 1024×900                                   | 390×844                                   |
| ------------------------------------- | ------------------------------------------ | ------------------------------------------ | ----------------------------------------- |
| Entered origination terms             | [View](screens/1440/new-loan-terms.png)    | [View](screens/1024/new-loan-terms.png)    | [View](screens/390/new-loan-terms.png)    |
| Actual saved schedule                 | [View](screens/1440/saved-schedule.png)    | [View](screens/1024/saved-schedule.png)    | [View](screens/390/saved-schedule.png)    |
| Disbursed account                     | [View](screens/1440/account.png)           | [View](screens/1024/account.png)           | [View](screens/390/account.png)           |
| Allocation and balanced posting       | [View](screens/1440/repayment-result.png)  | [View](screens/1024/repayment-result.png)  | [View](screens/390/repayment-result.png)  |
| Selected repayment and linked entries | [View](screens/1440/receipt-inspector.png) | [View](screens/1024/receipt-inspector.png) | [View](screens/390/receipt-inspector.png) |
| Selected financial journal            | [View](screens/1440/journal-inspector.png) | [View](screens/1024/journal-inspector.png) | [View](screens/390/journal-inspector.png) |
| Actual idempotency conflict           | [View](screens/1440/conflict.png)          | [View](screens/1024/conflict.png)          | [View](screens/390/conflict.png)          |
| Keyboard command palette              | [View](screens/1440/command-palette.png)   | [View](screens/1024/command-palette.png)   | [View](screens/390/command-palette.png)   |
| Actual audit event                    | [View](screens/1440/audit-inspector.png)   | [View](screens/1024/audit-inspector.png)   | [View](screens/390/audit-inspector.png)   |

[Long 48-instalment schedule, scrolled internally](screens/1440/long-schedule.png).

| Measured workflow            | Before: approved Precision Finance  | After: Workbench                  |
| ---------------------------- | ----------------------------------- | --------------------------------- |
| Origination / saved schedule | [Before](before/origination.png)    | [After](after/origination.png)    |
| Repayment                    | [Before](before/repayment.png)      | [After](after/repayment.png)      |
| Posted journal               | [Before](before/journal.png)        | [After](after/journal.png)        |
| Returning to receipt details | [Before](before/record-details.png) | [After](after/record-details.png) |
| Retry / conflict             | [Before](before/retry-conflict.png) | [After](after/retry-conflict.png) |

Current full light/dark workflows: [Light desktop](regression/themes/light/1440/), [Dark desktop](regression/themes/dark/1440/), [Light mobile](regression/themes/light/390/), [Dark mobile](regression/themes/dark/390/). The original financial/theme suite remains; its captures are now redirected into this phase. Initial dev runs refreshed some old Precision Finance gallery screenshots; its report is annotated, and the five `before/` images here are the reliable pre-edit baseline.

## Validation and review

[Executed validation](validation.json) records final counts, commands, environment and the resolved iteration failures. Existing financial checks remain: balanced journals and ledger-derived reconciliation, same-key retry, source deduplication, payload conflict, auditor denial, atomic overpayment rejection, actor-attributed audit and lost HTTP response after an actual committed transaction. New workbench checks exercise no-route inspection, original-key recovery after workbench refresh, safe gating before modified tests, origination drafts, role-aware commands, actual clipboard behavior retained by the theme suite and internal scrolling of a real 48-row schedule.

Screenshot critique led to a tighter posting result, journal placement before duplicate balance detail, stable rapid-reopen autofocus, a separate Delivery checks shortcut, and a collapsed idle inspector on laptop widths. Before-paint theme/OS/storage/reduced-motion coverage remains. Capture helpers retain keyboard focus rather than blurring the palette before Enter.

## Known limitations

- Recent-loan discovery is capped at 12 current-tab references. There is no new server portfolio/search endpoint. Audit history scans at most 5,000 global events; Activity keeps real pagination. Per-loan schedule/repayment/ledger APIs return their existing full records, not new server pagination.
- Unsent origination drafts survive client-side navigation and step changes, **not a full refresh before creation**. Origination has no repayment-style idempotency; uncertain creation still requires record inspection.
- After posting, use **New repayment** to prepare another instruction. Unknown outcomes stay frozen until explicitly retried/verified or deliberately edited as new with the existing warning.
- Long tables/results scroll internally; laptop inspectors collapse while idle, are compact when active and have no drag resizer. Mobile uses document scrolling plus a bottom sheet and visible action rather than narrow desktop columns.
- Financial before/after reads are separate observations, not atomic snapshots. Current receivables are not future payoff quotes; no accrual/job, reversal mutation, schedule recalculation or balance cache was introduced.
- Demo users are development-only impersonation, not production security. Physical devices, Safari/Firefox, full assistive-technology certification and Docker execution were not tested. Native PostgreSQL was used; the full backend pytest suite was not rerun for this frontend-only task.

[Exact changed files](changed-files.txt) includes code, tests, documentation and actual generated captures relative to the start-of-task snapshot. [Startup commands](../../README.md). Both main servers remain in labelled Terminal sessions; the temporary offline instance is stopped after verification.
