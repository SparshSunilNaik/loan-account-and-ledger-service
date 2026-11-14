# Precision Finance: visual identity and dual-theme evidence

> Historical design-stage report: the initial workbench theme tests refreshed some screenshots in this gallery. For the Precision Finance baseline captured before workbench edits, use [Workbench before evidence](../workbench/before/); for current validation, use the [Workbench report](../workbench/README.md).

The approved loan-first information architecture is preserved: **Loans, New loan, Activity, Testing**, and one shared working account. No backend endpoint, financial policy, schedule, migration, verified ZIP or technical write-up changed. Nothing committed or pushed.

## Identity and rationale

The new paired-ledger mark uses two equal posting rails joined by a transfer stroke. A quiet echo marks the financial position; the same active indicator identifies navigation. It refers to double-entry balance without introducing a chart or a fabricated KPI. The logo is repo-native SVG, not an AI image or external brand asset.

IBM Plex Sans remains locally served for interface text. Money and machine references use platform SF Mono/Menlo-compatible fonts and tabular figures: columns align and financial state is the anchor. Tables keep explicit Debit/Credit labels, current balances remain backend-derived, and original contractual interest remains clearly distinct from recognized receivables.

Light is a porcelain/ink workstation with white working surfaces and a deep teal action. Dark is a graphite instrument panel with raised blue-gray drawers, a dedicated dark financial-position surface and mint actions with **dark text**. Dark row detail, status, warning, error, scrim, field and control colors are mapped separately; there is no inversion filter. Semantic tokens own every component color. Existing accessible primitives and Lucide icons are retained; no dependency was added.

[Design criteria, palettes and skill review](design.md) records both actual installed skills and the decisions accepted/rejected. The pinned Anthropic instructions guide the subject-specific identity and critique; UI UX Pro Max contributes systematic contrast, type, interaction and theme review. Its Next hydration searches returned no verified match, so the installed Next.js before-hydration guide was read and followed.

## Theme architecture

- **Light / Dark / System** is a native, labelled, keyboard-operable select in the upper-right header, separate from demo identity.
- Only `ledgercore-studio-theme` is stored in localStorage. No financial payloads or credentials move there. New visitors default to System; explicit choices persist, including System.
- A static synchronous head script validates storage and resolves the effective theme **before the body appears**. The script serializes the same pure resolvers used after hydration. Root hydration suppression applies only to the root attributes this script changes.
- CSS has an OS-theme fallback. The client subscribes to `matchMedia` while System is active, follows cross-tab storage changes and removes listeners on unmount. Explicit Light/Dark overrides OS changes.
- If browser storage is disabled, appearance still works in the current tab and defaults to OS on the next load. Invalid values fall back to System.
- No global page entrance or animated money counters. Controls use 140ms feedback; Radix sheets use 180ms entrance / 140ms exit with a theme-specific scrim. Reduced motion disables transitions and drawer animation. Native theme selection itself is the confirmation.

## Screenshot review and refinements

Chrome opened every current major layout before edits. The [before captures](before/) show the previous approved light UX. The screenshots below are from real servicing operations against FastAPI/PostgreSQL, not mocked financial data. Each theme/viewport case creates an invented borrower and loan through the UI, disburses with manager authorization, records a partial repayment and inspects the resulting accounting.

Critique led to concrete adjustments: retained a tonal sidebar in light rather than adding a competing dark block; reduced the shell's visual weight; separated dark working/elevated/position surfaces; kept the teal/mint emphasis concentrated on actions and actual money; reflowed the mobile header so loan context, identity and theme remain accessible; used equal posting rails rather than another generic layered logo. Early theme-switch captures caught color transitions in flight, so evidence captures finish those transitions rather than presenting a misleading intermediate gray. No animations are used to change monetary values.

| Real workflow state              | Light desktop                                       | Dark desktop                                      | Light mobile                                      | Dark mobile                                     |
| -------------------------------- | --------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------- |
| Loans — known accounts           | [light 1440](after/light/1440/loans.png)            | [dark 1440](after/dark/1440/loans.png)            | [light 390](after/light/390/loans.png)            | [dark 390](after/dark/390/loans.png)            |
| New loan — entered terms         | [light 1440](after/light/1440/new-loan-terms.png)   | [dark 1440](after/dark/1440/new-loan-terms.png)   | [light 390](after/light/390/new-loan-terms.png)   | [dark 390](after/dark/390/new-loan-terms.png)   |
| New loan — actual saved schedule | [light 1440](after/light/1440/saved-schedule.png)   | [dark 1440](after/dark/1440/saved-schedule.png)   | [light 390](after/light/390/saved-schedule.png)   | [dark 390](after/dark/390/saved-schedule.png)   |
| Disbursed account                | [light 1440](after/light/1440/loan-detail.png)      | [dark 1440](after/dark/1440/loan-detail.png)      | [light 390](after/light/390/loan-detail.png)      | [dark 390](after/dark/390/loan-detail.png)      |
| Received payment and allocations | [light 1440](after/light/1440/repayment-result.png) | [dark 1440](after/dark/1440/repayment-result.png) | [light 390](after/light/390/repayment-result.png) | [dark 390](after/dark/390/repayment-result.png) |
| Selected payment journal         | [light 1440](after/light/1440/ledger.png)           | [dark 1440](after/dark/1440/ledger.png)           | [light 390](after/light/390/ledger.png)           | [dark 390](after/dark/390/ledger.png)           |
| Repayment history                | [light 1440](after/light/1440/repayments.png)       | [dark 1440](after/dark/1440/repayments.png)       | [light 390](after/light/390/repayments.png)       | [dark 390](after/dark/390/repayments.png)       |
| Activity register                | [light 1440](after/light/1440/activity.png)         | [dark 1440](after/dark/1440/activity.png)         | [light 390](after/light/390/activity.png)         | [dark 390](after/dark/390/activity.png)         |
| Testing — actual HTTP 409        | [light 1440](after/light/1440/testing-conflict.png) | [dark 1440](after/dark/1440/testing-conflict.png) | [light 390](after/light/390/testing-conflict.png) | [dark 390](after/dark/390/testing-conflict.png) |
| Testing — actual HTTP 403        | [light 1440](after/light/1440/testing-denied.png)   | [dark 1440](after/dark/1440/testing-denied.png)   | [light 390](after/light/390/testing-denied.png)   | [dark 390](after/dark/390/testing-denied.png)   |
| Actual account audit context     | [light 1440](after/light/1440/history.png)          | [dark 1440](after/dark/1440/history.png)          | [light 390](after/light/390/history.png)          | [dark 390](after/dark/390/history.png)          |

Laptop captures cover the same full workflow at **1024px** in [light](after/light/1024/) and [dark](after/dark/1024/). Empty states: [light](after/light/1440/empty-loans.png), [dark](after/dark/1440/empty-loans.png). Actual refresh-in-progress: [light](after/light/1440/refreshing.png), [dark](after/dark/1440/refreshing.png). The loading test holds an actual GET briefly, then continues to the real backend; no response data is fabricated.

Offline evidence: [light](after/backend-offline-light.png), [dark](after/backend-offline-dark.png). The separate temporary Next instance targets an unused local port and returns a real proxy 503; the user's FastAPI stays running. This temporary server is stopped after verification.

## Validation

[validation.json](validation.json) records final observed counts and commands. The original unit and financial browser suites remain, supplemented by explicit appearance tests:

- UI borrower → product/loan → actual schedule → manager disbursement → officer partial repayment → selected journal in **both themes at 1440/1024/390px**.
- Exact retry reuses the original receipt and journal; principal remains 9,100 paise after a 1,000-paise payment allocates 100 interest / 900 principal on the independently specified 10,000-paise case. Changed payload returns 409; auditor mutation returns 403. Existing atomic-overpayment, source-alias, audit-attribution and lost-response-after-commit checks remain.
- Appearance survives navigation and refresh, follows live OS changes only under System, syncs across tabs, supports keyboard type-ahead and retains visible focus.
- Cold-load tests block Next hydration scripts and inspect theme at first body insertion and computed body background. Explicit Dark with light OS, explicit Light with dark OS, System and invalid preferences all resolve correctly before hydration.
- Storage-denied browser paths remain usable; reduced-motion settings disable drawer animation. Clipboard verification reads back the copied actual loan ID and checks visible confirmation.
- No document overflow across all five major layouts at the three widths; wide journal/schedule/ID data remains inside local horizontal table scrollers.
- [32 independently calculated contrast pairs](contrast.json) cover text, action/hover, status/warning/error, raised surfaces, table headers, control boundaries and focus in both themes. Text pairs meet 4.5:1; selected control/focus pairs meet 3:1. This is a targeted contrast check, not full accessibility certification.

## Remaining limits

The existing API limitations are unchanged: recent loans are at most 12 browser-session references, not a server portfolio; loan History scans at most 5,000 audit records; preview is the actual saved schedule after creation. Before/after financial reads remain separate observations, not an atomic snapshot. Demo identities are development-only impersonation, not production authentication. The initial head script would require a nonce/hash if a strict production CSP were introduced. Physical devices, Safari/Firefox and full screen-reader certification were not tested; native font and select appearance may vary by OS. No paid API, runtime external font, new dependency, backend feature, scheduler or dataset replay was introduced.

[Exact files changed](changed-files.txt) is relative to the frontend snapshot at the start of this visual phase. Old product-UX evidence is preserved; legacy regression captures are redirected into this phase's evidence directory. [Startup commands](../../README.md) are unchanged. Main servers stay in labelled Terminal windows and Chrome is opened on an actual populated loan for review.
