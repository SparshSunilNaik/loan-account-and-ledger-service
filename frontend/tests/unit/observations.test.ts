import { expect, it } from "vitest";
import { receiptEffect, type Reply, type Snapshot } from "@/lib/api";
const reply: Reply = {
  status: 201,
  ok: true,
  body: { id: "receipt", journal_id: "journal" },
  rawText: "",
  origin: "backend",
};
const empty = { receipts: [], ledger: [] } as unknown as Snapshot;
const posted = {
  receipts: [{ id: "receipt" }],
  ledger: [{ id: "journal" }],
} as Snapshot;
it("never calls a 201 alone a new financial posting", () =>
  expect(receiptEffect(reply)).toContain("unverified"));
it("compares authoritative identifiers for new receipts and retries", () => {
  expect(receiptEffect(reply, empty, posted)).toContain(
    "New receipt and journal",
  );
  expect(receiptEffect(reply, posted, posted)).toContain(
    "original response reused",
  );
});
it("does not call inconsistent observations a successful retry", () =>
  expect(receiptEffect(reply, empty, empty)).toContain(
    "could not be reconciled",
  ));
it("does not claim rejection status proves atomicity", () =>
  expect(
    receiptEffect({ ...reply, ok: false, status: 409 }, posted, posted),
  ).toContain("status alone does not prove"));
