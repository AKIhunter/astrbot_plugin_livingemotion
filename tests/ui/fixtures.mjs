// Synthetic data only. Never imported by the production page.
import { nativeDTO } from "./native-dto.mjs";
export { nativeDTO, nativeDTOEvidence } from "./native-dto.mjs";
export function makeState(contextId = "fixture-a") {
  const config = structuredClone(nativeDTO.config);
  Object.assign(config.values, { persona_shared_state: false, mode: "observe_only" });
  return {
    api_version: 1, context_id: contextId, revision: "action-1",
    contexts: [{ id: "fixture-a", label: "合成范围 A · Bot / 私聊" }, { id: "fixture-b", label: "合成范围 B · Bot / 群聊" }],
    updated_at: "2026-11-05T10:30:00Z", mode: "observe_only",
    selection: { persona_id: "fixture-persona", view_scope: contextId === "fixture-b" ? "group" : "private", context_id: contextId },
    state_mode: "scene", capabilities: ["config.write", "behavior.preview", "relationship.write"],
    config,
    persona: { name: "测试人格", id: "fixture-persona", source: "AstrBot 当前会话（合成）", revision: "persona-3", description: "仅用于前端测试。没有模型或真实账号。" },
    bot_state: {
      label: "平静而关切", reason: "倾听让压力轻微上升，仍然愿意把注意力留给对方。",
      baseline: { pleasure: .5, arousal: .3, stress: 0, social_need: .3 },
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
    night: { state: "清醒", display_state: "awake", stage: "不在睡眠窗口", energy: 0.76, energy_percent: 76, sleep_at: null, wake_at: null,
      schedule_preview: { summary: "跨午夜夜间，午休独立", drowsy_at: "次日 01:00", wake_at: "次日 08:00 + 本周期赖床" },
      reason: "按真实时间结算（合成输入）", catch_up: { completed: 8, total: 12, reason: "仅处理有界未读范围，不自动补发。" } },
    experience: { diary_enabled: false, dream_enabled: false, reason: "手动生成未配置模型，自动任务默认关闭。" },
    memory: { mode: "local_vector", provider: "待配置 embedding", can_read: false, can_write: false, capabilities: [], reason: "未配置原生向量模型；情绪与作息继续运行。" },
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
    label: `合成变化 ${index + 1}`, title: `合成${{ emotion: "情绪记录", behavior: "行为记录", diary: "日记", dream: "梦境" }[kind]} ${index + 1}`,
    reason: kind === "emotion" ? "倾听后的关切，变化受上限约束。" : "来自明确授权的合成材料。",
    before: { pleasure: .50, arousal: .30, stress: .15, social_need: .40 },
    after: { pleasure: .58 - index * .009, arousal: .32, stress: .18, social_need: .42 },
    expires_at: index === 1 ? 1 : 4097520000, source: `fixture-source-${index + 1}`,
    candidate: `合成候选 ${index + 1}`, vetoes: ["autonomy_disabled"], result: index === 0 ? "unknown" : "cancelled",
    intent_id: `fixture-intent-${index + 1}`, request_id: `fixture-request-${index + 1}`, latency_ms: 12,
    context: "合成范围，不含真实账号",
    body: "今天我留意到对方的情绪有些低落。我选择保持平静，把注意力留给倾听。\n这是一段用于界面测试的主观文字，不是实际聊天或记忆。",
    visibility: "private", clarity: .72, pinned: false,
    context_id: "fixture-a", pin_available: kind === "diary" || kind === "dream",
    sources: [
      { kind: "bot_action", label: "一次成功回复（合成）", source_id: "fixture-bot-1", excerpt: "我做的：回复被成功发送。" },
      { kind: "human_action", label: "对方表达（合成）", source_id: "fixture-human-1", excerpt: "对方说 / 做的：表达低落。" },
      { kind: "dream", label: "想象（合成）", source_id: "fixture-dream-1", excerpt: "梦中内容：不能认作真实经历。" },
      { kind: "unknown", label: "来源不明（合成）", source_id: "fixture-unknown-1", excerpt: "不认领为自己或对方的行为。" },
    ],
  }));
}
export function makeScopes() {
  return { api_version: 1, personas: [{ id: "fixture-persona", name: "测试人格" }, { id: "fixture-persona-b", name: "第二人格（合成）" }],
    platforms: ["qq", "bilibili"], counts: { global: 2, private: 1, group: 1 },
    contexts: [
      { id: "fixture-a", persona_id: "fixture-persona", platform: "qq", view_scope: "private", scene_id: "scene-a", account_id: "10001", label: "QQ / 私聊 / 合成 A" },
      { id: "fixture-b", persona_id: "fixture-persona", platform: "bilibili", view_scope: "group", scene_id: "scene-b", account_id: "10001", label: "B站 / 群聊 / 合成 B" },
    ] };
}
export function makeRelationships() {
  return Array.from({ length: 217 }, (_, index) => ({
    id: `fixture-persona/${index % 2 ? "bilibili" : "qq"}/${10001 + Math.floor(index / 2)}`,
    persona_id: "fixture-persona", platform: index % 2 ? "bilibili" : "qq", account_id: String(10001 + Math.floor(index / 2)),
    label: `合成人物 ${index + 1}`, score: 42 + index % 50, raw: (42 + index % 50) * 10, normalized: (42 + index % 50) / 100,
    stage: "熟悉", trust: index % 2 ? null : .6, familiarity: .7, boundary: null, frozen: false,
    source_completeness: "完整（合成）", sources: [], version: 0,
  }));
}
export function makeEnergy() {
  const to = 1793959200, from = to - 86400;
  const kinds = ["reply", "fatigue", "recovery", "sleep", "wake", "manual", "config"];
  let after = 76;
  const items = Array.from({ length: 23 }, (_, i) => {
    const kind = kinds[i % 7], delta = { reply: -4, fatigue: -4, recovery: 12, manual: 4 }[kind] || 0;
    const before = after - delta;
    const item = { id: `energy-${i + 1}`, at: to - i * 3600, kind, before_energy: before, after_energy: after,
      delta, before_state: "awake", after_state: ["awake", "nap", "groggy", "drowsy", "deep_sleep"][i % 5], reason: "合成持久事件，无聊天正文" };
    after = before;
    return item;
  });
  return { api_version: 1, window_start: from, window_end: to, timezone: "Asia/Shanghai", collected: true,
    points: items.map(item => ({ at: item.at, energy: item.after_energy })), items };
}
