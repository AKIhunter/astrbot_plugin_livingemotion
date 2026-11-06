import { createApi, pageError, PageError } from "./api.mjs";
import {
  PAGE_SIZE, SECTIONS, DIMENSIONS, ACTIONS, object, list, text, unit, percent, yesno,
  reasons, hasRevision, date, expired, normalizeState, normalizeRecords, baselineDimensions, scopeParams, NIGHT_STATES,
} from "./model.mjs";
import { radar } from "./charts/radar.mjs";
import { mountRelationships } from "./charts/relationships.mjs";
import { mountEnergy } from "./charts/energy.mjs";
import { renderSettings as settingsView } from "./settings.mjs";

const $ = id => document.getElementById(id);
const api = createApi(() => window.AstrBotPluginView || window.AstrBotPluginPage);
const uiKey = "livingemotion.view.v1";
const emptyFilters = () => Object.fromEntries(["emotion", "behavior", "diary", "dream"].map(kind => [kind, { page: 1, query: "" }]));
const state = {
  data: null, section: "overview", contextId: "", filters: emptyFilters(), kind: "diary",
  draft: Object.create(null), baseRevision: null, conflict: false, stale: true,
  loading: false, writing: false, generation: 0, recordGeneration: 0, preview: null,
  pendingAction: null, uncertain: new Set(), invalidFields: new Map(),
  selection: {}, scopes: null, options: {}, dispose: null,
};
try {
  const saved = object(JSON.parse(sessionStorage.getItem(uiKey) || "{}"));
  if (Object.hasOwn(SECTIONS, saved.section)) state.section = saved.section;
  if (typeof saved.contextId === "string") state.contextId = saved.contextId;
  if (object(saved.selection).persona_id) state.selection = scopeParams(saved.selection);
  if (saved.kind === "diary" || saved.kind === "dream") state.kind = saved.kind;
  for (const kind of Object.keys(state.filters)) {
    const filter = object(object(saved.filters)[kind]);
    state.filters[kind] = {
      page: Number.isSafeInteger(filter.page) && filter.page > 0 ? filter.page : 1,
      query: text(filter.query, "").slice(0, 200),
    };
  }
} catch (_) { /* The page also works when storage is unavailable. */ }

function remember() {
  try {
    sessionStorage.setItem(uiKey, JSON.stringify({
      section: state.section, contextId: state.contextId, selection: state.selection, filters: state.filters, kind: state.kind,
    }));
  } catch (_) { /* No business data or drafts are persisted by this page. */ }
}
function node(tag, content, className) {
  const element = document.createElement(tag);
  if (content !== undefined) element.textContent = text(content, "");
  if (className) element.className = className;
  return element;
}
function button(label, handler, className) {
  const control = node("button", label, className);
  control.type = "button";
  control.addEventListener("click", handler);
  return control;
}
function badge(value, tone = "") { return node("span", value, `status ${tone}`); }
function details(title, child) {
  const wrapper = node("details");
  wrapper.append(node("summary", title));
  const body = node("div", undefined, "details-content");
  body.append(child);
  wrapper.append(body);
  return wrapper;
}
function pairs(entries) {
  const dl = node("dl", undefined, "key-values");
  entries.forEach(([key, value]) => dl.append(node("dt", key), node("dd", value)));
  return dl;
}
function block(title, ...children) {
  const section = node("section", undefined, "block");
  section.append(node("h2", title), ...children);
  return section;
}
function jsonDetails(title, value) {
  return details(title, node("pre", JSON.stringify(value, null, 2)));
}
function notify(message, type = "") {
  $("notice").textContent = message;
  $("notice").className = `notice ${type}`;
  $("notice").hidden = !message;
}
function canWrite() {
  return !!(state.data?.context_id || state.data?.scope_selection?.persona_id) && !state.loading && !state.writing && !state.stale;
}
function selectedScope() { return Object.keys(state.selection).length ? state.selection : state.contextId; }
function handleError(error) {
  const failure = pageError(error);
  if (["unauthorized", "forbidden", "bridge_error"].includes(failure.code)) {
    state.generation++;
    state.recordGeneration++;
    state.dispose?.(); state.dispose = null;
    state.data = null;
    state.draft = Object.create(null);
    state.invalidFields.clear();
    state.preview = null;
    state.stale = true;
    state.contextId = "";
    state.filters = emptyFilters();
    state.pendingAction = null;
    $("action-dialog").close();
    $("change-reason").value = "";
    $("action-reason").value = "";
    try { sessionStorage.removeItem(uiKey); } catch (_) {}
    $("context").replaceChildren(node("option", "需要宿主认证"));
    $("scope-persona").replaceChildren(node("option", "需要宿主认证"));
    $("view-scope").disabled = true; state.scopes = null; state.selection = {};
    $("content").replaceChildren(node("p", "私人内容已清空。请在 AstrBot 宿主重新登录并确认管理权限。", "empty"));
    $("settings").replaceChildren();
    $("records").replaceChildren();
    $("settings").hidden = $("records").hidden = true;
    $("mode").textContent = failure.code === "bridge_error" ? "连接未确认" : "访问被拒绝";
    $("connection").textContent = "需要重新确认宿主连接与权限";
    notify(failure.code === "bridge_error" ?
      "宿主仅返回了未分型错误，无法确认访问状态，已隐藏私人内容。请重新连接后核对上次请求结果。" :
      "访问被拒绝。页面参数不能代替宿主身份认证。", "error");
  } else {
    if (failure.code === "version_conflict") state.conflict = true;
    const stale = state.stale && state.data ? " 当前显示旧快照，写操作已停用。" : "";
    notify(`${failure.message}（${failure.code}）${stale}`, failure.code === "version_conflict" ? "warning" : "error");
  }
  updateControls();
}
function updateControls() {
  const dirty = Object.keys(state.draft).length;
  $("context").disabled = !state.data || state.loading || state.writing || dirty > 0 || state.invalidFields.size > 0;
  $("scope-persona").disabled = $("view-scope").disabled = !state.scopes || $("context").disabled;
  if (state.selection.view_scope === "global") $("context").disabled = true;
  $("refresh").disabled = state.loading || state.writing;
  $("content").setAttribute("aria-busy", String(state.loading));
  $("editor").hidden = !dirty && !state.invalidFields.size;
  $("draft-count").textContent = `${dirty} 项 · 基准版本 ${text(state.baseRevision)}${state.invalidFields.size ? ` · ${state.invalidFields.size} 项输入无效` : ""}`;
  $("save").disabled = !canWrite() || !state.data?.capabilities.includes("config.write") || state.conflict ||
    !hasRevision(state.baseRevision) || !dirty || state.uncertain.has("config") || state.invalidFields.size > 0;
  $("save").textContent = state.writing ? "正在提交…" : "保存到原生配置";
  $("rebase").hidden = !state.conflict;
  $("rebase").disabled = state.loading || state.writing;
  $("discard").disabled = state.writing;
  $("change-reason").disabled = state.writing;
  $("settings").querySelectorAll("input,select").forEach(control => {
    control.disabled = !canWrite() || control.dataset.editable !== "true";
  });
  $("content").querySelectorAll("[data-operation]").forEach(control => {
    const id = control.dataset.operation;
    const supported = id === "preview" ? state.data?.capabilities.includes("behavior.preview") :
      state.data?.actions.some(action => action.id === id && action.enabled === true) && hasRevision(state.data?.revision);
    control.disabled = !canWrite() || !state.data?.context_id || !supported || state.uncertain.has(id);
  });
  // History is a sibling of #content; stale/unknown pin controls live here.
  $("records").querySelectorAll("[data-pin-entry]").forEach(control => {
    control.disabled = !canWrite() || control.dataset.pinAvailable !== "true" ||
      state.uncertain.has(`experience.pin:${control.dataset.pinEntry}`);
  });
}
function metric(label, value) {
  const wrapper = node("div", undefined, "metric");
  const heading = node("div", undefined, "metric-head");
  heading.append(node("span", label), node("span", percent(value), "metric-value"));
  wrapper.append(heading);
  if (unit(value) !== null) {
    const meter = node("div", undefined, "meter");
    meter.setAttribute("role", "meter");
    meter.setAttribute("aria-label", label);
    meter.setAttribute("aria-valuemin", "0");
    meter.setAttribute("aria-valuemax", "100");
    meter.setAttribute("aria-valuenow", String(Math.round(value * 100)));
    const fill = node("span");
    fill.style.width = `${value * 100}%`;
    meter.append(fill);
    wrapper.append(meter);
  }
  return wrapper;
}
function dimensions(value) {
  const grid = node("div", undefined, "metrics");
  for (const [key, label] of Object.entries(DIMENSIONS)) grid.append(metric(label, object(value)[key]));
  return grid;
}
function sourceDetails(value, extra = []) {
  return details("来源与有效期", pairs([
    ["来源", text(value.source)], ["更新时间", date(value.updated_at ?? value.observed_at)],
    ["有效期", date(value.expires_at)],
    ["有效状态", expired(value.expires_at) === true ? "已过期，不应作为当前依据" :
      expired(value.expires_at) === false ? "有效期内" : "未提供有效期"],
    ...extra,
  ]));
}
function botHero() {
  const bot = state.data.bot_state;
  const hero = node("section", undefined, "hero");
  hero.setAttribute("aria-label", "Bot 当前感受");
  hero.append(node("p", "TA / LIVE EMOTION", "hero-label"), node("p", text(state.data.persona.name, "原生人格未提供"), "ta-identity"),
    node("h2", text(bot.label, "尚无 Bot 状态"), "hero-value"),
    node("p", text(bot.reason, "等待有来源的互动与状态评估。不会以对方情绪替代 Bot 感受。")));
  if (expired(bot.expires_at)) hero.append(badge("状态已过期", "warn"));
  return hero;
}
function observationBlock() {
  const value = state.data.observation;
  const section = block("对方观察",
    node("p", text(value.label, "尚无可用观察"), "observation-value"),
    node("p", "这是对对方状态的观察，不是 Bot 的感受。", "hint"),
    pairs([["观察对象", text(value.subject)], ["可信度", percent(value.confidence)], ["观察依据", text(value.reason)]]),
    sourceDetails(value),
  );
  section.classList.add("observation");
  section.setAttribute("aria-label", "对方观察");
  if (expired(value.expires_at)) section.append(badge("观察已过期，不作为当前依据", "warn"));
  return section;
}
function healthBlock() {
  const section = block("依赖健康");
  if (!state.data.health.length) section.append(node("p", "宿主尚未提供依赖健康。", "hint"));
  for (const item of state.data.health) {
    const statuses = { ok: ["可用", "good"], degraded: ["降级", "warn"], unavailable: ["不可用", "bad"] };
    const status = Object.hasOwn(statuses, item.status) ? statuses[item.status] : ["未提供", ""];
    const row = node("div", undefined, "health-row");
    row.append(node("strong", text(item.name)), badge(...status), node("p", text(item.reason), "hint"));
    section.append(row);
  }
  return section;
}
function renderOverview(container) {
  const layout = node("div", undefined, "ta-layout");
  layout.append(botHero(), radar(object(state.data.bot_state.dimensions), baselineDimensions(state.data)));
  container.append(layout);
  const stats = node("dl", undefined, "stat-line");
  for (const [key, value] of [
    ["精力 · 来自长夜", percent(state.data.night.energy)],
    ["当前作息", NIGHT_STATES[state.data.night.display_state] || text(state.data.night.state)],
    ["状态归属", { persona: "同一人格共享", shared: "同一人格共享", scene: "真实会话独立" }[state.data.state_mode] || "由宿主解析"],
  ]) {
    const group = node("div"); group.append(node("dt", key), node("dd", value)); stats.append(group);
  }
  container.append(stats,
    details("可用性与来源", pairs([["状态", state.data.availability.available === true ? "可用" :
      state.data.availability.available === false ? "暂不可用" : "未提供"],
    ["原因", reasons(state.data.availability.reasons)], ["来源", text(state.data.bot_state.source)],
    ["更新时间", date(state.data.bot_state.updated_at)]])), details("依赖健康", healthBlock()));
  if (state.selection.view_scope === "global" && state.data.state_mode === "scene") {
    container.append(node("p", `当前为真实会话独立模式。全局数值来自最近代表会话 ${text(state.data.representative_context_id)}，不是共享状态或多会话平均值。`, "hint"));
  }
}
function renderPersona(container) {
  const value = state.data.persona;
  container.append(block("当前人格", pairs([
    ["名称", text(value.name)], ["来源", text(value.source)], ["人格 ID", text(value.id)],
    ["修订号", text(value.revision)],
  ]), details("人格说明", node("p", text(value.description)))),
  node("p", "人格由 AstrBot 当前范围解析。切换页面主题不会切换人格；模型提供者也不代表 Bot 身份。", "hint"),
  button("前往设置修改人格", () => navigate("settings")));
}
function renderEmotion(container) {
  const columns = node("div", undefined, "columns");
  columns.append(radar(object(state.data.bot_state.dimensions), baselineDimensions(state.data)), observationBlock());
  container.append(botHero(), block("四维状态分析", columns),
    node("p", text(state.data.bot_state.decay_explanation ?? state.data.emotion_policy?.explanation,
      "实线与基准在同一归一坐标。情绪随时间恢复；刺激变化以实际记录为依据，不为打开页面调用模型。"), "hint"),
    sourceDetails(state.data.bot_state));
}
function renderRelationships(container) {
  if (!state.selection.persona_id) {
    container.append(node("p", "没有已授权人格，不能查询关系。请刷新宿主范围。", "empty")); return;
  }
  const panel = node("div"); panel.id = "relationship-body"; container.append(panel);
  state.dispose = mountRelationships(panel, {
    api, selection: { ...scopeParams(selectedScope()), platforms: state.scopes?.platforms },
    persona: state.data.persona, canWrite: () => canWrite() && state.data.capabilities.includes("relationship.write"),
    onError: handleError, uncertain: state.uncertain,
  });
}
function clientList(items, renderItem, emptyMessage) {
  const root = node("div");
  let page = 1;
  const render = () => {
    const retainFocus = root.contains(document.activeElement);
    root.replaceChildren();
    if (!items.length) { root.append(node("p", emptyMessage, "hint")); return; }
    const body = node("div");
    items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).forEach(item => body.append(renderItem(object(item))));
    root.append(body);
    if (items.length > PAGE_SIZE) {
      const pager = node("div", undefined, "pager");
      const previous = button("上一页", () => { page--; render(); });
      const next = button("下一页", () => { page++; render(); });
      previous.disabled = page <= 1; next.disabled = page * PAGE_SIZE >= items.length;
      pager.append(previous, node("span", `第 ${page} 页 · 共 ${items.length} 条 · 每页 10 条`), next);
      root.append(pager);
      if (retainFocus) (next.disabled ? previous : next).focus();
    }
  };
  render();
  return root;
}
function candidate(value) {
  const row = node("div", undefined, "record");
  row.append(node("h3", text(value.label ?? value.candidate ?? value.id)),
    node("p", `硬否决：${reasons(value.vetoes ?? value.reasons)}`, "hint"));
  if (value.score !== undefined) row.append(node("p", `适合度：${text(value.score)}`, "hint"));
  return row;
}
function actionControls(ids) {
  const root = node("div", undefined, "action-list");
  ids.forEach(id => {
    const [label, help] = ACTIONS[id];
    const allowed = state.data.actions.find(action => action.id === id);
    const row = node("div", undefined, "action-row");
    const description = node("div");
    description.append(node("h3", label), node("p", help, "hint"));
    if (!allowed?.enabled) description.append(node("p", text(allowed?.reason, "宿主未开放此操作，或尚未配置所需能力。"), "hint"));
    if (state.uncertain.has(id)) description.append(node("p", "上次执行结果不明。此页面已锁定重试，请核对执行记录。", "error-text"));
    const control = button(label, () => openAction(id));
    control.dataset.operation = id;
    row.append(description, control);
    root.append(row);
  });
  return root;
}
function renderPreview(root) {
  root.replaceChildren();
  if (!state.preview) return;
  root.append(badge(state.preview.eligible === true ? "模拟：符合条件" : "模拟：暂不符合", state.preview.eligible ? "good" : "warn"),
    node("p", `原因：${reasons(state.preview.reasons)}`),
    node("p", "模型调用 0 · 消息发送 0", "hint"),
    clientList(list(state.preview.candidates), candidate, "模拟未返回候选。"));
}
function renderBehavior(container) {
  const value = state.data.behavior;
  const explanations = {
    random_wait: "正在等一个自然的时机", checking: "正在想要不要开口",
    random_skip: "这次先安静陪着", conversation_active: "还在聊天，先不插话",
    missed_opportunity: "错过的时机已跳过", opportunity_interrupted: "上次检查中断，已停止旧任务",
    opportunity_timeout: "这次检查超时，先停下来", select_scene: "选择私聊或群聊查看具体节奏",
  };
  container.append(block("主动行为状态", pairs([
    ["自主发送", yesno(value.enabled)], ["剩余额度", text(value.remaining)],
    ["下次随机检查", date(value.next_check_at)], ["冷却截止", date(value.cooldown_until)],
    ["未回应次数", text(value.backoff)], ["最近动机", text(value.last_motive)],
    ["此刻", explanations[value.last_reason] || text(value.last_reason || value.reason)],
  ])), block("自然地开口",
    node("p", "想起聊过的事，就问问后续；关系熟悉时，关心近况或轻轻分享心情。每次只留一个容易接住的话头。"),
    node("p", `随机等待 ${list(value.random_interval).join("–") || "未配置"} 分钟后再次检查。对方没回应时放慢节奏，睡着或正在聊天时先安静。`, "hint"),
    node("p", "在「设置 → 主动行为」调整节奏、模型与联系范围，保存后自动开始等待。", "hint"),
    ...(value.scope_key ? [jsonDetails("当前联系范围标识", { scope_key: value.scope_key })] : []),
  ));
  const control = button("仅模拟 · 不计费不发送", async () => {
    if (!canWrite()) return;
    const generation = state.generation;
    state.writing = true; updateControls();
    try {
      const result = await api.preview(state.contextId);
      if (generation !== state.generation) return;
      if (result.api_version !== 1 || result.model_calls !== 0 || result.sends !== 0) {
        throw new PageError("invalid_preview", "模拟响应未证明零模型调用、零发送，不能作为安全模拟结果。");
      }
      state.preview = result;
      renderPreview(preview);
      notify("模拟结束。未请求真实生成或发送。");
    } catch (error) { if (generation === state.generation) handleError(error); }
    finally { state.writing = false; updateControls(); }
  }, "primary");
  control.dataset.operation = "preview";
  const preview = node("div"); preview.id = "preview-result"; preview.setAttribute("aria-live", "polite");
  renderPreview(preview);
  container.append(block("行为模拟", node("p", "先检查候选和硬否决。模拟只计算规则，不调用收费模型。", "hint"),
    control, preview));
  if (!state.data.capabilities.includes("behavior.preview")) container.append(node("p", "宿主未提供无费用模拟能力。", "hint"));
  container.append(block("候选", clientList(list(value.candidates), candidate, "当前没有已授权候选。")),
    details("实际生成与发送", actionControls(["behavior.send"])));
}
function renderNight(container) {
  const value = state.data.night;
  const catchUp = object(value.catch_up);
  container.append(block("长夜", pairs([
    ["作息状态", NIGHT_STATES[value.display_state] || text(value.state)], ["梦境内部阶段", text(value.stage)],
    ["入睡时间", date(value.sleep_at)], ["预计醒来", date(value.wake_at)], ["变化原因", text(value.reason)],
  ])), block("精力", metric("当前精力", value.energy)),
  block("醒后补课", pairs([
    ["已处理", text(catchUp.completed)], ["本次有界窗口", text(catchUp.total)], ["进度说明", text(catchUp.reason)],
  ])), details("手动作息操作", actionControls(["night.sleep", "night.wake"])));
  const stages = node("div", undefined, "sub-tabs"); stages.setAttribute("aria-label", "五档作息");
  for (const [key, label] of Object.entries(NIGHT_STATES)) stages.append(badge(label, value.display_state === key ? "good" : ""));
  container.prepend(stages);
  const energy = block("精力日志"); container.append(energy);
  if (state.selection.persona_id) state.dispose = mountEnergy(energy, { api, selection: selectedScope(), onError: handleError });
  else energy.append(node("p", "没有已授权人格，不能查询精力历史。", "empty"));
}
function renderExperience(container) {
  const value = state.data.experience;
  container.append(block("私人体验", node("p", "日记记录主观体会；梦境始终是想象。正文与来源仅在已认证管理页阅读。", "hint"),
    pairs([["日记", yesno(value.diary_enabled)], ["梦境", yesno(value.dream_enabled)], ["生成状态", text(value.reason)]])),
  details("手动生成 · 可能消耗模型额度", actionControls(["diary.generate", "dream.generate"])));
  const tabs = node("div", undefined, "sub-tabs"); tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "私人体验类型");
  for (const [key, label] of [["diary", "日记"], ["dream", "梦境 · 想象"]]) {
    const tab = button(label, () => { state.kind = key; remember(); render(); });
    tab.dataset.recordKind = key; tab.setAttribute("role", "tab"); tab.setAttribute("aria-selected", String(state.kind === key)); tabs.append(tab);
  }
  tabs.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault(); state.kind = event.key === "Home" ? "diary" : event.key === "End" ? "dream" : state.kind === "diary" ? "dream" : "diary";
    remember(); render(); container.querySelector(`[data-record-kind="${state.kind}"]`)?.focus();
  });
  container.append(tabs);
}
function renderMemory(container) {
  const value = state.data.memory;
  const mode = { none: "本地向量 · 待配置", local_lite: "本地轻量记录", local_vector: "本地向量记忆", external: "LivingMemory" }[value.mode];
  container.append(block("记忆接入", pairs([
    ["当前模式", mode || "未提供"], ["提供者", text(value.provider)], ["允许检索", yesno(value.can_read)],
    ["允许导出", yesno(value.can_write)], ["降级原因", text(value.reason)],
  ])), block("实际能力", value.capabilities?.length ? node("p", reasons(value.capabilities)) :
    node("p", "尚未声明可用记忆能力。", "hint")),
  node("p", "关闭 LivingMemory 后使用本地向量模式；未配置原生 embedding 时显示待配置，不伪装成已有向量库。开启外部后端后停止本地自动收录。", "hint"),
  button("前往设置管理记忆", () => navigate("settings")));
}
const renderers = {
  overview: renderOverview, persona: renderPersona, emotion: renderEmotion, behavior: renderBehavior,
  night: renderNight, experience: renderExperience, memory: renderMemory, relationships: renderRelationships,
  settings: container => container.append(node("p", "按任务完成配置，所有更改统一保存。", "hint")),
};

function renderSettings() {
  settingsView($("settings"), state, state.options, updateControls);
}
function render() {
  const [number, name, title] = SECTIONS[state.section];
  $("section-kicker").textContent = `${number} / ${name}`;
  $("section-title").textContent = title;
  document.querySelectorAll("[data-section]").forEach(button => {
    if (button.dataset.section === state.section) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (!state.data) { updateControls(); return; }
  $("mode").textContent = { active: "运行中", observe_only: "仅观察 · 不自主发送", disabled: "已停用" }[state.data.mode] || "模式未提供";
  $("mode").className = `status ${state.data.mode === "active" ? "good" : "warn"}`;
  state.dispose?.(); state.dispose = null;
  const container = $("content"); container.replaceChildren();
  renderers[state.section](container);
  renderSettings();
  renderRecordsShell();
  updateControls();
}
function selectedKind() {
  return state.section === "emotion" ? "emotion" : state.section === "behavior" ? "behavior" :
    state.section === "experience" ? state.kind : null;
}
function renderRecordsShell() {
  state.recordGeneration++;
  const root = $("records"); root.replaceChildren();
  const kind = selectedKind();
  root.hidden = !kind;
  if (!kind) return;
  const form = node("form", undefined, "record-toolbar");
  const field = node("div", undefined, "search-field");
  const label = node("label", "筛选记录"); label.htmlFor = "record-query";
  const search = node("input"); search.id = "record-query"; search.type = "search"; search.maxLength = 200;
  search.value = state.filters[kind].query; search.placeholder = "关键词或原因码";
  field.append(label, search);
  const submit = node("button", "筛选"); submit.type = "submit";
  form.append(field, submit);
  form.addEventListener("submit", event => {
    event.preventDefault();
    state.filters[kind] = { page: 1, query: search.value.trim() }; remember(); loadRecords();
  });
  const body = node("div"); body.id = "record-body"; body.setAttribute("aria-live", "polite");
  body.tabIndex = -1;
  root.append(form, body);
  loadRecords();
}
function timeline(items) {
  const values = items.slice().reverse().map(item => unit(object(item.after).pleasure));
  if (!values.some(value => value !== null)) return node("p", "当前页无有效数值曲线；详情按原记录显示。", "hint");
  const root = node("figure"); root.style.margin = "20px 0";
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.classList.add("chart"); svg.setAttribute("viewBox", "0 0 600 100"); svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "当前页 Bot 愉悦趋势，数值见各条记录的前后对照");
  const line = document.createElementNS(ns, "line");
  for (const [key, value] of Object.entries({ x1: 0, y1: 50, x2: 600, y2: 50 })) line.setAttribute(key, String(value));
  svg.append(line);
  let path = ""; let contiguous = false;
  values.forEach((value, index) => {
    if (value === null) { contiguous = false; return; }
    const x = values.length === 1 ? 300 : 8 + index / (values.length - 1) * 584;
    const y = 92 - value * 84;
    path += `${contiguous ? "L" : "M"}${x},${y} `; contiguous = true;
    const point = document.createElementNS(ns, "circle"); point.setAttribute("cx", String(x));
    point.setAttribute("cy", String(y)); point.setAttribute("r", "3"); svg.append(point);
  });
  const curve = document.createElementNS(ns, "path"); curve.setAttribute("d", path); svg.append(curve);
  root.append(svg, node("figcaption", "Bot 愉悦 · 当前页由旧到新 · 0–100% · 非连续时间轴", "chart-caption"));
  return root;
}
function emotionTable(item) {
  const table = node("table");
  const head = node("thead"), heading = node("tr");
  for (const label of ["Bot 维度", "变化前", "变化后"]) { const th = node("th", label); th.scope = "col"; heading.append(th); }
  head.append(heading); table.append(head);
  const body = node("tbody");
  for (const [key, label] of Object.entries(DIMENSIONS)) {
    const row = node("tr"); const th = node("th", label); th.scope = "row";
    row.append(th, node("td", percent(object(item.before)[key])), node("td", percent(object(item.after)[key])));
    body.append(row);
  }
  table.append(body);
  const wrapper = node("div", undefined, "table-wrap"); wrapper.append(table); return wrapper;
}
function recordView(item, kind, index) {
  const article = node("article", undefined, "record"); article.dataset.recordId = text(item.id, "");
  const heading = node("div", undefined, "record-heading");
  const title = node("h3");
  title.append(node("span", String((state.filters[kind].page - 1) * PAGE_SIZE + index + 1).padStart(2, "0"), "record-number"),
    node("span", text(item.title ?? item.label ?? item.candidate, { emotion: "情绪变化", behavior: "行为记录", diary: "私人日记", dream: "梦境" }[kind])));
  heading.append(title, node("span", date(item.created_at), "micro")); article.append(heading);
  if (kind === "dream") article.append(badge("梦境 · 想象，不是现实事实", "warn"));
  if (kind === "diary") article.append(badge("私人日记 · 主观内容"));
  if (kind === "diary") {
    const weather = object(item.weather), header = object(item.header);
    article.append(node("p", `${text(item.date ?? header.date, date(item.created_at))} · ${text(item.city ?? header.city, "住所未提供")} · ${text(weather.summary ?? header.weather, "天气未获取")}`, "micro"));
  }
  article.append(node("p", text(item.reason), "record-reason"));
  if (kind === "emotion") {
    article.append(emotionTable(item),
      node("p", expired(item.expires_at) === true ? "已过期" : expired(item.expires_at) === false ? "有效期内" : "有效期未提供", "hint"));
  } else if (kind === "behavior") {
    article.append(pairs([
      ["执行状态", text(item.result ?? item.status)],
      ["硬否决", reasons(item.vetoes)],
    ]));
    if ((item.result ?? item.status) === "unknown") article.append(node("p", "结果不明，不自动重发。", "error-text"));
  } else {
    const body = node("div");
    body.append(node("p", text(item.body, "正文未提供。"), "body"));
    body.append(pairs([...(kind === "dream" ? [["清晰度", percent(item.clarity)]] : []), ["置顶", yesno(item.pinned)]]));
    const pin = button(item.pinned ? "取消置顶" : "置顶", () => openAction("experience.pin", item));
    pin.dataset.pinEntry = text(item.id, "");
    pin.dataset.pinAvailable = String(item.pin_available === true &&
      typeof item.context_id === "string" && !!item.context_id && typeof item.pinned === "boolean");
    pin.disabled = !canWrite() || pin.dataset.pinAvailable !== "true" ||
      state.uncertain.has(`experience.pin:${item.id}`);
    body.append(pin);
    article.append(details("阅读私人正文", body));
    article.append(details("素材来源与角色", clientList(list(item.sources), source => {
      const entry = node("div", undefined, "record");
      entry.append(badge({ bot_action: "我做的", human_action: "对方说 / 做的", dream: "梦中内容", unknown: "来源不明" }[source.kind] || "来源不明"),
        node("p", text(source.label)), node("p", text(source.excerpt), "body"), node("p", text(source.source_id), "micro"));
      return entry;
    }, "未提供来源，不能据此认领真实事件。")));
  }
  article.append(jsonDetails("上下文、来源与耗时", {
    id: item.id, source: item.source, context: item.context, request_id: item.request_id,
    intent_id: item.intent_id, latency_ms: item.latency_ms, expires_at: item.expires_at, visibility: item.visibility,
  }));
  return article;
}
async function loadRecords() {
  const kind = selectedKind(), root = $("record-body");
  if (!kind || !root) return;
  if (!state.data?.context_id && !state.data?.scope_selection?.persona_id) {
    root.replaceChildren(node("p", "当前没有已授权范围，不能查询记录。", "empty"));
    root.setAttribute("aria-busy", "false");
    return;
  }
  const sequence = ++state.recordGeneration, generation = state.generation;
  const retainedFocus = root.contains(document.activeElement) ? document.activeElement.textContent : "";
  const filter = { ...state.filters[kind] };
  root.setAttribute("aria-busy", "true");
  root.replaceChildren(node("p", "正在读取记录…", "empty"));
  try {
    const response = normalizeRecords(await api.records({
      ...scopeParams(selectedScope()), kind, page: filter.page, page_size: PAGE_SIZE, query: filter.query,
    }), filter.page);
    if (sequence !== state.recordGeneration || generation !== state.generation) return;
    root.replaceChildren();
    if (!response.items.length) root.append(node("p", filter.query ? "没有符合筛选的记录。可以清空关键词重试。" : "当前范围暂无记录。不会用演示内容填充。", "empty"));
    if (kind === "emotion") root.append(timeline(response.items));
    response.items.forEach((item, index) => root.append(recordView(item, kind, index)));
    const pager = node("div", undefined, "pager");
    const changePage = page => { state.filters[kind].page = page; remember(); loadRecords(); };
    const previous = button("上一页", () => changePage(Math.max(1, filter.page - 1)));
    const next = button("下一页", () => changePage(filter.page + 1));
    previous.disabled = filter.page <= 1; next.disabled = filter.page * PAGE_SIZE >= response.total;
    pager.append(previous, node("span", `第 ${filter.page} / ${Math.max(1, Math.ceil(response.total / PAGE_SIZE))} 页 · 共 ${response.total} 条 · 每页 10 条`), next);
    root.append(pager);
    if (retainedFocus) {
      const control = retainedFocus === "下一页" ? next : previous;
      (control.disabled ? root : control).focus();
    }
  } catch (error) {
    if (sequence !== state.recordGeneration || generation !== state.generation) return;
    root.replaceChildren(node("p", "记录读取失败，不表示没有记录。", "error-text"), button("重试读取", loadRecords));
    handleError(error);
  } finally { if (sequence === state.recordGeneration) root.setAttribute("aria-busy", "false"); }
}
function applyData(raw, rebase = false) {
  const data = normalizeState(raw);
  const dirty = Object.keys(state.draft).length;
  if (dirty && data.context_id !== state.contextId) throw new PageError("invalid_context", "宿主返回了不同范围，未将草稿应用到其他范围。");
  if (dirty && !rebase && data.config.revision !== state.baseRevision) {
    state.conflict = true;
    notify("原生配置版本已变化。草稿保留，但需读取最新配置并复核后才能保存。", "warning");
  }
  state.data = data; state.contextId = data.context_id; state.stale = false;
  if (data.scope_selection.persona_id) state.selection = scopeParams(data.scope_selection);
  if (!dirty || rebase) {
    state.baseRevision = data.config.revision; state.conflict = false;
    const allowed = new Set(data.config.fields.filter(field => !field.readonly).map(field => field.key));
    for (const key of Object.keys(state.draft)) {
      if (!allowed.has(key) || state.draft[key] === data.config.values[key]) delete state.draft[key];
    }
    for (const key of state.invalidFields.keys()) if (!allowed.has(key)) state.invalidFields.delete(key);
  }
  $("context").replaceChildren();
  data.contexts.forEach(item => { const option = node("option", item.label); option.value = item.id; $("context").append(option); });
  if (!data.contexts.length) $("context").append(node("option", "没有已授权范围"));
  $("context").value = data.context_id;
  renderScopeControls();
  $("connection").textContent = `更新于 ${date(data.updated_at)}`;
  remember(); render();
}
function renderScopeControls() {
  const scopes = state.scopes;
  if (!scopes) return;
  const personaSelect = $("scope-persona"); personaSelect.replaceChildren();
  for (const item of list(scopes.personas)) {
    const option = node("option", text(item.name ?? item.label, item.id)); option.value = text(item.id, ""); personaSelect.append(option);
  }
  personaSelect.value = state.selection.persona_id || state.data?.persona.id || "";
  $("view-scope").value = state.selection.view_scope || "global";
  const scenes = list(scopes.contexts ?? scopes.scenes).filter(item =>
    (!item.persona_id || item.persona_id === personaSelect.value) &&
    (!state.selection.view_scope || state.selection.view_scope === "global" || (item.view_scope ?? item.scene_kind) === state.selection.view_scope));
  $("context").replaceChildren();
  if (scenes.length) {
    for (const item of scenes) {
      const option = node("option", text(item.label, `${text(item.platform)} / ${text(item.scene_id)}`)); option.value = text(item.id ?? item.context_id, ""); $("context").append(option);
    }
    $("context").value = state.selection.context_id || "";
  } else { const empty = node("option", "此范围没有已授权会话"); empty.value = ""; $("context").append(empty); }
  if (state.selection.view_scope === "global") {
    const global = node("option", "人格全局 · 仅管理查看"); global.value = ""; $("context").prepend(global); $("context").value = "";
  } else {
    const aggregate = node("option", `${state.selection.view_scope === "group" ? "群聊" : "私聊"} · 全部已授权会话`);
    aggregate.value = ""; $("context").prepend(aggregate);
    $("context").value = state.selection.context_id || "";
  }
}
async function loadState({ rebase = false } = {}) {
  if (state.writing || state.loading) return;
  const generation = ++state.generation;
  state.recordGeneration++;
  state.loading = true; updateControls();
  notify("");
  try {
    const optional = await Promise.allSettled([api.scopes(), api.settingsOptions()]);
    if (generation !== state.generation) return;
    for (const result of optional) {
      if (result.status === "rejected" && ["unauthorized", "forbidden", "bridge_error"].includes(pageError(result.reason).code)) {
        handleError(result.reason); return;
      }
    }
    if (optional[0].status === "fulfilled") state.scopes = optional[0].value;
    if (optional[1].status === "fulfilled") state.options = optional[1].value;
    if (!state.selection.persona_id && list(state.scopes?.personas).length) {
      const previous = list(state.scopes.contexts).find(item => item.id === state.contextId);
      state.selection = previous ? scopeParams(previous) : {
        persona_id: state.scopes.personas[0].id, view_scope: "global",
      };
      if (previous) state.selection.context_id = previous.id;
    }
    const data = await api.state(selectedScope());
    if (generation !== state.generation) return;
    applyData(data, rebase);
    if (rebase) notify("已读取最新原生配置，草稿尚未提交。请逐项复核后保存。", "warning");
  } catch (error) {
    if (generation !== state.generation) return;
    state.stale = true;
    $("connection").textContent = "读取失败";
    if (!state.data) $("content").replaceChildren(node("p", "无法读取状态。请确认宿主登录、插件加载与页面 API 能力。", "empty"));
    else $("connection").textContent = "旧快照 · 写操作已停用";
    handleError(error);
  } finally { state.loading = false; updateControls(); }
}
async function saveConfig() {
  if ($("save").disabled) return;
  const invalid = $("settings").querySelector(":invalid");
  if (invalid) { invalid.reportValidity(); return; }
  const reason = $("change-reason").value.trim();
  if (!reason) { notify("请填写修改原因，供管理审计使用。", "warning"); $("change-reason").focus(); return; }
  const generation = state.generation;
  let saved = false;
  state.writing = true; updateControls();
  try {
    const result = await api.save({
      context_id: state.contextId, expected_revision: state.baseRevision, patch: { ...state.draft }, reason,
    });
    if (generation !== state.generation) return;
    const checked = normalizeState(result);
    if (!hasRevision(checked.config.revision)) throw new PageError("invalid_response", "配置回执缺少版本，请核对宿主记录。");
    state.draft = Object.create(null);
    state.invalidFields.clear();
    state.data.config = checked.config; state.baseRevision = checked.config.revision; state.conflict = false;
    saved = true;
    // A config receipt uses the legacy context shape; reread the actual view.
    state.stale = true;
    applyData(await api.state(selectedScope()));
    $("change-reason").value = "";
    notify("已保存到原生配置。");
  } catch (error) {
    if (generation !== state.generation) return;
    if (["timeout", "bridge_error"].includes(pageError(error).code)) state.uncertain.add("config");
    handleError(error);
    if (saved && state.data) notify("配置已保存，但当前范围状态未能刷新。请手动刷新核对，不要重复保存。", "warning");
  } finally { state.writing = false; updateControls(); }
}
function openAction(id, item) {
  const pin = id === "experience.pin";
  const key = pin ? `experience.pin:${item?.id}` : id;
  if (!canWrite() || state.uncertain.has(key) || (pin
    ? item?.pin_available !== true || typeof item.context_id !== "string" || !item.context_id || typeof item.pinned !== "boolean"
    : !state.data.actions.some(action => action.id === id && action.enabled === true))) return;
  state.pendingAction = {
    id, key, contextId: pin ? item.context_id : state.contextId,
    revision: state.data.revision, generation: state.generation,
    ...(pin ? { entry_id: item.id, pinned: !item.pinned, expected_pinned: item.pinned } : {}),
  };
  $("action-title").textContent = pin ? (item.pinned ? "取消置顶" : "置顶") : ACTIONS[id][0];
  $("action-description").textContent = ACTIONS[id][1];
  $("action-reason").value = ""; $("action-error").textContent = "";
  $("confirm-action").disabled = false;
  $("action-dialog").showModal();
  $("action-reason").focus();
}
async function submitAction(event) {
  event.preventDefault();
  const pending = state.pendingAction;
  if (!pending || state.writing || pending.generation !== state.generation) {
    $("action-error").textContent = "状态已改变，请取消并重新核对操作。"; return;
  }
  const reason = $("action-reason").value.trim();
  if (!reason) { $("action-error").textContent = "请填写操作原因。"; return; }
  state.writing = true; $("confirm-action").disabled = true; updateControls();
  try {
    const result = await api.action({
      context_id: pending.contextId, action: pending.id, expected_revision: pending.revision, reason, confirmed: true,
      ...(pending.id === "experience.pin" ? {
        entry_id: pending.entry_id, pinned: pending.pinned, expected_pinned: pending.expected_pinned,
      } : {}),
    });
    if (pending.generation !== state.generation) return;
    if (result.api_version !== 1 || typeof result.status !== "string") throw new PageError("invalid_response", "动作回执无效，执行结果不明，请核对记录。");
    if (result.status === "unknown") state.uncertain.add(pending.key);
    $("action-dialog").close();
    notify(`操作结果：${result.status}。${text(result.reason, "")}${result.request_id ? ` 请求 ID：${text(result.request_id)}` : ""}`,
      result.status === "unknown" ? "warning" : "");
    state.stale = true;
    $("connection").textContent = "操作已返回 · 请刷新核对状态";
  } catch (error) {
    if (pending.generation !== state.generation) return;
    const failure = pageError(error);
    if (["timeout", "invalid_response", "bridge_error"].includes(failure.code)) state.uncertain.add(pending.key);
    $("action-dialog").close(); handleError(error);
  } finally { state.writing = false; state.pendingAction = null; updateControls(); }
}
function navigate(section, focus = false) {
  state.section = section; remember(); render();
  if (focus) $("main").focus();
}
async function boot() {
  $("navigation").addEventListener("click", event => {
    const control = event.target.closest("[data-section]");
    if (control) navigate(control.dataset.section);
  });
  $("navigation").addEventListener("keydown", event => {
    const buttons = [...$("navigation").querySelectorAll("button")];
    const index = buttons.indexOf(document.activeElement);
    if (index < 0 || !["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const target = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 :
      (index + (["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1) + buttons.length) % buttons.length;
    buttons[target].focus();
  });
  $("context").addEventListener("change", () => {
    state.contextId = $("context").value; state.data = null; state.preview = null;
    if (state.scopes) {
      const context = list(state.scopes.contexts).find(item => item.id === state.contextId);
      state.selection = { ...state.selection, context_id: state.contextId, platform: context?.platform || "" };
    }
    state.dispose?.(); state.dispose = null;
    state.filters = emptyFilters(); state.invalidFields.clear();
    $("content").replaceChildren(node("p", "正在读取新范围…", "empty"));
    $("records").replaceChildren(); $("settings").replaceChildren();
    remember(); loadState();
  });
  for (const id of ["scope-persona", "view-scope"]) {
    $(id).addEventListener("change", () => {
      state.dispose?.(); state.dispose = null;
      state.selection = { persona_id: $("scope-persona").value, view_scope: $("view-scope").value };
      state.contextId = ""; state.data = null; state.preview = null; state.filters = emptyFilters();
      $("content").replaceChildren(node("p", "正在读取所选人格与范围…", "empty"));
      $("records").replaceChildren(); $("settings").replaceChildren(); loadState();
    });
  }
  $("refresh").addEventListener("click", () => loadState());
  $("save").addEventListener("click", saveConfig);
  $("rebase").addEventListener("click", () => loadState({ rebase: true }));
  $("discard").addEventListener("click", () => {
    state.draft = Object.create(null); state.conflict = false;
    state.invalidFields.clear();
    $("change-reason").value = ""; notify("已放弃本页未保存更改。"); render();
  });
  $("action-form").addEventListener("submit", submitAction);
  $("cancel-action").addEventListener("click", () => $("action-dialog").close());
  $("action-dialog").addEventListener("close", () => { if (!state.writing) state.pendingAction = null; });
  window.addEventListener("beforeunload", event => {
    if (Object.keys(state.draft).length || state.invalidFields.size || state.writing) { event.preventDefault(); event.returnValue = ""; }
  });
  render();
  await loadState();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
else boot();
