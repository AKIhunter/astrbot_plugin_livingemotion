"""Closing uses the real composition root with synthetic models and chains."""

from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import Context
from test_retro_reply import FinalMessage, at_time


async def prepared(tmp_path, *, random=False):
    app, host, native, clock = await at_time(tmp_path, 21, 56, config={
        "night_schedule_enabled": False, "closing_enabled": True,
        "closing_random": random, "closing_lead_minutes": 5, "fatigue_start": "22:00",
    })
    # Mirror the native MessageChain shape; no platform transport is used.
    app.bridge.chain = lambda text: SimpleNamespace(chain=[SimpleNamespace(text=text)])
    message = FinalMessage(identifier="closing-message")
    await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
    context = Context.from_dict(message.extra["livingemotion:context"])
    return app, host, native, clock, message, context


@pytest.mark.asyncio
async def test_local_closing_merges_once_without_model_and_uses_shared_send_budget(tmp_path):
    app, host, _, _, message, context = await prepared(tmp_path)
    try:
        async def forbidden(*args, **kwargs):
            raise AssertionError("random disabled must not call a model")
        app.purpose_model = forbidden
        assert await app.on_reply_submitted(message) is True
        assert "晚安" in "".join(part.text for part in message.result.chain)
        assert await app.on_reply_submitted(message) is True
        assert len(message.result.chain) == 2 and host.sends == 0
        history = await app.store.behavior_history(context, "2026-11-06")
        assert history["global_used"] == 1
        batch = await app.catchup_archive.begin(
            context, 0, exclude_source_id="", wake_key="wake", revision=app.revision,
        )
        assert await app.catchup_archive.rows(context, batch) == []
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_closing_model_wait_cannot_reuse_revoked_memory_authorization(tmp_path):
    app, host, _, _, message, context = await prepared(tmp_path, random=True)
    revoked, checks = False, []
    query, materials = object(), ("synthetic private memory",)
    message.set_extra("livingemotion:memory_lease", (query, materials))
    try:
        async def generate(*args, **kwargs):
            nonlocal revoked
            revoked = True
            return "晚安。"

        async def validate(request, recalled, *, event):
            checks.append(revoked)
            return SimpleNamespace(valid=not revoked, materials=recalled)

        app.purpose_model = generate
        app.memory.validate_evidence = validate
        assert await app.on_reply_submitted(message) is False
        assert checks == [True] and host.sends == 0
        history = await app.store.energy_history(context, category="reply")
        assert history["total"] == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_new_message_during_random_closing_keeps_old_result_without_closing_line(tmp_path):
    app, host, _, _, message, context = await prepared(tmp_path, random=True)
    try:
        async def generate(*args, **kwargs):
            await app.on_message(FinalMessage(identifier="newer"))
            return "晚安。"
        app.purpose_model = generate
        # 新消息撤销的是这次临时的晚安合并，不撤销已经生成好的正文。
        assert await app.on_reply_submitted(message) is True
        assert len(message.result.chain) == 1 and host.sends == 0
        assert (await app.store.energy_history(context, category="reply"))["total"] == 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_closing_without_shared_send_quota_does_not_append_or_generate(tmp_path):
    app, host, _, _, message, context = await prepared(tmp_path, random=True)
    try:
        for index in range(app.config.behavior_daily_limit):
            await app.store.reserve_quota(
                f"existing:{index}", context, 0, period="2026-11-06", purpose="behavior",
                pool="send", limit=app.config.behavior_daily_limit,
                global_limit=app.config.behavior_daily_limit,
            )
        async def forbidden(*args, **kwargs):
            raise AssertionError("exhausted send budget must stop generation")
        app.purpose_model = forbidden
        assert await app.on_reply_submitted(message) is True
        assert len(message.result.chain) == 1 and host.sends == 0
    finally:
        await app.terminate()
