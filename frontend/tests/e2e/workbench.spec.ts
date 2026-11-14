import { expect, test } from "@playwright/test";
import {
  createAPI,
  capture,
  disburseUI,
  getJSON,
  makeLoanUI,
  recordUI,
} from "./helpers";
for (const width of [1440, 1024, 390])
  test(`persistent workbench lifecycle, inspector, delivery checks and keyboard at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    const folder = `docs/workbench/screens/${width}`;
    await page.goto("/loans");
    await page
      .getByLabel("Appearance", { exact: true })
      .selectOption(width === 1024 ? "light" : "dark");
    const name = `Workbench Sample ${width}`;
    const loan = await makeLoanUI(
      page,
      name,
      (n) => capture(page, folder, n),
      true,
    );
    await expect(page).toHaveURL(new RegExp(`/loans/${loan.id}$`));
    await disburseUI(page);
    await capture(page, folder, "account");
    await page
      .getByRole("button", { name: "Record repayment", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByLabel("Amount received (INR)")
      .fill("7.00");
    await page
      .getByRole("button", { name: "Close repayment", exact: true })
      .click();
    await page.getByRole("tab", { name: "Repayments", exact: true }).click();
    await page
      .getByRole("button", { name: "Record repayment", exact: true })
      .click();
    await expect(
      page.getByRole("dialog").getByLabel("Amount received (INR)"),
    ).toHaveValue("7.00");
    await page
      .getByRole("button", { name: "Close repayment", exact: true })
      .click();
    const receipt = await recordUI(page);
    if (width === 1440) {
      await expect(
        page.getByRole("heading", { name, exact: true }),
      ).toBeVisible();
      await expect(
        page
          .getByRole("dialog")
          .getByRole("cell", { name: "Balanced journal", exact: true }),
      ).toBeInViewport();
      expect(
        await page.evaluate(() => document.documentElement.scrollHeight),
      ).toBeLessThanOrEqual(900);
    }
    await capture(page, folder, "repayment-result");
    if (width === 390)
      await page
        .getByRole("button", { name: "Close repayment", exact: true })
        .click();
    await page
      .getByRole("button", { name: "Delivery checks", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Retry identical request", exact: true })
      .click();
    await expect(
      page.getByText(
        "Existing receipt and journal verified — original response reused.",
        { exact: true },
      ),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Test same-key conflict", exact: true })
      .click();
    await expect(page.getByText("HTTP 409", { exact: true })).toBeVisible();
    await capture(page, folder, "conflict");
    await page
      .getByRole("button", { name: "Test auditor denial", exact: true })
      .click();
    await expect(page.getByText("HTTP 403", { exact: true })).toBeVisible();
    const receipts = await getJSON(request, `/loans/${loan.id}/repayments`);
    expect(receipts).toHaveLength(1);
    expect(receipts[0].id).toBe(receipt.id);
    expect(await getJSON(request, `/loans/${loan.id}/balance`)).toMatchObject({
      principal_receivable_paise: 9100,
      interest_receivable_paise: 0,
      penalty_receivable_paise: 0,
    });
    await page
      .getByRole("button", { name: "Close repayment", exact: true })
      .click();
    await page.getByRole("tab", { name: "Repayments", exact: true }).click();
    const receiptURL = page.url();
    await page
      .getByRole("button", {
        name: `Inspect repayment ${receipt.id}`,
        exact: true,
      })
      .click();
    await expect(
      page.getByRole("heading", { name: "Repayment details", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Allocation records", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("cell", { name: "Balanced journal", exact: true }),
    ).toBeVisible();
    expect(page.url()).toBe(receiptURL);
    await capture(page, folder, "receipt-inspector");
    await page
      .getByRole("button", { name: "Inspect linked journal", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Journal details", exact: true }),
    ).toBeVisible();
    expect(page.url()).toBe(receiptURL);
    await page
      .getByRole("button", { name: "Close inspector", exact: true })
      .click();
    await page.getByRole("tab", { name: "Ledger", exact: true }).click();
    const journalURL = page.url();
    await page
      .getByRole("button", {
        name: `Inspect Repayment journal ${receipt.journal_id}`,
        exact: true,
      })
      .click();
    await expect(
      page.getByRole("heading", { name: "Journal details", exact: true }),
    ).toBeVisible();
    expect(page.url()).toBe(journalURL);
    await capture(page, folder, "journal-inspector");
    await page
      .getByRole("button", { name: "Close inspector", exact: true })
      .click();
    await page.keyboard.press("Meta+k");
    await page
      .getByRole("combobox", {
        name: "Search commands and known loans",
        exact: true,
      })
      .fill("open schedule");
    await capture(page, folder, "command-palette");
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("tab", { name: "Schedule", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Schedule", exact: true }).focus();
    await page.keyboard.press("Alt+2");
    await expect(
      page.getByRole("tab", { name: "Repayments", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await page.reload();
    await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
    await expect(
      page.getByRole("tab", { name: "Repayments", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await page.getByLabel("Active demo identity").selectOption("demo-manager");
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await page
      .getByRole("button", { name: "repayment.posted", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Audit event", exact: true }),
    ).toBeVisible();
    await capture(page, folder, "audit-inspector");
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);
  });

test("origination drafts survive navigation and safe step changes; palette is role-aware", async ({
  page,
}) => {
  await page.goto("/new-loan");
  await page
    .getByLabel("Borrower name", { exact: true })
    .fill("Invented Draft Borrower");
  await page.getByLabel("Phone (optional)").fill("9000012345");
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Loans", exact: true })
    .click();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "New loan", exact: true })
    .click();
  await expect(page.getByLabel("Borrower name", { exact: true })).toHaveValue(
    "Invented Draft Borrower",
  );
  await page.getByRole("button", { name: /Continue to loan terms/ }).click();
  await page.getByLabel("Principal (INR)", { exact: true }).fill("123.45");
  await page
    .getByRole("button", { name: "Change borrower", exact: true })
    .click();
  await expect(page.getByLabel("Phone (optional)")).toHaveValue("9000012345");
  await page.getByRole("button", { name: /Continue to loan terms/ }).click();
  await expect(page.getByLabel("Principal (INR)", { exact: true })).toHaveValue(
    "123.45",
  );
  await page.getByLabel("Active demo identity").selectOption("demo-auditor");
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Workbench commands" }),
  ).toBeVisible();
  await expect(
    page.getByRole("option", { name: /Create a new loan/ }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Principal (INR)", { exact: true })).toHaveValue(
    "123.45",
  );
});

test("unknown committed repayment survives workbench refresh and retries original identity", async ({
  page,
  request,
}) => {
  const loan = await makeLoanUI(page, "Invented Workbench Timeout");
  await disburseUI(page);
  const keys: string[] = [];
  let receiptId = "";
  await page.route(
    `**/api/backend/loans/${loan.id}/repayments`,
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      keys.push(route.request().headers()["idempotency-key"]);
      if (receiptId) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      expect(response.status()).toBe(201);
      receiptId = (await response.json()).id;
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
  await page.reload();
  await page
    .getByRole("button", { name: "Record repayment", exact: true })
    .click();
  await expect(page.getByLabel("Amount received (INR)")).toHaveValue("10.00");
  await expect(page.getByLabel("Amount received (INR)")).toBeDisabled();
  await page.getByText("Advanced delivery testing", { exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Test same-key conflict", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Test source alias", exact: true }),
  ).toBeDisabled();
  await page.getByText("Advanced delivery testing", { exact: true }).click();
  await page
    .getByRole("button", { name: "Retry prepared repayment", exact: true })
    .click();
  await expect(
    page.getByText("Existing receipt reused", { exact: true }),
  ).toBeVisible();
  const receipts = await getJSON(request, `/loans/${loan.id}/repayments`);
  expect(receipts).toHaveLength(1);
  expect(receipts[0].id).toBe(receiptId);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test("long actual schedules scroll inside the workbench without moving the document", async ({
  page,
  request,
}) => {
  const headers = { "X-Demo-User": "demo-officer" };
  const tag = crypto.randomUUID();
  const borrower = await request.post("/api/backend/borrowers", {
    headers,
    data: {
      full_name: "Invented Long-Schedule Borrower",
      external_reference: `WB-B-${tag}`,
    },
  });
  expect(borrower.status()).toBe(201);
  const products = await (
    await request.get("/api/backend/loan-products", { headers })
  ).json();
  const created = await request.post("/api/backend/loans", {
    headers,
    data: {
      external_reference: `WB-L-${tag}`,
      borrower_id: (await borrower.json()).id,
      product_id: products.find(
        (p: { code: string }) => p.code === "PERSONAL_EMI",
      ).id,
      principal_paise: 1000000,
      tenure_periods: 48,
      first_due_date: "2026-01-31",
    },
  });
  expect(created.status()).toBe(201);
  const loan = await created.json();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/loans/${loan.id}`);
  await expect(page.getByRole("cell", { name: "48", exact: true })).toHaveCount(
    1,
  );
  const records = page.getByRole("region", {
    name: "Loan records",
    exact: true,
  });
  expect(await records.evaluate((e) => e.scrollHeight > e.clientHeight)).toBe(
    true,
  );
  await records.focus();
  await records.press("End");
  await expect(
    page.getByRole("cell", { name: "48", exact: true }),
  ).toBeInViewport();
  expect(await page.evaluate(() => scrollY)).toBe(0);
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight),
  ).toBeLessThanOrEqual(900);
  await capture(page, "docs/workbench/screens/1440", "long-schedule");
});

test("header loan selector opens a known account directly from discovery", async ({
  page,
  request,
}) => {
  const first = await createAPI(request),
    second = await createAPI(request);
  await page.goto(`/loans/${first.id}`);
  await expect(page.getByLabel("Working account")).toHaveValue(first.id);
  await page.goto(`/loans/${second.id}`);
  await expect(page.getByLabel("Working account")).toHaveValue(second.id);
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Loans", exact: true })
    .click();
  await page.getByLabel("Working account").selectOption(first.id);
  await expect(page).toHaveURL(new RegExp(`/loans/${first.id}$`));
  await expect(page.locator(".account-heading-copy")).toContainText(
    first.external_reference,
  );
  await page.reload();
  await expect(page.getByLabel("Working account")).toHaveValue(first.id);
});
