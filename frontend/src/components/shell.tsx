"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  WalletCards,
  Plus,
  Activity,
  FlaskConical,
  ChevronDown,
} from "lucide-react";
import { NewLoan } from "./new-loan";
import { CommandPalette } from "./command-palette";
import { ThemeControl } from "./theme-control";
import { api } from "@/lib/api";
import { session, useStudio, UUID_PATTERN } from "@/lib/session";
import { actors, type Actor } from "@/lib/types";
const nav = [
  { href: "/loans", label: "Loans", icon: WalletCards },
  { href: "/new-loan", label: "New loan", icon: Plus },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/testing", label: "Testing", icon: FlaskConical },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const { actor, selectedLoan, recent } = useStudio();
  const path = usePathname();
  const router = useRouter();
  const health = useQuery({
    queryKey: ["health", actor],
    queryFn: () => api.health(actor),
    refetchInterval: 15000,
  });
  const loan = useQuery({
    queryKey: ["loan", selectedLoan, actor],
    queryFn: () => api.loan(selectedLoan, actor),
    enabled: UUID_PATTERN.test(selectedLoan),
  });
  const borrower = useQuery({
    queryKey: ["borrower", loan.data?.borrower_id, actor],
    queryFn: () => api.borrower(loan.data!.borrower_id, actor),
    enabled: !!loan.data?.borrower_id,
  });
  const connected = !health.isError && health.data?.status === "ok";
  function select(value: string) {
    if (!value) return;
    session.select(value);
    if (path.startsWith("/loans/") || path === "/loans" || path === "/new-loan")
      router.push(`/loans/${value}`);
    else {
      const url = new URL(window.location.href);
      if (url.searchParams.has("loanId")) {
        url.searchParams.set("loanId", value);
        router.replace(url.pathname + url.search);
      }
    }
  }
  return (
    <div
      className={`app-shell ${path.startsWith("/loans/") || path === "/new-loan" ? "workbench-shell" : ""}`}
    >
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link href="/loans" className="brand">
          <svg
            className="ledger-mark"
            viewBox="0 0 32 32"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M5 7h8v18H5M27 7h-8v18h8"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="square"
            />
            <path
              d="M5 13h8m6 6h8M13 16h6"
              stroke="currentColor"
              strokeWidth="2"
            />
          </svg>
          <span>
            LedgerCore<strong>Studio</strong>
          </span>
        </Link>
        <nav aria-label="Main navigation">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`nav-link ${path === n.href || path.startsWith(n.href + "/") || (n.href === "/new-loan" && path === "/workspace") ? "active" : ""}`}
              aria-current={
                path === n.href || path.startsWith(n.href + "/")
                  ? "page"
                  : undefined
              }
            >
              <n.icon size={19} aria-hidden="true" />
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="local-label">
            <i />
            Local demo
          </span>
          <p>
            Development-only identities.
            <br />
            Local testing environment.
          </p>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
            API documentation
          </a>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="account-switcher">
            <label htmlFor="working-loan">Working account</label>
            <div>
              <select
                id="working-loan"
                aria-label="Working account"
                value={selectedLoan}
                onChange={(e) => select(e.target.value)}
              >
                <option value="">Select a known loan</option>
                {recent.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id === selectedLoan && borrower.data
                      ? `${borrower.data.full_name} · ${r.reference}`
                      : r.reference}
                  </option>
                ))}
                {selectedLoan && !recent.some((r) => r.id === selectedLoan) && (
                  <option value={selectedLoan}>
                    {loan.data?.external_reference ?? "Loading account…"}
                  </option>
                )}
              </select>
              <ChevronDown size={14} aria-hidden="true" />
            </div>
          </div>
          <div className="topbar-actions">
            <CommandPalette />
            <span
              className={`connection ${!connected ? "connection-offline" : ""}`}
              aria-label={
                connected ? "Backend connected" : "Backend unavailable"
              }
            >
              <i />
              {health.isPending
                ? "Connecting"
                : connected
                  ? "Backend connected"
                  : "Backend unavailable"}
            </span>
            <label className="identity-select">
              <span>Demo identity</span>
              <select
                aria-label="Active demo identity"
                value={actor}
                title="Development-only impersonation. Roles are enforced by the backend."
                onChange={(e) => session.actor(e.target.value as Actor)}
              >
                {actors.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
            <ThemeControl />
          </div>
        </header>
        <main id="main-content" className="page-content">
          <div hidden={path !== "/new-loan"} className="origination-host">
            <NewLoan active={path === "/new-loan"} />
          </div>
          {children}
        </main>
        <footer className="page-footer">
          Local testing only <span>INR amounts · UTC dates</span>
        </footer>
      </div>
    </div>
  );
}
