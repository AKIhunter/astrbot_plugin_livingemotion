export const PAGE_SIZE = 10;
export const SECTIONS = Object.freeze({
  overview: ["01", "PERSONAL TELEMETRY", "TA"],
  persona: ["02", "PERSONA", "人格"],
  emotion: ["03", "EMOTION", "情绪"],
  relationships: ["04", "RELATIONSHIPS", "关系"],
  behavior: ["05", "BEHAVIOR", "主动行为"],
  night: ["06", "NIGHT", "长夜"],
  experience: ["07", "DIARY & DREAM", "日记与梦境"],
  memory: ["08", "MEMORY", "记忆接入"],
  settings: ["09", "SETTINGS", "设置"],
});
export const DIMENSIONS = Object.freeze({
  pleasure: "愉悦", arousal: "唤醒", stress: "压力", social_need: "社交需求",
});
export const ACTIONS = Object.freeze({
  "night.sleep": ["手动入睡", "变更作息状态。不会在此页面直接发送晚安。"],
  "night.wake": ["手动叫醒", "变更作息状态；后续行为仍须通过单一执行端与硬闸门。"],
  "diary.generate": ["生成私人日记", "可能调用模型并消耗额度。只生成私人内容，不发送到聊天。"],
  "dream.generate": ["生成梦境", "可能调用模型并消耗额度。仍须满足睡眠阶段与配额；内容始终是想象。"],
  "behavior.send": ["生成并真实发送", "可能调用模型并向当前范围真实发送消息。硬否决仍生效；结果不明时不要重复执行。"],
  "experience.pin": ["修改置顶", "保存这篇日记或梦境的置顶状态，不调用模型。取消置顶后按原创建日期恢复保留规则。"],
});
export const object = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};
export const list = value => Array.isArray(value) ? value : [];
export const text = (value, fallback = "未提供") =>
  typeof value === "string" || typeof value === "number" && Number.isFinite(value) ? String(value) : fallback;
export const unit = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
export const percent = value => unit(value) === null ? "未提供" : `${Math.round(value * 100)}%`;
export const yesno = value => value === true ? "开启" : value === false ? "关闭" : "未提供";
export const reasons = value => list(value).map(item => text(item, "")).filter(Boolean).join("；") || "未提供";
export const hasRevision = value => typeof value === "string" && value.length > 0 || typeof value === "number" && Number.isFinite(value);
export const NIGHT_STATES = Object.freeze({ awake: "清醒", nap: "小憩", groggy: "恍惚", drowsy: "困", deep_sleep: "沉睡" });
export const energyValue = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
export function scopeParams(value) {
  if (typeof value === "string") return value ? { context_id: value } : {};
  const selection = object(value);
  return Object.fromEntries(["persona_id", "view_scope", "context_id", "platform"]
    .filter(key => typeof selection[key] === "string" && selection[key]).map(key => [key, selection[key]]));
}
export function baselineDimensions(data) {
  return object(data.bot_state?.baseline ?? data.emotion_policy?.baseline ?? data.policy?.emotion?.baseline);
}

export function date(value, timeZone) {
  if (value === undefined || value === null || value === "") return "未提供";
  const parsed = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(parsed.getTime()) ? "时间无效" : new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
    ...(timeZone ? { timeZone } : {}),
  }).format(parsed);
}
export function expired(value, now = Date.now()) {
  if (value === undefined || value === null || value === "") return null;
  const time = new Date(typeof value === "number" ? value * 1000 : value).getTime();
  return Number.isFinite(time) ? time <= now : null;
}
export function safeKey(value) {
  return typeof value === "string" && /^[a-zA-Z0-9_.-]{1,120}$/.test(value) &&
    !value.split(".").some(part => ["__proto__", "constructor", "prototype"].includes(part));
}
export function normalizeState(raw) {
  const data = object(raw);
  if (data.api_version !== 1) throw Object.assign(new Error("页面 API 版本不兼容，需要 api_version=1。"), { code: "incompatible_version" });
  const contextId = text(data.context_id, "");
  const contexts = list(data.contexts).filter(item => typeof item?.id === "string" && item.id).map(item => ({
    id: item.id, label: text(item.label, item.id),
  }));
  if (contextId && !contexts.some(item => item.id === contextId)) {
    throw Object.assign(new Error("当前范围不在已授权列表内。"), { code: "invalid_context" });
  }
  const config = object(data.config);
  const fields = list(config.fields).filter(field => field && safeKey(field.key));
  return {
    ...data, context_id: contextId, contexts,
    config: { ...config, values: object(config.values), fields },
    capabilities: list(data.capabilities).filter(item => typeof item === "string"),
    actions: list(data.actions).filter(item => item && Object.hasOwn(ACTIONS, item.id)),
    bot_state: object(data.bot_state), observation: object(data.observation),
    relationship: object(data.relationship), persona: object(data.persona),
    availability: object(data.availability), health: list(data.health).map(object),
    behavior: object(data.behavior), night: object(data.night),
    experience: object(data.experience), memory: object(data.memory), scope_selection: object(data.selection ?? data.scope_selection),
  };
}
export function normalizeRecords(raw, requestedPage) {
  const data = object(raw);
  if (data.api_version !== 1 || !Array.isArray(data.items) || data.page_size !== PAGE_SIZE ||
      !Number.isSafeInteger(data.total) || data.total < 0 || data.page !== requestedPage ||
      data.items.length > PAGE_SIZE) {
    throw Object.assign(new Error("记录分页响应不符合 v1 契约，未显示不完整数据。"), { code: "invalid_response" });
  }
  return { ...data, items: data.items.map(object) };
}
export function fieldValue(field, input) {
  if (field.type === "boolean") return input.checked;
  if (field.type === "enum") {
    const option = list(field.options).find(item => item && String(item.value) === input.value);
    if (!option) throw new Error("请选择有效选项。");
    return option.value;
  }
  if (["integer", "number", "float"].includes(field.type)) {
    const value = input.value.trim() === "" ? NaN : Number(input.value);
    if (!Number.isFinite(value) || field.type === "integer" && !Number.isInteger(value) ||
        typeof field.min === "number" && value < field.min ||
        typeof field.max === "number" && value > field.max) throw new Error("请输入范围内的有效数值。");
    if (Number.isFinite(field.step) && field.step > 0 &&
        Math.abs((value - (field.min || 0)) / field.step - Math.round((value - (field.min || 0)) / field.step)) > 1e-7) {
      throw new Error(`请按 ${field.step} 的步进输入。`);
    }
    return value;
  }
  if (field.type === "string") return input.value;
  throw new Error("此字段类型暂不支持编辑。");
}
