"""R9 v1 in-process facade. No HTTP/admin trust is inferred from call arguments."""

from __future__ import annotations

import re

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from .config import Config
from .domain.relationship import initial_relationship
from .contracts import (
    API_VERSION,
    SCHEMA_VERSION,
    BotAffect,
    Context,
    Event,
    NightState,
    Relationship,
    RelationshipContribution,
    SceneKind,
    StateWrite,
    stable_key,
    to_dict,
)
from .runtime.background import BackgroundRuntime
from .runtime.projector import Projector, projection_event
from .storage import SQLiteStore, StoreClosed

ProjectEvent = Callable[
    [Event], Awaitable[tuple[Sequence[StateWrite], Sequence[RelationshipContribution]]]
]


class LivingEmotionAPI:
    api_version = API_VERSION

    def __init__(self, store: SQLiteStore, config: Config, runtime: BackgroundRuntime,
                 *, project_event: ProjectEvent | None = None, instance_id: str | None = None,
                 application=None):
        self._store = store
        self._config = config
        self._runtime = runtime
        self._project_event = project_event
        self._instance_id = instance_id
        self._active = True
        self._application = application

    def stop_accepting(self) -> None:
        self._active = False

    async def _sync(self):
        if self._application is not None and self._active:
            await self._application.refresh_config()

    @staticmethod
    def _context(context: Context | Mapping[str, Any]) -> Context:
        return context if isinstance(context, Context) else Context.from_dict(context)

    @staticmethod
    def _result(status: str, reason: str, **data: Any) -> dict[str, Any]:
        return {"api_version": API_VERSION, "status": status, "reason_code": reason, **data}

    async def get_capabilities(self, context=None) -> dict[str, Any]:
        await self._sync()
        mode = (self._application.effective_mode(self._context(context) if context is not None else None) if self._application
                else self._config.mode if self._config.enabled and self._active else "disabled")
        return self._result(
            "ok", "capabilities", schema_version=SCHEMA_VERSION,
            operations=["get_capabilities", "resolve_producer_context", "ingest_event", "get_bot_state",
                        "get_current_emotion",
                        "get_action_policy", "handoff_image_failure", "resume_image_followup",
                        "get_image_prompt_retry_policy",
                        "bind_image_promise", "settle_image_promise",
                        "get_observation", "get_relationship", "get_availability",
                        "preview_behavior", "get_health"],
            mode=mode, memory_mode=self._config.memory_mode,
            instance_id=self._instance_id,
            persistent_idempotency=True, domain_ready=self._project_event is not None,
            autonomous_executor=self._application is not None, model_generation=self._application is not None,
            scene_kinds=[kind.value for kind in SceneKind],
            reason_codes=[] if self._project_event else ["domain_not_connected"],
        )

    async def resolve_producer_context(self, source: Mapping[str, Any]) -> dict[str, Any]:
        """Trusted plugin producers supply source facts, never routes or host IDs."""
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        if self._instance_id is None:
            return self._result("unavailable", "instance_unavailable")
        required = {"producer", "bot_account", "adapter_id", "platform", "scene_kind",
                    "scene_id", "account_id", "persona_id", "persona_revision"}
        try:
            if set(source) != required:
                raise ValueError("producer fields")
            if any(not isinstance(source[name], str) or not source[name].strip()
                   or len(source[name]) > 512 for name in required):
                raise ValueError("source missing")
            kind = SceneKind(source["scene_kind"])
            if kind not in (SceneKind.PRIVATE, SceneKind.PUBLIC_COMMENT):
                raise ValueError("producer scene unsupported")
            if kind == SceneKind.PRIVATE and source["scene_id"] != source["account_id"]:
                raise ValueError("private scene mismatch")
            audience = (("public:" + stable_key(source["platform"], source["scene_id"]),)
                        if kind == SceneKind.PUBLIC_COMMENT else (
                            source["platform"] + ":" + source["bot_account"],
                            source["platform"] + ":" + source["account_id"],
                        ))
            context = Context(
                instance_id=self._instance_id,
                bot_id="producer:" + stable_key(self._instance_id, source["producer"],
                                                source["platform"], source["bot_account"]),
                persona_id=source["persona_id"], persona_revision=source["persona_revision"],
                adapter_id=source["adapter_id"], platform=source["platform"],
                scene_kind=kind, scene_id=source["scene_id"], account_id=source["account_id"],
                identity_revision="source:" + stable_key(source["platform"], source["account_id"]),
                audience=audience, route=None,
            )
            return self._result("ok", "producer_context", data=to_dict(context))
        except (ValueError, TypeError, KeyError):
            return self._result("rejected", "invalid_producer_context")

    async def ingest_event(self, event: Event | Mapping[str, Any]) -> dict[str, Any]:
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("rejected", "plugin_disabled")
        try:
            parsed = event if isinstance(event, Event) else Event.from_dict(event)
            if self._instance_id is not None and parsed.context.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            lock = self._store.projection_lock(parsed.context)
            # Waiting events keep their pre-clear generation. An uncontended built-in
            # projector acquires the lock without yielding, then reads one snapshot.
            generation = (await self._store.get_generation(parsed.context)
                          if lock.busy or not isinstance(self._project_event, Projector)
                          else None)
            async with lock:
                return await self._commit_projected(parsed, generation)
        except (TypeError, ValueError, KeyError):
            return self._result("rejected", "invalid_event")
        except StoreClosed:
            return self._result("rejected", "store_closed")
        except Exception:
            return self._result("rejected", "processing_failed")

    async def _commit_projected(self, parsed: Event, generation: int | None) -> dict[str, Any]:
        # Only the built-in path shares this request's immutable key view. Host
        # callbacks and custom projectors continue receiving the caller's event.
        request_event = (projection_event(parsed) if type(self._project_event) is Projector
                         else parsed)
        for _ in range(3):
            writes, contributions = (), ()
            traces = ()
            if self._project_event is not None:
                projection = await self._project_event(request_event)
                snapshot_generation = getattr(projection, "generation", None)
                if generation is None:
                    if type(snapshot_generation) is not int or snapshot_generation < 0:
                        raise ValueError("projection generation missing")
                    generation = snapshot_generation
                if snapshot_generation is not None and snapshot_generation != generation:
                    return self._result("rejected", "stale_generation")
                if hasattr(projection, "writes"):
                    writes, contributions, traces = (
                        projection.writes, projection.contributions, projection.traces,
                    )
                else:
                    writes, contributions = projection
            if not self._active:
                return self._result("rejected", "plugin_stopped")
            if self._application is not None:
                if not self._application.config.enabled:
                    return self._result("rejected", "plugin_disabled")
                # 自己登记“回复已提交”这类事件，消息其实已经出去了，
                # 只是补一笔记录；重启后实时来源不在了也不该把它丢掉。
                # 其余事件照旧用严格校验，必须有实时来源。
                relaxed = (getattr(parsed, "event_type", "") == "bot_reply_submitted"
                           and getattr(self._application, "validate_delivery", None))
                check = relaxed or self._application.validate_context
                if parsed.context.route and not await check(parsed.context, generation):
                    return self._result("rejected", "context_changed")
            result = await self._store.commit_event(
                request_event, generation, writes, contributions, traces=traces,
            )
            if result.reason_code != "version_conflict":
                if self._application and result.accepted:
                    await self._application.remember_context(parsed.context)
                    if self._project_event is not None:
                        self._application.queue_refinement(parsed, result, projection)
                return {"api_version": API_VERSION, **to_dict(result),
                        "domain_applied": self._project_event is not None and result.accepted}
        return self._result("rejected", "version_conflict")

    async def _snapshot(self, context: Context | Mapping[str, Any], kind: str,
                        default: Any) -> dict[str, Any]:
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        try:
            scope = self._context(context)
            if self._instance_id is not None and scope.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            if kind in ("observation", "relationship") and not scope.account_id:
                return self._result("rejected", "missing_account")
            record = await self._store.get_state(
                scope, kind, scope.account_id if kind in ("observation", "relationship") else "",
            )
            value = to_dict(default) if record is None else {
                key: val for key, val in record.value.items() if not key.startswith("_")
            }
            # Old/custom partial projections have no domain timestamp; do not
            # invent elapsed time or expand their legacy payload shape.
            if kind == "bot" and (record is None or {
                "pleasure", "arousal", "stress", "social_need", "updated_at",
            }.issubset(value)):
                from .runtime.projector import current_affect
                value = to_dict(current_affect(record, now=self._store.clock()))
            if kind == "relationship" and self._application is not None:
                relationship = await self._application.current_relationship(scope, record=record)
                if relationship is None:
                    return self._result("unavailable", "context_changed")
                value = to_dict(relationship)
            if kind == "relationship" and value is not None:
                value["normalized"] = value.get("score", 0) / 1000.0
            if kind == "observation" and value is not None:
                if value.get("expires_at", 0) <= self._store.clock():
                    value = None
            return self._result(
                "ok", "snapshot" if record is not None else "baseline",
                type=kind, data=value, context=to_dict(scope),
                generation=record.generation if record else await self._store.get_generation(scope),
                version=record.version if record else 0,
                reason_codes=[] if self._project_event else ["domain_not_connected"],
            )
        except (TypeError, ValueError, KeyError):
            return self._result("rejected", "invalid_context")
        except StoreClosed:
            return self._result("unavailable", "store_closed")
        except Exception:
            return self._result("unavailable", "storage_failed")

    async def get_bot_state(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        return await self._snapshot(context, "bot", BotAffect())

    async def get_current_emotion(self, context=None, *, event=None) -> dict[str, Any]:
        """Numeric read facade for other plugins; no text, evidence or identity fields."""
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        try:
            app = self._application
            if event is not None:
                if app is None:
                    return self._result("unavailable", "native_bridge_unavailable")
                source, _ = await app.bridge.normalize(event, self._store.clock())
                scope = source.context
            else:
                scope = self._context(context)
            if self._instance_id is not None and scope.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            # Shared private state is never exposed to a public-comment producer.
            if scope.scene_kind == SceneKind.PUBLIC_COMMENT:
                return self._result("unavailable", "public_comment_no_emotion")
            generation = await self._store.get_generation(scope)
            if app is not None and not await app.validate_context(scope, generation):
                return self._result("unavailable", "context_changed")
            from .runtime.projector import current_affect, snapshot, stored_context_emotions
            from .domain.context_emotion import expression_items
            from .domain.relationship import relationship_behavior
            from .storage.console_data import apply_relationship_override, read_relationship_override
            from .runtime.state_scope import source_affect
            from .domain.dreaming import six_emotions
            record = await self._store.get_state(scope, "bot")
            state = current_affect(record, now=self._store.clock())
            state = source_affect(state, scope)
            emotions = await app.weather_emotions(state) if app else six_emotions(state)
            relation_record, emotion_record, extra = None, None, {}
            if self._config.context_emotions_enabled and scope.account_id:
                relation_record = await self._store.get_state(scope, "relationship", scope.account_id)
                if relation_record is not None and relation_record.generation == generation:
                    relation = await apply_relationship_override(
                        self._store, scope, snapshot(relation_record, Relationship))
                    override = await read_relationship_override(self._store, scope)
                    description = relationship_behavior(relation.score, self._config,
                        note=(override or {}).get("note", ""))["description"]
                    emotion_record = await self._store.context_emotion_record(scope, relation_record)
                    rows = expression_items(stored_context_emotions(
                        emotion_record, scope, now=self._store.clock(),
                        fingerprint=app.context_emotion_fingerprint(scope) if app else "",
                        epoch=app._context_emotion_epoch if app else ""),
                        scope, now=self._store.clock(), relationship=relation,
                        relationship_note="\n".join(((override or {}).get("note", ""), description)))
                    # 用户维度下该对象可能还没有人级记录：没有记录按版本 0 返回。
                    extra = {"context_emotions": {r["kind"]: r["intensity"] for r in rows},
                             "context_emotions_version": 1,
                             "context_emotions_state_version": (
                                 emotion_record.version if emotion_record else 0)}
            if app is not None and not await app.validate_context(scope, generation):
                return self._result("unavailable", "context_changed")
            latest = await self._store.get_state(scope, "bot")
            if (latest.version if latest else 0) != (record.version if record else 0):
                return self._result("unavailable", "state_changed")
            if await self._store.get_generation(scope) != generation:
                return self._result("unavailable", "context_changed")
            if self._config.context_emotions_enabled and scope.account_id:
                latest_relation = await self._store.get_state(scope, "relationship", scope.account_id)
                if ((latest_relation.version if latest_relation else 0)
                        != (relation_record.version if relation_record else 0)):
                    return self._result("unavailable", "state_changed")
                if emotion_record is not None:
                    latest_emotion = await self._store.context_emotion_record(scope, latest_relation)
                    if (latest_emotion.version if latest_emotion else 0) != emotion_record.version:
                        return self._result("unavailable", "state_changed")
            dominant = max(emotions, key=emotions.get)
            dominant = dominant if emotions[dominant] >= .25 else "calm"
            mode = app.effective_mode(scope) if app else self._config.mode
            return self._result("ok", "current_emotion", data={
                "emotions": emotions, "dominant": dominant, "labels": list(state.labels),
                "affect": {k: getattr(state, k) for k in (
                    "pleasure", "arousal", "stress", "social_need")},
                "updated_at": state.updated_at, "sampled_at": self._store.clock(),
                "version": record.version if record else 0, "generation": generation,
                "mode": mode, "may_influence_reply": mode == "active",
                **extra,
            })
        except (TypeError, ValueError, KeyError, AttributeError):
            return self._result("rejected", "invalid_context")
        except StoreClosed:
            return self._result("unavailable", "store_closed")
        except Exception:
            return self._result("unavailable", "emotion_read_failed")

    async def get_observation(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        return await self._snapshot(context, "observation", None)

    async def _image_scope(self, context, event):
        """写接口只接受原生事件的真实来源，不从工具参数、文本或昵称推导身份。"""
        await self._sync()
        app = self._application
        if not self._active or not self._config.enabled or app is None or app.closed:
            raise ValueError("plugin_unavailable")
        timed = bool(event.get_extra("cron_job") or event.get_extra("livingemotion:promise_id"))
        handoff = bool(event.get_extra("_livinghello_image_failure"))
        if context is None and (timed or handoff):
            # 宿主 cron 没有入站消息钩子：只从已登记的真实会话重建来源。
            # 聊天直出的失败交接（issue #9）：LH 侧事件没有 context 参数，
            # 但事件自带 sender/route——与 cron 同样只认已登记的真实会话，
            # 不从文本或昵称推导身份。交接发生在原始请求之后，用 delivery 校验。
            sender = str(event.get_sender_id())
            route = str(event.unified_msg_origin)
            candidates = [c for c in await self._store.list_contexts()
                          if c.account_id == sender and c.adapter_id == route.split(":", 1)[0]]
            from dataclasses import replace
            from .contracts import rebuild_route
            context = next((replace(c, route=route) for c in candidates
                            if rebuild_route(c) == route), None)
        scope = self._context(context)
        check = (app.validate_delivery if (timed or handoff)
                 else app.validate_context)
        if (scope.instance_id != self._instance_id or not scope.route
                or scope.route != getattr(event, "unified_msg_origin", None)
                or scope.account_id != str(event.get_sender_id())
                or scope.scene_id != str(event.get_group_id() or event.get_sender_id())
                or scope.scene_kind.value != ("group" if event.get_group_id() else "private")
                or app.effective_mode(scope) != "active"
                or not await check(scope)):
            raise ValueError("context_changed")
        event.set_extra("livingemotion:context", to_dict(scope))
        return scope

    async def get_action_policy(self, context, *, event) -> dict[str, Any]:
        """关系只拦新个人生图请求；已经落库的生图义务不因关系变化撤销。"""
        try:
            scope = await self._image_scope(context, event)
            pid = (event.get_extra("livingemotion:promise_id")
                   or event.get_extra("_livinghello_requested_promise"))
            if pid:
                row = await self._application._promises().promises.get(str(pid))
                if (row and row["scope_key"] == scope.scope_key
                        and row.get("handoff_account_key", "") in ("", scope.account_key)
                        and row["generation"] == await self._store.get_generation(scope)
                        and row["status"] in ("scheduled", "running")):
                    from .runtime.promise_actions import needs_image
                    if needs_image(row["description"]):
                        return self._result(
                            "ok", "action_policy", contract="livingemotion.image-policy.v1",
                            data={"allowed": True, "reason": "existing_obligation"})
            data = await self._application.image_action_policy(scope, event=event)
            return self._result("ok", "action_policy", contract="livingemotion.image-policy.v1", data=data)
        except Exception:
            return self._result("unavailable", "action_policy_unavailable")

    async def handoff_image_failure(self, context, *, event) -> dict[str, Any]:
        """LH 已说明失败后交接；原请求 ID、原因和画面均取自受信事件。"""
        try:
            scope = await self._image_scope(context, event)
            app = self._application
            if not app.config.promise_enabled or not app.promise_actions_active():
                return self._result("unavailable", "promise_actions_disabled")
            failure = event.get_extra("_livinghello_image_failure")
            if (not isinstance(failure, dict)
                    or failure.get("notified") is not True
                    or failure.get("kind") not in {
                        "content_rejected", "rate_limited", "provider_error", "result_unknown",
                        "delivery_unknown", "quota_exhausted", "prompt_too_long", "prompt_adjustment_required"}
                    or not isinstance(failure.get("prompt"), str)
                    or not 1 <= len(failure["prompt"]) <= 4000
                    or not isinstance(failure.get("request_id"), str)
                    or not 1 <= len(failure["request_id"]) <= 128
                    or not isinstance(failure.get("reason"), str)
                    or not 1 <= len(failure["reason"]) <= 300
                    or type(failure.get("use_reference")) is not bool):
                return self._result("rejected", "invalid_image_failure")
            source_id = str(event.message_obj.message_id)
            # 自动改词权限由 LH 当前契约决定，不能信任事件里自报的布尔开关。
            from .livinghello_coupling import discover
            peer = discover(app.bridge.discover)
            from .runtime.promise_actions import ImagePromiseAction
            policy = ImagePromiseAction.mapping_policy(peer) if peer else {}
            metadata = {"adjustment_asked": failure.get("adjustment_asked") is True}
            for key in ("original_prompt", "attempted_prompt", "notice"):
                value = failure.get(key)
                if isinstance(value, str) and len(value) <= (200 if key == "notice" else 4000):
                    metadata[key] = value
            count = failure.get("prompt_retry_count", 0)
            metadata["prompt_retry_count"] = count if type(count) is int and 0 <= count <= 10 else 10
            metadata["auto_prompt_retry"] = bool(
                policy.get("enabled") and min(policy.get("retry_limit", 0),
                                              app._promises().retry_limit) > metadata["prompt_retry_count"]
                and failure["kind"] in {"content_rejected", "prompt_too_long"}
                and not failure["use_reference"])
            result = await app._promises().promises.accept_image_handoff(
                scope, request_id=failure["request_id"], source_event_id=source_id,
                failure={k: failure[k] for k in
                         ("request_id", "prompt", "kind", "reason", "use_reference")}
                | metadata,
                max_active=app._promises().max_active, retry_limit=app._promises().retry_limit)
            return self._result("ok", "image_failure_handoff",
                                contract="livingemotion.image-followup.v1", data=result)
        except Exception:
            return self._result("unavailable", "image_handoff_failed")

    async def get_image_prompt_retry_policy(self, context, *, event):
        try:
            await self._image_scope(context, event)
            app = self._application
            return self._result("ok", "image_prompt_retry_policy",
                contract="livingemotion.image-prompt-retry.v1",
                data={"allowed": bool(app.config.promise_enabled and app.promise_actions_active()
                                      and app._promises().retry_limit > 0),
                      "retry_limit": app._promises().retry_limit})
        except Exception:
            return self._result("unavailable", "image_prompt_retry_unavailable")

    async def resume_image_followup(self, context, *, event, promise_id, prompt) -> dict[str, Any]:
        try:
            scope = await self._image_scope(context, event)
            app = self._application
            if not app.config.promise_enabled or not app.promise_actions_active():
                return self._result("unavailable", "promise_actions_disabled")
            if (not isinstance(promise_id, str) or not 1 <= len(promise_id) <= 128
                    or not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000):
                return self._result("rejected", "invalid_image_adjustment")
            from .storage.promise_store import is_adjustment
            getter = getattr(event, "get_message_str", None)
            user_text = getter() if callable(getter) else getattr(event, "message_str", "")
            if (event.get_extra("cron_job") or event.get_extra("livingemotion:promise_id")
                    or not is_adjustment(user_text)):
                return self._result("rejected", "user_adjustment_required")
            rows = await app._promises().active(scope)
            waiting = [r for r in rows if r["status"] == "waiting"]
            adjustment_text = str(user_text)
            for row in waiting:
                adjustment_text = adjustment_text.replace(row["promise_id"], "")
                adjustment_text = adjustment_text.replace(row["promise_id"][:8], "")
            adjustment_text = re.sub(r"第[一二三123](?:条|张|个|件)", "", adjustment_text)
            if not is_adjustment(adjustment_text):
                return self._result("rejected", "user_adjustment_required")
            if len(waiting) > 1:
                # 多任务须有明确的 ID、编号或原画面；不能让模型任意挑一个。
                mentioned = [r for r in waiting if r["promise_id"][:8] in user_text
                             or r["description"].removeprefix("生图：") in user_text]
                numbered = re.search(r"第([一二三123])(?:条|张|个|件)", user_text)
                if numbered:
                    number = (int(numbered[1]) if numbered[1].isdigit()
                              else "一二三".find(numbered[1]) + 1)
                    if number <= len(rows):
                        mentioned.append(rows[number - 1])
                if {r["promise_id"] for r in mentioned} != {promise_id}:
                    return self._result("rejected", "ambiguous_image_adjustment")
            result = await app._promises().promises.resume_image_handoff(
                scope, promise_id, prompt=prompt.strip(), source_event_id=str(event.message_obj.message_id))
            return self._result("ok", "image_followup_resume",
                                contract="livingemotion.image-followup.v1", data=result)
        except Exception:
            return self._result("unavailable", "image_followup_resume_failed")

    async def bind_image_promise(self, context, *, event) -> dict[str, Any]:
        try:
            scope = await self._image_scope(context, event)
            app = self._application
            binding = event.get_extra("_livinghello_image_binding")
            if (not app.config.promise_enabled or not app.promise_actions_active()
                    or event.get_extra("cron_job")
                    or not isinstance(binding, dict)
                    or binding.get("use_reference") is not False
                    or any(not isinstance(binding.get(k), str) or not 1 <= len(binding[k]) <= n
                           for k, n in (("promise_id", 128), ("request_id", 128), ("prompt", 4000)))):
                return self._result("rejected", "invalid_image_binding")
            service = app._promises()
            # 与宿主注册/仲裁共用锁，查归属到领取之间不留重复执行窗口。
            async with service.ownership.lock:
                row = await service.promises.get(binding["promise_id"])
                if row and row["scope_key"] == scope.scope_key:
                    job = await service.ownership.host_match(
                        scope, row["description"], float(row["original_due_at"]))
                    if job:
                        return self._result("rejected", "image_owned_by_host")
                data = await service.promises.bind_image_request(scope, binding)
            return self._result("ok", "image_promise_binding",
                                contract="livingemotion.image-result.v1", data=data)
        except Exception:
            return self._result("unavailable", "image_binding_failed")

    async def settle_image_promise(self, context, *, event) -> dict[str, Any]:
        try:
            scope = await self._image_scope(context, event)
            receipt = event.get_extra("_livinghello_image_result")
            if (not isinstance(receipt, dict) or receipt.get("status") not in ("sent", "failed", "unknown")
                    or any(not isinstance(receipt.get(k), str) or not 1 <= len(receipt[k]) <= n
                           for k, n in (("promise_id", 128), ("request_id", 128), ("prompt", 4000)))):
                return self._result("rejected", "invalid_image_receipt")
            # 使用同一新版映射许可，原事项失败不新建第二条。
            if receipt.get("auto_prompt_retry"):
                policy = await self.get_image_prompt_retry_policy(scope, event=event)
                receipt = {**receipt, "auto_prompt_retry": bool(
                    policy.get("status") == "ok" and policy.get("data", {}).get("allowed"))}
            service = self._application._promises()
            data = await service.promises.settle_image_request(
                scope, receipt, ttl_seconds=service._trace_ttl(), retry_limit=service.retry_limit)
            return self._result("ok", "image_promise_receipt",
                                contract="livingemotion.image-result.v1", data=data)
        except Exception:
            return self._result("unavailable", "image_receipt_failed")

    async def get_relationship(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        return await self._snapshot(
            context, "relationship", initial_relationship(),
        )

    async def get_availability(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        try:
            scope = self._context(context)
            if self._instance_id and scope.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            if scope.scene_kind == SceneKind.PUBLIC_COMMENT:
                return self._result("ok", "public_comment_no_route", available=False,
                                    block_chat=False, reason_codes=["public_comment_no_route"])
            if self._application:
                availability = await self._application.availability(scope)
                return self._result("ok", "night_state", **to_dict(availability))
        except (ValueError, TypeError, KeyError):
            return self._result("rejected", "invalid_context")
        snapshot = await self._snapshot(context, "night", NightState())
        if snapshot["status"] != "ok":
            return snapshot
        phase = snapshot["data"].get("phase", "awake")
        sleeping = self._config.night_enabled and phase in ("settling", "asleep", "waking")
        return self._result(
            "ok", "night_state", available=not sleeping,
            block_chat=sleeping and self._config.night_block_chat,
            reason_codes=["sleeping"] if sleeping else [], version=snapshot["version"],
            generation=snapshot["generation"],
        )

    async def preview_behavior(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        await self._sync()
        if self._application:
            try:
                preview = await self._application.behavior.preview_behavior(self._context(context))
                return self._result("ok", "behavior_preview", **to_dict(preview))
            except (ValueError, TypeError):
                return self._result("rejected", "invalid_context")
        availability = await self.get_availability(context)
        if availability["status"] != "ok":
            return availability
        return self._result(
            "ok", "executor_not_connected", eligible=False, model_calls=0, sends=0,
            reason_codes=["executor_not_connected"]
            + ([] if self._config.autonomy_enabled else ["autonomy_disabled"])
            + (["observe_only"] if self._config.mode == "observe_only" else [])
            + availability["reason_codes"],
        )

    async def get_health(self) -> dict[str, Any]:
        await self._sync()
        if not self._active:
            return self._result("stopped", "plugin_stopped")
        try:
            storage = await self._store.health()
            return self._result("ok", "ready", storage=storage,
                                runtime=self._runtime.health(),
                                reason_codes=[] if self._project_event else ["domain_not_connected"])
        except Exception:
            return self._result("unavailable", "storage_failed")
