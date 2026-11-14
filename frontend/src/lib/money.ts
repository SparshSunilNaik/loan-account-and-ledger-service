export const MAX_PAISE = 100_000_000_000n;
export function paise(value: number | bigint): bigint {
  if (typeof value === "bigint") return value;
  if (!Number.isSafeInteger(value))
    throw new Error(
      "Backend monetary value is not a safe integer paise amount.",
    );
  return BigInt(value);
}
export function rupeesToPaise(input: string): number {
  const value = input.trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(value))
    throw new Error(
      "Enter rupees with at most two decimal places. No commas or exponent notation.",
    );
  const [whole, fraction = ""] = value.split(".");
  const result = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  if (result < 1n || result > MAX_PAISE)
    throw new Error("Amount must be between ₹0.01 and ₹100,00,00,000.00.");
  return Number(result); // Exact: bounded integer below Number.MAX_SAFE_INTEGER.
}
export function inr(value: number | bigint): string {
  const amount = paise(value),
    sign = amount < 0n ? "−" : "",
    absolute = amount < 0n ? -amount : amount;
  return `${sign}₹${new Intl.NumberFormat("en-IN").format(absolute / 100n)}.${String(absolute % 100n).padStart(2, "0")}`;
}
export function percent(fraction: string): string {
  if (!/^\d+(?:\.\d+)?$/.test(fraction)) return fraction;
  const [whole, decimals = ""] = fraction.split(".");
  const digits = (whole + decimals).padStart(decimals.length + 1, "0");
  const numerator = BigInt(digits) * 100n,
    denominator = 10n ** BigInt(decimals.length);
  const remainder = String(numerator % denominator)
    .padStart(decimals.length, "0")
    .replace(/0+$/, "");
  return `${numerator / denominator}${remainder ? "." + remainder : ""}%`;
}
export function journalTotals(
  entries: { amount_paise: number; direction: "debit" | "credit" }[],
) {
  const debit = entries
    .filter((e) => e.direction === "debit")
    .reduce((sum, e) => sum + paise(e.amount_paise), 0n);
  const credit = entries
    .filter((e) => e.direction === "credit")
    .reduce((sum, e) => sum + paise(e.amount_paise), 0n);
  return { debit, credit, balanced: entries.length >= 2 && debit === credit };
}
export function validateMonetaryIntegers(value: unknown): void {
  if (!value || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    if (key.endsWith("_paise") && typeof item === "number") paise(item);
    else if (item && typeof item === "object") validateMonetaryIntegers(item);
  }
}
