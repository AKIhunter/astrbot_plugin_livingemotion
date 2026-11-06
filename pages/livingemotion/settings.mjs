import { object, list, text, fieldValue } from "./model.mjs";
import { node } from "./dom.mjs";
const labels = {
  enabled: "启用 livingEmotion", mode: "工作模式", persona_mode: "人格解析方式", persona_id: "原生人格",
  state_mode: "状态模式", shared_state: "同一人格共享状态", persona_shared_state: "同一人格共享状态",
  state_shared: "同一人格共享状态", state_scope_mode: "状态归属模式",
  provider_id: "默认生成模型", livingmemory_enabled: "使用 LivingMemory", allow_sleep: "允许 TA 睡眠",
  timezone: "本地 IANA 时区", night_timezone: "本地 IANA 时区", residence_city: "Bot 住所城市",
  home_city: "Bot 住所城市", model_provider_id: "默认生成模型", emotion_model_enabled: "模型细化情绪",
  emotion_provider_id: "情绪模型", emotion_model_provider_id: "情绪模型", model_daily_limit: "每日模型预算",
  model_concurrency: "模型并发上限", model_token_budget: "每日 Token 预算",
  autonomy_enabled: "允许主动找人", autonomy_provider_id: "主动行为模型", group_enabled: "允许群聊主动行为",
  night_enabled: "允许 TA 睡眠", sleep_enabled: "允许 TA 睡眠",
  nap_start: "午休开始", nap_end: "午休结束", night_nap_start: "午休开始", night_nap_end: "午休结束",
  sleep_start: "夜间疲劳开始", sleep_end: "夜间疲劳结束", deep_sleep_at: "沉睡时间",
  wake_at: "基础起床时间", wake_time: "基础起床时间", sleep_time: "夜间疲劳开始",
  wake_mode: "聊天唤醒规则", wake_reply_limit: "唤醒回复轮数", wake_window_minutes: "唤醒窗口",
  wake_delay_min_minutes: "赖床最短时间", wake_delay_max_minutes: "赖床最长时间",
  energy_reply_cost: "每次回复消耗", energy_fatigue_per_minute: "疲劳每分钟消耗",
  energy_recovery_per_minute: "每分钟恢复", energy_max: "精力上限（固定）",
  night_energy_reply_cost: "每次回复消耗", night_energy_fatigue_per_minute: "疲劳每分钟消耗",
  night_energy_recovery_per_minute: "每分钟恢复",
  closing_enabled: "睡前晚安", closing_random: "道别语随机生成", closing_provider_id: "收尾模型",
  catchup_enabled: "醒后阅读未读", catchup_reply_enabled: "醒后历史补答", catchup_provider_id: "补课模型",
  diary_enabled: "自动私人日记", diary_provider_id: "日记模型", dream_enabled: "自动梦境",
  dream_provider_id: "梦境模型", memory_mode: "记忆后端", use_livingmemory: "使用 LivingMemory",
  memory_read: "允许记忆检索", memory_export: "允许记忆写入", memory_write: "允许记忆写入",
  embedding_provider_id: "原生向量模型", memory_embedding_provider_id: "原生向量模型",
};
const optionLabels = {
  active: "参与表达与行为", observe_only: "仅观察", disabled: "停用", follow: "跟随原生会话",
  explicit: "指定原生人格", none: "未启用", local_lite: "本地轻量记录", local_vector: "本地向量记忆",
  external: "LivingMemory", chat: "私聊可叫醒", never: "聊天不可叫醒", both: "私聊或群聊原生 @",
  global: "同一人格共享", shared: "同一人格共享", persona_shared: "同一人格共享", scene: "按真实会话独立",
  context: "按真实会话独立", per_scene: "按真实会话独立",
};
const groups = { quick: "快速开始", persona: "人格与状态模式", emotion: "情绪", relationships: "关系",
  behavior: "主动行为", night: "长夜", experience: "日记与梦境", memory: "记忆" };
const quickKeys = new Set(["enabled", "mode", "persona_id", "timezone", "night_timezone", "model_provider_id",
  "residence_city", "home_city", "memory_mode", "use_livingmemory", "night_enabled", "sleep_enabled"]);
const advancedPattern = /budget|limit|threshold|concurrency|timeout|cooldown|retention|ttl|maximum|max_records|read|export|write|lead|backoff/;
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
    return { id: group.id, label: group.label, fields: selected };
  });
  const remaining = fields.filter(field => !used.has(field.key)).filter(field => {
    const target = result.find(group => group.id === field.section);
    if (!target) return true;
    target.fields.push(field); return false;
  });
  if (remaining.length) result.push({ id: "additional", label: "其他高级设置", fields: remaining });
  return result;
}
export function schedulePreview(values) {
  const minutes = value => typeof value === "string" && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value) ?
    Number(value.slice(0, 2)) * 60 + Number(value.slice(3)) : null;
  const start = minutes(values.fatigue_start), deep = minutes(values.deep_sleep_at), wake = minutes(values.wake_at);
  if ([start, deep, wake].includes(null)) return "作息时间未完整配置，不能计算预览。";
  const deepAt = deep < start ? deep + 1440 : deep;
  const wakeAt = wake <= start ? wake + 1440 : wake;
  if (deepAt >= wakeAt) return "沉睡时间应位于夜间开始与基础起床之间，请核对跨午夜顺序。";
  const clock = value => `${value >= 1440 ? "次日 " : "当日 "}${String(Math.floor(value / 60) % 24).padStart(2, "0")}:${String(Math.floor(value) % 60).padStart(2, "0")}${value % 1 ? ":30" : ""}`;
  return `本地 ${text(values.timezone, "时区未配置")}：夜间 ${clock(start)} → 恍惚转困 ${clock((start + deepAt) / 2)} → 沉睡 ${clock(deepAt)} → 基础起床 ${clock(wakeAt)}。实际起床另加本周期持久赖床值，不在页面重抽。`;
}
export function renderSettings(root, state, options, updateControls) {
  root.replaceChildren(); root.hidden = state.section !== "settings";
  if (root.hidden) return;
  root.append(node("p", "一份原生配置，一次保存。普通分区只阅读状态；以下更改统一提交到 AstrBot。", "hint"),
    node("p", `来源：${text(state.data.config.source)} · 版本 ${text(state.data.config.revision)}`, "micro"));
  const fields = [...state.data.config.fields, ...list(state.data.config.readonly).filter(field =>
    field && !state.data.config.fields.some(item => item.key === field.key))];
  const previewText = node("p", schedulePreview({ ...state.data.config.values, ...state.draft }), "hint");
  previewText.id = "schedule-preview";
  if (!fields.length) root.append(node("p", "宿主未提供可编辑字段，请检查原生配置能力。", "empty"));
  for (const { id: group, label: title, fields: selected } of settingsGroups(fields, state.data.config)) {
    if (!selected.length && group !== "night") continue;
    const section = node("section", undefined, "settings-group"); section.dataset.taskGroup = group;
    section.append(node("h2", title));
    const common = node("div"), advanced = node("details"); advanced.className = "advanced-settings";
    advanced.append(node("summary", "高级设置 · 预算、阈值与边界"));
    const advancedBody = node("div", undefined, "details-content"); advanced.append(advancedBody);
    for (const original of selected) {
      const field = { ...original };
      if (/provider_id$/.test(field.key) || field.key === "persona_id") {
        const source = /embedding/.test(field.key) ? options.embedding_providers : options.chat_providers;
        const choices = field.key === "persona_id" ? options.personas : source;
        if (Array.isArray(choices)) {
          field.type = "enum";
          field.options = [{ value: "", label: field.key === "persona_id" ? "跟随当前会话人格" : /embedding/.test(field.key) ? "待配置" : "沿用当前聊天模型" },
            ...choices.map(item => ({ value: item.value ?? item.id, label: item.name ?? item.label ?? item.id }))];
        } else if (Array.isArray(field.options)) field.type = "enum";
      }
      const value = Object.hasOwn(state.draft, field.key) ? state.draft[field.key] :
        Object.hasOwn(state.data.config.values, field.key) ? state.data.config.values[field.key] : field.value;
      const wrapper = node("div", undefined, "field");
      const description = node("div"), id = `config-${field.key}`;
      const rawLabel = text(field.label, field.key);
      const label = node("label", labels[field.key] || rawLabel); label.htmlFor = id;
      const help = node("p", text(field.help, "更改由宿主校验并写回原生配置。"), "hint"); help.id = `${id}-help`;
      description.append(label, help);
      if (field.unit) description.append(node("span", `单位：${text(field.unit)}`, "micro"));
      let input;
      if (field.type === "enum") {
        input = node("select");
        for (const choice of list(field.options)) {
          if (!choice || !["string", "number", "boolean"].includes(typeof choice.value)) continue;
          const option = node("option", field.key === "memory_mode" && choice.value === "none" ? "本地向量（待配置）" :
            optionLabels[choice.value] || text(choice.label, choice.value));
          option.value = String(choice.value); input.append(option);
        }
        if (!list(field.options).some(choice => choice?.value === value)) {
          const unknown = node("option", `当前值：${text(value)}`); unknown.value = ""; unknown.disabled = true; input.prepend(unknown);
          input.value = "";
        } else input.value = String(value);
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
      input.id = id; input.dataset.key = field.key;
      if (field.readonly) input.readOnly = true;
      input.setAttribute("aria-describedby", help.id);
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
          if (!Object.keys(state.draft).length) state.baseRevision = state.data.config.revision;
          if (next === state.data.config.values[field.key]) delete state.draft[field.key];
          else state.draft[field.key] = next;
          if (!Object.keys(state.draft).length) state.conflict = false;
          previewText.textContent = schedulePreview({ ...state.data.config.values, ...state.draft });
          updateControls();
        } catch (error) {
          state.invalidFields.set(field.key, { value: input.value, message: error.message });
          input.setCustomValidity(error.message); input.setAttribute("aria-invalid", "true"); input.reportValidity(); updateControls();
        }
      });
      if (field.key === "autonomy_scopes") {
        const choices = node("div", undefined, "details-content");
        const sources = new Map(list(state.scopes?.contexts).filter(c =>
          typeof c.scope_key === "string" && c.scope_key
        ).map(c => [c.scope_key, c]));
        for (const [scopeKey, scope] of sources) {
          const choice = node("label", undefined, "scope-choice");
          const check = node("input"); check.type = "checkbox";
          check.dataset.autonomyScope = scopeKey;
          check.dataset.editable = input.dataset.editable;
          check.checked = String(value || "").split(/\s+/).includes(scopeKey);
          check.addEventListener("change", () => {
            const scopes = new Set(input.value.split(/\s+/).filter(Boolean));
            if (check.checked) scopes.add(scopeKey); else scopes.delete(scopeKey);
            input.value = [...scopes].join(" ");
            input.dispatchEvent(new Event("input", { bubbles: true }));
          });
          input.addEventListener("input", () => {
            check.checked = input.value.split(/\s+/).includes(scopeKey);
          });
          choice.append(check, node("span", `${text(scope.platform)} / ${scope.view_scope === "group" ?
            "群聊 " + text(scope.scene_id) : "私聊 " + text(scope.account_id)}`));
          choices.append(choice);
        }
        description.append(node("p", "勾选允许联系的会话，保存后生效。", "hint"), choices);
      }
      wrapper.append(description, input);
      (field.advanced || advancedPattern.test(field.key) ? advancedBody : common).append(wrapper);
    }
    section.append(common);
    if (group === "night") {
      section.append(node("p", "精力上限固定 100，不可修改。", "hint"));
      section.append(previewText);
      const preview = object(state.data.night.schedule_preview ?? options.schedule_preview);
      if (Object.keys(preview).length) section.append(node("p",
        `作息预览：${text(preview.reason ?? preview.summary)} · 恍惚转困 ${text(preview.drowsy_at)} · 实际起床 ${text(preview.wake_at)}`, "hint"));
      else section.append(node("p", "以上是配置顺序预览，不代表当前周期的持久实际起床时刻。最终作息以宿主状态与校验为准。", "hint"));
    }
    if (advancedBody.childElementCount) section.append(advanced);
    root.append(section);
  }
}
