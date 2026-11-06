/**
 * Wasila v1.0.0.0 calls: the Funding Room, the master list (search, Ask Wasila, custom fields
 * and AI columns, saved lists, warm intros), Claude settings, outreach, the deck editor and
 * funding costs. Every function takes a workspace-scoped client first (`api.ws(slug)` in the
 * browser, `await serverApi(slug)` on the server).
 */

import { seg, type ApiClient } from "./client";
import type { Investor, Timestamp, UUID } from "./types";

/* ---------- Funding Room ---------- */

export type RoomCategory =
  | "pitch"
  | "corporate"
  | "financial"
  | "technical"
  | "clinical"
  | "regulatory"
  | "ip"
  | "cybersecurity"
  | "data_protection"
  | "commercial"
  | "legal"
  | "tax_relief"
  | "other";
export type Confidentiality = "public" | "investors" | "nda" | "restricted";
export type ReviewStatus = "draft" | "in_review" | "approved" | "archived";
export type DocJurisdiction = "all" | "us" | "uk" | "ksa";

export const CATEGORY_LABEL: Record<RoomCategory, string> = {
  pitch: "Pitch and overview",
  corporate: "Corporate",
  financial: "Financial",
  technical: "Technical",
  clinical: "Clinical",
  regulatory: "Regulatory",
  ip: "Intellectual property",
  cybersecurity: "Cybersecurity",
  data_protection: "Data protection",
  commercial: "Commercial",
  legal: "Legal",
  tax_relief: "Tax relief (SEIS/EIS)",
  other: "Other",
};
export const CONFIDENTIALITY_LABEL: Record<Confidentiality, string> = {
  public: "Public",
  investors: "Investors",
  nda: "Under NDA",
  restricted: "Restricted",
};
export const REVIEW_LABEL: Record<ReviewStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  approved: "Approved",
  archived: "Archived",
};
export const JURISDICTION_LABEL: Record<DocJurisdiction, string> = {
  all: "All markets",
  us: "United States",
  uk: "United Kingdom",
  ksa: "Saudi Arabia",
};

export interface RoomVersion {
  version: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  note: string | null;
  created_at: Timestamp;
  actor_label?: string | null;
}

export interface RoomDocument {
  id: UUID;
  title: string;
  category: RoomCategory;
  category_label: string;
  folder: string | null;
  description: string | null;
  confidentiality: Confidentiality;
  review_status: ReviewStatus;
  jurisdiction: DocJurisdiction;
  is_deck: boolean;
  current_version: number;
  latest: RoomVersion | null;
  reviewed_at: Timestamp | null;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface RoomLink {
  id: UUID;
  label: string;
  investor_id: UUID | null;
  document_ids: UUID[];
  expires_at: Timestamp;
  revoked_at: Timestamp | null;
  view_count: number;
  last_viewed_at: Timestamp | null;
  state: "active" | "expired" | "revoked";
  created_at: Timestamp;
  token?: string;
}

export interface ChecklistItem {
  key: string;
  label: string;
  category: RoomCategory;
  status: "missing" | "present" | "approved";
  document_ids: string[];
}

export interface RoomEvent {
  id: UUID;
  document_id: UUID | null;
  kind: string;
  data: Record<string, unknown>;
  actor_type: string;
  actor_label: string | null;
  created_at: Timestamp;
}

export const listDocuments = (c: ApiClient, q: Record<string, string | undefined> = {}) =>
  c.get<{ data: RoomDocument[]; counts: Record<string, number>; categories: Record<string, string> }>(
    "/v1/funding-room/documents",
    q,
  );
export const createDocument = (
  c: ApiClient,
  body: Partial<Pick<RoomDocument, "title" | "category" | "folder" | "description" | "confidentiality" | "review_status" | "jurisdiction">>,
) => c.post<RoomDocument>("/v1/funding-room/documents", body);
export const updateDocument = (c: ApiClient, id: string, body: Partial<RoomDocument>) =>
  c.patch<RoomDocument>(`/v1/funding-room/documents/${seg(id)}`, body);
export const deleteDocument = (c: ApiClient, id: string) => c.del(`/v1/funding-room/documents/${seg(id)}`);
export const listVersions = (c: ApiClient, id: string) =>
  c.get<{ data: RoomVersion[] }>(`/v1/funding-room/documents/${seg(id)}/versions`);

/** Upload a file as the next version (raw body, name in X-Filename). */
export const uploadVersion = (c: ApiClient, id: string, file: Blob, filename: string, note?: string) =>
  c.post<RoomVersion>(`/v1/funding-room/documents/${seg(id)}/versions`, file, {
    headers: {
      "X-Filename": encodeURIComponent(filename),
      "Content-Type": "application/octet-stream",
      ...(note ? { "X-Note": encodeURIComponent(note) } : {}),
    },
  });

export const downloadPath = (id: string, version?: number) =>
  `/v1/funding-room/documents/${seg(id)}/download${version ? `?version=${version}` : ""}`;

export const listLinks = (c: ApiClient) => c.get<{ data: RoomLink[] }>("/v1/funding-room/links");
export const createLink = (
  c: ApiClient,
  body: { label: string; document_ids: string[]; investor_id?: string | null; days: number },
) => c.post<RoomLink>("/v1/funding-room/links", body);
export const revokeLink = (c: ApiClient, id: string) => c.del<RoomLink>(`/v1/funding-room/links/${seg(id)}`);
export const getChecklist = (c: ApiClient, jurisdiction: DocJurisdiction) =>
  c.get<{ jurisdiction: string; items: ChecklistItem[] }>("/v1/funding-room/checklist", { jurisdiction });
export const listRoomEvents = (c: ApiClient) => c.get<{ data: RoomEvent[] }>("/v1/funding-room/events");

export interface PublicRoom {
  company: string;
  label: string;
  expires_at: Timestamp;
  documents: { id: UUID; title: string; category_label: string; description: string | null; filename: string; size_bytes: number }[];
}
export const openRoomLink = (c: ApiClient, token: string) =>
  c.get<PublicRoom>(`/v1/room-links/${seg(token)}`, undefined, { workspace: null });

/* ---------- master list ---------- */

export interface Filters {
  q?: string;
  countries?: string[];
  types?: string[];
  tags_any?: string[];
  has_email?: boolean | null;
  not_contacted?: boolean | null;
  in_round?: string;
  not_in_round?: string;
  custom?: Record<string, string>;
}

export interface MasterInvestor extends Investor {
  country?: string | null;
  phone?: string | null;
  custom?: Record<string, unknown>;
}

export interface SearchResult {
  filters: Filters;
  total: number;
  data: MasterInvestor[];
  intros: Record<string, { connector_name: string; strength: number; relationship?: string | null }>;
  explanation?: string | null;
}

export const searchMasterList = (c: ApiClient, body: Filters & { limit?: number; offset?: number }) =>
  c.post<SearchResult>("/v1/master-list/search", body);
export const askWasila = (c: ApiClient, question: string) =>
  c.post<SearchResult>("/v1/master-list/ask", { question });
export const masterFacets = (c: ApiClient) =>
  c.get<{ total: number; countries: { value: string; count: number }[]; types: { value: string; count: number }[] }>(
    "/v1/master-list/facets",
  );

export interface InvestorField {
  id: UUID;
  key: string;
  label: string;
  kind: "text" | "number" | "yes_no" | "select" | "url" | "ai";
  options: string[];
  prompt: string | null;
  position: number;
}
export const listFields = (c: ApiClient) => c.get<{ data: InvestorField[] }>("/v1/investor-fields");
export const createField = (c: ApiClient, body: Pick<InvestorField, "label" | "kind"> & { options?: string[]; prompt?: string | null }) =>
  c.post<InvestorField>("/v1/investor-fields", body);
export const deleteField = (c: ApiClient, id: string) => c.del(`/v1/investor-fields/${seg(id)}`);
export const fillAiColumn = (c: ApiClient, id: string, investorIds: string[], overwrite = false) =>
  c.post<{ filled: Record<string, string>; skipped: string[] }>(`/v1/investor-fields/${seg(id)}/fill`, {
    investor_ids: investorIds,
    overwrite,
  });
export const setCustom = (c: ApiClient, investorId: string, values: Record<string, unknown>) =>
  c.put<MasterInvestor>(`/v1/investors/${seg(investorId)}/custom`, { values });

export interface SavedList {
  id: UUID;
  name: string;
  question: string | null;
  filters: Filters;
  pinned: number;
  created_at: Timestamp;
  updated_at: Timestamp;
}
export const listSavedLists = (c: ApiClient) => c.get<{ data: SavedList[] }>("/v1/saved-lists");
export const saveList = (c: ApiClient, body: { name: string; question?: string | null; filters?: Filters; investor_ids?: string[] }) =>
  c.post<SavedList>("/v1/saved-lists", body);
export const openSavedList = (c: ApiClient, id: string) => c.get<SearchResult>(`/v1/saved-lists/${seg(id)}`);
export const deleteSavedList = (c: ApiClient, id: string) => c.del(`/v1/saved-lists/${seg(id)}`);

export interface Intro {
  id: UUID;
  investor_id: UUID;
  connector_name: string;
  connector_email: string | null;
  relationship: string | null;
  strength: 1 | 2 | 3;
  strength_label: string;
  notes: string | null;
  created_at: Timestamp;
}
export const listIntros = (c: ApiClient, investorId: string) =>
  c.get<{ data: Intro[]; best: Intro | null }>(`/v1/investors/${seg(investorId)}/intros`);
export const addIntro = (
  c: ApiClient,
  investorId: string,
  body: { connector_name: string; connector_email?: string | null; relationship?: string | null; strength: number; notes?: string | null },
) => c.post<Intro>(`/v1/investors/${seg(investorId)}/intros`, body);
export const deleteIntro = (c: ApiClient, id: string) => c.del(`/v1/intros/${seg(id)}`);

/* ---------- Claude ---------- */

export interface ClaudeSettings {
  ready: boolean;
  key_last4: string | null;
  key_set_at: Timestamp | null;
  model: string;
  models: string[];
}
export const getClaude = (c: ApiClient) => c.get<ClaudeSettings>("/v1/claude");
export const putClaudeKey = (c: ApiClient, apiKey: string) => c.put<ClaudeSettings>("/v1/claude/key", { api_key: apiKey });
export const deleteClaudeKey = (c: ApiClient) => c.del("/v1/claude/key");
export const setClaudeModel = (c: ApiClient, model: string) => c.patch<ClaudeSettings>("/v1/claude", { model });

/* ---------- outreach ---------- */

export interface MailSettings {
  configured: boolean;
  host?: string | null;
  port?: number | null;
  security?: "starttls" | "ssl" | "none" | null;
  username?: string | null;
  from_email?: string | null;
  from_name?: string | null;
  reply_to?: string | null;
  bcc_self: boolean;
  password_set: boolean;
}
export const getMailSettings = (c: ApiClient) => c.get<MailSettings>("/v1/outreach/mail-settings");
export const putMailSettings = (c: ApiClient, body: Record<string, unknown>) =>
  c.put<MailSettings>("/v1/outreach/mail-settings", body);

export interface OutreachMessage {
  id: UUID;
  investor_id: UUID;
  campaign_id: UUID | null;
  kind: "outreach" | "update" | "follow_up";
  to_email: string;
  subject: string;
  body: string;
  attachments: { document_id: string; version: number; filename: string; size_bytes: number; title?: string | null }[];
  status: "draft" | "sending" | "sent" | "failed";
  drafted_by: "person" | "claude";
  error: string | null;
  sent_at: Timestamp | null;
  replied_at: Timestamp | null;
  created_at: Timestamp;
  updated_at: Timestamp;
}
export const listMessages = (c: ApiClient, q: Record<string, string | undefined> = {}) =>
  c.get<{ data: OutreachMessage[] }>("/v1/outreach/messages", q);
export const createMessage = (
  c: ApiClient,
  body: { investor_id: string; subject: string; body: string; attachment_ids?: string[]; kind?: string },
) => c.post<OutreachMessage>("/v1/outreach/messages", body);
export const claudeDraft = (
  c: ApiClient,
  body: { investor_id: string; kind?: "outreach" | "update"; instructions?: string; attachment_ids?: string[] },
) => c.post<OutreachMessage>("/v1/outreach/draft", body);
export const updateMessage = (c: ApiClient, id: string, body: { subject?: string; body?: string; attachment_ids?: string[]; to_email?: string }) =>
  c.patch<OutreachMessage>(`/v1/outreach/messages/${seg(id)}`, body);
export const deleteMessage = (c: ApiClient, id: string) => c.del(`/v1/outreach/messages/${seg(id)}`);
export const sendMessage = (c: ApiClient, id: string) => c.post<OutreachMessage>(`/v1/outreach/messages/${seg(id)}/send`);
export const markReplied = (c: ApiClient, id: string, note?: string) =>
  c.post<OutreachMessage>(`/v1/outreach/messages/${seg(id)}/replied`, { note: note || null });
export const followUpsDue = (c: ApiClient) => c.get<{ data: OutreachMessage[] }>("/v1/outreach/follow-ups");

export interface Campaign {
  id: UUID;
  name: string;
  kind: "outreach" | "update";
  subject: string;
  body: string;
  attachment_ids: UUID[];
  follow_up_days: number | null;
  stats: { drafts: number; sent: number; failed: number; replied: number };
  created_at: Timestamp;
}
export const listCampaigns = (c: ApiClient) => c.get<{ data: Campaign[] }>("/v1/outreach/campaigns");
export const createCampaign = (
  c: ApiClient,
  body: { name: string; kind: "outreach" | "update"; subject: string; body: string; attachment_ids?: string[]; follow_up_days?: number | null },
) => c.post<Campaign>("/v1/outreach/campaigns", body);
export const draftCampaign = (c: ApiClient, id: string, body: { investor_ids?: string[]; saved_list_id?: string }) =>
  c.post<{ created: OutreachMessage[]; skipped: { investor_id: string; name: string; reason: string }[] }>(
    `/v1/outreach/campaigns/${seg(id)}/drafts`,
    body,
  );

/* ---------- decks ---------- */

export interface DeckShape {
  shape: number;
  name: string;
  text: string;
}
export interface DeckSlide {
  slide: number;
  hidden: boolean;
  title: string;
  shapes: DeckShape[];
}
export interface Deck {
  document_id: UUID;
  title: string;
  version: number;
  filename: string;
  width: number;
  height: number;
  slides: DeckSlide[];
}
export const readDeck = (c: ApiClient, id: string, version?: number) =>
  c.get<Deck>(`/v1/decks/${seg(id)}`, version ? { version } : undefined);
export const saveDeck = (
  c: ApiClient,
  id: string,
  body: { base_version: number; edits: { slide: number; shape: number; text: string }[]; hidden?: number[]; order?: number[]; note?: string },
) => c.post<RoomVersion>(`/v1/decks/${seg(id)}/save`, body);
export const suggestDeck = (c: ApiClient, id: string, body: { instruction: string; investor_id?: string | null }) =>
  c.post<{ suggestions: { slide: number; shape: number; text: string; why: string }[] }>(`/v1/decks/${seg(id)}/suggest`, body);

/* ---------- funding costs ---------- */

export type CostKind = "funding" | "use_of_funds" | "income" | "cost";
export interface CostLine {
  id: UUID;
  kind: CostKind;
  grp: string;
  name: string;
  currency: string;
  amount: number;
  y1: number;
  y2: number;
  y3: number;
  y4: number;
  tranche: "seis" | "eis" | "equity" | "grant" | "other" | null;
  objective: string | null;
  position: number;
}
export interface CostSummary {
  currency: string | null;
  funding_total: number;
  use_of_funds_total: number;
  unallocated: number;
  tranches: Record<string, number>;
  use_of_funds: { id: string; name: string; amount: number; pct: number; objective: string | null }[];
  income: Record<"y1" | "y2" | "y3" | "y4", number>;
  costs: Record<"y1" | "y2" | "y3" | "y4", number>;
  cost_groups: Record<string, Record<"y1" | "y2" | "y3" | "y4", number>>;
  net: Record<"y1" | "y2" | "y3" | "y4", number>;
  total_costs_48m: number;
  total_income_48m: number;
  kpis: { monthly_burn_y1: number; runway_months: number | null; runway_beyond_48m: boolean; funding_gap_48m: number };
}
export const listCosts = (c: ApiClient) => c.get<{ data: CostLine[]; summary: CostSummary }>("/v1/funding-costs");
export const createCost = (c: ApiClient, body: Partial<CostLine>) => c.post<CostLine>("/v1/funding-costs", body);
export const updateCost = (c: ApiClient, id: string, body: Partial<CostLine>) => c.patch<CostLine>(`/v1/funding-costs/${seg(id)}`, body);
export const deleteCost = (c: ApiClient, id: string) => c.del(`/v1/funding-costs/${seg(id)}`);
export const importCosts = (c: ApiClient, file: Blob, currency: string, replace = true) =>
  c.request<{ data: CostLine[]; summary: CostSummary }>("/v1/funding-costs/import", {
    method: "POST",
    query: { currency, replace },
    body: file,
    headers: { "Content-Type": "application/octet-stream" },
  });

/* ---------- Excel / Word import ---------- */

export const convertTables = (c: ApiClient, file: Blob, filename: string) =>
  c.post<{ filename: string; tables: { name: string; header: string[]; rows: number; csv: string }[] }>("/v1/imports/convert", file, {
    headers: { "X-Filename": encodeURIComponent(filename), "Content-Type": "application/octet-stream" },
  });

/* ---------- helpers ---------- */

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** "{first_name}" placeholders the campaign composer supports (mirrors services/outreach.render). */
export const MERGE_FIELDS = ["first_name", "name", "firm", "title", "country", "intro_by"] as const;

export function renderMerge(template: string, inv: { name: string; firm?: string | null; title?: string | null; country?: string | null; warm_intro_by?: string | null }): string {
  const first = inv.name.split(/\s+/)[0] ?? inv.name;
  const values: Record<string, string> = {
    first_name: first,
    name: inv.name,
    firm: inv.firm ?? "",
    title: inv.title ?? "",
    country: inv.country ?? "",
    intro_by: inv.warm_intro_by ?? "",
  };
  return template.replace(/\{(first_name|name|firm|title|country|intro_by)\}/g, (_, k: string) => values[k] ?? "");
}

/** Fetch a file with the session and save it in the browser. Returns the file name. */
export async function saveFile(c: ApiClient, path: string, fallback: string): Promise<string> {
  const res = await c.raw(path, { headers: { Accept: "*/*" } });
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  const plain = /filename="([^"]+)"/i.exec(cd);
  const name = star ? decodeURIComponent(star[1]) : plain ? plain[1] : fallback;
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return name;
}
