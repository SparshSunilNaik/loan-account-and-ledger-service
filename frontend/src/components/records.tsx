"use client";
import Link from "next/link";
import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronDown, Check } from "lucide-react";
import { api } from "@/lib/api";
import { inr, journalTotals } from "@/lib/money";
import { useStudio } from "@/lib/session";
import type { Journal, Receipt } from "@/lib/types";
import { Badge, CopyId, Empty, ErrorState, Json, Loading, utc } from "./ui";
const explanations: Record<string, string> = {
  disbursement:
    "Principal receivable is debited and cash credited. Funds were disbursed once.",
  scheduled_interest:
    "Due contractual interest is recognized as a receivable and interest income.",
  repayment:
    "Cash is debited; recognized penalty, interest and principal receivables are credited according to allocation.",
  penalty:
    "A posted charge debits penalty receivable and credits penalty income. The API does not expose the accrual record itself.",
  reversal:
    "Opposite entries preserve the original posted journal and reverse its financial effect.",
};
export function ReceiptsTable({
  receipts,
  onSelect,
  selectedId,
}: {
  receipts: Receipt[];
  onSelect?: (id: string) => void;
  selectedId?: string;
}) {
  if (!receipts.length)
    return (
      <Empty title="No repayment receipts">
        No posted receipts were returned for this loan. Failed and denied
        delivery attempts are not payment receipts.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <caption className="sr-only">
          Authoritative repayment receipts and their operational state
        </caption>
        <thead>
          <tr>
            <th>Receipt / economic time</th>
            <th>Source event</th>
            <th className="numeric">Received amount</th>
            <th>Status</th>
            <th>Journal</th>
          </tr>
        </thead>
        <tbody>
          {receipts.map((r) => (
            <tr
              key={r.id}
              className={selectedId === r.id ? "is-selected" : undefined}
            >
              <td>
                {onSelect ? (
                  <button
                    className="record-select"
                    aria-label={`Inspect repayment ${r.id}`}
                    onClick={() => onSelect(r.id)}
                  >
                    View repayment
                  </button>
                ) : (
                  <CopyId value={r.id} short />
                )}
                <p className="muted text-xs mt-1">
                  Occurred {utc(r.occurred_at)}
                </p>
                <p className="muted text-xs">Received {utc(r.received_at)}</p>
              </td>
              <td>
                <span className="strong">{r.source}</span>
                <p className="mono text-xs mt-1 break-all">
                  {r.external_event_id}
                </p>
                <p className="muted text-xs">Business date {r.business_date}</p>
              </td>
              <td className="numeric strong">{inr(r.amount_paise)}</td>
              <td>
                <Badge tone={r.status === "reversed" ? "warn" : "good"}>
                  {r.status}
                </Badge>
                {!onSelect && (
                  <Json
                    label="Allocation records (paise)"
                    value={r.allocations}
                  />
                )}
              </td>
              <td>
                <CopyId value={r.journal_id} short />
                {r.reversal_journal_id && (
                  <p className="mt-2 text-xs">
                    Reversal <CopyId value={r.reversal_journal_id} short />
                  </p>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function JournalList({
  journals,
  limit,
  initialExpanded = true,
  onSelect,
  selectedId,
}: {
  journals: Journal[];
  limit?: number;
  initialExpanded?: boolean;
  onSelect?: (id: string) => void;
  selectedId?: string;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(
    () => new Set(initialExpanded ? journals.slice(0, 1).map((j) => j.id) : []),
  );
  if (!journals.length)
    return (
      <Empty title="No posted journals">
        Origination does not post a financial receivable. Disbursement creates
        the first journal.
      </Empty>
    );
  const rows = [...journals].sort(
    (a, b) =>
      a.posted_at.localeCompare(b.posted_at) || a.id.localeCompare(b.id),
  );
  const toggle = (id: string) =>
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  return (
    <>
      <div className="table-scroll">
        <table className="journal-register">
          <caption className="sr-only">
            Posted journals in posting chronology, expandable debit and credit
            entries
          </caption>
          <thead>
            <tr>
              <th>Journal / reference</th>
              <th>Posted · UTC</th>
              <th className="numeric">Debit (Dr)</th>
              <th className="numeric">Credit (Cr)</th>
              <th>Balance check</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, limit).map((j) => {
              const totals = journalTotals(j.entries);
              const open = !onSelect && expanded.has(j.id);
              const label = j.kind
                .replaceAll("_", " ")
                .replace(/^./, (c) => c.toUpperCase());
              return (
                <Fragment key={j.id}>
                  <tr
                    className={
                      selectedId === j.id
                        ? "journal-register-row is-selected"
                        : open
                          ? "journal-register-row expanded"
                          : "journal-register-row"
                    }
                  >
                    <td>
                      <button
                        className="journal-toggle"
                        aria-expanded={onSelect ? undefined : open}
                        aria-controls={onSelect ? undefined : `entries-${j.id}`}
                        aria-label={`${onSelect ? "Inspect" : open ? "Collapse" : "Expand"} ${label} journal ${j.id}`}
                        onClick={() =>
                          onSelect ? onSelect(j.id) : toggle(j.id)
                        }
                      >
                        <ChevronDown size={15} />
                        <span>{label}</span>
                      </button>
                      <div className="journal-id">
                        <CopyId value={j.id} short />
                        {j.repayment_id && (
                          <span className="muted"> · Receipt linked</span>
                        )}
                      </div>
                    </td>
                    <td className="journal-dates">
                      {utc(j.posted_at)}
                      <span className="cell-meta">
                        Business date {j.business_date}
                      </span>
                    </td>
                    <td className="numeric">{inr(totals.debit)}</td>
                    <td className="numeric">{inr(totals.credit)}</td>
                    <td>
                      <span
                        className={
                          totals.balanced
                            ? "balance-check"
                            : "balance-check failed"
                        }
                      >
                        {totals.balanced ? <Check size={13} /> : "!"}
                        {totals.balanced ? "Balanced" : "Unbalanced"}
                      </span>
                    </td>
                  </tr>
                  {open && (
                    <tr id={`entries-${j.id}`} className="entry-detail-row">
                      <td colSpan={5}>
                        <div className="entry-detail">
                          <div className="entry-explanation">
                            <p>{explanations[j.kind] ?? j.description}</p>
                            <span>Effective {utc(j.effective_at)}</span>
                          </div>
                          <table className="entry-table">
                            <caption className="sr-only">
                              Debit and credit entries for journal {j.id}
                            </caption>
                            <thead>
                              <tr>
                                <th>Ledger account</th>
                                <th>Entry references</th>
                                <th className="numeric">Debit (Dr)</th>
                                <th className="numeric">Credit (Cr)</th>
                              </tr>
                            </thead>
                            <tbody>
                              {j.entries.map((e) => (
                                <tr key={e.id}>
                                  <td>
                                    <span className="account-name">
                                      {e.account
                                        .toLowerCase()
                                        .replaceAll("_", " ")
                                        .replace(/^./, (c) => c.toUpperCase())}
                                    </span>
                                    <span className="cell-meta mono account-code">
                                      {e.account}
                                    </span>
                                  </td>
                                  <td>
                                    <div className="entry-refs">
                                      {e.schedule_id && (
                                        <span>
                                          Schedule{" "}
                                          <CopyId value={e.schedule_id} short />
                                        </span>
                                      )}
                                      {e.receivable_origin_id && (
                                        <span>
                                          Recognized lot{" "}
                                          <CopyId
                                            value={e.receivable_origin_id}
                                            short
                                          />
                                        </span>
                                      )}
                                      {!e.schedule_id &&
                                        !e.receivable_origin_id && (
                                          <span className="muted">
                                            Loan-level entry
                                          </span>
                                        )}
                                    </div>
                                  </td>
                                  <td className="numeric">
                                    {e.direction === "debit"
                                      ? inr(e.amount_paise)
                                      : "—"}
                                  </td>
                                  <td className="numeric">
                                    {e.direction === "credit"
                                      ? inr(e.amount_paise)
                                      : "—"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot>
                              <tr>
                                <td colSpan={2}>
                                  Journal totals · {j.entries.length} entries
                                </td>
                                <td className="numeric">{inr(totals.debit)}</td>
                                <td className="numeric">
                                  {inr(totals.credit)}
                                </td>
                              </tr>
                            </tfoot>
                          </table>
                          <div className="entry-footer">
                            <span>{j.description}</span>
                            {j.repayment_id && (
                              <span>
                                Repayment <CopyId value={j.repayment_id} />
                              </span>
                            )}
                            {j.reversal_of_id && (
                              <span>
                                Reverses <CopyId value={j.reversal_of_id} />
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {limit && rows.length > limit && (
        <p className="page-note">
          Showing {limit} of {rows.length} returned journals. Open the inspector
          for all entries.
        </p>
      )}
    </>
  );
}
export function LoanAudit({
  loanId,
  journalIds = [],
}: {
  loanId?: string;
  journalIds?: string[];
}) {
  const { actor } = useStudio();
  const events = useQuery({
    queryKey: ["loan-audit-first-page", actor, loanId],
    queryFn: () => api.audit(actor, 0, 100),
  });
  if (events.isPending) return <Loading />;
  if (events.isError) return <ErrorState error={events.error} />;
  const matches = events.data.filter(
    (e) =>
      e.entity_id === loanId ||
      e.details.loan_id === loanId ||
      journalIds.includes(String(e.details.journal_id)),
  );
  return (
    <>
      <p className="page-note">
        Matches in the first 100 audit records only. This is not a complete
        per-loan history endpoint.
      </p>
      {matches.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Action</th>
                <th>Time (UTC)</th>
                <th>Actor</th>
                <th>Correlation</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((e) => (
                <tr key={e.id}>
                  <td>
                    {e.action}
                    <Json value={e.details} label="Metadata" />
                  </td>
                  <td>{utc(e.created_at)}</td>
                  <td>
                    <CopyId value={e.actor_user_id} short />
                  </td>
                  <td>
                    <CopyId value={e.correlation_id} short />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title="No matches in this page">
          Use the audit viewer to paginate through the backend’s audit records.
        </Empty>
      )}
      <div className="px-6 py-4">
        <Link href="/audit" className="text-link">
          Open full audit viewer <ArrowUpRight size={12} />
        </Link>
      </div>
    </>
  );
}

export function PostingEntries({ journal }: { journal: Journal }) {
  const totals = journalTotals(journal.entries);
  return (
    <>
      <div className="table-scroll">
        <table className="payment-entry-table">
          <caption className="sr-only">Actual posted journal entries</caption>
          <thead>
            <tr>
              <th>Account</th>
              <th className="numeric">Debit</th>
              <th className="numeric">Credit</th>
            </tr>
          </thead>
          <tbody>
            {journal.entries.map((e) => (
              <tr key={e.id}>
                <td>
                  <span className="account-name">
                    {e.account.toLowerCase().replaceAll("_", " ")}
                  </span>
                </td>
                <td className="numeric">
                  {e.direction === "debit" ? inr(e.amount_paise) : "—"}
                </td>
                <td className="numeric">
                  {e.direction === "credit" ? inr(e.amount_paise) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>
                {totals.balanced ? "Balanced journal" : "Unbalanced journal"}
              </td>
              <td className="numeric">{inr(totals.debit)}</td>
              <td className="numeric">{inr(totals.credit)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="posting-date">
        Processing date {journal.business_date} · Posted{" "}
        {utc(journal.posted_at)}
      </p>
      <details className="technical-details">
        <summary>Journal reference</summary>
        <CopyId value={journal.id} />
      </details>
    </>
  );
}
