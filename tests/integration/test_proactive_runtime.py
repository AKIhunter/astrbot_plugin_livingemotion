"""Real Application, timer, memory gateway and sender with synthetic model/host."""

import asyncio
import json
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.contracts import Context, NightState, SceneKind
from astrbot_plugin_livingemotion.ports.memory import MemoryRequest
from astrbot_plugin_livingemotion.storage.proactivity import read_schedule
from test_application import Message, generation_app


class RandomDraws:
    def __init__(self, draw=0, minutes=30):
        self.draw, self.minutes = draw, minutes

    def randint(self, low, high):
        return max(low, min(high, self.minutes))

    def random(self):
        return self.draw


async def proactive_app(tmp_path, *, draw=0):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    native.update(
        diary_enabled=False, dream_enabled=False, autonomy_enabled=True,
        autonomy_scopes=context.scope_key, behavior_random_min_minutes=30,
        behavior_random_max_minutes=30,
    )
    await app.refresh_config()
    app._proactive_random = RandomDraws(draw)
    return app, host, native, context, binding, clock


async def drain(app):
    await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)


@pytest.mark.asyncio
async def test_random_timer_uses_memory_relationship_mood_and_unknown_never_retries(tmp_path):
    app, host, _, context, binding, clock = await proactive_app(tmp_path)
    try:
        await app.tick()
        waiting = await read_schedule(app.store, context)
        assert waiting["next_at"] == clock[0] + 1800
        assert not binding.calls and not host.sends
        clock[0] += 1800
        await asyncio.gather(app.tick(), app.tick(), app.tick())
        await drain(app)
        assert host.sends == len(binding.calls) == 1
        prompt, data, *_ = binding.calls[0]
        data = json.loads(data)
        assert "initiating a natural conversation" in prompt
        assert data["motive"] == "记忆回访"
        assert data["materials"][0]["text"] == "hello"
        assert "closeness" in data["relationship"] and "social_need" in data["mood"]
        state = await read_schedule(app.store, context)
        assert state["last_outcome"] == "unknown" and state["recent_topics"]
        assert state["last_mode"] == "memory_followup"
        await app.tick()
        await drain(app)
        assert host.sends == 1
        clock[0] += 1800
        await app.tick()
        await drain(app)
        assert host.sends == 1 and len(binding.calls) == 1
        assert (await read_schedule(app.store, context))["last_reason"] == "cooldown"
        dto = await app.console_state(context.account_key)
        assert dto["behavior"]["next_check_at"] and dto["behavior"]["backoff"] == 1
        assert dto["behavior"]["last_motive"] == "记忆回访"
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", ["active", "random", "sleep", "quota", "unanswered", "identity"])
async def test_skipped_opportunities_have_zero_model_or_send(tmp_path, gate):
    app, host, _, context, binding, clock = await proactive_app(
        tmp_path, draw=.999 if gate == "random" else 0,
    )
    try:
        await app.maybe_proact(context)
        clock[0] += 1800
        if gate == "active":
            await app.on_message(Message("new", "正在聊天"))
        elif gate == "sleep":
            snapshot = app.current_snapshot
            async def sleepy(source):
                value = await snapshot(source)
                return replace(value, night=NightState(display_state="nap"))
            app.behavior.current = sleepy
        elif gate in ("quota", "unanswered"):
            from astrbot_plugin_livingemotion.services.behavior import BehaviorHistory
            async def history(*args):
                return BehaviorHistory(global_used=6 if gate == "quota" else 0,
                                       unanswered_count=2 if gate == "unanswered" else 0)
            app.behavior.history = history
        elif gate == "identity":
            async def rejected(*args):
                return False
            app.behavior.validate_identity = rejected
        await app.maybe_proact(context)
        await drain(app)
        assert host.sends == len(binding.calls) == 0
        state = await read_schedule(app.store, context)
        assert state["last_outcome"] == "skipped" and state["finished_at"] == clock[0]
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_new_human_during_generation_cancels_before_send_and_topics_do_not_repeat(tmp_path):
    app, host, _, context, binding, clock = await proactive_app(tmp_path)
    binding.release = asyncio.Event()
    try:
        await app.maybe_proact(context)
        clock[0] += 1800
        await app.maybe_proact(context)
        await asyncio.wait_for(binding.started.wait(), 2)
        await app.on_message(Message("newer", "换个话题吧"))
        binding.release.set()
        await drain(app)
        assert host.sends == 0 and len(binding.calls) == 1
        request = MemoryRequest("another", "proactive:light_chat", context)
        material = await app.behavior_materials(request)
        assert [m.text for m in material.materials] == ["换个话题吧"]
        assert (await read_schedule(app.store, context))["last_outcome"] == "cancelled"
    finally:
        binding.release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_revoke_evidence_during_model_prevents_send(tmp_path):
    app, host, _, context, binding, clock = await proactive_app(tmp_path)
    binding.release = asyncio.Event()
    try:
        await app.maybe_proact(context)
        clock[0] += 1800
        await app.maybe_proact(context)
        await asyncio.wait_for(binding.started.wait(), 2)
        from astrbot_plugin_livingemotion.ports.memory import ValidationResult
        async def invalid(*args):
            return ValidationResult(False)
        app.behavior.validate_evidence = invalid
        binding.release.set()
        await drain(app)
        assert host.sends == 0
        assert (await read_schedule(app.store, context))["last_reason"] == "evidence_invalid"
    finally:
        binding.release.set()
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("withdraw", [False, True])
async def test_private_emotional_share_uses_mood_and_respects_relationship_changes(tmp_path, withdraw):
    app, host, _, context, binding, clock = await proactive_app(tmp_path)
    class MoodDraws(RandomDraws):
        def __init__(self):
            super().__init__()
            self.draws = iter((0, .999))
        def random(self):
            return next(self.draws)
    app._proactive_random = MoodDraws()
    binding.release = asyncio.Event()
    try:
        record = await app.store.get_state(context, "relationship", context.account_id)
        await app.correct_relationship(context.account_key, expected_version=record.version,
                                       score=900, reason="合成熟悉关系", actor_id="verified")
        await app.maybe_proact(context)
        clock[0] += 1800
        await app.maybe_proact(context)
        await asyncio.wait_for(binding.started.wait(), 2)
        data = json.loads(binding.calls[0][1])
        assert data["motive"] == "分享心情"
        assert "mood" in data and "reason_codes" not in data["mood"]
        if withdraw:
            record = await app.store.get_state(context, "relationship", context.account_id)
            await app.correct_relationship(context.account_key, expected_version=record.version,
                                           score=100, reason="合成关系变更", actor_id="verified")
        binding.release.set()
        await drain(app)
        assert host.sends == (0 if withdraw else 1)
        if withdraw:
            assert (await read_schedule(app.store, context))["last_reason"] == "relationship_boundary_changed"
    finally:
        binding.release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_group_uses_latest_speaker_once_and_never_private_material(tmp_path):
    app, host, native, context, binding, clock = await proactive_app(tmp_path)
    try:
        first, second = Message("g1", "公开话题一", group="room"), Message(
            "g2", "公开话题二", group="room", account="other",
        )
        await app.on_message(first)
        await app.on_message(second)
        group = Context.from_dict(second.extra["livingemotion:context"])
        native.update(autonomy_scopes=group.scope_key, group_autonomy_enabled=True)
        await app.refresh_config()
        await app.tick()
        clock[0] += 1800
        await app.tick()
        await drain(app)
        assert host.sends == len(binding.calls) == 1
        data = json.loads(binding.calls[0][1])
        assert data["scene"] == "group"
        assert data["motive"] != "分享心情"
        assert [m["text"] for m in data["materials"]] == ["公开话题二"]
        foreign = replace(group, scene_kind=SceneKind.PRIVATE, scene_id=context.scene_id,
                          account_id=context.account_id)
        assert not (await app.local_behavior_materials(
            MemoryRequest("group-check", "proactive:memory_followup", foreign)
        ))
    finally:
        await app.terminate()
