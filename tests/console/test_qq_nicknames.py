from dataclasses import replace
import json

from astrbot_plugin_livingemotion.contracts import SceneKind, canonical_json
from astrbot_plugin_livingemotion.storage.console_data import (
    NICKNAME_PREFIX, query_relationships, query_scopes, remember_qq_nickname,
)
from test_management_dto import selection


async def test_nickname_follows_selected_real_sources_and_clear_fences_late_write(le_store, le_context, le_event):
    private = replace(le_context, platform="qq", account_id="12345678")
    group = replace(private, scene_kind=SceneKind.GROUP, scene_id="34567890")
    other = replace(private, platform="bilibili")
    for number, context in enumerate((private, group, other)):
        await le_store.register_context(context)
        assert (await le_store.commit_event(replace(
            le_event, context=context, actor_id=context.account_id,
            event_id=f"nickname-{number}", source_id=f"nickname-{number}"), 0)).accepted
    await remember_qq_nickname(le_store, private, "小雨", 0, occurred_at=10)
    await remember_qq_nickname(le_store, group, "小雨的新QQ名", 0, occurred_at=20)
    await remember_qq_nickname(le_store, group, "过期名字", 0, occurred_at=19)
    await remember_qq_nickname(le_store, other, "非QQ名字", 0, occurred_at=30)
    read = lambda **changes: query_relationships(le_store, "local", selection(private, **changes))
    assert (await read(view_scope="private", platform="qq"))["nodes"][0]["label"] == "小雨"
    assert (await read(view_scope="group"))["nodes"][0]["label"] == "小雨的新QQ名"
    nodes = (await read())["nodes"]
    assert {n["platform"]: n["label"] for n in nodes} == {
        "qq": "小雨的新QQ名", "bilibili": "12345678"}
    assert (await query_relationships(le_store, "local", selection(private), query="小雨"))["total"] == 1
    assert (await query_scopes(le_store, "local", selection(private)))["contexts"]
    assert (await le_store.clear_scope(group, 0)).accepted
    await remember_qq_nickname(le_store, group, "迟到回调", 0, occurred_at=40)
    assert (await read(view_scope="group"))["nodes"][0]["label"] == "12345678"
    assert (await read(view_scope="private", platform="qq"))["nodes"][0]["label"] == "小雨"
    rows = await le_store._run(lambda db: list(db.execute(
        "SELECT value FROM runtime_meta WHERE key LIKE 'console.qq.nickname.v1:%'")))
    assert len(rows) == 1


async def test_old_group_card_cache_is_hidden_until_verified_qq_name(le_store, le_context, le_event):
    context = replace(le_context, platform="qq", account_id="12345678",
                      scene_kind=SceneKind.GROUP, scene_id="34567890")
    await le_store.register_context(context)
    assert (await le_store.commit_event(replace(
        le_event, context=context, actor_id=context.account_id), 0)).accepted
    await remember_qq_nickname(le_store, context, "旧群名片", 0, occurred_at=10)

    def legacy_cache(db):
        key = NICKNAME_PREFIX + context.account_key
        value = json.loads(db.execute(
            "SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()[0])
        value.pop("qq_name_verified")
        db.execute("UPDATE runtime_meta SET value=? WHERE key=?", (canonical_json(value), key))
    await le_store._run(legacy_cache)
    selected = selection(context, view_scope="group")
    assert (await query_relationships(le_store, "local", selected))["nodes"][0]["label"] == "12345678"
    assert (await query_scopes(le_store, "local", selected))["contexts"][0]["nickname"] == ""
    await remember_qq_nickname(le_store, context, "真正QQ名字", 0, occurred_at=20)
    assert (await query_relationships(le_store, "local", selected))["nodes"][0]["label"] == "真正QQ名字"
