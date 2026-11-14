# LedgerCore Studio

A local loan-servicing workspace, outside the verified backend submission. Four destinations:
**Loans**, **New loan**, **Activity**, **Testing**. The selected account follows you through
all views. Normal repayment happens inside the account, with the actual posting shown immediately.

[Workbench friction analysis, commands and evidence](docs/workbench/README.md) ·
[Precision Finance themes and evidence](docs/precision-finance/README.md) ·
[Approved UX plan and wireframes](docs/product-ux/design-plan.md) ·
[Workflow evidence and screenshots](docs/product-ux/README.md) ·
[Proposed discovery API — not implemented](docs/product-ux/proposed-loan-discovery-api.md)

## Start locally

Requirements: PostgreSQL 16+, Python/uv as in the backend README, Node 22.12+ on a supported
even-numbered release (22, 24 or 26), and npm. Use invented data only. These actions append
real local records; there is no database reset button or cleanup operation.

Terminal 1, repository root, with PostgreSQL already running:

```sh
uv sync --frozen --python 3.12
# Create ONCE if absent; never reset an existing database:
createdb ledgercore_studio
export DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/ledgercore_studio
export DEMO_AUTH_ENABLED=true
uv run alembic upgrade head
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000
```

Adapt the database URI to your local authentication/port. Skip `createdb` when the database
already exists. Migrations seed the three products, accounts and demo users.

Terminal 2, repository root:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open **http://127.0.0.1:3000**. For the optimized build:

```sh
cd frontend
npm run build
npm run start
```

On this Mac, if your shell selects the Homebrew Node with a missing shared library, use
the existing working installation before npm commands:

```sh
export PATH="$HOME/.local/share/vite-plus/bin:$PATH"
```

`BACKEND_URL` is server-only and defaults to `http://127.0.0.1:8000`. Change `.env.local`
and restart Next for another local port. The proxy accepts only credential-free loopback
HTTP origins, a small route allowlist and the three demo subjects. It rejects redirects
and cross-origin mutations; upstream timeout is 15 seconds, browser timeout 22 seconds.
No automatic mutation retries. No cloud service, external runtime font, AI API or API key.

Both services must stay on loopback. This is **development-only impersonation, not production
authentication**. The database decides each subject's permissions; no header selects a role.

| Identity       | Permission                                          |
| -------------- | --------------------------------------------------- |
| `demo-officer` | Originate and repay; read financial records         |
| `demo-manager` | Officer actions plus disbursement and audit history |
| `demo-auditor` | Read-only financial and audit records               |

## Use the workbench

1. **Loans:** filter at most 12 browser-known accounts by their fetched borrower name or reference. This is session history, not a server-backed portfolio. **Open a loan link** imports an exact account URL/ID once; all subsequent actions retain its ID.
2. **New loan:** create an invented borrower or load an existing borrower, select the actual product, enter rupees/tenure/due date, then create. The app opens the new account's canonical URL automatically and reads its real saved schedule. No speculative EMI preview, automatic disbursement or extra Open account step.
3. **Disburse:** use demo-manager, review the explicit UTC date, then press Disburse loan. The principal posts once through the existing backend. A new origination can be started with New application on returning to the completed origination draft.
4. **Record repayment:** the form opens beside the register on desktop, as a bottom sheet on mobile. Enter amount, UTC economic time and processing date; submission is always explicit. Successful results show actual HTTP status, allocations, journal and observed receivables. The persistent summary refreshes from the backend.
5. **Inspect:** Schedule, Repayments, Ledger and History share the current account. Select a receipt or journal to show its allocations, linked record, debit/credit entries and current receivables in the inspector without routing. History follows backend audit-role restrictions.
6. **Delivery checks:** opens advanced testing inside the repayment inspector. Retry always preserves the original actor/body/key. Modified-payload and source-alias checks require a verified original receipt/journal; use exact retry to verify an unknown delivery first. The separate Testing destination retains the full laboratory (including overpayment) and guided demo.
7. **Drafts:** editable repayment fields and prepared request identity survive panel switches and refresh, keyed by loan. Unsent origination fields survive client navigation and step changes. They are not persisted across a full browser refresh before creation; uncertain origination outcomes must be inspected before another attempt.

On desktop, the header and loan position remain visible while records and inspector scroll independently. Mobile has one main column, a visible repayment action and a modal bottom sheet. Use named scroll regions with the keyboard; no drag-only controls or resize dependency.

| Shortcut                      | Action                                              |
| ----------------------------- | --------------------------------------------------- |
| ⌘K / Ctrl+K                   | Search commands and locally known loan references   |
| ↑ / ↓, Enter, Escape          | Select/open/dismiss palette command                 |
| Alt+1 / Alt+2 / Alt+3 / Alt+4 | Schedule / Repayments / Ledger / History            |
| Alt+P                         | Open repayment when the current role/status permits |
| Alt+R                         | Refresh actual backend reads                        |

Alt shortcuts are ignored while editing inputs. None submits a payment or disbursement. On Mac, physical key codes accommodate Option-key character variations. Theme selection remains independent of actor and account. Legacy URLs remain compatibility entry points.

## Financial correctness and stored context

- Rupee input converts through Decimal-string/BigInt handling to bounded integer paise.
  No floating-point EMI or authoritative balance calculation runs in the frontend.
- Receivables always come from `/balance`. Schedule sums and journal totals are diagnostic
  sums of actual returned records. Future contractual interest is separate from recognized
  receivables; current receivables are **not necessarily a future payoff quote**.
- Reading a page never recognizes interest or runs a job. Eligible interest recognition
  occurs atomically in the existing repayment workflow. No schedule row is edited.
- Retry effects are verified from authoritative receipt/journal IDs in before/after reads,
  never inferred from HTTP 201 alone. Reads across endpoints are not an atomic snapshot.
- Session storage holds visited references, selected loan/actor, and latest **prepared request**
  per loan. Requests are saved before sending so uncertain outcomes can be retried exactly.
  No balances, passwords or production credentials are persisted. A prepared request does
  not prove that a payment was accepted; inspect its actual response and backend records.
- Origination has no repayment-style idempotency API. If creating a borrower/loan times out,
  keep the displayed reference and inspect audit/server records before another creation.
- Posted journals remain immutable; this UI exposes no reversal/job/reset action.

## Verify

With actual FastAPI/PostgreSQL and Studio running:

```sh
cd frontend
npm run lint
npm run typecheck
npm run format:check
npm test
npm run build
STUDIO_CAPTURE_ROOT=docs/workbench/regression CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm run test:e2e
# Or install Playwright Chromium once and omit CHROME_EXECUTABLE:
# npx playwright install chromium
```

`STUDIO_CAPTURE_ROOT=docs/workbench/regression` keeps historical design-stage captures separate
from current regression evidence. The workbench suite writes to `docs/workbench/screens/`.
`UX_PHASE=after node scripts/measure-workbench.mjs` records real 1440×900 click/route/scroll
measurements against the running production app; it creates a fresh invented account. Its
`before` mode targets the prior approved interface and is retained for provenance, not for
running against the new workbench. Timings are automated local samples, not human benchmarks.

`STUDIO_URL` overrides the browser-test URL (default port 3000). The browser suites create
invented records through the actual HTTP API. They complete journeys A/B/C at 1440, 1024
and 390px in light and dark, check keyboard behavior and overflow, and capture populated screenshots.
They also verify saved/System themes, live OS/cross-tab changes, blocked storage and before-body
theme resolution with hydration JavaScript blocked. `STUDIO_CAPTURE_ROOT` redirects legacy
regression captures; the dual-theme suite uses its own `themes/` subdirectory when this override is set. They
retain financial checks for partial repayment, exact retry, source deduplication, 409/403/400,
atomic overpayment rejection, actor audit attribution and balanced journals. The timeout
case lets the real API commit, drops the response and verifies one receipt after reload.

`STUDIO_OFFLINE=1 npm run test:e2e` selects only the unavailable-backend test. Use a separate
Next instance with `BACKEND_URL` pointed to an unused loopback port, or stop only your own
FastAPI instance. Never disrupt another user's service to test an outage.

OpenAPI types can be regenerated with `npm run types:generate`; the verified OpenAPI export
is only read. Financial response routes with generic schemas are manually typed from the
existing serializers in `src/lib/types.ts`. Backend OpenAPI changes are outside this scope.

## Design skills and limitations

UI UX Pro Max 2.15.0 was installed project-locally through the official Codex CLI command.
The pinned Anthropic frontend-design skill was manually installed/read at revision
`b5b01ac4f889fec0c4c6bb89f27ca7c8574473f6`; this is not a claimed Claude plugin installation.
Skill searches, selected/rejected recommendations and rationale are documented in the plan.
IBM Plex Sans is served locally under its included OFL license in `public/fonts/`.

Light, Dark and System appearances are available in the header, independently of demo identity.
The preference is stored as `ledgercore-studio-theme` in localStorage; System follows live OS
changes. A synchronous head script resolves the theme before content paints, including refresh.
Storage-disabled browsers can switch theme for the current tab; that preference cannot survive
reload. Only appearance is stored in localStorage; financial request recovery stays in session
storage. Motion is restrained and respects reduced-motion settings.

No server-backed
loan list/search or audit filter exists, so those capabilities are not simulated. No accrual
record API, job execution or reversal UI. Demo readers are not tenant-scoped. Chrome/viewport
QA does not certify every browser, physical device or assistive technology.

Studio changes leave backend accounting rules, migrations and the technical write-up untouched. The backend submission ZIP is generated separately.
Frontend source and its recorded design evidence are maintained separately from the backend-only submission ZIP. Local authoring skills under `.agents/` are ignored; they are not runtime dependencies. The demo recording script and current validation are linked from the repository README.
