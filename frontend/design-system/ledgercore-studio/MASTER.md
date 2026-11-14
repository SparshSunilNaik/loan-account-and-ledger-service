# LedgerCore Studio: Precision Finance

Current visual system. The [Workbench interaction layer](../../docs/workbench/plan.md) preserves these tokens while using a viewport-height shell, internally scrolling registers and adjacent inspectors. The approved loan-first IA is unchanged. The earlier [UX audit, journeys and wireframes](../../docs/product-ux/design-plan.md) remain the behavioral reference; the [current identity rationale](../../docs/precision-finance/design.md) supersedes that phase's light-only styling.

## Semantic palette

| Token                   | Light     | Dark      |
| ----------------------- | --------- | --------- |
| Background              | `#F6F7F5` | `#10171C` |
| Working surface         | `#FFFFFF` | `#19242B` |
| Raised surface / drawer | `#FFFFFF` | `#22313A` |
| Subtle surface          | `#EDF2F0` | `#1D2D34` |
| Primary ink             | `#19343B` | `#EDF5F3` |
| Secondary ink           | `#52696F` | `#A1B4B9` |
| Divider                 | `#DCE4E1` | `#304149` |
| Field boundary          | `#80948E` | `#627C86` |
| Action                  | `#126A70` | `#75D6C4` |
| Action label            | `#FFFFFF` | `#102B2D` |
| Financial position      | `#FFFFFF` | `#15292F` |
| Position amount         | `#193F48` | `#BCF1E8` |

All component colors resolve through semantic variables in `src/app/globals.css`, including hover, warning, error, success, overlay and selected states. Standalone SVG browser branding uses the light brand/action colors. No inversion filter, gradient, glow or external runtime asset.

## Type and alignment

Locally served IBM Plex Sans: regular 400 for reading, 500 for controls, 550–600 for headings. Typical scale: 12 metadata, 14 table/control, 16 body, 20 section, 30 page. SF Mono/Menlo-compatible system numerals are reserved for money and machine references. Principal is the visual anchor (responsive 28–40px), secondary balances 22–27px. Right-align amount columns; keep explicit Debit/Credit headers and text/icon status. Never animate or calculate authoritative balances.

## Signature and controls

The paired-ledger SVG mark is two equal posting rails with a connecting stroke. The pair repeats only in navigation selection and the financial position. Keep the shell quiet: four primary destinations, compact identity and separate appearance select. Fields use visible labels and clear boundaries; chosen product uses radio + border/edge. Table rows use tonal hover/focus-within; no fake sorting. Technical identifiers wrap or disclose fully and provide copy confirmation.

## Motion and themes

Control feedback 140ms; sheet entrance 180ms, exit 140ms. No page-load or value animation. Reduced motion removes animation/transition. Light / Dark / System is persisted independently of demo identity in localStorage. Synchronous head bootstrap precedes body paint; live OS changes and cross-tab preferences are observed. See [theme architecture and measured evidence](../../docs/precision-finance/README.md).

## Behavior guardrails

Loans, New loan, Activity, Testing share the same working account; no repeated ID entry. Repayment stays in the loan sheet, followed by actual journal entries. Financial data, original schedules, RBAC, exact paise conversion and frozen retry identities remain backend/client-contract governed. Browser history is never presented as a full portfolio. Never edit backend accounting, migration, ZIP or technical write-up as part of this visual system.
