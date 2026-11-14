# LedgerCore Workbench: interaction plan

The Precision Finance palette, themes, typography, SVG brand and four destinations remain. This phase changes composition and interaction, not financial contracts.

## Observed baseline (before application edits)

Chrome executed three real API-backed journeys at 1440×900. [Raw measurements](before/measurements.json) and four screenshots are saved. A: 7 pointer clicks, 2 URL changes, 8 field entries, zero repeated fields/loan IDs, document overflow up to 801px. B: 6 clicks, 4 URL changes, document overflow 1145px. C: 3 clicks, one trip to Testing, document overflow 769px. The previous UX already removed manual UUID repetition; this phase cannot claim that as a new improvement.

Times are a single automated local run, not human typing/reading times or statistical performance claims. The measurement script counts actual click events; programmatic fill/selectOption operations are counted separately or excluded explicitly. Final comparison uses the same definitions and stores raw timings.

## Friction audit and decisions

- Repayment opens a modal overlay, hiding context and requiring a separate action/route to inspect the same posting. Desktop will use a non-modal adjacent inspector, with the actual journal and current backend receivables visible after posting.
- Receipt allocations are nested raw JSON, disconnected from their journal. Selecting a receipt will reveal allocation rows, linked journal and current receivables in one inspector without routing.
- Selecting a journal expands the main table vertically. In the account workbench, the same action will select the adjacent inspector instead; standalone Activity keeps its existing detailed register.
- Retry testing requires leaving the account. Add explicit advanced delivery checks to its repayment inspector, reusing the frozen request and existing observation service. No automatic mutation or new-key retry.
- New loan creates a schedule then requires Open account to disburse. Open the created loan’s actual account automatically within the same shell; its canonical URL makes refresh reliable. Disbursement still requires explicit manager action/date.
- Origination component unmounts on navigation and the repayment component is keyed anew on each open. Keep origination mounted while hidden and persist per-loan editable repayment drafts in session storage; retain prepared request identity safely for unknown-outcome recovery.
- Long document pages conceal primary controls. Desktop shell is viewport-height; summary/actions stay fixed, data tables and inspector have independent named scroll regions. Mobile remains one readable content area, with an accessible modal bottom sheet.

## Composition

```
Compact header: current loan / Command K / demo identity / appearance
Sidebar          Borrower, product, status         Record repayment
                 Principal | Interest | Penalty    Refresh / references
                 Schedule Repayments Ledger History
                 +---------------------+----------------------+
                 | Scrollable register | Contextual inspector |
                 |                     | action / receipt /   |
                 | selected record     | entries / API result |
                 +---------------------+----------------------+
```

Use native controls and existing Radix dialogs; no resizer dependency. At laptop widths the inspector is compact; on mobile it becomes a bottom sheet. Keep substantive record data open rather than stacking accordions; raw HTTP/request evidence stays advanced.

## Commands and safeguards

Cmd/Ctrl+K: real labelled command palette, arrow navigation, Enter, Escape, current-session loan references only. Commands open known loan, New loan, Schedule, Repayments, Ledger, authorized History and Testing. Role/status hide inappropriate mutation actions. Alt+1/2/3/4 selects account views, Alt+P opens repayment when permitted, Alt+R refreshes actual data; shortcuts never submit mutations. Drafts are keyed by loan; record IDs and request identities are never confused across loans. Existing backend still authorizes all requests.

Both installed design skills were read. UI UX Pro Max keyboard guidance emphasizes focus, native controls and escape routes; its state-preservation Next search returned generic server-action advice that is rejected because this task must preserve the existing HTTP financial contracts. Anthropic guidance is applied as restraint: preserve the approved identity, remove redundant structures and keep visual relationships tied to actual receipt/allocation/journal data.
