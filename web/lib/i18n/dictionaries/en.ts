/**
 * English strings, keyed by area. Only the keys the scaffolding needs exist today; screens move
 * their copy here as the translation release reaches them.
 */
export const en = {
  "common.appName": "Wasila",
  "common.version": "Version",
  "settings.language.title": "Language",
  "settings.language.help":
    "Choose the language for Wasila on this browser. Arabic switches the layout to right-to-left; full Arabic translation arrives in a later release.",
  "settings.language.saved": "Language saved",
  "theme.toLight": "Switch to light mode",
  "theme.toDark": "Switch to dark mode",
  "fundingRoom.title": "Funding Room",
} as const;

export type MessageKey = keyof typeof en;
export type Dictionary = Record<MessageKey, string>;
