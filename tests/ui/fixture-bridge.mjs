import { makeState, makeRecords, makeScopes, makeRelationships, makePeerEdges, makeEnergy, nativeDTO, ATTACK } from "./fixtures.mjs";

const scenario = new URLSearchParams(location.search).get("scenario") || "normal";
const calls = [];
let data = scenario === "native-dto" ? structuredClone(nativeDTO.state) : makeState();
let rejectedSave = false;
let rejectedRelationship = false;
const relationships = makeRelationships();
const pins = new Map();
const clone = value => structuredClone(value);
const fail = (code, message) => Promise.reject(Object.assign(new Error(message), { code }));
const configKey = `livingemotion.synthetic.config.${scenario}`;
try {
  const saved = JSON.parse(sessionStorage.getItem(configKey) || "null");
  if (saved) { data.config = saved; data.state_mode = saved.values.persona_shared_state ? "persona" : "scene"; }
} catch (_) { /* Test fixture also covers denied storage. */ }
if (scenario === "malicious") {
  data.bot_state.label = ATTACK; data.bot_state.reason = ATTACK; data.observation.label = ATTACK;
  data.persona.description = ATTACK; data.config.fields[0].label = ATTACK;
}
if (scenario === "missing-state") { data.bot_state = null; data.observation.label = "只有对方观察，不能变成 Bot 感受"; }
if (scenario === "no-context") { data.contexts = []; data.context_id = ""; data.selection = {}; }
if (scenario === "no-capabilities") { data.capabilities = []; data.actions = []; }
if (scenario === "invalid-numbers") {
  data.bot_state.dimensions = { pleasure: NaN, arousal: Infinity, stress: -.1, social_need: 2 };
  data.night.energy = null;
}
if (scenario === "missing-baseline") delete data.bot_state.baseline;
if (scenario === "malformed-optional") {
  data.health = [null, { name: "无效状态", status: "__proto__" }];
  data.config.fields.find(item => item.key === "mode").options.unshift(null);
}
if (scenario === "host-theme") document.documentElement.setAttribute("data-theme", "dark");
const bridge = {
  async apiGet(path, params) {
    calls.push({ method: "GET", path, payload: clone(params) });
    if (scenario === "unauthorized") return fail("unauthorized", "合成 401");
    if (scenario === "message-only-auth") throw new Error("[livingemotion:forbidden] 资产令牌不能访问管理 API");
    if (scenario === "untyped-auth") throw new Error("Token has expired");
    if (scenario === "forbidden") return fail("forbidden", "合成 403");
    if (path === "console/state") {
      if (scenario === "loading") await new Promise(resolve => setTimeout(resolve, 500));
      if (scenario === "refresh-error" && calls.filter(call => call.path === path).length > 1) return fail("unavailable", "合成刷新失败");
      if (params.persona_id && scenario !== "native-dto") {
        data.selection = { ...params }; data.persona.id = params.persona_id;
        data.context_id = params.view_scope === "global" ? "" : params.context_id || (params.view_scope === "group" ? "fixture-b" : "fixture-a");
        data.representative_context_id = params.view_scope === "global" ? "fixture-a" : data.context_id;
      } else if (params.context_id) { data.context_id = params.context_id; data.selection.context_id = params.context_id; }
      return { status: "ok", data: clone(data) };
    }
    if (path === "console/scopes") return { status: "ok", data: scenario === "native-dto" ? clone(nativeDTO.scopes) :
      scenario === "no-context" ? { api_version: 1, personas: [], platforms: [], contexts: [] } : makeScopes() };
    if (path === "console/settings-options") return { status: "ok", data: {
      api_version: 1, personas: makeScopes().personas.map(item => ({ value: item.id, label: item.name })),
      chat_providers: [{ value: "fixture-chat", label: "合成聊天模型（不调用）" }],
      embedding_providers: [{ value: "fixture-embedding", label: "合成向量模型（不调用）" }], groups: [],
    } };
    if (path === "console/relationships") {
      if (scenario === "relationships-error") return fail("unavailable", "合成关系读取失败");
      if (scenario === "native-dto") return { status: "ok", data: clone(nativeDTO.relationships) };
      if (scenario === "relationship-race" && params.query === "old") await new Promise(resolve => setTimeout(resolve, 250));
      let filtered = scenario === "empty" ? [] : relationships.filter(item =>
        (!params.platform || params.platform === item.platform) && (!params.query || `${item.account_id} ${item.label}`.includes(params.query)));
      const nodes = filtered.slice(0, params.limit || 200);
      return { status: "ok", data: { api_version: 1, center: { id: "center", persona_id: params.persona_id },
        nodes: clone(nodes), edges: nodes.map(item => ({ source: "center", target: item.id })),
        peer_edges: scenario === "legacy-relationships" ? undefined : makePeerEdges(relationships)
          .filter(edge => nodes.some(n => n.id === edge.source) && nodes.some(n => n.id === edge.target)),
        items: clone(filtered.slice((params.page - 1) * 10, params.page * 10)), total: filtered.length, displayed: nodes.length, page: params.page, page_size: 10 } };
    }
    if (path === "console/energy") {
      if (scenario === "energy-error") return fail("unavailable", "合成精力读取失败");
      if (scenario === "native-dto") return { status: "ok", data: clone(nativeDTO.energy) };
      const energy = makeEnergy();
      if (scenario === "energy-series") {
        energy.series_total = 2;
        energy.points = energy.points.map((point, i) => ({ ...point, owner_key: i % 2 ? "owner-a" : "owner-b",
          min: point.energy - 1, max: point.energy + 1 }));
      }
      let items = scenario === "empty" ? [] : energy.items.filter(item => !params.event_type || item.kind === params.event_type);
      return { status: "ok", data: { ...energy, collected: scenario !== "empty", points: scenario === "empty" ? [] : energy.points,
        items: items.slice((params.page - 1) * 10, params.page * 10), total: items.length, page: params.page, page_size: 10 } };
    }
    if (path === "console/records") {
      if (scenario === "records-denied") return fail("unauthorized", "合成过期会话");
      if (scenario === "records-error") return fail("unavailable", "合成记录错误");
      let items = scenario === "empty" ? [] : makeRecords(params.kind);
      items.forEach(item => { if (pins.has(item.id)) item.pinned = pins.get(item.id); });
      if (scenario === "malicious") items.forEach(item => {
        item.title = ATTACK; item.reason = ATTACK; item.body = ATTACK;
        item.context = ATTACK; item.sources[0].excerpt = ATTACK;
      });
      if (params.query) items = items.filter(item => JSON.stringify(item).includes(params.query));
      const page = {
        api_version: 1, items: items.slice((params.page - 1) * 10, params.page * 10),
        total: items.length, page: params.page, page_size: 10,
      };
      if (scenario === "bad-pagination") page.page_size = 20;
      return { status: "ok", data: page };
    }
    return fail("not_found", "不存在的合成路由");
  },
  async apiPost(path, payload) {
    calls.push({ method: "POST", path, payload: clone(payload) });
    if (path === "console/config") {
      if (Object.keys(payload).some(key => !["context_id", "expected_revision", "patch", "reason"].includes(key))) {
        return fail("validation_error", "配置不能携带 ScopeSelection 额外字段");
      }
      if (scenario === "conflict" && !rejectedSave) {
        rejectedSave = true; data.config.revision = "config-2";
        return fail("version_conflict", "原生配置已在别处修改");
      }
      if (payload.expected_revision !== data.config.revision) return fail("version_conflict", "配置版本冲突");
      Object.assign(data.config.values, payload.patch); data.config.revision += "-saved";
      data.state_mode = data.config.values.persona_shared_state ? "persona" : "scene";
      try { sessionStorage.setItem(configKey, JSON.stringify(data.config)); } catch (_) {}
      return { status: "ok", data: clone(data) };
    }
    if (path === "console/relationship") {
      if (Object.keys(payload).some(key => !["persona_id", "context_id", "platform", "account_id", "score", "frozen", "expected_version", "reason"].includes(key))) {
        return fail("validation_error", "非法关系字段");
      }
      if (scenario === "relationship-unknown") return fail("unavailable", "合成写入结果无法确认");
      const item = relationships.find(item => item.platform === payload.platform && item.account_id === payload.account_id);
      if (!item) return fail("validation_error", "合成账号不存在");
      if (scenario === "relationship-conflict" && !rejectedRelationship) {
        rejectedRelationship = true; item.version++; item.score = 47.8; return fail("version_conflict", "关系已在别处修改");
      }
      if (payload.expected_version !== item.version) return fail("version_conflict", "关系版本变化");
      item.score = payload.score; item.raw = payload.score * 10; item.frozen = payload.frozen; item.version++;
      return { status: "ok", data: { api_version: 1, node: clone(item), version: item.version } };
    }
    if (path === "console/preview") return { status: "ok", data: {
      api_version: 1, eligible: false, reasons: ["autonomy_disabled", "observe_only"],
      model_calls: 0, sends: 0, candidates: clone(data.behavior.candidates),
    } };
    if (path === "console/action") {
      if (payload.action === "experience.pin") {
        if (scenario === "pin-conflict") return fail("version_conflict", "置顶已被修改，请刷新");
        if ((pins.get(payload.entry_id) || false) !== payload.expected_pinned) {
          return fail("version_conflict", "置顶记录已变化");
        }
        pins.set(payload.entry_id, payload.pinned);
        return { status: "ok", data: { api_version: 1, status: "updated",
          reason_code: "pin_updated", model_calls: 0, sends: 0 } };
      }
      return { status: "ok", data: {
        api_version: 1, status: scenario === "action-unknown" ? "unknown" : "succeeded",
        reason: "只返回测试回执，无模型、存储或发送端", request_id: "fixture-action-1",
      } };
    }
    return fail("not_found", "不存在的合成路由");
  },
};
Object.defineProperty(window, "__fixture", { value: { calls, get state() { return clone(data); } } });
if (scenario !== "missing-bridge") window.AstrBotPluginView = bridge;
document.title = `[合成测试] ${document.title}`;
