"use client";
import { Monitor, Moon, Sun, ChevronDown } from "lucide-react";
import { useTheme } from "@/lib/use-theme";
export function ThemeControl() {
  const { preference, setPreference } = useTheme();
  return (
    <label
      className="theme-control"
      title="Appearance is independent of demo identity"
    >
      <span className="theme-glyph" aria-hidden="true">
        <Sun className="theme-sun" size={16} />
        <Moon className="theme-moon" size={16} />
        <Monitor className="theme-system" size={16} />
      </span>
      <select
        aria-label="Appearance"
        value={preference}
        onChange={(event) => setPreference(event.target.value)}
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="system">System</option>
      </select>
      <ChevronDown size={12} aria-hidden="true" />
    </label>
  );
}
