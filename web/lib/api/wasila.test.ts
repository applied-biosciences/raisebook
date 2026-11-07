import assert from "node:assert/strict";
import { test } from "node:test";

import { fileSize, missingFigures, renderMerge, UPDATE_TEMPLATE } from "./wasila";

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

test("investor updates fill in the funding figures and flag the missing ones", () => {
  const figures = [
    { key: "raise_total", label: "Total raise", value: "\u00a32,000,000" },
    { key: "runway", label: "Runway", value: "" },
  ];
  assert.equal(
    renderMerge("{first_name}: {raise_total}, {runway} runway", { name: "Ada Sample" }, figures),
    "Ada: \u00a32,000,000,  runway",
  );
  assert.deepEqual(
    missingFigures("{raise_total} {runway}", figures).map((f) => f.key),
    ["runway"],
  );
  assert.ok(UPDATE_TEMPLATE.includes("{raise_total}"));
});
