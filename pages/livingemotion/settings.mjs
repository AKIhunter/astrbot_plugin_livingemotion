import { t, locale, controlled, resource } from "./i18n.mjs";
import { object, list, text, fieldValue, stageNames, DEFAULT_STAGE_NAMES } from "./model.mjs";
import { fieldHelp, localizedFieldLabel } from "./config-resources.mjs";
import { node, button } from "./dom.mjs";
const labels = resource({
  relationship_special_description: t("独特关系说明"),
  relationship_stage_names: t("关系阶段自定义名称"), enabled: t("启用 livingEmotion"), mode: t("工作模式"), persona_mode: t("人格解析方式"), persona_id: t("原生人格"),
  relationship_stage_descriptions: t("关系阶段描述"),
  state_mode: t("情绪共享方式（全局共享 / 拆分独立）"), shared_state: t("情绪共享方式（全局共享 / 拆分独立）"), persona_shared_state: t("情绪共享方式（全局共享 / 拆分独立）"),
  state_shared: t("情绪共享方式（全局共享 / 拆分独立）"), state_scope_mode: t("情绪共享方式（全局共享 / 拆分独立）"),
  provider_id: t("默认生成模型"), livingmemory_enabled: t("使用 LivingMemory"), allow_sleep: t("允许 TA 睡眠"),
  timezone: t("本地 IANA 时区"), night_timezone: t("本地 IANA 时区"), residence_city: t("TA 住所城市"),
  home_city: t("TA 住所城市"), model_provider_id: t("默认生成模型"), emotion_model_enabled: t("模型细化情绪"),
  emotion_provider_id: t("情绪模型"), emotion_model_provider_id: t("情绪模型"), model_daily_limit: t("每日模型预算"),
  model_concurrency: t("模型并发上限"), model_token_budget: t("每日 Token 预算"),
  autonomy_enabled: t("允许主动找人"), autonomy_provider_id: t("主动行为模型"), group_enabled: t("允许群聊主动行为"),
  night_enabled: t("允许 TA 睡眠"), sleep_enabled: t("允许 TA 睡眠"),
  nap_start: t("午休开始"), nap_end: t("午休结束"), night_nap_start: t("午休开始"), night_nap_end: t("午休结束"),
  sleep_start: t("夜间疲劳开始"), sleep_end: t("夜间疲劳结束"), deep_sleep_at: t("沉睡时间"),
  wake_at: t("基础起床时间"), wake_time: t("基础起床时间"), sleep_time: t("夜间疲劳开始"),
  wake_mode: t("聊天唤醒规则"), wake_reply_limit: t("唤醒回复轮数"), wake_window_minutes: t("唤醒窗口"),
  wake_delay_min_minutes: t("赖床最短时间"), wake_delay_max_minutes: t("赖床最长时间"),
  energy_reply_cost: t("每次回复消耗"), energy_fatigue_per_minute: t("疲劳每分钟消耗"),
  energy_recovery_per_minute: t("每分钟恢复"), energy_max: t("精力上限（固定）"),
  night_energy_reply_cost: t("每次回复消耗"), night_energy_fatigue_per_minute: t("疲劳每分钟消耗"),
  night_energy_recovery_per_minute: t("每分钟恢复"),
  closing_enabled: t("睡前晚安"), closing_random: t("道别语随机生成"), closing_provider_id: t("收尾模型"),
  catchup_enabled: t("醒后阅读未读"), catchup_reply_enabled: t("醒后历史补答"), catchup_provider_id: t("补课模型"),
  diary_enabled: t("自动私人日记"), diary_provider_id: t("日记模型"), dream_enabled: t("自动梦境"),
  dream_provider_id: t("梦境模型"), memory_mode: t("记忆后端"), use_livingmemory: t("使用 LivingMemory"),
  memory_read: t("允许记忆检索"), memory_export: t("允许记忆写入"), memory_write: t("允许记忆写入"),
  embedding_provider_id: t("原生向量模型"), memory_embedding_provider_id: t("原生向量模型"),
});
const optionLabels = resource({
  active: t("参与表达与行动"), observe_only: t("只观察，不主动发言"), disabled: t("停用"), follow: t("跟随原生会话"),
  explicit: t("指定原生人格"), none: t("未启用"), local_lite: t("本地轻量记录"), local_vector: t("本地向量记忆"),
  external: "LivingMemory", chat: t("私聊可叫醒"), never: t("聊天不可叫醒"), both: t("私聊或群聊原生 @"),
  global: t("同一人格共享"), shared: t("同一人格共享"), persona_shared: t("同一人格共享"), scene: t("按真实会话独立"),
  context: t("按真实会话独立"), per_scene: t("按真实会话独立"),
});
const groups = resource({ quick: t("快速开始"), persona: t("人格与状态模式"), emotion: t("情绪"), relationships: t("关系"),
  behavior: t("主动行为"), night: t("长夜"), experience: t("日记与梦境"), memory: t("记忆") });
const quickKeys = new Set(["enabled", "mode", "persona_id", "timezone", "night_timezone", "model_provider_id",
  "residence_city", "home_city", "memory_mode", "use_livingmemory", "night_enabled", "sleep_enabled"]);
const advancedPattern = /budget|limit|threshold|concurrency|timeout|cooldown|retention|ttl|maximum|max_records|read|export|write|lead|backoff/;
const legacyKeys = new Set(["night_enabled", "night_block_chat", "sleep_at", "memory_mode",
  "memory_export", "night_policy_version", "autonomy_scopes"]);
function orderedFields(fields) {
  const result = [], used = new Set();
  function add(field) {
    if (used.has(field.key)) return;
    used.add(field.key); result.push(field);
    fields.filter(child => child.parent === field.key && child.key !== field.key).forEach(add);
  }
  fields.filter(field => !fields.some(parent => parent.key === field.parent)).forEach(add);
  fields.forEach(add);
  return result;
}
const PERSONA_DESCRIPTION_CLAMP_CHARS = 60;
// 只读人格说明：默认折叠 3 行，超长可展开；内容在 AstrBot 人格管理中编辑。
function personaDescriptionBlock(select, loader) {
  const holder = node("div", undefined, "persona-description-preview");
  const body = node("p", undefined, "persona-description-text");
  const meta = node("p", undefined, "persona-description-meta");
  const toggle = button(t("展开全文"), () => {
    const expanded = holder.classList.toggle("is-expanded");
    toggle.textContent = expanded ? t("收起") : t("展开全文");
    body.scrollTop = 0;
  }, "persona-description-toggle");
  toggle.hidden = true;
  holder.append(body, meta, toggle);
  function reset() {
    holder.classList.remove("is-expanded");
    toggle.hidden = true;
    toggle.textContent = t("展开全文");
    body.classList.remove("is-empty");
  }
  function empty(message) {
    body.textContent = message;
    body.classList.add("is-empty");
  }
  async function render() {
    const personaId = text(select.value, "");
    reset();
    meta.textContent = t("只读 · 在 AstrBot 人格管理中编辑");
    if (!personaId) {
      empty(t("跟随当前会话人格，说明随会话不同；保存后可在「人格」页查看。"));
      return;
    }
    empty(t("正在读取人格说明…"));
    try {
      const description = text(await loader(personaId), "");
      if (text(select.value, "") !== personaId) return;
      if (!description) {
        empty(t("该人格未填写说明。"));
        meta.textContent = t("0 字 · 在 AstrBot 人格管理中编辑，本页只读");
        return;
      }
      body.textContent = description;
      body.classList.remove("is-empty");
      meta.textContent = t("共 {0} 字 · 在 AstrBot 人格管理中编辑，本页只读", [String(description.length)]);
      toggle.hidden = description.length <= PERSONA_DESCRIPTION_CLAMP_CHARS;
    } catch (_) {
      if (text(select.value, "") !== personaId) return;
      empty(t("人格说明读取失败；不影响其他设置。"));
    }
  }
  select.addEventListener("change", render);
  void render();
  return holder;
}
function setExpandedGroup(root, state, group, toggle = true) {
  const target = [...root.querySelectorAll("[data-task-group]")].find(section => section.dataset.taskGroup === group);
  if (!target) return;
  state.expandedSettingsGroup = state.expandedSettingsGroup === group && toggle ? "" : group;
  for (const section of root.querySelectorAll("[data-task-group]")) {
    const expanded = section.dataset.taskGroup === state.expandedSettingsGroup;
    section.hidden = !expanded;
    section.inert = !expanded;
    section.setAttribute("aria-hidden", String(!expanded));
    section.classList.remove("settings-group-opening");
    const jump = [...root.querySelectorAll("[data-settings-jump]")].find(button => button.dataset.settingsJump === section.dataset.taskGroup);
    jump?.setAttribute("aria-expanded", String(expanded));
    if (!expanded && section.contains(document.activeElement)) jump?.focus({ preventScroll: true });
  }
  if (state.expandedSettingsGroup) {
    target.hidden = false;
    target.inert = false;
    target.classList.remove("settings-group-opening");
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
      void target.offsetWidth;
      target.classList.add("settings-group-opening");
    }
  }
}
export function jumpToSettingsGroup(root, group, state) {
  if (state) setExpandedGroup(root, state, group, false);
}
function groupOf(field) {
  if (quickKeys.has(field.key)) return "quick";
  if (/persona|state_(?:shared|mode|scope)|shared_state/.test(field.key)) return "persona";
  if (/night|sleep|wake|nap|energy|closing|catchup/.test(field.key)) return "night";
  if (/memory|embedding|livingmemory/.test(field.key)) return "memory";
  if (/diary|dream|residence|home_city/.test(field.key)) return "experience";
  if (/relation|affinity/.test(field.key)) return "relationships";
  if (/autonomy|behavior|group/.test(field.key)) return "behavior";
  return Object.hasOwn(groups, field.section) ? field.section : "emotion";
}
export function settingsGroups(fields, config) {
  const metadata = list(config.groups);
  if (!metadata.length) return Object.entries(groups).map(([id, label]) => ({
    id, label, fields: fields.filter(field => groupOf(field) === id),
  }));
  const used = new Set();
  const result = metadata.map(group => {
    const selected = list(group.field_keys).flatMap(key => {
      const field = fields.find(item => item.key === key);
      if (!field || used.has(key)) return [];
      used.add(key); return [field];
    });
    return { id: group.id, label: controlled(group.label), fields: selected };
  });
  const remaining = fields.filter(field => !used.has(field.key)).filter(field => {
    const target = result.find(group => group.id === field.section);
    if (!target) return true;
    target.fields.push(field); return false;
  });
  if (remaining.length) result.push({ id: "additional", label: t("其他高级设置"), fields: remaining });
  return result;
}
export function schedulePreview(values) {
  const minutes = value => typeof value === "string" && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value) ?
    Number(value.slice(0, 2)) * 60 + Number(value.slice(3)) : null;
  const start = minutes(values.fatigue_start), deep = minutes(values.deep_sleep_at), wake = minutes(values.wake_at);
  if ([start, deep, wake].includes(null)) return t("作息时间未完整配置，不能计算预览。");
  const deepAt = deep < start ? deep + 1440 : deep;
  const wakeAt = wake <= start ? wake + 1440 : wake;
  if (deepAt >= wakeAt) return t("沉睡时间应位于夜间开始与基础起床之间，请核对跨午夜顺序。");
  const clock = value => `${value >= 1440 ? t("次日 ") : t("当日 ")}${String(Math.floor(value / 60) % 24).padStart(2, "0")}:${String(Math.floor(value) % 60).padStart(2, "0")}${value % 1 ? ":30" : ""}`;
  return t("本地 {0}：夜间 {1} → 恍惚转困 {2} → 沉睡 {3} → 基础起床 {4}。实际起床另加本周期持久赖床值，不在页面重抽。", [text(values.timezone, t("时区未配置")), clock(start), clock((start + deepAt) / 2), clock(deepAt), clock(wakeAt)]);
}
export function renderSettings(root, state, options, updateControls, descriptionLoader) {
  const experienceOnly = state.section === "experience";
  root.replaceChildren(); root.hidden = state.section !== "settings" && !experienceOnly;
  if (root.hidden) return;
  root.append(node("p", t("一份原生配置，一次保存。普通分区只阅读状态；以下更改统一提交到 AstrBot。"), "hint"),
    node("p", t("修改后点击底部保存。"), "micro"));
  if (!state.data.config.fields.some(field => field.key === "relationship_stage_names" || /^relationship_stage_\d+_name$/.test(field.key))) root.append(node("p", t("关系阶段命名尚未由宿主开放；默认名称仍按分数显示。"), "hint"));
  const fields = [...state.data.config.fields, ...list(state.data.config.readonly).filter(field =>
    field && !state.data.config.fields.some(item => item.key === field.key))].filter(field => !legacyKeys.has(field.key))
    .filter(field => !experienceOnly || /^(diary_|dream_|experience_|home_city$|timezone$|provider_id$|fallback_provider_id$)/.test(field.key));
  const taskGroups = experienceOnly ? [{ id: "experience", label: t("日记与梦境"), fields }] :
    settingsGroups(fields, state.data.config).filter(group => group.fields.length || group.id === "night");
  const jumps = node("div", undefined, "settings-jumps"); jumps.setAttribute("role", "group");
  jumps.setAttribute("aria-label", t("展开模块配置"));
  if (state.expandedSettingsGroup == null ||
    (state.expandedSettingsGroup !== "" && !taskGroups.some(group => group.id === state.expandedSettingsGroup))) {
    state.expandedSettingsGroup = taskGroups.some(group => group.id === "quick_start") ? "quick_start" : taskGroups[0]?.id || "";
  }
  for (const group of taskGroups) {
    const jump = button(group.label, () => setExpandedGroup(root, state, group.id));
    jump.dataset.settingsJump = group.id;
    jump.setAttribute("aria-controls", `settings-group-${group.id}`);
    jump.setAttribute("aria-expanded", String(state.expandedSettingsGroup === group.id));
    jumps.append(jump);
  }
  root.append(jumps);
  const dialog = node("dialog", undefined, "config-help-dialog");
  dialog.id = "config-help-dialog";
  dialog.setAttribute("aria-labelledby", "config-help-title");
  dialog.setAttribute("aria-describedby", "config-help-description");
  const dialogTitle = node("h2"); dialogTitle.id = "config-help-title";
  const dialogDescription = node("p"); dialogDescription.id = "config-help-description";
  const dialogExample = node("p", undefined, "config-example");
  const close = button(t("知道了"), () => dialog.close());
  dialog.append(node("p", t("配置说明"), "eyebrow"), dialogTitle, dialogDescription,
    node("h3", t("填写与使用示例")), dialogExample, close);
  root.append(dialog);
  const previewText = node("p", schedulePreview({ ...state.data.config.values, ...state.draft }), "hint");
  previewText.id = "schedule-preview";
  if (!fields.length) root.append(node("p", t("宿主未提供可编辑字段，请检查原生配置能力。"), "empty"));
  for (const { id: group, label: title, fields: selected } of taskGroups) {
    if (!selected.length && group !== "night") continue;
    const section = node("section", undefined, "settings-group"); section.dataset.taskGroup = group;
    section.id = `settings-group-${group}`;
    section.hidden = !experienceOnly && state.expandedSettingsGroup !== group;
    section.inert = section.hidden;
    section.setAttribute("aria-hidden", String(section.hidden));
    const heading = node("h2", title); heading.tabIndex = -1; section.append(heading);
    const common = node("div"), advanced = node("details"); advanced.className = "advanced-settings";
    advanced.append(node("summary", t("高级设置 · 预算、阈值与边界")));
    const advancedBody = node("div", undefined, "details-content"); advanced.append(advancedBody);
    for (const original of orderedFields(selected)) {
      const field = { ...original };
      if (/provider_id$/.test(field.key) || field.key === "persona_id") {
        const source = /embedding/.test(field.key) ? options.embedding_providers : options.chat_providers;
        const choices = field.key === "persona_id" ? options.personas : source;
        if (Array.isArray(choices)) {
          field.type = "enum";
          field.options = [{ value: "", label: field.key === "persona_id" ? t("跟随当前会话人格") : /embedding/.test(field.key) ? t("待配置") : t("沿用当前聊天模型") },
            ...choices.map(item => ({ value: item.value ?? item.id, label: item.name ?? item.label ?? item.id }))];
        } else if (Array.isArray(field.options)) field.type = "enum";
      }
      const value = Object.hasOwn(state.draft, field.key) ? state.draft[field.key] :
        Object.hasOwn(state.data.config.values, field.key) ? state.data.config.values[field.key] : field.value;
      const wrapper = node("div", undefined, "field");
      wrapper.dataset.level = String(Math.min(2, Math.max(0, Number(field.level) || 0)));
      if (field.parent) wrapper.dataset.parent = field.parent;
      const description = node("div"), id = `config-${field.key}`;
      const stageMatch = field.key.match(/^relationship_stage_(\d+)_name$/);
      const rawLabel = stageMatch ? `${Number(stageMatch[1]) === 10 ? "100" : `${Number(stageMatch[1]) * 10}–${Number(stageMatch[1]) * 10 + 9}`} · ${t("关系阶段自定义名称")}` : localizedFieldLabel(field);
      const label = node("label", labels[field.key] || rawLabel); label.htmlFor = id;
      const help = node("p", fieldHelp(field), "hint"); help.id = `${id}-help`;
      const labelRow = node("div", undefined, "field-title");
      const helpButton = button("?", () => {
        dialogTitle.textContent = label.textContent;
        dialogDescription.textContent = fieldHelp(field, "details");
        dialogExample.textContent = locale() !== "zh-CN" ? fieldHelp(field, "example") : text(field.example, t("当前值为“{0}”。按此项类型填写并保存，实际效果受相关模块开关影响。", [text(value)]));
        dialog.showModal();
      }, "config-help");
      helpButton.dataset.configHelp = field.key;
      helpButton.setAttribute("aria-label", t("{0}：详细说明和示例", [label.textContent]));
      labelRow.append(label, helpButton);
      description.append(labelRow, help);
      if (field.unit) description.append(node("span", t("单位：{0}", [controlled(text(field.unit))]), "micro"));
      let input;
      if (field.type === "enum") {
        input = node("select");
        for (const choice of list(field.options)) {
          if (!choice || !["string", "number", "boolean"].includes(typeof choice.value)) continue;
          const option = node("option", field.key === "memory_mode" && choice.value === "none" ? t("本地向量（待配置）") :
            optionLabels[choice.value] || text(choice.label, choice.value));
          option.value = String(choice.value); input.append(option);
        }
        if (!list(field.options).some(choice => choice?.value === value)) {
          const unknown = node("option", t("当前值：{0}", [text(value)])); unknown.value = ""; unknown.disabled = true; input.prepend(unknown);
          input.value = "";
        } else input.value = String(value);
      } else if (field.key === "dream_theme_pool") {
        input = node("textarea"); input.rows = 4; input.maxLength = 2000;
        try { input.value = JSON.parse(value).join("\n"); } catch (_) { input.value = text(value, ""); }
      } else {
        input = node("input");
        input.type = field.type === "boolean" ? "checkbox" : ["number", "integer", "float"].includes(field.type) ? "number" : "text";
        if (field.type === "boolean") input.checked = value === true;
        else input.value = text(value, "");
        input.maxLength = 2000;
        if (input.type === "number") {
          if (Number.isFinite(field.min)) input.min = String(field.min);
          if (Number.isFinite(field.max)) input.max = String(field.max);
          input.step = field.type === "integer" ? "1" : String(field.step || .1);
        }
      }
      if (field.key === "relationship_special_description") {
        const textarea = node("textarea"); textarea.rows = 4; textarea.maxLength = 1000;
        textarea.value = text(value, ""); input = textarea;
      }
      if (["relationship_stage_names", "relationship_stage_descriptions"].includes(field.key)) input.hidden = true;
      input.id = id; input.dataset.key = field.key;
      if (field.readonly) input.readOnly = true;
      input.setAttribute("aria-describedby", help.id);
      if (field.key === "embedding_provider_id") {
        const reason = node("p", t("LivingMemory 已启用：向量模型由 LivingMemory 管理，本地原生向量模型暂不可编辑。当前值会保留，关闭 LivingMemory 后可继续使用。"), "hint");
        reason.id = `${id}-disabled-reason`;
        reason.dataset.livingmemoryReason = "";
        reason.hidden = true;
        reason.setAttribute("aria-live", "polite");
        description.append(reason);
        input.setAttribute("aria-describedby", `${help.id} ${reason.id}`);
      }
      input.dataset.editable = String(!field.readonly && !/energy_(max|cap)$/.test(field.key) &&
        state.data.capabilities.includes("config.write") && Object.hasOwn(state.data.config.values, field.key));
      if (state.invalidFields.has(field.key)) {
        const invalid = state.invalidFields.get(field.key);
        input.value = invalid.value; input.setCustomValidity(invalid.message); input.setAttribute("aria-invalid", "true");
      }
      input.addEventListener("input", () => {
        input.setCustomValidity(""); input.removeAttribute("aria-invalid");
        try {
          const next = fieldValue(field, input); state.invalidFields.delete(field.key);
          if (field.key === "relationship_stage_names") stageNames(next);
          if (["autonomy_qq_ids", "autonomy_qq_group_ids"].includes(field.key)) {
            const entries = input.value.split(/[\s,，;；、]+/).filter(Boolean);
            if (input.value.length > 2000 || new Set(entries).size > 100 ||
              entries.some(entry => !/^[1-9][0-9]{4,19}$/.test(entry))) {
              throw new Error(t("请输入5至20位QQ/群号，多个用逗号或空格分隔，最多100个。"));
            }
          }
          if (!Object.keys(state.draft).length) {
            state.baseRevision = state.data.config.revision; state.baseValues = { ...state.data.config.values };
          }
          if (next === state.data.config.values[field.key] || field.key === "relationship_stage_names" && stageNames(next).every(name => name === "") && !state.data.config.values[field.key]) delete state.draft[field.key];
          else state.draft[field.key] = next;
          state.configConflicts = state.configConflicts.filter(item => Object.hasOwn(state.draft, item.key))
            .map(item => ({ ...item, draft: state.draft[item.key] }));
          state.conflict = state.configConflicts.length > 0;
          previewText.textContent = schedulePreview({ ...state.data.config.values, ...state.draft });
          updateControls();
        } catch (error) {
          state.invalidFields.set(field.key, { value: input.value, message: error.message });
          input.setCustomValidity(error.message); input.setAttribute("aria-invalid", "true"); input.reportValidity(); updateControls();
        }
      });
      let control = input;
      if (field.key === "livingmemory_enabled") {
        // 勾选「使用 LivingMemory」后，右侧立即出现「手动同步当前人格记忆」。
        // 同步只读对方数据库，写入本地只读镜像；未勾选时按钮不可用。
        const sync = button(t("手动同步当前人格记忆"), () => {
          if (sync.disabled) return;
          root.dispatchEvent(new CustomEvent("livingemotion:memory-sync", { bubbles: true }));
        });
        sync.id = "memory-sync";
        sync.dataset.operation = "memory-sync";
        const enabledValue = Object.hasOwn(state.draft, "livingmemory_enabled")
          ? state.draft.livingmemory_enabled === true
          : state.data.config.values.livingmemory_enabled === true;
        sync.disabled = !enabledValue || !state.data.capabilities.includes("memory.sync");
        sync.dataset.needsLivingMemory = "true";
        sync.title = enabledValue ? t("读取当前人格在 LivingMemory 的全部记忆")
          : t("请先勾选并使用 LivingMemory，保存后可手动同步");
        const row = node("div", undefined, "inline-control");
        row.append(input, sync);
        control = row;
        const note = node("p", t("勾选后保存，即可在右侧手动把当前人格的全量记忆读进本插件；未勾选时按钮不可用。"), "hint");
        description.append(note);
        input.addEventListener("change", () => {
          sync.disabled = input.checked !== true || !state.data.capabilities.includes("memory.sync");
        });
      }
      if (["autonomy_qq_ids", "autonomy_qq_group_ids"].includes(field.key)) {
        const isGroup = field.key === "autonomy_qq_group_ids";
        input.placeholder = isGroup ? t("留空=所有已知QQ群；多个群号用逗号分隔") : t("输入QQ号码，多个用逗号分隔");
        const suggestions = node("select"); suggestions.id = `${id}-suggestions`;
        suggestions.dataset.editable = input.dataset.editable;
        suggestions.setAttribute("aria-label", isGroup ? t("从已知QQ群追加群号") : t("从已知QQ私聊追加号码"));
        const placeholder = node("option", isGroup ? t("下拉追加已知群号…") : t("下拉追加已知QQ…"));
        placeholder.value = ""; suggestions.append(placeholder);
        const sources = new Map(list(state.scopes?.contexts).filter(c =>
          c.platform === "qq" && c.view_scope === (isGroup ? "group" : "private") &&
          /^[1-9][0-9]{4,19}$/.test(isGroup ? c.scene_id : c.account_id)
        ).map(c => [isGroup ? c.scene_id : c.account_id, c]));
        for (const [number, scope] of sources) {
          const option = node("option", `${isGroup ? t("QQ群") : text(scope.nickname, "QQ")} · ${number}`);
          option.value = number; suggestions.append(option);
        }
        suggestions.addEventListener("change", () => {
          if (!suggestions.value) return;
          const numbers = new Set(input.value.split(/[\s,，;；、]+/).filter(Boolean));
          numbers.add(suggestions.value); input.value = [...numbers].join(", ");
          suggestions.value = ""; input.dispatchEvent(new Event("input", { bubbles: true }));
        });
        control = node("div", undefined, "number-list-control"); control.append(input, suggestions);
      }
      wrapper.append(description, control);
      const body = field.advanced || advancedPattern.test(field.key) ? advancedBody : common;
      body.append(wrapper);
      // 人格说明只读展示：内容来自宿主 personas.system_prompt，本页不写入。
      if (field.key === "persona_id" && typeof descriptionLoader === "function") {
        body.append(personaDescriptionBlock(input, descriptionLoader));
      }
    }
    section.append(common);
    if (group === "persona") {
      // 这两个选项经常被误解，写清楚「拆分 / 全局」到底影响什么。
      section.append(node("h3", t("拆分与全局的区别"), "settings-subhead"),
        node("p", t("拆分（取消勾选）：每个私聊账号、每个群各自记录并维护自己的情绪，情绪参与回复时互不影响。"), "hint"),
        node("p", t("全局（勾选）：私聊和群聊共享同一份人格情绪，任何会话的互动都会更新这同一份状态。"), "hint"),
        node("p", t("「工作模式」只决定要不要参与表达和行动；它不改情绪是否共享。"), "hint"));
    }
    if (group === "night") {
      section.append(node("p", t("精力上限固定 100，不可修改。"), "hint"));
      section.append(previewText);
      const preview = object(state.data.night.schedule_preview ?? options.schedule_preview);
      if (Object.keys(preview).length) section.append(node("p",
        t("作息预览：{0} · 恍惚转困 {1} · 实际起床 {2}", [text(preview.reason ?? preview.summary), text(preview.drowsy_at), text(preview.wake_at)]), "hint"));
      else section.append(node("p", t("以上是配置顺序预览，不代表当前周期的持久实际起床时刻。最终作息以宿主状态与校验为准。"), "hint"));
    }
    if (advancedBody.childElementCount) section.append(advanced);
    root.append(section);
  }
  mountRelationshipEditor(root, state);
}

const DEFAULT_DESCRIPTIONS = [
  "反感：保持距离，可以冷淡或表达不满，不羞辱、威胁或攻击对方；正经任务仍可靠。",
  "陌生：礼貌、谨慎，先了解对方，避免擅自亲密。",
  "友好：自然友善，肯定对方的善意、合理批评和教导。",
  "亲近：更主动关心、温柔陪伴，关怀程度加倍，尊重对方边界。",
];
function descriptionValues(input) {
  try {
    const values = JSON.parse(input?.value || '["","","",""]');
    if (Array.isArray(values) && values.length === 4 && values.every(v => typeof v === "string")) return values;
  } catch (_) { /* 老宿主没有描述字段时，仍展示默认相处说明。 */ }
  return Array(4).fill("");
}
function mountRelationshipEditor(root, state) {
  const namesInput = root.querySelector("#config-relationship_stage_names");
  if (!namesInput) return;
  const descriptionsInput = root.querySelector("#config-relationship_stage_descriptions");
  const special = root.querySelector("#config-relationship_special_description");
  const specialWrapper = special?.closest(".field");
  const wrapper = namesInput.closest(".field");
  wrapper.classList.add("relationship-settings-field");
  const editor = node("fieldset", undefined, "stage-name-editor");
  editor.append(node("legend", t("关系名称与相处描述")));
  const header = node("div", undefined, "relationship-editor-head");
  header.append(node("span", t("关系")), node("span", t("描述"))); editor.append(header);
  const names = stageNames(namesInput.value), descriptions = descriptionValues(descriptionsInput);
  for (let index = 0; index < 5; index++) {
    const row = node("div", undefined, "relationship-editor-row");
    const left = node("div", undefined, "relationship-editor-name");
    const entry = node("input"); entry.type = "text"; entry.maxLength = 100;
    entry.value = names[index]; entry.placeholder = DEFAULT_STAGE_NAMES[index];
    entry.id = `stage-name-${index}`; entry.dataset.stageIndex = String(index);
    entry.dataset.key = namesInput.dataset.key; entry.dataset.editable = namesInput.dataset.editable;
    const label = node("label", index === 4 ? t("100 · 独特（管理员设置）") :
      t("{0}–{1} 分", [[0, 10], [11, 24], [25, 44], [45, 99]][index]));
    label.htmlFor = entry.id;
    entry.addEventListener("input", () => {
      // 每次从隐藏配置控件取最新值，自动更新后不把其它行恢复成旧值。
      const current = stageNames(namesInput.value); current[index] = entry.value;
      namesInput.value = JSON.stringify(current);
      namesInput.dispatchEvent(new Event("input", { bubbles: true }));
    });
    left.append(label, entry);
    let description;
    if (index === 4 && special) {
      description = special; description.rows = 3;
      description.placeholder = t("遵循管理员定义的特殊关系，自然关心并尊重边界。");
    } else {
      description = node("textarea"); description.rows = 3; description.maxLength = 1000;
      description.id = `stage-description-${index}`;
      description.value = descriptions[index] || controlled(DEFAULT_DESCRIPTIONS[index]);
      description.placeholder = controlled(DEFAULT_DESCRIPTIONS[index]);
      description.dataset.key = "relationship_stage_descriptions";
      description.dataset.editable = descriptionsInput?.dataset.editable || "false";
      description.addEventListener("input", () => {
        if (!descriptionsInput) return;
        const current = descriptionValues(descriptionsInput);
        current[index] = description.value === controlled(DEFAULT_DESCRIPTIONS[index]) ? "" : description.value;
        descriptionsInput.value = JSON.stringify(current);
        descriptionsInput.dispatchEvent(new Event("input", { bubbles: true }));
      });
    }
    description.setAttribute("aria-label", t("{0} · 相处描述", [names[index] || DEFAULT_STAGE_NAMES[index]]));
    row.append(left, description); editor.append(row);
  }
  if (descriptionsInput) descriptionsInput.closest(".field").hidden = true;
  if (special) {
    specialWrapper?.remove();
    special.setAttribute("aria-describedby", "relationship-editor-help");
  }
  const help = node("p", t("名称和描述均可自定义；留空沿用默认。100 分仅由管理员设置，单个对象的备注优先。"), "micro");
  help.id = "relationship-editor-help";
  wrapper.append(editor, help);
}

export function syncSettingsValues(root, state) {
  // 后台更新只同步未编辑字段，保留原 DOM、焦点、无效输入、折叠和滚动位置。
  for (const field of state.data.config.fields) {
    const input = root.querySelector(`#config-${field.key}`);
    if (!input || Object.hasOwn(state.draft, field.key) || state.invalidFields.has(field.key) ||
        input === document.activeElement) continue;
    const value = state.data.config.values[field.key];
    if (input.type === "checkbox") input.checked = value === true;
    else if (field.key === "dream_theme_pool") {
      try { input.value = JSON.parse(value).join("\n"); } catch (_) { input.value = text(value, ""); }
    } else input.value = text(value, "");
    if (field.key === "relationship_stage_names") {
      const names = stageNames(input.value);
      root.querySelectorAll("[data-stage-index]").forEach(entry => {
        if (entry !== document.activeElement) entry.value = names[Number(entry.dataset.stageIndex)];
      });
    }
    if (field.key === "relationship_stage_descriptions") {
      const descriptions = descriptionValues(input);
      descriptions.forEach((value, index) => {
        const entry = root.querySelector(`#stage-description-${index}`);
        if (entry && entry !== document.activeElement) entry.value = value || controlled(DEFAULT_DESCRIPTIONS[index]);
      });
    }
  }
}
