"use client";
import Link from "next/link";
import * as Tabs from "@radix-ui/react-tabs";
import { useRouter, useSearchParams } from "next/navigation";
import { useStudio, UUID_PATTERN } from "@/lib/session";
import { PageHeading } from "./ui";
import { RepaymentLab } from "./repayment-lab";
import { Walkthrough } from "./walkthrough";
export function Testing() {
  const { selectedLoan } = useStudio();
  const search = useSearchParams();
  const router = useRouter();
  const view = search.get("view") === "demo" ? "demo" : "requests";
  return (
    <>
      <PageHeading eyebrow="" title="Testing">
        Advanced delivery checks, with the working account and original request
        retained.
      </PageHeading>
      <Tabs.Root
        value={view}
        onValueChange={(v) => {
          const p = new URLSearchParams(search);
          p.set("view", v);
          router.replace("/testing?" + p.toString(), { scroll: false });
        }}
      >
        <Tabs.List className="tab-list" aria-label="Testing tools">
          <Tabs.Trigger value="requests" className="tab-trigger">
            Request checks
          </Tabs.Trigger>
          <Tabs.Trigger value="demo" className="tab-trigger">
            Guided demo
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="requests">
          {!UUID_PATTERN.test(selectedLoan) && (
            <p className="page-note">
              Choose a loan from{" "}
              <Link href="/loans" className="text-link">
                Loans
              </Link>
              , or open one below once. Normal repayments are recorded directly
              in the account.
            </p>
          )}
          <RepaymentLab key={selectedLoan} />
        </Tabs.Content>
        <Tabs.Content value="demo">
          <Walkthrough embedded />
        </Tabs.Content>
      </Tabs.Root>
    </>
  );
}
