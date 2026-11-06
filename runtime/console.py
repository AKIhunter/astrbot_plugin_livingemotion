"""Management DTOs. Authentication belongs to the product HTTP handlers."""

from __future__ import annotations

import inspect
import heapq
from dataclasses import fields, replace
from uuid import uuid4

from ..config import Config
from .. import contracts
from ..contracts import BotAffect, Context, HumanObservation, SceneKind, to_dict
from ..domain.emotion import DIMENSIONS, EmotionPolicy, decay_affect
from ..storage.console_data import (
    apply_relationship_override, context_dto, query_console_records, query_relationships,
    project_relationship_clues, query_scopes, selected_contexts, write_relationship_override,
)
from ..services.experience import dream_view
from .projector import snapshot


class ApplicationError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        self.status_code = {"validation_error": 400, "unauthorized": 401, "forbidden": 403,
                            "version_conflict": 409, "unavailable": 503}[code]
        super().__init__(message)


def dimensions(value):
    return {"pleasure": (value.pleasure + 1) / 2, "arousal": value.arousal,
            "stress": value.stress, "social_need": value.social_need}


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


class Console:
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
                 "persona_mode": ["follow", "explicit", "none"], "wake_mode": ["chat", "never", "both"]}
        enum_labels = {"active": "正常运行", "observe_only": "仅观察", "none": "不使用",
                       "local_lite": "旧版本地记录", "external": "外部记忆",
                       "follow": "跟随会话人格", "explicit": "指定人格",
                       "chat": "仅私聊", "never": "不允许聊天唤醒", "both": "私聊或群原生@Bot"}
        values = to_dict(self.config)
        options = options or {}
        result_fields = []
        for f in fields(Config):
            item = {"key": f.name, "label": FIELD_LABELS.get(f.name, "高级设置：" + f.name),
                    "section": field_section(f.name), "value": values[f.name],
                    "type": ("enum" if f.name in enums else "boolean" if type(f.default) is bool
                             else "integer" if type(f.default) is int
                             else "float" if type(f.default) is float else "string"),
                    "advanced": f.name.startswith(("model_", "window_", "body_", "event_"))
                    or f.name in ("scheduler_seconds", "night_policy_version", "night_block_chat",
                                  "memory_mode", "sleep_at")}
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
            result_fields.append(item)
        return {
            "revision": self.revision, "source": "AstrBot native plugin configuration",
            "values": values, "fields": result_fields,
            "groups": self._settings_groups(),
            "readonly": [{"key": "energy_max", "label": "总精力", "type": "float",
                          "value": 100.0, "step": 0.1, "unit": "点", "readonly": True,
                          "section": "night"}],
        }

    @staticmethod
    def _settings_groups():
        quick = {"enabled", "mode", "persona_id", "timezone", "provider_id", "home_city",
                 "livingmemory_enabled", "embedding_provider_id", "allow_sleep"}
        return [{"id": group, "label": label,
                 "field_keys": [f.name for f in fields(Config)
                                if (f.name in quick if group == "quick_start"
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
        memory = self.memory.capabilities()
        settings_options = await self.console_settings_options()
        state = {
            "api_version": 1, "context_id": context.account_key if context else "",
            "contexts": [{"id": c.account_key,
                          "label": f"{c.platform} / {c.scene_kind.value} / {c.scene_id} / {c.account_id}"}
                         for c in reversed(self._contexts.values())],
            "updated_at": self.store.clock(), "mode": self.effective_mode(context),
            "revision": self.revision, "config": self.config_dto(settings_options),
            "selection": selection,
            "state_mode": "persona" if getattr(self.config, "persona_shared_state", False) else "scene",
            "capabilities": ["config.write", "behavior.preview", "scopes.read", "relationships.read",
                             "relationship.write", "energy.read", "settings-options.read"],
            "health": [
                {"name": "runtime", "status": "ok" if self.config.enabled else "unavailable",
                 "reason": "ready" if self.config.enabled else "disabled"},
                {"name": "configuration", "status": "degraded" if self._config_fault else "ok",
                 "reason": "invalid_native_config" if self._config_fault else "native"},
                {"name": "ownership", "status": "degraded" if self.bridge.conflicts(context) else "ok",
                 "reason": "congling_scope_conflict" if self.bridge.conflicts(context) else "exclusive"},
                {"name": "background", "status": "degraded" if self._task_fault else "ok",
                 "reason": self._task_fault or "idle"},
                {"name": "reply_confirmation", "status": "unavailable",
                 "reason": "unsupported：当前宿主无可靠回复确认；收尾 120 秒超时取消，"
                           "不将 after-sent/bool/None 视为发送成功。"},
            ],
            "memory": {"mode": self.config.memory_mode, "provider": self.config.memory_mode,
                       "can_read": memory.recall, "can_write": memory.append_experience,
                       "capabilities": [], "reason": ", ".join(memory.reason_codes)},
            "experience": {"diary_enabled": self.config.diary_enabled,
                           "dream_enabled": self.config.dream_enabled,
                           "reason": "Explicitly enabled generation only"},
            "actions": [],
        }
        if selection is not None:
            state["contexts"] = [context_dto(c) for c in contexts]
        if context is None:
            return state
        owned_state = getattr(self.store, "get_owned_state", None)
        bot_record = (await owned_state(context, "bot") if callable(owned_state)
                      else await self.store.get_state(context, "bot"))
        policy = getattr(self, "emotion_policy", EmotionPolicy())
        if callable(policy):
            policy = policy()
        bot = decay_affect(snapshot(bot_record, BotAffect), now=self.store.clock(), policy=policy)
        reason = (", ".join(bot.reason_codes) if all(
            ref.context.scope_key == context.scope_key for ref in bot.evidence) else "")
        baseline = policy.baseline
        baseline = (dimensions(baseline) if isinstance(baseline, BotAffect)
                    else dimensions(BotAffect(**dict(zip(DIMENSIONS, baseline)))))
        obs_record = await self.store.get_state(context, "observation", context.account_id)
        obs = snapshot(obs_record, HumanObservation) if obs_record else None
        generation = await self.store.get_generation(context)
        relation = await self.current_relationship(context)
        night = await self.night_snapshot(context)
        availability = await self.availability(context)
        source = self.bridge.source(context)
        preview = await self.behavior.preview_behavior(context)
        model_ready = False
        try:
            await self.model_binding(context)
            model_ready = True
        except (ValueError, ImportError):
            pass
        active = self.effective_mode(context) == "active" and context.scene_kind != SceneKind.PUBLIC_COMMENT
        if relation is not None and not await self.validate_context(context, generation):
            relation = None
        if relation is not None:
            relation = await apply_relationship_override(self.store, context, relation)
        state.update({
            "persona": {"id": context.persona_id, "name": context.persona_id,
                        "source": "AstrBot native", "revision": context.persona_revision,
                        "description": source.persona.prompt if source else ""},
            "bot_state": {"dimensions": dimensions(bot), "baseline": baseline,
                          "label": ", ".join(bot.labels),
                          "reason": reason, "updated_at": bot.updated_at,
                          "version": bot_record.version if bot_record else 0, "source": "livingEmotion"},
            "observation": ({"subject": obs.subject_id, "label": ", ".join(obs.labels),
                             "confidence": obs.confidence, "observed_at": obs.occurred_at,
                             "expires_at": obs.expires_at, "source": "human observation"}
                            if obs and obs.expires_at > self.store.clock() else None),
            "relationship": ({"stage": relation.stage, "raw": relation.score,
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
                      "wake_at": night.wake_at, "reason": ""},
            "behavior": {"enabled": self.config.autonomy_enabled,
                         "reason": ", ".join(preview.reason_codes), "candidates": []},
            "actions": [
                {"id": name, "enabled": enabled,
                 "reason": "" if enabled else "Current mode, provider or policy does not permit this action"}
                for name, enabled in (
                    ("night.sleep", active and self.config.night_enabled),
                    ("night.wake", self.config.enabled and self.config.night_enabled),
                    ("diary.generate", active and self.config.diary_enabled and model_ready),
                    ("dream.generate", active and self.config.dream_enabled and model_ready
                     and night.phase.value == "asleep" and night.sleep_stage == "REM"),
                    ("behavior.send", active and model_ready and preview.eligible),
                )
            ],
        })
        if selection and selection["view_scope"] == "global":
            state["actions"] = []
            state["representative_context_id"] = context.account_key
            state["context_id"] = ""
            state["observation"] = None
            state["relationship"] = None
            # A global numerical view is not a new audience for private reasons.
            state["bot_state"]["reason"] = ""
        return state

    async def console_records(self, context_id="", kind="", page=1, page_size=10, query="",
                              persona_id="", view_scope="", platform=""):
        self._open()
        selection = None
        if persona_id or view_scope or platform:
            selection, _ = await self._selection(persona_id, view_scope, context_id, platform)
            context = None
        else:
            context = self._context(context_id)
        try:
            result = (await query_console_records(
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
                            result=row["status"], vetoes=value.get("reason_codes", []))
            else:
                loaded = await self.store.load_experience(row["id"])
                if loaded is None:
                    continue
                entry, _ = loaded
                item.update(title=entry.period, body=entry.body, visibility="private",
                            clarity=entry.clarity, pinned=entry.pinned,
                            context_id=entry.context.account_key,
                            pin_available=(self.config.enabled
                                           and entry.context.account_key in self._contexts),
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
        known = {p["id"]: p for p in result["personas"]}
        for p in options["personas"]:
            known.setdefault(p["value"], {"id": p["value"], "name": p["label"]})
        result["personas"] = list(known.values())
        return {"api_version": 1, "selection": selection, **result}

    async def console_relationships(self, persona_id, view_scope="global", context_id="",
                                    platform="", page=1, page_size=10, query="", limit=200):
        self._open()
        selection, contexts = await self._selection(persona_id, view_scope, context_id, platform)
        try:
            result = await query_relationships(self.store, self.instance_id, selection,
                                               page=page, page_size=page_size,
                                               query=query, limit=limit)
        except ValueError:
            raise ApplicationError("validation_error", "Invalid relationship query") from None
        if self.config.memory_read and contexts and result["nodes"]:
            supplement = await self._relationship_memory(contexts)
            # Recall can wait for I/O. Refresh local rows even when the supplement fails.
            result = await query_relationships(self.store, self.instance_id, selection,
                                              page=page, page_size=page_size, query=query, limit=limit)
            if supplement and self.config.memory_read:
                context, generation, statements = supplement
                result["peer_edges"] = await project_relationship_clues(
                    self.store, self.instance_id, selection, result["nodes"], statements,
                    memory_generation=(context.scope_key, generation))
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
                                   expected_version, actor_id, reason, context_id="",
                                   score=None, frozen=None):
        self._open()
        self._actor(actor_id, reason)
        _, contexts = await self._selection(persona_id, "global", context_id, platform)
        context = next((c for c in contexts if c.account_id == account_id), None)
        if context is None:
            raise ApplicationError("validation_error", "Unknown platform account")
        try:
            override = await write_relationship_override(
                self.store, context, expected_version=expected_version, actor_id=actor_id,
                reason=reason, score=score, frozen=frozen)
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

    async def update_config(self, patch, *, expected_revision, reason, actor_id, context_id=""):
        self._open()
        self._actor(actor_id, reason)
        await self.refresh_config()
        if context_id:
            self._context(context_id)
        async with self._config_lock:
            if expected_revision != self.revision:
                raise ApplicationError("version_conflict", "Configuration changed; refresh first")
            if not isinstance(patch, dict) or not patch or set(patch) - set(to_dict(self.config)):
                raise ApplicationError("validation_error", "Unknown or empty configuration patch")
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
        return await self.console_state(context_id)

    async def console_preview(self, context_id):
        self._open()
        context = self._context(context_id)
        result = await self.behavior.preview_behavior(context)
        return {"api_version": 1, "eligible": result.eligible,
                "reasons": list(result.reason_codes), "candidates": [],
                "model_calls": 0, "sends": 0}

    async def console_action(self, context_id, action, *, expected_revision, reason,
                             actor_id, confirmed, entry_id="", pinned=None, expected_pinned=None):
        self._open()
        self._actor(actor_id, reason)
        if confirmed is not True:
            raise ApplicationError("validation_error", "Explicit confirmation is required")
        if expected_revision != self.revision:
            raise ApplicationError("version_conflict", "Configuration changed; refresh first")
        if action == "experience.pin":
            if (not self.config.enabled or not isinstance(entry_id, str) or not entry_id
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
        state = await self.console_state(context_id)
        if not any(a["id"] == action and a["enabled"] for a in state["actions"]):
            raise ApplicationError("forbidden", "Action is unavailable")
        context = self._context(context_id)
        request_id = uuid4().hex
        if action.startswith("night."):
            result = await self.advance_scope(context, action=action)
            if result is None:
                raise ApplicationError("version_conflict", "Night state changed")
            result = {"status": "accepted", "reason": "night_state_committed"}
        elif action == "behavior.send":
            self.spawn_action(self.behavior.execute(context, intent_id="manual:" + request_id))
            result = {"status": "queued", "reason": "behavior_queued"}
        else:
            service = await self.experience_service(context)
            source = await self.bridge.current(context)
            if source is None:
                raise ApplicationError("unavailable", "Source changed")
            result = (await service.queue_diary(context, persona_text=source.persona.prompt)
                      if action == "diary.generate" else await service.queue_dream(
                          context, await self.night_snapshot(context),
                          persona_text=source.persona.prompt))
        await self.store.append_audit(action=action, actor_id=actor_id, reason=reason,
                                      context=context, value={"request_id": request_id,
                                                              "status": result["status"]})
        return {"api_version": 1, "request_id": request_id, **result}

    async def correct_relationship(self, context_id, *, expected_version, reason, actor_id,
                                   score=None, frozen=None):
        self._open()
        self._actor(actor_id, reason)
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
