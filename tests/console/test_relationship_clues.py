"""Real temporary SQLite plus synthetic memory. No model, network or sends."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import EvidenceRef, ContentKind
from astrbot_plugin_livingemotion.ports.memory import Material, RecallResult, ValidationResult
from astrbot_plugin_livingemotion.storage.console_data import query_relationships
from test_management_dto import ConsoleDouble, selection


async def seed(store, context, event):
    sender = replace(context, platform="qq", account_id="123", audience=("synthetic-owner",))
    peer = replace(sender, account_id="456")
    for c in (sender, peer):
        await store.register_context(c)
    message = replace(event, context=sender, actor_id="123", body="我和@456是朋友")
    assert (await store.commit_event(message, 0)).accepted
    return sender, peer, message


async def test_record_projection_scope_denial_and_clear(le_store, le_context, le_event):
    sender, peer, event = await seed(le_store, le_context, le_event)
    async def graph(**changes):
        return await query_relationships(le_store, "local", selection(sender, **changes))
    result = await graph()
    assert len(result["peer_edges"]) == 1
    assert result["peer_edges"][0]["evidence"][0]["source_id"] == event.source_id
    assert (await graph(view_scope="group"))["peer_edges"] == []
    assert (await graph(platform="bilibili"))["peer_edges"] == []
    assert (await graph(context_id=sender.account_key))["peer_edges"] == []
    denial = replace(event, event_id="deny", source_id="deny",
                     body="我和@456不是朋友", occurred_at=event.occurred_at + .5)
    assert (await le_store.commit_event(denial, 0)).accepted
    assert (await graph())["peer_edges"] == []
    assert (await le_store.clear_scope(sender, 0)).accepted
    assert (await graph())["peer_edges"] == []
    # Even retained old bodies cannot escape the generation join.
    assert await le_store._run(lambda db: db.execute("SELECT COUNT(*) FROM body_window").fetchone()[0]) == 0


async def test_group_evidence_explicit_third_party_and_platform_isolation(le_store, le_context, le_event):
    group = replace(le_context, platform="qq", scene_kind="group", scene_id="synthetic-group",
                    account_id="123", audience=("synthetic-group",))
    contexts = [group, replace(group, account_id="456"), replace(group, account_id="789"),
                replace(group, platform="bilibili", account_id="456")]
    for context in contexts:
        await le_store.register_context(context)
    ref = EvidenceRef("livingemotion", "human-message", group, "123", group.bot_id,
                      ContentKind.INTERACTION, le_event.occurred_at)
    event = replace(le_event, context=group, actor_id="123", body="@456和@789是同学", evidence=(ref,))
    assert (await le_store.commit_event(event, 0)).accepted
    graph = await query_relationships(le_store, "local", selection(group, view_scope="group"))
    assert len(graph["peer_edges"]) == 1
    edge = graph["peer_edges"][0]
    people = {node["id"]: (node["platform"], node["account_id"]) for node in graph["nodes"]}
    assert {people[edge["source"]], people[edge["target"]]} == {("qq", "456"), ("qq", "789")}
    assert edge["evidence"][0]["basis"] == "他人陈述"
    assert (await query_relationships(le_store, "local", selection(group, view_scope="private")))["peer_edges"] == []


@pytest.mark.parametrize("fault", ["identity", "persona", "actor", "role", "expiry", "kind", "corrupt", "generation"])
async def test_rejects_ineligible_source_metadata(le_store, le_context, le_event, fault):
    sender, _, event = await seed(le_store, le_context, le_event)
    import json
    def corrupt(db):
        metadata = json.loads(db.execute("SELECT metadata_json FROM events").fetchone()[0])
        if fault == "identity":
            metadata["context"]["identity_revision"] = "revoked"
        elif fault == "persona":
            metadata["context"]["persona_revision"] = "revoked"
        elif fault == "actor":
            metadata["actor_id"] = "456"
        elif fault == "role":
            metadata["actor_role"] = "bot"
        elif fault == "expiry":
            db.execute("UPDATE events SET occurred_at=1")
            db.execute("UPDATE body_window SET occurred_at=1")
            metadata["occurred_at"] = 1
        elif fault == "generation":
            db.execute("UPDATE scopes SET generation=1")
        elif fault == "kind":
            metadata["evidence"] = [{
                "provider": "livingemotion", "source_id": "dream", "context": metadata["context"],
                "subject_id": "123", "holder_id": sender.bot_id, "kind": "dream",
                "occurred_at": event.occurred_at,
            }]
        db.execute("UPDATE events SET metadata_json=?",
                   ("{" if fault == "corrupt" else json.dumps(metadata),))
    await le_store._run(corrupt)
    assert (await query_relationships(le_store, "local", selection(sender)))["peer_edges"] == []


async def memory_app(store, sender, event, *, kind=ContentKind.INTERACTION):
    app = ConsoleDouble(store, sender)
    app.config = replace(app.config, memory_read=True)
    material = Material(EvidenceRef(
        "livingmemory", "memory-1", replace(sender, route=None), "123", sender.bot_id,
        kind, event.occurred_at + .5, source_ids=("human-source",) if kind == ContentKind.SUMMARY else (),
    ), "我和@456是同事" if kind == ContentKind.INTERACTION else "qq123和qq456是同事")
    calls = []
    async def current(context):
        return SimpleNamespace(event=lambda: event) if context.account_key == sender.account_key else None
    async def guard(context, generation=None):
        return generation is None or await store.get_generation(context) == generation
    async def recall(request, **kwargs):
        calls.append((request.purpose, request.limit, kwargs["event"]))
        return RecallResult((material,))
    async def validate(request, materials, **kwargs):
        return ValidationResult(True, materials)
    app.bridge.current = current
    app.validate_context = guard
    app.memory.recall, app.memory.validate_evidence = recall, validate
    return app, material, calls


@pytest.mark.parametrize("kind", [ContentKind.INTERACTION, ContentKind.FACT, ContentKind.SUMMARY])
async def test_authorized_memory_supplements_real_records(le_store, le_context, le_event, kind):
    sender, _, event = await seed(le_store, le_context, le_event)
    app, _, calls = await memory_app(le_store, sender, event, kind=kind)
    graph = await app.console_relationships(sender.persona_id)
    assert {edge["relation"] for edge in graph["peer_edges"]} == {"朋友", "同事"}
    assert calls == [("relationships", 4, event)]
    assert next(e for e in graph["peer_edges"] if e["relation"] == "同事")["evidence"][0]["kind"] == "记忆"


@pytest.mark.parametrize("fault", ["disabled", "no_event", "invalid", "changed_material", "failure",
                                 "expired", "wrong_scope", "dream", "empty_summary", "clear"])
async def test_optional_memory_fails_closed_and_records_survive(le_store, le_context, le_event, fault):
    sender, peer, event = await seed(le_store, le_context, le_event)
    app, material, calls = await memory_app(le_store, sender, event)
    if fault == "disabled":
        app.config = replace(app.config, memory_read=False)
    elif fault == "no_event":
        async def no_event(context):
            return SimpleNamespace(event=lambda: None)
        app.bridge.current = no_event
    elif fault in ("invalid", "changed_material"):
        async def invalid(request, materials, **kwargs):
            return ValidationResult(fault == "changed_material", ())
        app.memory.validate_evidence = invalid
    else:
        async def recall(request, **kwargs):
            if fault == "failure":
                raise RuntimeError("unavailable")
            if fault == "clear":
                await le_store.clear_scope(sender, 0)
            ref = material.evidence
            if fault == "expired":
                ref = replace(ref, expires_at=le_store.clock())
            elif fault == "wrong_scope":
                ref = replace(ref, context=peer)
            elif fault == "dream":
                ref = replace(ref, kind=ContentKind.DREAM)
            elif fault == "empty_summary":
                ref = replace(ref, kind=ContentKind.SUMMARY)
            return RecallResult((replace(material, evidence=ref),))
        app.memory.recall = recall
    graph = await app.console_relationships(sender.persona_id)
    assert {edge["relation"] for edge in graph["peer_edges"]} == (set() if fault == "clear" else {"朋友"})
    if fault in ("disabled", "no_event"):
        assert not calls
