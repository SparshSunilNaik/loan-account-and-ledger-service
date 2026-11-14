"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { Fragment } from "react";
import { X } from "lucide-react";
import { useMobile } from "@/lib/workbench-state";
import { inr } from "@/lib/money";
import type {
  AuditEvent,
  Balance,
  Journal,
  Loan,
  Receipt,
  ScheduleRow,
} from "@/lib/types";
import { BalanceCards, Button, CopyId, Json, utc } from "./ui";
import { PostingEntries } from "./records";
export type SelectedRecord =
  | { kind: "journal" | "receipt" | "audit"; id: string }
  | { kind: "references" };
export function FinancialInspector({
  selected,
  loan,
  journals,
  receipts,
  schedules,
  balance,
  audit,
  onClose,
  onSelect,
}: {
  selected: SelectedRecord;
  loan: Loan;
  journals: Journal[];
  receipts: Receipt[];
  schedules: ScheduleRow[];
  balance?: Balance;
  audit?: AuditEvent;
  onClose: () => void;
  onSelect: (value: SelectedRecord) => void;
}) {
  const mobile = useMobile();
  const Portal = mobile ? Dialog.Portal : Fragment;
  const receipt =
    selected.kind === "receipt"
      ? receipts.find((r) => r.id === selected.id)
      : selected.kind === "journal"
        ? receipts.find(
            (r) =>
              r.journal_id === selected.id ||
              r.reversal_journal_id === selected.id ||
              journals.find((j) => j.id === selected.id)?.repayment_id === r.id,
          )
        : undefined;
  const journal =
    selected.kind === "journal"
      ? journals.find((j) => j.id === selected.id)
      : receipt
        ? journals.find((j) => j.id === receipt.journal_id)
        : undefined;
  const title =
    selected.kind === "receipt"
      ? "Repayment details"
      : selected.kind === "journal"
        ? "Journal details"
        : selected.kind === "audit"
          ? "Audit event"
          : "Loan references";
  return (
    <Dialog.Root
      open
      modal={mobile}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <Portal>
        {mobile && <Dialog.Overlay className="dialog-overlay" />}
        <Dialog.Content
          className="record-inspector"
          onInteractOutside={(e) => {
            if (!mobile) e.preventDefault();
          }}
        >
          <header className="sheet-heading">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>
                {loan.external_reference} · current loan
              </Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="Close inspector">
              <X size={18} />
            </Dialog.Close>
          </header>
          {selected.kind === "references" && (
            <dl className="drawer-record">
              <div>
                <dt>Loan ID</dt>
                <dd>
                  <CopyId value={loan.id} />
                </dd>
              </div>
              <div>
                <dt>Borrower ID</dt>
                <dd>
                  <CopyId value={loan.borrower_id} />
                </dd>
              </div>
              <div>
                <dt>Product ID</dt>
                <dd>
                  <CopyId value={loan.product_id} />
                </dd>
              </div>
              <div>
                <dt>Annual nominal rate / conversion</dt>
                <dd>
                  {loan.annual_rate} /{" "}
                  {loan.frequency === "weekly" ? "52" : "12"} per period
                </dd>
              </div>
              <div>
                <dt>Schedule version</dt>
                <dd>{loan.schedule_version}</dd>
              </div>
            </dl>
          )}
          {receipt && (
            <section className="inspector-receipt">
              <div className="inspector-amount">
                {inr(receipt.amount_paise)}
              </div>
              <p className="page-note">
                {receipt.status} · occurred {utc(receipt.occurred_at)} ·
                processing {receipt.business_date}
              </p>
              <h3>Allocation records</h3>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Component</th>
                      <th>Instalment</th>
                      <th className="numeric">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {receipt.allocations.map((a, i) => (
                      <tr key={i}>
                        <td className="capitalize">{a.component}</td>
                        <td>
                          {schedules.find((s) => s.id === a.schedule_id)
                            ?.instalment_number ?? (
                            <CopyId value={a.schedule_id} short />
                          )}
                        </td>
                        <td className="numeric">{inr(a.amount_paise)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="inspector-id">
                <span>Receipt</span>
                <CopyId value={receipt.id} />
              </div>
              <div className="inspector-id">
                <span>Journal</span>
                <CopyId value={receipt.journal_id} />
              </div>
              {selected.kind === "receipt" && (
                <Button
                  variant="quiet"
                  onClick={() =>
                    onSelect({ kind: "journal", id: receipt.journal_id })
                  }
                >
                  Inspect linked journal
                </Button>
              )}
            </section>
          )}
          {journal && (
            <section>
              <h3>{journal.kind.replaceAll("_", " ")}</h3>
              <p className="page-note">{journal.description}</p>
              <PostingEntries journal={journal} />
              {selected.kind === "journal" && receipt && (
                <Button
                  variant="quiet"
                  onClick={() => onSelect({ kind: "receipt", id: receipt.id })}
                >
                  Inspect linked receipt
                </Button>
              )}
            </section>
          )}
          {selected.kind !== "audit" && selected.kind !== "references" && (
            <>
              <h3>Current receivables</h3>
              <BalanceCards balance={balance} />
              <p className="form-note">
                Current backend ledger state; not a reconstruction at this
                record’s posting time or a future payoff quote.
              </p>
            </>
          )}
          {selected.kind === "audit" && audit && (
            <>
              <dl className="drawer-record">
                <div>
                  <dt>Action / UTC timestamp</dt>
                  <dd>
                    {audit.action}
                    <br />
                    {utc(audit.created_at)}
                  </dd>
                </div>
                <div>
                  <dt>Actor</dt>
                  <dd>
                    <CopyId value={audit.actor_user_id} />
                  </dd>
                </div>
                <div>
                  <dt>Entity</dt>
                  <dd>
                    {audit.entity_type}
                    <br />
                    <CopyId value={audit.entity_id} />
                  </dd>
                </div>
                <div>
                  <dt>Correlation</dt>
                  <dd>
                    <CopyId value={audit.correlation_id} />
                  </dd>
                </div>
              </dl>
              <Json open value={audit.details} label="Actual event metadata" />
            </>
          )}
        </Dialog.Content>
      </Portal>
    </Dialog.Root>
  );
}
