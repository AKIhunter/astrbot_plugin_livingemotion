"""补答不得成为回复的前置故障点。

2026-11-27 19:21 那次事故的反面：以前是"顺手补发"，现在是"只读历史"。
但只读也可能失败——读不到、模型超时、归档损坏。任何一种都不能让这一轮
回复发不出去（否则用户看到的就是"消息卡住不回"）。
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from astrbot_plugin_livingemotion.runtime.application import Application


@pytest.fixture(autouse=True)
def stub_revision():
    """revision 是只读 property（依赖真实 Config），这里只关心别把它算进去。"""
    with patch.object(Application, "revision", "rev-1"):
        yield


def make_app(*, night=None):
    app = object.__new__(Application)
    app.config = SimpleNamespace(catchup_enabled=True)
    app.store = SimpleNamespace(clock=lambda: 1000.0)

    async def night_snapshot(_context):
        return night

    app.night_snapshot = night_snapshot
    app.catchup = SimpleNamespace(prepare=None)
    return app


def make_event():
    seen = {}
    return SimpleNamespace(
        message_obj=SimpleNamespace(message_id="m-1"),
        set_extra=lambda key, value: seen.__setitem__(key, value),
        get_extra=lambda key, default=None: seen.get(key, default),
    ), seen


@pytest.mark.asyncio
async def test_unexpected_error_never_blocks_the_reply():
    """读历史抛什么都不能冒泡：这一轮该照常回复。"""

    async def boom(_context):
        raise RuntimeError("archive corrupted")

    app = make_app()
    app.night_snapshot = boom
    event, seen = make_event()

    await app._prepare_catchup(event, SimpleNamespace(extra_user_content_parts=[]), None)
    assert seen["livingemotion:catchup_status"] == "prepare_failed"


@pytest.mark.asyncio
async def test_awake_turn_never_reads_history():
    """清醒轮次直接返回：不读、不注入、也不留准备耗时。"""
    calls = []

    async def prepare(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError("清醒轮次不该读历史")

    app = make_app(night=SimpleNamespace(wake_window_deadline=None))
    app.catchup = SimpleNamespace(prepare=prepare)
    event, seen = make_event()
    request = SimpleNamespace(extra_user_content_parts=[])

    await app._prepare_catchup(event, request, None)
    assert calls == [] and request.extra_user_content_parts == []
    assert "livingemotion:wake_prepare_seconds" not in seen


@pytest.mark.asyncio
async def test_wake_window_reads_but_never_sends():
    """窗口内只读：必须显式传 allow_reply=False。"""
    captured = {}

    async def prepare(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(reason="full_reading_complete", summaries=(), blocked=False)

    app = make_app(night=SimpleNamespace(wake_window_deadline=2000.0,
                                         sleep_started_at=500.0, wake_at=900.0))
    app.catchup = SimpleNamespace(prepare=prepare)
    event, _ = make_event()

    await app._prepare_catchup(event, SimpleNamespace(extra_user_content_parts=[]),
                               SimpleNamespace(scope_key="scope-1"))
    assert captured["allow_reply"] is False
