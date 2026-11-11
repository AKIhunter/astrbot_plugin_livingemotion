"""Management DTOs. Authentication belongs to the product HTTP handlers."""

from __future__ import annotations

import inspect
import heapq
from dataclasses import fields, replace
from uuid import uuid4

from ..config import Config, LEGACY_FIELDS
from .config_help import field_help, field_parent
from .. import contracts
from ..contracts import BotAffect, Context, HumanObservation, SceneKind, to_dict
from ..domain.emotion import DIMENSIONS, EmotionPolicy, decay_affect
from ..domain.dreaming import six_emotions, apply_bonus, weather_bonus
from ..domain.relationship import relationship_stage_dto
from ..storage.console_data import (
    apply_relationship_override, context_dto, query_console_records, query_relationships,
    project_relationship_clues, query_scopes, selected_contexts, write_relationship_override,
)
from ..services.experience import dream_ready, dream_view
from .projector import account_affect, snapshot
from ..domain.proactivity import MOTIVES
from ..storage.proactivity import read_schedule


class ApplicationError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        self.status_code = {"validation_error": 400, "unauthorized": 401, "forbidden": 403,
                            "edit_disabled": 403, "version_conflict": 409,
                            "generation_in_progress": 409, "unavailable": 503}[code]
        super().__init__(message)

def behavior_transport_health(application, context):
    """A matching platform name alone does not prove a usable native route."""
    valid = False
    try:
        sender = application.behavior.sender
        valid = bool(context and sender._native_transport(
            application.bridge.source(context), context, context.route))
    except (ImportError, ValueError, AttributeError, TypeError):
        pass
    return {"name": "behavior_transport", "status": "ok" if valid else "degraded",
            "reason": ("QQ 原生路由已核验；取得消息编号才确认发送。" if valid else
                       "未核验到可确认的原生发送通道；发送结果可能未知。")}

def dimensions(value):
    return {"pleasure": (value.pleasure + 1) / 2, "arousal": value.arousal,
            "stress": value.stress, "social_need": value.social_need}


def _optional_int(value):
    """把「没传 / 空串 / 数字字符串」统一成 int 或 None，不接受其它形态。"""
    if value is None or value == "":
        return None
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ApplicationError("validation_error", "图片序号无效。")


def emotion_analysis(value: BotAffect):
    """仅从 BotAffect 数值派生展示指标，不写回状态，也不用于心理诊断。"""
    pleasure = max(-1.0, min(1.0, value.pleasure))
    arousal = max(0.0, min(1.0, value.arousal))
    stress = max(0.0, min(1.0, value.stress))
    social = max(0.0, min(1.0, value.social_need))
    positive = max(0.0, pleasure)
    negative = max(0.0, -pleasure)
    emotions = six_emotions(value)
    dimensions_ = {
        "valence": (pleasure + 1.0) / 2.0,
        "arousal": arousal,
        "stress": stress,
        "social_need": social,
        "control": max(0.0, min(1.0, 0.5 + pleasure * 0.25 - stress * 0.35)),
        "certainty": max(0.0, min(1.0, 0.75 - arousal * 0.2 - stress * 0.25)),
    }
    return {"emotions": emotions, "dimensions": dimensions_,
            "basis": "local_affect_heuristic", "kind": "heuristic",
            "note": "仅根据 BotAffect 数值计算的启发式状态指标，仅供软件展示；"
                    "情绪、控制感和确定感并非实测结果，不代表人的情绪，不是心理诊断"}


SETTINGS_GROUPS = (
    ("quick_start", "快速开始"), ("persona", "人格与状态模式"), ("emotion", "情绪"),
    ("relationship", "关系"), ("behavior", "主动行为"), ("night", "长夜"),
    ("experience", "日记与梦境"), ("memory", "记忆"),
)
FIELD_LABELS = {
    "enabled": "启用插件", "mode": "运行模式", "memory_mode": "旧版记忆模式",
    "memory_read": "允许读取记忆", "memory_export": "允许导出记忆",
    "autonomy_enabled": "允许主动找人", "group_autonomy_enabled": "允许群聊主动行为",
    "emotion_model_enabled": "模型辅助情绪分析", "dream_enabled": "生成梦境",
    "dream_theme_pool": "梦境主题池", "dream_owner_notify": "梦中惊醒给主人发消息",
    "dream_owner_qq": "主人QQ",
    "diary_enabled": "生成日记", "night_enabled": "启用作息记录",
    "night_block_chat": "旧版睡眠阻断聊天", "persona_mode": "人格选择方式",
    "persona_id": "原生人格", "timezone": "本地时区", "provider_id": "默认生成模型",
    "fallback_provider_id": "备用生成模型", "autonomy_scopes": "主动行为范围",
    "muted_scopes": "静默范围", "night_schedule_enabled": "自动作息",
    "sleep_at": "旧版入睡时间", "wake_at": "基础起床时间", "diary_at": "日记生成时间",
    "diary_backfill_yesterday": "补写昨天日记", "scheduler_seconds": "调度间隔",
    "dnd_start": "免打扰开始", "dnd_end": "免打扰结束", "active_start": "主动时段开始",
    "active_end": "主动时段结束", "behavior_daily_limit": "每日主动行为总额度",
    "behavior_scope_daily_limit": "每个会话每日主动额度",
    "behavior_cooldown_seconds": "主动行为冷却", "behavior_unanswered_limit": "未回应次数上限",
    "behavior_random_min_minutes": "随机等待最短时间",
    "behavior_random_max_minutes": "随机等待最长时间",
    "behavior_idle_minutes": "聊天结束后安静时间",
    "behavior_style": "主动节奏", "behavior_emotional_share": "允许分享心情",
    "behavior_provider_id": "主动聊天模型",
    "diary_retries": "日记重试次数", "dream_per_night": "每夜梦境上限",
    "diary_retention_days": "日记保留时间", "dream_retention_days": "梦境保留时间",
    "dream_half_life_seconds": "梦境清晰度半衰期", "experience_body_chars": "日记与梦境字数上限",
    "model_concurrency": "模型并发上限", "queue_size": "模型队列上限",
    "model_daily_limit": "每日模型调用上限", "emotion_interval_seconds": "情绪分析间隔",
    "model_input_tokens": "模型输入上限", "model_output_tokens": "模型输出上限",
    "model_timeout_seconds": "模型调用超时", "window_days": "聊天素材保留时间",
    "window_per_scope": "每个会话素材上限", "window_global": "全部素材上限",
    "body_max_chars": "单条素材字数上限", "event_days": "事件保留时间",
    "persona_shared_state": "同一人格共享状态", "night_policy_version": "睡眠规则版本",
    "allow_sleep": "允许TA睡眠", "nap_enabled": "启用午休", "nap_start": "午休开始",
    "nap_end": "午休结束", "fatigue_start": "夜间疲劳开始", "fatigue_end": "夜间疲劳结束",
    "deep_sleep_at": "沉睡时间", "lie_in_min_minutes": "最少赖床时间",
    "lie_in_max_minutes": "最多赖床时间", "wake_mode": "聊天唤醒方式",
    "wake_reply_limit": "唤醒回复轮数", "wake_window_minutes": "唤醒窗口",
    "energy_reply_cost": "每次回复精力消耗", "energy_fatigue_per_minute": "疲劳精力消耗速率",
    "energy_recovery_per_minute": "精力恢复速率", "catchup_enabled": "醒后阅读未读",
    "catchup_reply_enabled": "醒后历史补答", "closing_enabled": "睡前晚安",
    "closing_random": "道别语随机生成", "closing_lead_minutes": "晚安提前量",
    "diary_provider_id": "日记模型", "dream_provider_id": "梦境模型",
    "catchup_provider_id": "补课模型", "closing_provider_id": "收尾模型",
    "home_city": "Bot住所城市", "embedding_provider_id": "向量模型",
    "livingmemory_enabled": "使用LivingMemory", "memory_write": "允许写入记忆",
    "relationship_stage_names": "关系阶段自定义名称",
    "relationship_stage_descriptions": "关系阶段描述",
    "relationship_special_description": "独特关系说明",
    "relationship_edit_enabled": "允许在关系页修改好感",
    "wake_autocatchup_enabled": "自然醒后主动补答",
    "wake_greeting_enabled": "先发一句刚醒的招呼",
    "wake_greeting_texts": "刚醒招呼候选句子",
    "wake_autocatchup_enabled": "自然醒后主动补答",
    "wake_greeting_enabled": "先发一句刚醒的招呼",
    "wake_greeting_texts": "刚醒招呼候选句子",
    "autonomy_qq_ids": "主动私聊 QQ 号码", "autonomy_qq_group_ids": "主动发言 QQ 群号",
}


def field_section(name):
    if name in ("enabled", "mode", "timezone", "provider_id", "fallback_provider_id"):
        return "quick_start"
    for prefixes, group in (
            (("persona",), "persona"), (("memory", "livingmemory", "embedding", "window", "body",
                                        "event_days"), "memory"),
            (("night", "sleep", "wake", "nap", "fatigue", "deep_sleep", "lie_in", "energy",
              "allow_sleep", "catchup", "closing"), "night"),
            (("diary", "dream", "experience", "home_city"), "experience"),
            (("autonomy", "group", "behavior", "dnd", "active", "muted"), "behavior"),
            (("relationship",), "relationship")):
        if name.startswith(prefixes):
            return group
    return "emotion"


def night_display_state(night):
    display = getattr(night, "display_state", None)
    if display is not None:
        return getattr(display, "value", display)
    return {"awake": "awake", "drowsy": "groggy", "settling": "drowsy",
            "asleep": "deep_sleep", "waking": "groggy"}.get(night.phase.value, "awake")


EXPERIENCE_ACTION_REASONS = {
    "generation_disabled": "插件尚未启用，无法生成。",
    "observe_only": "当前为仅观察模式，无法生成。",
    "source_unavailable": "当前来源不支持生成，请选择有效的私聊或群聊。",
    "context_changed": "这个会话当前没有实时消息来源（插件重启后要等它先来一条消息），或来源刚发生变化。先在那个会话里发一句，再回来重试。",
    "diary_disabled": "请先启用日记生成。",
    "dream_disabled": "请先启用梦境生成。",
    "dream_requires_live_rem": "自动做梦要等睡着并睡够一小时；手动触发不受这个限制。",
    "model_unavailable": "当前用途的生成模型不可用，请检查模型配置。",
    "provider_budget_contract_unavailable": "当前用途没有可用且支持预算约束的模型。",
    "provider_budget_contract_unsupported": "当前用途的模型不支持所需预算约束。",
}

# 状态原因码只用于诊断，页面展示一律用中文解释，避免把 time_decay 这类
# 内部标识直接抛给使用者。
AFFECT_REASON_TEXT = {
    "time_decay": "没有新的互动刺激，情绪随时间自然回落到基准。",
    "appraisal_concern": "依据最近对话里出现的关切线索更新了情绪。",
    "similar_stimulus_limited": "同类刺激短时间内重复出现，本次只做有限调整。",
    "disabled": "情绪细化模型未启用，仅使用本地数值启发式。",
}
AFFECT_REASON_FALLBACK = "由本地情绪模型按最近的真实互动更新。"

MODE_REASON_TEXT = {
    "active": "参与表达与行动：可生成内容并按规则自主发送。",
    "observe_only": "仅观察：只记录状态，不主动发送。",
    "disabled": "插件未启用或已停止，所有自动行为暂停。",
    "ownership_conflict": "检测到其他情感插件占用了当前范围，已退让为仅观察。",
    "config_observe_only": "原生配置中的运行模式是「仅观察」，请在设置中改为「参与表达与行动」。",
}

# 同一状态（rejected/skipped）下面原因差别很大，按原因码给一句准话。
EXPERIENCE_REASON_TEXT = {
    "input_token_limit": "素材比模型输入上限多，已自动压缩；若仍失败请在设置里调大输入上限。",
    "input_budget_too_small": "模型输入上限太小，装不下系统提示与人格；请到设置里调大「模型输入上限」。",
    "no_qualified_material": "这一天没有可用素材：素材为空、超出窗口，或可见范围已变。",
    "experience_attempt_limit": "本次配额已用完，稍后再试或调整上限。",
    "dream_requires_live_rem": "自动做梦要等睡着并睡够；手动触发不受限制。",
    "model_unavailable": "模型不可用：检查主动/日记模型是否已配置、上游是否限流。",
    "source_unavailable": "当前来源不支持生成（如公开评论区）。",
    "context_changed": "会话状态在生成期间被重置，可重试。",
    "generation_disabled": "该类型生成已在设置里关闭。",
    "experience_exists": "这一天的内容已经存在，不重复生成。",
}

EXPERIENCE_TASK_TEXT = {
    "idle": "尚未触发：还没有手动生成，也没到自动计划时间。",
    "queued": "已排队：正在后台生成，稍后刷新查看结果。",
    "succeeded": "已完成：内容已保存，可在下方记录里阅读。",
    "skipped": "已跳过：本次条件不满足，详见下方原因。",
    "rejected": "已拒绝：来源或权限校验未通过。",
    "unavailable": "暂不可用：缺少模型或依赖，详见下方原因。",
    "failed": "失败：生成过程出错，未保存内容。",
    "unknown": "结果不明：请核对记录，不要重复生成。",
}


def affect_reason_text(reason_codes) -> str:
    """把内部状态原因码翻译成一句人话，保留诊断码本身不展示。"""
    codes = [code for code in reason_codes if isinstance(code, str)]
    texts = [AFFECT_REASON_TEXT[code] for code in codes if code in AFFECT_REASON_TEXT]
    return " ".join(dict.fromkeys(texts)) or AFFECT_REASON_FALLBACK


NIGHT_REASON_TEXT = {
    "fatigue": "处于疲惫时段，精力在下降。",
    "recovery": "正在恢复精力。",
    "manual_wake": "由管理端手动叫醒。",
    "manual": "由管理端手动调整作息。",
    "timeline": "按当前作息时间表推进。",
    "clock_rollback": "检测到系统时间回拨，已暂停结算。",
}


def night_reason_text(reason_codes) -> str:
    codes = [reason_codes] if isinstance(reason_codes, str) else [
        code for code in (reason_codes or ()) if isinstance(code, str)]
    texts = [NIGHT_REASON_TEXT[code] for code in codes if code in NIGHT_REASON_TEXT]
    return " ".join(dict.fromkeys(texts))


BEHAVIOR_REASON_TEXT = {
    "autonomy_disabled": "未开启「允许主动找人」。",
    "group_disabled": "群聊主动行为未开启。",
    "scope_not_allowed": "当前范围不在允许联系的名单内。",
    "muted_scope": "当前范围已被静音。",
    "do_not_disturb": "处于免打扰时段。",
    "outside_active_hours": "不在允许主动联系的时间段内。",
    "sleeping": "TA 正在睡觉或刚醒，先不打扰。",
    "low_energy": "精力过低，需要先休息。",
    "cooldown": "仍在冷却时间内。",
    "global_quota_exhausted": "今天主动说话的总额度已用完。",
    "scope_quota_exhausted": "这个会话今天的额度已用完。",
    "unanswered_backoff": "对方几次没回应，已主动放慢节奏。",
    "below_score_threshold": "当前时机分数不足，先不打扰。",
    "unverified_route": "会话路由未验证，不能发送。",
    "relationship_boundary_changed": "关系边界已变化，本次不分享情绪。",
    "context_changed": "会话范围已变化，请刷新。",
    "identity_invalid": "身份校验未通过。",
    "unavailable": "当前不可用（模式或睡眠限制）。",
    "behavior_history_unavailable": "缺少今日行为额度记录。",
    "behavior_dependency_unavailable": "主动行为依赖尚未就绪。",
    "new_human_message": "期间有新消息，本次跳过。",
    "stale_generation": "会话已更新，本次作废。",
    "expired_intent": "这次意图已过期。",
    "eligible": "全部条件满足，可以开口。",
    "random_wait": "正在等一个自然的时机。",
    "checking": "正在想要不要开口。",
    "random_skip": "这次先安静陪着。",
    "conversation_active": "还在聊天，先不插话。",
    "missed_opportunity": "错过的时机已跳过。",
    "opportunity_interrupted": "上次检查中断，已停止旧任务。",
    "opportunity_timeout": "这次检查超时，先停下来。",
    "select_scene": "选择私聊或群聊后查看具体节奏。",
    "scheduler_delayed": "调度出现延迟。",
    "queued": "已排队执行。",
}


def behavior_reason_texts(value) -> list[str]:
    codes = [value] if isinstance(value, str) else [
        code for code in (value or ()) if isinstance(code, str)]
    texts = [BEHAVIOR_REASON_TEXT[code] for code in codes if code in BEHAVIOR_REASON_TEXT]
    return list(dict.fromkeys(texts)) or ["当前条件未满足，原因码见下方诊断。"]


ACTION_REASON_TEXT = {
    "night.sleep": "当前模式不允许手动入睡，请把运行模式改为参与表达与行动。",
    "night.wake": "插件未启用或睡眠功能关闭。",
    "behavior.send": "当前条件不满足主动发送要求，先看行为模拟的判定。",
    "diary.generate": "日记生成条件未满足，详见原因。",
    "dream.generate": "梦境生成条件未满足，详见原因。",
}


class Console:
    @property
    def config_revision(self):
        # 配置版本只随配置内容变化；插件重载仍使用 revision 使旧行动失效。
        return contracts.stable_key(to_dict(self.config))

    async def _experience_action(self, context, kind, night):
        # 梦境手动生成是强制指令：除了「梦境生成」开关，不因睡眠、REM、夜间
        # 窗口或额度把按钮置灰。日记的既有判定保持不变。
        if kind == "dream" and not self.config.dream_enabled:
            return {"id": "dream.generate", "enabled": False, "reason_code": "dream_disabled",
                    "reason": EXPERIENCE_ACTION_REASONS["dream_disabled"], "context_id": ""}
        code = ""
        try:
            await self.manual_persona()
            await self.manual_model_binding(kind)
            if getattr(self, "manual_experience", None) is None or self.manual_experience.closed:
                code = "executor_stopped"
            else:
                value = await self.manual_experience_state()
                if value[kind].get("status") in ("queued", "running"):
                    code = "generating"
        except (ValueError, ImportError, AttributeError):
            code = "model_or_persona_unavailable"
        reasons = {"executor_stopped": "手动执行器已停止，请重新连接插件。",
                   "generating": "正在生成，完成后可以再次重写。",
                   "model_or_persona_unavailable": "请配置可用的原生人格和日记/梦境模型。"}
        return {"id": kind + ".generate", "enabled": not code, "reason_code": code,
                "reason": reasons.get(code, ""), "context_id": ""}

    async def _attach_manual_experience(self, state):
        try:
            value = await self.manual_experience_state()
            state["experience"].update(value)
            state["experience"]["reason"] = ("按当前人格保存。手动生成不看作息、睡眠阶段和每日额度，"
                                             "但需要先在设置里开启对应类型的生成。")
            if not state.get("persona"):
                state["persona"] = {"id": value["persona_id"], "name": value["persona_id"]}
        except Exception:
            state["experience"].update(persona_id="", reason="原生人格不可用，请检查设置。")
        state["actions"] = [a for a in state["actions"] if a["id"] not in ("diary.generate", "dream.generate")]
        state["actions"].extend([await self._experience_action(None, kind, None) for kind in ("diary", "dream")])

    def _context(self, context_id, *, optional=False):
        if not isinstance(context_id, str) or len(context_id) > 128:
            raise ApplicationError("validation_error", "Invalid context")
        if not context_id and optional:
            return next(reversed(self._contexts.values()), None)
        context = self._contexts.get(context_id)
        if context is None:
            raise ApplicationError("validation_error", "Unknown context")
        return context

    def _open(self):
        if self.closed:
            raise ApplicationError("unavailable", "Plugin stopped")

    @staticmethod
    def _actor(actor_id, reason):
        if (not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 512
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000):
            raise ApplicationError("validation_error", "An authenticated actor and reason are required")

    def config_dto(self, options=None):
        enums = {"mode": ["active", "observe_only"], "memory_mode": ["none", "local_lite", "external"],
                 "persona_mode": ["follow", "explicit", "none"], "wake_mode": ["chat", "never", "both"],
                 "behavior_style": ["gentle", "balanced", "lively"]}
        enum_labels = {"active": "正常运行", "observe_only": "仅观察", "none": "不使用",
                       "local_lite": "旧版本地记录", "external": "外部记忆",
                       "follow": "跟随会话人格", "explicit": "指定人格",
                       "chat": "仅私聊", "never": "不允许聊天唤醒", "both": "私聊或群原生@Bot",
                       "gentle": "轻柔", "balanced": "自然", "lively": "活泼"}
        values = to_dict(self.config)
        values = {key: value for key, value in values.items() if key not in LEGACY_FIELDS}
        options = options or {}
        result_fields = []
        for f in fields(Config):
            if f.name in LEGACY_FIELDS:
                continue
            item = {"key": f.name, "label": FIELD_LABELS.get(f.name, "高级设置：" + f.name),
                    "section": field_section(f.name), "value": values[f.name],
                    "type": ("enum" if f.name in enums else "boolean" if type(f.default) is bool
                             else "integer" if type(f.default) is int
                             else "float" if type(f.default) is float else "string"),
                    "advanced": f.name.startswith(("model_", "window_", "body_", "event_"))
                    or f.name == "scheduler_seconds"}
            parent, level = field_parent(f.name)
            item.update(field_help(f.name), parent=parent, level=level)
            if f.name in enums:
                item["options"] = [{"value": v, "label": enum_labels[v]} for v in enums[f.name]]
            if type(f.default) in (int, float):
                unit = ("秒" if f.name.endswith("_seconds") else
                        "分钟" if "minutes" in f.name else "天" if f.name.endswith("_days") else
                        "Token" if f.name.endswith("_tokens") else
                        "点/分钟" if f.name.endswith("_per_minute") else
                        "点/次" if f.name == "energy_reply_cost" else "次")
                item.update(step=0.1 if type(f.default) is float else 1, unit=unit)
            if f.name.endswith("provider_id"):
                kind = "embedding" if f.name == "embedding_provider_id" else "chat"
                item.update(type="enum", provider_kind=kind, options=[
                    {"value": "", "label": "未配置" if kind == "embedding" else "跟随当前聊天模型"},
                    *options.get(kind + "_providers", [])])
            if f.name == "persona_id":
                item["type"] = "enum"
                item["options"] = options.get("personas", [])
            if f.name in ("behavior_random_min_minutes", "behavior_random_max_minutes",
                          "behavior_idle_minutes"):
                item.update(min=1, max=1440 if f.name == "behavior_idle_minutes" else 10080)
            result_fields.append(item)
        return {
            "revision": self.config_revision, "source": "AstrBot native plugin configuration",
            "values": values, "fields": result_fields,
            "groups": self._settings_groups(),
            "readonly": [{"key": "energy_max", "label": "总精力", "type": "float",
                          "value": 100.0, "step": 0.1, "unit": "点", "readonly": True,
                          "section": "night", "parent": "night_schedule_enabled", "level": 1,
                          **field_help("energy_max")}],
        }

    @staticmethod
    def _settings_groups():
        quick = {"enabled", "mode", "timezone", "provider_id", "fallback_provider_id", "home_city"}
        return [{"id": group, "label": label,
                 "field_keys": [f.name for f in fields(Config)
                                if f.name not in LEGACY_FIELDS and
                                (f.name in quick if group == "quick_start"
                                    else field_section(f.name) == group)]}
                for group, label in SETTINGS_GROUPS]

    async def _selection(self, persona_id, view_scope, context_id, platform):
        selection = {"persona_id": persona_id, "view_scope": view_scope or "global",
                     "context_id": context_id, "platform": platform}
        if not persona_id or selection["view_scope"] not in ("global", "private", "group"):
            raise ApplicationError("validation_error", "A persona and valid view scope are required")
        try:
            contexts = await selected_contexts(self.store, self.instance_id, selection)
        except ValueError:
            raise ApplicationError("validation_error", "Unknown or mismatched scope") from None
        cls = getattr(contracts, "ScopeSelection", None)
        if cls is not None:
            # The wire ID stays opaque. Older P1 contracts call the real scene
            # selector scene_id; never pass an account_key as a scene identifier.
            names = {f.name for f in fields(cls)}
            values = {"persona_id": persona_id, "view_scope": selection["view_scope"],
                      "platform": platform or None}
            if "context_id" in names:
                values["context_id"] = context_id or None
            elif "scene_id" in names:
                values["scene_id"] = contexts[0].scene_id if context_id and contexts else None
            try:
                cls(**values)
            except (TypeError, ValueError):
                raise ApplicationError("validation_error", "Invalid scope selection") from None
        return selection, contexts

    async def console_configuration(self, context_id="", persona_id="", view_scope="", platform=""):
        """保存预读只返回配置，避开天气、图表、记录与模型选项查询。"""
        self._open()
        await self.refresh_config()
        if persona_id or view_scope or platform:
            await self._selection(persona_id, view_scope, context_id, platform)
        else:
            self._context(context_id, optional=True)
        return {"api_version": 1, "config": self.config_dto()}

    async def console_state(self, context_id="", persona_id="", view_scope="", platform=""):
        self._open()
        await self.refresh_config()
        selection = None
        if persona_id or view_scope or platform:
            selection, contexts = await self._selection(persona_id, view_scope, context_id, platform)
            persisted = contexts[0] if contexts else None
            context = self._contexts.get(persisted.account_key, persisted) if persisted else None
        else:
            context = self._context(context_id, optional=True)
        global_view = bool(selection and selection["view_scope"] == "global")
        memory = self.memory.capabilities()
        settings_options = await self.console_settings_options()
        effective = self.effective_mode(context)
        ownership_conflict = bool(context is not None and self.bridge.conflicts(context))
        mode_reason = ("ownership_conflict" if ownership_conflict and effective == "observe_only"
                       else effective if effective in MODE_REASON_TEXT else "disabled")
        # 「有实时来源的会话」才允许写动作。注意不能只看 _contexts：启动时
        # 会从库里回填上下文，那些会话没有实时来源，点下去必然 context_changed。
        live = getattr(self, "is_live_context", None)
        live_ok = (live(context) if callable(live)
                   else context is not None and context.account_key in self._contexts)
        action_context_id = context.account_key if context is not None and live_ok else ""
        from .feeling import feeling_state
        from .environment import environment_state
        state = {
            "environment": await environment_state(self),
            "feeling": await feeling_state(self, persona_id or (context.persona_id if context else "")),
            "api_version": 1, "context_id": context.account_key if context else "",
            # 动作落点：全局视图的 context_id 按约定留空，页面用这里交代的会话
            # 提交动作请求；只有进程内真实存在的会话才给落点（重启后从
            # source_contexts 读出的历史会话没有实时来源，动作必然失败）。
            "action_target": ({
                "context_id": action_context_id,
                # 带上范围与平台：页面可以直接切到该会话，不必先等 scopes。
                "view_scope": context.scene_kind.value,
                "platform": context.platform,
                "label": (f"{context.platform} / {context.scene_kind.value} / "
                          f"{context.scene_id} / {context.account_id}"),
            } if action_context_id else None),
            "contexts": [{"id": c.account_key,
                          "label": f"{c.platform} / {c.scene_kind.value} / {c.scene_id} / {c.account_id}"}
                         for c in reversed(self._contexts.values())],
            "updated_at": self.store.clock(), "mode": effective,
            "mode_detail": {"effective": effective, "configured": self.config.mode,
                            "reason": mode_reason,
                            "reason_text": MODE_REASON_TEXT.get(mode_reason, "")},
            "revision": self.revision, "config": self.config_dto(settings_options),
            "emotion_model_analysis": (self.emotion_model_analysis(
                contexts if selection else [context] if context else [])
                if hasattr(self, "emotion_model_analysis") else
                {"status": "uncollected", "reason_code": "uncollected", "applied": False}),
            "behavior_model": (await self.model_preflight(context, "behavior")
                               if context and hasattr(self, "model_preflight") else
                               {"available": False, "reason_code": "source_invalid"}),
            "selection": selection,
            "state_mode": "persona" if getattr(self.config, "persona_shared_state", False) else "scene",
            "capabilities": ["config.write", "configuration.read", "config.receipt", "behavior.preview", "scopes.read", "relationships.read",
                             "relationship.write", "energy.read", "settings-options.read",
                             "memory.sync"],
            "health": [
                {"name": "runtime", "status": "ok" if self.config.enabled else "unavailable",
                 "reason": "ready" if self.config.enabled else "disabled"},
                {"name": "configuration", "status": "degraded" if self._config_fault else "ok",
                 "reason": "invalid_native_config" if self._config_fault else "native"},
                {"name": "ownership", "status": "degraded" if ownership_conflict else "ok",
                 "reason": "congling_scope_conflict" if ownership_conflict else "exclusive"},
                {"name": "background", "status": "degraded" if self._task_fault else "ok",
                 "reason": self._task_fault or "idle"},
                {"name": "reply_confirmation", "status": "unavailable",
                 "reason": "unsupported：当前宿主无可靠回复确认；收尾 120 秒超时取消，"
                           "不将 after-sent/bool/None 视为发送成功。"},
                behavior_transport_health(self, context),
            ],
            "memory": await self._memory_dto(context),
            "experience": {"diary_enabled": self.config.diary_enabled,
                           "dream_enabled": self.config.dream_enabled,
                           # 任务状态：全局视图下动作本来就落在「最近会话」，
                           # 状态却藏着不给会逼用户切会话。这里统一给出，
                           # 由前端标注这是哪个会话的任务。
                           "diary": (self._experience_dto(context, "diary", detail=not global_view)
                                     if context and hasattr(self, "experience_status") else None),
                           "dream": (self._experience_dto(context, "dream", detail=not global_view)
                                     if context and hasattr(self, "experience_status") else None),
                           "scope_global": global_view,
                           "reason": "仅在明确启用后生成，不会为了填满页面而编造内容。"},
            "actions": [],
        }
        if selection is not None:
            state["contexts"] = [context_dto(c) for c in contexts]
        if context is None:
            await self._attach_manual_experience(state)
            await self._attach_emotion_curve(state, None)
            return state
        owned_state = getattr(self.store, "get_owned_state", None)
        bot_record = (await owned_state(context, "bot") if callable(owned_state)
                      else await self.store.get_state(context, "bot"))
        policy = getattr(self, "emotion_policy", EmotionPolicy())
        if callable(policy):
            policy = policy()
        bot = decay_affect(snapshot(bot_record, BotAffect), now=self.store.clock(), policy=policy)
        baseline = policy.baseline
        baseline = (dimensions(baseline) if isinstance(baseline, BotAffect)
                    else dimensions(BotAffect(**dict(zip(DIMENSIONS, baseline)))))
        obs_record = (await self.store.get_state(context, "observation", context.account_id)
                      if not global_view else None)
        obs = snapshot(obs_record, HumanObservation) if obs_record else None
        generation = await self.store.get_generation(context)
        relation = await self.current_relationship(context) if not global_view else None
        night = await self.night_snapshot(context)
        night_record = await self.store.get_state(context, "night")
        catchup_runtime = dict(((night_record.value or {}).get("_runtime") or {}).get("catchup") or {}) if night_record else {}
        availability = await self.availability(context)
        source = self.bridge.source(context) if not global_view else None
        preview = await self.behavior.preview_behavior(context)
        schedule = await read_schedule(self.store, context)
        behavior_history = (await self.behavior_history(context, self.store_period(), None)
                            if hasattr(self, "behavior_history") else None)
        behavior_ready = False
        try:
            await self._purpose_binding(context, "behavior")
            behavior_ready = True
        except (ValueError, ImportError, AttributeError):
            pass
        if schedule and self.config.autonomy_enabled and preview.eligible:
            stalled = (self.store.clock() - schedule["checked_at"]
                       > max(300, self.config.scheduler_seconds * 3))
            stuck = (schedule["last_outcome"] == "running"
                     and self.store.clock() >= schedule.get("deadline", float("inf")))
            state["health"].append({
                "name": "主动调度", "status": "degraded" if stalled or stuck else "ok",
                "reason": "opportunity_interrupted" if stuck else "scheduler_delayed" if stalled else "ready",
            })
        # 全局视图也要给出生成动作：它仍然绑定一个具体会话（最近使用的那个），
        # 否则页面只能显示「宿主未开放此操作」，用户看到的就是「开关开了却按不了」。
        experience_actions = ([await self._experience_action(context, kind, night)
                               for kind in ("diary", "dream")] if context is not None else [])
        active = self.effective_mode(context) == "active" and context.scene_kind != SceneKind.PUBLIC_COMMENT
        if relation is not None and not await self.validate_context(context, generation):
            relation = None
        if relation is not None:
            relation = await apply_relationship_override(self.store, context, relation)
        personal = None
        personal_record = None
        if not global_view and context.account_id:
            personal_record = await self.store.get_state(context, "relationship", context.account_id)
            if personal_record is not None and personal_record.generation == generation:
                personal = account_affect(personal_record, context)
            if personal is not None and (
                not await self.validate_context(context, generation)
                or await self.store.get_generation(context) != generation
            ):
                personal = None
        personal_state = (decay_affect(personal[0], now=self.store.clock(), policy=policy)
                          if personal else None)
        state.update({
            "user_emotion": ({
                "subject": context.account_id, "context_id": context.account_key,
                "scope_kind": "account", "source": "local_account_interactions",
                "label": ", ".join(personal_state.labels),
                "dimensions": dimensions(personal_state), "baseline": baseline,
                "emotion_analysis": emotion_analysis(personal_state),
                "reason": ", ".join(personal_state.reason_codes),
                "updated_at": personal[0].updated_at,
                "version": personal_record.version,
            } if personal_state else None),
            "persona": {"id": context.persona_id, "name": context.persona_id,
                        "source": "AstrBot native", "revision": context.persona_revision,
                        "description": source.persona.prompt if source else "",
                        "description_available": bool(source and source.persona.prompt)},
            "bot_state": {"dimensions": dimensions(bot), "baseline": baseline,
                          "label": ", ".join(bot.labels),
                          "emotion_analysis": emotion_analysis(bot),
                          "reason": affect_reason_text(bot.reason_codes),
                          "reason_codes": list(bot.reason_codes),
                          "updated_at": bot.updated_at,
                          "version": bot_record.version if bot_record else 0, "source": "livingEmotion"},
            "observation": ({"subject": obs.subject_id, "label": ", ".join(obs.labels),
                             "emotion_analysis": {"labels": list(obs.labels),
                                                  "confidence": obs.confidence,
                                                  "basis": "observed_human_signal",
                                                  "kind": "heuristic",
                                                  "note": "仅展示已记录的人类观测标签与置信度，"
                                                          "不补推其他情绪，不是心理诊断"},
                             "confidence": obs.confidence, "observed_at": obs.occurred_at,
                             "expires_at": obs.expires_at, "source": "human observation"}
                            if obs and obs.expires_at > self.store.clock() else None),
            "emotion_analysis": {"bot": emotion_analysis(bot),
                                 "human": ({"labels": list(obs.labels),
                                            "confidence": obs.confidence,
                                            "basis": "observed_human_signal",
                                            "kind": "heuristic",
                                            "note": "仅展示已记录的人类观测标签与置信度，"
                                                    "不补推其他情绪，不是心理诊断"}
                                           if obs and obs.expires_at > self.store.clock() else {})},
            "relationship": ({**relationship_stage_dto(relation.score, self.config),
                             "raw": relation.score, "score": round(relation.score / 10, 1),
                             "normalized": relation.normalized, "scale": "0-1000",
                             "source_completeness": "complete" if relation.evidence_complete else "partial",
                             "identity_revision": context.identity_revision,
                             "reason": ", ".join(relation.reason_codes)}
                             if relation is not None else None),
            "availability": {"available": availability.available, "state": night.phase.value,
                             "display_state": night_display_state(night),
                             "block_chat": availability.block_chat,
                             "reasons": list(availability.reason_codes)},
            "night": {"state": night.phase.value, "stage": night.sleep_stage,
                      "display_state": night_display_state(night),
                      "energy": night.energy / 100, "energy_percent": night.energy,
                      "energy_max": 100, "sleep_at": night.sleep_started_at,
                      "wake_at": night.wake_at,
                      "cycle_started_at": night.cycle_started_at,
                      "drowsy_at": night.drowsy_at, "deep_sleep_at": night.deep_sleep_at,
                      "base_wake_at": night.base_wake_at,
                      "cycle_kind": night.cycle_kind, "lie_in_minutes": night.lie_in_minutes,
                      "reason": night_reason_text(night.reason_codes),
                      "schedule": {
                          "schedule_enabled": bool(self.config.night_schedule_enabled),
                          "sleep_enabled": bool(self.config.night_enabled),
                          "allow_sleep": bool(self.config.allow_sleep),
                          "fatigue_start": self.config.fatigue_start,
                          "fatigue_end": self.config.fatigue_end,
                          "deep_sleep_at": self.config.deep_sleep_at,
                          "wake_at": self.config.wake_at,
                          "nap_enabled": bool(self.config.nap_enabled),
                          "nap_start": self.config.nap_start, "nap_end": self.config.nap_end,
                          "lie_in_min": self.config.lie_in_min_minutes,
                          "lie_in_max": self.config.lie_in_max_minutes,
                          "wake_mode": self.config.wake_mode,
                          "wake_reply_limit": self.config.wake_reply_limit,
                          "wake_window_minutes": self.config.wake_window_minutes,
                          "catchup_enabled": bool(self.config.catchup_enabled),
                          "catchup_reply_enabled": bool(self.config.catchup_reply_enabled),
                          "timezone": self.config.timezone,
                      },
                      "catch_up": {
                          "enabled": bool(self.config.catchup_enabled),
                          "reply_enabled": bool(self.config.catchup_reply_enabled),
                          "completed": catchup_runtime.get("completed", 0),
                          "total": catchup_runtime.get("total", 0),
                          "reason": catchup_runtime.get("reason", ""),
                      }},
            "behavior": {
                "enabled": self.config.autonomy_enabled,
                "reason": ", ".join(behavior_reason_texts(getattr(preview, "reason_codes", ()))),
                "reason_codes": list(getattr(preview, "reason_codes", ())),
                "eligible": bool(getattr(preview, "eligible", False)),
                "score": getattr(preview, "score", None),
                "min_score": self._behavior_min_score(),
                "reasons": list(getattr(preview, "reason_codes", ())),
                "candidates": [],
                "scope_key": context.scope_key,
                "remaining": (max(0, min(
                    self.config.behavior_daily_limit - behavior_history.global_used,
                    self.config.behavior_scope_daily_limit - behavior_history.scope_used,
                )) if behavior_history else None),
                "daily_used": (behavior_history.global_used if behavior_history else None),
                "scope_used": (behavior_history.scope_used if behavior_history else None),
                "backoff": (behavior_history.unanswered_count if behavior_history else None),
                "next_check_at": (schedule or {}).get("next_at"),
                "last_check_at": (schedule or {}).get("checked_at"),
                "last_outcome": (schedule or {}).get("last_outcome", "waiting"),
                "last_reason": (schedule or {}).get("last_reason", "random_wait"),
                "last_reason_text": behavior_reason_texts((schedule or {}).get("last_reason", "random_wait")),
                "last_motive": MOTIVES.get((schedule or {}).get("last_mode"), ("尚未开口", ""))[0],
                "random_interval": [self.config.behavior_random_min_minutes,
                                    self.config.behavior_random_max_minutes],
                "config": {name: getattr(self.config, name) for name in (
                    "enabled", "mode", "timezone", "scheduler_seconds",
                    "provider_id", "fallback_provider_id", "autonomy_scopes",
                    "autonomy_enabled", "group_autonomy_enabled", "autonomy_qq_ids",
                    "autonomy_qq_group_ids", "muted_scopes", "behavior_style",
                    "behavior_provider_id", "behavior_daily_limit", "behavior_scope_daily_limit",
                    "behavior_cooldown_seconds", "behavior_unanswered_limit",
                    "behavior_random_min_minutes", "behavior_random_max_minutes",
                    "behavior_idle_minutes", "behavior_emotional_share", "active_start",
                    "active_end", "dnd_start", "dnd_end",
                )},
                "style": self.config.behavior_style,
                "model_ready": behavior_ready,
                "cooldown_until": (max(
                    (behavior_history.last_attempt_at or 0) + self.config.behavior_cooldown_seconds
                    if behavior_history.last_attempt_at is not None else 0,
                    behavior_history.cooldown_until or 0,
                ) or None) if behavior_history else None,
                "motives": [label for label, _ in MOTIVES.values()],
            },
            "actions": [
                {"id": name, "enabled": enabled, "context_id": action_context_id,
                 "reason": "" if enabled else (ACTION_REASON_TEXT.get(name, "当前模式、模型或策略不允许此操作。")
                                               if state.get("mode") == "active"
                                               else MODE_REASON_TEXT.get(mode_reason, "")),
                 "reason_code": "" if enabled else ("mode_unavailable" if state.get("mode") != "active"
                                                    else "policy_unavailable")}
                for name, enabled in (
                    ("night.sleep", active and self.config.night_enabled),
                    ("night.wake", self.config.enabled and self.config.night_enabled),
                    # 真实发送由管理员显式触发：手动路径跳过时机分数、冷却与未回应
                    # 退避，其余硬约束（静音、时段、额度、身份、来源）照旧；模型是否
                    # 可用在执行时反馈，不再把按钮直接锁死。
                    ("behavior.send", active),
                )
            ] + experience_actions,
        })
        if global_view:
            # 全局视图不合并任何具体会话的内容，但动作仍然需要一个落点：
            # 每个动作自带 action_target 的 context_id，页面按它提交，
            # 不会出现「按钮能点、请求却被判 Unknown context」。
            state["representative_context_id"] = action_context_id
            state["context_id"] = ""
            state["observation"] = None
            state["emotion_analysis"]["human"] = {}
            state["relationship"] = None
            state["persona"].update(revision="")
            state["behavior"].update(
                scope_key="", next_check_at=None, last_check_at=None, remaining=None,
                cooldown_until=None, backoff=None, last_outcome="waiting", reason="",
                reason_codes=[], reasons=[], eligible=None, score=None,
                last_reason="select_scene", last_reason_text=behavior_reason_texts("select_scene"),
                last_motive="全局人格视图",
            )
            state["availability"]["reasons"] = []
            state["health"] = [item for item in state["health"] if item["name"] != "主动调度"]
            # 标签与曲线统一取同一份真实状态；拆分模式使用最近活跃会话投影。
            shared_state = bool(getattr(self.config, "persona_shared_state", False))
            state["bot_state"].update(
                label=state["bot_state"]["label"],
                reason=("这是私聊与群聊共享的人格情绪，不绑定具体会话。" if shared_state else
                        "当前展示最近活跃会话的人格状态，数值与曲线使用同一份状态。"),
                reason_codes=[], global_view=True,
            )
        await self._attach_manual_experience(state)
        await self._attach_emotion_curve(state, context)
        return state

    async def _attach_emotion_curve(self, state, context):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        zone = self.config.timezone or "Asia/Shanghai"
        now = self.store.clock()
        end = int(now // 300) * 300
        points = (await self.store.emotion_history(context, since=now - 86400, until=now)
                  if context else [{"at": at, "emotions": None, "basis": "uncollected"}
                      for at in range(end - 86100, end + 1, 300)])
        reports = {}
        weather = getattr(self, "_manual_weather", None)
        city = self.config.home_city
        days = {datetime.fromtimestamp(now, ZoneInfo(zone)).date().isoformat()}
        days.update(datetime.fromtimestamp(p["at"], ZoneInfo(zone)).date().isoformat() for p in points)
        for day in days:
            if weather and city:
                reports[day] = await weather.get(city, day, zone)
        current_day = datetime.fromtimestamp(now, ZoneInfo(zone)).date().isoformat()
        bonus = weather_bonus(reports.get(current_day), city=city, day=current_day, timezone=zone)
        for target in (state.get("emotion_analysis", {}).get("bot"),
                       state.get("bot_state", {}).get("emotion_analysis")):
            if target:
                target["emotions"] = apply_bonus(target["emotions"], bonus)
                target["weather_bonus"] = bonus
        current_emotions = state.get("emotion_analysis", {}).get("bot", {}).get("emotions", {})
        if any(bonus.values()) and current_emotions:
            dominant = max(current_emotions, key=current_emotions.get)
            state["bot_state"]["label"] = ({
                "joy": "happy", "anger": "angry", "sadness": "sad",
                "fear": "anxious", "surprise": "excited", "affection": "caring",
            }[dominant] if current_emotions[dominant] >= .25 else "calm")
        for point in points:
            if point["emotions"] is not None:
                day = datetime.fromtimestamp(point["at"], ZoneInfo(zone)).date().isoformat()
                point["emotions"] = apply_bonus(point["emotions"], weather_bonus(
                    reports.get(day), city=city, day=day, timezone=zone))
        state["emotion_curve"] = {"points": points, "interval_seconds": 300,
            "window_start": now - 86400, "window_end": now, "timezone": zone,
            "basis": "recorded_state_decay_with_daily_weather",
            "collected": any(p["emotions"] is not None for p in points)}

    def _behavior_min_score(self):
        try:
            policy = getattr(self, "behavior", None)
            policy = policy.policy() if policy is not None and callable(
                getattr(policy, "policy", None)) else None
            return getattr(policy, "min_score", None)
        except Exception:  # noqa: BLE001 - 旧宿主/测试替身没有 policy 时不影响页面
            return None

    def _experience_dto(self, context, kind, *, detail=True):
        """任务状态：从未触发显示「尚未触发」，不再伪装成错误。

        detail=False（全局视图）：只给进度/时间/原因，去掉 job_id 与会话键
        ——进度要能看，具体会话的技术标识不外露。
        """
        try:
            status = dict(self.experience_status(context, kind) or {})
        except Exception:  # noqa: BLE001 - 状态查询失败不该让整页读不出
            status = {"status": "unavailable", "reason_code": "experience_status_unavailable"}
        code = status.get("status")
        # 归属会话：全局视图下动作落在最近会话，任务卡要能说明「这是谁的」。
        if detail:
            status["context_id"] = context.account_key
        else:
            status.pop("job_id", None)
        if code == "unavailable" and status.get("reason_code") in (
                "experience_not_attempted", ""):
            return {**status, "status": "idle", "reason_code": "",
                    "reason": EXPERIENCE_TASK_TEXT["idle"]}
        if isinstance(code, str):
            specific = EXPERIENCE_REASON_TEXT.get(status.get("reason_code"))
            status.setdefault("status_text", specific or EXPERIENCE_TASK_TEXT.get(code, ""))
        return status

    def _memory_sync(self):
        from ..services.memory_sync import MemorySyncService
        service = getattr(self, "_memory_sync_service", None)
        if service is None:
            service = MemorySyncService(self.store, self.bridge.discover, self.config)
            self._memory_sync_service = service
        return service

    async def _memory_dto(self, context):
        """记忆后端真实能力；不再把内部枚举 mode=none 当成「本地向量 · 待配置」。"""
        caps = self.memory.capabilities()
        external = bool(getattr(self.config, "livingmemory_enabled", False))
        configured = getattr(self.config, "memory_mode", "none")
        mode = "external" if external else (
            configured if configured in ("local_lite", "local_vector") else "none")
        backend = {"external": "LivingMemory", "local_vector": "本地向量记忆",
                   "local_lite": "本地轻量记录"}.get(mode, "未接入记忆后端")
        reason_text = {
            "external_provider_unavailable": "未找到可用的 LivingMemory 插件，请确认它已安装并启用。",
            "external_read_disabled": "尚未开启「允许记忆检索」。",
            "external_write_disabled": "尚未开启「允许记忆写入」。",
            "external_background_authorization_unsupported": "外部后端不支持后台代为授权，后台自动流程会跳过记忆写入。",
            "external_idempotent_export_unsupported": "外部后端不支持幂等导出，因此不提供导出按钮。",
            "external_memory_closed": "记忆后端已关闭。",
            "embedding_provider_missing": "未配置原生向量模型，本地向量检索不可用。",
        }
        reasons = [reason_text.get(code, code) for code in caps.reason_codes]
        capabilities = []
        if caps.recall:
            capabilities.append("按需检索记忆（对话与生成时使用）")
        if caps.append_experience:
            capabilities.append("写入新的互动与体验（由当前后端的写入通道负责）")
        if external:
            capabilities.append("手动同步当前人格的全量记忆到本地只读镜像")
        persona_id = context.persona_id if context is not None else ""
        try:
            mirror = await self.store.external_memory_mirror(persona_id, limit=5)
        except (ValueError, AttributeError):
            mirror = {"total": 0, "provider": "", "synced_at": None,
                      "truncated": False, "items": []}
        status = self._memory_sync().status() if external else {
            "enabled": False, "available": False, "reason": "", "provider": ""}
        return {
            "mode": mode, "backend": backend,
            "provider": "astrbot_plugin_livingmemory" if external else "",
            "provider_ready": bool(status.get("available")),
            "can_read": caps.recall, "can_write": caps.append_experience,
            "capabilities": capabilities, "reasons": reasons,
            "reason": "；".join(reasons),
            "persona_id": persona_id, "mirror": mirror,
            "sync": status,
        }

    async def console_memory_sync(self, context_id="", *, actor_id="console"):
        """手动把当前人格在 LivingMemory 的记忆读进本地只读镜像。

        只在 livingmemory_enabled=True 时可用；只读对方库，不写回、不调用模型。
        供「设置 → 记忆 → 手动同步当前人格记忆」按钮使用。
        """
        self._open()
        self._actor(actor_id, "manual memory sync")
        context = (self._context(context_id) if context_id
                   else next(reversed(self._contexts.values()), None))
        outcome = await self._memory_sync().sync(context)
        if outcome.status == "synced":
            await self.store.append_audit(
                action="memory.sync", actor_id=actor_id, reason="manual memory sync",
                context=context, value={"persona_id": outcome.persona_id,
                                        "stored": outcome.stored,
                                        "truncated": outcome.truncated},
            )
        return outcome.as_dict()

    def store_period(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return (datetime.fromtimestamp(self.store.clock(), ZoneInfo(self.config.timezone))
                .date().isoformat() if self.config.timezone else "")

    async def console_records(self, context_id="", kind="", page=1, page_size=10, query="",
                              persona_id="", view_scope="", platform=""):
        self._open()
        selection = None
        if kind in ("diary", "dream"):
            selection = {"persona_id": persona_id or (
                self._context(context_id).persona_id if context_id else
                (await self.manual_persona())[0])}
            context = None
        elif kind == "behavior":
            if not persona_id and not context_id:
                persona_id = (await self.manual_persona())[0]
            selection = {"persona_id": persona_id or self._context(context_id).persona_id,
                         "view_scope": view_scope or "global", "context_id": context_id,
                         "platform": platform}
            context = None
        elif persona_id or view_scope or platform:
            selection, _ = await self._selection(persona_id, view_scope, context_id, platform)
            context = None
        else:
            context = self._context(context_id)
        try:
            from ..storage.behavior_logs import query_behavior_logs
            result = (await query_behavior_logs(
                self.store, self.instance_id, selection, page=page, page_size=page_size, query=query,
            ) if kind == "behavior" else await self.store.query_persona_experiences(
                self.instance_id, selection["persona_id"], kind,
                page=page, page_size=page_size, query=query,
            ) if kind in ("diary", "dream") else await query_console_records(
                self.store, self.instance_id, selection, kind,
                page=page, page_size=page_size, query=query,
            ) if selection else await self.store.query_records(
                context, kind, page=page, page_size=page_size, query=query))
        except ValueError:
            raise ApplicationError("validation_error", "Invalid record query") from None
        items = []
        for row in result["items"]:
            value = row["value"]
            source_context = Context.from_dict(row["context"]) if selection else context
            item = {"id": row["id"], "created_at": row["created_at"],
                    "status": row.get("status", "recorded"),
                    "reason": row.get("reason_code", ""), "source": "livingEmotion",
                    "context": source_context.account_key}
            if kind == "emotion":
                item.update({k: v for k, v in value.items()
                             if k in ("before", "after", "reason_codes", "label")})
                for name in ("before", "after"):
                    raw = item.get(name)
                    if isinstance(raw, dict) and "pleasure" in raw:
                        item[name] = {**raw, "pleasure": (raw["pleasure"] + 1) / 2}
            elif kind == "behavior":
                item.update(candidate=value.get("purpose", ""), intent_id=row["id"],
                            result=row["status"], vetoes=value.get("reason_codes", []),
                            purpose=value.get("purpose", ""),
                            transport_status=value.get("transport_receipt", {}).get("status", "uncollected"),
                            receipt_id=value.get("transport_receipt", {}).get("receipt_id"))
                item.update(send_id=row["id"], content=row.get("content", ""),
                            timestamp=row.get("timestamp", row["created_at"]),
                            emotion_snapshot=value.get("emotion_snapshot", ""),
                            replied=row.get("replied", False), simulated=row.get("simulated", False),
                            emotion=value.get("emotion", ""), emotion_label=value.get("emotion_label", ""),
                            target_id="" if row.get("simulated") else (
                                source_context.scene_id if source_context.scene_kind == SceneKind.GROUP
                                else source_context.account_id),
                            target_label="模拟" if row.get("simulated") else (
                                "QQ群号" if source_context.scene_kind == SceneKind.GROUP else "QQ号"
                                ) if source_context.platform == "qq" else source_context.platform)
            else:
                loaded = await self.store.load_experience(row["id"])
                if loaded is None:
                    continue
                entry, _ = loaded
                item.update(title=row.get("day") or entry.period, body=entry.body, visibility="private",
                            clarity=entry.clarity, pinned=entry.pinned,
                            context_id=entry.context.account_key,
                            pin_available=(entry.context.platform == "console" or
                                           self.config.enabled and entry.context.account_key in self._contexts),
                            sources=[{"kind": ref.kind.value, "label": ref.kind.value,
                                      "source_id": ref.source_id} for ref in entry.evidence])
                if kind == "dream":
                    view = dream_view(entry, now=self.store.clock())
                    item.update(body=view.get("body", ""), clarity=view["clarity"])
            items.append(item)
        return {"api_version": 1, **result, "items": items}

    async def console_scopes(self, persona_id="", view_scope="global", context_id="", platform=""):
        self._open()
        selection = {"persona_id": persona_id, "view_scope": view_scope,
                     "context_id": context_id, "platform": platform}
        try:
            result = await query_scopes(self.store, self.instance_id, selection)
        except ValueError:
            raise ApplicationError("validation_error", "Invalid scope query") from None
        options = await self.console_settings_options()
        # 历史会话保留在库中，但不能把已经删除的人格重新加入可选目录。
        known = {}
        for p in options["personas"]:
            known.setdefault(p["value"], {"id": p["value"], "name": p["label"]})
        result["personas"] = list(known.values())
        return {"api_version": 1, "selection": selection, **result}

    async def console_relationships(self, persona_id, view_scope="global", context_id="",
                                    platform="", page=1, page_size=10, query="", limit=200,
                                    graph_scope="matched"):
        self._open()
        selection, contexts = await self._selection(persona_id, view_scope, context_id, platform)
        try:
            result = await query_relationships(self.store, self.instance_id, selection,
                                               page=page, page_size=page_size,
                                               query=query, limit=limit, config=self.config,
                                               graph_scope=graph_scope)
        except ValueError:
            raise ApplicationError("validation_error", "Invalid relationship query") from None
        if self.config.memory_read and contexts and result["nodes"]:
            supplement = await self._relationship_memory(contexts)
            # Recall can wait for I/O. Refresh local rows even when the supplement fails.
            extra, memory_generation = (), None
            if supplement and self.config.memory_read:
                context, generation, statements = supplement
                extra, memory_generation = statements, (context.scope_key, generation)
            result = await query_relationships(
                self.store, self.instance_id, selection, page=page, page_size=page_size,
                query=query, limit=limit, config=self.config, graph_scope=graph_scope,
                extra=extra, memory_generation=memory_generation)
        return {"api_version": 1, "selection": selection, **result}

    async def _relationship_memory(self, contexts):
        """Optional public memory API; no synthetic event or private store scan."""
        from ..adapters.memory.base import material_allowed
        from ..contracts import ContentKind
        from ..domain.relationship_inference import RelationshipStatement
        from ..ports.memory import MemoryRequest
        try:
            # Find one retained real event; discovery is bounded, recall happens once.
            context, event = None, None
            for candidate in contexts[:8]:
                source = await self.bridge.current(candidate)
                current_event = source.event() if source else None
                if current_event is not None:
                    context, event = candidate, current_event
                    break
            if context is None:
                return
            generation = await self.store.get_generation(context)
            if not await self.validate_context(context, generation):
                return
            request = MemoryRequest(uuid4().hex, "relationships", context,
                                    query="朋友 同事 同学 家人 室友 搭档 人物关系", limit=4)
            recalled = await self.memory.recall(request, event=event)
            materials = recalled.materials[:4]
            if not materials:
                return
            validated = await self.memory.validate_evidence(request, materials, event=event)
            if not validated.valid or validated.materials != materials:
                return
            statements = []
            for material in materials:
                ref = material.evidence
                if (not material_allowed(material, context, self.store.clock())
                        or ref.kind not in (ContentKind.INTERACTION, ContentKind.FACT, ContentKind.SUMMARY)
                        or ref.kind == ContentKind.SUMMARY and not ref.source_ids):
                    continue
                statements.append(RelationshipStatement(
                    replace(ref.context, route=None), ref.source_id, "记忆", ref.occurred_at, material.text,
                    ref.subject_id if ref.kind == ContentKind.INTERACTION
                    and ref.subject_id == context.account_id else "",
                    "记忆摘要" if ref.kind == ContentKind.SUMMARY else "记忆陈述",
                ))
            # A deletion or identity change while recalling cannot authorize a stale clue.
            final = await self.memory.validate_evidence(request, materials, event=event)
            if (final.valid and final.materials == materials
                    and await self.validate_context(context, generation) and self.config.memory_read):
                return context, generation, statements
        except Exception:  # Optional recall failure preserves the local-record graph.
            return

    async def console_relationship(self, persona_id, platform, account_id, *,
                                   expected_version, actor_id, reason="", context_id="",
                                   score=None, frozen=None, note=None):
        self._open()
        if not self.config.relationship_edit_enabled:
            raise ApplicationError("edit_disabled", "Relationship editing is disabled")
        reason = reason or "控制台编辑关系"
        self._actor(actor_id, reason)
        _, contexts = await self._selection(persona_id, "global", context_id, platform)
        context = next((c for c in contexts if c.account_id == account_id), None)
        if context is None:
            raise ApplicationError("validation_error", "Unknown platform account")
        try:
            override = await write_relationship_override(
                self.store, context, expected_version=expected_version, actor_id=actor_id,
                reason=reason, score=score, frozen=frozen, note=note)
        except ValueError as exc:
            if getattr(exc, "code", None) == "version_conflict":
                raise ApplicationError("version_conflict", "Relationship changed; refresh first") from None
            raise ApplicationError("validation_error", "Invalid relationship correction") from None
        return {"api_version": 1, "version": override["version"], "node": override["node"]}

    async def console_energy(self, persona_id, view_scope="global", context_id="", platform="",
                             page=1, page_size=10, event_type=""):
        self._open()
        selection, contexts = await self._selection(persona_id, view_scope, context_id, platform)
        if (type(page) is not int or not 1 <= page <= 1000000
                or type(page_size) is not int or page_size != 10
                or event_type not in ("", "reply", "fatigue", "recovery", "sleep", "wake",
                                      "manual", "config")):
            raise ApplicationError("validation_error", "Invalid energy query")
        now = self.store.clock()
        history = getattr(self.store, "energy_history", None)
        if not callable(history):
            raise ApplicationError("unavailable", "Energy history storage is unavailable")
        result = {"collected": False, "reason": "energy_history_not_collected",
                  "points": [], "items": [], "total": 0, "page": page, "page_size": page_size}
        if contexts:
            # One shared owner is read once. Scene histories remain separate
            # series; merging their energy values would invent a single battery.
            owners = {}
            owner_for = getattr(self.store, "state_owner", None)
            for context in contexts:
                owner = owner_for(context) if callable(owner_for) else None
                key = owner.owner_key if owner else context.scope_key
                owners.setdefault(key, context)
            readers = {}
            points = []
            total = 0
            buckets = max(1, 1440 // len(owners))
            for key, context in owners.items():
                data = await history(context, since=max(0, now - 86400), until=now,
                                     category=event_type or None, page=1, page_size=10,
                                     buckets=buckets)
                total += data["total"]
                readers[key] = {"context": context, "data": data, "page": 1, "index": 0}
                points.extend({"at": p["occurred_at"], "energy": p["last"],
                               "min": p["min"], "max": p["max"], "first": p["first"],
                               "owner_key": key} for p in data["curve"])
            queue = []
            def push(key):
                reader = readers[key]
                row = reader["data"]["items"][reader["index"]]
                heapq.heappush(queue, (-row["occurred_at"], -row["seq"], key, row))
            for key, reader in readers.items():
                if reader["data"]["items"]:
                    push(key)
            offset, items = (page - 1) * page_size, []
            consumed = 0
            while queue and consumed < min(total, offset + page_size):
                _, _, key, row = heapq.heappop(queue)
                if consumed >= offset:
                    items.append({**row, "id": row["event_id"], "at": row["occurred_at"],
                                  "kind": row["category"], "before_energy": row["before"],
                                  "after_energy": row["after"], "reason": row["reason_code"]})
                consumed += 1
                reader = readers[key]
                reader["index"] += 1
                if reader["index"] == len(reader["data"]["items"]):
                    if reader["page"] * page_size < reader["data"]["total"]:
                        reader["page"] += 1
                        reader["data"] = await history(
                            reader["context"], since=max(0, now - 86400), until=now,
                            category=event_type or None, page=reader["page"], page_size=10,
                            buckets=1)
                        reader["index"] = 0
                    else:
                        continue
                if reader["data"]["items"]:
                    push(key)
            result.update(collected=bool(total),
                          reason="" if total else "energy_history_not_collected",
                          points=sorted(points, key=lambda p: (p["at"], p["owner_key"]))[:1440],
                          items=items, total=total, series_total=len(owners),
                          points_truncated=len(points) > 1440)
        return {"api_version": 1, "selection": selection,
                "window_start": max(0, now - 86400), "window_end": now,
                "timezone": self.config.timezone or "UTC", **result}

    async def console_persona_description(self, persona_id):
        """只读返回指定人格的 system_prompt；人格不存在或超长时标记不可用，不报错。"""
        self._open()
        manager = getattr(getattr(self, "host", None), "persona_manager", None)
        getter = getattr(manager, "get_persona", None)
        description, available = "", False
        if callable(getter):
            try:
                persona = getter(persona_id)
                if inspect.isawaitable(persona):
                    persona = await persona
                prompt = getattr(persona, "system_prompt", None) if persona is not None else None
                # 与 manual_experience.manual_persona 的上限保持一致；超长按不可用处理，不截断。
                if isinstance(prompt, str) and len(prompt) <= 16000:
                    description, available = prompt, True
            except Exception:
                description, available = "", False
        return {"api_version": 1, "persona_id": persona_id, "description": description,
                "characters": len(description), "available": available}

    async def console_settings_options(self):
        self._open()
        host = getattr(self, "host", None)
        reasons = []

        async def listing(owner, method):
            function = getattr(owner, method, None)
            if not callable(function):
                reasons.append(method + "_unavailable")
                return []
            try:
                result = function()
                if inspect.isawaitable(result):
                    result = await result
                if not isinstance(result, (list, tuple)):
                    raise ValueError("invalid native listing")
                return result
            except Exception:
                reasons.append(method + "_unavailable")
                return []

        personas = []
        for persona in await listing(getattr(host, "persona_manager", None), "get_all_personas"):
            identifier = getattr(persona, "persona_id", None)
            if isinstance(identifier, str) and identifier:
                personas.append({"value": identifier, "label": identifier})

        async def providers(method, supported):
            options = []
            for provider in await listing(host, method):
                if type(provider).__name__ not in supported:
                    continue
                try:
                    meta = provider.meta()
                    identifier = meta.id
                    model = provider.get_model()
                    if isinstance(identifier, str) and identifier and isinstance(model, str):
                        options.append({"value": identifier, "label": f"{identifier} / {model}"})
                except Exception:
                    continue
            return options

        return {
            "api_version": 1, "personas": personas,
            "chat_providers": await providers("get_all_providers", {"ProviderOpenAIOfficial"}),
            "embedding_providers": await providers("get_all_embedding_providers", {
                "OpenAIEmbeddingProvider", "DashScopeEmbeddingProvider",
            }),
            "groups": self._settings_groups(), "reasons": reasons,
        }

    async def update_config(self, patch, *, expected_revision, reason, actor_id, context_id="", receipt="state"):
        self._open()
        if receipt not in ("state", "config"):
            raise ApplicationError("validation_error", "Invalid configuration receipt")
        # 保存配置不再要求用户填写原因：留空时用固定审计说明，审计记录仍然完整。
        reason = reason.strip() if isinstance(reason, str) else ""
        reason = reason or "控制台保存配置"
        self._actor(actor_id, reason)
        await self.refresh_config()
        if context_id:
            self._context(context_id)
        async with self._config_lock:
            # 兼容旧页面提交的当前运行版本；新页面使用独立的配置版本。
            if expected_revision not in (self.config_revision, self.revision):
                raise ApplicationError("version_conflict", "Configuration changed; refresh first")
            if (not isinstance(patch, dict) or not patch
                    or set(patch) - (set(to_dict(self.config)) - LEGACY_FIELDS)):
                raise ApplicationError("validation_error", "Unknown or empty configuration patch")
            # New list edits replace hidden legacy grants, including on clear.
            patch = dict(patch)
            if {"autonomy_qq_ids", "autonomy_qq_group_ids"} & patch.keys():
                patch["autonomy_scopes"] = ""
            # 改作息时间本身就表达「要用这套作息」：自动打开时间表，
            # 否则设置里填了时间却永远不生效，页面与设置对不上。
            schedule_keys = {"fatigue_start", "fatigue_end", "deep_sleep_at", "wake_at",
                             "nap_enabled", "nap_start", "nap_end",
                             "lie_in_min_minutes", "lie_in_max_minutes", "timezone"}
            if patch.keys() & schedule_keys and "night_schedule_enabled" not in patch:
                patch["night_schedule_enabled"] = True
            # 改梦境模型会重建业务对象并关闭手动执行器：正在跑的梦会被取消并落成
            # unknown / reload_after_dispatch。这里先拒绝并提示，等生成结束再保存
            # （原生 AstrBot 配置页的外部修改走 _watch_config，无法在这一层拦）。
            if (patch.get("dream_provider_id", self.config.dream_provider_id)
                    != self.config.dream_provider_id):
                executor = getattr(self, "manual_experience", None)
                if executor is not None and not executor.closed and executor.active("dream"):
                    raise ApplicationError(
                        "generation_in_progress",
                        "梦境正在生成，现在保存会中断这次生成并留下结果不明的任务。请等它结束后再改梦境模型。")
            try:
                updated = Config.from_mapping({**to_dict(self.config), **patch})
            except (ValueError, TypeError, KeyError, OverflowError):
                raise ApplicationError("validation_error", "Invalid configuration value") from None
            old = dict(self.native_config)
            self.native_config.update(patch)
            try:
                saved = self.native_config.save_config()
                if inspect.isawaitable(saved):
                    await saved
            except Exception:
                self.native_config.clear()
                self.native_config.update(old)
                raise ApplicationError("unavailable", "Native configuration could not be saved") from None
            await self._replace_config(updated)
            await self.store.append_audit(action="config.update", actor_id=actor_id,
                                          reason=reason, value={"fields": sorted(patch)})
            # 回执仍在锁内形成，只在原生持久化、运行时替换与审计完成后确认成功。
            if receipt == "config":
                return {"api_version": 1, "config": self.config_dto()}
        return await self.console_state(context_id)

    async def console_preview(self, context_id):
        self._open()
        context = self._context(context_id)
        result = await self.behavior.evaluate(context)
        codes = list(result.reason_codes)
        return {"api_version": 1, "eligible": bool(result.eligible),
                "score": result.score,
                "min_score": getattr(self.behavior.policy(), "min_score", None),
                "reasons": codes,
                "reason_text": "；".join(behavior_reason_texts(codes)),
                "gates": [{"code": code, "text": BEHAVIOR_REASON_TEXT.get(code, "未在页面登记的原因码。")}
                          for code in codes],
                "candidates": [],
                "model_calls": 0, "sends": 0}

    async def console_behavior_simulate(self, context_id="", persona_id="", emotion="current",
                                        request_id="", *, actor_id):
        from .behavior_simulation import simulate
        return await simulate(self, context_id, persona_id, emotion, request_id, actor_id=actor_id)

    async def console_action(self, context_id, action, *, expected_revision, reason,
                             actor_id, confirmed, entry_id="", pinned=None, expected_pinned=None):
        self._open()
        self._actor(actor_id, reason)
        if confirmed is not True:
            raise ApplicationError("validation_error", "Explicit confirmation is required")
        if expected_revision != self.revision:
            raise ApplicationError("version_conflict", "Configuration changed; refresh first")
        if action == "experience.pin":
            private_entry = await self.store.load_experience(entry_id) if entry_id else None
            private_archive = bool(private_entry and private_entry[0].context.platform == "console")
            if (not self.config.enabled and not private_archive or not isinstance(entry_id, str) or not entry_id
                    or len(entry_id) > 512 or type(pinned) is not bool
                    or type(expected_pinned) is not bool or pinned == expected_pinned):
                raise ApplicationError("validation_error", "Invalid pin update")
            # Reuse private-read authorization and the whole-record transactional
            # comparison. Pinning does not initialize or invoke any model.
            result = await self.pin_experience(
                context_id, entry_id, pinned=pinned, expected_pinned=expected_pinned,
                reason=reason, actor_id=actor_id,
            )
            if result["status"] in ("rejected", "unsupported"):
                code = ("version_conflict" if result.get("reason_code") in
                        ("experience_changed", "context_changed") else "forbidden")
                raise ApplicationError(code, "Record changed or pinning is unavailable")
            return {**result, "model_calls": 0, "sends": 0}
        if entry_id or pinned is not None or expected_pinned is not None:
            raise ApplicationError("validation_error", "Pin fields require a pin action")
        if action in ("diary.generate", "dream.generate"):
            return await self.console_experience_generate(
                str(uuid4()), (await self.manual_persona())[0], action.split(".")[0], actor_id=actor_id)
        state = await self.console_state(context_id)
        if expected_revision != self.revision:
            raise ApplicationError("version_conflict", "Configuration changed; refresh first")
        if not any(a["id"] == action and a["enabled"] for a in state["actions"]):
            raise ApplicationError("forbidden", "Action is unavailable")
        context = self._context(context_id)
        request_id = uuid4().hex
        if action.startswith("night."):
            result = await self.advance_scope(context, action=action)
            if result is None:
                raise ApplicationError("version_conflict", "Night state changed")
            result = {"status": "accepted",
                      "reason": ("已按手动指令进入疲劳期：精力清零，随后进入睡眠。" if action == "night.sleep"
                                 else "已按手动指令叫醒，精力保持不变。"),
                      "reason_code": "night_state_committed"}
        elif action == "behavior.send":
            # 管理员显式要求「现在发一条」：跳过时机分数、冷却与未回应退避，
            # 静音、免打扰、额度、身份与来源校验仍然生效。
            self.spawn_action(self.behavior.execute(context, intent_id="manual:" + request_id,
                                                    manual=True))
            result = {"status": "queued",
                      "reason": "已按管理员指令排队发送，结果会写入行为记录，可在下方「最近执行」查看。",
                      "reason_code": "behavior_queued"}
        else:
            # 日记与梦境都是管理员在控制台显式触发：一律按手动处理。
            result = await self.queue_experience(
                context, action.removesuffix(".generate"), manual=True,
            )
        await self.store.append_audit(action=action, actor_id=actor_id, reason=reason,
                                      context=context, value={"request_id": request_id,
                                                              "status": result["status"],
                                                              "reason_code": result.get("reason_code", "")})
        return {"api_version": 1, "request_id": request_id, **result}

    async def correct_relationship(self, context_id, *, expected_version, reason, actor_id,
                                   score=None, frozen=None):
        self._open()
        # 关系校正也允许免填原因：审计仍记录一条固定说明。
        reason = reason.strip() if isinstance(reason, str) else ""
        reason = reason or "控制台修改好感"
        self._actor(actor_id, reason)
        if not getattr(self.config, "relationship_edit_enabled", False):
            raise ApplicationError("forbidden", "Relationship editing is disabled in settings")
        context = self._context(context_id)
        result = await self.store.correct_relationship(
            context, await self.store.get_generation(context), expected_version=expected_version,
            actor_id=actor_id, reason=reason, score=score, frozen=frozen,
        )
        if not result.accepted:
            code = "version_conflict" if result.reason_code in (
                "version_conflict", "generation_conflict") else "validation_error"
            raise ApplicationError(code, "Relationship correction was rejected")
        return {"api_version": 1, **to_dict(result)}

    async def clear_context(self, context_id, *, expected_generation, reason, actor_id):
        self._open()
        self._actor(actor_id, reason)
        result = await self.store.clear_scope(
            self._context(context_id), expected_generation, actor_id=actor_id, reason_code=reason,
        )
        return {"api_version": 1, **to_dict(result)}

    async def pin_experience(self, context_id, entry_id, *, pinned, reason, actor_id,
                             expected_pinned=None):
        self._open()
        self._actor(actor_id, reason)
        loaded = await self.store.load_experience(entry_id)
        if loaded and loaded[0].context.platform == "console":
            old, generation = loaded
            identifier = (await self.manual_persona())[0]
            if (old.context.persona_id != identifier or old.context.instance_id != self.instance_id
                    or old.context.account_key != context_id or old.pinned != expected_pinned):
                raise ApplicationError("version_conflict", "档案或人格已变化")
            result = await self.store.pin_experience(
                old, replace(old, pinned=pinned), generation, actor_id=actor_id, reason=reason)
            return {"api_version": 1, **result}
        context = self._context(context_id)
        from .models import _pin_actor
        token = _pin_actor.set((actor_id, reason))
        try:
            service = await self.experience_service(context, need_model=False)
            result = await service.set_pin(
                entry_id, context, self._admin, pinned=pinned, expected_pinned=expected_pinned,
            )
            return {"api_version": 1, **result}
        finally:
            _pin_actor.reset(token)

    # ---- 情绪卡片图片（管理员自行维护，按情绪名称匹配） ----
    def _emotion_images(self):
        from ..storage.emotion_images import EmotionImages
        return EmotionImages(self.data_dir)

    async def console_emotion_images(self):
        """只返回元数据：真正图片按需单独取，避免 state 载荷被图片撑大。"""
        from ..storage.emotion_images import EmotionImageError
        try:
            return self._emotion_images().list()
        except EmotionImageError as error:
            raise ApplicationError(error.code, error.message) from error

    async def console_emotion_image(self, mood, index=None, data_url=None, remove=False,
                                    *, actor_id="console"):
        from ..storage.emotion_images import EmotionImageError
        images = self._emotion_images()
        try:
            if remove:
                removed = images.delete(mood, _optional_int(index))
                return {"api_version": 1, "mood": mood, "removed": removed,
                        "moods": images.list()["moods"]}
            if data_url is not None:
                stored = images.save(mood, data_url)
                payload = images.read(mood, stored.index)
                return {"api_version": 1, "mood": mood, "saved": stored.name,
                        "index": stored.index, "bytes": stored.size,
                        "updated_at": stored.updated_at,
                        "data_url": f"data:{payload[0]};base64,{payload[1]}",
                        "moods": images.list()["moods"]}
            payload = images.read(mood, _optional_int(index))
            if payload is None:
                return {"api_version": 1, "mood": mood, "data_url": None, "updated_at": None}
            return {"api_version": 1, "mood": mood,
                    "data_url": f"data:{payload[0]};base64,{payload[1]}",
                    "updated_at": payload[2]}
        except EmotionImageError as error:
            raise ApplicationError(error.code, error.message) from error
