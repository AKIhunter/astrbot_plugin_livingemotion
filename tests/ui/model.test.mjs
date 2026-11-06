import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { normalizeState, normalizeRecords, percent, unit, fieldValue, safeKey, expired, scopeParams, baselineDimensions, energyValue } from "../../pages/livingemotion/model.mjs";
import { createApi, unwrap, pageError } from "../../pages/livingemotion/api.mjs";
import { makeState, nativeDTO, makeRelationships } from "./fixtures.mjs";
import { graphData, NODE_CAP } from "../../pages/livingemotion/charts/relationships.mjs";
import { energyPoints } from "../../pages/livingemotion/charts/energy.mjs";
import { settingsGroups, schedulePreview } from "../../pages/livingemotion/settings.mjs";

test("Bot 状态不会从对方观察补值", () => {
  const raw = makeState(); delete raw.bot_state;
  const data = normalizeState(raw);
  assert.deepEqual(data.bot_state, {});
  assert.equal(data.observation.label, "低落，需要被倾听");
});
test("拒绝版本、越权范围和不合契约的分页", () => {
  assert.throws(() => normalizeState({ api_version: 2 }));
  assert.throws(() => normalizeState({ ...makeState(), context_id: "outside" }));
  assert.throws(() => normalizeRecords({ api_version: 1, items: [], page: 2, page_size: 10, total: 0 }, 1));
  assert.throws(() => normalizeRecords({ api_version: 1, items: Array(11).fill({}), page: 1, page_size: 10, total: 11 }, 1));
  assert.equal(normalizeRecords({ api_version: 1, items: [], page: 1, page_size: 10, total: 0 }, 1).total, 0);
});
test("缺失、非有限和越界值不伪造成零", () => {
  for (const value of [NaN, Infinity, -.1, 1.1, null, undefined, "0.5"]) {
    assert.equal(unit(value), null); assert.equal(percent(value), "未提供");
  }
  assert.equal(percent(0), "0%"); assert.equal(percent(1), "100%");
  assert.equal(expired(1, 2000), true); assert.equal(expired(null), null);
});
test("配置字段白名单与数值校验", () => {
  for (const key of ["__proto__", "a.constructor.b", "<img>", "a.prototype"]) assert.equal(safeKey(key), false);
  assert.equal(safeKey("memory_mode"), true);
  assert.throws(() => fieldValue({ type: "integer", min: 1, max: 10 }, { value: "1.5" }));
  assert.throws(() => fieldValue({ type: "number" }, { value: "" }));
  assert.throws(() => fieldValue({ type: "enum", options: [] }, { value: "admin" }));
  assert.equal(fieldValue({ type: "integer", min: 1, max: 10 }, { value: "10" }), 10);
  assert.equal(fieldValue({ type: "float", step: .1 }, { value: "4.1" }), 4.1);
  assert.throws(() => fieldValue({ type: "float", step: .1 }, { value: "4.15" }));
});
test("实际 Console DTO、float单位、原生任务组单一来源", () => {
  const state = normalizeState(nativeDTO.state);
  assert.equal(state.scope_selection.view_scope, "global");
  assert.equal(state.context_id, "");
  assert.equal(state.night.energy_percent, 74.1);
  assert.equal(baselineDimensions(state).pleasure, .5);
  const missing = makeState(); delete missing.bot_state.baseline;
  assert.deepEqual(baselineDimensions(missing), {});
  const groups = settingsGroups(state.config.fields, state.config);
  const keys = groups.flatMap(group => group.fields.map(field => field.key));
  assert.equal(new Set(keys).size, state.config.fields.length);
  assert.equal(keys.length, state.config.fields.length);
  assert.equal(state.config.fields.find(field => field.key === "energy_reply_cost").type, "float");
  assert.equal(state.config.fields.find(field => field.key === "energy_reply_cost").unit, "点/次");
  assert.equal(state.config.readonly[0].value, 100);
  assert.match(schedulePreview(state.config.values), /恍惚转困 次日 01:00/);
  assert.match(schedulePreview({ fatigue_start: "bad" }), /未完整配置/);
  assert.deepEqual(scopeParams({ persona_id: "p", view_scope: "private", scene_id: "bad", actor_id: "admin" }),
    { persona_id: "p", view_scope: "private" });
});
test("关系真实DTO、平台同号隔离与200裁剪；能量不补缺失点", () => {
  const result = graphData(nativeDTO.relationships);
  assert.equal(result.items.length, 10);
  assert.equal(new Set(result.nodes.map(item => item.id)).size, result.nodes.length);
  const nodes = makeRelationships();
  assert.notEqual(nodes[0].id, nodes[1].id);
  const capped = graphData({ api_version: 1, nodes, edges: [], items: nodes.slice(0, 10), total: nodes.length, page_size: 10 });
  assert.equal(capped.nodes.length, NODE_CAP);
  const empty = energyPoints(nativeDTO.energy);
  assert.equal(empty.collected, false); assert.deepEqual(empty.points, []);
  assert.equal(energyValue(null), null); assert.equal(energyValue(100), 100);
  assert.throws(() => energyPoints({ ...nativeDTO.energy, page_size: 11 }));
});
test("宿主响应包装、401、403和409保留语义", () => {
  assert.deepEqual(unwrap({ status: "ok", data: { api_version: 1 } }), { api_version: 1 });
  assert.deepEqual(unwrap({ ok: true, data: { api_version: 1 } }), { api_version: 1 });
  assert.equal(pageError({ status: 401 }).code, "unauthorized");
  assert.equal(pageError({ status: 403 }).code, "forbidden");
  assert.equal(pageError(new Error("[livingemotion:forbidden] 资产令牌不是管理身份")).code, "forbidden");
  assert.equal(pageError(new Error("[livingemotion:version_conflict] 请重新读取")).code, "version_conflict");
  assert.equal(pageError(new Error("Request failed with status code 401")).code, "unauthorized");
  assert.equal(pageError(new Error("Token has expired")).code, "bridge_error");
  assert.throws(() => unwrap({ status: 409 }), error => error.code === "version_conflict");
});
test("只走宿主桥；模拟与动作路径分离，写请求超时不重试", async () => {
  const calls = [];
  const api = createApi(() => ({
    apiGet: async (...args) => { calls.push(["GET", ...args]); return { api_version: 1 }; },
    apiPost: async (...args) => { calls.push(["POST", ...args]); return { api_version: 1 }; },
  }));
  await api.state("scope"); await api.records({ page: 1 }); await api.preview("scope");
  await api.action({ action: "night.sleep" });
  assert.deepEqual(calls.map(item => item[1]), ["console/state", "console/records", "console/preview", "console/action"]);
  assert.equal(calls.some(item => JSON.stringify(item).includes("admin")), false);
  let attempts = 0;
  const stuck = createApi(() => ({ apiPost: () => { attempts++; return new Promise(() => {}); } }), 10);
  await assert.rejects(stuck.action({}), error => error.code === "timeout");
  assert.equal(attempts, 1);
  await assert.rejects(createApi(() => null).state(""), error => error.code === "missing_bridge");
});
test("生产页面无注入 sink、外部资源、fixture 或直接网络调用，主题在 CSS 前", async () => {
  const base = new URL("../../pages/livingemotion/", import.meta.url);
  const html = await readFile(new URL("index.html", base), "utf8");
  const scripts = (await Promise.all(["app.mjs", "model.mjs", "api.mjs", "theme.js"].map(name => readFile(new URL(name, base), "utf8")))).join("\n");
  assert.doesNotMatch(scripts, /\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write|\beval\(|\bfetch\(|XMLHttpRequest|postMessage\(/);
  assert.equal(/https?:\/\/|fixture-bridge|fixtures\.mjs/.test((html + scripts).replaceAll("http://www.w3.org/2000/svg", "")), false);
  assert.ok(html.indexOf('src="./theme.js"') < html.indexOf('href="./style.css"'));
  assert.ok(html.includes('src="/api/plugin/page/bridge-sdk.js"'));
});
