import { t, locale, controlled, resource } from "./i18n.mjs?v=eff0d6f932b0";
export const PAGE_SIZE = 10;
export const SECTIONS = resource({
  overview: ["01", "PERSONAL TELEMETRY", "TA"],
  persona: ["02", "PERSONA", t("人格")],
  relationships: ["04", "RELATIONSHIPS", t("关系")],
  behavior: ["05", "BEHAVIOR", t("主动行为")],
  night: ["06", "NIGHT", t("长夜")],
  experience: ["07", "DIARY & DREAM", t("日记与梦境")],
  memory: ["08", "MEMORY", t("记忆接入")],
  settings: ["09", "SETTINGS", t("设置")],
});
export const DIMENSIONS = resource({
  pleasure: t("愉悦"), arousal: t("唤醒"), stress: t("压力"), social_need: t("社交需求"),
});
// 页面五维：前四维参与运行期计算，底气只由模型异步写入、只用于展示。
export const BOT_DIMENSIONS = resource({
  pleasure: t("愉悦"), arousal: t("唤醒"), stress: t("压力"),
  social_need: t("社交需求"), control: t("底气"),
});
export const ACTIONS = resource({
  "night.sleep": [t("手动入睡"), t("变更作息状态。不会在此页面直接发送晚安。")],
  "night.wake": [t("手动叫醒"), t("变更作息状态；后续行为仍须通过单一执行端与硬闸门。")],
  "diary.generate": [t("生成私人日记"),
    t("立即生成当日私人日记；无当日素材时写自省。成功后替换当天日记，不受自动设置与日额度限制。")],
  "dream.generate": [t("生成梦境"), t("立即生成当日梦境；两种主题结合当日情绪。成功后替换当天梦境，不受自动设置与日额度限制。")],
  "behavior.send": [t("生成并真实发送"), t("可能调用模型并向当前范围真实发送消息。硬否决仍生效；结果不明时不要重复执行。")],
  "experience.pin": [t("修改置顶"), t("保存这篇日记或梦境的置顶状态，不调用模型。取消置顶后按原创建日期恢复保留规则。")],
});
export const object = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};
export const list = value => Array.isArray(value) ? value : [];
export const text = (value, fallback = t("未提供")) =>
  typeof value === "string" || typeof value === "number" && Number.isFinite(value) ? String(value) : fallback;
export const unit = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
export const percent = value => unit(value) === null ? t("未提供") : `${Math.round(value * 100)}%`;
export const yesno = value => value === true ? t("开启") : value === false ? t("关闭") : t("未提供");
export const reasons = value => list(value).map(item => text(item, "")).filter(Boolean).join("；") || t("未提供");
export const hasRevision = value => typeof value === "string" && value.length > 0 || typeof value === "number" && Number.isFinite(value);
export const NIGHT_STATES = resource({ awake: t("清醒"), nap: t("小憩"), groggy: t("恍惚"), drowsy: t("困"), deep_sleep: t("沉睡") });
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
export function modelDiagnosticText(code) {
  const labels = {
    uncollected: "未采集最近分析，请等待一次新互动", model_disabled: "模型细化未开启",
    queued: "已排队", running: "正在分析", completed: "分析完成，已应用有效结果（变化也可能为零）",
    ready: "模型绑定与预算参数可用，尚未调用模型",
    mode_unavailable: "当前模式不允许模型细化", observe_only: "当前仅观察",
    route_missing: "缺少真实会话路由", source_invalid: "真实消息来源不可用",
    context_changed: "会话或运行代次已变化", state_changed: "状态已更新，旧结果未覆盖新状态",
    seed_missing: "本次事件没有可细化的状态", queue_full: "分析队列已满",
    model_unavailable: "没有可用的生成模型", provider_budget_contract_unsupported: "模型适配器不支持所需预算参数",
    provider_changed: "分析期间模型已切换", task_cancelled: "分析已取消",
    model_output_invalid: "模型结果格式无效，未应用",
    quota_exhausted: "模型预算已用完", quota_limit: "模型预算已用完", quota_cooldown: "模型仍在冷却",
    global_quota_limit: "总模型预算已用完", scope_quota_limit: "会话模型预算已用完",
    daily_limit: "每日模型预算已用完", min_interval: "尚未到下次模型分析时间",
    token_limit: "Token 预算不足", rate_limited: "模型调用频率受限",
    task_timeout: "分析超时，结果不明", model_result_unknown: "模型结果不明",
    stale_generation: "旧运行代次的结果已丢弃", runtime_stopped: "运行已停止",
    job_failed: "分析任务失败", analysis_failed: "分析失败，未应用结果",
  };
  return t(labels[code] || "分析未完成，请核对模型与运行设置");
}

export function date(value, timeZone, options = {}) {
  if (value === undefined || value === null || value === "") return t("未提供");
  const parsed = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(parsed.getTime()) ? t("时间无效") : new Intl.DateTimeFormat(locale(), {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
    ...(timeZone ? { timeZone } : {}),
    ...options,
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
const defaultStageKeys = ["反感", "陌生", "友好", "亲近", "独特"];
export const DEFAULT_STAGE_NAMES = resource(defaultStageKeys);
export function stageNames(value) {
  if (value === "" || value == null) return Array(5).fill("");
  let names;
  try { names = typeof value === "string" ? JSON.parse(value) : value; }
  catch (_) { throw new Error(t("阶段名称必须是包含5个字符串的JSON数组，每个名称最多100字符。")); }
  if (!Array.isArray(names) || ![5, 11].includes(names.length) || names.some(name => typeof name !== "string" || name.length > 100)) {
    throw new Error(t("阶段名称必须是包含5个字符串的JSON数组，每个名称最多100字符。"));
  }
  return names.length === 11 ? [0, 2, 5, 6, 10].map(index => names[index]) : names;
}
export function relationshipStage(item, configured) {
  const index = typeof item.score === "number" && Number.isFinite(item.score) && item.score >= 0 && item.score <= 100 ?
    [11, 25, 45, 100].filter(threshold => item.score >= threshold).length :
    Number.isInteger(item.stage_index) && item.stage_index >= 0 && item.stage_index <= 4 ? item.stage_index :
    /^stage_[0-4]$/.test(item.stage_key || "") ? Number(item.stage_key.slice(6)) : null;
  if (index === null) return { index, name: t("未建立"), custom: false };
  let names = [];
  try { names = stageNames(configured); } catch (_) { /* 无效配置不影响旧数据展示。 */ }
  if (names.every((name, index) => name === defaultStageKeys[index])) names = [];
  const custom = names[index]?.trim() || (typeof item.stage_name === "string" && item.stage_name.trim() && controlled(item.stage_name) !== DEFAULT_STAGE_NAMES[index] ? item.stage_name : "");
  return { index, name: custom || DEFAULT_STAGE_NAMES[index], custom: !!custom };
}
export function behaviorFields(config) {
  const keys = new Set(list(config.groups).filter(group => group.id === "behavior").flatMap(group => list(group.field_keys)));
  return list(config.fields).filter(field => field.section === "behavior" || keys.has(field.key));
}
// 后端已把原因码翻成中文时直接显示；旧后端只给原因码时在页面兜底翻译，
// 避免把 conversation_active 这类内部标识直接丢给使用者。
export const BEHAVIOR_REASONS = resource({
  random_wait: t("正在等一个自然的时机"), checking: t("正在想要不要开口"),
  random_skip: t("这次先安静陪着"), conversation_active: t("还在聊天，先不插话"),
  missed_opportunity: t("错过的时机已跳过"), opportunity_interrupted: t("上次检查中断，已停止旧任务"),
  opportunity_timeout: t("这次检查超时，先停下来"), select_scene: t("选择私聊或群聊查看具体节奏"),
  eligible: t("全部条件满足，可以开口"), autonomy_disabled: t("未开启主动找人"),
  sleeping: t("TA 正在睡觉或刚醒"), cooldown: t("仍在冷却时间内"),
  unanswered_backoff: t("对方几次没回应，已主动放慢"), below_score_threshold: t("当前时机分数不足"),
  low_energy: t("精力过低，需要先休息"), do_not_disturb: t("处于免打扰时段"),
  outside_active_hours: t("不在允许主动联系的时间段内"),
  global_quota_exhausted: t("今天主动说话的总额度已用完"),
  scope_quota_exhausted: t("这个会话今天的额度已用完"),
  unverified_route: t("会话路由未验证，不能发送"), muted_scope: t("当前范围已被静音"),
});
export function behaviorReason(value) {
  const codes = Array.isArray(value) ? value : [value];
  const parts = codes.filter(code => typeof code === "string" && code)
    .map(code => BEHAVIOR_REASONS[code] || code);
  return parts.join("；");
}
export const EMOTIONS = resource({ joy: t("喜悦"), anger: t("愤怒"), sadness: t("悲伤"), fear: t("恐惧"), surprise: t("惊讶"), affection: t("关爱") });
export const ANALYSIS_DIMENSIONS = resource({ valence: t("情感效价"), arousal: t("唤醒"), stress: t("压力"), social_need: t("社交需求"), control: t("掌控感"), certainty: t("确定感") });
export const AFFECT_LABELS = resource({ calm: t("平静"), neutral: t("平常"), happy: t("开心"), joyful: t("喜悦"), sad: t("悲伤"), anxious: t("焦虑"), angry: t("愤怒"), tired: t("疲惫"), excited: t("兴奋"), caring: t("关切"), lonely: t("孤独"), content: t("满足"), strained: t("紧绷"), tense: t("紧张"), concerned: t("担忧"), subdued: t("低落"), alert: t("警觉"), seeking_company: t("渴望陪伴") });
export function affectLabel(value, fallback = t("未提供")) {
  const raw = text(value, "");
  const labels = raw.split(",").map(label => label.trim()).filter(Boolean);
  return labels.length && labels.every(label => Object.hasOwn(AFFECT_LABELS, label)) ?
    labels.map(label => AFFECT_LABELS[label]).join(locale() === "en" ? ", " : "、") : raw || fallback;
}
export function emotionAnalysis(data) {
  const analysis = object(data.emotion_analysis);
  const topTA = object(analysis.bot), topHuman = object(analysis.human);
  const bot = Object.keys(topTA).length ? topTA : object(object(data.bot_state).emotion_analysis);
  const human = Object.keys(topHuman).length ? topHuman : object(object(data.observation).emotion_analysis);
  return { bot, human, available: Object.keys(bot).length > 0 };
}
export function emotionOwnership(data) {
  const kind = text(object(data.bot_state).scope_kind, "") || text(data.state_mode, "");
  const shared = ["persona", "shared"].includes(kind) || (!kind && object(object(data.config).values).persona_shared_state === true);
  const labels = { persona: t("同一人格共享"), shared: t("同一人格共享"), scene: t("真实会话独立"), context: t("真实会话独立") };
  return { kind, shared, label: Object.hasOwn(labels, kind) ? labels[kind] : kind || (shared ? t("同一人格共享") : t("由宿主解析")) };
}
export const ANALYSIS_BASES = resource({
  local_affect_heuristic: t("本地情绪数值启发式"),
  observed_human_signal: t("按人记录的 HumanObservation 信号"),
});
export function analysisBasis(value) {
  const label = item => typeof item === "string" ? (Object.hasOwn(ANALYSIS_BASES, item) ? ANALYSIS_BASES[item] : item) :
    item && typeof item === "object" ? JSON.stringify(item) : text(item);
  return Array.isArray(value) ? value.map(label).join("；") || t("未提供") : label(value);
}
export const experienceStatus = value => value === "queued" ? t("已排队") :
  ["succeeded", "success", "completed", "generated"].includes(value) ? t("已完成") : resultLabel(value);
export const REASON_CODES = resource({
  generated: t("内容已生成。"), succeeded: t("操作已完成。"), pin_updated: t("置顶状态已更新。"),
  already_generated: t("本周期已有记录，不重复生成。"), already_exists: t("记录已存在，不重复生成。"),
  model_unavailable: t("模型不可用，请检查模型配置。"), provider_unavailable: t("模型不可用，请检查模型配置。"),
  model_not_configured: t("尚未配置模型。"), no_material: t("没有可用素材，不会编造经历。"), no_sources: t("没有可用素材，不会编造经历。"),
  insufficient_material: t("有效素材不足，暂不生成。"), budget_exhausted: t("模型预算已用完。"), daily_limit: t("已达到每日额度。"),
  quota_exhausted: t("本周期额度已用完。"), dream_limit: t("已达到本夜梦境上限。"), not_sleeping: t("当前未处于允许生成梦境的睡眠阶段。"),
  not_deep_sleep: t("当前未处于允许生成梦境的睡眠阶段。"), disabled: t("此功能已关闭。"), unknown: t("结果不明，请核对记录，不要重复执行。"),
  autonomy_disabled: t("自主发送已关闭。"), observe_only: t("观察模式不自主发送。"), cooldown: t("仍在冷却时间内。"),
  sleeping: t("睡眠限制仍生效。"), conversation_active: t("聊天仍活跃，暂不插话。"),
  generation_disabled: "生成功能已关闭或当前模式不允许生成。",
  dream_requires_live_rem: "自动做梦需要睡着并睡满一小时（不再要求 REM 阶段）；手动触发不看这一条。",
  night_revalidation_unavailable: "无法重新验证睡眠状态，暂不生成梦境。",
  experience_attempt_limit: "已达到日记或本周期梦境的尝试上限。",
  experience_exists: "记录已存在，不重复生成。", experience_saved: "内容已保存。",
  no_qualified_material: "没有符合来源权限和有效期要求的素材。",
  model_or_tokenizer_unavailable: "生成模型或 Token 计数能力不可用。",
  diary_not_due: "尚未到计划日记时间。", diary_backfill_out_of_range: "补写日期超出允许范围。",
  diary_date_invalid: "日记日期无效。", diary_manual_invalid: "手动生成参数无效。",
  context_changed: "会话范围或版本已变化，请刷新后核对。",
  evidence_changed: "素材依据已变化，已停止本次生成。", context_or_evidence_changed: "会话范围或素材依据已变化，已停止本次生成。",
  mixed_context_revisions: "素材范围版本不一致，无法生成。",
  experience_preparation_unavailable: "生成准备失败，请检查宿主记录。",
  new_human_message: "生成期间来了新消息，这一天不再算封存。写今天的日记需要安静时段；补写昨天不受影响。",
  stale_generation: "会话状态已被重置（清空或换版本），这次没有写入；可以重试。",
  experience_status_unavailable: "任务状态读取失败，请刷新页面重试。",
  model_response_invalid: "模型返回内容不可用，未保存。",
  multi_scope_commit_unsupported: "宿主不支持此次跨范围保存。",
  input_token_limit: "素材超出模型输入上限（已自动压缩；仍失败请到设置里调大「模型输入上限」）。",
  input_budget_too_small: "模型输入上限太小，装不下系统提示与人格；请到设置里调大「模型输入上限」。",
  output_token_limit: "输出超出 Token 上限。",
  persona_text_invalid: "人格内容无效，无法生成。", model_response_invalid: "模型响应无效，未保存生成内容。",
  generation_failed: "生成失败，请检查宿主记录和额度。", generation_cancelled: "本次生成已取消。",
  model_timeout: "模型请求超时，结果不明，不自动重试。", queued: "已排队，完成后自动更新。",
  model_preflight_http_error: "接口预检查未返回 HTTP 200，本次未生成。",
  model_preflight_timeout: "接口预检查超时，本次未生成。",
  model_preflight_unavailable: "接口预检查未连接成功，本次未生成。",
  dream_success_limit: "这一夜已写够梦境。",
  generation_in_progress: "同一任务正在生成，完成后自动更新。",
  duplicate_job: "已有相同任务，不重复提交。", job_not_retained: "任务状态已不再保留，请核对记录。",
  dream_remembered: "梦境仍可回忆，内容始终是想象。", dream_faint_no_details: "梦境已模糊，不展示细节。", dream_forgotten: "梦境已淡忘，不补造细节。", 
});
export const RESULT_LABELS = resource({ queued: "已排队", completed: "已完成", succeeded: "已完成", success: "已完成", generated: "已生成", updated: "已更新", skipped: "已跳过", rejected: "已拒绝", failed: "失败", cancelled: "已取消", canceled: "已取消", unknown: "结果不明", pending: "等待执行", running: "执行中", blocked: "受限" });
export const resultLabel = value => Object.hasOwn(RESULT_LABELS, value) ? `${RESULT_LABELS[value]} (${value})` : text(value);
export function reasonExplanation(code) {
  const http = /^model_preflight_http_error:(\d{3})$/.exec(code);
  if (http) return `${REASON_CODES.model_preflight_http_error} HTTP ${http[1]}`;
  return REASON_CODES[code] || t("后端返回了此原因码，详细含义请核对宿主说明；页面不会绕过限制。");
}
export function normalizeState(raw) {
  const data = object(raw);
  if (data.api_version !== 1) throw Object.assign(new Error(t("页面 API 版本不兼容，需要 api_version=1。")), { code: "incompatible_version" });
  const contextId = text(data.context_id, "");
  const contexts = list(data.contexts).filter(item => typeof item?.id === "string" && item.id).map(item => ({
    id: item.id, label: text(item.label, item.id),
  }));
  if (contextId && !contexts.some(item => item.id === contextId)) {
    throw Object.assign(new Error(t("当前范围不在已授权列表内。")), { code: "invalid_context" });
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
    generation_target: object(data.generation_target),
    action_target: object(data.action_target),
  };
}
export function normalizeRecords(raw, requestedPage) {
  const data = object(raw);
  if (data.api_version !== 1 || !Array.isArray(data.items) || data.page_size !== PAGE_SIZE ||
      !Number.isSafeInteger(data.total) || data.total < 0 || data.page !== requestedPage ||
      data.items.length > PAGE_SIZE) {
    throw Object.assign(new Error(t("记录分页响应不符合 v1 契约，未显示不完整数据。")), { code: "invalid_response" });
  }
  return { ...data, items: data.items.map(object) };
}
export function fieldValue(field, input) {
  if (field.type === "boolean") return input.checked;
  if (field.type === "enum") {
    const option = list(field.options).find(item => item && String(item.value) === input.value);
    if (!option) throw new Error(t("请选择有效选项。"));
    return option.value;
  }
  if (["integer", "number", "float"].includes(field.type)) {
    const value = input.value.trim() === "" ? NaN : Number(input.value);
    if (!Number.isFinite(value) || field.type === "integer" && !Number.isInteger(value) ||
        typeof field.min === "number" && value < field.min ||
        typeof field.max === "number" && value > field.max) throw new Error(t("请输入范围内的有效数值。"));
    if (Number.isFinite(field.step) && field.step > 0 &&
        Math.abs((value - (field.min || 0)) / field.step - Math.round((value - (field.min || 0)) / field.step)) > 1e-7) {
      throw new Error(t("请按 {0} 的步进输入。", [field.step]));
    }
    return value;
  }
  if (field.type === "string") return input.value;
  throw new Error(t("此字段类型暂不支持编辑。"));
}
