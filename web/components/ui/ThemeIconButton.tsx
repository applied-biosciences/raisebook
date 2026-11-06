"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { applyThemePref, readThemePref } from "@/lib/theme";

type Mode = "light" | "dark";

function currentMode(): Mode {
  const pref = readThemePref();
  if (pref !== "system") return pref;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * One-tap light/dark switch (sun / moon icon), shown on every page by GlobalChrome. It stores
 * an explicit choice through lib/theme, so the pre-paint script keeps it on reload; the
 * Light · Dark · System control in the footers and Settings still offers "System".
 */
export function ThemeIconButton({ className }: { className?: string }) {
  const [mode, setMode] = useState<Mode | null>(null);
  useEffect(() => setMode(currentMode()), []);
  const next: Mode = mode === "dark" ? "light" : "dark";
  const label = next === "dark" ? "Switch to dark mode" : "Switch to light mode";
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      data-testid="theme-toggle"
      onClick={() => {
        applyThemePref(next);
        setMode(next);
      }}
      className={cn(
        "inline-flex h-32 w-32 items-center justify-center rounded-pill border border-line bg-surface text-fg",
        "shadow-pill hover:border-accent hover:text-accent focus-visible:outline-2 focus-visible:outline-accent",
        className,
      )}
    >
      {mode === "dark" ? (
        // Sun: tapping returns to light.
        <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="4.5" />
          <path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8 6 18M18 6l1.8-1.8" />
        </svg>
      ) : (
        <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z" />
        </svg>
      )}
    </button>
  );
}
