import { normalizeLocale, type Locale } from "./config";
import { ar } from "./dictionaries/ar";
import { en, type MessageKey } from "./dictionaries/en";

export * from "./config";
export type { MessageKey } from "./dictionaries/en";

const DICTS: Record<Locale, Partial<Record<MessageKey, string>>> = { en, ar };

/** Look a key up in the locale's dictionary, falling back to English, then to the key. */
export function translate(locale: Locale | string | undefined, key: MessageKey): string {
  const loc = normalizeLocale(locale);
  return DICTS[loc][key] ?? en[key] ?? key;
}

/** Keys an Arabic translator still has to fill (used by the scaffolding test). */
export function missingKeys(locale: Locale): MessageKey[] {
  return (Object.keys(en) as MessageKey[]).filter((k) => DICTS[locale][k] === undefined);
}
