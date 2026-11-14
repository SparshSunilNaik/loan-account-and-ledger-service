"use client";
import Link from "next/link";
import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient, useIsFetching } from "@tanstack/react-query";
import {
  ArrowLeft,
  Plus,
  RefreshCw,
  PanelRight,
  Info,
  TerminalSquare,
} from "lucide-react";
import { api, type Reply } from "@/lib/api";
import { inr, percent } from "@/lib/money";
import { session, useStudio } from "@/lib/session";
import type { AuditEvent } from "@/lib/types";
import { type WorkbenchAction } from "@/lib/workbench-state";
import {
  Badge,
  Button,
  ErrorState,
  Field,
  Loading,
  ReplyView,
  ScheduleTable,
} from "./ui";
import { JournalList, ReceiptsTable } from "./records";
import { RepaymentSheet } from "./repayment-sheet";
import { LoanHistory } from "./loan-history";
import { FinancialInspector, type SelectedRecord } from "./financial-inspector";
const tabs = ["schedule", "repayments", "ledger", "history"] as const;
function selectView(tab: string) {
  if (!tabs.includes(tab as (typeof tabs)[number])) return;
  const url = new URL(window.location.href);
  url.searchParams.set("tab", tab);
  window.history.replaceState(null, "", url.pathname + url.search);
}
export function LoanDetail({ id }: { id: string }) {
  const { actor } = useStudio();
  const cache = useQueryClient();
  const search = useSearchParams();
  const initialTab = tabs.includes(search.get("tab") as (typeof tabs)[number])
    ? search.get("tab")!
    : "schedule";
  const tab = initialTab;
  const [sheet, setSheet] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [selected, setSelected] = useState<SelectedRecord | null>(() =>
    search.get("journal")
      ? { kind: "journal", id: search.get("journal")! }
      : null,
  );
  const [audit, setAudit] = useState<AuditEvent>();
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<Reply>();
  const [disburseDate, setDisburseDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const loan = useQuery({
    queryKey: ["loan", id, actor],
    queryFn: () => api.loan(id, actor),
  });
  const borrower = useQuery({
    queryKey: ["borrower", loan.data?.borrower_id, actor],
    queryFn: () => api.borrower(loan.data!.borrower_id, actor),
    enabled: !!loan.data,
  });
  const products = useQuery({
    queryKey: ["products", actor],
    queryFn: () => api.products(actor),
  });
  const schedule = useQuery({
    queryKey: ["schedule", id, actor],
    queryFn: () => api.schedule(id, actor),
  });
  const balance = useQuery({
    queryKey: ["balance", id, actor],
    queryFn: () => api.balance(id, actor),
  });
  const receipts = useQuery({
    queryKey: ["receipts", id, actor],
    queryFn: () => api.receipts(id, actor),
  });
  const ledger = useQuery({
    queryKey: ["ledger", id, actor],
    queryFn: () => api.ledger(id, actor),
  });
  const refreshing = useIsFetching({ queryKey: ["balance", id, actor] }) > 0;
  const permitted =
    loan.data?.status === "disbursed" && actor !== "demo-auditor";
  useEffect(() => {
    if (loan.data) session.remember(id, loan.data.external_reference);
  }, [id, loan.data]);
  useEffect(() => {
    function command(action: WorkbenchAction) {
      if (tabs.includes(action as (typeof tabs)[number])) selectView(action);
      if (action === "payment" && permitted) {
        setSelected(null);
        setSheet(true);
      }
      if (action === "refresh") void cache.invalidateQueries();
    }
    const custom = (e: Event) =>
      command((e as CustomEvent<WorkbenchAction>).detail);
    const keyboard = (e: KeyboardEvent) => {
      if (
        !e.altKey ||
        e.ctrlKey ||
        e.metaKey ||
        e.shiftKey ||
        (e.target instanceof HTMLElement &&
          (e.target.isContentEditable ||
            /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)))
      )
        return;
      const action = (
        {
          "1": "schedule",
          "2": "repayments",
          "3": "ledger",
          "4": "history",
          p: "payment",
          r: "refresh",
        } as Record<string, WorkbenchAction>
      )[
        e.code.startsWith("Digit")
          ? e.code.slice(5)
          : e.code.startsWith("Key")
            ? e.code.slice(3).toLowerCase()
            : e.key.toLowerCase()
      ];
      if (action) {
        e.preventDefault();
        command(action);
      }
    };
    window.addEventListener("ledgercore:workbench", custom);
    window.addEventListener("keydown", keyboard);
    return () => {
      window.removeEventListener("ledgercore:workbench", custom);
      window.removeEventListener("keydown", keyboard);
    };
  }, [permitted, cache]);
  function select(record: SelectedRecord) {
    setSheet(false);
    setSelected(record);
  }
  if (loan.isPending) return <Loading label="Opening the loan account…" />;
  if (loan.isError)
    return <ErrorState error={loan.error} retry={() => void loan.refetch()} />;
  const l = loan.data,
    product = products.data?.find((p) => p.id === l.product_id),
    name = borrower.data?.full_name ?? "Reading borrower…";
  return (
    <section
      className={`loan-workbench ${sheet || selected ? "has-inspector" : ""}`}
      aria-label="Loan workbench"
    >
      <div className="workbench-summary">
        <div className="account-heading">
          <Link
            href="/loans"
            className="workbench-back"
            aria-label="Back to known loans"
          >
            <ArrowLeft size={17} />
          </Link>
          <div className="account-heading-copy">
            <h1>{name}</h1>
            <p>
              {product?.name ?? "Reading product…"}{" "}
              <span>{l.external_reference}</span>
            </p>
          </div>
          <Badge tone={l.status === "disbursed" ? "good" : "neutral"}>
            {l.status === "originated" ? "Awaiting disbursement" : l.status}
          </Badge>
          <Button
            className={
              l.status === "originated" ? "awaiting-disbursement" : undefined
            }
            onClick={() => {
              setSelected(null);
              setAdvanced(false);
              setSheet(true);
            }}
            disabled={!permitted}
          >
            <Plus size={17} />
            Record repayment
          </Button>
        </div>
        {borrower.isError && <ErrorState error={borrower.error} />}
        <div className="account-position">
          <div className="account-principal">
            <span>Principal outstanding</span>
            <strong>
              {!balance.isError && balance.data
                ? inr(balance.data.principal_receivable_paise)
                : "—"}
            </strong>
            <small>Original {inr(l.principal_paise)}</small>
          </div>
          <div>
            <span>Recognized interest</span>
            <strong>
              {!balance.isError && balance.data
                ? inr(balance.data.interest_receivable_paise)
                : "—"}
            </strong>
          </div>
          <div>
            <span>Outstanding penalties</span>
            <strong>
              {!balance.isError && balance.data
                ? inr(balance.data.penalty_receivable_paise)
                : "—"}
            </strong>
          </div>
        </div>
        {balance.isError && <ErrorState error={balance.error} />}
        <div className="account-position-note">
          <span>Posted receivables, not a future payoff quote.</span>
          <div>
            <Button
              variant="quiet"
              onClick={() => {
                setSelected(null);
                setAdvanced(true);
                setSheet(true);
              }}
            >
              <TerminalSquare size={14} aria-hidden="true" />
              Delivery checks
            </Button>
            <Button
              variant="quiet"
              onClick={() => select({ kind: "references" })}
            >
              <Info size={14} />
              References
            </Button>
            <Button
              variant="quiet"
              busy={refreshing}
              onClick={() => void cache.invalidateQueries()}
            >
              {!refreshing && <RefreshCw size={14} aria-hidden="true" />}
              {refreshing ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
        </div>
        {actor === "demo-auditor" && (
          <p className="role-note">
            Auditor is read-only. Recording a repayment requires demo-officer or
            demo-manager.
          </p>
        )}
        {l.status === "originated" && (
          <div className="disbursement-prompt">
            <div>
              <h2>Ready for disbursement</h2>
              <p>
                {actor === "demo-manager"
                  ? "Posts the original principal once. Confirm the processing date before disbursing."
                  : "Choose demo-manager in the identity menu to disburse."}
              </p>
            </div>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                try {
                  setReply(await api.disburse(id, disburseDate, actor));
                  await cache.invalidateQueries();
                } finally {
                  setBusy(false);
                }
              }}
            >
              <Field label="Disbursement date (UTC)">
                <input
                  name="date"
                  type="date"
                  value={disburseDate}
                  onChange={(e) => setDisburseDate(e.target.value)}
                  required
                />
              </Field>
              <Button
                variant="secondary"
                busy={busy}
                disabled={actor !== "demo-manager"}
              >
                Disburse loan
              </Button>
            </form>
          </div>
        )}
        {reply && !reply.ok && <ReplyView reply={reply} />}
      </div>
      <div className="workbench-panels">
        <div className="workbench-register">
          <Tabs.Root value={tab} onValueChange={(tab) => selectView(tab)}>
            <Tabs.List className="tab-list" aria-label="Loan account views">
              {tabs.map((t) => (
                <Tabs.Trigger key={t} value={t} className="tab-trigger">
                  {t[0].toUpperCase() + t.slice(1)}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            <div
              className="workbench-data"
              role="region"
              aria-label="Loan records"
              tabIndex={0}
            >
              <Tabs.Content value="schedule">
                <div className="section-toolbar">
                  <h2>Contractual schedule</h2>
                  <span>
                    {l.tenure_periods} {l.frequency} instalments ·{" "}
                    {percent(l.annual_rate)} annual nominal ·{" "}
                    {l.interest_method === "flat"
                      ? "Flat rate"
                      : "Reducing balance"}
                  </span>
                </div>
                {schedule.isPending ? (
                  <Loading />
                ) : schedule.isError ? (
                  <ErrorState error={schedule.error} />
                ) : (
                  <ScheduleTable rows={schedule.data} />
                )}
                <p className="page-note">
                  Original amounts remain unchanged. Future contractual interest
                  is separate from recognized receivables.
                </p>
              </Tabs.Content>
              <Tabs.Content value="repayments">
                <div className="section-toolbar">
                  <h2>Repayments received</h2>
                  <span>Select a receipt for allocations and its journal.</span>
                </div>
                {receipts.isPending ? (
                  <Loading />
                ) : receipts.isError ? (
                  <ErrorState error={receipts.error} />
                ) : (
                  <ReceiptsTable
                    receipts={receipts.data}
                    onSelect={(id) => select({ kind: "receipt", id })}
                    selectedId={
                      selected?.kind === "receipt" ? selected.id : undefined
                    }
                  />
                )}
              </Tabs.Content>
              <Tabs.Content value="ledger">
                <div className="section-toolbar">
                  <h2>Money movement</h2>
                  <span>Select a posting to inspect its entries.</span>
                </div>
                {ledger.isPending ? (
                  <Loading />
                ) : ledger.isError ? (
                  <ErrorState error={ledger.error} />
                ) : (
                  <JournalList
                    journals={ledger.data}
                    initialExpanded={false}
                    onSelect={(id) => select({ kind: "journal", id })}
                    selectedId={
                      selected?.kind === "journal" ? selected.id : undefined
                    }
                  />
                )}
              </Tabs.Content>
              <Tabs.Content value="history">
                <h2>Loan history</h2>
                <LoanHistory
                  loanId={id}
                  relatedIds={[
                    ...(ledger.data?.map((j) => j.id) ?? []),
                    ...(receipts.data?.map((r) => r.id) ?? []),
                  ]}
                  onSelect={(event) => {
                    setAudit(event);
                    select({ kind: "audit", id: event.id });
                  }}
                />
              </Tabs.Content>
            </div>
          </Tabs.Root>
        </div>
        <aside className="workbench-inspector" aria-label="Financial inspector">
          {!sheet && !selected && (
            <div className="inspector-idle">
              <PanelRight size={22} />
              <h2>Inspect this account</h2>
              <p>
                Select a repayment or journal. Allocations, entries and current
                receivables appear here.
              </p>
              <Button
                variant="secondary"
                disabled={!permitted}
                onClick={() => setSheet(true)}
              >
                Open repayment form
              </Button>
              <p className="form-note">
                ⌘K / Ctrl+K commands · Alt+1–4 account views
              </p>
            </div>
          )}
          <RepaymentSheet
            key={id}
            loan={l}
            borrowerName={name}
            open={sheet}
            onOpenChange={setSheet}
            advanced={advanced}
            onAdvancedChange={setAdvanced}
            onRecorded={() => {
              /* Observation service and cache invalidation refresh actual records. */
            }}
            onViewJournal={(journalId) =>
              select({ kind: "journal", id: journalId })
            }
          />
          {selected && (
            <FinancialInspector
              selected={selected}
              loan={l}
              journals={ledger.data ?? []}
              receipts={receipts.data ?? []}
              schedules={schedule.data ?? []}
              balance={balance.isError ? undefined : balance.data}
              audit={audit}
              onClose={() => setSelected(null)}
              onSelect={select}
            />
          )}
        </aside>
      </div>
    </section>
  );
}
