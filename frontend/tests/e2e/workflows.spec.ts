import { test, expect } from "@playwright/test";
import {
  createAPI,
  officer,
  manager,
  auditor,
  getJSON,
  makeLoanUI,
  disburseUI,
  capture,
} from "./helpers";
test("guided demo posts once, verifies retry, and keeps the account selected", async ({
  page,
  request,
}) => {
  await page.goto("/testing?view=demo");
  const create = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/backend/loans") && r.request().method() === "POST",
  );
  for (const name of [
    "Create borrower",
    "Create loan",
    "Inspect schedule",
    "Disburse loan",
    "Post partial repayment",
    "Retry identical delivery",
    "Verify financial records",
    "Verify audit trail",
  ])
    await page.getByRole("button", { name, exact: true }).click();
  await expect(page.getByText(/Walkthrough complete\./)).toBeVisible();
  await expect(
    page.getByText(
      "Existing receipt and journal verified — original response reused.",
      { exact: true },
    ),
  ).toBeVisible();
  const id = (await (await create).json()).id;
  await expect(page.getByLabel("Working account")).toHaveValue(id);
  expect(await getJSON(request, `/loans/${id}/repayments`)).toHaveLength(1);
  await capture(
    page,
    process.env.STUDIO_CAPTURE_ROOT ?? "test-results/screenshots",
    "guided-demo",
  );
});
test("RBAC, atomic overpayment rejection, journal reconciliation and audit attribution", async ({
  page,
  request,
}) => {
  const loan = await createAPI(request);
  expect(
    (
      await request.post(`/api/backend/loans/${loan.id}/disburse`, {
        headers: officer,
        data: { business_date: "2026-01-01" },
      })
    ).status(),
  ).toBe(403);
  expect(
    (
      await request.post(`/api/backend/loans/${loan.id}/disburse`, {
        headers: manager,
        data: { business_date: "2026-01-01" },
      })
    ).status(),
  ).toBe(201);
  expect(
    (
      await request.post(`/api/backend/loans/${loan.id}/disburse`, {
        headers: manager,
        data: { business_date: "2026-01-01" },
      })
    ).status(),
  ).toBe(409);
  await page.goto(`/loans/${loan.id}`);
  await page.getByLabel("Active demo identity").selectOption("demo-auditor");
  await expect(
    page.getByRole("button", { name: "Record repayment", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Active demo identity").selectOption("demo-officer");
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Testing", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Test auditor denial", exact: true })
    .click();
  await expect(page.getByText("HTTP 403", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Attempt overpayment", exact: true })
    .click();
  await expect(page.getByText("HTTP 400", { exact: true })).toBeVisible();
  expect(await getJSON(request, `/loans/${loan.id}/repayments`)).toHaveLength(
    0,
  );
  expect(await getJSON(request, `/loans/${loan.id}/balance`)).toMatchObject({
    principal_receivable_paise: 10000,
    interest_receivable_paise: 0,
    penalty_receivable_paise: 0,
  });
  await page
    .getByRole("button", { name: "Submit repayment", exact: true })
    .click();
  await expect(
    page.getByText("New receipt and journal observed in backend records.", {
      exact: true,
    }),
  ).toBeVisible();
  const receipts = await getJSON(request, `/loans/${loan.id}/repayments`);
  expect(receipts).toHaveLength(1);
  const ledger = await getJSON(request, `/loans/${loan.id}/ledger`);
  expect(ledger).toHaveLength(3);
  for (const j of ledger) {
    const debit = j.entries
      .filter((e: { direction: string }) => e.direction === "debit")
      .reduce(
        (s: bigint, e: { amount_paise: number }) => s + BigInt(e.amount_paise),
        0n,
      );
    const credit = j.entries
      .filter((e: { direction: string }) => e.direction === "credit")
      .reduce(
        (s: bigint, e: { amount_paise: number }) => s + BigInt(e.amount_paise),
        0n,
      );
    expect(debit).toBe(credit);
  }
  await page.goto("/activity?view=audit");
  await expect(page.getByText(/HTTP 403/)).toBeVisible();
  await page.getByLabel("Active demo identity").selectOption("demo-auditor");
  await page.getByRole("table").waitFor();
  await page
    .getByRole("button", { name: /Inspect audit event/ })
    .first()
    .click();
  await expect(
    page.getByRole("dialog").getByText("Recorded metadata", { exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const records = [];
  for (let offset = 0; offset < 5000; offset += 500) {
    const r = await request.get(
      `/api/backend/audit-events?limit=500&offset=${offset}`,
      { headers: auditor },
    );
    expect(r.status()).toBe(200);
    const rows = await r.json();
    records.push(...rows);
    if (rows.length < 500) break;
  }
  expect(
    records.some(
      (e) =>
        e.action === "repayment.posted" &&
        e.entity_id === receipts[0].id &&
        e.actor_user_id === "20000000-0000-0000-0000-000000000001",
    ),
  ).toBe(true);
});
test("lost response after commit survives reload and edited form; exact retry creates no second receipt", async ({
  page,
  request,
}) => {
  const loan = await makeLoanUI(page, "Invented Timeout Borrower");
  await disburseUI(page);
  let receiptId: string | undefined;
  await page.route(
    `**/api/backend/loans/${loan.id}/repayments`,
    async (route) => {
      if (route.request().method() !== "POST" || receiptId) {
        await route.continue();
        return;
      }
      const r = await route.fetch();
      expect(r.status()).toBe(201);
      receiptId = (await r.json()).id;
      await route.abort("failed");
    },
  );
  await page
    .getByRole("button", { name: "Record repayment", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Amount received (INR)").fill("10.00");
  await dialog.getByLabel("Payment time (UTC)").fill("2026-01-31T10:00");
  await dialog.getByLabel("Processing date (UTC)").fill("2026-01-31");
  await dialog
    .getByRole("button", { name: "Record repayment", exact: true })
    .click();
  await expect(
    page.getByText("No HTTP response", { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByLabel("Amount received (INR)")).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: "Close repayment" }),
  ).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Testing", exact: true })
    .click();
  await page.waitForURL(/\/testing/);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Retry identical request", exact: true }),
  ).toBeEnabled();
  await page.getByLabel("Amount (INR)", { exact: true }).fill("20.00");
  await page
    .getByRole("button", { name: "Retry identical request", exact: true })
    .click();
  await expect(
    page.getByText(
      "Existing receipt and journal verified — original response reused.",
      { exact: true },
    ),
  ).toBeVisible();
  const receipts = await getJSON(request, `/loans/${loan.id}/repayments`);
  expect(receipts).toHaveLength(1);
  expect(receipts[0]).toMatchObject({ id: receiptId, amount_paise: 1000 });
});
test("exact input validation, same-reference lookup, and proxy boundaries", async ({
  page,
  request,
}) => {
  await page.goto("/new-loan");
  await page
    .getByLabel("Borrower name", { exact: true })
    .fill("Invented Validation Borrower");
  await page.getByRole("button", { name: /Continue to loan terms/ }).click();
  await page.getByLabel("Principal (INR)", { exact: true }).fill("1.005");
  await page
    .getByRole("button", { name: /Create loan & review schedule/ })
    .click();
  await expect(page.locator("#new-principal")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(page.locator(".validation-summary[role=alert]")).toBeFocused();
  expect((await request.get("/api/backend/openapi.json")).status()).toBe(404);
  expect(
    (
      await request.post("/api/backend/borrowers", {
        headers: { Origin: "http://untrusted.example", ...officer },
        data: {},
      })
    ).status(),
  ).toBe(403);
  expect(
    (
      await request.get("/api/backend/loan-products", {
        headers: { "X-Demo-User": "arbitrary-manager" },
      })
    ).status(),
  ).toBe(403);
  const loan = await createAPI(request);
  await page.goto("/loans");
  await page.getByText("Open a loan link", { exact: true }).click();
  await page
    .getByLabel("Loan link or ID", { exact: true })
    .fill(`http://127.0.0.1:3000/loans/${loan.id}`);
  await page.getByRole("button", { name: "Open account", exact: true }).click();
  await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
  await page.goto("/loans");
  await expect(
    page.getByRole("link", {
      name: "Invented API Fixture Borrower",
      exact: true,
    }),
  ).toBeVisible();
});
