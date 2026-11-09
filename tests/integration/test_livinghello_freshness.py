"""群聊新消息不误撤销，但接管者与记忆授权仍须逐次复核。无平台发送。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_livingemotion.contracts import Context
from test_retro_reply import FinalMessage, at_time


def delegate(event, *, policy="", freshness=""):
    event.extra["_livinghello_policy_send_check"] = lambda: policy
    event.extra["_at_guard_send_check"] = lambda: freshness


@pytest.mark.asyncio
async def test_two_group_messages_during_generation_preserve_owned_reply(tmp_path):
    app, host, _, _ = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        old = FinalMessage(identifier="old", group="group")
        await app.on_llm_request(old, SimpleNamespace(extra_user_content_parts=[]))
        for i in range(2):
            await app.on_message(FinalMessage(identifier=f"new{i}", group="group"))
        delegate(old)
        assert await app.on_reply_submitted(old) is True
        assert await app.on_reply_submitted(old) is True
        context = Context.from_dict(old.extra["livingemotion:context"])
        assert (await app.store.energy_history(context, category="reply"))["total"] == 1
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "private", "no_owner", "missing_policy", "recall", "expired", "blacklist",
    "policy_changed", "blocked", "callback_error", "revision", "generation", "mode",
    "memory_invalid", "policy_changes_during_memory",
])
async def test_delegation_does_not_bypass_final_protections(tmp_path, case):
    app, host, native, _ = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        group = "" if case == "private" else "group"
        old = FinalMessage(identifier="old", group=group)
        await app.on_llm_request(old, SimpleNamespace(extra_user_content_parts=[]))
        await app.on_message(FinalMessage(identifier="new", group=group))
        delegate(old)
        if case == "no_owner":
            old.extra.pop("_at_guard_send_check")
        if case == "missing_policy":
            old.extra.pop("_livinghello_policy_send_check")
        if case in ("recall", "expired"):
            delegate(old, freshness="message_" + case)
        if case in ("blacklist", "policy_changed"):
            delegate(old, policy=case)
        if case == "blocked":
            old.extra["_at_guard_delivery_blocked"] = "cancelled"
        if case == "callback_error":
            def broken():
                raise ValueError("synthetic")
            old.extra["_at_guard_send_check"] = broken
        if case == "revision":
            old.extra["livingemotion:reply_lease"]["revision"] = "obsolete"
        if case == "generation":
            old.extra["livingemotion:reply_lease"]["generation"] = -1
        if case == "mode":
            native["mode"] = "observe_only"
            await app.refresh_config()
        if case.startswith("memory_") or case == "policy_changes_during_memory":
            old.extra["livingemotion:memory_lease"] = (object(), ("evidence",))
            async def validate(*_, **__):
                if case == "policy_changes_during_memory":
                    delegate(old, policy="blacklist")
                return SimpleNamespace(valid=case != "memory_invalid", materials=("evidence",))
            app.memory.validate_evidence = AsyncMock(side_effect=validate)
        assert await app.on_reply_submitted(old) is False
        assert host.sends == 0
    finally:
        await app.terminate()
