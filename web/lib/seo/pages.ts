/**
 * Every public page, in one place: its title, description, share card, section and the date
 * its content last changed. metadata, the sitemap, the generated OG images, breadcrumbs,
 * JSON-LD and llms.txt all read this list, so a new public page is added here first.
 * `updated` is the date the page's text last changed (git log of the page file); bump it
 * when you change what a page says.
 */

export type Section = "home" | "product" | "compare" | "guide" | "docs" | "about";

export interface PublicPage {
  path: string;
  /** <title> (the root template adds " · Wasila"; docs add " · Wasila docs"). */
  title: string;
  /** A full title used as is (home only). */
  absoluteTitle?: string;
  description: string;
  section: Section;
  updated: string;
  /** Breadcrumb label; defaults to title. */
  crumb?: string;
  og: { eyebrow: string; title: string; subtitle: string };
  /** Shown in llms.txt under its section. */
  llms?: boolean;
}

export const PAGES: PublicPage[] = [
  {
    path: "/",
    title: "Investor CRM and Funding Room for US, UK and Saudi raises",
    absoluteTitle: "Wasila · Investor CRM and Funding Room",
    description:
      "Wasila keeps your investor master list, round pipeline, Funding Room, outreach and funding costs in one place, with Claude and an MCP server for agents.",
    section: "home",
    updated: "2026-11-06",
    crumb: "Home",
    og: {
      eyebrow: "Wasila · v1.0.0.0",
      title: "Your raise, in one place.",
      subtitle: "Master list, pipeline, Funding Room, outreach and costs, for US, UK and Saudi rounds.",
    },
    llms: true,
  },
  {
    path: "/faq",
    title: "Questions founders ask",
    crumb: "FAQ",
    description:
      "Answers about Wasila: the Funding Room, outreach, Claude, SEIS and EIS, Saudi rounds, importing investor lists, agents and MCP, privacy and leaving.",
    section: "about",
    updated: "2026-10-15",
    og: { eyebrow: "FAQ", title: "Questions founders ask.", subtitle: "Funding Room, outreach, Claude, SEIS/EIS and Saudi rounds." },
    llms: true,
  },
  {
    path: "/docs",
    title: "Getting started",
    crumb: "Docs",
    description:
      "Set up Wasila in a few minutes: sign in, create a workspace and a round, bring your investors, and work the pipeline from the board, the table or your agent.",
    section: "docs",
    updated: "2026-10-13",
    og: {
      eyebrow: "Wasila docs",
      title: "Connect your agent. Import your sheet.",
      subtitle: "MCP setup for Claude Code, Codex and Cursor. REST API. CSV format.",
    },
    llms: true,
  },
  {
    path: "/docs/mcp",
    title: "Connect an agent (MCP)",
    description:
      "Connect Claude Code, Codex, Cursor or any MCP client to Wasila with a workspace API key. Copy-ready setup for each client.",
    section: "docs",
    updated: "2026-10-14",
    og: { eyebrow: "Docs · MCP", title: "Connect an agent.", subtitle: "Claude Code, Codex, Cursor and any MCP client." },
    llms: true,
  },
  {
    path: "/docs/mcp-tools",
    title: "MCP tools reference",
    description:
      "The 26 core Wasila MCP tools and the 5 research tools: what each one does, its parameters, what it returns, and which ones are safe to repeat.",
    section: "docs",
    updated: "2026-10-14",
    og: { eyebrow: "Docs · MCP", title: "MCP tools reference.", subtitle: "Every tool, its parameters and what it returns." },
    llms: true,
  },
  {
    path: "/docs/api",
    title: "REST API",
    description:
      "The Wasila REST API under /v1: authentication with workspace API keys, conventions, errors, rate limits and every endpoint.",
    section: "docs",
    updated: "2026-10-13",
    og: { eyebrow: "Docs · API", title: "REST API.", subtitle: "Rounds, investors, activity, meetings and exports under /v1." },
    llms: true,
  },
  {
    path: "/docs/meetings",
    title: "Meetings and the calendar feed",
    description:
      "Schedule investor meetings in Wasila, record outcomes and next steps, download .ics files, and subscribe from Google, Apple or Outlook calendars.",
    section: "docs",
    updated: "2026-10-15",
    og: { eyebrow: "Docs · Meetings", title: "Meetings and the calendar feed.", subtitle: "Schedule, record outcomes, subscribe from any calendar." },
    llms: true,
  },
  {
    path: "/docs/csv",
    title: "CSV import format",
    description:
      "How Wasila reads a spreadsheet: accepted column names, list, date and money formats, dedupe and what happens to each row.",
    section: "docs",
    updated: "2026-10-13",
    og: { eyebrow: "Docs · CSV", title: "Bring your spreadsheet.", subtitle: "Column names, mapping, preview and dedupe." },
    llms: true,
  },
  {
    path: "/docs/research",
    title: "Investor research",
    description:
      "How Wasila's investor research works: your own OpenRouter key, identity first, cited dossiers, presets and costs, the monthly limit, and save_dossier.",
    section: "docs",
    updated: "2026-10-13",
    og: { eyebrow: "Docs · Research", title: "Investor research.", subtitle: "Cited dossiers on your own OpenRouter key." },
    llms: true,
  },
  {
    path: "/docs/export",
    title: "Export and delete",
    description: "Take your data out of Wasila as CSV or JSON at any time, and delete an investor, a round, a workspace or your account permanently.",
    section: "docs",
    updated: "2026-10-13",
    og: { eyebrow: "Docs · Export", title: "Export and delete.", subtitle: "CSV and JSON, any time. Hard delete, effective immediately." },
    llms: true,
  },
  {
    path: "/docs/self-hosting",
    title: "Self-hosting",
    description: "Run Wasila on your own server with Docker Compose: Postgres, the API and MCP server, the web app and Caddy for TLS, all from one open-source repository.",
    section: "docs",
    updated: "2026-10-13",
    og: { eyebrow: "Docs · Self-hosting", title: "Run your own Wasila.", subtitle: "Docker Compose: Postgres, API, web and Caddy." },
    llms: true,
  },
  {
    path: "/privacy",
    title: "Privacy",
    description:
      "Wasila's privacy promise and the details behind it: what is stored, what is never collected, cookies, logs, email, backups and deletion.",
    section: "about",
    updated: "2026-10-13",
    og: { eyebrow: "Privacy", title: "The privacy promise.", subtitle: "Never pooled, sold or mined. No trackers. Leave any time." },
    llms: true,
  },
  {
    path: "/research-policy",
    title: "Research Policy",
    description:
      "What Wasila's investor research does, who starts it, what it collects and never collects, who can see it, how long it is kept, and how to ask for removal.",
    section: "about",
    updated: "2026-10-13",
    og: { eyebrow: "Research Policy", title: "What research collects, and what it never does.", subtitle: "Professional information only. Removal on request." },
    llms: true,
  },
  {
    path: "/terms",
    title: "Terms",
    description: "The terms for using Wasila, the investor CRM and Funding Room, in plain language: your data stays yours, fair use, and how the service is run.",
    section: "about",
    updated: "2026-10-13",
    og: { eyebrow: "Terms", title: "Terms of service.", subtitle: "For the hosted service at wasila.app." },
  },
  {
    path: "/support",
    title: "Support",
    description:
      "How to get help with Wasila: where to report a problem, how to reach Applied Biosciences, and what to include so we can fix it quickly for your team.",
    section: "about",
    updated: "2026-10-13",
    og: { eyebrow: "Support", title: "Get help with Wasila.", subtitle: "Report a problem or ask a question." },
    llms: true,
  },
  {
    path: "/changelog",
    title: "Changelog",
    description: "What changed in Wasila, the investor CRM and Funding Room, newest first: features, fixes and changes to the API and MCP server, from v1.0.0.0.",
    section: "about",
    updated: "2026-10-14",
    og: { eyebrow: "Changelog", title: "What changed.", subtitle: "Wasila, release by release." },
    llms: true,
  },
];

export function page(path: string): PublicPage {
  const p = PAGES.find((x) => x.path === path);
  if (!p) throw new Error(`unknown public page ${path}`);
  return p;
}

/** "/" → "home", "/compare/visible" → "compare-visible". Used as the OG image id. */
export function ogSlug(path: string): string {
  return path === "/" ? "home" : path.slice(1).replace(/\//g, "-");
}

export function ogPath(path: string): string {
  return `/og-image/${ogSlug(path)}`;
}

export function pageForOgSlug(slug: string): PublicPage | undefined {
  return PAGES.find((p) => ogSlug(p.path) === slug);
}

/** Breadcrumb trail of [label, path] pairs, Home first. */
export function crumbs(path: string): { name: string; path: string }[] {
  const out = [{ name: "Home", path: "/" }];
  if (path === "/") return out;
  const parts = path.split("/").filter(Boolean);
  let acc = "";
  for (const part of parts) {
    acc += `/${part}`;
    const p = PAGES.find((x) => x.path === acc);
    if (p) out.push({ name: p.crumb ?? p.title, path: p.path });
  }
  return out;
}
