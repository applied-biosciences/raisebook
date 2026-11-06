import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { HOME_FAQ, MORE_FAQ } from "./faq";
import { llmsFullTxt, llmsTxt } from "./llms";
import { PAGES, crumbs, ogSlug, pageForOgSlug } from "./pages";
import { breadcrumbList, faqPage, softwareApplication } from "./schema";

const MARKETING = join(process.cwd(), "app/(marketing)");

function pageFile(path: string): boolean {
  if (path === "/") return existsSync(join(MARKETING, "page.tsx"));
  return existsSync(join(MARKETING, path.slice(1), "page.tsx"));
}

test("every registered page exists, once, with a unique share card", () => {
  const paths = PAGES.map((p) => p.path);
  assert.equal(new Set(paths).size, paths.length);
  const slugs = PAGES.map((p) => ogSlug(p.path));
  assert.equal(new Set(slugs).size, slugs.length);
  for (const p of PAGES) {
    assert.ok(pageFile(p.path), `no page file for ${p.path}`);
    assert.equal(pageForOgSlug(ogSlug(p.path))?.path, p.path);
    assert.match(p.updated, /^\d{4}-\d{2}-\d{2}$/);
    // Search results cut descriptions past ~160 characters and titles past ~60.
    assert.ok(p.description.length >= 120 && p.description.length <= 160, `${p.path} description length ${p.description.length}`);
    const title = p.absoluteTitle ?? `${p.title} · Wasila${p.section === "docs" && p.path !== "/docs" ? " docs" : ""}`;
    assert.ok(title.length <= 60, `${p.path} title length ${title.length}`);
  }
});

test("breadcrumbs walk from home through registered parents", () => {
  assert.deepEqual(
    crumbs("/docs/mcp").map((c) => c.path),
    ["/", "/docs", "/docs/mcp"],
  );
  assert.deepEqual(crumbs("/docs/mcp").map((c) => c.name), ["Home", "Docs", "Connect an agent (MCP)"]);
  const list = breadcrumbList("/docs/mcp") as { itemListElement: { position: number; item: string }[] };
  assert.deepEqual(list.itemListElement.map((i) => i.position), [1, 2, 3]);
  assert.match(list.itemListElement[2].item, /\/docs\/mcp$/);
});

test("structured data stays factual: no price claims, ratings or reviews", () => {
  const app = softwareApplication() as { offers?: unknown };
  assert.equal(app.offers, undefined);
  const json = JSON.stringify([app, faqPage(HOME_FAQ, "/")]);
  assert.doesNotMatch(json, /aggregateRating|"review"|ratingValue/);
});

test("FAQ structured data matches the visible questions", () => {
  const all = [...HOME_FAQ, ...MORE_FAQ.flatMap((g) => g.items)];
  const qs = all.map((f) => f.q);
  assert.equal(new Set(qs).size, qs.length, "duplicate question");
  const data = faqPage(HOME_FAQ, "/") as { mainEntity: { name: string; acceptedAnswer: { text: string } }[] };
  assert.deepEqual(
    data.mainEntity.map((m) => m.name),
    HOME_FAQ.map((f) => f.q),
  );
  assert.equal(data.mainEntity[0].acceptedAnswer.text, HOME_FAQ[0].a);
});

test("llms.txt states the facts and links every listed page", () => {
  const txt = llmsTxt();
  assert.match(txt, /^# Wasila\n\n> /);
  for (const fact of ["Funding Room", "SEIS/EIS", "Saudi Arabia", "20,000 investors", "50 rounds", "AGPL-3.0", "Google Calendar", "/v1", "26 tools"]) {
    assert.ok(txt.includes(fact), `llms.txt is missing ${fact}`);
  }
  for (const p of PAGES.filter((x) => x.llms)) assert.ok(txt.includes(`(https://wasila.app${p.path === "/" ? "" : p.path})`), p.path);
  const full = llmsFullTxt();
  assert.doesNotMatch(full, new RegExp(["rai", "sebook"].join(""), "i"));
  assert.doesNotMatch(full, /\bcustomers love\b|\btrusted by\b|\bstars?\b rating/i);
});
