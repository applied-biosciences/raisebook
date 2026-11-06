import Link from "next/link";

import { SiteNav } from "@/components/marketing/SiteNav";
import { REPO_URL, SPONSOR_URL } from "@/components/marketing/site";
import { ButtonLink, ThemeToggle, Wordmark } from "@/components/ui";
import { APP_VERSION_LABEL } from "@/lib/version";

const FOOTER: { title: string; links: { href: string; label: string; external?: boolean }[] }[] = [
  {
    title: "Product",
    links: [
      { href: "/#features", label: "Features" },
      { href: "/faq", label: "FAQ" },
      { href: "/docs", label: "Docs" },
      { href: "/docs/mcp", label: "MCP setup" },
      { href: "/docs/api", label: "REST API" },
    ],
  },
  {
    title: "Guides",
    links: [
      { href: "/docs/csv", label: "Import investor lists" },
      { href: "/docs/meetings", label: "Meetings and calendar" },
      { href: "/docs/mcp-tools", label: "MCP tools" },
      { href: "/docs/export", label: "Export your data" },
    ],
  },
  {
    title: "Project",
    links: [
      { href: REPO_URL, label: "GitHub", external: true },
      { href: "/changelog", label: "Changelog" },
      { href: "/docs/self-hosting", label: "Self-hosting" },
      { href: "/support", label: "Support" },
    ],
  },
  {
    title: "Promises",
    links: [
      { href: "/privacy", label: "Privacy" },
      { href: "/research-policy", label: "Research Policy" },
      { href: "/terms", label: "Terms" },
      { href: "/docs/export", label: "Export and delete" },
    ],
  },
];

/** Marketing shell (SYSTEM §4.14): 64px nav, full-width main, footer. */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b-3 border-brand-gold bg-canvas md:static">
        <div className="gutter mx-auto flex h-64 max-w-site items-center gap-12 sm:gap-24">
          <Wordmark size={22} href="/" />
          <SiteNav className="hidden md:flex" />
          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-6">
            <Link href="/docs" className="inline-flex min-h-44 items-center px-8 font-medium text-muted hover:text-fg md:hidden">
              Docs
            </Link>
            <ButtonLink href="/signin" variant="ghost" className="hidden sm:inline-flex">
              Sign in
            </ButtonLink>
            <ButtonLink href="/signin" variant="primary">
              Open Wasila
            </ButtonLink>
          </div>
        </div>
      </header>

      <main id="main" className="marketing flex-1">
        {children}
      </main>

      <footer className="border-t-3 border-brand bg-accent-soft">
        <div className="gutter mx-auto grid max-w-site gap-x-32 gap-y-32 py-48 sm:grid-cols-2 xl:grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,1fr))]">
          <div className="flex flex-col gap-10">
            <Wordmark size={22} />
            <p className="max-w-[32ch] text-muted">Investor CRM and Funding Room for US, UK and Saudi raises. By Applied Biosciences.</p>
            {SPONSOR_URL ? (
              <a
                href={SPONSOR_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="link self-start text-sm"
              >
                Support Wasila <span aria-hidden>↗</span>
              </a>
            ) : null}
          </div>
          {FOOTER.map((col) => (
            <nav key={col.title} aria-label={col.title}>
              <p className="t-label mb-10">{col.title}</p>
              <ul className="m-0 flex list-none flex-col gap-6 p-0">
                {col.links.map((l) => (
                  <li key={l.label}>
                    {l.external ? (
                      <a
                        href={l.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted hover:text-fg"
                      >
                        {l.label} <span aria-hidden>↗</span>
                      </a>
                    ) : (
                      <Link href={l.href} className="text-muted hover:text-fg">
                        {l.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>
        <div className="border-t border-line">
          <div className="gutter mx-auto flex max-w-site flex-wrap items-center gap-x-18 gap-y-8 py-14">
            <p className="t-micro text-muted">Wasila {APP_VERSION_LABEL} · AGPL-3.0</p>
            <ThemeToggle className="sm:ml-auto" />
          </div>
        </div>
      </footer>
    </div>
  );
}
