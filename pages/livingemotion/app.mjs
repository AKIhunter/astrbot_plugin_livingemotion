import { t, locale, controlled, setLocale, staticUI } from "./i18n.mjs";
import { createApi, pageError, PageError } from "./api.mjs";
import {
  PAGE_SIZE, SECTIONS, DIMENSIONS, ACTIONS, object, list, text, unit, percent, yesno,
  reasons, hasRevision, date, expired, normalizeState, normalizeRecords, baselineDimensions, scopeParams, NIGHT_STATES,
  behaviorFields, behaviorReason, emotionAnalysis, emotionOwnership, EMOTIONS, ANALYSIS_DIMENSIONS, affectLabel, analysisBasis,
  experienceStatus, reasonExplanation, resultLabel, AFFECT_LABELS, modelDiagnosticText,
} from "./model.mjs";
import { radar3d } from "./charts/radar3d.mjs";
import { mountRelationships } from "./charts/relationships.mjs";
import { mountEnergy } from "./charts/energy.mjs";
import { emotionChart } from "./charts/emotion.mjs";
import { renderSettings as settingsView, jumpToSettingsGroup, syncSettingsValues } from "./settings.mjs";
import { EXPERIENCE_TABS, experienceTabs, selectExperienceTab, turnPage, cancelPageTurn } from "./experience.mjs";
import { reconcileDraft } from "./draft.mjs";

const $ = id => document.getElementById(id);
const api = createApi(() => window.AstrBotPluginView || window.AstrBotPluginPage);
const uiKey = "livingemotion.view.v1";
const emptyFilters = () => Object.fromEntries(["emotion", "behavior", "diary", "dream"].map(kind => [kind, { page: 1, query: "" }]));
const state = {
  data: null, section: "overview", contextId: "", filters: emptyFilters(), kind: "diary",
  relationshipQuery: { platform: "", query: "", page: 1 },
  draft: Object.create(null), baseRevision: null, conflict: false, stale: true,
  baseValues: {}, configConflicts: [],
  loading: false, writing: false, generation: 0, recordGeneration: 0, preview: null,
  uncertain: new Set(), invalidFields: new Map(),
  selection: {}, scopes: null, options: {}, dispose: null, expandedSettingsGroup: null,
  bootstrapped: false,
  experienceRequests: {}, expandedExperience: "",
  expandedNight: {},
  behaviorLogSequence: 0, behaviorLogLoading: false,
};
try {
  const saved = object(JSON.parse(sessionStorage.getItem(uiKey) || "{}"));
  if (Object.hasOwn(SECTIONS, saved.section)) state.section = saved.section;
  if (typeof saved.contextId === "string") state.contextId = saved.contextId;
  if (object(saved.selection).persona_id) state.selection = scopeParams(saved.selection);
  if (EXPERIENCE_TABS.includes(saved.kind)) state.kind = saved.kind;
  state.experienceRequests = object(saved.experienceRequests);
  for (const kind of Object.keys(state.filters)) {
    const filter = object(object(saved.filters)[kind]);
    state.filters[kind] = {
      page: Number.isSafeInteger(filter.page) && filter.page > 0 ? filter.page : 1,
      query: text(filter.query, "").slice(0, 200),
    };
  }
  // 关系页的筛选与页码跟其他记录页一样跨刷新保留，避免自动刷新后回到第一页。
  const relationship = object(saved.relationshipQuery);
  state.relationshipQuery = {
    platform: text(relationship.platform, "").slice(0, 64),
    query: text(relationship.query, "").slice(0, 200),
    page: Number.isSafeInteger(relationship.page) && relationship.page > 0 ? relationship.page : 1,
  };
} catch (_) { /* The page also works when storage is unavailable. */ }
// 旧页签与会话缓存迁移：控制台始终读取当前人格的全局视图。
state.contextId = "";
state.selection = state.selection.persona_id ? { persona_id: state.selection.persona_id, view_scope: "global" } : {};

function remember() {
  try {
    sessionStorage.setItem(uiKey, JSON.stringify({
      section: state.section, contextId: state.contextId, selection: state.selection, filters: state.filters, kind: state.kind,
      relationshipQuery: state.relationshipQuery,
      experienceRequests: state.experienceRequests,
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
// 没有值的行直接不渲染：与其铺一排「未提供」，不如什么都不说。
function missingValue(value) {
  return value === null || value === undefined || value === "" || value === t("未提供");
}
function pairs(entries) {
  const dl = node("dl", undefined, "key-values");
  entries.filter(([, value]) => !missingValue(value))
    .forEach(([key, value]) => dl.append(node("dt", key), node("dd", value)));
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
  $("draft-feedback").textContent = message;
  $("draft-feedback").hidden = !message;
  $("editor").dataset.warning = String(type === "warning" || type === "error");
}
function canWrite() {
  return !!(state.data?.context_id || state.data?.scope_selection?.persona_id || state.data?.experience.persona_id) && !state.loading && !state.writing && !state.stale;
}
function selectedScope() { return Object.keys(state.selection).length ? state.selection : state.contextId; }
function handleError(error) {
  const failure = pageError(error);
  if (locale() !== "zh-CN") failure.message = controlled(failure.message);
  if (["unauthorized", "forbidden", "bridge_error"].includes(failure.code)) {
    if ($("content").contains($("settings"))) $("content").after($("settings"));
    cancelPageTurn();
    clearTimeout(experiencePoll);
    state.generation++;
    state.recordGeneration++;
    state.dispose?.(); state.dispose = null;
    state.data = null;
    renderEnvironment(null);
    state.draft = Object.create(null);
    state.invalidFields.clear();
    state.configConflicts = []; state.baseValues = {};
    state.preview = null;
    state.stale = true;
    state.contextId = "";
    state.filters = emptyFilters();
    // Retain opaque request identities only, so reconnecting reconciles a paid
    // request instead of dispatching again. All private snapshots/drafts vanish.
    try { sessionStorage.setItem(uiKey, JSON.stringify({ experienceRequests: state.experienceRequests })); } catch (_) {}
    state.scopes = null; state.selection = {};
    $("content").replaceChildren(node("p", t("私人内容已清空。请在 AstrBot 宿主重新登录并确认管理权限。"), "empty"));
    $("settings").replaceChildren();
    $("records").replaceChildren();
    $("settings").hidden = $("records").hidden = true;
    $("mode").textContent = failure.code === "bridge_error" ? t("连接未确认") : t("访问被拒绝");
    $("connection").textContent = t("需要重新确认宿主连接与权限");
    notify(failure.code === "bridge_error" ?
      t("宿主仅返回了未分型错误，无法确认访问状态，已隐藏私人内容。请重新连接后核对上次请求结果。") :
      t("访问被拒绝。页面参数不能代替宿主身份认证。"), "error");
  } else {
    if (failure.code === "version_conflict") state.conflict = true;
    const stale = state.stale && state.data ? t(" 当前显示旧快照，写操作已停用。") : "";
    notify(failure.code === "version_conflict" ?
      t("配置已变化，你的修改已保留。请刷新后核对冲突项。") :
      `${failure.message}（${failure.code}）${stale}`, failure.code === "version_conflict" ? "warning" : "error");
  }
  updateControls();
}
function updateControls() {
  const dirty = Object.keys(state.draft).length;
  $("refresh").disabled = state.loading || state.writing;
  $("content").setAttribute("aria-busy", String(state.loading));
  $("editor").hidden = !dirty && !state.invalidFields.size;
  if ($("editor").hidden) {
    $("draft-feedback").textContent = ""; $("draft-feedback").hidden = true;
  }
  document.body.dataset.configDirty = String(!$("editor").hidden);
  $("draft-count").textContent = t("有 {0} 项未保存", [dirty]) +
    (state.invalidFields.size ? t(" · {0} 项输入无效", [state.invalidFields.size]) : "");
  $("save").disabled = !canWrite() || !state.data?.capabilities.includes("config.write") || state.conflict ||
    !hasRevision(state.baseRevision) || !dirty || state.uncertain.has("config") || state.invalidFields.size > 0;
  $("save").textContent = state.writing ? t("正在保存…") : t("保存");
  $("rebase").hidden = !state.conflict;
  $("rebase").disabled = state.loading || state.writing || state.stale || !state.configConflicts.length;
  $("draft-review").hidden = !state.configConflicts.length;
  $("draft-conflicts").replaceChildren(...state.configConflicts.map(item => {
    const section = node("div", undefined, "draft-conflict");
    const label = state.data?.config.fields.find(field => field.key === item.key)?.label || item.key;
    const value = item => typeof item === "boolean" ? yesno(item) : text(item, t("未填写"));
    section.append(node("strong", controlled(label)), pairs([
      [t("最新配置"), value(item.current)], [t("我的修改"), value(item.draft)],
    ]));
    return section;
  }));
  $("discard").disabled = state.writing;
  const livingMemoryEnabled = Object.hasOwn(state.draft, "livingmemory_enabled") ? state.draft.livingmemory_enabled : state.data?.config.values.livingmemory_enabled;
  $("settings").querySelectorAll("input,select,textarea").forEach(control => {
    control.disabled = !canWrite() || control.dataset.editable !== "true" ||
      (control.dataset.key === "embedding_provider_id" && livingMemoryEnabled === true);
  });
  $("settings").querySelectorAll("[data-livingmemory-reason]").forEach(reason => {
    reason.hidden = livingMemoryEnabled !== true;
  });
  const sync = $("settings").querySelector("#memory-sync");
  if (sync) {
    sync.disabled = !canWrite() || livingMemoryEnabled !== true ||
      !state.data?.capabilities.includes("memory.sync") || state.uncertain.has("memory-sync");
  }
  $("content").querySelectorAll("[data-operation]").forEach(control => {
    const id = control.dataset.operation;
    if (id === "behavior.simulate") {
      control.disabled = !canWrite() || !state.data?.capabilities.includes("behavior.preview");
      return;
    }
    if (id === "diary.generate" || id === "dream.generate") {
      control.disabled = !canWrite() || !state.data?.actions.some(action => action.id === id && action.enabled) ||
        EXPERIENCE_ACTIVE.has(object(state.data?.experience[id.split(".")[0]]).status);
      return;
    }
    const target = id === "preview" ? actionTarget() : actionContextId(id);
    const supported = id === "preview" ? state.data?.capabilities.includes("behavior.preview") :
      state.data?.actions.some(action => action.id === id && action.enabled === true) && hasRevision(state.data?.revision);
    control.disabled = !canWrite() || !target || !supported || state.uncertain.has(id);
  });
  // 常驻阅读面板与普通历史列表都同步禁用过期/结果未知的置顶操作。
  document.querySelectorAll("[data-pin-entry]").forEach(control => {
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
  return details(t("来源与有效期"), pairs([
    [t("来源"), value.source === "human observation" ? t("人类观察记录") : text(value.source)], [t("更新时间"), date(value.updated_at ?? value.observed_at)],
    [t("有效期"), date(value.expires_at)],
    [t("有效状态"), expired(value.expires_at) === true ? t("已过期，不应作为当前依据") :
      expired(value.expires_at) === false ? t("有效期内") : t("未提供有效期")],
    ...extra,
  ]));
}
// 页面标题由顶部的 #section-kicker / #section-title 统一负责，这里只补
// 「一句说明 + 状态 chips」，避免同一页出现两个大标题。
function sectionHead(eyebrow, title, note, chips = []) {
  const root = node("div", undefined, "emotion-head page-subhead");
  const titleBox = node("div", undefined, "emotion-title");
  if (note) titleBox.append(node("p", note, "hint"));
  if (titleBox.childElementCount) root.append(titleBox);
  if (chips.length) {
    const row = node("div", undefined, "chip-row");
    for (const [label, tone] of chips) row.append(node("span", label, `chip${tone ? " " + tone : ""}`));
    root.append(row);
  }
  return root;
}
function isGlobalView() { return state.selection.view_scope === "global"; }
// 所有控制台动作都绑定一个具体会话。全局视图的 context_id 按约定留空，
// 宿主在 action_target 与每个动作的 context_id 里交代落点，页面照它提交。
function actionTarget() {
  const target = object(state.data?.action_target);
  return text(target.context_id, "") || text(state.data?.context_id, "");
}
function actionContextId(id) {
  const action = list(state.data?.actions).find(item => item.id === id);
  return text(action?.context_id, "") || actionTarget();
}
function actionTargetText() {
  const target = object(state.data?.action_target);
  const id = actionTarget();
  const label = text(target.label, "") || text(
    list(state.data?.contexts).find(item => item.id === id)?.label, "");
  return label
    ? t("全局视图不指定会话：这些操作作用于最近的会话「{0}」。要换会话，请在「查看范围」选择私聊或群聊。", [label])
    : t("暂时没有可操作的会话：插件重启后需要该会话先产生一条新消息，或者直接在「查看范围」选择私聊或群聊。");
}
function heroFacts() {
  const night = object(state.data.night);
  // 一行一个「标签 值」，不再上下堆叠，避免百分号掉到下一行造成错位。
  const wrap = node("dl", undefined, "hero-facts");
  for (const [key, value] of [
    [t("精力"), percent(night.energy)],
    [t("当前作息"), NIGHT_STATES[night.display_state] || text(night.state, t("未提供"))],
  ]) {
    const group = node("div", undefined, "hero-fact");
    group.append(node("dt", key), node("dd", value));
    wrap.append(group);
  }
  return wrap;
}
function feelingCard() {
  const feeling = object(state.data.feeling);
  const card = node("div", undefined, "hero-feeling");
  card.setAttribute("aria-label", t("此刻心绪"));
  card.append(node("span", t("此刻心绪"), "eyebrow"),
    node("p", feeling.text || t("静待下一次心绪落笔。"), "feeling-text"));
  const time = node("span", feeling.generated_at ? date(feeling.generated_at) : t("每 12 小时落笔一次"), "micro");
  if (feeling.generated_at) time.title = t("每 12 小时落笔一次");
  card.append(time);
  return card;
}
function botHero() {
  const bot = state.data.bot_state;
  const hero = node("section", undefined, "hero");
  hero.setAttribute("aria-label", t("TA 当前感受"));
  const main = node("div", undefined, "hero-main");
  const moodLine = node("div", undefined, "hero-mood");
  const identity = node("p", text(state.data.persona.name, t("原生人格未提供")), "ta-identity");
  moodLine.append(node("p", "TA / LIVE EMOTION", "hero-label"));
  main.append(moodLine);
  if (isGlobalView() || bot.global_view === true) {
    const hasState = !!(bot.label || Object.values(object(bot.dimensions)).some(value => typeof value === "number"));
    const title = bot.label ? affectLabel(bot.label) : hasState ? t("共享人格情绪") : t("尚无 TA 状态");
    // 情绪为主，人格与作息集中在下方；全局页不重复解释状态归属。
    const secondary = node("div", undefined, "hero-secondary");
    secondary.append(identity, heroFacts());
    main.append(node("h2", title, "hero-value"), secondary);
    hero.append(main, feelingCard());
    return hero;
  }
  moodLine.append(identity);
  main.append(node("h2", affectLabel(bot.label, t("尚无 TA 状态")), "hero-value"),
    node("p", text(bot.reason, t("等待有来源的互动与状态评估。不会以对方情绪替代 TA 感受。")), "hero-note"));
  const chips = node("div", undefined, "hero-chips");
  chips.append(node("span", `${t("更新")} ${date(bot.updated_at)}`, "chip"));
  main.append(chips, heroFacts());
  hero.append(main, feelingCard());
  if (expired(bot.expires_at)) hero.append(badge(t("状态已过期"), "warn"));
  return hero;
}
function observationBlock() {
  const value = state.data.observation;
  const analysis = emotionAnalysis(state.data).human;
  const section = block(t("对方观察"),
    node("p", affectLabel(value.label ?? list(analysis.labels).join(", "), t("尚无可用观察")), "observation-value"),
    node("p", t("这是对对方状态的观察，不是 TA 的感受。"), "hint"),
    pairs([[t("观察对象"), text(value.subject)], [t("可信度"), percent(value.confidence ?? analysis.confidence)],
      [t("观察依据"), analysisBasis(analysis.basis)], [t("原因"), text(value.reason)],
      [t("说明"), controlled(text(analysis.note))]]),
    sourceDetails(value),
  );
  section.classList.add("observation");
  section.setAttribute("aria-label", t("对方观察"));
  if (expired(value.expires_at)) section.append(badge(t("观察已过期，不作为当前依据"), "warn"));
  return section;
}
function healthBlock() {
  const section = block(t("依赖健康"));
  if (!state.data.health.length) section.append(node("p", t("宿主尚未提供依赖健康。"), "hint"));
  for (const item of state.data.health) {
    const statuses = { ok: [t("可用"), "good"], degraded: [t("降级"), "warn"], unavailable: [t("不可用"), "bad"] };
    const status = Object.hasOwn(statuses, item.status) ? statuses[item.status] : [t("未提供"), ""];
    const row = node("div", undefined, "health-row");
    row.append(node("strong", text(item.name)), badge(...status), node("p", text(item.reason), "hint"));
    section.append(row);
  }
  return section;
}
function renderOverview(container) {
  const global = isGlobalView();
  const analysis = emotionAnalysis(state.data).bot;
  const layout = node("div", undefined, global ? "ta-layout global" : "ta-layout");
  // 球体直接画六维分析（valence/arousal/stress/social_need/control/certainty），
  // 数值由球下方的图例承担，避免同一份数据在两处重复成表。
  layout.append(botHero(), radar3d(object(analysis.dimensions), {},
    { label: t("当前人格的六维情绪球"), dimensions: ANALYSIS_DIMENSIONS }));
  container.append(layout);
  container.append(emotionChart(state.data.emotion_curve));
  container.append(details(t("可用性与来源"), pairs([[t("状态"), state.data.availability.available === true ? t("可用") :
    state.data.availability.available === false ? t("暂不可用") : t("未提供")],
    [t("原因"), reasons(state.data.availability.reasons)], [t("来源"), text(state.data.bot_state.source)],
    [t("更新时间"), date(state.data.bot_state.updated_at)]])), details(t("依赖健康"), healthBlock()));
  if (state.selection.view_scope === "global" && ["scene", "context"].includes(emotionOwnership(state.data).kind)) {
    container.append(node("p", t("全局页面展示最近活跃会话的人格状态。"), "hint"));
  }
}
function personaPicker() {
  const personas = list(state.scopes?.personas);
  const root = node("div", undefined, "persona-picker");
  if (!personas.length) {
    root.append(node("p", t("宿主没有返回可用人格，无法在此切换。"), "hint"));
    return root;
  }
  const label = node("label", t("切换人格")); label.htmlFor = "persona-picker";
  const select = node("select"); select.id = "persona-picker";
  for (const item of personas) {
    const option = node("option", text(item.name ?? item.label, item.id));
    option.value = text(item.id, ""); select.append(option);
  }
  select.value = state.selection.persona_id || state.data.persona.id || "";
  const apply = button(t("应用"), () => {
    const value = select.value;
    if (!value || value === state.selection.persona_id) return;
    state.dispose?.(); state.dispose = null;
    state.selection = { persona_id: value, view_scope: state.selection.view_scope || "global" };
    state.contextId = ""; state.data = null; state.preview = null; state.filters = emptyFilters();
    $("content").replaceChildren(node("p", t("正在读取所选人格…"), "empty"));
    $("records").replaceChildren(); $("settings").replaceChildren(); loadState();
  }, "primary");
  apply.disabled = !state.scopes;
  const row = node("div", undefined, "persona-picker-row");
  row.append(select, apply);
  root.append(label, row, node("p", t("人格由 AstrBot 原生解析；换人格会重新读取该人格的状态，不会改动聊天模型。"), "hint"));
  return root;
}
function personaText(description) {
  const raw = text(description, "");
  if (!raw) return node("p", t("宿主没有返回这个人的「人格说明」（prompt）。请到 AstrBot 人格设置里填写，或确认当前范围能读取到人格。"), "empty");
  const wrapper = node("div", undefined, "persona-prose");
  // 保留原始换行与段落，不把 prompt 当 HTML 解析。
  for (const paragraph of raw.split(/\n{2,}/)) {
    const chunk = paragraph.trim();
    if (!chunk) continue;
    wrapper.append(node("p", chunk));
  }
  return wrapper;
}
// 人格说明按需从宿主 personas.system_prompt 读取；缓存避免自动刷新时重复请求。
const personaDescriptionCache = new Map();
const personaDescriptionErrors = new Set();
async function personaDescriptionLoader(personaId) {
  const key = text(personaId, "");
  if (!key) return "";
  if (personaDescriptionCache.has(key)) return personaDescriptionCache.get(key);
  const data = await api.personaDescription(key);
  const description = text(data.description, "");
  personaDescriptionCache.set(key, description);
  return description;
}
function renderDescriptionFailure(holder, container, personaId) {
  const retry = button(t("重新读取人格说明"), () => {
    personaDescriptionErrors.delete(personaId);
    personaLoadAttempts.delete(personaId);
    holder.replaceChildren(node("p", t("正在读取人格说明…"), "empty"));
    loadPersonaDescription(container, personaId);
  });
  holder.replaceChildren(node("p", t("人格说明读取失败；不影响其他页面。"), "hint"), retry);
  const status = container.querySelector("[data-persona-status]");
  if (status) status.textContent = t("读取失败");
}
const personaLoadAttempts = new Set();
async function loadPersonaDescription(container, personaId) {
  if (personaLoadAttempts.has(personaId)) return;
  personaLoadAttempts.add(personaId);
  const holder = container.querySelector("[data-persona-description]");
  const status = container.querySelector("[data-persona-status]");
  try {
    const description = await personaDescriptionLoader(personaId);
    if (holder) holder.replaceChildren(personaText(description));
    if (status) status.textContent = description ? t("已读取 {0} 字", [String(description.length)]) : t("未提供");
    if (description && state.data?.persona?.id === personaId) state.data.persona.description = description;
  } catch (error) {
    personaDescriptionErrors.add(personaId);
    if (holder) renderDescriptionFailure(holder, container, personaId);
    handleError(error);
  }
}
function renderPersona(container) {
  const value = state.data.persona;
  const personaId = text(value.id, text(state.selection.persona_id, ""));
  const description = node("div");
  description.dataset.personaDescription = "";
  const known = text(value.description, "") || text(personaDescriptionCache.get(personaId), "");
  if (known) description.append(personaText(known));
  else if (personaId && personaDescriptionErrors.has(personaId)) renderDescriptionFailure(description, container, personaId);
  else description.append(personaId ? node("p", t("正在读取人格说明…"), "empty") : personaText(""));
  const status = node("dd", known ? t("已读取 {0} 字", [String(known.length)]) : t("未提供"));
  status.dataset.personaStatus = "";
  const meta = pairs([
    [t("人格"), text(value.name, text(value.id))], [t("来源"), text(value.source)],
    [t("修订号"), text(value.revision)],
  ]);
  meta.append(node("dt", t("说明状态")), status);
  container.append(personaPicker(), block(t("当前人格"), meta),
    block(t("人格说明"), description),
    node("p", t("人格由 AstrBot 当前范围解析。切换页面主题不会切换人格；模型提供者也不代表 TA 身份。"), "hint"),
    button(t("前往设置修改人格相关选项"), () => navigateToSettings("persona")));
  if (!known && personaId && !personaDescriptionErrors.has(personaId)) loadPersonaDescription(container, personaId);
}
function analysisBlock({ includeHuman = true, data = state.data, title = t("TA 情绪分析"),
  showDimensions = true } = {}) {
  const { bot, human, available } = emotionAnalysis(data);
  const section = block(title, node("p", t("数值由本插件本地规则从四维状态推导，不是医学或心理诊断；缺少数据时不推测观测。"), "hint"));
  section.dataset.emotionAnalysis = "";
  if (!available) section.append(node("p", t("宿主尚未提供情绪分析，以下仅显示已有 TA 状态。"), "hint"));
  else {
    const grid = node("div", undefined, "metrics");
    for (const [key, label] of Object.entries(EMOTIONS)) grid.append(metric(label, object(bot.emotions)[key]));
    section.append(grid);
    if (showDimensions) section.append(block(t("六维分析"), pairs(Object.entries(ANALYSIS_DIMENSIONS).map(([key, label]) => {
      const value = object(bot.dimensions)[key];
      const valid = typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
      return [label, valid ? `${Math.round(value * 100)}%` : t("未提供")];
    }))));
    section.append(pairs([
      [t("分析方法"), bot.kind === "heuristic" ? t("四维情绪状态机 · 本地规则计算") : text(bot.kind)],
      [t("分析依据"), analysisBasis(bot.basis)],
      [t("说明"), controlled(text(bot.note))],
    ]), methodDetails());
  }
  if (includeHuman && Object.keys(human).length) section.append(block(t("对方分析 · HumanObservation"),
    node("p", t("这是对对方状态的观察，不是 TA 的感受。"), "hint"), pairs([
      [t("观察标签"), list(human.labels).map(label => affectLabel(label)).join(locale() === "en" ? ", " : "、") || t("未提供")],
      [t("可信度"), percent(human.confidence)], [t("观察依据"), analysisBasis(human.basis)],
    ])));
  return section;
}
// 方法说明直接来自 docs/emotion-analysis.md 的结论，可折叠，不编造外部链接。
function methodDetails() {
  const details = node("details", undefined, "method-details");
  details.append(node("summary", t("分析方法与局限")));
  const body = node("div", undefined, "details-content");
  body.append(
    node("p", t("方法：四维情绪状态机（pleasure / arousal / stress / social_need）＋事件增量＋半衰期回落，规则版本 emotion-1。"), "hint"),
    node("p", t("输入：带来源的真实事件（信号、置信度、时间）、本地规则表，可选模型给出的有界增量修正。"), "hint"),
    node("p", t("步骤：取权重 → 查增量 → 单次裁剪到 ±0.15 → 窗口预算限制 → 迟到衰减 → 写回四维状态 → 无事件时按半衰期回落到基准。"), "hint"),
    node("p", t("输出：6 个情绪倾向与 6 个分析维度（0–100%）；置信度是输入事件自带的，不被本地规则改写。"), "hint"),
    node("p", t("局限：规则驱动的近似，线性组合，没有学习与校准；描述的是软件状态，不是对人的心理测量。"), "hint"),
    node("p", t("完整说明见插件目录 docs/emotion-analysis.md。"), "micro"));
  details.append(body);
  return details;
}
function accountEmotionBlock() {
  const value = object(state.data.user_emotion);
  const section = block(t("TA 对此人的情绪"));
  section.dataset.accountEmotion = "";
  if (!Object.keys(value).length) {
    section.append(node("p", t("尚无此人的独立互动状态；不会用人格总体情绪代替。"), "hint"));
    return section;
  }
  section.append(node("h3", affectLabel(value.label)),
    node("p", t("仅由当前账号在此会话的真实互动独立更新，不跨用户、会话或人格合并；不是对方的情绪。"), "hint"),
    pairs([[t("观察对象"), text(value.subject)], [t("更新时间"), date(value.updated_at)]]),
    radar3d(object(value.dimensions), object(value.baseline), { label: t("对此人的四维情绪球") }),
    analysisBlock({ includeHuman: false, data: { bot_state: value }, title: t("对此人的情绪分析") }));
  return section;
}
function modelDiagnostic(kind) {
  const emotion = kind === "emotion", value = object(state.data[emotion ? "emotion_model_analysis" : "behavior_model"]);
  const statuses = { queued: t("已排队"), running: t("分析中"), completed: t("已完成"), skipped: t("已跳过"),
    failed: t("失败"), discarded: t("未应用"), cancelled: t("已取消"), unknown: t("结果不明") };
  const section = block(emotion ? t("最近一次模型细化") : t("发送模型检查"), pairs([
    [t("状态"), emotion ? statuses[value.status] || t("未采集") : value.available ? t("可用") : t("不可用")],
    [t("说明"), modelDiagnosticText(value.reason_code || "uncollected")],
    [t("排队时间"), date(value.queued_at)], [t("开始时间"), date(value.started_at)],
    [t("完成时间"), date(value.finished_at)],
  ]));
  if (emotion) section.append(node("p", t("情绪由新互动推动并随时间回落；LivingMemory 的词汇数量不决定情绪。刷新页面只读取状态。"), "hint"));
  section.dataset.modelDiagnostic = kind;
  return section;
}
function renderEmotion(container) {
  container.append(modelDiagnostic("emotion"));
  const ownership = emotionOwnership(state.data);
  // 保留机器可读的归属标记：测试与外部检查用它确认「没有把共享状态冒充逐人状态」。
  const ownershipTag = node("p", text(ownership.kind), "micro ownership-tag");
  ownershipTag.dataset.emotionOwnership = "";
  ownershipTag.hidden = true;
  container.append(ownershipTag);
  if (isGlobalView()) {
    // 全局范围没有「某个人/某个群」的情绪，先把这件事说清楚，再展示总体状态。
    const globalBlock = block(t("全局情绪"),
      node("p", t("当前是全局范围：这里没有「对某个人的情绪」，展示的是这个人格在全局层面的总体情绪状态，由全部已授权会话的互动共同累积。"), ""),
      node("p", t("要查看「TA 对此人的情绪」或某个会话的独立状态，请在上方「查看范围」选择私聊或群聊，再选具体会话。"), "hint"),
      pairs([[t("状态归属"), ownership.label], [t("归属类型"), text(ownership.kind, t("由宿主解析"))]]),
      state.data.bot_state.label ? node("span", "", "micro") : node("p", t("只有对方观察，不能变成 TA 感受"), "hint"),
      botHero(),
      analysisBlock({ includeHuman: false }));
    globalBlock.dataset.globalEmotion = "";
    container.append(globalBlock);
    return;
  }
  container.append(accountEmotionBlock());
  if (!state.data.bot_state.label) container.append(node("p", t("只有对方观察，不能变成 TA 感受"), "hint"));
  container.append(botHero());
  const columns = node("div", undefined, "columns");
  columns.append(radar3d(object(state.data.bot_state.dimensions), baselineDimensions(state.data), { label: t("当前人格的四维情绪球") }), observationBlock());
  container.append(block(t("四维状态分析"), columns));
  container.append(
    node("p", t("情绪会随时间回落到基准，新的互动才会推动变化；打开页面本身不会调用模型。"), "hint"),
    sourceDetails(state.data.bot_state), analysisBlock({ includeHuman: false }));
}
// 关系页平台候选只取当前人格真实出现过的平台；scopes.platforms 是所有人格的合集，
// 直接使用会让人选中一个本人物不存在的平台，查询结果看起来像“筛选没生效”。
function personaPlatforms() {
  const contexts = list(state.scopes?.contexts);
  if (!contexts.length) return list(state.scopes?.platforms);
  return [...new Set(contexts
    .filter(item => item?.persona_id === state.selection.persona_id && item.platform)
    .map(item => item.platform))].sort();
}
function renderRelationships(container) {
  if (!state.selection.persona_id) {
    container.append(node("p", t("没有已授权人格，不能查询关系。请刷新宿主范围。"), "empty")); return;
  }
  const panel = node("div"); panel.id = "relationship-body"; container.append(panel);
  state.dispose = mountRelationships(panel, {
    api, selection: { ...scopeParams(selectedScope()), platforms: personaPlatforms() },
    queryState: state.relationshipQuery,
    onQuery: value => { state.relationshipQuery = value; remember(); },
    stageNames: state.data.config.values.relationship_stage_names ?? Array.from({ length: 11 }, (_, index) => state.data.config.values[`relationship_stage_${index}_name`] || ""),
    persona: state.data.persona, canWrite: () => canWrite() && state.data.capabilities.includes("relationship.write"),
    // 好感是可改写的敏感数据：只有设置里显式打开才出现编辑表单。
    editEnabled: state.data.config.values.relationship_edit_enabled === true,
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
      const previous = button(t("上一页"), () => { page--; render(); });
      const next = button(t("下一页"), () => { page++; render(); });
      previous.disabled = page <= 1; next.disabled = page * PAGE_SIZE >= items.length;
      pager.append(previous, node("span", t("第 {0} 页 · 共 {1} 条 · 每页 10 条", [page, items.length])), next);
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
    node("p", t("硬否决：{0}", [reasons(value.vetoes ?? value.reasons)]), "hint"));
  if (value.score !== undefined) row.append(node("p", t("适合度：{0}", [text(value.score)]), "hint"));
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
    if (!allowed?.enabled) description.append(node("p", text(allowed?.reason, t("宿主未开放此操作，或尚未配置所需能力。")), "hint"));
    if (allowed?.reason_code) description.append(reasonCodeView(allowed.reason_code));
    if (state.uncertain.has(id)) description.append(node("p", t("上次执行结果不明。此页面已锁定重试，请核对执行记录。"), "error-text"));
    const control = button(label, () => runAction(id));
    control.dataset.operation = id;
    row.append(description, control);
    root.append(row);
  });
  return root;
}
function renderPreview(root) {
  root.replaceChildren();
  if (!state.preview) return;
  const preview = state.preview;
  // 模拟结果：只展示这一段话，不再堆判定明细。
  if (preview.simulated) {
    if (preview.status === "ok") {
      const quote = node("blockquote", controlled(text(preview.text, "")), "simulated-text");
      root.append(quote, node("p", t("这是模拟内容，没有发送；素材 {0} 条。",
        [text(preview.materials, "0")]), "hint"));
    } else {
      root.append(node("p", t("没有生成内容：{0}", [
        controlled(text(preview.reason_code, t("未知原因")))]), "hint warn-text"));
    }
    return;
  }
  const head = node("div", undefined, "preview-head");
  head.append(badge(preview.eligible === true ? t("模拟：符合条件") : t("模拟：暂不符合"),
    preview.eligible ? "good" : "warn"));
  if (typeof preview.score === "number") {
    head.append(node("span", t("时机分数 {0}{1}", [Math.round(preview.score * 100) / 100,
      typeof preview.min_score === "number" ? t(" · 门槛 {0}", [preview.min_score]) : ""]), "chip"));
  }
  root.append(head);
  const gates = list(preview.gates);
  if (gates.length) {
    const list_ = node("ul", undefined, "gate-list");
    for (const gate of gates) {
      list_.append(node("li", controlled(text(gate.text, gate.code))));
    }
    root.append(node("p", t("判定明细（全部满足才会真实发送）"), "hint"), list_);
  } else root.append(node("p", controlled(text(preview.reason_text, t("未提供判定明细。")))));
  root.append(node("p", t("模型调用 0 · 消息发送 0"), "hint"));
  if (list(preview.candidates).length) root.append(clientList(list(preview.candidates), candidate, ""));
}
const SIMULATION_EMOTIONS = [["current", "当前情绪"], ["calm", "平静"], ["joy", "喜悦"],
  ["sadness", "悲伤"], ["anger", "愤怒"], ["fear", "恐惧"], ["surprise", "惊讶"], ["disgust", "厌恶"]];
async function loadBehaviorOutcome(root) {
  if (!root || !state.data || state.section !== "behavior") return;
  const sequence = ++state.behaviorLogSequence;
  const scope = JSON.stringify(selectedScope());
  const filter = { ...state.filters.behavior };
  root.setAttribute("aria-busy", "true");
  state.behaviorLogLoading = true;
  try {
    const response = normalizeRecords(await api.records({
      ...scopeParams(selectedScope()), kind: "behavior", page: filter.page, page_size: PAGE_SIZE, query: filter.query,
    }), filter.page);
    if (!root.isConnected || sequence !== state.behaviorLogSequence || scope !== JSON.stringify(selectedScope())) return;
    if (filter.page > 1 && !response.items.length && response.total <= (filter.page - 1) * PAGE_SIZE) {
      state.filters.behavior.page = Math.max(1, Math.ceil(response.total / PAGE_SIZE));
      return void loadBehaviorOutcome(root);
    }
    const table = node("table", undefined, "behavior-log-table");
    const head = node("thead"), titles = node("tr");
    const labels = [t("时间"), t("发送 ID"), t("当时情绪"), t("目标 ID（QQ号）"), t("发送内容"), t("是否回应")];
    for (const label of labels) { const th = node("th", label); th.scope = "col"; titles.append(th); }
    head.append(titles); table.append(head);
    const body = node("tbody");
    for (const item of response.items) {
      const row = node("tr"); row.dataset.sendId = text(item.send_id ?? item.id, "");
      const time = node("td");
      const timestamp = node("time", date(item.timestamp ?? item.created_at,
        state.data.config.values.timezone, { year: "numeric", second: "2-digit" }));
      time.append(timestamp);
      const id = node("td"); id.append(node("code", row.dataset.sendId));
      // 旧记录不能用当前情绪补填，「当前情绪」也不是历史快照。
      const emotion = node("td", item.emotion_snapshot ? affectLabel(item.emotion_snapshot) :
        item.emotion_label && item.emotion_label !== "当前情绪" ? controlled(item.emotion_label) : t("未记录"));
      const target = node("td", item.simulated ? t("模拟") :
        `${text(item.target_label, "")} ${text(item.target_id, "")}`.trim());
      const content = node("td");
      const fallback = item.simulated && item.status === "running" ? t("生成中…") :
        item.simulated && item.status === "failed" ? t("生成失败") : t("内容未留存");
      content.append(node("p", text(item.content, "") || fallback, "body"));
      const replied = node("td", String(item.replied === true));
      [time, id, emotion, target, content, replied].forEach((cell, index) => { cell.dataset.label = labels[index]; row.append(cell); });
      body.append(row);
    }
    table.append(body);
    root.replaceChildren(response.items.length ? table : node("p", filter.query ? t("没有匹配日志。") : t("暂无发送日志。"), "hint"));
    if (response.total > PAGE_SIZE || filter.page > 1) {
      const pager = node("div", undefined, "pager");
      const change = page => { state.filters.behavior.page = page; remember(); void loadBehaviorOutcome(root); };
      const previous = button(t("上一页"), () => change(filter.page - 1));
      const next = button(t("下一页"), () => change(filter.page + 1));
      previous.disabled = filter.page <= 1; next.disabled = filter.page * PAGE_SIZE >= response.total;
      pager.append(previous, node("span", `${filter.page} / ${Math.max(1, Math.ceil(response.total / PAGE_SIZE))}`), next);
      root.append(pager);
    }
  } catch (error) {
    if (root.isConnected && sequence === state.behaviorLogSequence) handleError(error);
  } finally {
    if (sequence === state.behaviorLogSequence) { state.behaviorLogLoading = false; root.setAttribute("aria-busy", "false"); }
  }
}
function renderBehavior(container) {
  const panel = node("div"); panel.id = "behavior-panel";
  panel.dataset.persona = state.data.scope_selection?.persona_id || state.data.experience.persona_id;
  const dialog = node("dialog", undefined, "behavior-simulation-dialog");
  dialog.id = "behavior-simulation-dialog";
  const title = node("h2", t("测试发送")); title.id = "simulation-title";
  dialog.setAttribute("aria-labelledby", title.id);
  const label = node("label", t("情绪")); label.htmlFor = "simulation-emotion";
  const select = node("select"); select.id = "simulation-emotion";
  for (const [key, name] of SIMULATION_EMOTIONS) {
    const option = node("option", t(name)); option.value = key; select.append(option);
  }
  const generate = button(t("生成"), async () => {
    if (!canWrite()) return;
    state.writing = true; generate.disabled = true; updateControls();
    const requestId = crypto.randomUUID();
    try {
      const result = await api.simulate({ persona_id: panel.dataset.persona, emotion: select.value, request_id: requestId });
      if (result.api_version !== 1 || result.sends !== 0) throw new PageError("invalid_response", t("测试结果无效"));
      dialog.close();
      state.filters.behavior.page = 1; state.filters.behavior.query = ""; query.value = ""; remember();
      await loadBehaviorOutcome(outcome);
      notify(result.status === "completed" ? t("测试内容已写入日志。") : t("测试未完成，请查看日志。"),
        result.status === "completed" ? "" : "warning");
    } catch (error) { dialog.close(); handleError(error); await loadBehaviorOutcome(outcome); }
    finally { state.writing = false; generate.disabled = false; updateControls(); }
  }, "primary");
  const cancel = button(t("取消"), () => dialog.close());
  const actions = node("div", undefined, "simulation-actions"); actions.append(cancel, generate);
  dialog.append(title, label, select, actions);
  const test = button(t("测试发送"), () => { select.value = "current"; dialog.showModal(); });
  test.dataset.operation = "behavior.simulate";
  panel.append(block(t("测试发送"), node("p", t("按人格、所选情绪和现有素材生成；无素材也生成，结果写入下方日志。"), "hint"), test));
  const send = button(t("真实发送"), () => runAction("behavior.send"));
  send.dataset.operation = "behavior.send";
  panel.append(block(t("真实发送"), node("p", t("根据当前人格、情绪、关系和聊天素材生成，发送到当前会话。"), "hint"), send));
  const query = node("input"); query.type = "search"; query.maxLength = 200;
  query.id = "behavior-log-query"; query.placeholder = t("查询 ID、号码或内容");
  query.setAttribute("aria-label", query.placeholder); query.value = state.filters.behavior.query;
  let debounce;
  query.addEventListener("input", () => {
    state.filters.behavior.query = query.value; state.filters.behavior.page = 1; remember();
    clearTimeout(debounce); debounce = setTimeout(() => loadBehaviorOutcome(outcome), 250);
  });
  const outcome = node("div"); outcome.id = "behavior-outcome"; outcome.setAttribute("aria-live", "polite");
  panel.append(block(t("发送日志"), query, outcome), dialog); container.append(panel);
  void loadBehaviorOutcome(outcome);
}
async function submitNightAction(action) {
  if (!canWrite()) return;
  const allowed = state.data.actions.find(item => item.id === action && item.enabled === true);
  if (!allowed) { notify(state.data.actions.find(item => item.id === action)?.reason || t("当前不允许这个操作。"), "warning"); return; }
  const generation = state.generation;
  state.writing = true; updateControls();
  try {
    const result = await api.action({
      context_id: actionContextId(action), action, expected_revision: state.data.revision, confirmed: true,
      reason: action === "night.sleep" ? "管理端手动入睡" : "管理端手动叫醒",
    });
    if (generation !== state.generation) return;
    state.stale = true;
    if (result.status === "unknown") state.uncertain.add(action);
    notify(t("操作结果：{0}。{1}", [resultLabel(result.status), text(result.reason, "")]),
      result.status === "unknown" ? "warning" : "");
    try { applyData(await readStateConfig()); } catch (error) { handleError(error); }
  } catch (error) {
    if (generation === state.generation) {
      if (["timeout", "bridge_error", "invalid_response"].includes(pageError(error).code)) state.uncertain.add(action);
      handleError(error);
    }
  }
  finally { state.writing = false; updateControls(); }
}
async function enableNightSchedule() {
  if (!canWrite()) return;
  const generation = state.generation;
  state.writing = true; updateControls();
  try {
    const result = await api.save({
      context_id: state.contextId, expected_revision: state.baseRevision,
      patch: { night_schedule_enabled: true }, reason: "长夜页面：启用作息时间表",
    });
    if (generation !== state.generation) return;
    const checked = normalizeState(result);
    state.data.config = checked.config; state.baseRevision = checked.config.revision;
    state.stale = true;
    applyData(await readStateConfig());
    notify(t("作息时间表已启用，配置的入睡、深睡、午休与起床时间从现在开始生效。"));
  } catch (error) { if (generation === state.generation) handleError(error); }
  finally { state.writing = false; updateControls(); }
}
function clockText(value) {
  return typeof value === "string" && /^\d{2}:\d{2}$/.test(value) ? value : text(value);
}
function nightDetails(key, title, child) {
  const panel = details(title, child);
  panel.dataset.nightPanel = key;
  // 首次默认收起；刷新重建页面时保留用户的展开选择，不存储业务数据。
  panel.open = state.expandedNight[key] === true;
  panel.addEventListener("toggle", () => {
    if (panel.isConnected) state.expandedNight[key] = panel.open;
  });
  return panel;
}
function renderNight(container) {
  const value = state.data.night;
  const catchUp = object(value.catch_up);
  const plan = object(value.schedule);
  const stages = node("div", undefined, "sub-tabs"); stages.setAttribute("aria-label", t("五档作息"));
  for (const [key, label] of Object.entries(NIGHT_STATES)) stages.append(badge(label, value.display_state === key ? "good" : ""));
  container.append(stages);

  const head = sectionHead("NIGHT CYCLE", t("长夜"),
    t("作息、精力与醒后补课。手动操作只改变作息状态，不会改动聊天内容。"), [
      [`${t("作息状态")} · ${NIGHT_STATES[value.display_state] || text(value.state)}`],
      [`${t("作息时间表")} · ${plan.schedule_enabled ? t("已启用") : t("未启用")}`,
        plan.schedule_enabled ? "on" : "off"],
      [`${t("聊天可用")} · ${plan.allow_sleep ? t("受作息影响") : t("不受作息影响")}`],
    ]);
  container.append(head);
  // 长夜页精简：移除会话提示和周期详情，页头后直接展示精力。
  container.append(block(t("精力"), metric(t("当前精力"), value.energy)));

  const schedule = node("div");
  schedule.append(
    node("p", t("以下时间来自「设置 → 长夜」，与实际周期对应；改完设置保存后立即生效。"), "hint"),
    pairs([
      [t("夜间疲劳开始 / 结束"), `${clockText(plan.fatigue_start)} → ${clockText(plan.fatigue_end)}`],
      [t("深睡（最晚入睡）"), clockText(plan.deep_sleep_at)],
      [t("基础起床"), clockText(plan.wake_at)],
      [t("午休"), plan.nap_enabled ? `${clockText(plan.nap_start)} → ${clockText(plan.nap_end)}` : t("未启用")],
      [t("赖床范围"), t("{0}–{1} 分钟", [text(plan.lie_in_min), text(plan.lie_in_max)])],
      [t("聊天唤醒"), `${({ chat: t("仅私聊"), never: t("不可唤醒"), both: t("私聊或群原生 @") })[plan.wake_mode] || text(plan.wake_mode)} · ${t("{0} 轮 / {1} 分钟", [text(plan.wake_reply_limit), text(plan.wake_window_minutes)])}`],
      [t("允许睡眠影响聊天"), yesno(plan.allow_sleep)],
      [t("时区"), clockText(plan.timezone)],
    ]));
  if (!plan.schedule_enabled) {
    schedule.append(node("p", t("注意：作息时间表未启用，设置里的入睡 / 午休 / 深睡 / 起床时间目前不会自动生效，只有手动操作会改变作息。"), "error-text"));
    const enable = button(t("启用作息时间表"), enableNightSchedule, "primary");
    enable.dataset.operation = "enable-night-schedule";
    schedule.append(enable);
  }
  container.append(nightDetails("schedule", t("作息计划 · 来自设置"), schedule));

  container.append(nightDetails("catch-up", t("醒后补课"), pairs([
    [t("功能开关"), yesno(catchUp.enabled)],
    [t("补答开关"), yesno(catchUp.reply_enabled)],
    [t("已处理"), text(catchUp.completed)], [t("本次有界窗口"), text(catchUp.total)],
    [t("进度说明"), text(catchUp.reason)],
  ])));

  const manual = node("div");
  manual.append(
    node("p", t("手动入睡会直接进入睡眠；手动叫醒立即醒来，且不会修改精力值。两项都只执行一次。"), "hint"));
  for (const action of ["night.sleep", "night.wake"]) {
    const allowed = state.data.actions.find(item => item.id === action);
    const row = node("div", undefined, "action-row");
    const description = node("div");
    description.append(node("h3", ACTIONS[action][0]),
      node("p", allowed?.enabled ? (action === "night.sleep" ? t("现在就让 TA 去睡。") : t("立刻叫醒，不需要二次确认。")) : text(allowed?.reason, t("当前不允许这个操作。")), "hint"));
    const control = button(ACTIONS[action][0], () => submitNightAction(action),
      action === "night.wake" ? "primary" : "");
    control.dataset.operation = action;
    control.disabled = !canWrite() || !allowed?.enabled || state.uncertain.has(action);
    row.append(description, control);
    manual.append(row);
  }
  container.append(nightDetails("manual", t("手动作息"), manual));

  const energy = block(t("精力日志")); container.append(energy);
  if (state.selection.persona_id) state.dispose = mountEnergy(energy, { api, selection: selectedScope(), onError: handleError });
  else energy.append(node("p", t("没有已授权人格，不能查询精力历史。"), "empty"));
}
function reasonCodeView(code) {
  const root = node("div", undefined, "reason-code");
  root.append(pairs([[t("原因码 · reason_code"), text(code)]]), node("p", reasonExplanation(code), "hint"));
  return root;
}
// Only reconcile existing requests; polling and refresh never dispatch a model.
let experiencePoll = null;
let experienceViewScope = "", experienceConfigRevision = null;
const experienceRecordLoads = new Map(), experienceRecordKeys = new Map();
const EXPERIENCE_ACTIVE = new Set(["queued", "running", "pending", "request_unknown"]);
function experienceRunning() {
  const experience = object(state.data?.experience);
  return ["diary", "dream"].some(kind => EXPERIENCE_ACTIVE.has(object(experience[kind]).status));
}
function pollExperience() {
  clearTimeout(experiencePoll); experiencePoll = null;
  if (state.section !== "experience" || !state.data) return;
  const persona = state.data.experience.persona_id;
  const tasks = ["diary", "dream"].map(kind => [kind,
    state.experienceRequests[`${persona}:${kind}`] || state.data.experience[kind]?.request_id])
    .filter(([kind, id]) => id && (EXPERIENCE_ACTIVE.has(state.data.experience[kind]?.status) ||
      state.data.experience[kind]?.status === "request_unknown"));
  if (!tasks.length) return;
  experiencePoll = setTimeout(async () => {
    if (state.section !== "experience" || state.writing) return;
    for (const [kind, id] of tasks) {
      try {
        const result = await api.experienceTask(id);
        if (!state.data || state.data.experience.persona_id !== persona) return;
        if ((state.experienceRequests[`${persona}:${kind}`] || state.data.experience[kind]?.request_id) !== id) continue;
        state.data.experience[kind] = result;
        if (result.status === "succeeded") {
          state.filters[kind] = { page: 1, query: "" };
          state.expandedExperience = result.experience_id;
          delete state.experienceRequests[`${persona}:${kind}`];
          notify(t(kind === "diary" ? "已更新今日私人日记。" : "已更新今日梦境。"));
        } else if (!EXPERIENCE_ACTIVE.has(result.status)) {
          delete state.experienceRequests[`${persona}:${kind}`];
        }
      } catch (error) {
        if (!state.data || state.data.experience.persona_id !== persona) return;
        if ((state.experienceRequests[`${persona}:${kind}`] || state.data.experience[kind]?.request_id) !== id) continue;
        if (pageError(error).code === "validation_error") {
          delete state.experienceRequests[`${persona}:${kind}`];
          state.data.experience[kind] = { status: "failed", reason_code: "request_not_found" };
        } else { handleError(error); if (!state.data) return; }
      }
    }
    remember();
    if (state.data) {
      render();
    }
    pollExperience();
  }, 2000);
}
function renderExperience(container) {
  $("records").replaceChildren(); $("records").hidden = true;
  const value = state.data.experience;
  container.append(sectionHead("DIARY & DREAM", t("日记与梦境"),
    t("按当前人格保存。日记是私人自省，梦境始终是想象。")));
  const tabs = experienceTabs(state.kind, next => {
    const previous = state.kind;
    if (previous === next) return;
    state.kind = next; remember(); syncExperience();
    turnPage(previous, next, [$(`experience-panel-${next}`)]);
    $(`experience-tab-${next}`)?.focus({ preventScroll: true });
  });
  container.append(tabs);
  const book = node("div", undefined, "experience-book"); book.id = "experience-panel"; container.append(book);
  for (const kind of EXPERIENCE_TABS) {
    const panel = node("section", undefined, "experience-paper");
    panel.id = `experience-panel-${kind}`;
    panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", `experience-tab-${kind}`);
    book.append(panel);
  if (kind === "settings") {
    panel.append(node("p", t("这里的作息和额度只控制自动生成；手动按钮立即生成当日内容，但梦境需要先开启「梦境生成」。"), "hint"));
    panel.append($("settings"));
  } else {
    const task = node("div"); task.dataset.experienceControls = kind; panel.append(task);
    const records = node("div"); records.id = `${kind}-record-body`; records.dataset.experienceRecords = kind;
    records.setAttribute("aria-live", "polite"); panel.append(records);
  }
  }
  experienceRecordLoads.clear(); experienceRecordKeys.clear();
  syncExperience();
  pollExperience();
}
function renderExperienceTask(kind) {
  const panel = document.querySelector(`[data-experience-controls="${kind}"]`);
  if (!panel) return;
  const value = state.data.experience;
  const task = object(value[kind]);
  const action = state.data.actions.find(item => item.id === `${kind}.generate`);
  const signature = JSON.stringify([task, action]);
  if (panel.dataset.signature === signature) return;
  panel.dataset.signature = signature;
  const focused = panel.contains(document.activeElement);
  panel.replaceChildren();
  const label = kind === "diary" ? t("生成私人日记") : t("生成梦境");
  const control = button(label, () => generateExperience(kind), "primary");
  control.dataset.operation = `${kind}.generate`;
  panel.className = "experience-controls";
  panel.append(control);
  if (action?.reason) panel.append(node("p", controlled(action.reason), "hint warn-text"));
  const statuses = { idle: t("尚未生成"), queued: t("已排队"), running: t("正在生成"),
    succeeded: t("私人档案已更新"), failed: t("生成失败，原内容保留"),
    cancelled: t("任务已取消，原内容保留"), unknown: t("执行结果不明"),
    request_unknown: t("正在核对执行结果") };
  const taskCard = node("span", statuses[task.status] || experienceStatus(task.status), "micro");
  taskCard.dataset.experienceTask = kind;
  if (task.reason_code && ["failed", "cancelled", "unknown"].includes(task.status)) {
    taskCard.append(reasonCodeView(task.reason_code));
  }
  if (task.status === "unknown") taskCard.append(node("p",
    t("模型可能已经消耗费用。再次点击会发起新请求，可能再次计费；不会自动重试。"), "hint warn-text"));
  panel.append(taskCard);
  if (focused && !panel.closest(".experience-paper").hidden) control.focus({ preventScroll: true });
}
function syncExperience() {
  if (!$("experience-panel") || !state.data) return;
  selectExperienceTab(document.querySelector(".experience-tabs"), state.kind);
  for (const kind of EXPERIENCE_TABS) {
    const panel = $(`experience-panel-${kind}`); panel.hidden = kind !== state.kind;
    if (kind !== "settings") {
      renderExperienceTask(kind);
      const root = panel.querySelector("[data-experience-records]");
      root.id = kind === state.kind ? "record-body" : `${kind}-record-body`;
    }
  }
  $("settings").hidden = state.kind !== "settings";
  $("records").hidden = true;
  if (state.kind !== "settings") {
    const kind = state.kind, root = $("record-body"), task = object(state.data.experience[kind]);
    const key = JSON.stringify([state.generation, state.filters[kind], task.status === "succeeded" ? task.experience_id : null,
      state.data.experience[kind + "_today"]?.experience_id]);
    if (experienceRecordKeys.get(kind) !== key) {
      experienceRecordKeys.set(kind, key); loadRecords(kind, root);
    }
  }
  updateControls();
}

async function generateExperience(kind) {
  if (!canWrite() || !state.data.actions.some(action => action.id === `${kind}.generate` && action.enabled)) return;
  const persona = state.data.experience.persona_id, key = `${persona}:${kind}`;
  if (EXPERIENCE_ACTIVE.has(state.data.experience[kind]?.status)) return;
  const requestId = crypto.randomUUID();
  state.experienceRequests[key] = requestId;
  state.data.experience[kind] = { request_id: requestId, status: "queued" };
  state.writing = true; remember(); syncExperience();
  try {
    const result = await api.experienceGenerate({ request_id: requestId, persona_id: persona, kind });
    if (!state.data || state.data.experience.persona_id !== persona) return;
    if ((state.experienceRequests[key] || state.data.experience[kind]?.request_id) !== requestId) return;
    state.experienceRequests[key] = result.request_id;
    state.data.experience[kind] = result;
    if (result.status === "succeeded") {
      state.filters[kind] = { page: 1, query: "" };
      state.expandedExperience = result.experience_id;
    }
  } catch (error) {
    if (["timeout", "bridge_error", "invalid_response"].includes(pageError(error).code) && state.data) {
      state.data.experience[kind] = { request_id: requestId, status: "request_unknown" };
    } else delete state.experienceRequests[key];
    handleError(error);
  } finally {
    state.writing = false; remember();
    if (state.data && state.section === "experience") syncExperience();
    updateControls(); pollExperience();
  }
}
async function syncPersonaMemory(control) {
  if (!canWrite()) return;
  control.disabled = true;
  const label = control.textContent;
  control.textContent = t("正在同步…");
  try {
    const result = await api.memorySync({ context_id: state.contextId });
    if (result.status !== "synced") throw new PageError(result.reason_code || "memory_sync_failed",
      t("同步未完成：{0}", [result.reason_code || t("未知原因")]));
    notify(t("已从 LivingMemory 读取 {0} 条记忆，保存 {1} 条到本地镜像。",
      [text(result.read), text(result.stored)]));
    applyData(await readStateConfig());
  } catch (error) { handleError(error); }
  finally { control.textContent = label; updateControls(); }
}
function renderMemory(container) {
  const value = state.data.memory;
  const mirror = object(value.mirror);
  const external = value.mode === "external";
  // 页面标题已经是「记忆接入」，这里不再重复一遍大标题。
  const rows = [
    [t("当前后端"), text(value.backend)],
    [t("允许检索"), yesno(value.can_read)],
    [t("允许写入"), yesno(value.can_write)],
    [t("绑定人格"), text(value.persona_id, t("未选择人格"))],
  ];
  if (external) rows.push([t("提供者"), value.provider || "astrbot_plugin_livingmemory"]);
  if (value.reason) rows.push([t("状态说明"), controlled(text(value.reason))]);
  container.append(block(t("接入状态"),
    node("p", t("这里显示真实的记忆后端与能力；改后端请到「设置 → 记忆」。"), "hint"),
    pairs(rows)));

  const capabilityList = node("ul", undefined, "capability-list");
  for (const item of list(value.capabilities)) capabilityList.append(node("li", controlled(text(item))));
  container.append(block(t("实际能力"),
    list(value.capabilities).length
      ? capabilityList
      : node("p", t("当前后端没有声明可用能力；不会用演示数据补位。"), "hint")));

  const mirrorBlock = block(t("当前人格的记忆镜像"),
    node("p", t("镜像是一份只读副本，用来在管理端核对「到底读到了多少条」；对话检索仍然走 LivingMemory 实时接口。"), "hint"),
    pairs([
      [t("镜像条数"), text(mirror.total)],
      [t("最近同步"), date(mirror.synced_at)],
      [t("是否截断"), mirror.truncated ? t("是，超出单次上限") : t("否")],
    ]));
  if (!mirror.total) {
    mirrorBlock.append(node("p", t("还没有同步过。勾选「使用 LivingMemory」后，点下面的按钮读取当前人格的全量记忆。"), "hint"));
  }
  if (external && value.provider_ready !== true) {
    mirrorBlock.append(node("p", t("LivingMemory 插件当前不可用或数据库未打开，暂时无法同步。"), "error-text"));
  }
  const sync = button(t("手动同步当前人格记忆"), () => syncPersonaMemory(sync), "primary");
  sync.dataset.operation = "memory-sync";
  sync.disabled = !canWrite() || !external || value.provider_ready !== true;
  mirrorBlock.append(sync);
  container.append(mirrorBlock);
  container.append(node("p", t("关闭 LivingMemory 后使用本地向量模式；开启 LivingMemory 外部后端后，自动收录转由 LivingMemory 负责，本地向量自动收录停止。"), "hint"));
  container.append(node("p", t("要更换记忆后端、开启检索或写入权限，请到「设置 → 记忆」修改并保存；本页不再提供跳转按钮。"), "hint"));
}
const renderers = {
  overview: renderOverview, persona: renderPersona, emotion: renderEmotion, behavior: renderBehavior,
  night: renderNight, experience: renderExperience, memory: renderMemory, relationships: renderRelationships,
  settings: container => container.append(node("p", t("按任务完成配置，所有更改统一保存。"), "hint")),
};

function renderSettings() {
  settingsView($("settings"), state, state.options, updateControls, personaDescriptionLoader);
}
function navigateToSettings(group) {
  navigate("settings");
  jumpToSettingsGroup($("settings"), group, state);
}
function render(preserveSettings = false) {
  for (const label of document.querySelectorAll("[data-section-label]")) label.textContent = SECTIONS[label.dataset.sectionLabel][2];
  const [number, name, title] = SECTIONS[state.section];
  $("section-kicker").textContent = `${number} / ${name}`;
  $("section-title").textContent = title;
  document.querySelectorAll("[data-section]").forEach(button => {
    if (button.dataset.section === state.section) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  document.body.dataset.leSection = state.section;
  if (!state.data) { updateControls(); return; }
  const detail = object(state.data.mode_detail);
  const labels = { active: t("参与中 · 自主发送"), observe_only: t("仅观察 · 不自主发送"), disabled: t("已停用") };
  let modeLabel = labels[state.data.mode] || t("模式未提供");
  if (state.data.mode === "observe_only" && detail.configured === "active") modeLabel = t("受限 · 仅观察");
  $("mode").textContent = modeLabel;
  $("mode").className = `status ${state.data.mode === "active" ? "good" : "warn"}`;
  $("mode").title = text(detail.reason_text, "");
  if (preserveSettings && state.section === "settings") {
    syncSettingsValues($("settings"), state); updateControls(); return;
  }
  if (state.section === "behavior" && $("behavior-panel")?.dataset.persona ===
      (state.data.scope_selection?.persona_id || state.data.experience.persona_id)) {
    void loadBehaviorOutcome($("behavior-outcome")); updateControls(); return;
  }
  const experienceScope = JSON.stringify([state.data.experience.persona_id, scopeParams(selectedScope())]);
  if (state.section === "experience" && experienceViewScope === experienceScope && $("experience-panel")) {
    if (preserveSettings) syncSettingsValues($("settings"), state);
    else if (experienceConfigRevision !== state.data.config.revision) {
      renderSettings(); experienceConfigRevision = state.data.config.revision;
    }
    syncExperience(); pollExperience(); updateControls(); return;
  }
  // 配置节点借给设置面板使用；离开时归还，避免随内容销毁。
  if ($("content").contains($("settings"))) $("content").after($("settings"));
  experienceViewScope = state.section === "experience" ? experienceScope : "";
  experienceConfigRevision = state.data.config.revision;
  state.dispose?.(); state.dispose = null;
  const container = $("content"); container.replaceChildren();
  renderers[state.section](container);
  renderSettings();
  if (state.section === "experience") syncExperience();
  renderRecordsShell();
  updateControls();
}
function selectedKind() {
  return state.section === "emotion" ? "emotion" : state.section === "behavior" ? "behavior" :
    state.section === "experience" && state.kind !== "settings" ? state.kind : null;
}
function renderRecordsShell() {
  if (["experience", "behavior"].includes(state.section)) { $("records").replaceChildren(); $("records").hidden = true; return; }
  state.recordGeneration++;
  const root = $("records"); root.replaceChildren();
  const kind = selectedKind();
  root.hidden = !kind;
  if (!kind) return;
  // 记录区只做展示，不再提供关键词筛选。
  const body = node("div"); body.id = "record-body"; body.setAttribute("aria-live", "polite");
  body.tabIndex = -1;
  root.append(body);
  loadRecords();
}
function timeline(items) {
  const values = items.slice().reverse().map(item => unit(object(item.after).pleasure));
  if (!values.some(value => value !== null)) return node("p", t("当前页无有效数值曲线；详情按原记录显示。"), "hint");
  const root = node("figure"); root.style.margin = "20px 0";
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.classList.add("chart"); svg.setAttribute("viewBox", "0 0 600 100"); svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("role", "img"); svg.setAttribute("aria-label", t("当前页 TA 愉悦趋势，数值见各条记录的前后对照"));
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
  root.append(svg, node("figcaption", t("TA 愉悦 · 当前页由旧到新 · 0–100% · 非连续时间轴"), "chart-caption"));
  return root;
}
function emotionTable(item) {
  const table = node("table");
  const head = node("thead"), heading = node("tr");
  for (const label of [t("TA 维度"), t("变化前"), t("变化后")]) { const th = node("th", label); th.scope = "col"; heading.append(th); }
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
  if (kind === "diary" || kind === "dream") return paperView(item, kind);
  const article = node("article", undefined, "record"); article.dataset.recordId = text(item.id, "");
  const heading = node("div", undefined, "record-heading");
  const title = node("h3");
  title.append(node("span", String((state.filters[kind].page - 1) * PAGE_SIZE + index + 1).padStart(2, "0"), "record-number"),
    node("span", text(item.title ?? item.label ?? item.candidate, { emotion: t("情绪变化"), behavior: t("行为记录"), diary: t("私人日记"), dream: t("梦境") }[kind])));
  heading.append(title, node("span", date(item.created_at), "micro")); article.append(heading);
  if (kind === "dream") article.append(badge(t("梦境 · 想象，不是现实事实"), "warn"));
  if (kind === "diary") article.append(badge(t("私人日记 · 主观内容")));
  if (kind === "diary") {
    const weather = object(item.weather), header = object(item.header);
    article.append(node("p", `${text(item.date ?? header.date, date(item.created_at))} · ${text(item.city ?? header.city, t("住所未提供"))} · ${text(weather.summary ?? header.weather, t("天气未获取"))}`, "micro"));
  }
  article.append(node("p", text(item.reason), "record-reason"));
  if (item.reason_code) article.append(reasonCodeView(item.reason_code));
  if (kind === "emotion") {
    article.append(emotionTable(item),
      node("p", expired(item.expires_at) === true ? t("已过期") : expired(item.expires_at) === false ? t("有效期内") : t("有效期未提供"), "hint"));
  } else if (kind === "behavior") {
    article.append(pairs([
      [t("用途"), ({ behavior: t("主动行为"), closing: t("睡前收尾"), catchup: t("醒后补答") })[item.purpose] || t("未采集")],
      [t("执行状态"), resultLabel(item.result ?? item.status)],
      [t("发送凭据"), ({ confirmed: t("协议端已确认"), unknown: t("结果不明，可能已经发送"), rejected: t("已拒绝"),
        uncollected: t("未采集") })[item.transport_status] || t("未采集")],
      [t("消息编号"), text(item.receipt_id, "")],
      [t("硬否决"), reasons(item.vetoes)],
    ]));
    if ((item.result ?? item.status) === "unknown") article.append(node("p", t("结果不明，消息可能已发送；不会自动重发。"), "error-text"));
  } else {
    const body = node("div");
    body.append(node("p", text(item.body, t("正文未提供。")), "body"));
    body.append(pairs([...(kind === "dream" ? [[t("清晰度"), percent(item.clarity)]] : []), [t("置顶"), yesno(item.pinned)]]));
    const pin = button(item.pinned ? t("取消置顶") : t("置顶"), () => runAction("experience.pin", item));
    pin.dataset.pinEntry = text(item.id, "");
    pin.dataset.pinAvailable = String(item.pin_available === true &&
      typeof item.context_id === "string" && !!item.context_id && typeof item.pinned === "boolean");
    pin.disabled = !canWrite() || pin.dataset.pinAvailable !== "true" ||
      state.uncertain.has(`experience.pin:${item.id}`);
    body.append(pin);
    article.append(details(t("阅读私人正文"), body));
    article.append(details(t("素材来源与角色"), clientList(list(item.sources), source => {
      const entry = node("div", undefined, "record");
      entry.append(badge({ bot_action: t("我做的"), human_action: t("对方说 / 做的"), dream: t("梦中内容"), unknown: t("来源不明") }[source.kind] || t("来源不明")),
        node("p", text(source.label)), node("p", text(source.excerpt), "body"), node("p", text(source.source_id), "micro"));
      return entry;
    }, t("未提供来源，不能据此认领真实事件。"))));
  }
  article.append(jsonDetails(t("上下文、来源与耗时"), {
    id: item.id, source: item.source, context: item.context, request_id: item.request_id,
    intent_id: item.intent_id, latency_ms: item.latency_ms, expires_at: item.expires_at, visibility: item.visibility,
  }));
  return article;
}
function paperView(item, kind) {
  const article = node("article", undefined, "paper-entry record");
  article.dataset.recordId = text(item.id, "");
  const paper = node("details", undefined, "paper-sheet");
  const header = object(item.header), weather = object(item.weather);
  let body = text(item.body, t("正文未提供。"));
  const weatherText = weather.summary ?? header.weather ??
    body.match(/^天气[：:]\s*(.+)$/m)?.[1] ?? "";
  const day = text(item.date ?? item.period ?? header.date,
    body.match(/^日期[：:]\s*(\d{4}-\d{2}-\d{2})/m)?.[1] ?? date(item.created_at));
  // 程序头只显示一次，正文保持纯文本，不把内容当成 HTML。
  body = body.replace(/^(?:日期|住所|城市|天气)[：:].*(?:\r?\n|$)/gm, "")
    .replace(/^Dream \(imagined\):\s*/, "").trim();
  const summary = node("summary", undefined, "paper-heading");
  summary.append(node("h3", text(item.title, kind === "diary" ? t("私人日记") : t("梦境"))));
  const metadata = node("div", undefined, "paper-meta");
  metadata.append(node("time", day));
  if (kind === "diary" && weatherText) metadata.append(node("span", weatherText));
  summary.append(metadata);
  paper.append(summary, node("div", body, "paper-body"));
  paper.addEventListener("toggle", () => {
    if (paper.open && !matchMedia("(prefers-reduced-motion: reduce)").matches)
      paper.querySelector(".paper-body").animate([
        { opacity: .2, transform: "translateY(-6px) scaleY(.95)", filter: "blur(1px)" },
        { opacity: 1, transform: "translateY(0) scaleY(1)", filter: "blur(0)" },
      ], { duration: 300, easing: "cubic-bezier(.2,.8,.2,1)" });
  });
  article.append(paper);
  return article;
}
async function loadRecords(requestKind, requestRoot) {
  const kind = typeof requestKind === "string" ? requestKind : selectedKind(), root = requestRoot || $("record-body");
  if (!kind || !root) return;
  if (!state.data?.context_id && !state.data?.scope_selection?.persona_id && !state.data?.experience.persona_id) {
    root.replaceChildren(node("p", t("当前没有已授权范围，不能查询记录。"), "empty"));
    root.setAttribute("aria-busy", "false");
    return;
  }
  const experience = ["diary", "dream"].includes(kind);
  const sequence = experience ? (experienceRecordLoads.get(kind) || 0) + 1 : ++state.recordGeneration, generation = state.generation;
  if (experience) experienceRecordLoads.set(kind, sequence);
  const current = () => root.isConnected && generation === state.generation &&
    sequence === (experience ? experienceRecordLoads.get(kind) : state.recordGeneration);
  const opened = [...root.querySelectorAll("article")].map(article => [
    article.dataset.recordId, [...article.querySelectorAll("details")].map(d => d.open),
  ]);
  const scroll = root.closest(".experience-paper")?.scrollTop;
  const retainedFocus = root.contains(document.activeElement) ? document.activeElement.textContent : "";
  const filter = { ...state.filters[kind] };
  root.setAttribute("aria-busy", "true");
  if (!root.childElementCount) root.replaceChildren(node("p", t("正在读取记录…"), "empty"));
  try {
    const response = normalizeRecords(await api.records({
      ...(["diary", "dream"].includes(kind) ? {
        persona_id: state.data.experience.persona_id, view_scope: "global",
      } : scopeParams(selectedScope())), kind, page: filter.page, page_size: PAGE_SIZE, query: filter.query,
    }), filter.page);
    if (!current()) return;
    root.replaceChildren();
    if (!response.items.length) root.append(node("p", filter.query ? t("没有符合筛选的记录。可以清空关键词重试。") : t("当前范围暂无记录。不会用演示内容填充。"), "empty"));
    if (kind === "emotion") root.append(timeline(response.items));
    response.items.forEach((item, index) => root.append(recordView(item, kind, index)));
    for (const [id, flags] of opened) {
      const article = [...root.querySelectorAll("article")].find(a => a.dataset.recordId === id);
      article?.querySelectorAll("details").forEach((d, index) => { d.open = flags[index] === true; });
    }
    if (state.expandedExperience) {
      [...root.querySelectorAll("article")].find(item => item.dataset.recordId === state.expandedExperience)
        ?.querySelector("details")?.setAttribute("open", "");
    }
    const pager = node("div", undefined, "pager");
    const changePage = page => { state.filters[kind].page = page; remember(); loadRecords(kind, root); };
    const previous = button(t("上一页"), () => changePage(Math.max(1, filter.page - 1)));
    const next = button(t("下一页"), () => changePage(filter.page + 1));
    previous.disabled = filter.page <= 1; next.disabled = filter.page * PAGE_SIZE >= response.total;
    pager.append(previous, node("span", t("第 {0} / {1} 页 · 共 {2} 条 · 每页 10 条", [filter.page, Math.max(1, Math.ceil(response.total / PAGE_SIZE)), response.total])), next);
    root.append(pager);
    if (scroll !== undefined) root.closest(".experience-paper").scrollTop = scroll;
    if (retainedFocus) {
      const control = retainedFocus === t("下一页") ? next : previous;
      (control.disabled ? root : control).focus();
    }
  } catch (error) {
    if (!current()) return;
    root.replaceChildren(node("p", t("记录读取失败，不表示没有记录。"), "error-text"), button(t("重试读取"), loadRecords));
    handleError(error);
  } finally { if (current()) root.setAttribute("aria-busy", "false"); }
}
function applyData(raw, preserveSettings = false) {
  const scroll = { x: window.scrollX, y: window.scrollY };
  const data = normalizeState(raw);
  const dirty = Object.keys(state.draft).length;
  if (dirty && data.context_id !== state.contextId) throw new PageError("invalid_context", t("宿主返回了不同范围，未将草稿应用到其他范围。"));
  const allowed = new Set(data.config.fields.filter(field => !field.readonly).map(field => field.key));
  if (dirty) {
    const reconciled = reconcileDraft(state.draft, state.baseValues, data.config.values, allowed);
    state.draft = reconciled.patch; state.configConflicts = reconciled.conflicts;
    state.conflict = reconciled.conflicts.length > 0;
    if (state.conflict) {
      $("draft-review").open = true;
      notify(t("有 {0} 项也在别处修改。请核对下方内容，再选择保留我的修改或放弃更改。", [reconciled.conflicts.length]), "warning");
    }
  }
  state.data = data; state.contextId = data.context_id; state.stale = false; state.bootstrapped = true;
  if (!state.expandedExperience && ["diary", "dream"].includes(state.kind)) {
    state.expandedExperience = data.experience[state.kind + "_today"]?.experience_id || "";
  }
  for (const kind of ["diary", "dream"]) {
    const pending = state.experienceRequests[`${data.experience.persona_id}:${kind}`];
    if (pending && data.experience[kind]?.request_id !== pending) {
      data.experience[kind] = { request_id: pending, status: "request_unknown" };
    }
  }
  if (data.scope_selection.persona_id) state.selection = scopeParams(data.scope_selection);
  if (!state.conflict) {
    state.baseRevision = data.config.revision;
    state.baseValues = { ...data.config.values }; state.configConflicts = [];
  }
  for (const key of state.invalidFields.keys()) if (!allowed.has(key)) state.invalidFields.delete(key);
  renderEnvironment(data.environment);
  $("connection").textContent = t("更新于 {0}", [date(data.updated_at)]);
  remember(); render(preserveSettings);
  // 重建配置控件时保留阅读位置，浮动保存后不跳到页面头尾。
  if (state.section === "settings" || state.section === "experience") window.scrollTo(scroll.x, scroll.y);
}
let environmentClock = null;
let environmentSnapshot = null;
function tickEnvironment() {
  if (!environmentSnapshot) return;
  const { value, started, timeFormat, dateFormat } = environmentSnapshot;
  // 宿主时间 + 单调时钟，不依赖浏览器所在时区或用户电脑的钟表设置。
  const instant = new Date(value.server_time * 1000 + performance.now() - started);
  $("environment-clock").textContent = timeFormat.format(instant);
  $("environment-clock").dateTime = instant.toISOString();
  $("environment-date").textContent = dateFormat.format(instant);
  const weather = object(value.weather);
  $("environment-weather").textContent = weather.status === "ok" &&
    Number.isFinite(weather.observed_at) && Math.abs(instant.getTime() / 1000 - weather.observed_at) <= 3600
    ? controlled(weather.summary) : controlled(weather.status === "loading" ? "天气更新中" : "天气暂不可用");
}
function renderEnvironment(raw) {
  const previous = environmentSnapshot;
  clearInterval(environmentClock);
  environmentSnapshot = null;
  const card = $("environment");
  card.hidden = true;
  for (const child of card.children) child.textContent = "";
  const value = object(raw);
  if (value.enabled !== true || !value.city || !value.timezone ||
      !Number.isFinite(value.server_time)) return;
  try {
    const options = { timeZone: value.timezone };
    const timeFormat = new Intl.DateTimeFormat(locale(), {
      ...options, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
    });
    const dateFormat = new Intl.DateTimeFormat(locale(), {
      ...options, month: "short", day: "numeric", weekday: "short",
    });
    environmentSnapshot = { value, started: previous?.value === raw ? previous.started : performance.now(), timeFormat, dateFormat };
    $("environment-city").textContent = value.city;
    $("environment-zone").textContent = value.timezone;
    card.hidden = false;
    tickEnvironment();
    environmentClock = setInterval(tickEnvironment, 1000);
  } catch (_) { environmentSnapshot = null; card.hidden = true; }
}
function checkedConfig(raw) {
  const config = raw?.config ?? raw;
  if (!config || !Array.isArray(config.fields) || !config.values ||
      typeof config.values !== "object" || Array.isArray(config.values) || !hasRevision(config.revision)) {
    throw new PageError("invalid_response", t("配置读取失败，写操作已停用。"));
  }
  return config;
}
async function readConfiguration() {
  if (state.data?.capabilities.includes("configuration.read")) return checkedConfig(await api.configuration(selectedScope()));
  return checkedConfig(await readStateConfig());
}
function applyConfiguration(config) {
  // 复用现有草稿三方合并，但配置读取不需要重建图表或等待天气。
  applyData({ ...state.data, config }, true);
}
async function readStateConfig() {
  const selection = selectedScope();
  const data = await api.state(selection);
  // Older/native hosts provide fresh persisted configuration inside state,
  // but do not register GET console/config. Never probe an unadvertised route:
  // the parent bridge can erase HTTP status and turn it into an unknown error.
  if (!list(data.capabilities).includes("config.read")) {
    const config = data.config;
    if (!config || !Array.isArray(config.fields) || !config.values || typeof config.values !== "object" || Array.isArray(config.values) || !hasRevision(config.revision)) {
      throw new PageError("invalid_response", t("配置读取失败，写操作已停用。"));
    }
    data.config = { ...config, endpointFallback: true };
    return data;
  }
  const [configResult] = await Promise.allSettled([api.config(selection)]);
  if (configResult.status === "fulfilled") {
    const config = configResult.value.config ?? configResult.value;
    if (!Array.isArray(config.fields) || !config.values || typeof config.values !== "object" || Array.isArray(config.values) || !hasRevision(config.revision)) {
      throw new PageError("invalid_response", t("配置读取失败，写操作已停用。"));
    }
    data.config = config;
  } else if (["not_found", "method_not_allowed", "404", "405"].includes(String(pageError(configResult.reason).code))) {
    data.config = { ...object(data.config), endpointFallback: true };
  } else throw configResult.reason;
  return data;
}
let stateRefresh = null;
async function loadState({ automatic = false } = {}) {
  if (state.writing || (automatic && (document.hidden || !state.data))) return;
  const relationshipEdit = $("content").querySelector(".relationship-edit");
  if (automatic && (($("content").contains(document.activeElement) &&
      document.activeElement.matches("input,textarea,select")) ||
      (relationshipEdit && !relationshipEdit.closest("[hidden]")))) return;
  if (stateRefresh) return stateRefresh;
  stateRefresh = refreshState(automatic);
  try { return await stateRefresh; } finally { stateRefresh = null; }
}
async function refreshState(automatic) {
  const generation = ++state.generation;
  state.recordGeneration++;
  if (!automatic) { state.loading = true; updateControls(); notify(""); }
  try {
    {
      // 手动与自动刷新都更新原生人格目录，删除的人格不能停留在旧选项中。
      const optional = await Promise.allSettled([api.scopes(), ...(!automatic ? [api.settingsOptions()] : [])]);
      if (generation !== state.generation) return;
      for (const result of optional) {
        if (result.status === "rejected" && ["unauthorized", "forbidden", "bridge_error"].includes(pageError(result.reason).code)) {
          handleError(result.reason); return;
        }
      }
      if (optional[0].status === "rejected") throw optional[0].reason;
      state.scopes = optional[0].value;
      if (optional[1]?.status === "fulfilled") state.options = optional[1].value;
      const personas = list(state.scopes?.personas);
      const known = id => Boolean(id) && personas.some(item => item.id === id);
      // 首屏或当前选择已不在目录里：用已持久化的人格配置决定视图。
      // 旧实现读取 state.data?.config.values.persona_id，而首屏 state.data 恒为 null，
      // 于是永远回落到目录第一项（线上即 default），刷新后人格看起来被改回默认。
      // 配置为空（跟随会话）时才沿用缓存里的有效选择，最后才回落到目录第一项。
      if (personas.length && (!state.bootstrapped || !known(state.selection.persona_id))) {
        const probe = await readStateConfig();
        if (generation !== state.generation) return;
        const preferred = text(probe.config?.values?.persona_id, "");
        const target = (known(preferred) ? personas.find(item => item.id === preferred) : null)
          || (known(state.selection.persona_id) ? personas.find(item => item.id === state.selection.persona_id) : null)
          || personas[0];
        if (target && target.id !== state.selection.persona_id) {
          state.selection = { persona_id: target.id, view_scope: "global" };
          state.contextId = ""; state.preview = null;
        }
      }
    }
    const data = await readStateConfig();
    if (generation !== state.generation || state.writing) return;
    applyData(data, true);
  } catch (error) {
    if (generation !== state.generation) return;
    state.stale = true;
    $("connection").textContent = t("读取失败");
    if (!state.data) $("content").replaceChildren(node("p", t("无法读取状态。请确认宿主登录、插件加载与页面 API 能力。"), "empty"));
    else $("connection").textContent = t("旧快照 · 写操作已停用");
    handleError(error);
  } finally {
    // 读取始终单请求；权限失效会递增generation，也必须释放加载状态以便重新登录后刷新。
    state.loading = false; updateControls();
  }
}
async function saveConfig() {
  if ($("save").disabled) return;
  const invalid = $("settings").querySelector(":invalid");
  if (invalid) { invalid.reportValidity(); return; }
  const reason = "控制台保存配置";
  // 使此前自动读取的旧响应失效，不能覆盖新保存的配置回执。
  const generation = ++state.generation;
  const compact = state.data.capabilities.includes("config.receipt");
  let saved = false, submitted = false;
  state.writing = true; updateControls();
  notify("");
  try {
    // 提交前核对最新内容，合并无关修改；真正同字段冲突仍需明确复核。
    const latest = await readConfiguration();
    if (generation !== state.generation) return;
    applyConfiguration(latest);
    if (state.conflict) return;
    if (!Object.keys(state.draft).length) {
      notify(t("最新配置已包含你的修改。")); return;
    }
    submitted = true;
    const previousPersona = text(state.data?.config?.values?.persona_id, "");
    const result = await api.save({
      context_id: state.contextId, expected_revision: state.baseRevision, patch: { ...state.draft }, reason,
      ...(compact ? { receipt: "config" } : {}),
    });
    if (generation !== state.generation) return;
    if (compact && result?.api_version !== 1) throw new PageError("invalid_response", t("配置回执缺少版本，请核对宿主记录。"));
    const config = checkedConfig(compact ? result : normalizeState(result));
    state.draft = Object.create(null);
    state.invalidFields.clear();
    state.configConflicts = [];
    state.data.config = config; state.baseRevision = config.revision; state.baseValues = { ...config.values }; state.conflict = false;
    // 设置页刚改了人格：当前视图立即跟随，避免保存后仍停在旧人格、要刷新一次才正确。
    const savedPersona = text(config.values.persona_id, "");
    if (savedPersona && savedPersona !== previousPersona &&
        list(state.scopes?.personas).some(item => item.id === savedPersona)) {
      state.selection = { persona_id: savedPersona, view_scope: "global" };
      state.contextId = ""; state.preview = null;
    }
    saved = true;
    state.stale = false;
    syncSettingsValues($("settings"), state);
    notify(t("已保存到原生配置。"));
  } catch (error) {
    if (generation !== state.generation) return;
    if (pageError(error).code === "version_conflict" && !saved) {
      // CAS 失败说明没有写入：只读取并保留草稿，不自动重试提交。
      try {
        applyConfiguration(await readConfiguration());
        if (!state.conflict) notify(t("已读取最新配置并保留你的修改，请再次保存。"), "warning");
      } catch (refreshError) { state.stale = true; handleError(refreshError); }
      return;
    }
    if (submitted && ["timeout", "bridge_error", "invalid_response"].includes(pageError(error).code)) state.uncertain.add("config");
    if (!submitted) state.stale = true;
    handleError(error);
    if (saved && state.data) notify(t("配置已保存，但当前范围状态未能刷新。请手动刷新核对，不要重复保存。"), "warning");
  } finally {
    state.writing = false; updateControls();
    // 保存反馈先结束；实际生活状态另行更新，不延长「正在保存」。
    if (saved) {
      const pending = stateRefresh;
      void Promise.resolve(pending).then(() => loadState({ automatic: true }));
    }
  }
}
// 一级菜单里的操作不再二次确认：按钮本身已经是明确指令，点了就执行。
// 审计仍保留，原因统一记为「控制台直接执行」，不再要求管理员手填。
const DIRECT_ACTION_REASON = "控制台直接执行（未填写原因）";
async function runAction(id, item) {
  const pin = id === "experience.pin";
  const key = pin ? `experience.pin:${item?.id}` : id;
  if (!canWrite() || state.writing || state.uncertain.has(key)) return;
  if (pin ? (item?.pin_available !== true || typeof item.context_id !== "string"
      || !item.context_id || typeof item.pinned !== "boolean")
    : !state.data.actions.some(action => action.id === id && action.enabled === true)) return;
  const contextId = pin ? item.context_id : actionContextId(id);
  if (!contextId) return;
  const revision = state.data.revision, generation = state.generation;
  state.writing = true; updateControls();
  try {
    const result = await api.action({
      context_id: contextId, action: id, expected_revision: revision,
      reason: DIRECT_ACTION_REASON, confirmed: true,
      ...(pin ? { entry_id: item.id, pinned: !item.pinned, expected_pinned: item.pinned } : {}),
    });
    if (generation !== state.generation) return;
    if (result.api_version !== 1 || typeof result.status !== "string") {
      throw new PageError("invalid_response", t("动作回执无效，执行结果不明，请核对记录。"));
    }
    if (result.status === "unknown") state.uncertain.add(key);
    if (pin) experienceRecordKeys.clear();
    const outcome = t("操作结果：{0}。{1}{2}", [resultLabel(result.status), text(result.reason, ""),
      result.request_id ? t(" 请求 ID：{0}", [text(result.request_id)]) : ""]);
    state.stale = true;
    if (["diary.generate", "dream.generate"].includes(id) && result.status !== "unknown") {
      try { applyData(await readStateConfig()); }
      catch (error) { state.stale = true; handleError(error); }
      // 任务在后台跑：持续刷新任务状态，直到出现结果或超时。
      pollExperience();
    }
    if (id === "behavior.send" && result.status !== "unknown") {
      // 真实发送在后台执行：稍后自动刷新一次状态和最近执行，避免"点了没反应"。
      setTimeout(async () => {
        if (state.section !== "behavior" || state.writing) return;
        try {
          await loadState();
          const outcome = $("behavior-outcome");
          if (outcome) await loadBehaviorOutcome(outcome);
        } catch (error) { /* 本次自动刷新失败不覆盖用户手动刷新结果。 */ }
      }, 2500);
    }
    notify(outcome, result.status === "unknown" || state.stale ? "warning" : "");
    if (result.reason_code) $("notice").append(reasonCodeView(result.reason_code));
    if (state.stale) $("connection").textContent = t("操作已返回 · 请刷新核对状态");
  } catch (error) {
    if (generation !== state.generation) return;
    const failure = pageError(error);
    if (["timeout", "invalid_response", "bridge_error"].includes(failure.code)) state.uncertain.add(key);
    handleError(error);
  } finally { state.writing = false; updateControls(); }
}

function navigate(section, focus = false) {
  state.section = section; remember(); render();
  if (focus) $("main").focus();
}
async function boot() {
  staticUI();
  matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", event => {
    if (event.matches) {
      cancelPageTurn();
      document.getAnimations().filter(a => a.effect?.target?.closest?.(".paper-sheet")).forEach(a => a.cancel());
    }
  });
  for (const control of document.querySelectorAll("[data-section]")) {
    const label = node("span"); label.dataset.sectionLabel = control.dataset.section;
    for (const child of [...control.childNodes]) if (child.nodeType === Node.TEXT_NODE) child.remove();
    control.append(label);
  }
  window.livingEmotionTranslate = controlled;
  window.dispatchEvent(new Event("livingemotion:locale"));
  $("language").value = locale();
  $("language").addEventListener("change", () => {
    setLocale($("language").value); staticUI();
    window.dispatchEvent(new Event("livingemotion:locale"));
    render(); renderEnvironment(state.data?.environment);
    if (state.data) $("connection").textContent = state.stale ? t("旧快照 · 写操作已停用") : t("更新于 {0}", [date(state.data.updated_at)]);
  });
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
  $("refresh").addEventListener("click", () => loadState());
  new ResizeObserver(entries => {
    if (!$("editor").hidden) document.documentElement.style.setProperty(
      "--editor-clearance", `${Math.ceil(entries[0].target.getBoundingClientRect().height) + 32}px`);
  }).observe($("editor"));
  $("save").addEventListener("click", saveConfig);
  $("settings").addEventListener("livingemotion:memory-sync", () => {
    const control = $("settings").querySelector("#memory-sync");
    if (control && !control.disabled) syncPersonaMemory(control);
  });
  $("rebase").addEventListener("click", () => {
    if (!state.configConflicts.length || state.loading || state.writing || state.stale) return;
    // 用户复核的是屏幕上这份快照；下一次保存仍重新读取并执行 CAS。
    state.baseRevision = state.data.config.revision; state.baseValues = { ...state.data.config.values };
    state.conflict = false; state.configConflicts = [];
    notify(t("已保留你的修改，点击保存提交。")); updateControls();
  });
  $("discard").addEventListener("click", () => {
    state.draft = Object.create(null); state.conflict = false;
    state.invalidFields.clear();
    state.configConflicts = []; state.baseRevision = state.data?.config.revision;
    state.baseValues = { ...state.data?.config.values };
    if (state.section === "experience") renderSettings();
    notify(t("已放弃本页未保存更改。")); render();
  });
  window.addEventListener("beforeunload", event => {
    if (Object.keys(state.draft).length || state.invalidFields.size || state.writing) { event.preventDefault(); event.returnValue = ""; }
  });
  render();
  await loadState();
  // 固定节奏仅在启动时建立一次，手动刷新不重置计时；后台页不发请求。
  const autoUpdate = setInterval(() => { void loadState({ automatic: true }); }, 60000);
  // 新日志独立自动读取；查询条件一直保留，也不重置页面的默认刷新计时。
  const behaviorUpdate = setInterval(() => {
    if (!document.hidden && state.section === "behavior" && state.data &&
        !state.behaviorLogLoading) void loadBehaviorOutcome($("behavior-outcome"));
  }, 5000);
  window.addEventListener("pagehide", () => {
    clearInterval(autoUpdate); clearInterval(behaviorUpdate); clearInterval(environmentClock);
    state.generation++; state.recordGeneration++;
  }, { once: true });
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
else boot();
