"use client";

import { useState } from "react";

import { APP_VERSION_LABEL } from "@/lib/version";

/**
 * Last resort: the root layout itself failed, so nothing from it (styles, fonts, theme) is
 * available. Plain inline styles in both color schemes.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // The theme stylesheet is gone here, so the light/dark switch flips the color scheme inline.
  const [scheme, setScheme] = useState<"light dark" | "light" | "dark">("light dark");
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "grid",
          placeItems: "center",
          fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
          fontSize: 16,
          lineHeight: 1.5,
          background: "Canvas",
          color: "CanvasText",
          colorScheme: scheme,
          padding: 16,
        }}
      >
        <main style={{ maxWidth: 480 }}>
          <p style={{ fontWeight: 700, margin: "0 0 8px" }}>Wasila</p>
          <h1 style={{ fontSize: 22, margin: "0 0 8px" }}>Something went wrong on our side</h1>
          <p style={{ margin: "0 0 16px", opacity: 0.75 }}>
            The page could not be shown. Your data is safe. Try again in a moment.
            {error.digest ? (
              <span style={{ display: "block", fontFamily: "monospace", fontSize: 12 }}>
                ref {error.digest}
              </span>
            ) : null}
          </p>
          <button
            type="button"
            onClick={reset}
            style={{ font: "inherit", padding: "6px 14px", marginRight: 12, cursor: "pointer" }}
          >
            Try again
          </button>
          {/* A full page load on purpose: the app shell itself failed. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a href="/">Home</a>
          <p style={{ margin: "24px 0 0", fontSize: 12, opacity: 0.7, display: "flex", gap: 12 }}>
            <span>Wasila {APP_VERSION_LABEL}</span>
            <button
              type="button"
              aria-label="Toggle light or dark mode"
              onClick={() => setScheme((s) => (s === "dark" ? "light" : "dark"))}
              style={{ font: "inherit", cursor: "pointer", padding: "0 8px" }}
            >
              ☀︎/☾
            </button>
          </p>
        </main>
      </body>
    </html>
  );
}
