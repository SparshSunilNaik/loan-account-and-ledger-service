"use client";
import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { session, UUID_PATTERN, useStudio } from "@/lib/session";
import { Button, Field, Notice } from "./ui";
export function useSelectedLoan() {
  const search = useSearchParams();
  const state = useStudio();
  const linked = search.get("loanId");
  useEffect(() => {
    if (linked && UUID_PATTERN.test(linked) && linked !== state.selectedLoan)
      session.select(linked);
  }, [linked, state.selectedLoan]);
  return linked ?? state.selectedLoan;
}
export function LoanPicker({ id, route }: { id: string; route: string }) {
  const { recent } = useStudio();
  const router = useRouter();
  const select = (value: string) => {
    session.select(value);
    router.replace(`${route}?loanId=${encodeURIComponent(value)}`);
  };
  return (
    <>
      <form
        key={id}
        className="loan-picker"
        onSubmit={(e) => {
          e.preventDefault();
          const value = String(
            new FormData(e.currentTarget).get("loanId") ?? "",
          ).trim();
          if (UUID_PATTERN.test(value)) select(value);
        }}
      >
        <Field label="Loan UUID">
          <input
            name="loanId"
            defaultValue={id}
            placeholder="Paste a loan UUID"
            pattern={"[0-9a-fA-F\\-]{36}"}
            required
            aria-label="Loan UUID"
          />
        </Field>
        {recent.length > 0 && (
          <Field label="Recent in this session">
            <select
              aria-label="Select a recently visited loan"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) select(e.target.value);
              }}
            >
              <option value="">Choose a visited loan…</option>
              {recent.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.reference}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Button type="submit" variant="secondary">
          Open loan
        </Button>
      </form>
      {id && !UUID_PATTERN.test(id) && (
        <Notice tone="bad">
          Enter a valid loan UUID. No query was sent for this identifier.
        </Notice>
      )}
    </>
  );
}
