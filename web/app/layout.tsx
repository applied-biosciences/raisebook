import type { Metadata, Viewport } from "next";

import { GlobalChrome, ToastProvider } from "@/components/ui";
import { localeInitScript } from "@/lib/i18n";
import { themeInitScript } from "@/lib/theme";

import { fontVariables } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://wasila.app"),
  title: {
    default: "Wasila · Investor CRM and Funding Room",
    template: "%s · Wasila",
  },
  description:
    "Wasila is an investor CRM and Funding Room for founders raising in the US, UK and Saudi Arabia: every investor through every round, a document room for diligence, outreach and funding costs, with Claude and an MCP server for agentic work.",
  applicationName: "Wasila",
  authors: [{ name: "Applied Biosciences" }],
  creator: "Applied Biosciences",
  publisher: "Wasila",
  category: "business",
  openGraph: {
    type: "website",
    siteName: "Wasila",
    locale: "en_US",
  },
  twitter: { card: "summary_large_image" },
  ...(process.env.NEXT_PUBLIC_GIT_SHA
    ? { other: { "wasila-commit": process.env.NEXT_PUBLIC_GIT_SHA } }
    : {}),
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F4F8FB" },
    { media: "(prefers-color-scheme: dark)", color: "#0B1120" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVariables} suppressHydrationWarning>
      <head>
        {/* Applies the stored theme before first paint (SYSTEM 3.27). Inline, first-party. */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        {/* Applies the stored language (lang/dir) before first paint: bilingual scaffolding. */}
        <script dangerouslySetInnerHTML={{ __html: localeInitScript }} />
      </head>
      <body>
        <a
          href="#main"
          className="sr-only rounded-sm bg-fg px-12 py-8 text-canvas focus:not-sr-only focus:fixed focus:top-8 focus:left-8 focus:z-[80]"
        >
          Skip to content
        </a>
        <ToastProvider>{children}</ToastProvider>
        <GlobalChrome />
      </body>
    </html>
  );
}
