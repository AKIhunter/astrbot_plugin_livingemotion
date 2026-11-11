import assert from "node:assert/strict";
import test from "node:test";
import { reconcileDraft } from "../../pages/livingemotion/draft.mjs";

test("无关字段的修改可合并，只提交本页草稿", () => {
  const result = reconcileDraft({ diary: true }, { diary: false, dream: false },
    { diary: false, dream: true }, new Set(["diary", "dream"]));
  assert.deepEqual({ ...result.patch }, { diary: true });
  assert.deepEqual(result.conflicts, []);
});
test("同字段不同修改需复核，已应用的修改和失去权限的字段不再提交", () => {
  const result = reconcileDraft({ mode: "active", diary: true, removed: "old" },
    { mode: "observe_only", diary: false }, { mode: "disabled", diary: true },
    new Set(["mode", "diary"]));
  assert.deepEqual({ ...result.patch }, { mode: "active" });
  assert.deepEqual(result.conflicts, [{ key: "mode", current: "disabled", draft: "active" }]);
});
test("复核后又发生新修改时仍报告冲突，未知基线保守复核", () => {
  const allowed = new Set(["value"]);
  assert.equal(reconcileDraft({ value: "mine" }, { value: "reviewed" },
    { value: "newer" }, allowed).conflicts.length, 1);
  assert.equal(reconcileDraft({ value: "mine" }, {},
    { value: "newer" }, allowed).conflicts.length, 1);
});
