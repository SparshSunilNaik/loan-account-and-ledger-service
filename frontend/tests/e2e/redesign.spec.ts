import { test, expect } from "@playwright/test";
import { makeLoanUI, disburseUI, recordUI, capture, getJSON } from "./helpers";
for (const width of [1440, 1024, 390])
  test(`Journeys A, B and C preserve loan context at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const folder = `${process.env.STUDIO_CAPTURE_ROOT ?? "test-results/screenshots"}/${width}`;
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const shot = (name: string) => capture(page, folder, name);
    const borrower = `Mira Sample ${width}`;
    // A: all origination and servicing actions use the UI, without ID or request-key entry.
    const loan = await makeLoanUI(page, borrower, shot);
    await disburseUI(page);
    await shot("loan-account");
    const receipt = await recordUI(page);
    expect(
      await page
        .getByRole("dialog")
        .evaluate((e) => e.scrollWidth <= e.clientWidth),
    ).toBe(true);
    await shot("repayment-result");
    await page
      .getByRole("button", { name: /View posted journal in account/ })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Journal details",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: `Copy ${receipt.id}`, exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/loans/${loan.id}$`));
    await shot("posted-journal");
    expect(await getJSON(request, `/loans/${loan.id}/balance`)).toMatchObject({
      principal_receivable_paise: 9100,
      interest_receivable_paise: 0,
      penalty_receivable_paise: 0,
    });
    expect(await getJSON(request, `/loans/${loan.id}/repayments`)).toHaveLength(
      1,
    );
    await page
      .getByRole("button", { name: "Close inspector", exact: true })
      .click();
    // B: return through browser-known names, keep the same context across tabs and reload.
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Loans", exact: true })
      .click();
    await page.getByLabel("Filter browser-known loans").fill(borrower);
    await expect(
      page.getByRole("link", { name: borrower, exact: true }),
    ).toBeVisible();
    await shot("loans");
    await page.getByRole("link", { name: borrower, exact: true }).click();
    await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
    await expect(page.locator(".account-principal strong")).toHaveText(
      "₹91.00",
    );
    await page.getByRole("tab", { name: "Schedule", exact: true }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(
      page.getByRole("tab", { name: "Repayments", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      page.getByRole("cell", { name: "₹10.00", exact: true }),
    ).toBeVisible();
    await shot("repayment-history");
    await page.reload();
    await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
    await page.getByRole("tab", { name: "Schedule", exact: true }).click();
    await expect(
      page.getByRole("cell", { name: "₹49.75", exact: true }),
    ).toBeVisible();
    // C: use the inherited original delivery, even after reload. No identifier is entered.
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Testing", exact: true })
      .click();
    await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
    await expect(page.locator("input[name=key]")).toHaveValue(/^payment-/);
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
      .getByRole("button", { name: "Test source alias", exact: true })
      .click();
    await expect(
      page.getByText(
        "Existing receipt and journal verified — original response reused.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(await getJSON(request, `/loans/${loan.id}/repayments`)).toHaveLength(
      1,
    );
    await page
      .getByRole("button", { name: "Test same-key conflict", exact: true })
      .click();
    await expect(page.getByText("HTTP 409", { exact: true })).toBeVisible();
    expect(await getJSON(request, `/loans/${loan.id}/repayments`)).toHaveLength(
      1,
    );
    expect(await getJSON(request, `/loans/${loan.id}/balance`)).toMatchObject({
      principal_receivable_paise: 9100,
      interest_receivable_paise: 0,
      penalty_receivable_paise: 0,
    });
    await shot("testing-conflict");
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Activity", exact: true })
      .click();
    await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
    await expect(page.getByText("Balanced", { exact: true })).toHaveCount(3);
    await shot("activity");
    await page
      .getByRole("link", { name: "Open loan account", exact: true })
      .click();
    await page.getByLabel("Active demo identity").selectOption("demo-manager");
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await expect(
      page.getByRole("cell", { name: "repayment.posted", exact: true }),
    ).toBeVisible();
    await shot("loan-history");
    for (const path of [
      "/loans",
      `/loans/${loan.id}`,
      "/new-loan",
      "/activity",
      "/testing",
    ]) {
      await page.goto(path);
      await page.getByRole("heading", { level: 1 }).waitFor();
      await page.waitForLoadState("networkidle");
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
        `${path} at ${width}px`,
      ).toBeLessThanOrEqual(width);
      expect(
        await page
          .getByRole("navigation", { name: "Main navigation" })
          .getByRole("link")
          .count(),
      ).toBe(4);
    }
    expect(errors).toEqual([]);
  });
