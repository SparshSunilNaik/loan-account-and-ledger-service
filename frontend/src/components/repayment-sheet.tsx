"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { Fragment, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, X, ArrowRight } from "lucide-react";
import {
  observeRepayment,
  receiptEffect,
  type Attempt,
  type Observation,
} from "@/lib/api";
import { useDelivery, rememberDelivery } from "@/lib/delivery-context";
import { MAX_PAISE, rupeesToPaise, inr } from "@/lib/money";
import { useStudio } from "@/lib/session";
import type { Loan, Receipt } from "@/lib/types";
import {
  useSessionDraft,
  isPaymentDraft,
  useMobile,
} from "@/lib/workbench-state";
import { Button, Field, Json, Notice, BalanceCards, CopyId } from "./ui";

import { PostingEntries } from "./records";
import { ObservationView } from "./observation";
export function RepaymentSheet({
  loan,
  borrowerName,
  open,
  onOpenChange,
  onRecorded,
  onViewJournal,
  advanced = false,
  onAdvancedChange,
}: {
  advanced?: boolean;
  onAdvancedChange?: (open: boolean) => void;
  loan: Loan;
  borrowerName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRecorded: (observation: Observation) => void;
  onViewJournal: (id: string) => void;
}) {
  const { actor } = useStudio();
  const cache = useQueryClient();
  const now = new Date().toISOString();
  const mobile = useMobile();
  const saved = useDelivery(loan.id);
  const [draft, setDraft] = useSessionDraft(
    `payment:${loan.id}`,
    {
      amount: "",
      date: now.slice(0, 10),
      occurred: now.slice(0, 16),
      preparedKey: "",
    },
    isPaymentDraft,
  );
  const { amount, date, occurred } = draft;
  const setAmount = (value: string) =>
    setDraft((v) => ({ ...v, amount: value }));
  const setDate = (value: string) => setDraft((v) => ({ ...v, date: value }));
  const setOccurred = (value: string) =>
    setDraft((v) => ({ ...v, occurred: value }));
  const [identity, setIdentity] = useState(() => ({
    key: `payment-${crypto.randomUUID()}`,
    event: `payment-${crypto.randomUUID()}`,
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [localFrozen, setFrozen] = useState<Attempt>();
  const frozen =
    localFrozen ??
    (draft.preparedKey && saved?.key === draft.preparedKey ? saved : undefined);
  const [verifiedKey, setVerifiedKey] = useState("");
  const [testResult, setTestResult] = useState<Observation>();
  const [result, setResult] = useState<Observation>();
  const errorRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const advancedRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => {
      const container = contentRef.current;
      if (!container || container.dataset.state !== "open") return;
      if (advanced && advancedRef.current) {
        container.scrollTop =
          advancedRef.current.offsetTop - container.offsetTop;
        advancedRef.current
          .querySelector<HTMLButtonElement>("button:not(:disabled)")
          ?.focus({ preventScroll: true });
      } else if (!draft.preparedKey && !result) {
        container
          .querySelector<HTMLInputElement>("#payment-amount")
          ?.focus({ preventScroll: true });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [open, advanced, draft.preparedKey, result]);
  async function send(attempt: Attempt) {
    setBusy(true);
    setError("");
    setFrozen(attempt);
    setDraft((v) => ({ ...v, preparedKey: attempt.key }));
    rememberDelivery(attempt);
    try {
      const o = await observeRepayment(attempt, "Account repayment");
      setResult(o);
      const observed = receiptEffect(o.reply, o.before, o.after);
      if (
        observed.startsWith("New receipt") ||
        observed.startsWith("Existing receipt")
      )
        setVerifiedKey(attempt.key);
      await cache.invalidateQueries();
      if (o.reply.ok) onRecorded(o);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "No repayment was confirmed. Retry the same prepared request after checking connectivity.",
      );
      setTimeout(() => errorRef.current?.focus(), 0);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => {
        if (contentRef.current) contentRef.current.scrollTop = 0;
      });
    }
  }
  const receipt =
    result?.reply.ok && result.reply.status === 201
      ? (result.reply.body as Receipt)
      : undefined;
  const effect = result
    ? receiptEffect(result.reply, result.before, result.after)
    : "";
  const verified =
    effect.startsWith("New receipt") || effect.startsWith("Existing receipt");
  const journal = receipt
    ? result?.after?.ledger.find((j) => j.id === receipt.journal_id)
    : undefined;
  const allocations = receipt
    ? ["penalty", "interest", "principal"].map((c) => ({
        component: c,
        amount: receipt.allocations
          .filter((a) => a.component === c)
          .reduce((sum, a) => sum + BigInt(a.amount_paise), 0n),
      }))
    : [];
  async function testDelivery(
    kind: "retry" | "conflict" | "alias" | "auditor",
  ) {
    const original = frozen || saved;
    if (!original) return;
    if (
      (kind === "conflict" || kind === "alias") &&
      verifiedKey !== original.key
    ) {
      setError(
        "Verify the original delivery with Retry identical request before testing a modified payload or new key.",
      );
      return;
    }
    const attempt = structuredClone(original);
    if (kind === "conflict")
      attempt.body.amount_paise = Number(
        BigInt(attempt.body.amount_paise) +
          (BigInt(attempt.body.amount_paise) === MAX_PAISE ? -1n : 1n),
      );
    if (kind === "alias") attempt.key = `alias-${crypto.randomUUID()}`;
    if (kind === "auditor") {
      attempt.actor = "demo-auditor";
      attempt.key = crypto.randomUUID();
      attempt.body.external_event_id = crypto.randomUUID();
    }
    setBusy(true);
    try {
      const observed = await observeRepayment(
        attempt,
        kind === "retry"
          ? "Exact frozen retry"
          : kind === "conflict"
            ? "Same key · modified amount"
            : kind === "alias"
              ? "Source alias"
              : "Auditor denial",
      );
      setTestResult(observed);
      const effect = receiptEffect(
        observed.reply,
        observed.before,
        observed.after,
      );
      if (
        kind === "retry" &&
        (effect.startsWith("New receipt") ||
          effect.startsWith("Existing receipt"))
      )
        setVerifiedKey(original.key);
      await cache.invalidateQueries();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "No delivery result available. Original identity is retained.",
      );
    } finally {
      setBusy(false);
    }
  }
  const Portal = mobile ? Dialog.Portal : Fragment;
  return (
    <Dialog.Root
      modal={mobile}
      open={open}
      onOpenChange={(v) => {
        if (!busy) onOpenChange(v);
      }}
    >
      <Portal>
        {mobile && <Dialog.Overlay className="dialog-overlay" />}
        <Dialog.Content
          aria-hidden={!open || undefined}
          ref={contentRef}
          className="repayment-sheet workbench-repayment"
          onInteractOutside={(e) => {
            if (!mobile) e.preventDefault();
          }}
          onEscapeKeyDown={(e) => {
            if (busy) e.preventDefault();
          }}
        >
          <header className="sheet-heading">
            <div>
              <Dialog.Title>
                {receipt && verified
                  ? "Repayment recorded"
                  : "Record repayment"}
              </Dialog.Title>
              <Dialog.Description>
                {borrowerName} · {loan.external_reference}
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="icon-button"
              aria-label="Close repayment"
              disabled={busy}
            >
              <X size={21} />
            </Dialog.Close>
          </header>
          {!result?.reply.ok && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setError("");
                if (frozen) {
                  void send(frozen);
                  return;
                }
                if (draft.preparedKey) {
                  setError(
                    "The prepared delivery is still loading. Inspect its original identity before sending another payment.",
                  );
                  return;
                }
                let paise: number;
                try {
                  paise = rupeesToPaise(amount);
                } catch (e) {
                  setError(
                    e instanceof Error
                      ? e.message
                      : "Enter a valid rupee amount",
                  );
                  setTimeout(() => errorRef.current?.focus(), 0);
                  return;
                }
                const occurredISO = new Date(occurred + "Z");
                if (Number.isNaN(occurredISO.valueOf())) {
                  setError("Enter a valid UTC payment time.");
                  return;
                }
                void send({
                  loanId: loan.id,
                  actor,
                  key: identity.key,
                  body: {
                    amount_paise: paise,
                    source: "studio-account",
                    external_event_id: identity.event,
                    occurred_at: occurredISO.toISOString(),
                    business_date: date,
                  },
                });
              }}
            >
              <Field label="Amount received (INR)">
                <input
                  id="payment-amount"
                  aria-describedby={error ? "payment-error" : undefined}
                  aria-invalid={!!error}
                  inputMode="decimal"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  required
                  disabled={!!draft.preparedKey}
                  autoFocus
                />
              </Field>
              <Field label="Payment time (UTC)">
                <input
                  type="datetime-local"
                  value={occurred}
                  onChange={(e) => setOccurred(e.target.value)}
                  required
                  disabled={!!draft.preparedKey}
                />
              </Field>
              <Field label="Processing date (UTC)">
                <input
                  type="date"
                  min="1900-01-01"
                  max="2100-12-31"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  required
                  disabled={!!draft.preparedKey}
                />
              </Field>
              <p className="payment-policy">
                The backend recognizes interest due by this processing date,
                then allocates to penalties, interest and principal. Future
                interest is not collected.
              </p>
              {error && (
                <div
                  ref={errorRef}
                  id="payment-error"
                  className="validation-summary"
                  tabIndex={-1}
                  role="alert"
                >
                  <h3>Payment not confirmed</h3>
                  <p>{error}</p>
                </div>
              )}
              <div className="form-actions">
                <Button
                  busy={busy}
                  disabled={actor === "demo-auditor" && !frozen}
                >
                  {frozen ? "Retry prepared repayment" : "Record repayment"}
                </Button>
                {frozen && (
                  <Button
                    type="button"
                    variant="quiet"
                    disabled={busy}
                    onClick={() => {
                      setFrozen(undefined);
                      setDraft((v) => ({ ...v, preparedKey: "" }));
                      setIdentity({
                        key: `payment-${crypto.randomUUID()}`,
                        event: `payment-${crypto.randomUUID()}`,
                      });
                      setResult(undefined);
                      setError("");
                    }}
                  >
                    Edit as a new request
                  </Button>
                )}
              </div>
              {frozen && (
                <p className="form-note">
                  Retry uses exactly the prepared actor, amount, date and
                  delivery identity. Editing as new creates a different
                  instruction; inspect records first if the prior outcome is
                  unknown.
                </p>
              )}
            </form>
          )}
          {receipt && (
            <div className="payment-confirmation">
              <div className="payment-confirmation-amount">
                <span className="confirmation-check">
                  <Check size={21} />
                </span>
                <strong>{inr(receipt.amount_paise)}</strong>
                <span>
                  {effect.startsWith("Existing receipt")
                    ? "Existing receipt reused"
                    : verified
                      ? "Received and verified"
                      : "Response received; verification incomplete"}
                </span>
              </div>
              <h3>Where the payment went</h3>
              <dl className="allocation-story">
                {allocations.map((a) => (
                  <div key={a.component}>
                    <dt>
                      {a.component === "principal"
                        ? "Principal settled"
                        : a.component === "interest"
                          ? "Recognized interest paid"
                          : "Penalties paid"}
                    </dt>
                    <dd>{inr(a.amount)}</dd>
                  </div>
                ))}
              </dl>
              <p className="compact-http" role="status">
                HTTP {result!.reply.status} ·{" "}
                {result!.reply.origin === "backend"
                  ? "FastAPI response"
                  : "Proxy result"}
              </p>
              {journal && (
                <>
                  <h3>How this payment was recorded</h3>
                  <PostingEntries journal={journal} />
                </>
              )}
              <h3>Receivables after this observation</h3>
              <BalanceCards balance={result?.after?.balance} />
              <Button onClick={() => onViewJournal(receipt.journal_id)}>
                View posted journal in account <ArrowRight size={16} />
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setFrozen(undefined);
                  setDraft((v) => ({ ...v, amount: "", preparedKey: "" }));
                  setResult(undefined);
                  setTestResult(undefined);
                  setError("");
                  setIdentity({
                    key: `payment-${crypto.randomUUID()}`,
                    event: `payment-${crypto.randomUUID()}`,
                  });
                }}
              >
                New repayment
              </Button>
              <details className="technical-details">
                <summary>Receipt, request and balance evidence</summary>
                <ObservationView value={result!} />
              </details>
            </div>
          )}
          {result && !receipt && (
            <>
              <Notice tone="bad">
                {result.reply.status === 403
                  ? "This identity cannot record repayments."
                  : result.reply.status === 409
                    ? "The request conflicts with a prior delivery. Keep the original request to retry it safely."
                    : "The payment was not accepted or could not be confirmed. Read the response before preparing a new request."}
              </Notice>
              <ObservationView value={result} />
            </>
          )}
          <details
            ref={advancedRef}
            open={advanced}
            onToggle={(e) => onAdvancedChange?.(e.currentTarget.open)}
            className="technical-details delivery-testing"
          >
            <summary>Advanced delivery testing</summary>
            <p className="form-note">
              No automatic retries. Exact retry always uses the original actor,
              amount, dates and source identity. Test buttons send actual
              requests.
            </p>
            {!draft.preparedKey && (
              <p className="form-note">
                Unsent form identity: <CopyId value={identity.key} /> · event{" "}
                <CopyId value={identity.event} />. Submitting this form is a new
                instruction. Tests below target the latest prepared delivery, if
                available.
              </p>
            )}
            <h3>
              {frozen || saved ? "Exact retry target" : "Unsent delivery"}
            </h3>
            <dl className="delivery-identities">
              <div>
                <dt>Idempotency key</dt>
                <dd>
                  <CopyId value={frozen?.key ?? saved?.key ?? identity.key} />
                </dd>
              </div>
              <div>
                <dt>Source event</dt>
                <dd>
                  <CopyId
                    value={
                      frozen?.body.external_event_id ??
                      saved?.body.external_event_id ??
                      identity.event
                    }
                  />
                </dd>
              </div>
              <div>
                <dt>Delivery actor / source</dt>
                <dd>
                  {frozen?.actor ?? saved?.actor ?? actor} /{" "}
                  {frozen?.body.source ??
                    saved?.body.source ??
                    "studio-account"}
                </dd>
              </div>
            </dl>
            {(frozen || saved) && (
              <Json
                label="Original retry payload, actor and key"
                value={frozen || saved}
              />
            )}
            <div className="form-actions">
              <Button
                variant="secondary"
                disabled={busy || !(frozen || saved)}
                onClick={() => void testDelivery("retry")}
              >
                Retry identical request
              </Button>
              <Button
                variant="secondary"
                disabled={busy || verifiedKey !== (frozen || saved)?.key}
                onClick={() => void testDelivery("conflict")}
              >
                Test same-key conflict
              </Button>
              <Button
                variant="secondary"
                disabled={busy || verifiedKey !== (frozen || saved)?.key}
                onClick={() => void testDelivery("alias")}
              >
                Test source alias
              </Button>
              <Button
                variant="secondary"
                disabled={busy || !(frozen || saved)}
                onClick={() => void testDelivery("auditor")}
              >
                Test auditor denial
              </Button>
            </div>
            {testResult && <ObservationView value={testResult} />}
          </details>
          {frozen && !result && (
            <Json label="Prepared request identity" value={frozen} />
          )}
        </Dialog.Content>
      </Portal>
    </Dialog.Root>
  );
}
