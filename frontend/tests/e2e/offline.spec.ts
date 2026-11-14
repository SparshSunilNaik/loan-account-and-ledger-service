import { test, expect } from "@playwright/test";
for (const theme of ["light", "dark"])
  test(`unavailable backend is identified without fabricated account data (${theme})`, async ({
    page,
    request,
  }) => {
    const r = await request.get("/api/backend/health");
    expect(r.status()).toBe(503);
    expect(await r.json()).toMatchObject({ studio_proxy: true });
    await page.goto("/loans");
    await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
    await expect(page.locator(".connection")).toContainText(
      "Backend unavailable",
    );
    await page.getByText("Available loan products", { exact: true }).click();
    await expect(page.locator(".error-state[role=alert]")).toContainText(
      "Local FastAPI backend is unavailable",
    );
    await page.screenshot({
      path: `${process.env.STUDIO_CAPTURE_ROOT ?? "docs/product-ux/after"}/backend-offline-${theme}.png`,
      animations: "disabled",
      fullPage: true,
    });
  });
