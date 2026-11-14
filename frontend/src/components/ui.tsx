"use client";
import Link from "next/link";
import { Check, Copy, LoaderCircle, TriangleAlert, Info } from "lucide-react";
import { useState } from "react";
import { ApiFailure, errorMessage, type Reply } from "@/lib/api";
import { inr } from "@/lib/money";
import type { Balance, ScheduleRow } from "@/lib/types";
export const cx = (...names: (string | false | undefined)[]) =>
  names.filter(Boolean).join(" ");
export function Button({
  children,
  className,
  variant = "primary",
  busy,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      {...props}
      aria-busy={busy || undefined}
      disabled={props.disabled || busy}
      className={cx("button", `button-${variant}`, className)}
    >
      {busy && (
        <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}
export function ButtonLink({
  href,
  children,
  quiet = false,
}: {
  href: string;
  children: React.ReactNode;
  quiet?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`button button-${quiet ? "secondary" : "primary"}`}
    >
      {children}
    </Link>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
export function PageHeading({
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p className="lede">{children}</p>
      </div>
      {action}
    </div>
  );
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("panel", className)}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Notice({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "warn" | "bad" | "good";
}) {
  return (
    <div
      className={`notice notice-${tone}`}
      role={tone === "bad" ? "alert" : undefined}
    >
      {tone === "warn" || tone === "bad" ? (
        <TriangleAlert size={17} aria-hidden="true" />
      ) : (
        <Info size={17} aria-hidden="true" />
      )}
      <div>{children}</div>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <div className="empty-copy">{children}</div>
    </div>
  );
}
export function Loading({
  label = "Reading backend records…",
}: {
  label?: string;
}) {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />
      {label}
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  const text =
    error instanceof Error ? error.message : "Unable to read backend data.";
  return (
    <div
      className="error-state"
      data-status={error instanceof ApiFailure ? error.reply.status : undefined}
      role="alert"
    >
      <TriangleAlert size={20} />
      <div>
        <strong>
          {error instanceof ApiFailure && error.reply.status
            ? `HTTP ${error.reply.status} · `
            : ""}
          {error instanceof ApiFailure && error.reply.status === 403
            ? "Access restricted"
            : "Unable to complete request"}
        </strong>
        <p>{text}</p>
        {retry && (
          <Button variant="secondary" onClick={retry}>
            Try reading again
          </Button>
        )}
      </div>
    </div>
  );
}
export function Json({
  value,
  label = "Actual response body",
  open = false,
}: {
  value: unknown;
  label?: string;
  open?: boolean;
}) {
  return (
    <details className="json-view" open={open}>
      <summary>{label}</summary>
      <pre>
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}
export function ReplyView({ reply }: { reply: Reply }) {
  return (
    <div
      className="reply"
      data-outcome={
        reply.status === 409
          ? "conflict"
          : reply.status === 403
            ? "denied"
            : reply.ok
              ? "success"
              : "failure"
      }
    >
      <div className="flex items-center gap-3">
        <Badge tone={reply.ok ? "good" : "bad"}>
          {reply.status === null ? "No HTTP response" : `HTTP ${reply.status}`}
        </Badge>
        <span className="muted text-xs">
          {reply.origin === "backend"
            ? "FastAPI response"
            : `${reply.origin} result · upstream outcome may need verification`}
        </span>
      </div>
      {!reply.ok && <p className="error-copy">{errorMessage(reply.body)}</p>}
      <Json value={reply.body} />
    </div>
  );
}
export function CopyId({
  value,
  short = false,
}: {
  value: string | null | undefined;
  short?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  return value ? (
    <span className="copy-id">
      <code title={value}>
        {short ? value.slice(0, 8) + "…" + value.slice(-4) : value}
      </code>
      <button
        type="button"
        aria-label={`Copy ${value}`}
        title="Copy identifier"
        onClick={async () => {
          try {
            setCopyError(false);
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          } catch {
            setCopied(false);
            setCopyError(true);
            setTimeout(() => setCopyError(false), 2500);
          }
        }}
      >
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </button>
      <span
        role="status"
        className={copied || copyError ? "copy-feedback" : "sr-only"}
      >
        {copied ? "Copied" : copyError ? "Copy unavailable" : ""}
      </span>
    </span>
  ) : (
    <span className="muted">Not provided</span>
  );
}
export function utc(value: string, includeTime = true) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return (
    new Intl.DateTimeFormat("en-IN", {
      dateStyle: "medium",
      ...(includeTime ? { timeStyle: "short" } : {}),
      timeZone: "UTC",
    }).format(date) + (includeTime ? " UTC" : "")
  );
}
export function BalanceCards({ balance }: { balance?: Balance }) {
  return (
    <dl className="balance-strip">
      {[
        [
          "Principal receivable",
          balance?.principal_receivable_paise,
          "Outstanding posted principal",
        ],
        [
          "Recognized interest",
          balance?.interest_receivable_paise,
          "Due interest recognized by the ledger",
        ],
        [
          "Penalty receivable",
          balance?.penalty_receivable_paise,
          "Posted overdue charges",
        ],
      ].map(([label, value, help]) => (
        <div key={String(label)}>
          <dt>{label}</dt>
          <dd>{typeof value === "number" ? inr(value) : "—"}</dd>
          <small>{help}</small>
        </div>
      ))}
    </dl>
  );
}
export function ScheduleTable({ rows }: { rows: ScheduleRow[] }) {
  return (
    <div className="table-scroll">
      <table>
        <caption className="sr-only">
          Original contractual instalment schedule, all monetary amounts
          displayed in INR
        </caption>
        <thead>
          <tr>
            <th>Instalment</th>
            <th>Due date (UTC)</th>
            <th className="numeric">Principal</th>
            <th className="numeric">Contractual interest</th>
            <th className="numeric">Scheduled total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <span className="number-chip">
                  {String(row.instalment_number).padStart(2, "0")}
                </span>
              </td>
              <td>{utc(row.due_date, false)}</td>
              <td className="numeric">{inr(row.principal_due_paise)}</td>
              <td className="numeric">{inr(row.interest_due_paise)}</td>
              <td className="numeric strong">
                {inr(
                  BigInt(row.principal_due_paise) +
                    BigInt(row.interest_due_paise),
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
