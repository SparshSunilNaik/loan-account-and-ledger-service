# Studio interface redesign

The redesigned application is available locally at **http://127.0.0.1:3000**.
FastAPI remains at **http://127.0.0.1:8000** with demo authentication enabled.
Both run in the existing labelled Terminal sessions.

## Design audit and changes

Before editing, every live page was inspected in Chrome with an actual fresh-loan flow,
including a populated schedule, ledger and audit trail. Existing screenshots were reviewed.
The repeated rounded panels, tiny type, full-width notices and duplicated evidence made
unrelated tasks look alike and pushed important results below the fold.

The new system uses charcoal surfaces (`#111316` / `#181b1f`), neutral dividers,
soft white text and a restrained green accent (`#91c6b5`). Page titles are 29–32px,
section headings 14px, table text 12–13px and secondary metadata 10–11px. Financial
figures use monospaced/tabular numerals. No external font, image service or dependency was added.

- **Shell:** 196px sidebar, compact navigation and 55px top bar. Connectivity and the demo
  subject are available without a large banner. Development-only impersonation stays explicit.
- **Overview:** open recent-loan and product tables, a live system line and a narrow workflow
  column. Browser history is labelled; no portfolio statistics are invented.
- **Origination:** numbered borrower → terms → schedule sequence, continuous form sections,
  inline UUID lookup and a contextual borrower/product summary. The actual generated schedule
  remains on the resulting account page; no speculative financial preview is calculated.
- **Loan account:** restrained account header, three aligned ledger-derived receivables,
  record tabs and a dense contractual schedule. Future contractual interest remains distinct
  from recognized receivables, and a payoff-quote caveat remains visible.
- **Repayment lab:** side-by-side instruction/results workstation on desktop, exact request
  retry, attempt-history selector and before/after receivable comparison. Each observed result
  names its actual actor and loan; raw responses and frozen request evidence are expandable.
- **Ledger:** a continuous journal register with posting/business dates, debit/credit columns,
  balance checks and expandable entry tables. Available schedule, recognized-lot, repayment
  and reversal links are retained. Register totals are explicitly diagnostic entry sums.
- **Audit:** compact event table, supported pagination and a keyboard-accessible metadata
  drawer. No nonfunctional search/filter control. Short UUIDs include a suffix so seeded
  actor IDs with the same prefix remain distinguishable.
- **Walkthrough:** vertical stepper, one action at the active step, inline results and a sticky
  transaction summary on desktop. Evidence opens on demand instead of repeating large cards
  and JSON payloads. Mobile uses a compact summary above the timeline.

## Actual production-build screenshots

These are real Chrome captures at **1440px**, **1024px** and **390px**, after the optimized
production build. Each row links to the same page at all three target widths.

| Page               | Desktop · 1440                 | Laptop · 1024                  | Mobile · 390                  |
| ------------------ | ------------------------------ | ------------------------------ | ----------------------------- |
| Overview           | [View](1440/overview.png)      | [View](1024/overview.png)      | [View](390/overview.png)      |
| Borrowers & loans  | [View](1440/workspace.png)     | [View](1024/workspace.png)     | [View](390/workspace.png)     |
| Loan account       | [View](1440/loan.png)          | [View](1024/loan.png)          | [View](390/loan.png)          |
| Repayment lab      | [View](1440/repayment-lab.png) | [View](1024/repayment-lab.png) | [View](390/repayment-lab.png) |
| Ledger inspector   | [View](1440/ledger.png)        | [View](1024/ledger.png)        | [View](390/ledger.png)        |
| Audit trail        | [View](1440/audit.png)         | [View](1024/audit.png)         | [View](390/audit.png)         |
| Guided walkthrough | [View](1440/walkthrough.png)   | [View](1024/walkthrough.png)   | [View](390/walkthrough.png)   |

Additional capture: [audit event detail drawer](audit-event-details.png).

The tests create invented records through the real API. Screenshots show actual UUIDs and
amounts at capture time. The shared review loan receives additional actual repayments during
responsive passes, so later viewport captures can legitimately show smaller receivables.
No record was reset or removed to prepare a screenshot.

## Executed validation

| Command / check                                                        | Observed result                    |
| ---------------------------------------------------------------------- | ---------------------------------- |
| `npm run lint`                                                         | Passed                             |
| `npm run typecheck`                                                    | Passed                             |
| `npm run format:check`                                                 | Passed                             |
| `npm test`                                                             | 30 passed; zero failed/skipped     |
| `npm run build`                                                        | Passed; optimized production build |
| `CHROME_EXECUTABLE='…/Google Chrome' npm run test:e2e` on port 3000    | 8 passed; zero failed/skipped      |
| `STUDIO_URL=http://127.0.0.1:3002 STUDIO_OFFLINE=1 … npm run test:e2e` | 1 passed; zero failed/skipped      |

The **39 passing tests** comprise 30 existing unit/component tests and nine browser tests.
The eight normal browser cases include all existing financial workflows, all seven pages at
three widths, journal expansion and the audit drawer. They ran against the actual running
FastAPI and native PostgreSQL 16.15 database, using Chrome 157.0.8103.52 on macOS arm64.
Node 26.13.1, Next 16.4.6, TypeScript 5.9.3 and the existing lockfile were used.

Verified workflows: borrower creation and exact lookup, loan creation/schedule, manager
single disbursement, partial repayment, original receipt/journal reuse, changed-payload 409,
auditor mutation 403, overpayment rejection, account records, ledger rendering and audit access.
The response-loss test allows the actual backend to commit, drops delivery to the browser,
then retries the frozen request after the amount field is edited: exactly one original
receipt remains. The full guided flow verifies the same receipt and journal IDs and counts.
Journal/audit UI interaction tests assert that backend balances and journal records are unchanged.

All 21 responsive page checks passed with no document horizontal overflow and no browser
runtime errors. Dense tables use local scroll regions. The tests caught and fixed a mobile
caption-containment issue; updated assertions also follow the accessible Expand/Collapse
button names correctly. All final production tests passed.

For offline validation, a separate temporary Next instance targeted an unused loopback port.
Its proxy genuinely failed to connect and returned 503; the existing FastAPI service stayed
running. The temporary preview/offline servers were stopped after validation. Docker was
not used. No full backend pytest rerun, physical-device validation or cross-browser certification
is claimed for this UI refactor.

## Preservation and limitations

The API client, monetary utilities, proxy, session semantics and generated contracts remain
unchanged. Backend source, schema, migrations, accounting policies, original submission ZIP
and technical write-up remain untouched. All edits are confined to `frontend/`; no commit,
push, deployment, database reset or destructive operation was performed.

The original backend limits remain: demo-only authentication; no portfolio listing/aggregates,
no audit search endpoint, and no accrual-record API. Querying balances does not recognize
interest or execute jobs. There is no new reversal/job UI. Before/after reads are not atomic
cross-endpoint snapshots. All financial acceptance decisions remain with the backend.

No functional regression was observed in the executed suites. Safari/Firefox, assistive-device
certification and physical-device behavior remain unverified. Keyboard dialog dismissal,
mobile navigation and semantic journal expansion were exercised in Chrome.

See [changed-files.txt](changed-files.txt) for the exact changed/new file list relative to
the beginning of this redesign. Next development mode also generated its standard local
`frontend/AGENTS.md` guidance file; it is not a product feature.
