/**
 * Questions founders ask, as plain text so the same entries render on the page and in the
 * FAQPage structured data (Google requires the marked-up answer to be visible). `link` is
 * rendered after the answer.
 */

import { LIMITS, MCP_CORE_TOOLS, MCP_TOOLS_WITH_RESEARCH } from "./facts";

export interface FaqItem {
  q: string;
  a: string;
  link?: { href: string; label: string };
}

export const HOME_FAQ: FaqItem[] = [
  {
    q: "What is Wasila?",
    a: "Wasila is an investor CRM and Funding Room for founders raising in the US, the UK and Saudi Arabia. It keeps a searchable master list of investors, every round's pipeline, your diligence documents, your outreach and your funding costs in one place.",
  },
  {
    q: "Does Wasila email investors for me?",
    a: "Only when you press Send. Emails go from your own mailbox (Gmail, Outlook or any SMTP account), with the Funding Room documents you attach by hand, and each send is recorded on the investor's timeline. Claude can draft a message, but a person always reviews and sends it.",
  },
  {
    q: "How does Claude fit in?",
    a: "Each workspace adds its own Anthropic API key. Claude turns plain-English questions into master-list filters, fills AI columns, drafts warm letters and investor updates, and suggests deck edits. It sees public investor profile data only (never emails, phone numbers, amounts or notes) and runs only when someone clicks.",
  },
  {
    q: "What is the Funding Room?",
    a: "Your diligence repository. Documents are filed by category with every version kept, a review status and a confidentiality level, and there are checklists for US, UK and Saudi raises. A share link shows approved documents only, expires on its own and can be revoked.",
    link: { href: "/docs", label: "Getting started" },
  },
  {
    q: "Can I import my investor lists?",
    a: "Yes: CSV, Excel (.xlsx) and Word (.docx) tables, or add investors by hand. Columns are mapped for you, every row is previewed, and duplicates are matched on email, LinkedIn, and name and firm.",
    link: { href: "/docs/csv", label: "Import format" },
  },
  {
    q: "What happens if I want to leave?",
    a: "Export the workspace as JSON and each round as CSV, then delete the workspace. Deletion is immediate and permanent, and backups age out within 14 days.",
    link: { href: "/docs/export", label: "Export and delete" },
  },
];

/** Extra questions for the /faq hub, grouped after the home set. */
export const MORE_FAQ: { group: string; items: FaqItem[] }[] = [
  {
    group: "Raising in the US, the UK and Saudi Arabia",
    items: [
      {
        q: "Does Wasila handle SEIS and EIS?",
        a: "A UK round can be marked SEIS, EIS or SEIS then EIS, the funding costs page splits the round into SEIS and EIS tranches, and the UK checklist includes HMRC advance assurance. Wasila records your plan; it is not tax advice, so confirm eligibility with your accountant.",
      },
      {
        q: "What about Saudi Arabia?",
        a: "A Saudi round uses SAR by default, can be marked Sharia-compliant, and its Funding Room checklist covers the Commercial Registration, the MISA licence, ZATCA registration, PDPL data protection and SFDA. Arabic and English are being prepared: the language switch is in Settings.",
      },
      {
        q: "Which instruments are supported?",
        a: "SAFE, priced equity, convertible notes and the UK advance subscription agreement (ASA), with a valuation cap or pre-money valuation, target and close date per round.",
      },
    ],
  },
  {
    group: "Agents, data and privacy",
    items: [
      {
        q: "Can an AI agent use Wasila?",
        a: `Yes. Wasila's MCP server has ${MCP_CORE_TOOLS} tools (${MCP_TOOLS_WITH_RESEARCH} with research on) to read the pipeline and the Funding Room, search the master list, add investors, move stages, log activity, schedule meetings and draft (never send) emails. It has no delete tools, and every write shows on the timeline under the agent's name.`,
        link: { href: "/docs/mcp", label: "Connect an agent" },
      },
      {
        q: "How many investors can a workspace hold?",
        a: `Up to ${LIMITS.investors.toLocaleString("en-US")} investors and ${LIMITS.rounds} rounds per workspace, with up to ${LIMITS.members} members as owners, editors or viewers.`,
      },
      {
        q: "Who can see my data?",
        a: "Only the members of your workspace and the API keys its owners create. Wasila never pools, sells or mines workspace data, has no ads or trackers, and stores Funding Room files and secrets (your Anthropic key and mail password) encrypted on your own server.",
        link: { href: "/privacy", label: "Privacy" },
      },
      {
        q: "Is the source code available?",
        a: "Yes. Wasila is open source under AGPL-3.0 (the NOTICE file credits the project it builds on), and you can run your own copy with Docker Compose.",
        link: { href: "/docs/self-hosting", label: "Self-hosting" },
      },
    ],
  },
];
