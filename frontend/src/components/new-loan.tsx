"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Check, ArrowLeft, ArrowRight } from "lucide-react";
import { api, type Reply } from "@/lib/api";
import { inr, percent, rupeesToPaise } from "@/lib/money";
import { session, useStudio } from "@/lib/session";
import type { Borrower, Loan } from "@/lib/types";
import {
  Button,
  ErrorState,
  Field,
  Loading,
  Notice,
  PageHeading,
  ReplyView,
} from "./ui";
import { LoanDetail } from "./loan-detail";
export function NewLoan({ active = true }: { active?: boolean }) {
  const { actor } = useStudio();
  const router = useRouter();
  const products = useQuery({
    queryKey: ["products", actor],
    queryFn: () => api.products(actor),
  });
  const [step, setStep] = useState(0);
  const [borrower, setBorrower] = useState<Borrower>();
  const [loan, setLoan] = useState<Loan>();
  const [reply, setReply] = useState<Reply>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [amountError, setAmountError] = useState("");
  const [selected, setSelected] = useState("");
  const [draft, setDraft] = useState({
    name: "",
    phone: "",
    principal: "10000.00",
    periods: "12",
    date: "2026-12-01",
  });
  const borrowerRef = useRef("");
  const loanRef = useRef("");
  const errorRef = useRef<HTMLDivElement>(null);
  const product = products.data?.find(
    (p) =>
      p.id ===
      (selected || products.data?.find((p) => p.code === "PERSONAL_EMI")?.id),
  );
  const permitted = actor !== "demo-auditor";
  function fail(message: string) {
    setError(message);
    setTimeout(() => errorRef.current?.focus(), 0);
  }
  if (step === 2 && loan)
    return active ? (
      <div className="originated-account">
        <div className="origination-complete" role="status">
          <span>Loan created. Your schedule is ready.</span>
          <Button
            variant="quiet"
            disabled={busy}
            onClick={() => {
              setStep(0);
              setLoan(undefined);
              setBorrower(undefined);
              setReply(undefined);
              setError("");
              borrowerRef.current = "";
              loanRef.current = "";
              setDraft({
                name: "",
                phone: "",
                principal: "10000.00",
                periods: "12",
                date: "2026-12-01",
              });
            }}
          >
            New application
          </Button>
          <Link href={`/loans/${loan.id}`} className="text-link">
            Open loan account
          </Link>
        </div>
        <LoanDetail key={loan.id} id={loan.id} />
      </div>
    ) : null;
  return (
    <>
      <PageHeading title="New loan" eyebrow="">
        A borrower, clear terms, and a schedule you can review before
        disbursement.
      </PageHeading>
      <div className="origination-progress" aria-label="Loan creation progress">
        {["Borrower", "Loan terms", "Review schedule"].map((name, i) => (
          <span
            key={name}
            className={step === i ? "current" : step > i ? "complete" : ""}
            aria-current={step === i ? "step" : undefined}
          >
            {step > i ? <Check size={16} aria-hidden="true" /> : null}
            {name}
          </span>
        ))}
      </div>
      {!permitted && (
        <Notice tone="warn">
          Auditor is read-only. Choose demo-officer or demo-manager to create a
          loan.
        </Notice>
      )}
      <div className="new-loan-layout">
        <div className="wizard-form">
          {error && (
            <div
              ref={errorRef}
              tabIndex={-1}
              className="validation-summary"
              role="alert"
            >
              <h2>Unable to continue</h2>
              <p>{error}</p>
              {amountError && (
                <a href="#new-principal">Check the principal amount</a>
              )}
            </div>
          )}
          {step === 0 && (
            <>
              <h2>Who is borrowing?</h2>
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const name = String(f.get("name")).trim(),
                    phone = String(f.get("phone")).trim();
                  setDraft((v) => ({ ...v, name, phone }));
                  if (!name) {
                    fail("Enter an invented borrower name.");
                    return;
                  }
                  if (
                    borrower?.full_name === name &&
                    (borrower.phone ?? "") === phone
                  ) {
                    setStep(1);
                    return;
                  }
                  if (borrower) borrowerRef.current = "";
                  setBusy(true);
                  setError("");
                  try {
                    borrowerRef.current ||= `STUDIO-B-${crypto.randomUUID()}`;
                    const r = await api.createBorrower(
                      {
                        full_name: name,
                        phone: phone || null,
                        external_reference: borrowerRef.current,
                      },
                      actor,
                    );
                    setReply(r);
                    if (r.ok) {
                      setBorrower(r.body);
                      setStep(1);
                    } else
                      fail(
                        "The borrower was not confirmed. Review the response below before retrying.",
                      );
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <Field label="Borrower name">
                  <input
                    name="name"
                    autoComplete="off"
                    value={draft.name}
                    onChange={(e) =>
                      setDraft((v) => ({ ...v, name: e.target.value }))
                    }
                    required
                    maxLength={200}
                    placeholder="Use an invented name"
                  />
                </Field>
                <Field label="Phone (optional)">
                  <input
                    name="phone"
                    type="tel"
                    value={draft.phone}
                    onChange={(e) =>
                      setDraft((v) => ({ ...v, phone: e.target.value }))
                    }
                    pattern="\+?[0-9]{7,15}"
                    placeholder="7–15 digits"
                  />
                </Field>
                <div className="form-actions">
                  <Button busy={busy} disabled={!permitted}>
                    Continue to loan terms <ArrowRight size={16} />
                  </Button>
                </div>
              </form>
              <details className="existing-borrower">
                <summary>Use an existing borrower instead</summary>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setBusy(true);
                    setError("");
                    try {
                      const b = await api.borrower(
                        String(
                          new FormData(e.currentTarget).get("borrowerId"),
                        ).trim(),
                        actor,
                      );
                      setBorrower(b);
                      setStep(1);
                    } catch (e) {
                      fail(
                        e instanceof Error
                          ? e.message
                          : "Borrower could not be loaded",
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <Field label="Existing borrower ID">
                    <input name="borrowerId" required />
                  </Field>
                  <Button variant="secondary" busy={busy}>
                    Use borrower
                  </Button>
                </form>
              </details>
            </>
          )}
          {step === 1 && (
            <>
              <div className="wizard-section-heading">
                <h2>Choose the loan terms</h2>
                <Button
                  variant="quiet"
                  onClick={() => {
                    setError("");
                    setStep(0);
                  }}
                >
                  Change borrower
                </Button>
              </div>
              {products.isPending ? (
                <Loading />
              ) : products.isError ? (
                <ErrorState error={products.error} />
              ) : (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setError("");
                    setAmountError("");
                    const f = new FormData(e.currentTarget);
                    const values = {
                      principal: String(f.get("principal")),
                      periods: String(f.get("periods")),
                      date: String(f.get("date")),
                    };
                    setDraft((v) => ({ ...v, ...values }));
                    let principal: number;
                    try {
                      principal = rupeesToPaise(values.principal);
                    } catch (e) {
                      const msg =
                        e instanceof Error
                          ? e.message
                          : "Enter a valid rupee amount";
                      setAmountError(msg);
                      fail(msg);
                      return;
                    }
                    if (!product || !borrower) {
                      fail("Select a product and borrower first.");
                      return;
                    }
                    const tenure = Number(values.periods);
                    if (
                      !/^\d+$/.test(values.periods) ||
                      tenure < 1 ||
                      tenure > 600
                    ) {
                      fail(
                        "Tenure must be a whole number from 1 to 600 instalments.",
                      );
                      return;
                    }
                    setBusy(true);
                    try {
                      loanRef.current ||= `LC-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
                      const r = await api.createLoan(
                        {
                          external_reference: loanRef.current,
                          borrower_id: borrower.id,
                          product_id: product.id,
                          principal_paise: principal,
                          tenure_periods: tenure,
                          first_due_date: values.date,
                        },
                        actor,
                      );
                      setReply(r);
                      if (r.ok) {
                        setLoan(r.body);
                        session.remember(r.body.id, r.body.external_reference);
                        setStep(2);
                        router.replace(`/loans/${r.body.id}`);
                      } else
                        fail(
                          "The loan was not confirmed. Review the actual response before another attempt.",
                        );
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <div className="mobile-product-select">
                    <Field label="Loan product">
                      <select
                        value={product?.id ?? ""}
                        onChange={(e) => setSelected(e.target.value)}
                      >
                        <option value="" disabled>
                          Choose a product
                        </option>
                        {products.data
                          .filter((p) => p.active)
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                      </select>
                    </Field>
                    {product && (
                      <p>
                        {percent(product.annual_rate)} annual nominal ·{" "}
                        {product.frequency} ·{" "}
                        {product.interest_method === "flat"
                          ? "Flat rate"
                          : "Reducing balance"}
                      </p>
                    )}
                  </div>
                  <fieldset className="product-options">
                    <legend>Loan product</legend>
                    {products.data
                      .filter((p) => p.active)
                      .map((p) => (
                        <label
                          key={p.id}
                          className={
                            product?.id === p.id
                              ? "product-option selected"
                              : "product-option"
                          }
                        >
                          <input
                            type="radio"
                            name="product"
                            value={p.id}
                            checked={product?.id === p.id}
                            onChange={() => setSelected(p.id)}
                          />
                          <span>
                            <strong>{p.name}</strong>
                            <small>
                              {percent(p.annual_rate)} annual nominal ·{" "}
                              {p.frequency} ·{" "}
                              {p.interest_method === "flat"
                                ? "Flat rate"
                                : "Reducing balance"}
                            </small>
                          </span>
                        </label>
                      ))}
                  </fieldset>
                  <Field label="Principal (INR)">
                    <input
                      id="new-principal"
                      name="principal"
                      inputMode="decimal"
                      value={draft.principal}
                      onChange={(e) =>
                        setDraft((v) => ({ ...v, principal: e.target.value }))
                      }
                      aria-invalid={!!amountError}
                      aria-describedby={
                        amountError ? "principal-error" : undefined
                      }
                      required
                    />
                    {amountError && (
                      <span id="principal-error" className="field-error">
                        {amountError}
                      </span>
                    )}
                  </Field>
                  <div className="form-grid">
                    <Field label="Tenure (instalments)">
                      <input
                        name="periods"
                        type="number"
                        min={1}
                        max={600}
                        value={draft.periods}
                        onChange={(e) =>
                          setDraft((v) => ({ ...v, periods: e.target.value }))
                        }
                        required
                      />
                    </Field>
                    <Field label="First due date (UTC)">
                      <input
                        name="date"
                        type="date"
                        min="1900-01-01"
                        max="2100-12-31"
                        value={draft.date}
                        onChange={(e) =>
                          setDraft((v) => ({ ...v, date: e.target.value }))
                        }
                        required
                      />
                    </Field>
                  </div>
                  <p className="form-note">
                    This creates the loan and its contractual schedule. No funds
                    are posted until a manager disburses it.
                  </p>
                  <div className="form-actions">
                    <Button busy={busy} disabled={!permitted || !product}>
                      Create loan & review schedule <ArrowRight size={16} />
                    </Button>
                  </div>
                </form>
              )}
            </>
          )}
          {reply && !reply.ok && <ReplyView reply={reply} />}
        </div>
        <aside className="wizard-summary">
          <h2>{borrower ? "Your borrower" : "Before you start"}</h2>
          {borrower ? (
            <>
              <div className="borrower-avatar">
                {borrower.full_name.slice(0, 1)}
              </div>
              <h3>{borrower.full_name}</h3>
              <span>{borrower.phone ?? "No phone supplied"}</span>
            </>
          ) : (
            <p>
              Use invented details. Create the account first; disbursement and
              repayment happen together in its workspace.
            </p>
          )}
          {product && step > 0 && (
            <dl>
              <div>
                <dt>Product</dt>
                <dd>{product.name}</dd>
              </div>
              <div>
                <dt>Annual nominal rate</dt>
                <dd>{percent(product.annual_rate)}</dd>
              </div>
              <div>
                <dt>Repayment method</dt>
                <dd>
                  {product.interest_method === "flat"
                    ? "Flat rate"
                    : "Reducing balance"}
                </dd>
              </div>
              {loan && (
                <div>
                  <dt>Original principal</dt>
                  <dd>{inr(loan.principal_paise)}</dd>
                </div>
              )}
            </dl>
          )}
          <p>
            INR only. Values convert exactly to integer paise. The backend
            generates every instalment.
          </p>
          <Link href="/loans" className="text-link">
            <ArrowLeft size={14} />
            Back to loans
          </Link>
        </aside>
      </div>
    </>
  );
}
