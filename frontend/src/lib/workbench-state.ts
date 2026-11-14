"use client";
import { useEffect, useSyncExternalStore } from "react";
const listeners = new Set<() => void>();
const values = new Map<string, string>();
const loaded = new Set<string>();
const prefix = "ledgercore-workbench:";
function publish(key: string, raw: string) {
  values.set(key, raw);
  try {
    sessionStorage.setItem(prefix + key, raw);
  } catch {}
  listeners.forEach((listener) => listener());
}
// Editable drafts only: no balance or record snapshot is persisted here.
export function useSessionDraft<T>(
  key: string,
  initial: T,
  validate: (value: unknown) => value is T,
) {
  const raw = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => values.get(key) ?? null,
    () => null,
  );
  useEffect(() => {
    if (loaded.has(key)) return;
    loaded.add(key);
    try {
      const stored = sessionStorage.getItem(prefix + key);
      if (stored && validate(JSON.parse(stored))) publish(key, stored);
    } catch {}
  }, [key, validate]);
  let value = initial;
  try {
    if (raw && validate(JSON.parse(raw))) value = JSON.parse(raw) as T;
  } catch {}
  function set(next: T | ((old: T) => T)) {
    let previous = initial;
    try {
      const stored = values.get(key);
      if (stored && validate(JSON.parse(stored)))
        previous = JSON.parse(stored) as T;
    } catch {}
    publish(
      key,
      JSON.stringify(
        typeof next === "function" ? (next as (old: T) => T)(previous) : next,
      ),
    );
  }
  return [value, set] as const;
}
export interface PaymentDraft {
  amount: string;
  date: string;
  occurred: string;
  preparedKey: string;
}
export const isPaymentDraft = (v: unknown): v is PaymentDraft =>
  !!v &&
  typeof v === "object" &&
  ["amount", "date", "occurred", "preparedKey"].every(
    (k) =>
      typeof (v as Record<string, unknown>)[k] === "string" &&
      String((v as Record<string, unknown>)[k]).length <= 300,
  );
export type WorkbenchAction =
  "schedule" | "repayments" | "ledger" | "history" | "payment" | "refresh";
export function workbenchCommand(action: WorkbenchAction) {
  window.dispatchEvent(
    new CustomEvent("ledgercore:workbench", { detail: action }),
  );
}
export function useMobile() {
  return useSyncExternalStore(
    (listener) => {
      const media = matchMedia("(max-width: 760px)");
      media.addEventListener("change", listener);
      return () => media.removeEventListener("change", listener);
    },
    () => matchMedia("(max-width: 760px)").matches,
    () => false,
  );
}
