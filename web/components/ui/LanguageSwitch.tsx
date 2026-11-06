"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { applyLocale, LOCALE_LABELS, LOCALES, readLocale, type Locale } from "@/lib/i18n";

/**
 * Settings → Language (bilingual scaffolding). Stores the choice in the wsl-locale cookie and
 * flips <html lang dir> at once. Arabic text is not translated yet; English strings remain.
 */
export function LanguageSwitch({ className }: { className?: string }) {
  const [locale, setLocale] = useState<Locale | null>(null);
  useEffect(() => setLocale(readLocale()), []);
  return (
    <div role="radiogroup" aria-label="Language" className={cn("flex flex-wrap gap-8", className)}>
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          role="radio"
          aria-checked={locale === l}
          data-testid={`locale-${l}`}
          onClick={() => {
            applyLocale(l);
            setLocale(l);
          }}
          className={cn(
            "h-36 min-w-[96px] rounded-md border px-14 text-13",
            locale === l
              ? "border-accent bg-accent-soft text-fg"
              : "border-line bg-surface text-muted hover:text-fg",
          )}
          lang={l}
        >
          {LOCALE_LABELS[l]}
        </button>
      ))}
    </div>
  );
}
