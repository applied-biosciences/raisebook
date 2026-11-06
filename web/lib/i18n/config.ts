/**
 * Bilingual scaffolding (Wasila v1.0.0.0). English is complete; Arabic is wired end to end
 * (cookie → <html lang dir> → font → dictionary lookup) but not translated yet: every Arabic
 * entry falls back to English until the translation release fills `dictionaries/ar.ts`.
 *
 * The choice lives in a first-party cookie so server components can render the right
 * `lang`/`dir` on the first byte (no flash, no client-only switch).
 */
export const LOCALES = ["en", "ar"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "wsl-locale";

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  ar: "العربية",
};

export function isLocale(v: unknown): v is Locale {
  return typeof v === "string" && (LOCALES as readonly string[]).includes(v);
}

export function normalizeLocale(v: unknown): Locale {
  return isLocale(v) ? v : DEFAULT_LOCALE;
}

export function dirFor(locale: Locale): "ltr" | "rtl" {
  return locale === "ar" ? "rtl" : "ltr";
}

/**
 * Inline pre-paint script for <head> (like the theme script): applies the stored locale's
 * `lang` and `dir` before first paint, so static pages stay static.
 */
export const localeInitScript = `(function(){try{var m=document.cookie.match(/(?:^|; )${LOCALE_COOKIE}=([^;]+)/);var l=m&&decodeURIComponent(m[1]);if(l==="ar"){var d=document.documentElement;d.setAttribute("lang","ar");d.setAttribute("dir","rtl")}}catch(e){}})();`;

/** Store the locale (one year, first-party, Lax) and apply it to the current page. */
export function applyLocale(locale: Locale): void {
  const d = document.documentElement;
  d.setAttribute("lang", locale);
  d.setAttribute("dir", dirFor(locale));
  document.cookie = `${LOCALE_COOKIE}=${locale}; Path=/; Max-Age=31536000; SameSite=Lax`;
}

export function readLocale(): Locale {
  if (typeof document === "undefined") return DEFAULT_LOCALE;
  const m = document.cookie.match(new RegExp(`(?:^|; )${LOCALE_COOKIE}=([^;]+)`));
  return normalizeLocale(m ? decodeURIComponent(m[1]) : undefined);
}
