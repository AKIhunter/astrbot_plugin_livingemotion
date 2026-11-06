import { createApi, pageError, PageError } from "./api.mjs";
import {
  PAGE_SIZE, SECTIONS, DIMENSIONS, ACTIONS, object, list, text, unit, percent, yesno,
  reasons, hasRevision, date, expired, normalizeState, normalizeRecords, fieldValue,
} from "./model.mjs";

const $ = id => document.getElementById(id);
const api = createApi(() => window.AstrBotPluginView || window.AstrBotPluginPage);
const uiKey = "livingemotion.view.v1";
const emptyFilters = () => Object.fromEntries(["emotion", "behavior", "diary", "dream"].map(kind => [kind, { page: 1, query: "" }]));
const state = {
  data: null, section: "overview", contextId: "", filters: emptyFilters(), kind: "diary",
  draft: Object.create(null), baseRevision: null, conflict: false, stale: true,
  loading: false, writing: false, generation: 0, recordGeneration: 0, preview: null,
  pendingAction: null, uncertain: new Set(), invalidFields: new Map(),
};
try {
  const saved = object(JSON.parse(sessionStorage.getItem(uiKey) || "{}"));
  if (Object.hasOwn(SECTIONS, saved.section)) state.section = saved.section;
  if (typeof saved.contextId === "string") state.contextId = saved.contextId;
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
      section: state.section, contextId: state.contextId, filters: state.filters, kind: state.kind,
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
  return !!state.data?.context_id && !state.loading && !state.writing && !state.stale;
}
function handleError(error) {
  const failure = pageError(error);
  if (["unauthorized", "forbidden", "bridge_error"].includes(failure.code)) {
    state.generation++;
    state.recordGeneration++;
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
    control.disabled = !canWrite() || !supported || state.uncertain.has(id);
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
  hero.append(node("p", "BOT / 当前感受", "hero-label"),
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
function relationshipBlock() {
  const value = state.data.relationship;
  return block("关系", pairs([
    ["当前阶段", text(value.stage)], ["原始分值", text(value.raw)], ["原量纲", text(value.scale)],
    ["归一值", percent(value.normalized)], ["变化原因", text(value.reason)],
  ]), details("证据与身份投影", pairs([
    ["来源完整度", text(value.source_completeness)], ["身份修订号", text(value.identity_revision)],
  ])));
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
  container.append(botHero());
  const columns = node("div", undefined, "columns");
  columns.append(block("Bot 状态维度", dimensions(state.data.bot_state.dimensions), sourceDetails(state.data.bot_state)),
    observationBlock());
  const stats = node("dl", undefined, "stat-line");
  for (const [key, value] of [
    ["精力 · 来自长夜", percent(state.data.night.energy)],
    ["当前作息", text(state.data.night.state)],
    ["关系阶段", text(state.data.relationship.stage)],
  ]) {
    const group = node("div"); group.append(node("dt", key), node("dd", value)); stats.append(group);
  }
  container.append(columns, stats,
    block("当前可用性", pairs([["状态", state.data.availability.available === true ? "可用" :
      state.data.availability.available === false ? "暂不可用" : "未提供"],
    ["原因", reasons(state.data.availability.reasons)]])), healthBlock());
}
function renderPersona(container) {
  const value = state.data.persona;
  container.append(block("当前人格", pairs([
    ["名称", text(value.name)], ["来源", text(value.source)], ["人格 ID", text(value.id)],
    ["修订号", text(value.revision)],
  ]), details("人格说明", node("p", text(value.description)))),
  node("p", "人格由 AstrBot 当前范围解析。切换页面主题不会切换人格；模型提供者也不代表 Bot 身份。", "hint"));
}
function renderEmotion(container) {
  container.append(botHero(), block("Bot 状态维度", dimensions(state.data.bot_state.dimensions)),
    observationBlock(), relationshipBlock());
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
  container.append(block("主动行为状态", pairs([
    ["自主发送", yesno(value.enabled)], ["剩余额度", text(value.remaining)],
    ["冷却截止", date(value.cooldown_until)], ["未回复退避", text(value.backoff)], ["当前原因", text(value.reason)],
  ])));
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
    ["作息状态", text(value.state)], ["睡眠阶段", text(value.stage)],
    ["入睡时间", date(value.sleep_at)], ["预计醒来", date(value.wake_at)], ["变化原因", text(value.reason)],
  ])), block("精力", metric("当前精力", value.energy)),
  block("醒后补课", pairs([
    ["已处理", text(catchUp.completed)], ["本次有界窗口", text(catchUp.total)], ["进度说明", text(catchUp.reason)],
  ])), details("手动作息操作", actionControls(["night.sleep", "night.wake"])));
}
function renderExperience(container) {
  const value = state.data.experience;
  container.append(block("私人体验", node("p", "日记记录主观体会；梦境始终是想象。正文与来源仅在已认证管理页阅读。", "hint"),
    pairs([["日记", yesno(value.diary_enabled)], ["梦境", yesno(value.dream_enabled)], ["生成状态", text(value.reason)]])),
  details("手动生成 · 可能消耗模型额度", actionControls(["diary.generate", "dream.generate"])));
}
function renderMemory(container) {
  const value = state.data.memory;
  const mode = { none: "关闭长期记忆", local_lite: "内置轻量记忆", external: "外部记忆后端" }[value.mode];
  container.append(block("记忆接入", pairs([
    ["当前模式", mode || "未提供"], ["提供者", text(value.provider)], ["允许检索", yesno(value.can_read)],
    ["允许导出", yesno(value.can_write)], ["降级原因", text(value.reason)],
  ])), block("实际能力", value.capabilities?.length ? node("p", reasons(value.capabilities)) :
    node("p", "尚未声明可用记忆能力。", "hint")),
  node("p", "关闭长期记忆不关闭情绪、关系与作息。外部模式不重复抽取事实；检索与导出分别控制。", "hint"));
}
const renderers = {
  overview: renderOverview, persona: renderPersona, emotion: renderEmotion, behavior: renderBehavior,
  night: renderNight, experience: renderExperience, memory: renderMemory,
};

function renderSettings() {
  const root = $("settings"); root.replaceChildren();
  const fields = state.data.config.fields.filter(field => field.section === state.section);
  root.hidden = state.section === "overview";
  if (root.hidden) return;
  const body = node("div");
  body.append(node("p", `配置来源：${text(state.data.config.source)} · 版本 ${text(state.data.config.revision)}`, "hint"));
  if (!state.data.capabilities.includes("config.write")) body.append(node("p", "宿主未开放配置写入，本页只读。", "hint"));
  if (state.invalidFields.size) body.append(node("p", "存在未通过校验的输入。请返回对应分区修正，或放弃更改。", "error-text"));
  if (!fields.length) body.append(node("p", "宿主未提供本区可编辑字段，请在 AstrBot 原生配置检查。", "hint"));
  fields.forEach((field, index) => {
    const value = Object.hasOwn(state.draft, field.key) ? state.draft[field.key] : state.data.config.values[field.key];
    const id = `config-field-${index}`;
    const wrapper = node("div", undefined, "field");
    const description = node("div");
    const label = node("label", text(field.label, field.key)); label.htmlFor = id;
    const help = node("p", text(field.help, field.key), "hint"); help.id = `${id}-help`;
    description.append(label, help);
    let input;
    if (field.type === "enum") {
      input = node("select");
      for (const option of list(field.options)) {
        if (!option || !["string", "number", "boolean"].includes(typeof option.value)) continue;
        const element = node("option", text(option.label, String(option.value)));
        element.value = String(option.value); input.append(element);
      }
      if (!list(field.options).some(option => option?.value === value)) {
        const unknown = node("option", `当前值：${text(value)}`); unknown.value = ""; unknown.disabled = true;
        input.prepend(unknown); input.value = "";
      } else input.value = String(value);
    } else {
      input = node("input");
      input.type = field.type === "boolean" ? "checkbox" : ["number", "integer"].includes(field.type) ? "number" : "text";
      if (field.type === "boolean") input.checked = value === true;
      else input.value = text(value, "");
      input.maxLength = 2000;
      if (input.type === "number") {
        if (Number.isFinite(field.min)) input.min = String(field.min);
        if (Number.isFinite(field.max)) input.max = String(field.max);
        input.step = field.type === "integer" ? "1" : Number.isFinite(field.step) ? String(field.step) : "any";
      }
    }
    input.id = id; input.dataset.key = field.key;
    if (state.invalidFields.has(field.key)) {
      const invalid = state.invalidFields.get(field.key);
      input.value = invalid.value; input.setCustomValidity(invalid.message);
    }
    input.setAttribute("aria-describedby", help.id);
    input.dataset.editable = String(!field.readonly && state.data.capabilities.includes("config.write") &&
      ["boolean", "enum", "number", "integer", "string"].includes(field.type) &&
      Object.hasOwn(state.data.config.values, field.key));
    input.addEventListener("input", () => {
      input.setCustomValidity("");
      try {
        const next = fieldValue(field, input);
        state.invalidFields.delete(field.key);
        if (!Object.keys(state.draft).length) state.baseRevision = state.data.config.revision;
        if (next === state.data.config.values[field.key]) delete state.draft[field.key];
        else state.draft[field.key] = next;
        if (!Object.keys(state.draft).length) state.conflict = false;
        updateControls();
      } catch (error) {
        state.invalidFields.set(field.key, { value: input.value, message: error.message });
        input.setCustomValidity(error.message); input.reportValidity(); updateControls();
      }
    });
    wrapper.append(description, input); body.append(wrapper);
  });
  root.append(details("配置 · 与 AstrBot 原生配置共用", body));
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
  if (state.section === "experience") {
    const field = node("div"); const label = node("label", "阅读类型"); label.htmlFor = "record-kind";
    const select = node("select"); select.id = "record-kind";
    for (const [key, title] of [["diary", "日记"], ["dream", "梦境 · 想象"]]) {
      const option = node("option", title); option.value = key; select.append(option);
    }
    select.value = state.kind;
    select.addEventListener("change", () => { state.kind = select.value; remember(); renderRecordsShell(); });
    field.append(label, select); form.append(field);
  }
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
    if (kind === "dream") body.append(pairs([["清晰度", percent(item.clarity)], ["置顶", yesno(item.pinned)]]));
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
  if (!state.data?.context_id) {
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
      context_id: state.contextId, kind, page: filter.page, page_size: PAGE_SIZE, query: filter.query,
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
  $("connection").textContent = `更新于 ${date(data.updated_at)}`;
  remember(); render();
}
async function loadState({ rebase = false } = {}) {
  if (state.writing || state.loading) return;
  const generation = ++state.generation;
  state.recordGeneration++;
  state.loading = true; updateControls();
  notify("");
  try {
    const data = await api.state(state.contextId);
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
  state.writing = true; updateControls();
  try {
    const result = await api.save({
      context_id: state.contextId, expected_revision: state.baseRevision, patch: { ...state.draft }, reason,
    });
    if (generation !== state.generation) return;
    const checked = normalizeState(result);
    if (checked.context_id !== state.contextId) throw new PageError("invalid_context", "配置回执范围不一致，请核对宿主记录。");
    state.draft = Object.create(null);
    state.invalidFields.clear();
    applyData(checked);
    $("change-reason").value = "";
    notify("已保存到原生配置。");
  } catch (error) {
    if (generation !== state.generation) return;
    if (["timeout", "bridge_error"].includes(pageError(error).code)) state.uncertain.add("config");
    handleError(error);
  } finally { state.writing = false; updateControls(); }
}
function openAction(id) {
  if (!canWrite() || state.uncertain.has(id) || !state.data.actions.some(action => action.id === id && action.enabled === true)) return;
  state.pendingAction = { id, contextId: state.contextId, revision: state.data.revision, generation: state.generation };
  $("action-title").textContent = ACTIONS[id][0];
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
    });
    if (pending.generation !== state.generation) return;
    if (result.api_version !== 1 || typeof result.status !== "string") throw new PageError("invalid_response", "动作回执无效，执行结果不明，请核对记录。");
    if (result.status === "unknown") state.uncertain.add(pending.id);
    $("action-dialog").close();
    notify(`操作结果：${result.status}。${text(result.reason, "")}${result.request_id ? ` 请求 ID：${text(result.request_id)}` : ""}`,
      result.status === "unknown" ? "warning" : "");
    state.stale = true;
    $("connection").textContent = "操作已返回 · 请刷新核对状态";
  } catch (error) {
    if (pending.generation !== state.generation) return;
    const failure = pageError(error);
    if (["timeout", "invalid_response", "bridge_error"].includes(failure.code)) state.uncertain.add(pending.id);
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
    state.filters = emptyFilters(); state.invalidFields.clear();
    $("content").replaceChildren(node("p", "正在读取新范围…", "empty"));
    $("records").replaceChildren(); $("settings").replaceChildren();
    remember(); loadState();
  });
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
