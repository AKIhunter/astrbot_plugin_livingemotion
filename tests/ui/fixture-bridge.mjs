import { makeState, makeRecords, ATTACK } from "./fixtures.mjs";

const scenario = new URLSearchParams(location.search).get("scenario") || "normal";
const calls = [];
let data = makeState();
let rejectedSave = false;
const clone = value => structuredClone(value);
const fail = (code, message) => Promise.reject(Object.assign(new Error(message), { code }));
if (scenario === "malicious") {
  data.bot_state.label = ATTACK; data.bot_state.reason = ATTACK; data.observation.label = ATTACK;
  data.persona.description = ATTACK; data.config.fields[0].label = ATTACK;
}
if (scenario === "missing-state") { data.bot_state = null; data.observation.label = "只有对方观察，不能变成 Bot 感受"; }
if (scenario === "no-context") { data.contexts = []; data.context_id = ""; }
if (scenario === "no-capabilities") { data.capabilities = []; data.actions = []; }
if (scenario === "invalid-numbers") {
  data.bot_state.dimensions = { pleasure: NaN, arousal: Infinity, stress: -.1, social_need: 2 };
  data.night.energy = null;
}
if (scenario === "malformed-optional") {
  data.health = [null, { name: "无效状态", status: "__proto__" }];
  data.config.fields[0].options.unshift(null);
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
      if (params.context_id) data.context_id = params.context_id;
      return { status: "ok", data: clone(data) };
    }
    if (path === "console/records") {
      if (scenario === "records-denied") return fail("unauthorized", "合成过期会话");
      if (scenario === "records-error") return fail("unavailable", "合成记录错误");
      let items = scenario === "empty" ? [] : makeRecords(params.kind);
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
      if (scenario === "conflict" && !rejectedSave) {
        rejectedSave = true; data.config.revision = "config-2";
        return fail("version_conflict", "原生配置已在别处修改");
      }
      if (payload.expected_revision !== data.config.revision) return fail("version_conflict", "配置版本冲突");
      Object.assign(data.config.values, payload.patch); data.config.revision += "-saved";
      return { status: "ok", data: clone(data) };
    }
    if (path === "console/preview") return { status: "ok", data: {
      api_version: 1, eligible: false, reasons: ["autonomy_disabled", "observe_only"],
      model_calls: 0, sends: 0, candidates: clone(data.behavior.candidates),
    } };
    if (path === "console/action") return { status: "ok", data: {
      api_version: 1, status: scenario === "action-unknown" ? "unknown" : "succeeded",
      reason: "只返回测试回执，无模型、存储或发送端", request_id: "fixture-action-1",
    } };
    return fail("not_found", "不存在的合成路由");
  },
};
Object.defineProperty(window, "__fixture", { value: { calls, get state() { return clone(data); } } });
if (scenario !== "missing-bridge") window.AstrBotPluginView = bridge;
document.title = `[合成测试] ${document.title}`;
