import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch:
    process.env.STUDIO_OFFLINE === "1"
      ? "offline.spec.ts"
      : [
          "workflows.spec.ts",
          "redesign.spec.ts",
          "themes.spec.ts",
          "workbench.spec.ts",
        ],
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.STUDIO_URL ?? "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: process.env.CHROME_EXECUTABLE
      ? { executablePath: process.env.CHROME_EXECUTABLE }
      : undefined,
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium", viewport: { width: 1440, height: 1080 } },
    },
  ],
});
