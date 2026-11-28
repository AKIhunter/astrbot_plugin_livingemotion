"""画像存储边界：空值、截断、部分更新与版本冲突。

画像由 LivingEmotion 自己维护（监听消息沉淀 + 面板补编），这里只覆盖
存储层的行为边界：不该因为脏输入写坏关系页，也不该把旧版本覆盖新版本。
"""

import pytest

from astrbot_plugin_livingemotion.contracts import StateWrite
from astrbot_plugin_livingemotion.storage.console_data import write_profile


@pytest.mark.asyncio
async def test_profile_roundtrip_and_partial_update(le_store, le_event):
    context = le_event.context
    value = await write_profile(le_store, context, interests=["摄影", "猫"],
                                tags=["老友"], note="常聊相机")
    assert value["interests"] == ["摄影", "猫"]
    record = await le_store.get_state(context, "profile", context.account_id)
    assert record.value["tags"] == ["老友"]
    # 只改备注时，已有爱好与标签必须保留。
    value = await write_profile(le_store, context, note="改过备注")
    assert value["interests"] == ["摄影", "猫"] and value["tags"] == ["老友"]
    assert value["note"] == "改过备注"


@pytest.mark.asyncio
async def test_profile_drops_blank_items_and_truncates(le_store, le_event):
    context = le_event.context
    value = await write_profile(
        le_store, context, interests=["  ", "x" * 40, "正常"], tags=[], note="n" * 800)
    # 空项丢弃、单项截到 24 字、备注截到 500 字。
    assert value["interests"] == ["x" * 24, "正常"]
    assert value["tags"] == []
    assert len(value["note"]) == 500


@pytest.mark.asyncio
async def test_profile_empty_list_clears_only_that_field(le_store, le_event):
    context = le_event.context
    await write_profile(le_store, context, interests=["a"], tags=["b"])
    value = await write_profile(le_store, context, interests=[])
    assert value["interests"] == [] and value["tags"] == ["b"]


@pytest.mark.asyncio
async def test_profile_stale_version_is_rejected(le_store, le_event):
    context = le_event.context
    await write_profile(le_store, context, interests=["a"])
    record = await le_store.get_state(context, "profile", context.account_id)
    generation = await le_store.get_generation(context)
    stale = await le_store.write_states(
        context, generation,
        (StateWrite("profile", {"interests": ["旧"]},
                    expected_version=max(0, record.version - 1),
                    record_key=context.account_id),))
    assert not stale.accepted
    fresh = await le_store.get_state(context, "profile", context.account_id)
    assert fresh.value["interests"] == ["a"]
