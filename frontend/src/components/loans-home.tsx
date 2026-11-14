"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Plus, Search, ArrowUpRight, WalletCards } from "lucide-react";
import { api } from "@/lib/api";
import { session, useStudio, UUID_PATTERN } from "@/lib/session";
import { inr, percent } from "@/lib/money";
import {
  Badge,
  Button,
  ButtonLink,
  ErrorState,
  Field,
  Loading,
  PageHeading,
  Notice,
} from "./ui";
export function LoansHome() {
  const { recent, actor } = useStudio();
  const router = useRouter();
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const records = useQueries({
    queries: recent.map((r) => ({
      queryKey: ["known-loan", r.id, actor],
      queryFn: async () => {
        const loan = await api.loan(r.id, actor);
        const [borrower, balance, products] = await Promise.all([
          api.borrower(loan.borrower_id, actor),
          api.balance(r.id, actor),
          api.products(actor),
        ]);
        return {
          loan,
          borrower,
          balance,
          product: products.find((p) => p.id === loan.product_id),
        };
      },
    })),
  });
  const products = useQuery({
    queryKey: ["products", actor],
    queryFn: () => api.products(actor),
  });
  const shown = recent
    .map((r, i) => ({ r, query: records[i] }))
    .filter(({ r, query }) =>
      `${r.reference} ${query.data?.borrower.full_name ?? ""}`
        .toLowerCase()
        .includes(filter.toLowerCase()),
    );
  return (
    <>
      <PageHeading
        title="Loans"
        eyebrow=""
        action={
          recent.length ? (
            <ButtonLink href="/new-loan">
              <Plus size={18} />
              New loan
            </ButtonLink>
          ) : undefined
        }
      >
        Find an account, understand its position, and take the next action.
      </PageHeading>
      {products.isError && (
        <ErrorState
          error={products.error}
          retry={() => void products.refetch()}
        />
      )}
      <div className="discovery-bar">
        <label className="local-search">
          <Search size={18} aria-hidden="true" />
          <input
            aria-label="Filter browser-known loans"
            placeholder="Find a known name or account"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
        <details className="open-reference">
          <summary>Open a loan link</summary>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setError("");
              const input = String(
                new FormData(e.currentTarget).get("id"),
              ).trim();
              let id = input;
              if (!UUID_PATTERN.test(input)) {
                try {
                  const link = new URL(input, window.location.origin);
                  const match = link.pathname.match(
                    /^\/loans\/([0-9a-f-]{36})$/i,
                  );
                  id = match?.[1] ?? "";
                } catch {
                  id = "";
                }
              }
              if (!UUID_PATTERN.test(id)) {
                setError(
                  "Paste a complete loan account link or its full loan ID. Short account references cannot be searched on this server.",
                );
                return;
              }
              try {
                const loan = await api.loan(id, actor);
                session.remember(id, loan.external_reference);
                router.push(`/loans/${id}`);
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Loan could not be opened",
                );
              }
            }}
          >
            <Field label="Loan link or ID">
              <input
                name="id"
                required
                placeholder="Paste an existing loan account link"
              />
            </Field>
            <Button>Open account</Button>
            {error && <Notice tone="bad">{error}</Notice>}
          </form>
        </details>
      </div>
      <div className="known-heading">
        <h2>Known in this browser</h2>
        <span>
          {recent.length} saved references. This is not the full server
          portfolio.
        </span>
      </div>
      {recent.length === 0 ? (
        <div className="first-loan">
          <WalletCards size={34} aria-hidden="true" />
          <h2>No loans known in this session.</h2>
          <p>
            Create an invented borrower and loan, or open an existing account
            using its link. It will stay available in this browser session.
          </p>
          <ButtonLink href="/new-loan">Create a loan</ButtonLink>
          <Link href="/testing?view=demo" className="text-link">
            Try the guided demonstration
          </Link>
        </div>
      ) : shown.length === 0 ? (
        <Notice>
          No known account matches this filter. Clear the text to see your saved
          references.
        </Notice>
      ) : (
        <div className="table-scroll">
          <table className="known-loans">
            <thead>
              <tr>
                <th>Borrower / account</th>
                <th>Loan product</th>
                <th>Status</th>
                <th className="numeric">Principal outstanding</th>
                <th>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map(({ r, query }) => (
                <tr key={r.id}>
                  <td>
                    <Link href={`/loans/${r.id}`} className="borrower-link">
                      {query.data?.borrower.full_name ?? r.reference}
                    </Link>
                    <span className="cell-meta">
                      {query.data ? r.reference : "Reading saved reference…"}
                    </span>
                    {query.isError && (
                      <span className="error-copy">
                        Unable to read this account
                      </span>
                    )}
                  </td>
                  <td>{query.data?.product?.name ?? "—"}</td>
                  <td>
                    <Badge
                      tone={
                        query.data?.loan.status === "disbursed"
                          ? "good"
                          : "neutral"
                      }
                    >
                      {query.data?.loan.status === "originated"
                        ? "Awaiting disbursement"
                        : (query.data?.loan.status ?? "Loading")}
                    </Badge>
                  </td>
                  <td className="numeric">
                    {query.data
                      ? inr(query.data.balance.principal_receivable_paise)
                      : "—"}
                  </td>
                  <td>
                    <Link
                      className="open-account-link"
                      href={`/loans/${r.id}`}
                      aria-label={`Open account ${query.data?.borrower.full_name ?? r.reference}`}
                    >
                      Open <ArrowUpRight size={15} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <details className="product-library">
        <summary>Available loan products</summary>
        {products.isPending ? (
          <Loading />
        ) : products.isError ? null : (
          <div className="product-library-grid">
            {products.data.map((p) => (
              <div key={p.id}>
                <h3>{p.name}</h3>
                <p>{percent(p.annual_rate)} annual nominal</p>
                <span>
                  {p.frequency} ·{" "}
                  {p.interest_method === "flat"
                    ? "Flat rate"
                    : "Reducing balance"}
                </span>
              </div>
            ))}
          </div>
        )}
      </details>
    </>
  );
}
