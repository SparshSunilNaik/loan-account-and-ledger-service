# Precision Finance

Visual refinement of the approved loan-first IA. Loans, New loan, Activity, Testing and all account tabs remain unchanged.

## Direction, reviewed before implementation

Treat the account as an instrument panel: borrower context first, ledger-derived amounts as anchors, then a precise record table. The signature is **paired posting rails**: equal-length strokes linked through the brand mark, echoed once at the financial position. This refers to balanced double-entry movements, not a decorative chart or invented financial measure.

- Light: porcelain `#F6F7F5`, white working surfaces, ink `#19343B`, muted ink `#52696F`, teal `#126A70`, neutral rules `#DCE4E1`.
- Dark: graphite `#10171C`, working surface `#19242B`, elevated `#22313A`, off-white `#EDF5F3`, muted `#A1B4B9`, mint `#75D6C4`. Dark buttons use ink text; dark entry details and financial position get their own tonal hierarchy rather than inverted white fills.
- Type: existing locally served IBM Plex Sans for conversation and interface; platform SF Mono/Menlo for money and machine references. Tabular numerals, aligned decimals, no animated financial counters. The only large text is the actual principal position.
- Form hierarchy: crisp field boundaries, selected product indicated by border + native radio, generous touch heights. No new input steps.
- Tables: consistent header baseline, quieter row rules, hover/focus-within feedback, explicit Debit/Credit labels; identifiers can wrap/disclose. No unsupported sorting/filtering.
- Motion: 140ms controls/exits, 180ms sheet entrance. Only user-triggered transitions; no page entrances, gradients or glow. Reduced motion disables them.

## Plan critique

A wholesale dark sidebar in light mode would create a second theme inside the first and draw attention away from financial state. Keep the light shell tonal. Bright mint on every dark element would read as a trading terminal; reserve it for actions, selection and financial emphasis. Keep system-native selects instead of installing a dropdown library. Preserve four destinations, current responsive navigation, exact API data and frozen retry semantics.

## Theme architecture

Three choices (Light, Dark, System), a separate compact header control. A static, synchronous head script resolves a validated localStorage preference before body paint. CSS has OS-based fallback if JavaScript is unavailable. A small external store uses the same theme resolver, observes live matchMedia and cross-tab storage changes, and treats unavailable storage as a session-only preference. No theme cookie, server request or dependency. No financial state is stored in localStorage. Root hydration suppression is scoped to attributes changed by this script.

## Skills actually consulted

Read both project-local SKILL.md files: UI UX Pro Max and Anthropic frontend-design pinned at b5b01ac4f889fec0c4c6bb89f27ca7c8574473f6. UI UX Pro Max design-system searches: `financial workstation precision`, narrower `banking operations`; accepted readability, IBM Plex and contrast guidance, rejected marketing sections, gold/neon and generic landing layouts. `dark mode --domain style` returned OLED/neon guidance; only its independent dark-contrast principle fits. `dark mode contrast --domain ux` returned text readability and 4.5:1 checks. Next.js `theme flash hydration` and narrower `hydration` returned no verified match; the installed Next.js guide `preventing-flash-before-hydration.md` supplies the implementation guidance instead. Anthropic principles shape the subject-specific motif, typography, restrained copy and screenshot critique.

Before editing, Chrome opened all five existing major layouts, with an actual saved/disbursed/repaid account. Before screenshots are in `before/`. No new design skill installation is claimed in this phase.
