/**
 * Linked cards (SPEC §3.10): two or more investor cards linked as one team. Pure rules for
 * what each card's `linked` list becomes after a link or an unlink, so the board, the table and
 * the sheet update in place without re-reading the round. Unit-tested.
 */

import type { InvestorLinks, LinkedInvestorBrief, UUID } from "./api/types";

/** What changed on each affected card: its team id and the other members. */
export type LinkPatch = Map<UUID, Required<InvestorLinks>>;

/** The API's order: by name (then id, so equal names stay put). */
export function byName(a: LinkedInvestorBrief, b: LinkedInvestorBrief): number {
  return a.name.localeCompare(b.name, undefined, { sensitivity: "base" }) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
}

/** The brief a card shows for another member. */
export function briefOf(i: LinkedInvestorBrief): LinkedInvestorBrief {
  return { id: i.id, name: i.name, firm: i.firm ?? null, title: i.title ?? null, email: i.email ?? null };
}

/**
 * After `POST /links`: every member of the (possibly merged) team lists the others.
 * `members` is the response's `investors` (this investor included).
 */
export function patchAfterLink(groupId: UUID, members: LinkedInvestorBrief[]): LinkPatch {
  const out: LinkPatch = new Map();
  const all = members.map(briefOf).sort(byName);
  for (const m of all) out.set(m.id, { group_id: groupId, linked: all.filter((x) => x.id !== m.id) });
  return out;
}

/**
 * After `DELETE /links` on `leaving`: it has no team; the rest keep theirs, unless one card is
 * left, when the team dissolves. `team` is every member before the unlink (`leaving` included).
 */
export function patchAfterUnlink(groupId: UUID | null, team: LinkedInvestorBrief[], leaving: UUID): LinkPatch {
  const out: LinkPatch = new Map();
  out.set(leaving, { group_id: null, linked: [] });
  const rest = team.filter((m) => m.id !== leaving).map(briefOf).sort(byName);
  const dissolved = rest.length < 2 || !groupId;
  for (const m of rest)
    out.set(m.id, dissolved ? { group_id: null, linked: [] } : { group_id: groupId, linked: rest.filter((x) => x.id !== m.id) });
  return out;
}

/** "Bruce Lee (Acme)": a member as a line in a tip or a label. */
export function memberLabel(m: Pick<LinkedInvestorBrief, "name" | "firm">): string {
  return m.firm ? `${m.name} (${m.firm})` : m.name;
}

/** "Linked with Bruce Lee (Acme) and Dana Wu": the chip's tooltip and accessible name. */
export function linkedTip(linked: readonly LinkedInvestorBrief[]): string {
  const names = linked.map(memberLabel);
  if (names.length === 0) return "";
  if (names.length === 1) return `Linked with ${names[0]}`;
  return `Linked with ${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
