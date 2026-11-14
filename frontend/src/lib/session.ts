"use client";
import { useEffect, useSyncExternalStore } from "react";
import type { Actor } from "./types";
import { actors } from "./types";
export const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export interface RecentLoan {
  id: string;
  reference: string;
  visitedAt: string;
}
interface State {
  actor: Actor;
  selectedLoan: string;
  recent: RecentLoan[];
}
const initial: State = { actor: "demo-officer", selectedLoan: "", recent: [] };
let current = initial,
  hydrated = false;
const listeners = new Set<() => void>();
const key = "ledgercore-studio-session-v1";
function publish(state: State) {
  current = state;
  try {
    sessionStorage.setItem(key, JSON.stringify(state));
  } catch {
    /* Browser storage may be disabled; memory still works. */
  }
  listeners.forEach((listener) => listener());
}
function hydrate() {
  if (hydrated) return;
  hydrated = true;
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) ?? "null");
    if (saved && actors.includes(saved.actor))
      publish({
        actor: saved.actor,
        selectedLoan: UUID_PATTERN.test(saved.selectedLoan)
          ? saved.selectedLoan
          : "",
        recent: Array.isArray(saved.recent)
          ? saved.recent
              .filter(
                (r: RecentLoan) =>
                  UUID_PATTERN.test(r.id) &&
                  typeof r.reference === "string" &&
                  typeof r.visitedAt === "string",
              )
              .slice(0, 12)
          : [],
      });
  } catch {
    /* A malformed local history is not a backend financial record. */
  }
}
export const session = {
  actor: (actor: Actor) => publish({ ...current, actor }),
  select: (id: string) => publish({ ...current, selectedLoan: id }),
  remember: (id: string, reference: string) =>
    publish({
      ...current,
      selectedLoan: id,
      recent: [
        { id, reference, visitedAt: new Date().toISOString() },
        ...current.recent.filter((r) => r.id !== id),
      ].slice(0, 12),
    }),
  clear: () => publish({ ...current, recent: [], selectedLoan: "" }),
};
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export function useStudio() {
  const state = useSyncExternalStore(
    subscribe,
    () => current,
    () => initial,
  );
  useEffect(hydrate, []);
  return state;
}
