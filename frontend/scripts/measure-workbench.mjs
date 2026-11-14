import { chromium, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
const phase = process.env.UX_PHASE ?? "before";
const after = phase === "after";
const base = process.env.STUDIO_URL ?? "http://127.0.0.1:3000";
const folder = `docs/workbench/${phase}`;
mkdirSync(folder, { recursive: true });
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_EXECUTABLE ??
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => {
  const fresh = () => ({ clicks: 0, routes: [], scrolls: 0, maxOverflow: 0 });
  window.ux = fresh();
  window.resetUX = () => {
    window.ux = fresh();
  };
  document.addEventListener("click", () => window.ux.clicks++, true);
  window.addEventListener("scroll", () => {
    if (scrollY > 0) window.ux.scrolls++;
  });
  for (const key of ["pushState", "replaceState"]) {
    const original = history[key].bind(history);
    history[key] = (...args) => {
      const previous = location.href;
      const r = original(...args);
      if (location.href !== previous)
        window.ux.routes.push(location.pathname + location.search);
      return r;
    };
  }
  window.sampleUX = () => {
    window.ux.maxOverflow = Math.max(
      window.ux.maxOverflow,
      document.documentElement.scrollHeight - innerHeight,
    );
    return window.ux;
  };
});
const records = [];
let fields = [];
let start;
async function begin(name) {
  await page.evaluate(() => window.resetUX());
  fields = [];
  start = performance.now();
  records.push({ journey: name });
}
async function sample() {
  await page.evaluate(() => window.sampleUX());
}
async function fill(label, value) {
  fields.push(label);
  await page.getByLabel(label, { exact: true }).fill(value);
  await sample();
}
async function click(name) {
  const inside = page
    .getByRole("dialog")
    .getByRole("button", { name, exact: true });
  await (
    (await inside.count())
      ? inside
      : page.getByRole("button", { name, exact: true })
  ).click();
  await sample();
}
async function finish(extra = {}) {
  await sample();
  Object.assign(records.at(-1), await page.evaluate(() => window.ux), {
    field_entries: fields.length,
    repeated_field_entries: fields.length - new Set(fields).size,
    manual_loan_id_entries: 0,
    elapsed_ms: Math.round(performance.now() - start),
    ...extra,
  });
}
async function shot(name) {
  await page.screenshot({
    path: `${folder}/${name}.png`,
    fullPage: false,
    animations: "disabled",
  });
}
await page.goto(base + "/new-loan");
await page.waitForLoadState("networkidle");
await begin("A: originate, disburse, partial repayment, inspect posting");
const name = `Workbench Measurement ${phase}`;
await fill("Borrower name", name);
await click("Continue to loan terms");
await page.getByRole("radio", { name: /Personal EMI Loan/ }).check();
await fill("Principal (INR)", "100.00");
await fill("Tenure (instalments)", "2");
await fill("First due date (UTC)", "2026-01-31");
const created = page.waitForResponse(
  (r) =>
    r.url().endsWith("/api/backend/loans") && r.request().method() === "POST",
);
await click("Create loan & review schedule");
const loan = await (await created).json();
await expect(
  page.getByRole("cell", { name: "₹49.75", exact: true }),
).toBeVisible();
await shot("origination");
if (!after)
  await page
    .getByRole("link", { name: "Open loan account", exact: true })
    .click();
await page.getByLabel("Active demo identity").selectOption("demo-manager");
await fill("Disbursement date (UTC)", "2026-01-01");
await click("Disburse loan");
await expect(
  page.getByRole("button", { name: "Record repayment", exact: true }),
).toBeEnabled();
await page.getByLabel("Active demo identity").selectOption("demo-officer");
await click("Record repayment");
const paymentStart = performance.now();
await fill("Amount received (INR)", "10.00");
await fill("Payment time (UTC)", "2026-01-31T10:00");
await fill("Processing date (UTC)", "2026-01-31");
await click("Record repayment");
await expect(
  page.getByText("Received and verified", { exact: true }),
).toBeVisible();
await shot("repayment");
const repayment_ms = Math.round(performance.now() - paymentStart);
const journalStart = performance.now();
if (!after) await click("View posted journal in account");
await expect(
  page.getByRole("cell", { name: "Balanced journal", exact: true }),
).toBeVisible();
await shot("journal");
await finish({
  repayment_details_ms: repayment_ms,
  journal_inspection_ms: Math.round(performance.now() - journalStart),
  loan_id: loan.id,
});
await begin("B: return to known loan, repayment details, associated journal");
if (after) await click("Close repayment");
await page
  .getByRole("navigation", { name: "Main navigation" })
  .getByRole("link", { name: "Loans", exact: true })
  .click();
await fill("Filter browser-known loans", name);
await page.getByRole("link", { name, exact: true }).click();
await page.getByRole("tab", { name: "Repayments", exact: true }).click();
await expect(
  page.getByRole("heading", { name: "Repayments received", exact: true }),
).toBeVisible();
const detailsStart = performance.now();
if (after)
  await page
    .getByRole("button", { name: /Inspect repayment/ })
    .first()
    .click();
else
  await page.getByText("Allocation records (paise)", { exact: true }).click();
const details_ms = Math.round(performance.now() - detailsStart);
const linkedStart = performance.now();
if (after)
  await expect(
    page.getByRole("cell", { name: "Balanced journal", exact: true }),
  ).toBeVisible();
else {
  await page.getByRole("tab", { name: "Ledger", exact: true }).click();
  await page.getByRole("button", { name: /Expand Repayment journal/ }).click();
  await expect(
    page.getByText("Journal totals · 3 entries", { exact: true }),
  ).toBeVisible();
}
await shot("record-details");
await finish({
  repayment_details_ms: details_ms,
  journal_inspection_ms: Math.round(performance.now() - linkedStart),
});
await begin("C: exact retry and changed-payload conflict");
if (after) await click("Delivery checks");
else
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Testing", exact: true })
    .click();
await click("Retry identical request");
await expect(
  page.getByText(
    "Existing receipt and journal verified — original response reused.",
    { exact: true },
  ),
).toBeVisible();
await click("Test same-key conflict");
await expect(page.getByText("HTTP 409", { exact: true })).toBeVisible();
await shot("retry-conflict");
await finish();
const out = {
  phase,
  viewport: { width: 1440, height: 900 },
  clock: new Date().toISOString(),
  method:
    "Real installed Chrome + native PostgreSQL/FastAPI. Pointer click events counted (fill/selectOption excluded), field-entry calls counted separately. Route changes include query-string changes. Times are one automated local run including API latency, not human task times or statistical performance claims.",
  records,
};
writeFileSync(
  `${folder}/measurements.json`,
  JSON.stringify(out, null, 2) + "\n",
);
console.log(JSON.stringify(out, null, 2));
await browser.close();
