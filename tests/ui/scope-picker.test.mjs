import assert from "node:assert/strict";
import test from "node:test";
import { personSceneLabel, personSuggestions, scopeSuggestions, SCOPE_SUGGESTION_LIMIT } from "../../pages/livingemotion/scope-picker.mjs";

const conversation = (id, view_scope, scene_id, account_id, nickname) => ({
  id, scope_key: `scope-${id}`, persona_id: "fixture-persona", platform: "qq", view_scope, scene_id,
  account_id, nickname, label: `QQ / ${account_id}`, person_id: `person-${account_id}`,
});
// 同一 QQ（80001）同时有私聊和两个群；另外两个 QQ 各只有一种会话。
const contexts = [
  conversation("priv", "private", "", "80001", "合成对象甲"),
  conversation("g1", "group", "g1", "80001", "合成对象甲"),
  conversation("g2", "group", "g2", "80001", "合成对象甲"),
  conversation("b", "group", "g1", "80002", "合成对象乙"),
  conversation("c", "private", "", "80003", "合成对象丙"),
];

test("用户维度：同一 QQ 的私聊与各群合成一项，落在最近更新的会话", () => {
  const items = personSuggestions(contexts, "fixture-persona");
  assert.deepEqual(items.map(item => item.id), ["person-80001", "person-80002", "person-80003"]);
  assert.equal(items[0].view_scope, "private");
  assert.equal(items[0].platform, "qq");
  // 其他人格或没有人级键的旧数据不进入候选。
  assert.deepEqual(personSuggestions([{ ...contexts[0], persona_id: "other" }, { ...contexts[1], person_id: "" }],
    "fixture-persona"), []);
});

test("用户维度：选项文案标出私聊与群聊数量", () => {
  const items = personSuggestions(contexts, "fixture-persona");
  assert.deepEqual(items.map(personSceneLabel), ["私聊 + 2 个群聊", "1 个群聊", "私聊"]);
});

test("用户维度：按昵称过滤，账号精确匹配排第一", () => {
  assert.deepEqual(personSuggestions(contexts, "fixture-persona", "合成对象乙").map(item => item.account_id), ["80002"]);
  assert.equal(personSuggestions(contexts, "fixture-persona", "80003")[0].account_id, "80003");
});

test("用户维度：候选最多十条", () => {
  const many = Array.from({ length: 12 }, (_, index) => conversation(`c${index}`, "private", "", `${90000 + index}`, `对象${index}`));
  const items = personSuggestions(many, "fixture-persona");
  assert.equal(items.length, SCOPE_SUGGESTION_LIMIT);
  assert.equal(items[0].account_id, "90000");
});

test("会话维度：仍是一会话一项", () => {
  assert.deepEqual(scopeSuggestions(contexts, "fixture-persona").map(item => item.id), ["priv", "c", "g1", "g2", "b"]);
});
