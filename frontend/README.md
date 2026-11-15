# LedgerCore Studio

LedgerCore Studio is an optional local interface for the LedgerCore API. It keeps a selected
loan in context while an operator reviews its schedule, posts a repayment, follows the linked
journal, and tests delivery failures. All balances and financial records come from FastAPI;
the browser does not calculate authoritative receivables.

## Run locally

Start PostgreSQL and the backend from the repository root first:

```sh
uv sync --frozen --python 3.12
createdb ledgercore_studio                 # run once; skip if it already exists
export DATABASE_URL=postgresql+psycopg://127.0.0.1:5432/ledgercore_studio
export DEMO_AUTH_ENABLED=true
uv run alembic upgrade head
uv run uvicorn ledgercore.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open <http://127.0.0.1:3000>. `BACKEND_URL` is server-only and defaults to
`http://127.0.0.1:8000`; restart Next.js after changing it. The proxy accepts only loopback
backend URLs and forwards only the supported demo identity and idempotency headers.

The three database-seeded identities are:

| Identity       | Access                                                         |
| -------------- | -------------------------------------------------------------- |
| `demo-officer` | Create borrowers and loans, post repayments, read loan records |
| `demo-manager` | Officer access plus disbursement, reversal and audit history   |
| `demo-auditor` | Read-only financial and audit access                           |

`X-Demo-User` is development-only impersonation. It is unsuitable for deployment and does
not provide tenant isolation.

## Workbench behavior

- **Loans** shows browser-known loan references. It is not a server-backed portfolio search.
- **New loan** creates an invented borrower and loan, then opens the saved schedule.
- The loan workspace keeps Schedule, Repayments, Ledger and History under one selected loan.
- Repayment results show the actual receipt, allocations, posted journal and refreshed API
  balance. Advanced delivery checks exercise exact retry, conflict, duplicate and RBAC paths.
- **Activity** displays available journals and audit events; **Testing** retains the guided
  demonstration and failure controls.
- Light, Dark and System themes are available. Theme preference is local; selected loan,
  actor and prepared repayment state are kept in session storage.

Financial input is converted from a decimal string to integer paise without JavaScript
floating-point arithmetic. Reads never recognize interest or run accrual jobs. Current
receivables are ledger-derived and are not necessarily a future payoff quote.

Keyboard shortcuts: `Cmd/Ctrl+K` opens commands, `Alt+1` through `Alt+4` select loan tabs,
`Alt+P` opens repayment when permitted, and `Alt+R` refreshes backend reads. No shortcut
submits a financial mutation.

## Validate

With FastAPI and PostgreSQL running:

```sh
cd frontend
npm ci
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
npm run test:e2e
```

Browser tests use `STUDIO_URL` (default `http://127.0.0.1:3000`) and create invented records
through the real API. Screenshots and traces are written under ignored `test-results/` and
`playwright-report/`. Set `CHROME_EXECUTABLE` to use an installed Chrome, or install Playwright
Chromium. To exercise the offline state, start a separate Next.js instance whose
`BACKEND_URL` points to an unused loopback port, then run:

```sh
STUDIO_OFFLINE=1 STUDIO_URL=http://127.0.0.1:3001 npm run test:e2e
```

OpenAPI types can be regenerated with `npm run types:generate`. IBM Plex Sans is served from
`public/fonts/` under the included SIL Open Font License.

## Limitations

The backend has no list/search endpoint, so Studio explicitly labels its recent-loan list as
browser history. A minimal read-only improvement is documented separately in the
[proposed loan-discovery API](docs/product-ux/proposed-loan-discovery-api.md). Studio has no
accrual-job, low-level journal, historical-balance or general
reversal UI. Audit access follows backend roles, but demo readers are not tenant-scoped.
Browser tests cover the supported desktop, laptop and mobile viewports; they do not certify
every browser or assistive technology.
