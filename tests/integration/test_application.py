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
        self.sends = 0
        self.persona_manager = self
        self.conversation_manager = self

    def get_registered_star(self, name):
        return None

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
async def test_native_qq_names_and_number_grants_keep_private_group_separate(tmp_path):
    app, _, native = await application(tmp_path, {
        "autonomy_qq_ids": "12345678", "autonomy_qq_group_ids": "34567890",
    })
    try:
        cases = [
            Message("private", account="12345678"),
            Message("unlisted", account="23456789"),
            Message("group", group="34567890", account="23456789"),
            Message("same-number-wrong-kind", group="12345678", account="23456789"),
        ]
        for message in cases:
            message.message_obj.sender = SimpleNamespace(nickname="原生QQ名字")
            if message.group:
                message.message_obj.sender.nickname = "群名片"
                message.message_obj.raw_message = {
                    "sender": {"user_id": message.account, "nickname": "真正QQ名字", "card": "群名片"},
                }
            await app.on_message(message)
            assert message.extra["livingemotion:ingest"] == "accepted"
        contexts = {c.scene_id: c for c in app._contexts.values() if c.scene_kind.value == "private"}
        group_context = next(c for c in app._contexts.values() if c.scene_id == "34567890")
        grants = app.behavior_policy().whitelist
        assert contexts["12345678"].scope_key in grants
        assert group_context.scope_key in grants
        assert contexts["23456789"].scope_key not in grants
        # Group number equal to an allowed private QQ does not authorize that group.
        assert next(c for c in app._contexts.values() if c.scene_kind.value == "group"
                    and c.scene_id == "12345678").scope_key not in grants
        graph = await app.console_relationships(persona_id="native", view_scope="private", query="原生QQ")
        assert graph["total"] == 2
        group_graph = await app.console_relationships(persona_id="native", view_scope="group")
        assert group_graph["nodes"][0]["label"] == "真正QQ名字"
        native["autonomy_qq_ids"] = "99999999"
        await app.refresh_config()
        assert contexts["12345678"].scope_key not in app.behavior_policy().whitelist
        assert len(app.behavior_policy().whitelist) == 1  # The real group remains.
        native["autonomy_scopes"] = next(iter(app._contexts.values())).scope_key
        await app.refresh_config()
        await app.update_config({"autonomy_qq_ids": ""}, expected_revision=app.revision,
                                actor_id="verified", reason="clear number grants")
        assert native["autonomy_scopes"] == ""
        assert len(app.behavior_policy().whitelist) == 1
        with pytest.raises(ApplicationError, match="Unknown"):
            await app.update_config({"night_block_chat": True}, expected_revision=app.revision,
                                    actor_id="verified", reason="legacy setting rejected")
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_sender", [None, {"user_id": "99999999", "nickname": "别人的QQ名"}])
async def test_group_card_or_mismatched_raw_sender_is_not_cached(tmp_path, raw_sender):
    app, _, _ = await application(tmp_path)
    try:
        message = Message("unverified-name", group="34567890", account="12345678")
        message.message_obj.sender = SimpleNamespace(nickname="群名片")
        if raw_sender is not None:
            message.message_obj.raw_message = {"sender": raw_sender}
        await app.on_message(message)
        assert message.extra["livingemotion:ingest"] == "accepted"
        graph = await app.console_relationships(persona_id="native", view_scope="group")
        assert graph["nodes"][0]["label"] == "12345678"
        cached = await app.store._run(lambda db: db.execute(
            "SELECT COUNT(*) FROM runtime_meta WHERE key LIKE 'console.qq.nickname.v1:%'").fetchone()[0])
        assert cached == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_failed_application_initialize_closes_started_workers_and_store(tmp_path, monkeypatch):
    app = Application(Host(), NativeConfig({}), tmp_path, bridge_factory=TestBridge)

    async def fail_services():
        raise RuntimeError("synthetic startup failure")

    monkeypatch.setattr(app, "_build_services", fail_services)
    with pytest.raises(RuntimeError, match="synthetic startup failure"):
        await app.initialize()
    assert app.closed and app.lifecycle.store is None and app.lifecycle.runtime is None
    assert not app.api._active
    assert not [task for task in asyncio.all_tasks()
                if task.get_name().startswith("livingemotion-") and not task.done()]


@pytest.mark.asyncio
async def test_console_pin_uses_real_record_cas_and_never_calls_model(tmp_path, monkeypatch):
    app, host, _ = await application(tmp_path)
    try:
        message = Message(identifier="pin-source")
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        now = app.store.clock()
        entry = Experience("console-pin", context, "diary", "2026-11-06", now,
                           "A synthetic private diary.", expires_at=now + 60)
        generation = await app.store.get_generation(context)
        assert (await app.store.save_experience_guarded(
            entry, ((context, generation),)))["status"] == "created"

        async def no_model(*args, **kwargs):
            raise AssertionError("pinning must not select a model")

        monkeypatch.setattr(app, "model_binding", no_model)
        records = await app.console_records(context.account_key, "diary")
        assert records["items"][0]["context_id"] == context.account_key
        assert records["items"][0]["pin_available"]
        parameters = dict(expected_revision=app.revision, actor_id="dashboard-admin",
                          reason="retain", confirmed=True, entry_id=entry.experience_id,
                          pinned=True, expected_pinned=False)
        result = await app.console_action(context.account_key, "experience.pin", **parameters)
        assert result["status"] == "updated" and result["model_calls"] == result["sends"] == 0
        stored, _ = await app.store.load_experience(entry.experience_id)
        assert stored.pinned and stored.created_at == now and stored.expires_at == now + 60
        with pytest.raises(ApplicationError) as stale:
            await app.console_action(context.account_key, "experience.pin", **parameters)
        assert stale.value.code == "version_conflict"
        audit = await app.store.audit_records(context)
        assert len(audit) == 1 and audit[0]["actor_id"] == "dashboard-admin"
        assert host.sends == 0
        app.store.clock = lambda: now + 61
        await app.console_action(context.account_key, "experience.pin",
                                 **{**parameters, "pinned": False, "expected_pinned": True})
        with pytest.raises(ApplicationError) as expired:
            await app.console_action(context.account_key, "experience.pin", **parameters)
        assert expired.value.code == "forbidden"
    finally:
        await app.terminate()


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
async def test_config_revision_survives_reload_but_actions_do_not(tmp_path):
    app, host, native = await application(tmp_path)
    config_revision, action_revision = app.config_revision, app.revision
    assert app.config_dto()["revision"] == config_revision
    await app.terminate()
    app = Application(host, native, tmp_path, bridge_factory=TestBridge)
    await app.initialize()
    try:
        assert app.revision != action_revision
        assert app.config_revision == config_revision
        await app.update_config({"enabled": False}, expected_revision=config_revision,
                                actor_id="verified", reason="")
        assert native.saved["enabled"] is False
        assert app.config_revision != config_revision
        with pytest.raises(ApplicationError, match="Configuration changed"):
            await app.update_config({"enabled": True}, expected_revision=config_revision,
                                    actor_id="verified", reason="")
        assert native.saved["enabled"] is False
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_config_content_change_before_save_still_rejects_old_revision(tmp_path):
    app, _, native = await application(tmp_path)
    try:
        revision = app.config_revision
        native["diary_enabled"] = True
        with pytest.raises(ApplicationError, match="Configuration changed"):
            await app.update_config({"dream_enabled": True}, expected_revision=revision,
                                    actor_id="verified", reason="")
        assert app.config.diary_enabled is True
        assert app.config.dream_enabled is False
        assert not getattr(native, "saved", None)
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
async def test_local_mode_persona_change_and_sleep(tmp_path):
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
        assert app.effective_mode(context) == "active"
        native["mode"] = "observe_only"
        await app.refresh_config()
        assert app.effective_mode(context) == "observe_only"
        request = SimpleNamespace(extra_user_content_parts=[SimpleNamespace(text=SUFFIX + "old")])
        await app.on_llm_request(message, request)
        assert request.extra_user_content_parts == []
        native["mode"] = "active"
        await app.refresh_config()
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
            assert expression["relationship"]["raw_score"] == state["relationship"]["raw"] == 777
            assert expression["relationship"]["score"] == 77.7
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

    async def preflight(self):
        return {"http_status": 200, "reason_code": "model_preflight_ok"}

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
        assert entry.evidence and entry.body.endswith("A quiet synthetic day.")
        assert entry.body.startswith("日期：2026-11-05（UTC）\n城市：未配置\n天气：未获取\n")
        pinned = await app.pin_experience(context.account_key, entry.experience_id,
                                          pinned=True, actor_id="verified", reason="retain")
        assert pinned["status"] == "updated"
        assert (await app.store.load_experience(entry.experience_id))[0].pinned
        assert (await app.store.audit_records(context))[0]["action"] == "experience.pin"
        assert (await service.queue_diary(context))["reason_code"] == "daily_content_preserved"
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
        native.update(autonomy_enabled=True, autonomy_scopes=context.scope_key,
                      relationship_edit_enabled=True)
        await app.refresh_config()
        from astrbot_plugin_livingemotion.adapters.behavior_sender import AstrBotBehaviorSender
        # This fixture tests the fallback host bool, independent of native QQ receipts.
        app.behavior.sender = AstrBotBehaviorSender(host.send_message, make_chain=app.bridge.chain,
                                                   recorded_route=app.bridge.recorded_route)
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
                      night_schedule_enabled=True, sleep_at="23:00", wake_at="08:00",
                      relationship_edit_enabled=True)
        await app.refresh_config()
        from astrbot_plugin_livingemotion.adapters.behavior_sender import AstrBotBehaviorSender
        app.behavior.sender = AstrBotBehaviorSender(host.send_message, make_chain=app.bridge.chain,
                                                   recorded_route=app.bridge.recorded_route)
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
        refined_relation = await app.store.get_state(context, "relationship", context.account_id)
        assert refined_relation.value["score"] == relationship.value["score"]
        assert refined_relation.value["_runtime"] == relationship.value["_runtime"]
        assert refined_relation.version == relationship.version + 1
        assert refined_relation.value["_account_affect"]["state"]["pleasure"] > relationship.value[
            "_account_affect"]["state"]["pleasure"]
        records = await app.console_records(context.account_key, "emotion")
        assert records["total"] == 2
        assert any("model_refined" in item["reason_codes"] for item in records["items"])
        assert app.emotion_model_analysis([context])["status"] == "completed"
        assert host.sends == 0
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["none", "new_message", "clear", "cancel"])
async def test_refinement_retains_real_event_and_fences_late_result(tmp_path, change):
    import gc
    import weakref
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    release, started = asyncio.Event(), asyncio.Event()
    try:
        native["emotion_model_enabled"] = True
        await app.refresh_config()
        identity_validate = app.bridge.identity.validate
        async def require_real_event(snapshot, *, event=None):
            return event is not None and await identity_validate(snapshot, event=event)
        app.bridge.identity.validate = require_real_event
        async def generate(*_):
            started.set()
            await release.wait()
            return '{"rule_version":"emotion-1","delta":{"pleasure":0},"confidence":1}'
        binding.generate = generate
        newer = Message("retained-source", "neutral synthetic message")
        reference = weakref.ref(newer)
        await app.on_message(newer)
        del newer
        gc.collect()
        await asyncio.wait_for(started.wait(), 1)
        assert reference() is not None
        before = await app.store.get_state(context, "bot")
        ledger = await app.store.relationship_ledger(context)
        tasks = tuple(app._actions)
        if change == "new_message":
            followup = Message("later-source", "later interaction")
            # Suppress only the second model job; its rule projection still commits.
            native["emotion_model_enabled"] = False
            await app.refresh_config()
            await app.on_message(followup)
        elif change == "clear":
            await app.store.clear_scope(context, 0)
        elif change == "cancel":
            for task in tasks:
                task.cancel()
        expected = await app.store.get_state(context, "bot")
        release.set()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 2)
        after = await app.store.get_state(context, "bot")
        if change == "none":
            assert after.version == before.version + 1
            assert app.emotion_model_analysis([context])["status"] == "completed"
            assert await app.store.relationship_ledger(context) == ledger
            assert len(await app.store.read_window(context)) == 2
        else:
            assert after == expected
        gc.collect()
        assert reference() is None
        assert app.emotion_model_analysis([])["status"] == "uncollected"
        assert host.sends == 0
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,expected", [
    ("unsupported", "provider_budget_contract_unsupported"),
    ("missing", "model_unavailable"), ("invalid", "model_output_invalid"),
    ("timeout", "task_timeout"), ("quota", "quota_exhausted"),
    ("observe", "mode_unavailable"), ("disabled", "model_disabled"),
])
async def test_emotion_model_diagnostics_are_controlled(tmp_path, failure, expected):
    from astrbot_plugin_livingemotion.runtime.models import ModelUnavailable
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        native["emotion_model_enabled"] = failure != "disabled"
        if failure == "observe":
            native["mode"] = "observe_only"
        if failure == "quota":
            native["model_daily_limit"] = 1
        await app.refresh_config()
        if failure in ("unsupported", "missing"):
            async def unavailable(_):
                raise ModelUnavailable(expected)
            app.model_binding = unavailable
        async def generate(*_):
            if failure == "timeout":
                raise TimeoutError("PRIVATE_PROVIDER_TEXT_MUST_NOT_ESCAPE")
            return "not-json" if failure == "invalid" else (
                '{"rule_version":"emotion-1","delta":{"pleasure":0},"confidence":1}')
        binding.generate = generate
        if failure == "quota":
            await app.store.reserve_quota("used-model", context, 0, period="2026-11-05",
                                         purpose="diary", limit=1, global_limit=1)
        newer = Message("diagnostic-source", "Synthetic private text")
        await app.on_message(newer)
        if app._actions:
            await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 2)
        value = app.emotion_model_analysis([context])
        assert value["reason_code"] == expected
        assert value["status"] not in ("queued", "running")
        assert "PRIVATE_PROVIDER_TEXT" not in str(value) and "Synthetic private text" not in str(value)
        assert host.sends == 0
    finally:
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
        assert result["status"] == "rejected" and result["reason_code"] == "input_budget_too_small"
        assert not binding.calls and host.sends == 0
    finally:
        await app.terminate()
