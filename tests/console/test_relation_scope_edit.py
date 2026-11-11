"""Scope, search and CAS regressions using temporary SQLite only."""
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.storage.console_data import (
    ConsoleDataConflict, query_relationships, read_relationship_override,
    write_relationship_override,
)
from astrbot_plugin_livingemotion.runtime.console import ApplicationError
from test_management_dto import ConsoleDouble, selection


async def test_target_and_neighbor_outside_cap_and_exact_id(le_store, le_context, le_event):
    sender = replace(le_context, platform="qq", account_id="123")
    peer = replace(sender, account_id="456")
    for context in [sender, peer, *(replace(sender, account_id=str(1000 + i)) for i in range(205))]:
        await le_store.register_context(context)
    assert (await le_store.commit_event(replace(
        le_event, context=sender, actor_id="123", body="我和@456是朋友"), 0)).accepted
    graph = await query_relationships(le_store, "local", selection(sender),
                                     query="123", graph_scope="neighbors")
    assert graph["total"] == 1 and graph["items"][0]["account_id"] == "123"
    assert {n["account_id"] for n in graph["nodes"]} == {"123", "456"}
    assert len(graph["focus_ids"]) == 1 and len(graph["peer_edges"]) == 1
    old = await query_relationships(le_store, "local", selection(sender), query="123")
    assert len(old["nodes"]) == 1 and old["peer_edges"] == []
    missing = await query_relationships(le_store, "local", selection(sender),
                                       query="does-not-exist", graph_scope="neighbors")
    assert missing["nodes"] == [] and missing["items"] == []
    all_nodes = await query_relationships(le_store, "local", selection(sender), graph_scope="neighbors")
    assert all_nodes["graph_truncated"] and all_nodes["graph_total"] == 207
    page = await query_relationships(le_store, "local", selection(sender), page=21)
    assert len(page["items"]) == 7 and page["nodes"] == all_nodes["nodes"]


async def test_note_cas_clear_and_platform_isolation(le_store, le_context):
    qq = replace(le_context, platform="qq")
    other = replace(qq, platform="other")
    await le_store.register_context(qq)
    await le_store.register_context(other)
    wrote = await write_relationship_override(
        le_store, qq, note="真实昵称不受备注影响\n只用于管理", score=62.1, frozen=True,
        expected_version=0, actor_id="admin", reason="合成测试")
    assert wrote["node"]["note"].startswith("真实昵称") and wrote["node"]["frozen"]
    assert wrote["node"]["label"] == qq.account_id
    with pytest.raises(ConsoleDataConflict):
        await write_relationship_override(le_store, qq, note="stale", expected_version=0,
                                          actor_id="admin", reason="合成测试")
    assert len(await le_store.audit_records()) == 1
    cleared = await write_relationship_override(le_store, qq, note="", expected_version=1,
                                               actor_id="admin", reason="清空")
    assert cleared["node"]["note"] == "" and cleared["score"] == 621 and cleared["frozen"]
    assert await read_relationship_override(le_store, other) is None
    for note in ("a\x00b", "a\x1bb", "a\x7fb", "a" * 1001):
        with pytest.raises(ValueError):
            await write_relationship_override(le_store, qq, note=note, expected_version=2,
                                              actor_id="admin", reason="invalid")


async def test_edit_disabled_rejects_before_selection(le_store, le_context):
    app = ConsoleDouble(le_store, le_context)
    with pytest.raises(ApplicationError) as error:
        await app.console_relationship("unknown", "unknown", "unknown", note="test",
                                       expected_version=0, actor_id="admin", reason="test")
    assert error.value.code == "edit_disabled"
    assert await le_store.audit_records() == []
