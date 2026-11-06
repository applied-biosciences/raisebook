import { APP_VERSION_LABEL } from "@/lib/version";

import { ThemeIconButton } from "./ThemeIconButton";

/**
 * Shown on every page (rendered by the root layout): the light/dark icon and the Wasila
 * version. It sits at the bottom end corner, above the phone tab bar (--wsl-tabbar), and
 * mirrors to the left in right-to-left layouts (logical `end-`).
 */
export function GlobalChrome() {
  return (
    <div
      data-testid="global-chrome"
      className="pointer-events-none fixed end-12 z-[60] flex items-center gap-8 print:hidden"
      style={{ bottom: "calc(12px + max(env(safe-area-inset-bottom), var(--wsl-tabbar)))" }}
    >
      <span
        data-testid="app-version"
        className="pointer-events-auto rounded-pill border border-line bg-surface px-8 py-2 font-mono text-2xs text-muted shadow-pill"
        title="Wasila version"
      >
        Wasila {APP_VERSION_LABEL}
      </span>
      <ThemeIconButton className="pointer-events-auto" />
    </div>
  );
}
