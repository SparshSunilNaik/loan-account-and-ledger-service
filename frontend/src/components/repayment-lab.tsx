"use client";
import { useState } from "react";
import { rememberDelivery, useDelivery } from "@/lib/delivery-context";
import { useQueryClient } from "@tanstack/react-query";
import {
  errorMessage,
  observeRepayment,
  api,
  type Attempt,
  type Observation,
} from "@/lib/api";
import { MAX_PAISE, rupeesToPaise } from "@/lib/money";
import { useStudio, UUID_PATTERN } from "@/lib/session";
import { actors, type Actor } from "@/lib/types";
import { LoanPicker, useSelectedLoan } from "./loan-picker";
import { LoanContext } from "./loan-context";
import { ObservationView } from "./observation";
import { Button, Field, Notice } from "./ui";
import { TerminalSquare } from "lucide-react";
export function RepaymentLab() {
  const loanId = useSelectedLoan();
  const saved = useDelivery(loanId);
  const { actor } = useStudio();
  const cache = useQueryClient();
  const [last, setLast] = useState<Attempt>();
  const frozen = last?.loanId === loanId ? last : saved;
  const [successful, setSuccessful] = useState(false);
  const [results, setResults] = useState<Observation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selectedResult, setSelectedResult] = useState(0);
  async function run(attempt: Attempt, name: string, freeze = false) {
    setBusy(true);
    setError("");
    if (freeze) {
      setLast(attempt);
      rememberDelivery(attempt);
      setSuccessful(false);
    }
    try {
      const result = await observeRepayment(attempt, name);
      setResults((r) => [result, ...r]);
      setSelectedResult(0);
      if (
        freeze ||
        (frozen &&
          attempt.key === frozen.key &&
          JSON.stringify(attempt.body) === JSON.stringify(frozen.body))
      )
        setSuccessful(result.reply.ok);
      await cache.invalidateQueries();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Unable to observe backend records; no repayment sent.",
      );
    } finally {
      setBusy(false);
    }
  }
  function fields(form: HTMLFormElement): Attempt {
    const f = new FormData(form);
    const occurred = String(f.get("occurred"));
    const date = new Date(occurred);
    if (
      !occurred ||
      Number.isNaN(date.valueOf()) ||
      !/(Z|[+-]\d{2}:\d{2})$/.test(occurred)
    )
      throw new Error(
        "Economic timestamp must include an explicit UTC Z or timezone offset.",
      );
    return {
      loanId,
      actor: String(f.get("actor")) as Actor,
      key: String(f.get("key")),
      body: {
        amount_paise: rupeesToPaise(String(f.get("amount"))),
        source: String(f.get("source")),
        external_event_id: String(f.get("event")),
        occurred_at: date.toISOString(),
        business_date: String(f.get("date")),
      },
    };
  }
  return (
    <>
      {!UUID_PATTERN.test(loanId) ? (
        <LoanPicker id={loanId} route="/testing" />
      ) : (
        <LoanContext id={loanId} />
      )}
      {frozen && (
        <Notice>
          Prepared delivery available from this account. Retry preserves its
          original actor and full payload; it may or may not have posted. The
          result is verified against actual receipts and journals.
        </Notice>
      )}
      <div className="transaction-workstation">
        <section className="transaction-input">
          <div className="workstation-section-heading">
            <h2>Payment instruction</h2>
            <span>INR · UTC processing</span>
          </div>
          <form
            className="payment-form"
            key={`${loanId}-${saved?.key ?? "new"}`}
            onSubmit={(e) => {
              e.preventDefault();
              try {
                void run(fields(e.currentTarget), "Repayment delivery", true);
              } catch (e) {
                setError(e instanceof Error ? e.message : "Invalid input");
              }
            }}
          >
            <div className="form-grid">
              <Field label="Amount (INR)">
                <input
                  name="amount"
                  inputMode="decimal"
                  defaultValue={
                    frozen
                      ? `${BigInt(frozen.body.amount_paise) / 100n}.${String(BigInt(frozen.body.amount_paise) % 100n).padStart(2, "0")}`
                      : "10.00"
                  }
                  required
                />
              </Field>
              <Field
                label="Economic occurred_at"
                hint="ISO 8601 with explicit timezone"
              >
                <input
                  name="occurred"
                  defaultValue={
                    frozen?.body.occurred_at ?? "2026-01-31T10:00:00Z"
                  }
                  required
                />
              </Field>
              <Field label="Processing business date (UTC)">
                <input
                  name="date"
                  type="date"
                  defaultValue={frozen?.body.business_date ?? "2026-01-31"}
                  required
                />
              </Field>
              <Field label="Source">
                <input
                  name="source"
                  defaultValue={frozen?.body.source ?? "studio"}
                  required
                  maxLength={100}
                />
              </Field>
              <Field label="External event ID">
                <input
                  name="event"
                  defaultValue={
                    frozen?.body.external_event_id ??
                    "studio-event-" + loanId.slice(0, 8)
                  }
                  required
                  maxLength={200}
                />
              </Field>
              <Field label="Idempotency key">
                <input
                  name="key"
                  defaultValue={
                    frozen?.key ?? "studio-key-" + loanId.slice(0, 8)
                  }
                  required
                  maxLength={200}
                />
              </Field>
              <Field
                label="Delivery actor"
                hint="Development-only impersonation"
              >
                <select name="actor" defaultValue={frozen?.actor ?? actor}>
                  {actors.map((a) => (
                    <option key={a}>{a}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="form-actions">
              <Button busy={busy} disabled={!UUID_PATTERN.test(loanId)}>
                Submit repayment
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={busy || !frozen}
                onClick={() => frozen && void run(frozen, "Exact frozen retry")}
              >
                Retry identical request
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={busy || !frozen}
                onClick={() => {
                  if (frozen)
                    void run(
                      { ...frozen, key: `alias-${crypto.randomUUID()}` },
                      "Source-event alias · new key, same financial identity",
                    );
                }}
              >
                Test source alias
              </Button>
            </div>
            <div className="form-actions">
              <Button
                type="button"
                variant="quiet"
                disabled={busy}
                onClick={(e) => {
                  const form = e.currentTarget.form;
                  if (!form) return;
                  for (const name of ["event", "key"]) {
                    const input = form.elements.namedItem(name);
                    if (input instanceof HTMLInputElement)
                      input.value = `studio-${crypto.randomUUID()}`;
                  }
                }}
              >
                New delivery identifiers
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={busy || !frozen || !successful}
                onClick={() => {
                  if (frozen)
                    void run(
                      {
                        ...frozen,
                        body: {
                          ...frozen.body,
                          amount_paise: Number(
                            BigInt(frozen.body.amount_paise) +
                              (BigInt(frozen.body.amount_paise) === MAX_PAISE
                                ? -1n
                                : 1n),
                          ),
                        },
                      },
                      "Same key · modified amount",
                    );
                }}
              >
                Test same-key conflict
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={busy || !UUID_PATTERN.test(loanId)}
                onClick={(e) => {
                  const form = e.currentTarget.form;
                  if (!form) return;
                  try {
                    const a = fields(form);
                    void run(
                      {
                        ...a,
                        actor: "demo-auditor",
                        key: crypto.randomUUID(),
                        body: {
                          ...a.body,
                          external_event_id: crypto.randomUUID(),
                        },
                      },
                      "Auditor mutation attempt",
                    );
                  } catch (e) {
                    setError(String(e));
                  }
                }}
              >
                Test auditor denial
              </Button>
              <Button
                type="button"
                variant="danger"
                disabled={busy || !UUID_PATTERN.test(loanId)}
                onClick={async (e) => {
                  const form = e.currentTarget.form;
                  if (!form) return;
                  setError("");
                  setBusy(true);
                  try {
                    const a = fields(form);
                    const [b, s] = await Promise.all([
                      api.balance(loanId, a.actor),
                      api.schedule(loanId, a.actor),
                    ]);
                    const upper =
                      BigInt(b.total_posted_receivables_paise) +
                      s.reduce(
                        (sum, r) => sum + BigInt(r.interest_due_paise),
                        0n,
                      );
                    if (upper >= MAX_PAISE)
                      throw new Error(
                        "Cannot guarantee an overpayment within the API amount bound for this loan. Use a smaller fresh test loan.",
                      );
                    await run(
                      {
                        ...a,
                        key: crypto.randomUUID(),
                        body: {
                          ...a.body,
                          amount_paise: Number(MAX_PAISE),
                          external_event_id: crypto.randomUUID(),
                        },
                      },
                      "Overpayment attempt · maximum valid amount",
                    );
                  } catch (e) {
                    setError(String(e));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Attempt overpayment
              </Button>
            </div>
            <p className="form-note payment-footnote">
              Retry keeps the original actor, key and payload, even after a
              timeout. Test actions send real requests. Current receivables are
              not a future payoff quote.
            </p>
          </form>
          {error && <Notice tone="bad">{error}</Notice>}
        </section>
        <aside className="transaction-results" aria-live="polite">
          <div className="workstation-section-heading">
            <h2>Delivery result</h2>
            <span>
              {results.length
                ? `${results.length} observed attempts`
                : "Awaiting a request"}
            </span>
          </div>
          {results.length > 1 && (
            <div className="attempt-selector">
              <label htmlFor="result-attempt">Attempt history</label>
              <select
                id="result-attempt"
                value={selectedResult}
                onChange={(e) => setSelectedResult(Number(e.target.value))}
              >
                {results.map((r, i) => (
                  <option key={results.length - i} value={i}>
                    {results.length - i}. {r.name} ·{" "}
                    {r.reply.status ?? "No response"}
                  </option>
                ))}
              </select>
            </div>
          )}
          {results[selectedResult]?.reply.status === 409 && (
            <Notice tone="warn">
              {errorMessage(results[selectedResult].reply.body)
                .toLowerCase()
                .includes("idempotency")
                ? "This delivery key belongs to a different payload. Retry the original request, or use New delivery identifiers for a genuinely new payment."
                : "A financial conflict prevented this operation. Inspect the actual response and keep the original delivery evidence."}
            </Notice>
          )}
          {results[selectedResult] ? (
            <ObservationView value={results[selectedResult]} />
          ) : (
            <div className="result-empty">
              <TerminalSquare size={25} strokeWidth={1.3} />
              <h3>Ready to receive a response</h3>
              <p>
                The actual HTTP result, receipt identifiers and before / after
                balances will appear here.
              </p>
              <div className="result-empty-example">
                <span>Request</span>
                <span>Receipt + journal</span>
                <span>Ledger verification</span>
              </div>
            </div>
          )}
        </aside>
      </div>
      <p className="page-note">
        Due interest is recognized atomically before allocation. Future interest
        is never collected early. Balances always come from posted ledger
        entries.
      </p>
    </>
  );
}
