/**
 * Product facts used by the public pages, llms.txt and the structured data. Every number here
 * comes from the code or the spec (docs/SPEC.md §2 limits, §6.8 tool counts,
 * RESEARCH-PLAN for research). Change the spec first, then this file. Never add customers,
 * ratings, user counts or press here: Wasila has none to cite.
 */

export const OPERATOR = {
  name: "Applied Biosciences",
  email: "hello@wasila.app",
};

/** One-line definition, quoted by llms.txt, JSON-LD and the README. */
export const DEFINITION =
  "Wasila is an investor CRM and Funding Room for founders raising in the US, the UK and Saudi Arabia: a searchable master list of investors, every round's pipeline, email outreach with Funding Room attachments, a deck editor, funding costs, and Claude plus an MCP server for agentic work.";

/** Workspace limits (SPEC §2): the same for everyone. */
export const LIMITS = {
  rounds: 50,
  investors: 20_000,
  members: 20,
  apiKeys: 20,
};

/** MCP tools: 26 core (SPEC §6.4, the meeting tools of §6.8, the linked-card tools of §6.9 and
 * Wasila's list_funding_room, search_master_list and draft_outreach), 31 with research on. */
export const MCP_CORE_TOOLS = 26;
export const MCP_TOOLS_WITH_RESEARCH = 31;

/** Default stages of a new round (backend/wasila/models/round.py DEFAULT_STAGES). */
export const DEFAULT_STAGES = [
  "New",
  "Researching",
  "Contacted",
  "Replied",
  "Meeting",
  "Diligence",
  "Committed",
  "Passed",
];

/** Research: the monthly spend limit default per workspace (docs/research). */
export const RESEARCH_MONTHLY_LIMIT_USD = 25;

/** Short feature list, in the words founders search with. */
export const FEATURES: { name: string; text: string }[] = [
  {
    name: "US, UK and Saudi raising",
    text: "Each round names its market (US, UK, Saudi Arabia) with the right currency (USD, GBP, SAR), SAFE, priced, convertible note or UK advance subscription (ASA), SEIS/EIS tax relief for UK rounds, and Sharia-compliant terms for Saudi rounds.",
  },
  {
    name: "Funding Room",
    text: "A diligence repository: documents by category (pitch, corporate, financial, technical, clinical, regulatory, IP, cybersecurity, data protection, commercial, legal, SEIS/EIS) with every version kept, review status, confidentiality and US/UK/KSA checklists. Expiring share links show approved documents only, with private view counts.",
  },
  {
    name: "Master list and Ask Wasila",
    text: "Import investor leads from CSV, Excel or Word tables (or add them by hand) into one deduplicated master list. Filter by market, type, interest and contact state, or ask in plain words and Claude turns the question into filters. Save lists, add custom fields and AI columns.",
  },
  {
    name: "Email outreach and investor updates",
    text: "Write to investors from your own mailbox with approved Funding Room documents attached by hand; every send is recorded on the investor's timeline. Claude can draft a warm letter or an update. Campaigns merge one email into reviewed drafts, and follow-ups list mail with no reply.",
  },
  {
    name: "Warm intros",
    text: "Record who in your network knows each investor and how well; the best path shows on the investor's file and in the master list.",
  },
  {
    name: "Deck editor and funding costs",
    text: "Edit the words of a PowerPoint deck from the Funding Room, hide or reorder slides and save a new version; Claude can suggest a version tailored to one investor. Keep use of funds, SEIS/EIS tranches and the 48-month cost plan, with burn, runway and the funding gap.",
  },
  {
    name: "Investor pipeline",
    text: "Rounds with a target, instrument, cap and close date, and stages you can rename, recolor and reorder. Default stages: New, Researching, Contacted, Replied, Meeting, Diligence, Committed, Passed.",
  },
  {
    name: "Three views",
    text: "Triage to decide on new investors one at a time (number keys, undo), a kanban Board you can drag, and a sortable, filterable Table. A ledger strip shows committed against target, the funnel and follow-ups due.",
  },
  {
    name: "Investor files",
    text: "One file per investor, shared across rounds: stage, fit, check size, follow-up, notes and an append-only timeline of emails, calls, meetings and notes. Dedupe on email, LinkedIn and name + firm.",
  },
  {
    name: "Follow-ups",
    text: "Every investor can carry a follow-up date and note; Today and the ledger strip list who is due or overdue.",
  },
  {
    name: "Meetings and a calendar feed",
    text: "Schedule meetings from an investor's file (it moves them to Meeting), see today's meetings, record the outcome and next step, download .ics files, and subscribe from Google Calendar, Apple Calendar or Outlook with a private feed URL.",
  },
  {
    name: "Investor research with AI",
    text: "On demand, on your own OpenRouter key: a short, cited dossier per investor (recent deals, thesis, a way in, an opener, a risk). Every fact cites a source. A monthly spend limit per workspace ($25 by default) and no markup.",
  },
  {
    name: "MCP server and REST API",
    text: `An MCP server with ${MCP_CORE_TOOLS} tools (${MCP_TOOLS_WITH_RESEARCH} with research on, as on wasila.app) for Claude Code, Codex, Cursor, Claude Desktop (through mcp-remote) or any MCP client that can send an API key header, and a REST API under /v1. Web-only connectors (claude.ai and ChatGPT connectors) need OAuth, which Wasila does not offer yet. Agents cannot delete anything over MCP, and every write shows on the timeline under the agent's name.`,
  },
  {
    name: "Import and export",
    text: "Import CSV, Excel (.xlsx) or Word (.docx) tables with column mapping, preview and dedupe. CSV and JSON export of a round, all investors or the whole workspace, at any time. Hard delete of anything.",
  },
  {
    name: "Team",
    text: `Co-founders and advisors as owners, editors and viewers (up to ${LIMITS.members} members). Sign in with an emailed link or with Google.`,
  },
  {
    name: "Phone layout",
    text: "The pipeline, board and triage work on a phone, with touch-sized controls.",
  },
  {
    name: "Open source and self-hostable",
    text: "AGPL-3.0. One repository holds the API, the MCP server, the web app and the Docker Compose deploy files.",
  },
];

/** Who it is for, in one paragraph. */
export const WHO_FOR =
  "Founding teams raising a pre-seed, seed or Series A round across the US, the UK and Saudi Arabia who need one place for the investor list, the pipeline, the diligence documents and the outreach, with an AI assistant that drafts and searches but never acts without a person's click.";

/** What Wasila is not, so recommendations stay accurate. */
export const NOT_FOR = [
  "It has no investor database to search: you bring your own lists (CSV, Excel, Word, by hand or by agent).",
  "It never emails investors on its own: every email is reviewed and sent by a person, from their own mailbox.",
  "It is built for founders raising money, not for VC firms managing deal flow or LPs, and it gives no legal or tax advice.",
];
