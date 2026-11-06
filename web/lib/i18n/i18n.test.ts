import assert from "node:assert/strict";
import { test } from "node:test";

import { dirFor, missingKeys, normalizeLocale, translate } from "./index";

test("locales normalize to en or ar", () => {
  assert.equal(normalizeLocale("ar"), "ar");
  assert.equal(normalizeLocale("fr"), "en");
  assert.equal(normalizeLocale(undefined), "en");
});

test("Arabic is right-to-left", () => {
  assert.equal(dirFor("ar"), "rtl");
  assert.equal(dirFor("en"), "ltr");
});

test("Arabic falls back to English until translated", () => {
  assert.equal(translate("ar", "common.appName"), "وسيلة");
  assert.equal(translate("ar", "settings.language.title"), "Language");
  assert.ok(missingKeys("ar").includes("settings.language.title"));
  assert.equal(missingKeys("en").length, 0);
});
