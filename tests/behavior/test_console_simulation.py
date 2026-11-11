"""SQLite-backed simulation and unified logs; synthetic providers never send."""
import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from astrbot_plugin_livingemotion.contracts import (
    ActorRole, BehaviorIntent, BotAffect, Event, StateWrite, to_dict,
)
from astrbot_plugin_livingemotion.adapters.astrbot import AstrBotBridge
from astrbot_plugin_livingemotion.adapters.weather import OpenMeteoWeather, WeatherReport
from astrbot_plugin_livingemotion.domain.dreaming import six_emotions
from astrbot_plugin_livingemotion.services.manual_experience import accepted_day
from astrbot_plugin_livingemotion.runtime.application import Application
from astrbot_plugin_livingemotion.runtime.models import ModelUnavailable
from astrbot_plugin_livingemotion.runtime.console import ApplicationError
from astrbot_plugin_livingemotion.storage.behavior_logs import simulation_record


class NativeConfig(dict):
    def save_config(self):
        self.saved = dict(self)


class Host:
    def __init__(self):
        self.sends = 0
        self.persona_manager = self
        self.conversation_manager = self
    def get_registered_star(self, name):
        return None
    async def get_curr_conversation_id(self, route):
        return None
    async def resolve_selected_persona(self, **kwargs):
        return "native", {"prompt": "Synthetic persona"}, None, False
    async def get_persona(self, identifier):
        return SimpleNamespace(system_prompt="Synthetic persona " + identifier, begin_dialogs=[])
    async def get_current_chat_provider_id(self, route):
        raise ValueError("no provider")
    async def send_message(self, route, chain):
        self.sends += 1
        return True


class TestBridge(AstrBotBridge):
    __test__ = False
    text_part = staticmethod(lambda text: SimpleNamespace(text=text))
    chain = staticmethod(lambda text: text)


class Message:
    def __init__(self, identifier, account="12345678"):
        self.platform_meta = SimpleNamespace(id="adapter", name="aiocqhttp")
        self.message_obj = SimpleNamespace(message_id=identifier, timestamp=0)
        self.message_str = "synthetic human message"
        self.unified_msg_origin = "adapter:FriendMessage:" + account
        self.account, self.extra = account, {}
    def get_self_id(self):
        return "synthetic-bot"
    def get_sender_id(self):
        return self.account
    def get_group_id(self):
        return ""
    def get_extra(self, key):
        return self.extra.get(key)
    def set_extra(self, key, value):
        self.extra[key] = value


class SimulationBinding:
    def __init__(self):
        self.calls = []
        self.error = None
        self.release = asyncio.Event()
        self.release.set()
        self.started = asyncio.Event()

    def count(self, system, data):
        return len(system.encode()) + len(data.encode())

    async def generate(self, system, data, output, timeout):
        self.calls.append((system, json.loads(data), output, timeout))
        self.started.set()
        await self.release.wait()
        if self.error:
            raise self.error
        return "今天心情不错，想和你聊聊。"


async def setup(tmp_path):
    host = Host()
    native = NativeConfig({"enabled": False, "mode": "observe_only", "diary_enabled": False,
        "dream_enabled": False, "persona_mode": "explicit", "persona_id": "native",
        "timezone": "Asia/Shanghai", "model_input_tokens": 8192, "model_output_tokens": 1024})
    app = Application(host, native, tmp_path, bridge_factory=TestBridge)
    await app.initialize()
    app.store.clock = lambda: 1794229200.0
    binding = SimulationBinding()
    async def select(purpose, route=None):
        if purpose != "behavior":
            raise ModelUnavailable("model_unavailable")
        return binding
    app._select_model_binding = select
    return app, binding, host, native


async def submit(app, emotion="current", request_id=None, actor_id="verified-admin"):
    return await app.console_behavior_simulate(
        persona_id="native", emotion=emotion, request_id=request_id or str(uuid4()),
        actor_id=actor_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("emotion", ["current", "calm", "joy", "sadness", "anger", "fear", "surprise", "disgust"])
async def test_no_source_no_material_disabled_observe_generates(emotion, tmp_path):
    app, model, host, _ = await setup(tmp_path)
    try:
        result = await submit(app, emotion)
        assert result["status"] == "completed" and result["sends"] == 0
        assert len(model.calls) == 1 and model.calls[0][1]["materials"] == []
        assert model.calls[0][1]["tone"] and model.calls[0][1]["emotion"] == result["emotion_label"]
        logs = await app.console_records(kind="behavior", persona_id="native")
        assert logs["total"] == 1
        item = logs["items"][0]
        assert item["send_id"] == result["request_id"] and item["content"] == result["text"]
        assert item["simulated"] and item["replied"] is False and item["target_id"] == ""
        assert item["timestamp"] == result["created_at"] == 1794229200.0
        assert bool(item["emotion_snapshot"]) == (emotion == "current")
        assert host.sends == 0 and not app._contexts
        assert await app.store._run(lambda db: db.execute("SELECT COUNT(*) FROM intents").fetchone()[0]) == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_identity_retry_conflict_busy_and_failed_log(tmp_path):
    app, model, host, _ = await setup(tmp_path)
    try:
        with pytest.raises(ApplicationError):
            await submit(app, actor_id="")
        assert model.calls == []
        result = await submit(app, "anger")
        assert (await submit(app, "anger", result["request_id"]))["text"] == result["text"]
        assert len(model.calls) == 1
        with pytest.raises(ApplicationError, match="另一条测试"):
            await submit(app, "joy", result["request_id"])
        model.release.clear()
        model.started.clear()
        task = asyncio.create_task(submit(app, "fear"))
        await model.started.wait()
        with pytest.raises(ApplicationError, match="仍在生成"):
            await submit(app)
        model.release.set()
        await task
        model.error = TimeoutError()
        failed = await submit(app)
        assert failed["status"] == "failed" and failed["reason_code"] == "model_timeout"
        assert (await submit(app, request_id=failed["request_id"]))["status"] == "failed"
        assert len(model.calls) == 3 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_page_query_id_number_content_persona_isolation_and_real_capture(tmp_path):
    app, model, host, _ = await setup(tmp_path)
    try:
        for number in range(12):
            result = await submit(app, "joy")
        rows = await app.console_records(kind="behavior", persona_id="native", page=1)
        assert len(rows["items"]) == 10 and rows["total"] == 12
        assert (await app.console_records(kind="behavior", persona_id="native", page=2))["total"] == 12
        assert (await app.console_records(kind="behavior", persona_id="other"))["total"] == 0
        assert (await app.console_records(kind="behavior", persona_id="native", query=result["request_id"]))["total"] == 1
        await app.update_config({"enabled": True}, expected_revision=app.config_revision,
                                reason="synthetic ingestion", actor_id="admin")
        await app.on_message(Message("base", account="12345678"))
        context = next(iter(app._contexts.values()))
        generation = await app.store.get_generation(context)
        now = app.store.clock()
        intent = BehaviorIntent("unique-real-send-id", context, "proactive", now, now + 300,
                                generation=generation, human_watermark=await app.store.human_watermark(context))
        await app.store.create_intent(intent)
        # Keep this a storage-only transition: no platform send is involved.
        await app.store._run(lambda db: db.execute(
            "UPDATE intents SET status='generating' WHERE intent_id=?", (intent.intent_id,)))
        app.store.clock = lambda: now + 3
        changed = await app.store.transition_intent(context, intent.intent_id, generation,
            expected_status="generating", status="sending", reason_code="synthetic",
            content="这里是确实留存的发送正文。", emotion_snapshot="happy,excited")
        assert changed["status"] == "updated"
        logs = await app.console_records(kind="behavior", persona_id="native", query="12345678")
        assert logs["total"] == 1 and logs["items"][0]["target_id"] == "12345678"
        assert not logs["items"][0]["replied"]
        assert logs["items"][0]["timestamp"] == now + 3
        assert logs["items"][0]["created_at"] == now
        assert logs["items"][0]["emotion_snapshot"] == "happy,excited"
        app.store.clock = lambda: now + 5
        await app.on_message(Message("reply", account="12345678"))
        logs = await app.console_records(kind="behavior", persona_id="native", query="留存的发送正文")
        assert logs["items"][0]["replied"] is True
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_model_failure_and_reload_never_repeat_paid_request(tmp_path):
    app, model, _, _ = await setup(tmp_path)
    result = await submit(app)
    await app.terminate()
    app, model, _, _ = await setup(tmp_path)
    try:
        replay = await submit(app, request_id=result["request_id"])
        assert replay["status"] == "completed" and not model.calls
        row = await simulation_record(app.store, result["request_id"])
        row["status"] = "running"
        await simulation_record(app.store, result["request_id"], row)
        assert (await submit(app, request_id=result["request_id"]))["status"] == "running"
        assert not model.calls
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_historical_body_requires_exact_receipt_and_same_scope(tmp_path):
    app, _, host, _ = await setup(tmp_path)
    try:
        await app.update_config({"enabled": True}, expected_revision=app.config_revision,
                                reason="synthetic ingestion", actor_id="admin")
        await app.on_message(Message("history", account="12345678"))
        context = next(iter(app._contexts.values()))
        generation, now = await app.store.get_generation(context), app.store.clock()
        intent = BehaviorIntent("historical-intent-id", context, "proactive", now, now + 300,
                                generation=generation)
        await app.store.create_intent(intent)
        await app.store._run(lambda db: db.execute(
            "UPDATE intents SET status='succeeded',attempted_at=?,value_json="
            "json_set(value_json,'$.transport_receipt',json(?)) WHERE intent_id=?",
            (now, '{"status":"confirmed","receipt_id":"exact-receipt"}', intent.intent_id)))
        event = Event("synthetic-bot-event", "livingemotion.behavior", "bot_action_succeeded",
                      context, ActorRole.BOT, now, "exact-receipt",
                      actor_id=context.bot_id, body="回执对应的历史正文")
        await app.store.commit_event(event, generation)
        logs = await app.console_records(kind="behavior", persona_id="native", query="历史正文")
        assert logs["total"] == 1 and logs["items"][0]["content"] == "回执对应的历史正文"
        assert logs["items"][0]["emotion_snapshot"] == ""
        await app.store._run(lambda db: db.execute(
            "UPDATE intents SET value_json=json_set(value_json,"
            "'$.transport_receipt.receipt_id','wrong-receipt') WHERE intent_id=?",
            (intent.intent_id,)))
        logs = await app.console_records(kind="behavior", persona_id="native")
        assert logs["items"][0]["content"] == ""
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_real_local_materials_and_emotion_overlay_do_not_mutate_affect(tmp_path):
    app, model, host, _ = await setup(tmp_path)
    try:
        await app.update_config({"enabled": True}, expected_revision=app.config_revision,
                                reason="synthetic ingestion", actor_id="admin", receipt="config")
        await app.on_message(Message("material"))
        context = next(iter(app._contexts.values()))
        before = await app.store.get_state(context, "bot")
        await submit(app, "anger")
        await submit(app, "joy")
        after = await app.store.get_state(context, "bot")
        assert before == after
        assert "synthetic human message" in model.calls[0][1]["materials"]
        assert model.calls[0][1]["tone"] != model.calls[1][1]["tone"]
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("weather,code,axis,bonus", [
    ("rain", 61, "sadness", .2),
    ("sun", 0, "joy", .2),
    ("snow", 73, "affection", .4),
    ("storm", 95, "fear", .25),
    ("cloud", 3, "sadness", .1),
    ("unavailable", None, "sadness", 0),
    ("wrong_day", 61, "sadness", 0),
    ("no_city", 61, "sadness", 0),
])
async def test_simulation_weather_matches_page_without_compounding(
        tmp_path, monkeypatch, weather, code, axis, bonus):
    app, model, host, native = await setup(tmp_path)
    try:
        calls = []

        async def get_weather(client, city, day, zone):
            calls.append((city, day, zone))
            return WeatherReport(
                city, "2000-01-01" if weather == "wrong_day" else day, zone,
                "unavailable" if weather == "unavailable" else "ok", code=code,
            )

        async def get_current_weather(client, city, zone):
            day, _ = accepted_day(app.store.clock(), zone)
            return await get_weather(client, city, day, zone)

        # Config refresh recreates the client; stub every instance before enabling weather.
        monkeypatch.setattr(OpenMeteoWeather, "get", get_weather)
        monkeypatch.setattr(OpenMeteoWeather, "get_current", get_current_weather)
        native.update(enabled=True, home_city="" if weather == "no_city" else "成都")
        await app.refresh_config()
        await app.on_message(Message("weather-source"))
        context = next(iter(app._contexts.values()))
        record = await app.store.get_state(context, "bot")
        affect = BotAffect(pleasure=-.75, arousal=.2, stress=.4,
                           labels=("sad",), updated_at=app.store.clock())
        generation = await app.store.get_generation(context)
        saved = await app.store.write_states(context, generation, (
            StateWrite("bot", to_dict(affect), record.version, owner=record.owner),
        ))
        assert saved.status == "accepted"
        before = await app.store.get_state(context, "bot")
        page = await app.console_state(persona_id="native", view_scope="global")
        displayed = page["emotion_analysis"]["bot"]["emotions"]
        assert displayed[axis] == round(min(1, six_emotions(affect)[axis] + bonus), 4)

        for emotion in ("current", "current", "anger"):
            result = await submit(app, emotion)
            assert result["status"] == "completed" and result["sends"] == 0
            data = model.calls[-1][1]
            assert data["current_emotions"] == displayed
            if emotion == "current":
                assert json.loads(data["tone"].split("：", 1)[1]) == displayed
            else:
                assert data["emotion"] == "愤怒" and "表达不满" in data["tone"]
        assert await app.store.get_state(context, "bot") == before
        assert host.sends == 0
        if weather == "no_city":
            assert calls == []
        else:
            assert calls and all(city == "成都" and zone == "Asia/Shanghai"
                                 for city, _, zone in calls)
    finally:
        await app.terminate()
