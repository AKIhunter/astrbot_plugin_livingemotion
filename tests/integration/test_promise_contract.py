"""记账契约的即时与延迟口径。

用户要照片、自拍这类**能立即给**的东西时，契约必须放行当场调生图工具、
不许写记账指令；只有「晚点」「稍后」这类明确延后才落标记。
"""

from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import Context
from test_retro_reply import FinalMessage, at_time


async def contract_text(tmp_path, *, hour=10, minute=0):
    """注入承诺契约，返回拼进请求的全部附加文本。"""
    app, _, _, _ = await at_time(tmp_path, hour, minute, config={
        "night_schedule_enabled": False, "promise_enabled": True,
    })
    try:
        message = FinalMessage(identifier="contract-probe")
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        return "\n".join(
            str(getattr(part, "text", "")) for part in request.extra_user_content_parts)
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_contract_allows_immediate_image_tool_and_forbids_mark(tmp_path):
    """能立即给的照片/自拍：契约必须说「直接做、别记账」，并放行生图工具。"""
    text = await contract_text(tmp_path)
    # 即时路径的三个关键口径都要在。
    assert "直接做" in text and "绝对不写记账指令" in text
    assert "本轮新生图请求许可" in text
    assert "行动仍按本轮许可处理" in text
    # 旧版的绝对禁令必须消失：它会把即时生图一起禁掉。
    assert "绝对不要调用生图" not in text
    assert "还不到时候" not in text


@pytest.mark.asyncio
async def test_contract_keeps_deferred_recording_path(tmp_path):
    """延迟请求（晚点/稍后/具体分钟）仍然走记账，档位与格式说明保留。"""
    text = await contract_text(tmp_path)
    for token in ("<!--promise:档位:这件事做什么-->", "晚点", "稍后", "10分钟后",
                  "一会儿", "待会", "今晚", "明天", "过几天"):
        assert token in text, token


@pytest.mark.asyncio
async def test_contract_lists_active_promises_and_cancel_syntax(tmp_path):
    """挂着待办时，契约要列出条目并给取消语法。"""
    app, _, _, clock = await at_time(tmp_path, 10, 0, config={
        "night_schedule_enabled": False, "promise_enabled": True,
    })
    try:
        message = FinalMessage(identifier="contract-mount", body="明天叫我看日出")
        # 直接落一条待办，再触发一次契约注入。
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        await app._promises().remember(
            context, [("明天", "提醒他看日出")],
            summary="", query="看日出")
        text_parts = SimpleNamespace(extra_user_content_parts=[])
        probe = FinalMessage(identifier="contract-mount-2")
        await app.on_llm_request(probe, text_parts)
        joined = "\n".join(
            str(getattr(part, "text", "")) for part in text_parts.extra_user_content_parts)
        assert "现在挂着这些没做完的事" in joined
        assert "提醒他看日出" in joined
        assert "<!--promise-cancel:编号或关键词-->" in joined
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_contract_absent_when_promise_disabled(tmp_path):
    """promise_enabled=false 时不注入记账规则，标记也不会出现。"""
    app, _, _, _ = await at_time(tmp_path, 10, 0, config={
        "night_schedule_enabled": False, "promise_enabled": False,
    })
    try:
        request = SimpleNamespace(extra_user_content_parts=[])
        probe = FinalMessage(identifier="contract-off")
        await app.on_llm_request(probe, request)
        joined = "\n".join(
            str(getattr(part, "text", "")) for part in request.extra_user_content_parts)
        assert "记账规则" not in joined
    finally:
        await app.terminate()
