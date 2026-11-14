import { afterEach, describe, expect, it, vi } from "vitest";
import { THEME_BOOTSTRAP, THEME_KEY } from "@/lib/theme";
describe("before-paint theme bootstrap", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
  });
  it.each([
    ["dark", false, "dark"],
    ["light", true, "light"],
    ["system", true, "dark"],
    ["system", false, "light"],
    ["untrusted-value", true, "dark"],
  ])(
    "preference %s with OS dark=%s resolves to %s",
    (saved, osDark, expected) => {
      localStorage.setItem(THEME_KEY, saved);
      vi.stubGlobal("matchMedia", () => ({ matches: osDark }));
      new Function(THEME_BOOTSTRAP)();
      expect(document.documentElement.dataset.theme).toBe(expected);
    },
  );
  it("storage failure falls back to OS before painting", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("Blocked", "SecurityError");
    });
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    expect(() => new Function(THEME_BOOTSTRAP)()).not.toThrow();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.dataset.themePreference).toBe("system");
  });
});
