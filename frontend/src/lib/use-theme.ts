"use client";
import { useSyncExternalStore } from "react";
import {
  validTheme,
  resolveTheme,
  THEME_KEY,
  type ThemePreference,
} from "./theme";

function current(): ThemePreference {
  const fromDOM = document.documentElement.dataset.themePreference;
  if (fromDOM) return validTheme(fromDOM);
  try {
    return validTheme(localStorage.getItem(THEME_KEY));
  } catch {
    return "system";
  }
}
function apply(preference: ThemePreference) {
  const root = document.documentElement;
  root.dataset.themePreference = preference;
  root.dataset.theme = resolveTheme(
    preference,
    window.matchMedia("(prefers-color-scheme: dark)").matches,
  );
}
const listeners = new Set<() => void>();
function notify() {
  listeners.forEach((listener) => listener());
}
function subscribe(listener: () => void) {
  listeners.add(listener);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onOSChange = () => {
    if (current() === "system") apply("system");
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY || event.key === null) {
      apply(validTheme(event.newValue));
      notify();
    }
  };
  // Reapply after development Strict Mode can reset unmanaged root attributes.
  apply(current());
  media.addEventListener("change", onOSChange);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", onOSChange);
    window.removeEventListener("storage", onStorage);
  };
}
export function useTheme() {
  const preference = useSyncExternalStore(
    subscribe,
    current,
    () => "system" as const,
  );
  function setPreference(value: string) {
    const next = validTheme(value);
    apply(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Still usable in this tab when browser storage is disabled.
    }
    notify();
  }
  return { preference, setPreference };
}
