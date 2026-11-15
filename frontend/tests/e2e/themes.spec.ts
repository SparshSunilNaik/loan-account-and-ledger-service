import { test, expect } from "@playwright/test";
import { makeLoanUI, disburseUI, recordUI, capture, getJSON } from "./helpers";
const key = "ledgercore-studio-theme";
const evidence = process.env.STUDIO_CAPTURE_ROOT
  ? `${process.env.STUDIO_CAPTURE_ROOT}/themes`
  : "test-results/screenshots/themes";
for (const theme of ["light", "dark"] as const)
  for (const width of [1440, 1024, 390])
    test(`${theme}: actual servicing workflow and all layouts at ${width}px`, async ({
      page,
      request,
      context,
    }) => {
      await page.setViewportSize({ width, height: 1000 });
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto("/loans");
      await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      const folder = `${evidence}/${theme}/${width}`;
      const shot = (name: string) => capture(page, folder, name);
      if (width === 1440) await shot("empty-loans");
      const name = `Precision Sample ${theme} ${width}`;
      const loan = await makeLoanUI(page, name, shot);
      await disburseUI(page);
      await shot("loan-detail");
      let release!: () => void;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      await page.route(
        `**/api/backend/loans/${loan.id}/balance`,
        async (route) => {
          await gate;
          await route.continue();
        },
        { times: 1 },
      );
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      try {
        await expect(
          page.getByRole("button", { name: "Refreshing…", exact: true }),
        ).toBeDisabled();
        if (width === 1440) await shot("refreshing");
      } finally {
        release();
      }
      await expect(
        page.getByRole("button", { name: "Refresh", exact: true }),
      ).toBeEnabled();
      if (width === 390) await page.emulateMedia({ reducedMotion: "reduce" });
      const receipt = await recordUI(page);
      if (width === 390) {
        expect(
          await page
            .getByRole("dialog")
            .evaluate((e) => getComputedStyle(e).animationName),
        ).toBe("none");
      }
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
      await shot("ledger");
      expect(await getJSON(request, `/loans/${loan.id}/balance`)).toMatchObject(
        {
          principal_receivable_paise: 9100,
          interest_receivable_paise: 0,
          penalty_receivable_paise: 0,
        },
      );
      // Financial data and selected account persist independently of appearance.
      await page.reload();
      await expect(page.getByLabel("Appearance", { exact: true })).toHaveValue(
        theme,
      );
      await expect(page.getByLabel("Working account")).toHaveValue(loan.id);
      await page.getByRole("tab", { name: "Repayments", exact: true }).click();
      await expect(
        page.getByRole("heading", { name: "Repayments received", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("cell", { name: "₹10.00", exact: true }),
      ).toBeVisible();
      await shot("repayments");
      await page.getByRole("tab", { name: "Schedule", exact: true }).focus();
      await page.keyboard.press("ArrowRight");
      await expect(
        page.getByRole("tab", { name: "Repayments", exact: true }),
      ).toBeFocused();
      await page
        .getByRole("button", { name: "References", exact: true })
        .click();
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
      await page
        .getByRole("button", { name: `Copy ${loan.id}`, exact: true })
        .click();
      await expect(
        page.getByRole("status").filter({ hasText: /^Copied$/ }),
      ).toBeVisible();
      expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
        loan.id,
      );
      await page
        .getByRole("button", { name: "Close inspector", exact: true })
        .click();
      await page
        .getByRole("navigation", { name: "Main navigation" })
        .getByRole("link", { name: "Loans", exact: true })
        .click();
      await page.getByLabel("Filter browser-known loans").fill(name);
      await expect(page.getByRole("link", { name, exact: true })).toBeVisible();
      await shot("loans");
      await page
        .getByRole("navigation", { name: "Main navigation" })
        .getByRole("link", { name: "Activity", exact: true })
        .click();
      await expect(page.getByText("Balanced", { exact: true })).toHaveCount(3);
      await shot("activity");
      await page
        .getByRole("navigation", { name: "Main navigation" })
        .getByRole("link", { name: "Testing", exact: true })
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
      const receipts = await getJSON(request, `/loans/${loan.id}/repayments`);
      expect(receipts).toHaveLength(1);
      expect(receipts[0]).toMatchObject({
        id: receipt.id,
        journal_id: receipt.journal_id,
      });
      await page
        .getByRole("button", { name: "Test same-key conflict", exact: true })
        .click();
      await expect(page.getByText("HTTP 409", { exact: true })).toBeVisible();
      await shot("testing-conflict");
      await page.getByRole("button", { name: /auditor/i }).click();
      await expect(page.getByText("HTTP 403", { exact: true })).toBeVisible();
      await shot("testing-denied");
      await page
        .getByLabel("Active demo identity")
        .selectOption("demo-manager");
      await page.goto(`/loans/${loan.id}?tab=history`);
      await expect(
        page.getByRole("cell", { name: "repayment.posted", exact: true }),
      ).toBeVisible();
      await shot("history");
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
          `${theme} ${width} ${path}`,
        ).toBeLessThanOrEqual(width);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      }
      expect(errors).toEqual([]);
    });

test("System follows live OS changes; explicit preferences survive OS changes, reload and another tab", async ({
  page,
  context,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/loans");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByLabel("Appearance", { exact: true })).toHaveValue(
    "system",
  );
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByLabel("Appearance", { exact: true }).focus();
  expect(
    await page
      .getByLabel("Appearance", { exact: true })
      .evaluate((e) => getComputedStyle(e).outlineStyle),
  ).not.toBe("none");
  await page.keyboard.press("l");
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Appearance", { exact: true })).toHaveValue(
    "light",
  );
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const second = await context.newPage();
  await second.goto("/loans");
  await second.getByLabel("Appearance", { exact: true }).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await second.getByLabel("Appearance", { exact: true }).selectOption("system");
  await expect(page.getByLabel("Appearance", { exact: true })).toHaveValue(
    "system",
  );
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await page.evaluate((k) => localStorage.getItem(k), key)).toBe(
    "system",
  );
});

test("cold-load theme is correct before body and hydration; blocked storage and reduced motion remain usable", async ({
  browser,
  baseURL,
}) => {
  for (const [saved, os, expected] of [
    ["dark", "light", "dark"],
    ["light", "dark", "light"],
    ["system", "dark", "dark"],
    ["invalid", "dark", "dark"],
  ] as const) {
    const context = await browser.newContext({
      colorScheme: os,
      reducedMotion: "reduce",
    });
    await context.addInitScript(
      ({ key, saved }) => {
        localStorage.setItem(key, saved);
        // Observe the first opportunity at which body exists, before React hydration.
        new MutationObserver((_records, observer) => {
          if (document.body) {
            (
              window as unknown as { firstBodyTheme: string | undefined }
            ).firstBodyTheme = document.documentElement.dataset.theme;
            observer.disconnect();
          }
        }).observe(document, { childList: true, subtree: true });
      },
      { key, saved },
    );
    const page = await context.newPage();
    // Block hydration scripts only; the static trusted inline bootstrap must suffice.
    await page.route("**/_next/**/*.js*", (route) => route.abort());
    await page.goto(`${baseURL}/loans`, { waitUntil: "load" });
    expect(
      await page.evaluate(
        () => (window as unknown as { firstBodyTheme: string }).firstBodyTheme,
      ),
    ).toBe(expected);
    await expect(page.locator("html")).toHaveAttribute("data-theme", expected);
    const background = await page
      .locator("body")
      .evaluate((e) => getComputedStyle(e).backgroundColor);
    expect(background).toBe(
      expected === "dark" ? "rgb(16, 23, 28)" : "rgb(246, 247, 245)",
    );
    await context.close();
  }
  const context = await browser.newContext({
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  await context.addInitScript(() => {
    Object.defineProperty(Storage.prototype, "getItem", {
      value: () => {
        throw new DOMException("Storage blocked", "SecurityError");
      },
    });
    Object.defineProperty(Storage.prototype, "setItem", {
      value: () => {
        throw new DOMException("Storage blocked", "SecurityError");
      },
    });
  });
  const page = await context.newPage();
  await page.goto(`${baseURL}/loans`);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByLabel("Appearance", { exact: true }).selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(
    await page
      .locator(".theme-control")
      .evaluate((e) => getComputedStyle(e).transitionDuration),
  ).toBe("0s");
  await context.close();
});
