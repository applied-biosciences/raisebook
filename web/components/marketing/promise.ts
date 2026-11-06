/**
 * The privacy promise, word for word from SPEC §8.4. The landing page, /privacy and the README
 * use this exact text. Change the spec first, then this file.
 */
export const PRIVACY_PROMISE: { lead: string; body: string }[] = [
  {
    lead: "Your data is yours.",
    body: "A workspace is visible only to its members and to the API keys its owners create.",
  },
  {
    lead: "We never pool, sell, rent or mine it.",
    body: "Wasila never builds an investor database from your data and never shows one workspace's data to another.",
  },
  {
    lead: "No ads, no trackers.",
    body: "No analytics scripts, pixels or third-party cookies. Fonts are served by Wasila.",
  },
  {
    lead: "No AI on your data unless you bring it.",
    body: "Wasila never runs or pays for AI on its own. Claude and investor research run only when you press a button, on your own Anthropic or OpenRouter key, and see only public investor profile data, your company profile and round terms: never emails, phone numbers, amounts or notes. Agents you connect use your key, and every action they take is on the timeline.",
  },
  {
    lead: "Leave any time.",
    body: "Export everything as CSV and JSON. Delete your workspace or account permanently, effective immediately.",
  },
  {
    lead: "Check our work.",
    body: "Wasila is open source under AGPL-3.0, including the code that handles your data.",
  },
];
