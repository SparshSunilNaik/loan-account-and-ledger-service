import React from "react";
import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BalanceCards, ReplyView, ScheduleTable } from "@/components/ui";
import type { ScheduleRow } from "@/lib/types";
it("unknown balances are dashes, never fabricated zero balances", () => {
  render(<BalanceCards />);
  expect(screen.getAllByText("—")).toHaveLength(3);
  expect(screen.queryByText("₹0.00")).not.toBeInTheDocument();
});
it("renders independently known schedule components in INR", () => {
  const rows = [
    {
      id: "row",
      loan_id: "loan",
      instalment_number: 1,
      due_date: "2026-01-31",
      principal_due_paise: 4975,
      interest_due_paise: 100,
    },
  ] as ScheduleRow[];
  render(<ScheduleTable rows={rows} />);
  expect(screen.getByText("₹49.75")).toBeInTheDocument();
  expect(screen.getByText("₹1.00")).toBeInTheDocument();
  expect(screen.getByText("₹50.75")).toBeInTheDocument();
});
it("labels proxy failures separately from actual backend statuses", () => {
  render(
    <ReplyView
      reply={{
        ok: false,
        status: 503,
        origin: "proxy",
        body: { detail: "Backend unavailable", studio_proxy: true },
        rawText: "",
      }}
    />,
  );
  expect(screen.getByText("HTTP 503")).toBeInTheDocument();
  expect(screen.getByText(/proxy result/)).toBeInTheDocument();
});
