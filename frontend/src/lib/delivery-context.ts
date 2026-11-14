"use client";
import { useEffect, useSyncExternalStore } from "react";
import type { Attempt } from "./api";
import { actors } from "./types";
import { UUID_PATTERN } from "./session";
const empty: Record<string, Attempt> = {};
let current = empty,
  hydrated = false;
const listeners = new Set<() => void>();
const storageKey = "ledgercore-studio-deliveries-v1";
function publish(value: Record<string, Attempt>) {
  current = value;
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(value));
  } catch {}
  listeners.forEach((f) => f());
}
function hydrate() {
  if (hydrated) return;
  hydrated = true;
  try {
    const raw = JSON.parse(sessionStorage.getItem(storageKey) ?? "{}");
    const safe: Record<string, Attempt> = {};
    for (const [id, a] of Object.entries(raw) as [string, Attempt][]) {
      if (
        UUID_PATTERN.test(id) &&
        a.loanId === id &&
        actors.includes(a.actor) &&
        typeof a.key === "string" &&
        a.key.length <= 200 &&
        a.body &&
        Number.isSafeInteger(a.body.amount_paise) &&
        a.body.amount_paise > 0 &&
        typeof a.body.business_date === "string" &&
        typeof a.body.occurred_at === "string" &&
        typeof a.body.source === "string" &&
        typeof a.body.external_event_id === "string"
      )
        safe[id] = a;
    }
    publish(safe);
  } catch {}
}
export function rememberDelivery(attempt: Attempt) {
  hydrate();
  publish({ ...current, [attempt.loanId]: structuredClone(attempt) });
}
const subscribe = (f: () => void) => {
  listeners.add(f);
  return () => {
    listeners.delete(f);
  };
};
export function useDelivery(id: string) {
  const state = useSyncExternalStore(
    subscribe,
    () => current,
    () => empty,
  );
  useEffect(hydrate, []);
  return state[id];
}
