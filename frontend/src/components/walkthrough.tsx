"use client";
import { useState } from "react";
import { Check, ArrowRight } from "lucide-react";
import {
  api,
  snapshot,
  observeRepayment,
  type Attempt,
  type Observation,
  type Reply,
  type Snapshot,
} from "@/lib/api";
import { session } from "@/lib/session";
import { inr } from "@/lib/money";
import type { AuditEvent, Borrower, Loan, ScheduleRow } from "@/lib/types";
import { JournalList } from "./records";
import { ObservationView } from "./observation";
import {
  BalanceCards,
  Button,
  ButtonLink,
  CopyId,
  Json,
  Notice,
  PageHeading,
  ReplyView,
  ScheduleTable,
  utc,
} from "./ui";
const stages = [
  "Create borrower",
  "Create loan",
  "Inspect schedule",
  "Disburse loan",
  "Post partial repayment",
  "Retry identical delivery",
  "Verify financial records",
  "Verify audit trail",
];
const descriptions = [
  "Create an invented borrower as demo-officer.",
  "Originate ₹100 over two monthly instalments.",
  "Read the immutable schedule returned by the backend.",
  "Post the disbursement as demo-manager on 1 Jan 2026.",
  "Post ₹10 on 31 Jan; recognize due interest atomically.",
  "Replay the frozen actor, key and payload.",
  "Read the receivables, receipts and journals as demo-auditor.",
  "Find this transaction’s actual audit records.",
];
export function Walkthrough({ embedded = false }: { embedded?: boolean }) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [borrower, setBorrower] = useState<Borrower>();
  const [loan, setLoan] = useState<Loan>();
  const [rows, setRows] = useState<ScheduleRow[]>();
  const [reply, setReply] = useState<Reply>();
  const [stepReplies, setStepReplies] = useState<Record<number, Reply>>({});
  const [attempt, setAttempt] = useState<Attempt>();
  const [observations, setObservations] = useState<Observation[]>([]);
  const [records, setRecords] = useState<Snapshot>();
  const [audit, setAudit] = useState<AuditEvent[]>();
  const [auditInfo, setAuditInfo] = useState("");
  async function advance() {
    setBusy(true);
    setError("");
    try {
      if (step === 0) {
        const r = await api.createBorrower(
          {
            external_reference: `STUDIO-DEMO-B-${crypto.randomUUID()}`,
            full_name: "Invented Studio Walkthrough Borrower",
            phone: null,
          },
          "demo-officer",
        );
        setReply(r);
        setStepReplies((previous) => ({ ...previous, [step]: r }));
        if (!r.ok) return;
        setBorrower(r.body);
      }
      if (step === 1) {
        if (!borrower) throw Error("Create a borrower first.");
        const products = await api.products("demo-officer");
        const p = products.find((p) => p.code === "PERSONAL_EMI" && p.active);
        if (!p) throw Error("Active PERSONAL_EMI product not available.");
        const r = await api.createLoan(
          {
            external_reference: `STUDIO-DEMO-L-${crypto.randomUUID()}`,
            borrower_id: borrower.id,
            product_id: p.id,
            principal_paise: 10000,
            tenure_periods: 2,
            first_due_date: "2026-01-31",
          },
          "demo-officer",
        );
        setReply(r);
        setStepReplies((previous) => ({ ...previous, [step]: r }));
        if (!r.ok) return;
        setLoan(r.body);
        session.remember(r.body.id, r.body.external_reference);
      }
      if (!loan && step >= 2) throw Error("No walkthrough loan is available.");
      if (step === 2) setRows(await api.schedule(loan!.id, "demo-officer"));
      if (step === 3) {
        const r = await api.disburse(loan!.id, "2026-01-01", "demo-manager");
        setReply(r);
        setStepReplies((previous) => ({ ...previous, [step]: r }));
        if (!r.ok) return;
      }
      if (step === 4) {
        const a: Attempt = attempt ?? {
          loanId: loan!.id,
          actor: "demo-officer",
          key: `studio-demo-${crypto.randomUUID()}`,
          body: {
            amount_paise: 1000,
            source: "studio-walkthrough",
            external_event_id: `demo-${crypto.randomUUID()}`,
            occurred_at: "2026-01-31T10:00:00Z",
            business_date: "2026-01-31",
          },
        };
        setAttempt(a);
        const r = await observeRepayment(
          a,
          "Partial repayment · due interest recognized atomically",
        );
        setObservations([r]);
        setReply(r.reply);
        if (!r.reply.ok) return;
      }
      if (step === 5) {
        if (!attempt) throw Error("No frozen delivery is available.");
        const r = await observeRepayment(
          attempt,
          "Exact retry · verify the same receipt and journal",
        );
        setObservations((o) => [...o, r]);
        setReply(r.reply);
        if (!r.reply.ok) return;
        const original = observations[0]?.reply.body as {
          id?: string;
          journal_id?: string;
        };
        const retried = r.reply.body as { id?: string; journal_id?: string };
        if (
          original.id !== retried.id ||
          original.journal_id !== retried.journal_id ||
          !r.before ||
          !r.after ||
          r.before.receipts.length !== r.after.receipts.length ||
          r.before.ledger.length !== r.after.ledger.length
        )
          throw Error(
            "Retry invariants could not be verified. Inspect actual records.",
          );
      }
      if (step === 6) setRecords(await snapshot(loan!.id, "demo-auditor"));
      if (step === 7) {
        const found: AuditEvent[] = [];
        let offset = 0,
          done = false;
        const ids = new Set(
          (await api.ledger(loan!.id, "demo-auditor")).map((j) => j.id),
        );
        for (let page = 0; page < 100; page++) {
          const events = await api.audit("demo-auditor", offset, 500);
          found.push(
            ...events.filter(
              (e) =>
                e.entity_id === loan!.id ||
                e.entity_id === borrower?.id ||
                e.details.loan_id === loan!.id ||
                ids.has(String(e.details.journal_id)),
            ),
          );
          offset += events.length;
          if (events.length < 500) {
            done = true;
            break;
          }
        }
        setAudit(found);
        setAuditInfo(
          `Read ${offset} actual audit records${done ? " (end of available history)" : "; safety limit reached, use Audit viewer to continue"}. Filtered by this borrower, loan and journal identifiers.`,
        );
        if (!found.length)
          throw Error(
            "No matching audit records found in the pages read; verification is incomplete.",
          );
      }
      setStep((s) => s + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {embedded ? (
        <div className="embedded-heading">
          <h2>Guided demonstration</h2>
          <p>
            Create a fresh loan, post a partial payment and verify the same
            delivery is reused.
          </p>
        </div>
      ) : (
        <PageHeading eyebrow="" title="Guided demonstration">
          A fresh loan, a partial payment, and a verified identical retry.
        </PageHeading>
      )}
      <div className="walkthrough-layout">
        <div className="walkthrough-main">
          <div className="walkthrough-intro">
            <span className="status-dot" />
            <p>
              Live local API calls. Each step names its demo actor. Existing
              records are never deleted.
            </p>
          </div>
          <ol className="transaction-stepper">
            {stages.map((name, i) => (
              <li
                key={name}
                className={
                  i < step ? "complete" : i === step ? "current" : "pending"
                }
                aria-current={i === step ? "step" : undefined}
              >
                <span className="step-marker">
                  {i < step ? (
                    <Check size={15} />
                  ) : (
                    String(i + 1).padStart(2, "0")
                  )}
                </span>
                <div className="step-content">
                  <div className="step-heading">
                    <h2>{name}</h2>
                    <span>
                      {i < 3
                        ? "Officer"
                        : i === 3
                          ? "Manager"
                          : i < 6
                            ? "Officer"
                            : "Auditor"}
                    </span>
                  </div>
                  <p className="step-description">{descriptions[i]}</p>
                  {i === 0 && borrower && (
                    <div className="step-record">
                      <span>{borrower.full_name}</span>
                      <CopyId value={borrower.id} short />
                    </div>
                  )}
                  {i === 1 && loan && (
                    <div className="step-record">
                      <span>
                        {inr(loan.principal_paise)} · {loan.tenure_periods}{" "}
                        instalments · first due {loan.first_due_date}
                      </span>
                      <CopyId value={loan.id} short />
                    </div>
                  )}
                  {i === 2 && rows && (
                    <details className="step-evidence" open={step === 3}>
                      <summary>
                        Returned schedule · {rows.length} instalments
                      </summary>
                      <ScheduleTable rows={rows} />
                    </details>
                  )}
                  {i === 3 && stepReplies[3] && (
                    <div className="step-record">
                      <span>
                        Disbursement response · HTTP {stepReplies[3].status}
                      </span>
                      <CopyId
                        value={
                          (stepReplies[3].body as { journal_id?: string })
                            .journal_id
                        }
                      />
                    </div>
                  )}
                  {i === 4 && observations[0] && (
                    <ObservationView value={observations[0]} compact />
                  )}
                  {i === 5 && observations.length > 1 && (
                    <ObservationView
                      value={observations[observations.length - 1]}
                      compact
                    />
                  )}
                  {i === 6 && records && (
                    <>
                      <p className="step-record">
                        {records.receipts.length} receipts ·{" "}
                        {records.ledger.length} posted journals returned
                      </p>
                      <details className="step-evidence">
                        <summary>Inspect financial records</summary>
                        <JournalList journals={records.ledger} />
                        <Json
                          value={records.receipts}
                          label="Actual repayment receipts"
                        />
                      </details>
                    </>
                  )}
                  {i === 7 && audit && (
                    <>
                      <p className="step-record">
                        {audit.length} matching events
                      </p>
                      <details className="step-evidence" open={step === 8}>
                        <summary>Audit evidence</summary>
                        <p className="page-note">{auditInfo}</p>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>Action</th>
                                <th>Actor</th>
                                <th>Timestamp · UTC</th>
                              </tr>
                            </thead>
                            <tbody>
                              {audit.map((e) => (
                                <tr key={e.id}>
                                  <td>{e.action}</td>
                                  <td>
                                    <CopyId value={e.actor_user_id} short />
                                  </td>
                                  <td>{utc(e.created_at)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <Json
                          value={audit}
                          label="Actual matching audit events · actor IDs and metadata"
                        />
                      </details>
                    </>
                  )}
                  {i === step && reply && !reply.ok && (
                    <ReplyView reply={reply} />
                  )}
                  {i === step && (
                    <div className="step-action">
                      <Button busy={busy} onClick={() => void advance()}>
                        {step === 4 && attempt
                          ? "Retry frozen partial repayment"
                          : name}
                        <ArrowRight size={14} />
                      </Button>
                      {error && <Notice tone="bad">{error}</Notice>}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
          {step === 8 && (
            <Notice tone="good">
              Walkthrough complete. The actual retry returned the same receipt
              and journal, and observed counts remained unchanged.
            </Notice>
          )}
        </div>
        <aside className="walk-summary">
          <div className="summary-heading">
            <h2>Transaction summary</h2>
            <span>{step} / 8</span>
          </div>
          <div
            className="walk-progress"
            role="progressbar"
            aria-label="Walkthrough progress"
            aria-valuenow={step}
            aria-valuemin={0}
            aria-valuemax={8}
          >
            <span style={{ width: `${(step / 8) * 100}%` }} />
          </div>
          <div className="summary-block">
            <span className="meta-label">
              {loan
                ? "Original principal · API"
                : "Planned example · not yet originated"}
            </span>
            <div className="summary-money">
              {loan ? inr(loan.principal_paise) : "₹100.00"}
            </div>
            <p className="muted">Personal EMI · 2 monthly instalments</p>
          </div>
          <dl className="drawer-record">
            <div>
              <dt>Borrower ID</dt>
              <dd>
                <CopyId value={borrower?.id} />
              </dd>
            </div>
            <div>
              <dt>Loan ID</dt>
              <dd>
                <CopyId value={loan?.id} />
              </dd>
            </div>
            <div>
              <dt>Frozen idempotency key</dt>
              <dd>
                <CopyId value={attempt?.key} />
              </dd>
            </div>
          </dl>
          {records && (
            <>
              <h3 className="summary-section-title">Posted receivables</h3>
              <BalanceCards balance={records.balance} />
              <p className="summary-note">
                Actual ledger-derived balances, not a future payoff quote.
              </p>
            </>
          )}
          {loan && (
            <div className="summary-links">
              <ButtonLink href={`/loans/${loan.id}`} quiet>
                Open loan
              </ButtonLink>
              <ButtonLink href="/testing" quiet>
                Open laboratory
              </ButtonLink>
            </div>
          )}
          {reply && (
            <details className="step-evidence">
              <summary>
                Latest HTTP response · {reply.status ?? "No response"}
              </summary>
              <ReplyView reply={reply} />
            </details>
          )}
          <p className="summary-note">
            Progress is held in this page. Reloading starts a new flow without
            resetting the database.
          </p>
        </aside>
      </div>
    </>
  );
}
