"use client";
import Link from "next/link";
import * as Tabs from "@radix-ui/react-tabs";
import { useRouter, useSearchParams } from "next/navigation";
import { useSelectedLoan } from "./loan-picker";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStudio, UUID_PATTERN } from "@/lib/session";
import { ErrorState, Loading, PageHeading, ButtonLink } from "./ui";
import { JournalList, ReceiptsTable } from "./records";
import { AuditViewer } from "./audit-viewer";
import { LoanContext } from "./loan-context";
export function Activity() {
  const { actor } = useStudio();
  const id = useSelectedLoan();
  const search = useSearchParams();
  const router = useRouter();
  const tab = ["journals", "repayments", "audit"].includes(
    search.get("view") ?? "",
  )
    ? search.get("view")!
    : "journals";
  const setTab = (value: string) => {
    const p = new URLSearchParams(search);
    p.set("view", value);
    router.replace("/activity?" + p.toString(), { scroll: false });
  };
  const valid = UUID_PATTERN.test(id);
  const ledger = useQuery({
    queryKey: ["ledger", id, actor],
    queryFn: () => api.ledger(id, actor),
    enabled: valid,
  });
  const receipts = useQuery({
    queryKey: ["receipts", id, actor],
    queryFn: () => api.receipts(id, actor),
    enabled: valid,
  });
  return (
    <>
      <PageHeading
        eyebrow=""
        title="Activity"
        action={
          valid ? (
            <ButtonLink href={`/loans/${id}`}>Open loan account</ButtonLink>
          ) : undefined
        }
      >
        Follow the working account’s financial activity, or review the
        authorized audit log.
      </PageHeading>
      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List className="tab-list" aria-label="Activity records">
          <Tabs.Trigger className="tab-trigger" value="journals">
            Journals
          </Tabs.Trigger>
          <Tabs.Trigger className="tab-trigger" value="repayments">
            Repayments
          </Tabs.Trigger>
          <Tabs.Trigger className="tab-trigger" value="audit">
            Global audit log
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="journals">
          {!valid ? (
            <p>
              Choose a working account from{" "}
              <Link href="/loans" className="text-link">
                Loans
              </Link>{" "}
              to see its actual posted journals.
            </p>
          ) : (
            <>
              <LoanContext id={id} />
              {ledger.isPending ? (
                <Loading />
              ) : ledger.isError ? (
                <ErrorState error={ledger.error} />
              ) : (
                <JournalList journals={ledger.data} />
              )}
            </>
          )}
        </Tabs.Content>
        <Tabs.Content value="repayments">
          {!valid ? (
            <p>
              Choose a working account from{" "}
              <Link href="/loans" className="text-link">
                Loans
              </Link>{" "}
              to see its received payments.
            </p>
          ) : (
            <>
              <LoanContext id={id} />
              {receipts.isPending ? (
                <Loading />
              ) : receipts.isError ? (
                <ErrorState error={receipts.error} />
              ) : (
                <ReceiptsTable receipts={receipts.data} />
              )}
            </>
          )}
        </Tabs.Content>
        <Tabs.Content value="audit">
          <AuditViewer embedded />
        </Tabs.Content>
      </Tabs.Root>
    </>
  );
}
