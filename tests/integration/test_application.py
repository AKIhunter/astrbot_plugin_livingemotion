import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from astrbot_plugin_livingemotion.adapters.astrbot import AstrBotBridge
from astrbot_plugin_livingemotion.contracts import Context, Experience, Relationship, StateWrite, to_dict
from astrbot_plugin_livingemotion.runtime.application import SUFFIX, Application, ApplicationError
from astrbot_plugin_livingemotion.storage import SQLiteStore


class NativeConfig(dict):
    def save_config(self):
        self.saved = dict(self)


class Host:
    def __init__(self):
        self.persona_id, self.prompt = "native", "Native character"
        self.congling = None
        self.sends = 0
        self.persona_manager = self
        self.conversation_manager = self

    def get_registered_star(self, name):
        return (SimpleNamespace(activated=True, star_cls=self.congling)
                if name == "astrbot_plugin_congling" and self.congling else None)

    async def get_curr_conversation_id(self, route):
        return None

    async def resolve_selected_persona(self, **kwargs):
        return self.persona_id, {"prompt": self.prompt}, None, False

    async def get_current_chat_provider_id(self, route):
        raise ValueError("synthetic no provider")

    async def send_message(self, route, chain):
        self.sends += 1
        return True


class TestBridge(AstrBotBridge):
    __test__ = False
    text_part = staticmethod(lambda text: SimpleNamespace(text=text))
    chain = staticmethod(lambda text: text)


class Message:
    def __init__(self, identifier="m1", body="hello", group="", account="human"):
        self.platform_meta = SimpleNamespace(id="adapter", name="aiocqhttp")
        self.message_obj = SimpleNamespace(message_id=identifier, timestamp=0)
        self.message_str = body
        self.group, self.account = group, account
        self.unified_msg_origin = ("adapter:GroupMessage:" + group if group
                                   else "adapter:FriendMessage:" + account)
        self.extra = {}

    def get_self_id(self):
        return "bot-account"

    def get_sender_id(self):
        return self.account

    def get_group_id(self):
        return self.group

    def get_extra(self, key):
        return self.extra.get(key)

    def set_extra(self, key, value):
        self.extra[key] = value


async def application(tmp_path, config=None):
    host, native = Host(), NativeConfig(config or {})
    app = Application(host, native, tmp_path, bridge_factory=TestBridge)
    await app.initialize()
    return app, host, native


@pytest.mark.asyncio
async def test_default_chat_without_model_and_unique_suffix(tmp_path):
    app, host, native = await application(tmp_path)
    try:
        message = Message(body="我很难过")
        await app.on_message(message)
        assert message.extra["livingemotion:ingest"] == "accepted"
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert context.instance_id == app.instance_id != "local"
        request = SimpleNamespace(extra_user_content_parts=[SimpleNamespace(text="host block")])
        await app.on_llm_request(message, request)
        await app.on_llm_request(message, request)
        assert len(request.extra_user_content_parts) == 2
        assert request.extra_user_content_parts[-1].text.startswith(SUFFIX)
        assert host.prompt not in request.extra_user_content_parts[-1].text
        state = await app.console_state()
        assert state["observation"]["subject"] == "human"
        assert state["bot_state"]["dimensions"]["pleasure"] >= 0.5
        assert state["night"]["energy"] <= 1
        assert state["relationship"]["raw"] > 0
        assert (await app.console_records(context.account_key, "emotion"))["total"] == 1
        assert (await app.console_preview(context.account_key))["model_calls"] == 0
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_console_reports_native_reply_confirmation_unsupported(tmp_path):
    app, host, _ = await application(tmp_path)
    try:
        state = await app.console_state()
        confirmation = next(row for row in state["health"] if row["name"] == "reply_confirmation")
        assert confirmation["status"] == "unavailable"
        assert "unsupported" in confirmation["reason"] and "120" in confirmation["reason"]
        assert "after-sent/bool/None" in confirmation["reason"]
        assert callable(app.confirm_reply) and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_config_cas_disable_restore_and_three_reload(tmp_path):
    app, host, native = await application(tmp_path)
    instance = app.instance_id
    try:
        revision = app.revision
        await app.update_config({"enabled": False}, expected_revision=revision,
                                actor_id="verified", reason="test disable")
        assert app.runtime.health()["workers"] == 0 and app._scheduler is None
        message = Message()
        await app.on_message(message)
        assert "livingemotion:context" not in message.extra
        with pytest.raises(ApplicationError, match="Configuration changed"):
            await app.update_config({"enabled": True}, expected_revision=revision,
                                    actor_id="verified", reason="stale")
        native["enabled"] = True
        await app.refresh_config()
        assert app.runtime.health()["workers"] == 1
        assert (await app.api.get_capabilities())["mode"] == "active"
    finally:
        await app.terminate()
    for _ in range(3):
        app = Application(host, native, tmp_path, bridge_factory=TestBridge)
        await app.initialize()
        assert app.instance_id == instance
        await app.terminate()
    assert not [t for t in asyncio.all_tasks() if t.get_name().startswith("livingemotion-")
                and not t.done()]


@pytest.mark.asyncio
async def test_dynamic_scope_conflict_persona_change_and_sleep(tmp_path):
    app, host, native = await application(tmp_path)
    try:
        message = Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert await app.validate_context(context)
        host.prompt = "Changed native character"
        assert not await app.validate_context(context)
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        host.congling = SimpleNamespace(enabled_for=lambda event: False)
        assert app.effective_mode(context) == "active"
        host.congling.enabled_for = lambda event: True
        assert app.effective_mode(context) == "observe_only"
        request = SimpleNamespace(extra_user_content_parts=[SimpleNamespace(text=SUFFIX + "old")])
        await app.on_llm_request(message, request)
        assert request.extra_user_content_parts == []
        host.congling = None
        await app.advance_scope(context, action="night.sleep")
        assert not (await app.api.get_availability(context))["block_chat"]
        native["night_block_chat"] = True
        await app.refresh_config()
        assert (await app.api.get_availability(context))["block_chat"]
        assert not (await app.availability(context, exempt=True)).block_chat
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_relationship_projection_shared_without_local_fallback(tmp_path, monkeypatch, available):
    app, host, _ = await application(tmp_path)
    try:
        message = Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        record = await app.store.get_state(context, "relationship", context.account_id)
        calls = []
        projected = Relationship(score=777, identity_revision=context.identity_revision)

        async def projection(store, identities, identity, *, event=None, record=None):
            assert store is app.store and identities is app.bridge.identity
            source = app.bridge.source(context)
            assert identity is source.identity and event is message
            calls.append(record)
            return projected if available else None

        monkeypatch.setattr(
            "astrbot_plugin_livingemotion.runtime.application.read_relationship_projection",
            projection,
        )
        result = await app.api.get_relationship(context)
        assert calls[0] == record
        snapshot = await app.current_snapshot(context)
        request = SimpleNamespace(extra_user_content_parts=[SimpleNamespace(text=SUFFIX + "old")])
        await app.on_llm_request(message, request)
        state = await app.console_state(context.account_key)
        if available:
            assert result["data"]["score"] == snapshot.relationship.score == 777
            expression = json.loads(request.extra_user_content_parts[0].text.split("\n")[-1])
            assert expression["relationship"]["score"] == state["relationship"]["raw"] == 777
        else:
            assert result["status"] == "unavailable" and result["reason_code"] == "context_changed"
            assert snapshot is None and request.extra_user_content_parts == []
            assert state["relationship"] is None
        assert (await app.store.get_state(context, "relationship", context.account_id)) == record
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["behavior", "expression", "console"])
async def test_relationship_use_revalidates_after_later_await(tmp_path, monkeypatch, consumer):
    app, host, _ = await application(tmp_path)
    try:
        message = Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        original = app.night_snapshot

        async def changed(context):
            state = await original(context)
            host.prompt = "Different native persona"
            return state

        monkeypatch.setattr(app, "night_snapshot", changed)
        if consumer == "behavior":
            assert await app.current_snapshot(context) is None
        elif consumer == "expression":
            request = SimpleNamespace(extra_user_content_parts=[])
            await app.on_llm_request(message, request)
            assert request.extra_user_content_parts == []
        else:
            assert (await app.console_state(context.account_key))["relationship"] is None
        assert await app.current_relationship(context) is None
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("unresolved", [False, True])
async def test_history_keeps_real_counts_and_absolute_cooldown(tmp_path, monkeypatch, unresolved):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        native.update(autonomy_enabled=True, autonomy_scopes=context.scope_key)
        await app.refresh_config()
        policy = app.behavior.policy
        app.behavior.policy = lambda: replace(policy(), min_score=0, cooldown_seconds=1)
        raw = {
            "global_used": 0, "scope_used": 0, "unanswered_count": 0,
            "last_attempt_at": None, "cooldown_until": clock[0] + 60,
            "reason_codes": ("legacy_scope_unresolved",) if unresolved else (),
        }

        async def history(ctx, period, exclude):
            assert ctx == context
            return dict(raw)

        monkeypatch.setattr(app.store, "behavior_history", history)
        before = await app.behavior_history(context, "2026-11-05", None)
        assert before.global_used == before.scope_used == before.unanswered_count == 0
        assert before.last_attempt_at is None and before.cooldown_until == raw["cooldown_until"]
        initial = await app.behavior.evaluate(context)
        assert not initial.eligible and "cooldown" in initial.reason_codes
        clock[0] += 61
        released = await app.behavior.evaluate(context)
        if unresolved:
            assert not released.eligible and "legacy_scope_unresolved" in released.reason_codes
        else:
            assert released.eligible
        assert before == await app.behavior_history(context, "2026-11-05", None)
        assert host.sends == 0 and binding.calls == []
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_sqlite_experience_pin_and_all_source_generation_atomic(tmp_path, le_context):
    store = SQLiteStore(tmp_path / "test.db")
    await store.open()
    try:
        now = store.clock()
        other = replace(le_context, scene_id="other")
        entry = Experience("entry", le_context, "dream", "day", now, "Dream (imagined): hello",
                           expires_at=now + 86400)
        await store.clear_scope(other, 0)
        result = await store.save_experience_guarded(entry, ((le_context, 0), (other, 0)))
        assert result["status"] == "rejected"
        assert await store.load_experience("entry") is None
        assert (await store.save_experience_guarded(
            entry, ((le_context, 0), (other, 1))))["status"] == "created"
        updated = replace(entry, pinned=True, clarity=0.8)
        assert (await store.pin_experience(entry, updated, 0, actor_id="verified",
                                          reason="pin"))["status"] == "updated"
        assert (await store.pin_experience(entry, updated, 0, actor_id="verified",
                                          reason="stale"))["status"] == "rejected"
        assert len(await store.audit_records(le_context)) == 1
    finally:
        await store.close()
    reopened = SQLiteStore(tmp_path / "test.db")
    await reopened.open()
    try:
        loaded, generation = await reopened.load_experience("entry")
        assert loaded.pinned and loaded.clarity == 0.8 and generation == 0
    finally:
        await reopened.close()


class Binding:
    fingerprint = "synthetic-binding"

    def __init__(self):
        self.calls = []
        self.started = asyncio.Event()
        self.release = None

    def count(self, system, data):
        return len((system + data).encode("utf-8")) + (256 if system else 0)

    async def generate(self, system, data, output_tokens, timeout):
        self.calls.append((system, data, output_tokens, timeout))
        self.started.set()
        if self.release:
            await self.release.wait()
        return ('Hello again.' if system.startswith("Write one short")
                else '{"body":"A quiet synthetic day."}')


async def generation_app(tmp_path):
    app, host, native = await application(tmp_path, {
        "timezone": "UTC", "diary_at": "00:00", "diary_enabled": True,
        "dream_enabled": True, "model_input_tokens": 16384,
    })
    clock = [datetime(2026, 11, 5, 23, 10, tzinfo=timezone.utc).timestamp()]
    app.store.clock = lambda: clock[0]
    app.memory.clock = lambda: clock[0]
    message = Message()
    await app.on_message(message)
    context = Context.from_dict(message.extra["livingemotion:context"])
    binding = Binding()

    async def model_binding(source):
        if not await app.validate_context(source):
            raise ValueError("context_changed")
        return binding

    app.model_binding = model_binding
    return app, host, native, message, context, binding, clock


@pytest.mark.asyncio
async def test_diary_shared_worker_persistent_pin_and_duplicate(tmp_path):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        service = await app.experience_service(context)
        queued = await service.queue_diary(context, persona_text=host.prompt)
        assert queued["status"] == "queued", queued
        await asyncio.wait_for(app.runtime.join(), 2)
        assert service.outcome(queued["job_id"])["status"] == "created"
        entry, _ = await app.store.load_experience(queued["experience_id"])
        assert entry.evidence and entry.body == "A quiet synthetic day."
        pinned = await app.pin_experience(context.account_key, entry.experience_id,
                                          pinned=True, actor_id="verified", reason="retain")
        assert pinned["status"] == "updated"
        assert (await app.store.load_experience(entry.experience_id))[0].pinned
        assert (await app.store.audit_records(context))[0]["action"] == "experience.pin"
        assert (await service.queue_diary(context))["status"] == "duplicate"
        assert len(binding.calls) == 1 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["human", "persona", "clear"])
@pytest.mark.parametrize("stage", ["queued", "generating"])
async def test_experience_invalidated_before_dispatch_or_save(tmp_path, change, stage):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    release, started = asyncio.Event(), asyncio.Event()
    newer = None
    try:
        if stage == "queued":
            async def occupy_worker():
                started.set()
                await release.wait()
            await app.runtime.submit("occupy", context, 0, occupy_worker)
            await started.wait()
        else:
            binding.release = release
        service = await app.experience_service(context)
        queued = await service.queue_diary(context, persona_text=host.prompt)
        assert queued["status"] == "queued", queued
        if stage == "generating":
            await asyncio.wait_for(binding.started.wait(), 2)
        if change == "human":
            newer = Message("m2", "a new human message")
            await app.on_message(newer)
        elif change == "persona":
            host.prompt = "Changed persona"
        else:
            await app.clear_context(context.account_key, expected_generation=0,
                                    actor_id="verified", reason="clear during work")
        release.set()
        await asyncio.wait_for(app.runtime.join(), 2)
        assert await app.store.load_experience(queued["experience_id"]) is None
        assert len(binding.calls) == (stage == "generating")
        assert service.outcome(queued["job_id"])["status"] in ("failed", "cancelled")
        assert host.sends == 0
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_behavior_shared_worker_unknown_history_and_clear(tmp_path):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        native.update(autonomy_enabled=True, autonomy_scopes=context.scope_key)
        await app.refresh_config()
        relation = await app.store.get_state(context, "relationship", context.account_id)
        await app.correct_relationship(context.account_key, expected_version=relation.version,
                                       score=900, reason="synthetic", actor_id="verified")
        result = await asyncio.wait_for(app.behavior.execute(context, intent_id="logical-1"), 2)
        assert result.status == "unknown", result
        assert result.sender_calls == 1 and host.sends == 1
        assert len(binding.calls) == 1 and result.receipt_recorded is False
        again = await app.behavior.execute(context, intent_id="logical-1")
        assert again.status == "unknown" and again.sender_calls == 0
        history = await app.store.behavior_history(context, "2026-11-05")
        assert history["global_used"] == history["scope_used"] == history["unanswered_count"] == 1
        other = replace(context, scene_id="other", account_id="other")
        await app.store.reserve_quota("other-purpose", other, 0, period="2026-11-05",
                                      purpose="another-sender", pool="send", limit=10)
        assert (await app.store.behavior_history(context, "2026-11-05"))["global_used"] == 2
        await app.clear_context(context.account_key, expected_generation=0,
                                actor_id="verified", reason="clear")
        history = await app.store.behavior_history(context, "2026-11-06")
        assert history["global_used"] == 0 and history["unanswered_count"] == 1
        assert history["last_attempt_at"] == clock[0]
        assert (await app.behavior.execute(context, intent_id="logical-1")).sender_calls == 0
        assert host.sends == 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_wake_catchup_revalidated_and_scheduled_sleep_waits_for_receipt(tmp_path):
    from astrbot_plugin_livingemotion.contracts import NightPhase
    from astrbot_plugin_livingemotion.domain.night import ReplyReceipt
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        native.update(autonomy_enabled=True, autonomy_scopes=context.scope_key,
                      night_schedule_enabled=True, sleep_at="23:00", wake_at="08:00")
        await app.refresh_config()
        relation = await app.store.get_state(context, "relationship", context.account_id)
        await app.correct_relationship(context.account_key, expected_version=relation.version,
                                       score=900, reason="synthetic", actor_id="verified")
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        night = await app.advance_scope(context)
        assert night.phase == NightPhase.SETTLING
        await app.confirm_reply(ReplyReceipt(context, "unknown", clock[0], message_id="m1"))
        assert (await app.night_snapshot(context)).phase == NightPhase.SETTLING
        await app.confirm_reply(ReplyReceipt(context, "succeeded", clock[0], message_id="wrong"))
        assert (await app.night_snapshot(context)).phase == NightPhase.SETTLING
        await app.confirm_reply(ReplyReceipt(context, "succeeded", clock[0], message_id="m1"))
        assert (await app.night_snapshot(context)).phase == NightPhase.ASLEEP
        await app.advance_scope(context, action="night.wake")
        tasks = tuple(app._actions)
        await asyncio.wait_for(asyncio.gather(*tasks), 2)
        assert host.sends == 1
        assert '"kind":"summary"' in binding.calls[0][1]
        assert "hello" in binding.calls[0][1]
        await app.advance_scope(context)
        record = await app.store.get_state(context, "night")
        assert "summary" not in record.value["_runtime"]["catchup"]
        assert host.sends == 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_emotion_refinement_is_async_and_does_not_double_count(tmp_path):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()
    try:
        native["emotion_model_enabled"] = True
        await app.refresh_config()

        async def generate(system, data, output_tokens, timeout):
            started.set()
            await release.wait()
            return '{"rule_version":"emotion-1","delta":{"pleasure":0.04},"confidence":1}'

        binding.generate = generate
        newer = Message("refine-message", "a neutral synthetic message")
        await asyncio.wait_for(app.on_message(newer), 1)
        await asyncio.wait_for(started.wait(), 1)
        before = await app.store.get_state(context, "bot")
        ledger = await app.store.relationship_ledger(context)
        relationship = await app.store.get_state(context, "relationship", context.account_id)
        release.set()
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 2)
        after = await app.store.get_state(context, "bot")
        assert after.version == before.version + 1
        assert after.value["pleasure"] > before.value["pleasure"]
        assert len(await app.store.read_window(context)) == 2
        assert await app.store.relationship_ledger(context) == ledger
        assert await app.store.get_state(context, "relationship", context.account_id) == relationship
        records = await app.console_records(context.account_key, "emotion")
        assert records["total"] == 2
        assert any("model_refined" in item["reason_codes"] for item in records["items"])
        assert host.sends == 0
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_live_rem_dream_persists_imagined_and_pin_freezes_clarity(tmp_path):
    from astrbot_plugin_livingemotion.contracts import NightState
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        record = await app.store.get_state(context, "night")
        night = NightState(phase="asleep", sleep_started_at=clock[0] - 3601,
                           wake_at=clock[0] + 7200, updated_at=clock[0])
        await app.store.write_states(context, 0, (StateWrite("night", to_dict(night), record.version),))
        service = await app.experience_service(context)
        queued = await service.queue_dream(context, await app.night_snapshot(context),
                                           persona_text=host.prompt)
        assert queued["status"] == "queued", queued
        await asyncio.wait_for(app.runtime.join(), 2)
        assert service.outcome(queued["job_id"])["status"] == "created"
        entry, _ = await app.store.load_experience(queued["experience_id"])
        assert entry.body.startswith("Dream (imagined):") and entry.kind.value == "dream"
        clock[0] += 60
        result = await app.pin_experience(context.account_key, entry.experience_id,
                                         pinned=True, actor_id="verified", reason="retain dream")
        assert result["status"] == "updated"
        pinned = (await app.store.load_experience(entry.experience_id))[0]
        assert pinned.pinned and 0 < pinned.clarity < entry.clarity
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_model_input_limit_rejects_before_dispatch(tmp_path):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        native["model_input_tokens"] = 1
        await app.refresh_config()
        service = await app.experience_service(context)
        result = await service.queue_diary(context, persona_text=host.prompt)
        assert result["status"] == "rejected" and result["reason_code"] == "input_token_limit"
        assert not binding.calls and host.sends == 0
    finally:
        await app.terminate()
