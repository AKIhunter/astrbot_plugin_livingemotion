import asyncio
from dataclasses import replace
import json

import pytest

from astrbot_plugin_livingemotion.contracts import NightState
from astrbot_plugin_livingemotion.runtime.models import OpenAIBinding
from budget_support import App, scope


async def test_real_provider_request_local_wire_payload(rig, wire, record_property):
    app = App(rig, wire)
    result = await app.behavior_model(await app.behavior_request(output_tokens=23))
    await rig.runtime.join()
    payload = wire.requests[0]
    record_property("measurements", {
        "calls": len(wire.requests), "max_tokens": payload.get("max_tokens"),
        "n": payload.get("n"), "message_count": len(payload["messages"]),
        "roles": [m["role"] for m in payload["messages"]],
        "tools_present": "tools" in payload, "shared_provider_unchanged": wire.unchanged(),
        "thinking_disabled": payload.get("enable_thinking") is False,
    })
    assert result == "ok" and len(wire.requests) == 1
    assert payload["max_tokens"] == 23 and payload["n"] == 1
    assert payload["model"] == "qwen-offline-fixture" and "max_completion_tokens" not in payload
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]
    assert "tools" not in payload and "tool_choice" not in payload
    assert payload["enable_thinking"] is False
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["temperature"] == .2 and wire.unchanged()


async def test_real_behavior_composition_exact_input_boundary(rig, wire, record_property):
    app = App(rig, wire)
    await app.behavior_model(await app.behavior_request(0, persona=""))
    messages = wire.requests[0]["messages"]
    binding = OpenAIBinding(wire.provider)
    base = binding.count(messages[0]["content"], messages[1]["content"])
    assert 0 < base < 4096
    persona = "a" * (4096 - base)
    await app.behavior_model(await app.behavior_request(1, persona=persona))
    second = wire.requests[1]["messages"]
    actual_count = binding.count(second[0]["content"], second[1]["content"])
    with pytest.raises(ValueError, match="token_limit"):
        await app.behavior_model(await app.behavior_request(2, persona=persona + "a"))
    with pytest.raises(ValueError, match="token_limit"):
        await app.behavior_model(await app.behavior_request(3, output_tokens=1025))
    record_property("measurements", {"boundary_input_upper_bound": actual_count,
                                      "wire_calls": len(wire.requests),
                                      "oversized_rejected_before_wire": 2})
    assert actual_count == 4096 and len(wire.requests) == 2 and wire.unchanged()


@pytest.mark.parametrize("mode", ("error", "timeout", "output_overflow", "cancel"))
async def test_provider_error_timeout_cancel_output_no_retry(rig, wire, mode, record_property):
    await rig.reopen(model_daily_limit=1, fallback_provider_id="synthetic-fallback")
    app = App(rig, wire)
    request = await app.behavior_request(output_tokens=4)
    if mode == "output_overflow":
        wire.text = "a" * 5
    else:
        wire.mode = "blocked" if mode == "cancel" else mode
    task = asyncio.create_task(app.behavior_model(request))
    await asyncio.wait_for(wire.entered.wait(), 3)
    if mode == "cancel":
        await rig.runtime.stop()
    with pytest.raises(ValueError):
        await task
    await rig.runtime.join()
    rows = await rig.rows()
    record_property("measurements", {
        "wire_calls": len(wire.requests), "transport_cancellations": wire.cancelled,
        "persisted_outcomes": rows, "shared_provider_unchanged": wire.unchanged(),
    })
    assert len(wire.requests) == 1 and wire.unchanged()
    assert "synthetic-fallback" not in app.lookups
    assert rows[0]["status"] == ("cancelled" if mode == "cancel" else "unknown")
    await rig.reopen()
    app = App(rig, wire)
    with pytest.raises(ValueError, match="quota_exhausted"):
        await app.behavior_model(await app.behavior_request(2))
    assert len(wire.requests) == 1


async def test_active_generation_caller_cancel_reaches_transport(rig, wire, record_property):
    app = App(rig, wire)
    wire.mode = "blocked"
    task = asyncio.create_task(app.behavior_model(await app.behavior_request()))
    await asyncio.wait_for(wire.entered.wait(), 3)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(.05)
    wire.release.set()
    await rig.runtime.join()
    rows = await rig.rows()
    record_property("measurements", {
        "wire_calls": len(wire.requests), "transport_cancellations": wire.cancelled,
        "persisted_outcomes": rows, "shared_provider_unchanged": wire.unchanged(),
    })
    assert len(wire.requests) == wire.cancelled == 1, "caller cancellation did not reach transport"
    assert rows[0]["status"] == "cancelled"


def night(rig):
    return NightState(phase="asleep", updated_at=rig.now, sleep_started_at=rig.now - 100,
                      wake_at=rig.now + 3600, sleep_stage="REM")


async def queue_entry(app, rig, purpose):
    service = await app.experience_service(scope())
    if purpose == "diary":
        result = await service.queue_diary(scope(), persona_text="Synthetic persona.")
    else:
        result = await service.queue_dream(
            scope(), night(rig), persona_text="Synthetic persona.")
    await rig.runtime.join()
    return service, result


@pytest.mark.parametrize("purpose", ("diary", "dream"))
async def test_live_experience_wire_budget_and_persisted_purpose_limit(
        rig, wire, purpose, record_property):
    await rig.ingest(0)
    wire.mode = "entry"
    app = App(rig, wire)
    service, first = await queue_entry(app, rig, purpose)
    assert first["status"] == "queued", first
    assert service.outcome(first["job_id"])["status"] == "created", service.outcome(first["job_id"])
    saved = await rig.store.load_experience(first["experience_id"])
    assert saved is not None
    if purpose == "dream":
        service, second = await queue_entry(app, rig, purpose)
        assert second["status"] == "queued", second
        assert service.outcome(second["job_id"])["status"] == "created"
    await rig.reopen()
    app = App(rig, wire)
    _, denied = await queue_entry(app, rig, purpose)
    record_property("measurements", {
        "wire_calls": len(wire.requests), "after_restart_reason": denied["reason_code"],
        "payload_max_tokens": [p.get("max_tokens") for p in wire.requests],
        "payload_n": [p.get("n") for p in wire.requests],
        "input_byte_upper_bounds": [
            OpenAIBinding(wire.provider).count(p["messages"][0]["content"],
                                               p["messages"][1]["content"])
            for p in wire.requests],
        "persisted_outcomes": await rig.rows(),
    })
    assert denied["reason_code"] == (
        "experience_exists" if purpose == "diary" else "experience_attempt_limit")
    assert len(wire.requests) == (1 if purpose == "diary" else 2)
    assert all(p["max_tokens"] == 1024 and p["n"] == 1 for p in wire.requests)
    assert wire.unchanged()


@pytest.mark.parametrize("purpose", ("diary", "dream"))
async def test_live_experience_unknown_attempts_bounded_after_restart(
        rig, wire, purpose, record_property):
    await rig.ingest(0)
    wire.mode = "error"
    app = App(rig, wire)
    limit = 3 if purpose == "diary" else 2
    for attempt in range(limit):
        service, result = await queue_entry(app, rig, purpose)
        assert result["status"] == "queued", result
        assert service.outcome(result["job_id"])["status"] == "unknown"
        assert len(wire.requests) == attempt + 1
        await rig.reopen()
        app = App(rig, wire)
    _, denied = await queue_entry(app, rig, purpose)
    record_property("measurements", {
        "explicit_attempts": limit, "wire_calls": len(wire.requests),
        "implicit_retries": len(wire.requests) - limit,
        "blocked_reason": denied["reason_code"], "persisted_outcomes": await rig.rows(),
    })
    assert denied["reason_code"] == "experience_attempt_limit"
    assert len(wire.requests) == limit


async def test_diary_owner_quota_shared_across_scenes_and_clear(rig, wire, record_property):
    await rig.ingest(0)
    wire.mode = "entry"
    app = App(rig, wire)
    _, first = await queue_entry(app, rig, "diary")
    assert first["status"] == "queued"
    await rig.store.clear_scope(scope(), 0)
    await rig.reopen()
    await rig.ingest(1, scope(1))
    app = App(rig, wire)
    service = await app.experience_service(scope(1))
    denied = await service.queue_diary(scope(1), persona_text="Synthetic persona.")
    record_property("measurements", {"wire_calls": len(wire.requests),
                                      "after_clear_other_scene": denied["reason_code"]})
    assert denied["reason_code"] == "experience_exists"
    assert len(wire.requests) == 1


async def test_same_night_dream_attempts_survive_midnight_restart(rig, wire, record_property):
    await rig.ingest(0)
    wire.mode = "error"
    original_night = night(rig)
    for attempt in range(2):
        app = App(rig, wire)
        service = await app.experience_service(scope())
        current_night = replace(original_night, updated_at=rig.now)
        result = await service.queue_dream(scope(), current_night)
        assert result["status"] == "queued", result
        await rig.runtime.join()
        assert service.outcome(result["job_id"])["status"] == "unknown"
        await rig.reopen()
        if attempt == 0:
            rig.now += 1801
    app = App(rig, wire)
    service = await app.experience_service(scope())
    denied = await service.queue_dream(scope(), replace(original_night, updated_at=rig.now))
    record_property("measurements", {"wire_calls": len(wire.requests),
                                      "after_midnight_restart": denied["reason_code"],
                                      "persisted_outcomes": await rig.rows()})
    assert denied["reason_code"] == "experience_attempt_limit" and len(wire.requests) == 2


@pytest.mark.parametrize("purpose", ("diary", "dream"))
async def test_live_experience_input_limit_before_queue(rig, wire, purpose, record_property):
    await rig.ingest(0)
    app = App(rig, wire)
    service = await app.experience_service(scope())
    args = {"persona_text": "a" * 4096}
    result = (await service.queue_diary(scope(), **args) if purpose == "diary"
              else await service.queue_dream(scope(), night(rig), **args))
    record_property("measurements", {"wire_calls": len(wire.requests),
                                      "reason": result["reason_code"]})
    assert result["reason_code"] == "input_token_limit"
    assert len(wire.requests) == 0 and await rig.rows() == []


async def test_real_emotion_refinement_payload_budget(rig, wire, record_property):
    app = App(rig, wire)
    event = await rig.ingest(0)
    # Obtain the original pre-event seed through the real projector on a second scope.
    from astrbot_plugin_livingemotion.runtime.projector import Projector
    event = replace(event, event_id="refinement-event", source_id="refinement-source",
                    context=scope(2), actor_id=scope(2).account_id)
    projection = await Projector(rig.store, lambda: rig.config)(event)
    committed = await rig.api.ingest_event(event)
    wire.text = json.dumps({"rule_version": "emotion-1", "delta": {
        "pleasure": 0, "arousal": 0, "stress": 0, "social_need": 0}, "confidence": .5})
    await app.refine_emotion(event, 0, committed["versions"]["bot:"], projection.refinement)
    await rig.runtime.join()
    record_property("measurements", {
        "wire_calls": len(wire.requests),
        "max_tokens": wire.requests[0].get("max_tokens") if wire.requests else None,
        "persisted_outcomes": await rig.rows(),
    })
    assert len(wire.requests) == 1 and wire.requests[0]["max_tokens"] == 1024
    assert (await rig.rows())[0]["purpose"] == "emotion" and wire.unchanged()
