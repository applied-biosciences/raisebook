import assert from "node:assert/strict";
import { test } from "node:test";

import { linkedTip, patchAfterLink, patchAfterUnlink } from "./links";

const m = (id: string, name: string, firm: string | null = null) => ({ id, name, firm, title: null, email: null });
const ids = (l: { id: string }[]) => l.map((x) => x.id);

test("patchAfterLink: each member lists the others, sorted by name", () => {
  const p = patchAfterLink("g1", [m("c", "Cara"), m("a", "avi"), m("b", "Ben")]);
  assert.equal(p.size, 3);
  assert.deepEqual(ids(p.get("a")!.linked), ["b", "c"]);
  assert.deepEqual(ids(p.get("b")!.linked), ["a", "c"]);
  assert.deepEqual(ids(p.get("c")!.linked), ["a", "b"]);
  assert.equal(p.get("a")!.group_id, "g1");
});

test("patchAfterUnlink: the leaver has no team; the rest keep theirs", () => {
  const p = patchAfterUnlink("g1", [m("a", "Avi"), m("b", "Ben"), m("c", "Cara")], "b");
  assert.deepEqual(p.get("b"), { group_id: null, linked: [] });
  assert.deepEqual(ids(p.get("a")!.linked), ["c"]);
  assert.deepEqual(ids(p.get("c")!.linked), ["a"]);
  assert.equal(p.get("c")!.group_id, "g1");
});

test("patchAfterUnlink: a team left with one card dissolves", () => {
  const p = patchAfterUnlink("g1", [m("a", "Avi"), m("b", "Ben")], "a");
  assert.deepEqual(p.get("a"), { group_id: null, linked: [] });
  assert.deepEqual(p.get("b"), { group_id: null, linked: [] });
});

test("linkedTip: one, two and three members", () => {
  assert.equal(linkedTip([]), "");
  assert.equal(linkedTip([m("a", "Avi", "Fund One")]), "Linked with Avi (Fund One)");
  assert.equal(linkedTip([m("a", "Avi"), m("b", "Ben")]), "Linked with Avi and Ben");
  assert.equal(linkedTip([m("a", "Avi"), m("b", "Ben"), m("c", "Cara")]), "Linked with Avi, Ben and Cara");
});
