import localFont from "next/font/local";

/*
 * Fonts are bundled in the repository (app/fonts, SIL Open Font License) and served by Wasila
 * through next/font/local, so builds need no network and pages make no runtime requests to
 * third parties (SPEC §1.6, privacy promise 3). CSS variables: --f-display, --f-body, --f-mono
 * (SYSTEM §1.4) and --f-arabic (IBM Plex Sans Arabic, used when <html dir="rtl">).
 */

/** Display: Bricolage Grotesque, variable weight with the optical-size axis (12..96). */
export const display = localFont({
  src: [{ path: "./fonts/BricolageGrotesque-opsz.woff2", weight: "200 800", style: "normal" }],
  display: "swap",
  variable: "--f-display",
});

export const body = localFont({
  src: [
    { path: "./fonts/IBMPlexSans-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/IBMPlexSans-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/IBMPlexSans-600.woff2", weight: "600", style: "normal" },
  ],
  display: "swap",
  variable: "--f-body",
});

export const mono = localFont({
  src: [
    { path: "./fonts/IBMPlexMono-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/IBMPlexMono-500.woff2", weight: "500", style: "normal" },
  ],
  display: "swap",
  variable: "--f-mono",
});

/** Arabic script (bilingual scaffolding): loaded lazily by the browser only when used. */
export const arabic = localFont({
  src: [
    { path: "./fonts/IBMPlexSansArabic-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/IBMPlexSansArabic-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/IBMPlexSansArabic-600.woff2", weight: "600", style: "normal" },
  ],
  display: "swap",
  preload: false,
  variable: "--f-arabic",
});

export const fontVariables = `${display.variable} ${body.variable} ${mono.variable} ${arabic.variable}`;
