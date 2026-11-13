"""Real services/SQLite with virtual time and explicit transport stubs; zero network."""
from dataclasses import replace
import asyncio
import json
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BotAffect, StateWrite, to_dict
from astrbot_plugin_livingemotion.runtime.background import ModelResultUnknown
from astrbot_plugin_livingemotion.runtime.models import (
    ModelPreflightFailed, RouterBinding, check_provider_api,
)
from astrbot_plugin_livingemotion.services.experience import ExperiencePolicy, parse_entry
from astrbot_plugin_livingemotion.tests.experience.test_experience import h  # noqa: F401
from astrbot_plugin_livingemotion.tests.experience.test_manual_daily import (
    make_app, submit, finish,
)
from astrbot_plugin_livingemotion.tests.experience.test_router_binding import router


class Transport:
    def __init__(self, status=200, error=None):
        self.status, self.error, self.calls, self.options = status, error, 0, None
        self.models = SimpleNamespace(with_raw_response=self)

    def with_options(self, **options):
        self.options = options
        return self

    async def list(self):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(status_code=self.status)


@pytest.mark.parametrize("status", [200, 401, 403, 429, 503])
async def test_same_api_preflight_http_and_no_retry(status):
    wire = Transport(status)
    if status == 200:
        assert (await check_provider_api(SimpleNamespace(client=wire)))["http_status"] == 200
    else:
        with pytest.raises(ModelPreflightFailed) as caught:
            await check_provider_api(SimpleNamespace(client=wire))
        assert caught.value.http_status == status
        assert str(caught.value) == "model_preflight_http_error"
    assert wire.calls == 1 and wire.options == {"max_retries": 0, "timeout": 5}


async def test_pinned_preflight_uses_selected_slot_only():
    provider = router()
    selected, other = Transport(), Transport(401)
    provider.upstreams = [
        SimpleNamespace(slot=6, client=SimpleNamespace(client=other)),
        SimpleNamespace(slot=12, client=SimpleNamespace(client=selected)),
    ]
    assert (await RouterBinding(provider).preflight())["http_status"] == 200
    assert selected.calls == 1 and other.calls == 0 and provider.calls == []

async def test_preflight_timeout_and_transport_error_never_leak_exception():
    for error, reason in [(TimeoutError("synthetic private endpoint"), "model_preflight_timeout"),
                          (RuntimeError("synthetic private endpoint"), "model_preflight_unavailable")]:
        with pytest.raises(ModelPreflightFailed) as caught:
            await check_provider_api(SimpleNamespace(client=Transport(error=error)))
        assert str(caught.value) == reason
        assert caught.value.http_status is None


async def test_automatic_yesterday_window_is_bounded_and_idempotent(h):
    await h.event(occurred=h.now - 86400, source="yesterday")
    h.service = h.make_service(policy=ExperiencePolicy(backfill_yesterday=True))
    result = await h.service.queue_diary(h.context, day="2026-11-04")
    assert result["status"] == "queued"
    await h.runtime.join()
    assert h.records[result["experience_id"]][0].period == "2026-11-04"
    assert (await h.service.queue_diary(h.context, day="2026-11-04"))["status"] == "duplicate"
    assert (await h.service.queue_diary(h.context, day="2026-11-03"))[
        "reason_code"] == "diary_backfill_out_of_range"
    assert len(h.model.calls) == 1


@pytest.mark.parametrize("kind", ["diary", "dream"])
@pytest.mark.parametrize("status", [401, 503])
async def test_failed_preflight_no_generation_or_quota(h, kind, status):
    await h.event()
    async def check(_purpose):
        raise ModelPreflightFailed("model_preflight_http_error", status)
    h.service = h.make_service(preflight=check)
    result = (await h.service.queue_diary(h.context) if kind == "diary" else
              await h.service.queue_dream(h.context, h.night()))
    assert result["status"] == "failed" and result["http_status"] == status
    assert h.model.calls == []
    assert (await h.store.health())["counts"]["quota_reservations"] == 0


@pytest.mark.parametrize("kind", ["diary", "dream"])
async def test_2000_chinese_body_independent_of_global_1024(h, kind):
    await h.event()
    h.model.response = {"title": "一盏灯留到了夜里", "body": "中" * 2000}
    h.service = h.make_service(
        policy=ExperiencePolicy(output_tokens=8192),
        count_tokens=lambda system, data: len(data.encode()) + len(system.encode()) + 256,
    )
    result = (await h.service.queue_diary(h.context) if kind == "diary" else
              await h.service.queue_dream(h.context, h.night()))
    await h.runtime.join()
    assert h.service.outcome(result["job_id"])["status"] == "created"
    assert h.model.calls[0].max_output_tokens == 8192
    assert h.runtime.config.model_output_tokens == 1024
    saved = h.records[result["experience_id"]][0]
    assert saved.body.endswith("中" * 2000)
    assert (saved.title == "一盏灯留到了夜里") == (kind == "diary")


def test_body_limit_2001_and_safe_optional_title():
    with pytest.raises(ValueError, match="model_body_invalid"):
        parse_entry({"body": "中" * 2001}, allowed_sources=set())
    assert parse_entry({"body": "中文正文"}, allowed_sources=set()).title == ""
    assert parse_entry({"body": "中文正文", "title": "<img>"}, allowed_sources=set()).title == ""
    assert Config.from_mapping({"experience_body_chars": 8000}).experience_body_chars == 2000
    with pytest.raises(ValueError):
        Config(experience_body_chars=2001)
    with pytest.raises(ValueError, match="body_chars_invalid"):
        ExperiencePolicy(body_chars=2001)


async def test_captured_state_survives_normal_refresh_but_clear_revokes(h):
    generation = await h.store.get_generation(h.context)
    await h.store.write_states(h.context, generation, [
        StateWrite("bot", to_dict(BotAffect(pleasure=.7, updated_at=h.now)), 0)])
    h.model.resume.clear()
    result = await h.service.queue_diary(h.context)
    assert result["status"] == "queued", result
    await asyncio.wait_for(h.model.entered.wait(), 1)
    record = await h.store.get_state(h.context, "bot")
    await h.store.write_states(h.context, generation, [
        StateWrite("bot", to_dict(BotAffect(pleasure=.2, updated_at=h.now)), record.version)])
    h.model.resume.set()
    await h.runtime.join()
    assert h.service.outcome(result["job_id"])["status"] == "created"
    saved = h.records[result["experience_id"]][0]
    assert saved.emotion_snapshot["label"] == "喜悦"
    assert "state:bot:" in saved.evidence[0].source_id
    # 下一天在生成期间清空，旧快照不能跨清空授权存活。
    h.now += 86400
    h.service.memory.clock = lambda: h.now
    await h.event(source="next")
    h.model.entered.clear()
    h.model.resume.clear()
    result = await h.service.queue_diary(h.context)
    assert result["status"] == "queued", result
    await asyncio.wait_for(h.model.entered.wait(), 1)
    await h.store.clear_scope(h.context, generation, actor_id="admin")
    h.model.resume.set()
    await h.runtime.join()
    assert h.service.outcome(result["job_id"])["status"] != "created"


async def test_dream_failure_can_retry_success_and_unknown_cannot(h):
    await h.event()
    h.service = h.make_service(policy=ExperiencePolicy(dream_per_night=1))
    night = h.night()
    h.model.response = {"error": "explicit failed response"}
    first = await h.service.queue_dream(h.context, night)
    await h.runtime.join()
    assert h.service.outcome(first["job_id"])["status"] == "failed"
    h.model.response = {"body": "我走在想象中的云上。"}
    second = await h.service.queue_dream(h.context, night)
    await h.runtime.join()
    assert h.service.outcome(second["job_id"])["status"] == "created"
    assert (await h.service.queue_dream(h.context, night))["reason_code"] == "dream_success_limit"
    assert len(h.model.calls) == 2
    h.now += 86400
    await h.event(source="another-night")
    h.model.response = ModelResultUnknown("model_output_invalid")
    night = h.night()
    third = await h.service.queue_dream(h.context, night)
    await h.runtime.join()
    assert h.service.outcome(third["job_id"])["reason_code"] == "model_output_invalid"
    assert (await h.service.queue_dream(h.context, night))["reason_code"] == "model_result_unknown"
    assert len(h.model.calls) == 3


@pytest.mark.parametrize("kind", ["diary", "dream"])
async def test_manual_header_body_limit_and_failed_preflight_preserves_old(tmp_path, kind):
    app, binding, _, _ = await make_app(tmp_path)
    try:
        binding.response = json.dumps({"title": "旧日的小光", "body": "中" * 2000})
        first = await submit(app, kind)
        await finish(app)
        task = await app.console_experience_task(first["request_id"])
        assert task["status"] == "succeeded"
        old, _ = await app.store.load_experience(task["experience_id"])
        assert old.body.endswith("中" * 2000)
        rows = await app.console_records(kind=kind, persona_id="native")
        assert rows["items"][0]["date"] == "2026-11-09"
        assert rows["items"][0]["emotion_snapshot"]["label"]
        async def failed():
            raise ModelPreflightFailed("model_preflight_http_error", 401)
        binding.preflight = failed
        second = await submit(app, kind)
        await finish(app)
        result = await app.console_experience_task(second["request_id"])
        assert result["status"] == "failed"
        assert result["reason_code"] == "model_preflight_http_error:401"
        assert binding.calls == 1
        assert (await app.store.load_experience(task["experience_id"]))[0] == old
    finally:
        await app.terminate()


async def test_auto_status_survives_reads_and_does_not_hide_manual(tmp_path):
    app, binding, _, _ = await make_app(tmp_path)
    try:
        first = await submit(app)
        await finish(app)
        task = await app.console_experience_task(first["request_id"])
        entry, _ = await app.store.load_experience(task["experience_id"])
        await app.store.record_auto_experience_status(entry.context, "diary", {
            "status": "failed", "reason_code": "model_preflight_http_error",
            "http_status": 503, "day": "2026-11-10"})
        for _ in range(2):
            view = (await app.console_state())["experience"]
            assert view["diary"]["status"] == "succeeded"
            assert view["automatic"]["diary"]["http_status"] == 503
        assert binding.calls == 1
    finally:
        await app.terminate()
