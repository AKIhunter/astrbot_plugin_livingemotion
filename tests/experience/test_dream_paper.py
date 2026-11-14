"""Numeric weather/history and owner-notification checks; all transports synthetic."""
from dataclasses import replace
import json
import random
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.adapters.weather import WeatherReport
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BotAffect, Experience, NightState, StateWrite, to_dict
from astrbot_plugin_livingemotion.domain.dreaming import (
    DEFAULT_THEMES, EMOTIONS, apply_bonus, dream_profile, six_emotions, theme_pool,
    weather_affect, weather_bonus,
)
from astrbot_plugin_livingemotion.domain.night import advance_life, LifePolicy
from astrbot_plugin_livingemotion.runtime.night import NightRuntime
from astrbot_plugin_livingemotion.runtime.projector import snapshot
from astrbot_plugin_livingemotion.services.behavior import BehaviorService, BehaviorPolicy, SendReceipt
from astrbot_plugin_livingemotion.tests.experience.test_manual_daily import make_app, submit, finish


def test_pool_and_seven_dream_tones():
    assert len(DEFAULT_THEMES) == 12
    assert theme_pool("赛博朋克，绿野仙踪\n生活日常，生活日常") == DEFAULT_THEMES[:3]
    for key in (*EMOTIONS, "calm"):
        profile = dream_profile({key: .8} if key != "calm" else {}, picker=random.Random(9))
        assert len(set(profile["themes"])) == 2
        assert profile["dominant"] == key and profile["tone"]
        assert profile["night_event"] == (key if key in ("anger", "fear") else "")
    assert dream_profile({"fear": .9}, nap=True)["night_event"] == ""
    with pytest.raises(ValueError):
        Config(dream_theme_pool="同一个，同一个")
    with pytest.raises(ValueError):
        dream_profile({"joy": float("nan")})


def test_surprise_counts_only_arousal_above_baseline():
    calm = six_emotions(BotAffect(arousal=0.3))
    assert calm["surprise"] == 0
    assert 0 < six_emotions(BotAffect(arousal=0.6))["surprise"] < \
        six_emotions(BotAffect(arousal=0.9))["surprise"]
    # 动态基准同样生效：基准抬高后，原来的唤醒值不再算兴奋。
    refined = BotAffect(arousal=0.6, baseline_refined=True, baseline_arousal=0.6)
    assert six_emotions(refined)["surprise"] == 0
    # 阴天全维 +0.1 不再把平静状态推过 0.25 标签阈值（原逻辑会显示「兴奋」）。
    bonus = weather_bonus(WeatherReport("成都", "2026-11-12", "Asia/Shanghai", "ok", code=3),
                          city="成都", day="2026-11-12", timezone="Asia/Shanghai")
    assert max(apply_bonus(calm, bonus).values()) < .25


@pytest.mark.asyncio
@pytest.mark.parametrize("affect", [
    BotAffect(),
    BotAffect(pleasure=.03611172758487537, arousal=.3482770126419815,
              stress=.007583487618904544, social_need=.24917923686372706,
              baseline_refined=True, baseline_arousal=.3144831037925945),
    BotAffect(arousal=.6, baseline_refined=True, baseline_arousal=.6),
    BotAffect(arousal=.9),
])
async def test_console_label_is_not_rewritten_by_weather(affect):
    from astrbot_plugin_livingemotion.runtime.console import Console, emotion_analysis

    class Cloudy:
        async def get(self, city, day, timezone):
            return WeatherReport(city, day, timezone, "ok", code=3)

    app = SimpleNamespace(config=Config(home_city="合成城市", timezone="UTC"),
                          store=SimpleNamespace(clock=lambda: 1794484800.0),
                          _manual_weather=Cloudy())
    # 空上下文走合成曲线；只检验真实控制台标签路径，不访问模型、网络或生产库。
    state = {"emotion_analysis": {"bot": emotion_analysis(affect)},
             "bot_state": {"emotion_analysis": emotion_analysis(affect), "label": "calm"}}
    await Console._attach_emotion_curve(app, state, None)
    # 阴天曾经把 label 改写成六情绪 dominant（arousal .9 -> excited），导致同一天里
    # 大标题有时来自五维阈值、有时来自六情绪；现在天气不进展示值，label 只看五维。
    assert state["bot_state"]["label"] == "calm"
    assert state["bot_state"]["emotion_analysis"]["emotions"] == (
        state["emotion_analysis"]["bot"]["emotions"])
    assert state["emotion_analysis"]["bot"]["emotions"] == six_emotions(affect)
    assert affect.labels == ("calm",)


@pytest.mark.parametrize("code,key,amount", [
    (0, "joy", .2), (61, "sadness", .2), (3, "joy", .1),
    (73, "affection", .4), (95, "fear", .25), (99, "fear", .25),
])
def test_exact_weather_replaceable_overlay(code, key, amount):
    report = WeatherReport("上海", "2026-11-09", "Asia/Shanghai", "ok", code=code)
    bonus = weather_bonus(report, city="上海", day="2026-11-09", timezone="Asia/Shanghai")
    assert bonus[key] == amount
    raw = dict.fromkeys(EMOTIONS, .8)
    once = apply_bonus(raw, bonus)
    assert once == apply_bonus(raw, bonus) and once[key] == min(1, .8 + amount)
    assert not any(weather_bonus(report, city="北京", day=report.day, timezone=report.timezone).values())
    assert not any(weather_bonus(report, city=report.city, day="2026-11-10", timezone=report.timezone).values())
    if code == 3:
        assert set(bonus.values()) == {.1}


@pytest.mark.parametrize("code,expected", [
    (0, (.040, .010, -.020, 0.0)),
    (61, (-.050, -.020, .030, .020)),
    (3, (-.020, 0.0, .010, 0.0)),
    (73, (.010, -.010, -.010, .050)),
    (95, (-.040, .050, .080, .020)),
])
def test_weather_drift_targets_four_axes_only(code, expected):
    """天气只给四维回落目标，永不产出六情绪键——六情绪保持纯函数投影。"""
    report = WeatherReport("上海", "2026-11-09", "Asia/Shanghai", "ok", code=code)
    assert weather_affect(report, city="上海", day="2026-11-09",
                          timezone="Asia/Shanghai") == expected
    assert weather_affect(report, city="北京", day="2026-11-09",
                          timezone="Asia/Shanghai") == (0.0, 0.0, 0.0, 0.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("shared", [False, True])
async def test_real_history_missing_decay_generation_and_body_free(le_store, le_context, shared):
    now = le_store.clock()
    owner = await le_store.initialize_state_mode(le_context, shared=shared)
    old = await le_store.get_state(le_context, "bot")
    written = await le_store.write_states(le_context, 0, (
        StateWrite("bot", to_dict(BotAffect(pleasure=.8, updated_at=now)),
                   expected_version=old.version if old else 0, owner=owner),))
    assert written.accepted, written
    points = await le_store.emotion_history(le_context, since=now - 86400, until=now)
    assert len(points) == 288 and all(p["emotions"] is None for p in points)
    le_store.clock = lambda: now + 600
    points = await le_store.emotion_history(le_context, since=now + 600 - 86400, until=now + 600)
    measured = [p["emotions"] for p in points if p["emotions"]]
    assert measured and measured[-1]["joy"] < .8
    assert "body" not in json.dumps(points) and le_context.account_id not in json.dumps(points)
    await le_store.clear_scope(le_context, 0)
    points = await le_store.emotion_history(le_context, since=now - 86400, until=now + 600)
    assert all(p["emotions"] is None for p in points)


@pytest.mark.asyncio
async def test_manual_themes_weather_but_no_owner_messages(tmp_path):
    app, model, _, _ = await make_app(tmp_path, {
        "home_city": "上海", "dream_owner_notify": True, "dream_owner_qq": "12345678"})
    class Snow:
        async def get(self, city, day, timezone):
            return WeatherReport(city, day, timezone, "ok", "雪，0–2°C", code=73)
    app.manual_experience.weather = Snow()
    try:
        await submit(app, "dream"); await finish(app)
        data = model.payloads[-1]
        assert len(set(data["dream"]["themes"])) == 2
        # 天气不再改写六情绪：没有互动的一天 dominant 仍是 calm，affection 停在
        # 五维推导的 0.105，不会被雪硬抬到 0.505。城市仍在 header 里（天气数据源）。
        assert data["dream"]["dominant"] == "calm"
        assert data["mood"]["emotions"]["affection"] == pytest.approx(.105, abs=1e-6)
        assert data["program_header"]["city"] == "上海"
        result = await app.store._run(lambda db: db.execute("SELECT count(*) FROM intents").fetchone()[0])
        assert result == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_weather_same_current_curve_and_expression_no_double_overlay(le_store, le_context):
    from datetime import datetime
    from astrbot_plugin_livingemotion.runtime.console import Console, emotion_analysis
    from astrbot_plugin_livingemotion.runtime.manual_experience import ManualExperienceRuntime
    now = le_store.clock()
    await le_store.register_context(le_context)
    affect = BotAffect(pleasure=.4, arousal=.3, stress=.2, updated_at=now)
    raw = six_emotions(affect)
    class Rain:
        async def get(self, city, day, timezone):
            return WeatherReport(city, day, timezone, "ok", code=61)
    async def history(*args, **kwargs):
        return [{"at": now, "emotions": dict(raw), "basis": "recorded_decay"}]
    app = SimpleNamespace(config=Config(home_city="上海", timezone="UTC"),
        store=SimpleNamespace(clock=le_store.clock, emotion_history=history), _manual_weather=Rain())
    # 雨天不再往六情绪上叠 0.2：愉悦为正时 negative=0，那是凭空造悲伤。
    expected = dict(raw)
    def state():
        return {"emotion_analysis": {"bot": emotion_analysis(affect)},
                "bot_state": {"emotion_analysis": emotion_analysis(affect), "label": "calm"}}
    first, refreshed = state(), state()
    await Console._attach_emotion_curve(app, first, le_context)
    await Console._attach_emotion_curve(app, refreshed, le_context)
    assert first == refreshed
    current = await ManualExperienceRuntime.weather_emotions(app, affect)
    assert current == first["emotion_analysis"]["bot"]["emotions"]
    assert current == first["bot_state"]["emotion_analysis"]["emotions"]
    assert current == first["emotion_curve"]["points"][0]["emotions"]
    assert current["sadness"] == expected["sadness"] == 0.0
    assert six_emotions(affect) == raw


class NightDouble(NightRuntime):
    def __init__(self, store, context):
        self.store, self.context = store, context
        self.config = Config(timezone="UTC", night_policy_version=2,
            dream_owner_notify=True, dream_owner_qq=context.account_id)
        self.closed, self.revision = False, "same-config"
        self.sent, self.outcome = [], "confirmed"
        self.guard_errors = []
        self.api = SimpleNamespace(ingest_event=self.ingest)
        self.behavior = BehaviorService(store, current=self.current, validate_identity=self.valid,
            validate_evidence=self.current, model=self.current, sender=self.sender,
            policy=lambda: BehaviorPolicy(timezone="UTC"), clock=store.clock)

    async def valid(self, c, generation=None):
        return c == self.context and (generation is None or generation == await self.store.get_generation(c))
    validate_context = valid
    def effective_mode(self, c): return self.config.mode if self.config.enabled else "disabled"
    async def current(self, *args): return None
    async def _ready_text(self, text): return text
    async def night_snapshot(self, c): return snapshot(await self.store.get_state(c, "night"), NightState)
    def _advance_life(self, state, now, runtime):
        return advance_life(state, now=now, policy=LifePolicy())
    async def ingest(self, event):
        result = await self.store.commit_event(event, await self.store.get_generation(event.context))
        return {"status": result.status}
    async def sender(self, request):
        try:
            allowed = await request.authorize()
        except Exception as exc:
            self.guard_errors.append(repr(exc))
            raise
        if not allowed:
            return SendReceipt(request.intent_id, request.context.route, "rejected")
        self.sent.append(request)
        return SendReceipt(request.intent_id, request.context.route, self.outcome,
                           "synthetic-receipt" if self.outcome == "confirmed" else None,
                           1 if self.outcome == "confirmed" else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["confirmed", "unknown"])
@pytest.mark.parametrize("guard", ["allowed", "owner_changed", "source_revoked",
    "night_disabled", "wake_changed", "notify_disabled", "recipient_changed",
    "manual", "nap", "muted", "observe"])
async def test_night_owner_guard_dedupe_unknown_and_wake(le_store, le_context, outcome, guard):
    now = le_store.clock()
    context = replace(le_context, platform="qq", account_id="12345678")
    await le_store.register_context(context)
    written = await le_store.write_states(context, 0, (StateWrite("night", to_dict(NightState(
        phase="asleep", display_state="deep_sleep", policy_version=2, energy=50, energy_units=500,
        updated_at=now, sleep_started_at=now - 3600, wake_at=now + 3600,
        cycle_id="synthetic-night", cycle_kind="night", cycle_started_at=now - 3600,
        deep_sleep_at=now - 1800))),))
    assert written.accepted, written
    profile = {**dream_profile({"fear": .9}), "automatic": True, "notify_enabled": True,
               "recipient": context.account_id, "cycle_id": "synthetic-night",
               "sleep_started_at": now - 3600, "wake_at": now + 3600}
    if guard == "manual":
        profile["automatic"] = False
    if guard == "nap":
        profile["nap"] = True
    if guard == "wake_changed":
        profile["wake_at"] = now + 1800
    entry = Experience("synthetic-dream", context, "dream", "synthetic-night", now,
                       "PRIVATE BODY MUST NEVER BE SENT", expires_at=now + 86400, dream_profile=profile)
    saved = await le_store.save_experience(entry, 0)
    assert saved["status"] == "created", saved
    app = NightDouble(le_store, context); app.outcome = outcome
    try:
        app.config = replace(app.config, dream_owner_notify=False)
        await app.maybe_dream_wake(context)
        assert not app.sent
        app.config = replace(app.config, dream_owner_notify=True)
        if guard == "owner_changed":
            await le_store.initialize_state_mode(context, shared=True)
        if guard == "source_revoked":
            async def revoked(*args): return False
            app.validate_context = revoked
        overrides = {
            "night_disabled": {"night_enabled": False},
            "notify_disabled": {"dream_owner_notify": False},
            "recipient_changed": {"dream_owner_qq": "87654321"},
            "muted": {"muted_scopes": context.scope_key},
            "observe": {"mode": "observe_only"},
        }
        app.config = replace(app.config, **overrides.get(guard, {}))
        await app.maybe_dream_wake(context)
        await app.maybe_dream_wake(context)
        intents = await le_store._run(lambda db: [dict(r) for r in db.execute(
            "SELECT status,reason_code FROM intents")])
        if guard != "allowed":
            assert not app.sent and not intents, (guard, intents, app.guard_errors)
            return
        assert len(app.sent) == 1, (intents, app.guard_errors)
        assert entry.body not in app.sent[0].text
        night = await app.night_snapshot(context)
        assert night.wake_session.startswith("dream:") and night.wake_window_deadline == now + 300
        after, _ = advance_life(night, now=now + 301, policy=LifePolicy())
        assert after.display_state.value == "deep_sleep"
        intent = await le_store.get_intent(context, app.sent[0].intent_id)
        assert intent["status"] == ("succeeded" if outcome == "confirmed" else "unknown")
        # 发送日志依赖这段正文；控制类发送也要在进入 sending 时落库。
        assert intent["value"]["content"] == app.sent[0].text
    finally:
        await app.behavior.close()
