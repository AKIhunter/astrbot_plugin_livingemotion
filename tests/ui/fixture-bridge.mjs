import { makeState, makeRecords, makeScopes, makeRelationships, makePeerEdges, makeEnergy, nativeDTO, ATTACK } from "./fixtures.mjs";

const scenario = new URLSearchParams(location.search).get("scenario") || "normal";
const calls = [];
let denyAccess = false;
let data = scenario === "native-dto" || scenario.startsWith("save-") ? structuredClone(nativeDTO.state) : makeState();
let rejectedSave = false;
let rejectedRelationship = false;
const relationships = makeRelationships();
const pins = new Map();
const clone = value => structuredClone(value);
const fail = (code, message) => Promise.reject(Object.assign(new Error(message), { code }));
const configKey = `livingemotion.synthetic.config.${scenario}`;
const dailyScenario = scenario.startsWith("daily");
const fastScenario = scenario.startsWith("save-fast");
if (fastScenario) {
  data.capabilities.push("configuration.read", "config.receipt");
  data.config.values.relationship_stage_descriptions = '["","","",""]';
  data.config.fields.push({ key: "relationship_stage_descriptions", label: "关系阶段描述",
    type: "string", section: "relationship", help: "留空沿用默认", details: "每项最多1000字", example: '["","","",""]' });
  data.config.groups.find(group => group.id === "relationship")?.field_keys.push("relationship_stage_descriptions");
}
if (["relationship-conflict", "relationship-unknown", "relation-scope"].includes(scenario)) {
  data.config.values.relationship_edit_enabled = true;
}
const jobKey = `livingemotion.synthetic.jobs.${scenario}`;
let jobs = {};
try { jobs = JSON.parse(sessionStorage.getItem(jobKey) || "{}"); } catch (_) {}
function persistJobs() { sessionStorage.setItem(jobKey, JSON.stringify(jobs)); }
if (dailyScenario) {
  data.experience = { persona_id: "fixture-persona", day: "2026-11-09", timezone: "Asia/Shanghai",
    diary: { status: "idle" }, dream: { status: "idle" } };
  data.actions.filter(a => /^(diary|dream)\.generate$/.test(a.id)).forEach(a => {
    a.enabled = true; a.reason = "";
  });
  for (const job of Object.values(jobs)) data.experience[job.kind] = clone(job);
}
try {
  const saved = JSON.parse(sessionStorage.getItem(configKey) || "null");
  if (saved) { data.config = saved; data.state_mode = saved.values.persona_shared_state ? "persona" : "scene"; }
} catch (_) { /* Test fixture also covers denied storage. */ }
if (scenario === "malicious") {
  data.bot_state.label = ATTACK; data.bot_state.reason = ATTACK; data.observation.label = ATTACK;
  data.persona.description = ATTACK; data.config.fields[0].label = ATTACK;
}
if (scenario === "missing-state") { data.bot_state = null; data.observation.label = "只有对方观察，不能变成 Bot 感受"; }
if (scenario === "no-context") { data.contexts = []; data.context_id = ""; data.selection = {}; data.experience = {}; }
if (scenario === "model-diagnostics") {
  data.emotion_model_analysis = { status: "completed", reason_code: "completed", applied: true,
    queued_at: 1793959200, started_at: 1793959201, finished_at: 1793959202 };
  data.behavior_model = { available: true, reason_code: "ready" };
}
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
    if (scenario === "unauthorized" || denyAccess) return fail("unauthorized", "合成 401");
    if (scenario === "message-only-auth") throw new Error("[livingemotion:forbidden] 资产令牌不能访问管理 API");
    if (scenario === "untyped-auth") throw new Error("Token has expired");
    if (scenario === "forbidden") return fail("forbidden", "合成 403");
    if (dailyScenario && path === "console/experience-task") {
      const job = jobs[params.request_id];
      if (!job) return fail("validation_error", "当前人格下没有这个生成请求");
      if (job.status === "queued") {
        job.status = scenario === "daily-unknown" ? "unknown" : "succeeded";
        job.reason_code = job.status === "unknown" ? "model_result_unknown" : "private_archive_updated";
        job.experience_id = `daily-${job.kind}`;
        persistJobs();
      }
      data.experience[job.kind] = clone(job);
      return { status: "ok", data: clone(job) };
    }
    if (path === "console/state") {
      if (scenario === "loading") await new Promise(resolve => setTimeout(resolve, 500));
      if (scenario === "refresh-error" && calls.filter(call => call.path === path).length > 1) return fail("unavailable", "合成刷新失败");
      if (scenario === "save-read-error" && calls.filter(call => call.path === path).length > 1) return fail("timeout", "合成预读超时");
      if (params.persona_id && scenario !== "native-dto" && !scenario.startsWith("save-")) {
        data.selection = { ...params }; data.persona.id = params.persona_id;
        data.context_id = params.view_scope === "global" ? "" : params.context_id || (params.view_scope === "group" ? "fixture-b" : "fixture-a");
        data.representative_context_id = params.view_scope === "global" ? "fixture-a" : data.context_id;
      } else if (params.context_id) { data.context_id = params.context_id; data.selection.context_id = params.context_id; }
      return { status: "ok", data: clone(data) };
    }
    if (path === "console/configuration") {
      if (!fastScenario) return fail("not_found", "旧宿主未开放配置读取");
      if (scenario === "save-fast-read-error") return fail("timeout", "合成预读超时");
      return { status: "ok", data: { api_version: 1, config: clone(data.config) } };
    }
    if (path === "console/scopes") return { status: "ok", data: scenario === "native-dto" || scenario.startsWith("save-") ? clone(nativeDTO.scopes) :
      scenario === "no-context" ? { api_version: 1, personas: [], platforms: [], contexts: [] } : makeScopes() };
    if (path === "console/settings-options") return { status: "ok", data: {
      api_version: 1, personas: makeScopes().personas.map(item => ({ value: item.id, label: item.name })),
      chat_providers: [{ value: "fixture-chat", label: "合成聊天模型（不调用）" }],
      embedding_providers: [{ value: "fixture-embedding", label: "合成向量模型（不调用）" }], groups: [],
    } };
    if (path === "console/persona-description") {
      if (!params?.persona_id) return fail("validation_error", "缺少 persona_id");
      const description = scenario === "malicious" ? ATTACK :
        `合成人格说明：${params.persona_id}。\n\n${"第二段用于测试三行折叠与展开，不包含真实人格内容。".repeat(3)}`;
      return { status: "ok", data: { api_version: 1, persona_id: params.persona_id,
        description, characters: description.length, available: true } };
    }
    if (path === "console/emotion-images") return { status: "ok", data: { api_version: 1, moods: [] } };
    if (path === "console/relationships") {
      if (scenario === "relationships-error") return fail("unavailable", "合成关系读取失败");
      if (scenario === "native-dto") return { status: "ok", data: clone(nativeDTO.relationships) };
      if (scenario === "relationship-race" && params.query === "old") await new Promise(resolve => setTimeout(resolve, 250));
      let filtered = scenario === "empty" ? [] : relationships.filter(item =>
        (!params.platform || params.platform === item.platform) && (!params.query || `${item.account_id} ${item.label}`.includes(params.query)));
      const focusIds = new Set(filtered.map(item => item.id)), neighborIds = new Set(focusIds);
      if (params.query && params.graph_scope === "neighbors") for (const edge of makePeerEdges(relationships)) {
        if (focusIds.has(edge.source)) neighborIds.add(edge.target);
        if (focusIds.has(edge.target)) neighborIds.add(edge.source);
      }
      const candidates = params.query && params.graph_scope === "neighbors" ?
        [...filtered, ...relationships.filter(item => !focusIds.has(item.id) && neighborIds.has(item.id) &&
          (!params.platform || params.platform === item.platform))] : filtered;
      const nodes = candidates.slice(0, params.limit || 200);
      return { status: "ok", data: { api_version: 1, center: { id: "center", persona_id: params.persona_id },
        nodes: clone(nodes), edges: nodes.map(item => ({ source: "center", target: item.id })),
        peer_edges: scenario === "legacy-relationships" ? undefined : makePeerEdges(relationships)
          .filter(edge => nodes.some(n => n.id === edge.source) && nodes.some(n => n.id === edge.target)),
        items: clone(filtered.slice((params.page - 1) * 10, params.page * 10)), total: filtered.length,
        graph_total: candidates.length, truncated: candidates.length > nodes.length, focus_ids: [...focusIds],
        displayed: nodes.length, page: params.page, page_size: 10 } };
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
      if (scenario === "model-diagnostics" && params.kind === "behavior") {
        items[0].purpose = "behavior"; items[0].transport_status = "unknown";
        items[1].purpose = "catchup"; items[1].transport_status = "confirmed"; items[1].receipt_id = "-123456";
      }
      if (dailyScenario && ["diary", "dream"].includes(params.kind)) {
        const job = Object.values(jobs).filter(j => j.kind === params.kind && j.status === "succeeded").at(-1);
        if (job) items.unshift({ ...items[0], id: job.experience_id, period: job.day,
          title: job.day, body: `今日合成${params.kind}正文，仅用于验收。`, pinned: false });
      }
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
    if (dailyScenario && path === "console/experience-generate") {
      const job = jobs[payload.request_id] || { api_version: 1, ...payload,
        day: "2026-11-09", timezone: "Asia/Shanghai", status: "queued", reason_code: "queued" };
      jobs[payload.request_id] = job; data.experience[payload.kind] = clone(job); persistJobs();
      if (scenario === "daily-timeout") return fail("timeout", "合成受理后丢失响应");
      if (scenario === "daily-not-found") {
        delete jobs[payload.request_id]; persistJobs(); return fail("timeout", "合成受理前超时");
      }
      return { status: "ok", data: clone(job) };
    }
    if (path === "console/config") {
      if (Object.keys(payload).some(key => !["context_id", "expected_revision", "patch", "reason", ...(fastScenario ? ["receipt"] : [])].includes(key))) {
        return fail("validation_error", "配置不能携带 ScopeSelection 额外字段");
      }
      if (scenario === "conflict" && !rejectedSave) {
        rejectedSave = true; data.config.revision = "config-2";
        return fail("version_conflict", "原生配置已在别处修改");
      }
      if (["save-race", "save-fast-race"].includes(scenario) && !rejectedSave) {
        rejectedSave = true; data.config.values.home_city = "上海"; data.config.revision = "race-2";
        return fail("version_conflict", "Revision changed; reload and review before submitting again.");
      }
      if (payload.expected_revision !== data.config.revision) return fail("version_conflict", "配置版本冲突");
      Object.assign(data.config.values, payload.patch); data.config.revision += "-saved";
      data.state_mode = data.config.values.persona_shared_state ? "persona" : "scene";
      try { sessionStorage.setItem(configKey, JSON.stringify(data.config)); } catch (_) {}
      if (["save-timeout", "save-fast-timeout"].includes(scenario)) return fail("timeout", "合成配置写入后回执超时");
      return { status: "ok", data: payload.receipt === "config" ? { api_version: 1, config: clone(data.config) } : clone(data) };
    }
    if (path === "console/relationship") {
      if (Object.keys(payload).some(key => !["persona_id", "context_id", "platform", "account_id", "score", "frozen", "note", "expected_version", "reason"].includes(key))) {
        return fail("validation_error", "非法关系字段");
      }
      if (scenario === "relationship-unknown") return fail("unavailable", "合成写入结果无法确认");
      const item = relationships.find(item => item.platform === payload.platform && item.account_id === payload.account_id);
      if (!item) return fail("validation_error", "合成账号不存在");
      if (scenario === "relationship-conflict" && !rejectedRelationship) {
        rejectedRelationship = true; item.version++; item.score = 47.8; return fail("version_conflict", "关系已在别处修改");
      }
      if (payload.expected_version !== item.version) return fail("version_conflict", "关系版本变化");
      item.score = payload.score; item.raw = payload.score * 10; item.frozen = payload.frozen; item.note = payload.note; item.version++;
      return { status: "ok", data: { api_version: 1, node: clone(item), version: item.version } };
    }
    if (path === "console/preview") return { status: "ok", data: {
      api_version: 1, eligible: false, reasons: ["autonomy_disabled", "observe_only"],
      model_calls: 0, sends: 0, candidates: clone(data.behavior.candidates),
    } };
    if (path === "console/behavior-simulate") return { status: "ok", data: {
      api_version: 1, status: "ok", text: "合成模拟内容", model_calls: 1, sends: 0,
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
Object.defineProperty(window, "__fixture", { value: {
  calls, get state() { return clone(data); },
  // 测试专用：模拟另一位管理员写入；不会进入生产页面包。
  changeConfig(patch, revision) { Object.assign(data.config.values, patch); data.config.revision = revision; },
  setFeeling(value) { data.feeling = clone(value); },
  setEnvironment(value) { data.environment = clone(value); },
  denyAccess() { denyAccess = true; },
} });
if (scenario !== "missing-bridge") window.AstrBotPluginView = bridge;
document.title = `[合成测试] ${document.title}`;
