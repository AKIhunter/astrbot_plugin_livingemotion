// Synthetic data only. Never imported by the production page.
export function makeState(contextId = "fixture-a") {
  return {
    api_version: 1, context_id: contextId, revision: "action-1",
    contexts: [{ id: "fixture-a", label: "合成范围 A · Bot / 私聊" }, { id: "fixture-b", label: "合成范围 B · Bot / 群聊" }],
    updated_at: "2026-11-05T10:30:00Z", mode: "observe_only",
    capabilities: ["config.write", "behavior.preview"],
    config: {
      revision: "config-1", source: "AstrBot 原生配置（合成）",
      values: { mode: "observe_only", emotion_model_enabled: false, autonomy_enabled: false, night_enabled: true, diary_enabled: false, memory_mode: "none", memory_read: false, memory_export: false, model_daily_limit: 48 },
      fields: [
        { key: "mode", label: "工作模式", section: "emotion", type: "enum", options: [{ value: "active", label: "参与表达与行为" }, { value: "observe_only", label: "仅观察" }], help: "观察模式不注入状态，不自主发送。" },
        { key: "emotion_model_enabled", label: "模型细化", section: "emotion", type: "boolean", help: "开启后按后台预算运行，普通聊天不等待额外调用。" },
        { key: "model_daily_limit", label: "每日模型预算", section: "emotion", type: "integer", min: 1, max: 100, help: "额度包含失败与在途预留。" },
        { key: "autonomy_enabled", label: "自主发送", section: "behavior", type: "boolean", help: "仍受白名单、免打扰、配额与发送前复核限制。" },
        { key: "night_enabled", label: "作息状态", section: "night", type: "boolean", help: "精力只由长夜结算。" },
        { key: "diary_enabled", label: "私人日记", section: "experience", type: "boolean", help: "关闭长期记忆仍可使用有来源的本地互动。" },
        { key: "memory_mode", label: "长期记忆模式", section: "memory", type: "enum", options: [{ value: "none", label: "关闭长期记忆" }, { value: "local_lite", label: "内置轻量" }, { value: "external", label: "外部后端" }] },
        { key: "memory_read", label: "允许检索", section: "memory", type: "boolean" },
        { key: "memory_export", label: "允许导出", section: "memory", type: "boolean" },
      ],
    },
    persona: { name: "测试人格", id: "fixture-persona", source: "AstrBot 当前会话（合成）", revision: "persona-3", description: "仅用于前端测试。没有模型或真实账号。" },
    bot_state: {
      label: "平静，保有一点关切", reason: "对方表达了低落；Bot 的压力轻微上升，但并未直接继承对方的悲伤。",
      updated_at: "2026-11-05T10:28:00Z", expires_at: "2099-11-05T11:00:00Z", source: "fixture-event-12", version: "bot-7",
      dimensions: { pleasure: 0.58, arousal: 0.32, stress: 0.18, social_need: 0.42 },
    },
    observation: {
      subject: "合成对方 A", label: "低落，需要被倾听", confidence: 0.82,
      reason: "依据一条明确表达心情的合成消息。", observed_at: "2026-11-05T10:28:00Z",
      expires_at: "2099-11-05T11:00:00Z", source: "fixture-observation-1",
    },
    relationship: { stage: "熟悉", raw: 420, normalized: 0.42, scale: "0–1000", source_completeness: "完整（合成）", identity_revision: "identity-2", reason: "稳定互动；本次变化 +2。" },
    availability: { available: false, state: "observe_only", reasons: ["观察模式不自主发送"] },
    health: [
      { name: "状态存储", status: "ok", reason: "测试桩可用；无数据库连接" },
      { name: "模型", status: "unavailable", reason: "未配置；规则状态继续工作" },
      { name: "长期记忆", status: "degraded", reason: "模式 none；情绪、关系和作息仍可运行" },
    ],
    behavior: { enabled: false, remaining: 3, cooldown_until: null, backoff: "无待回复", reason: "自主发送关闭",
      candidates: [{ label: "合成候选 A", score: 0.61, vetoes: ["autonomy_disabled", "observe_only"] }] },
    night: { state: "清醒", stage: "不在睡眠窗口", energy: 0.76, sleep_at: null, wake_at: null, reason: "按真实时间结算（合成输入）", catch_up: { completed: 8, total: 12, reason: "仅处理有界未读范围，不自动补发。" } },
    experience: { diary_enabled: false, dream_enabled: false, reason: "手动生成未配置模型，自动任务默认关闭。" },
    memory: { mode: "none", provider: "无", can_read: false, can_write: false, capabilities: [], reason: "没有长期记忆仍保留自身运行状态。" },
    actions: [
      { id: "night.sleep", enabled: true }, { id: "night.wake", enabled: true },
      { id: "diary.generate", enabled: false, reason: "未配置模型" }, { id: "dream.generate", enabled: false, reason: "未配置模型" },
      { id: "behavior.send", enabled: false, reason: "未启用自主发送；没有真实路由" },
    ],
  };
}
export const ATTACK = '<img src=x onerror="window.__injected=true"><script>alert("fixture")</script>';
export function makeRecords(kind) {
  return Array.from({ length: 23 }, (_, index) => ({
    id: `fixture-${kind}-${index + 1}`, created_at: 1793874600 - index * 300, status: "succeeded",
    label: `合成变化 ${index + 1}`, title: `合成${kind === "dream" ? "梦境" : "日记"} ${index + 1}`,
    reason: kind === "emotion" ? "倾听后的关切，变化受上限约束。" : "来自明确授权的合成材料。",
    before: { pleasure: .50, arousal: .30, stress: .15, social_need: .40 },
    after: { pleasure: .58 - index * .009, arousal: .32, stress: .18, social_need: .42 },
    expires_at: index === 1 ? 1 : 4097520000, source: `fixture-source-${index + 1}`,
    candidate: `合成候选 ${index + 1}`, vetoes: ["autonomy_disabled"], result: index === 0 ? "unknown" : "cancelled",
    intent_id: `fixture-intent-${index + 1}`, request_id: `fixture-request-${index + 1}`, latency_ms: 12,
    context: "合成范围，不含真实账号",
    body: "今天我留意到对方的情绪有些低落。我选择保持平静，把注意力留给倾听。\n这是一段用于界面测试的主观文字，不是实际聊天或记忆。",
    visibility: "private", clarity: .72, pinned: false,
    sources: [
      { kind: "bot_action", label: "一次成功回复（合成）", source_id: "fixture-bot-1", excerpt: "我做的：回复被成功发送。" },
      { kind: "human_action", label: "对方表达（合成）", source_id: "fixture-human-1", excerpt: "对方说 / 做的：表达低落。" },
      { kind: "dream", label: "想象（合成）", source_id: "fixture-dream-1", excerpt: "梦中内容：不能认作真实经历。" },
      { kind: "unknown", label: "来源不明（合成）", source_id: "fixture-unknown-1", excerpt: "不认领为自己或对方的行为。" },
    ],
  }));
}
