// Run only against a Studio instance backed by a disposable database.
import { chromium, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const baseURL = process.env.STUDIO_URL;
if (!baseURL) throw new Error("Set STUDIO_URL to a disposable Studio instance");
const output = process.env.DEMO_OUTPUT ?? "/tmp/ledgercore-demo-verification";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_EXECUTABLE ??
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
const context = await browser.newContext({
  baseURL,
  viewport: { width: 1440, height: 900 },
});
const page = await context.newPage();
const statuses = [];
const capture = (name) =>
  page.screenshot({ path: `${output}/${name}.png`, animations: "disabled" });
const get = async (path) => {
  const r = await context.request.get(`/api/backend${path}`, {
    headers: { "X-Demo-User": "demo-auditor" },
  });
  expect(r.status()).toBe(200);
  return r.json();
};
try {
  await page.goto("/new-loan");
  await page.getByLabel("Active demo identity").selectOption("demo-officer");
  await page.getByLabel("Appearance", { exact: true }).selectOption("light");
  await page
    .getByLabel("Borrower name", { exact: true })
    .fill("Nila Synthetic Recording");
  await page.getByRole("button", { name: /Continue to loan terms/ }).click();
  await page.getByRole("radio", { name: /Personal EMI Loan/ }).check();
  await page.getByLabel("Principal (INR)", { exact: true }).fill("100.00");
  await page.getByLabel("Tenure (instalments)").fill("2");
  await page.getByLabel("First due date (UTC)").fill("2026-01-31");
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/backend/loans") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: /Create loan & review schedule/ })
    .click();
  const loanResponse = await created;
  expect(loanResponse.status()).toBe(201);
  const loan = await loanResponse.json();
  await expect(page).toHaveURL(new RegExp(`/loans/${loan.id}$`));
  const schedule = await get(`/loans/${loan.id}/schedule`);
  expect(
    schedule.map((r) => [
      r.due_date,
      r.principal_due_paise,
      r.interest_due_paise,
    ]),
  ).toEqual([
    ["2026-01-31", 4975, 100],
    ["2026-02-28", 5025, 50],
  ]);
  expect(
    (await get(`/loans/${loan.id}/balance`)).principal_receivable_paise,
  ).toBe(0);
  await capture("01-schedule");
  await page.getByLabel("Active demo identity").selectOption("demo-manager");
  await page.getByLabel("Disbursement date (UTC)").fill("2026-01-01");
  await page
    .getByRole("button", { name: "Disburse loan", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Record repayment", exact: true }),
  ).toBeEnabled();
  await page.getByRole("tab", { name: "Ledger", exact: true }).click();
  await page
    .getByRole("button", { name: /^Inspect Disbursement journal / })
    .click();
  await expect(
    page.getByRole("heading", { name: "Journal details", exact: true }),
  ).toBeVisible();
  await capture("02-disbursement");
  await page
    .getByRole("button", { name: "Close inspector", exact: true })
    .click();
  await page.getByLabel("Active demo identity").selectOption("demo-officer");
  await page
    .getByRole("button", { name: "Record repayment", exact: true })
    .click();
  const form = page.getByRole("dialog");
  await form.getByLabel("Amount received (INR)").fill("10.00");
  await form.getByLabel("Payment time (UTC)").fill("2026-01-31T10:00");
  await form.getByLabel("Processing date (UTC)").fill("2026-01-31");
  const posted = page.waitForResponse(
    (r) => /\/repayments$/.test(r.url()) && r.request().method() === "POST",
  );
  await form
    .getByRole("button", { name: "Record repayment", exact: true })
    .click();
  const response = await posted;
  statuses.push(response.status());
  expect(response.status()).toBe(201);
  const receipt = await response.json();
  await expect(
    form.getByText("Received and verified", { exact: true }),
  ).toBeVisible();
  await capture("03-repayment");
  const balance = await get(`/loans/${loan.id}/balance`);
  expect(balance).toMatchObject({
    principal_receivable_paise: 9100,
    interest_receivable_paise: 0,
    penalty_receivable_paise: 0,
  });
  await page
    .getByRole("button", { name: "View posted journal in account" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Journal details", exact: true }),
  ).toBeVisible();
  await capture("04-journal");
  await page
    .getByRole("button", { name: "Close inspector", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Delivery checks", exact: true })
    .click();
  for (const [button, status] of [
    ["Retry identical request", 201],
    ["Test same-key conflict", 409],
    ["Test auditor denial", 403],
  ]) {
    const sent = page.waitForResponse(
      (r) => /\/repayments$/.test(r.url()) && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: button, exact: true }).click();
    const actual = await sent;
    statuses.push(actual.status());
    expect(actual.status()).toBe(status);
    if (button === "Retry identical request") {
      expect((await actual.json()).id).toBe(receipt.id);
      await expect(
        page.getByText(
          "Existing receipt and journal verified — original response reused.",
          { exact: true },
        ),
      ).toBeVisible();
    } else
      await expect(
        page.getByText(`HTTP ${status}`, { exact: true }),
      ).toBeVisible();
    await capture(`05-${status}-${statuses.length}`);
  }
  const repayments = await get(`/loans/${loan.id}/repayments`);
  expect(repayments).toHaveLength(1);
  expect(repayments[0].id).toBe(receipt.id);
  const ledger = await get(`/loans/${loan.id}/ledger`);
  expect(ledger).toHaveLength(3);
  for (const journal of ledger) {
    const debit = journal.entries
      .filter((e) => e.direction === "debit")
      .reduce((a, e) => a + BigInt(e.amount_paise), 0n);
    const credit = journal.entries
      .filter((e) => e.direction === "credit")
      .reduce((a, e) => a + BigInt(e.amount_paise), 0n);
    expect(debit).toBe(credit);
  }
  expect(
    receipt.allocations.map((a) => [a.component, a.amount_paise]).sort(),
  ).toEqual([
    ["interest", 100],
    ["principal", 900],
  ]);
  const posting = ledger.find((j) => j.id === receipt.journal_id);
  expect(
    posting.entries.map((e) => [e.account, e.direction, e.amount_paise]).sort(),
  ).toEqual([
    ["CASH", "debit", 1000],
    ["INTEREST_RECEIVABLE", "credit", 100],
    ["LOAN_PRINCIPAL_RECEIVABLE", "credit", 900],
  ]);
  const recognition = ledger.find((j) => j.kind === "scheduled_interest");
  expect(
    recognition.entries
      .map((e) => [e.account, e.direction, e.amount_paise])
      .sort(),
  ).toEqual([
    ["INTEREST_INCOME", "credit", 100],
    ["INTEREST_RECEIVABLE", "debit", 100],
  ]);
  expect(await get(`/loans/${loan.id}/balance`)).toEqual(balance);
  await page
    .getByRole("button", { name: "Close repayment", exact: true })
    .click();
  await page.getByLabel("Active demo identity").selectOption("demo-auditor");
  await expect(
    page.getByRole("button", { name: "Record repayment", exact: true }),
  ).toBeDisabled();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page
    .getByRole("button", { name: "repayment.posted", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Audit event", exact: true }),
  ).toBeVisible();
  await capture("06-audit");
  writeFileSync(
    `${output}/report.json`,
    JSON.stringify(
      {
        observed_at: new Date().toISOString(),
        browser: await browser.version(),
        studio_url: baseURL,
        loan_id: loan.id,
        receipt,
        schedule,
        balance,
        ledger,
        repayments,
        statuses,
        receipt_count: repayments.length,
        journal_count: ledger.length,
        all_assertions_passed: true,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(`Demo verified: ${output}/report.json`);
} finally {
  await browser.close();
}
