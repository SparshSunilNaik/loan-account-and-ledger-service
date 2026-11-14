import { expect, type Page, type APIRequestContext } from "@playwright/test";
import { mkdirSync } from "node:fs";
export const officer = { "X-Demo-User": "demo-officer" },
  manager = { "X-Demo-User": "demo-manager" },
  auditor = { "X-Demo-User": "demo-auditor" };
export async function capture(page: Page, folder: string, name: string) {
  mkdirSync(folder, { recursive: true });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: `${folder}/${name}.png`,
    animations: "disabled",
    fullPage:
      (page.viewportSize()?.width ?? 1440) > 760 &&
      !(await page.getByRole("dialog").count()),
  });
}
export async function makeLoanUI(
  page: Page,
  name: string,
  captureStage?: (name: string) => Promise<void>,
  stayInline = false,
) {
  await page.goto("/new-loan");
  await page.getByLabel("Borrower name", { exact: true }).fill(name);
  await page.getByRole("button", { name: /Continue to loan terms/ }).click();
  const mobileProduct = page.getByRole("combobox", {
    name: "Loan product",
    exact: true,
  });
  if ((page.viewportSize()?.width ?? 1440) <= 760)
    await mobileProduct.selectOption({ label: "Personal EMI Loan" });
  else await page.getByRole("radio", { name: /Personal EMI Loan/ }).check();
  await page.getByLabel("Principal (INR)", { exact: true }).fill("100.00");
  await page.getByLabel("Tenure (instalments)").fill("2");
  await page.getByLabel("First due date (UTC)").fill("2026-01-31");
  await captureStage?.("new-loan-terms");
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/backend/loans") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: /Create loan & review schedule/ })
    .click();
  const response = await created;
  expect(response.status()).toBe(201);
  const loan = await response.json();
  await expect(
    page.getByRole("cell", { name: "₹49.75", exact: true }),
  ).toBeVisible();
  await captureStage?.("saved-schedule");
  if (!stayInline)
    await expect(page).toHaveURL(new RegExp(`/loans/${loan.id}$`));
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
  return loan;
}
export async function disburseUI(page: Page) {
  await expect(
    page.getByRole("button", { name: "Disburse loan", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Active demo identity").selectOption("demo-manager");
  await page.getByLabel("Disbursement date (UTC)").fill("2026-01-01");
  await page
    .getByRole("button", { name: "Disburse loan", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Record repayment", exact: true }),
  ).toBeEnabled();
  await page.getByLabel("Active demo identity").selectOption("demo-officer");
  await expect(
    page.getByRole("button", { name: "Record repayment", exact: true }),
  ).toBeEnabled();
}
export async function recordUI(page: Page, amount = "10.00") {
  await page
    .getByRole("button", { name: "Record repayment", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Amount received (INR)")).toBeFocused();
  await dialog.getByLabel("Amount received (INR)").fill(amount);
  await dialog.getByLabel("Payment time (UTC)").fill("2026-01-31T10:00");
  await dialog.getByLabel("Processing date (UTC)").fill("2026-01-31");
  const posted = page.waitForResponse(
    (r) => /\/repayments$/.test(r.url()) && r.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Record repayment", exact: true })
    .click();
  const response = await posted;
  expect(response.status()).toBe(201);
  const receipt = await response.json();
  await expect(
    dialog.getByText("Received and verified", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByText("₹9.00", { exact: true }).first(),
  ).toBeVisible();
  return receipt;
}
export async function createAPI(request: APIRequestContext) {
  const ref = crypto.randomUUID();
  const b = await request.post("/api/backend/borrowers", {
    headers: officer,
    data: {
      external_reference: `UX-B-${ref}`,
      full_name: "Invented API Fixture Borrower",
    },
  });
  expect(b.status()).toBe(201);
  const products = await (
    await request.get("/api/backend/loan-products", { headers: officer })
  ).json();
  const l = await request.post("/api/backend/loans", {
    headers: officer,
    data: {
      external_reference: `UX-L-${ref}`,
      borrower_id: (await b.json()).id,
      product_id: products.find(
        (p: { code: string }) => p.code === "PERSONAL_EMI",
      ).id,
      principal_paise: 10000,
      tenure_periods: 2,
      first_due_date: "2026-01-31",
    },
  });
  expect(l.status()).toBe(201);
  return await l.json();
}
export async function getJSON(request: APIRequestContext, path: string) {
  const r = await request.get("/api/backend" + path, { headers: auditor });
  expect(r.status()).toBe(200);
  return r.json();
}
