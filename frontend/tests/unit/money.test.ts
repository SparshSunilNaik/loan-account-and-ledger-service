import { describe, expect, it } from "vitest";
import {
  inr,
  rupeesToPaise,
  percent,
  journalTotals,
  validateMonetaryIntegers,
} from "@/lib/money";
describe("exact monetary boundaries", () => {
  it.each([
    ["0.01", 1],
    ["0.29", 29],
    ["100000.10", 10000010],
    ["1000000000.00", 100000000000],
  ])("converts %s without floating point", (value, expected) =>
    expect(rupeesToPaise(value)).toBe(expected),
  );
  it.each(["0", "-1", "1.005", "1e3", "1,000.00", "NaN", "", "1000000000.01"])(
    "rejects ambiguous or out-of-range %s",
    (v) => expect(() => rupeesToPaise(v)).toThrow(),
  );
  it("formats integer paise and rates exactly", () => {
    expect(inr(10000010)).toBe("₹1,00,000.10");
    expect(inr(-1n)).toBe("−₹0.01");
    expect(inr(0)).toBe("₹0.00");
    expect(percent("0.1200000000")).toBe("12%");
    expect(percent("0.000005")).toBe("0.0005%");
  });
  it("rejects unsafe and fractional JSON money", () => {
    expect(() =>
      validateMonetaryIntegers({
        entries: [{ amount_paise: Number.MAX_SAFE_INTEGER + 1 }],
      }),
    ).toThrow();
    expect(() => validateMonetaryIntegers({ amount_paise: 1.2 })).toThrow();
  });
  it("diagnoses journal balance with BigInt totals", () => {
    expect(
      journalTotals([
        { direction: "debit", amount_paise: 10000 },
        { direction: "credit", amount_paise: 9000 },
        { direction: "credit", amount_paise: 1000 },
      ]),
    ).toEqual({ debit: 10000n, credit: 10000n, balanced: true });
    expect(journalTotals([]).balanced).toBe(false);
    expect(
      journalTotals([
        { direction: "debit", amount_paise: 1 },
        { direction: "credit", amount_paise: 2 },
      ]).balanced,
    ).toBe(false);
  });
});
