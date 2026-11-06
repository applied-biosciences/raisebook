import type { MessageKey } from "./en";

/**
 * Arabic strings. Intentionally sparse in v1.0.0.0: a missing key falls back to English (see
 * `translate` in lib/i18n/index.ts). The translation release fills this in; keep keys in step
 * with dictionaries/en.ts.
 */
export const ar: Partial<Record<MessageKey, string>> = {
  "common.appName": "وسيلة",
};
