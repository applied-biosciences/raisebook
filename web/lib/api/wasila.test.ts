import assert from "node:assert/strict";
import { test } from "node:test";

import { fileSize, renderMerge } from "./wasila";

test("mail merge mirrors the server placeholders", () => {
  const out = renderMerge("Hi {first_name}, {firm} via {intro_by}{unknown}", {
    name: "Ada Sample",
    firm: "North Fund",
    warm_intro_by: "Sam",
  });
  assert.equal(out, "Hi Ada, North Fund via Sam{unknown}");
});

test("file sizes read in plain units", () => {
  assert.equal(fileSize(900), "900 B");
  assert.equal(fileSize(2048), "2 KB");
  assert.equal(fileSize(3 * 1024 * 1024), "3.0 MB");
});
