"use client";
import { receiptEffect, type Observation } from "@/lib/api";
import { inr } from "@/lib/money";
import { CopyId, Json, ReplyView } from "./ui";
export function ObservationView({
  value,
  compact = false,
}: {
  value: Observation;
  compact?: boolean;
}) {
  const body = value.reply.body as { id?: string; journal_id?: string } | null;
  const rows = [
    [
      "Principal",
      value.before?.balance.principal_receivable_paise,
      value.after?.balance.principal_receivable_paise,
    ],
    [
      "Recognized interest",
      value.before?.balance.interest_receivable_paise,
      value.after?.balance.interest_receivable_paise,
    ],
    [
      "Penalty",
      value.before?.balance.penalty_receivable_paise,
      value.after?.balance.penalty_receivable_paise,
    ],
  ] as const;
  const evidence = (
    <>
      <dl className="result-identifiers">
        <div>
          <dt>Loan ID</dt>
          <dd>
            <CopyId value={value.attempt.loanId} />
          </dd>
        </div>
        <div>
          <dt>Repayment ID</dt>
          <dd>
            <CopyId value={body?.id} />
          </dd>
        </div>
        <div>
          <dt>Journal ID</dt>
          <dd>
            <CopyId value={body?.journal_id} />
          </dd>
        </div>
      </dl>
      <div className="table-scroll">
        <table className="balance-comparison">
          <caption className="sr-only">
            Before and after ledger-derived receivables
          </caption>
          <thead>
            <tr>
              <th>Receivable</th>
              <th className="numeric">Before</th>
              <th className="numeric">After</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, before, after]) => (
              <tr key={label}>
                <td>{label}</td>
                <td className="numeric muted">
                  {before === undefined ? "—" : inr(before)}
                </td>
                <td className="numeric">
                  {after === undefined ? "—" : inr(after)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="observation-counts">
        <span>
          Receipts{" "}
          <b>
            {value.before?.receipts.length ?? "—"} →{" "}
            {value.after?.receipts.length ?? "—"}
          </b>
        </span>
        <span>
          Journals{" "}
          <b>
            {value.before?.ledger.length ?? "—"} →{" "}
            {value.after?.ledger.length ?? "—"}
          </b>
        </span>
      </div>
      {value.verificationError && (
        <p className="error-copy">
          After-state unavailable: {value.verificationError}
        </p>
      )}
      <ReplyView reply={value.reply} />
      <Json
        value={value.attempt}
        label="Frozen request · actor, body and key"
      />
      <p className="observation-note">
        Separate backend reads, not an atomic snapshot. Concurrent activity can
        affect observations.
      </p>
    </>
  );
  return (
    <section className="observation">
      <header>
        <h3>{value.name}</h3>
        <span className="meta-label">{value.attempt.actor}</span>
      </header>
      <p className={`receipt-effect ${value.reply.ok ? "effect-good" : ""}`}>
        {receiptEffect(value.reply, value.before, value.after)}
      </p>
      {compact ? (
        <>
          <div className="compact-receipt-ids">
            <span>
              Receipt <CopyId value={body?.id} short />
            </span>
            <span>
              Journal <CopyId value={body?.journal_id} short />
            </span>
          </div>
          <details className="compact-observation-details">
            <summary>
              Balance evidence · receipts {value.before?.receipts.length ?? "—"}{" "}
              → {value.after?.receipts.length ?? "—"} · journals{" "}
              {value.before?.ledger.length ?? "—"} →{" "}
              {value.after?.ledger.length ?? "—"}
            </summary>
            {evidence}
          </details>
        </>
      ) : (
        evidence
      )}
    </section>
  );
}
