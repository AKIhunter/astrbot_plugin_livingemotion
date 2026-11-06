"""T11 independent cross-module probes. No real models, transports or user data."""

import asyncio
import ast
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.adapters.identity import IdentityAdapter
from astrbot_plugin_livingemotion.adapters.memory import MemoryGateway
from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import (
    BotAffect, Context, Event, EvidenceRef, NightState, RelationshipContribution,
)
from astrbot_plugin_livingemotion.domain.relationship import project_relationship
from astrbot_plugin_livingemotion.ports.memory import Material, MemoryRequest
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.services.behavior import BehaviorHistory
from astrbot_plugin_livingemotion.services.experience import ExperienceService
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.tests.behavior import test_behavior as behavior_fixtures
from astrbot_plugin_livingemotion.tests.integration import test_application as app_fixtures
from astrbot_plugin_livingemotion.tests.memory import fakes

ROOT = Path(__file__).resolve().parents[2]


def facade(store):
    config = Config()
    return LivingEmotionAPI(
        store, config, BackgroundRuntime(store, config),
        project_event=Projector(store, lambda: config),
    )


def test_domain_ast_has_no_host_private_plugin_or_sql_access():
    allowed = {"__future__", "dataclasses", "datetime", "hashlib", "json", "math",
               "re", "typing", "unicodedata", "zoneinfo", "contracts", "emotion"}
    for path in sorted((ROOT / "domain").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] in allowed for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed, (path.name, node.lineno, node.module)
            elif isinstance(node, ast.Attribute):
                assert node.attr not in {"initializer", "store", "cfg", "execute", "send_message"}
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(table in node.value for table in ("mem_atom", "mem_subject",
                                                                 "msg_archive"))


async def test_api_fault_after_state_write_rolls_back_keys_trace_ledger_and_projection(
    le_store, le_event,
):
    api = facade(le_store)
    event = replace(le_event, signals=("care",))
    # Fault after state/key/event writes, unlike a preflight-invalid input test.
    with sqlite3.connect(le_store.path) as db:
        db.execute("CREATE TRIGGER verification_fault BEFORE INSERT ON event_traces "
                   "BEGIN SELECT RAISE(ABORT,'synthetic fault'); END")
    db.close()
    failed = await api.ingest_event(event)
    assert failed["status"] == "rejected" and failed["reason_code"] == "processing_failed"
    with sqlite3.connect(le_store.path) as db:
        counts = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in ("states", "events", "event_keys", "relationship_ledger",
                                "event_traces", "body_window")}
        db.execute("DROP TRIGGER verification_fault")
    db.close()
    assert set(counts.values()) == {0}, counts
    assert await le_store.human_watermark(event.context) == 0
    assert (await api.ingest_event(event))["status"] == "accepted"
    versions = (await le_store.get_state(event.context, "bot")).version
    assert versions == 1
    assert (await api.ingest_event(event))["status"] == "duplicate"
    assert (await le_store.get_state(event.context, "bot")).version == versions
    assert (await le_store.query_records(event.context, "emotion"))["total"] == 1


async def test_actual_projector_duplicate_race_applies_all_state_once(le_store, le_event):
    api = facade(le_store)
    results = await asyncio.gather(*(api.ingest_event(le_event) for _ in range(20)))
    assert [r["status"] for r in results].count("accepted") == 1
    assert [r["status"] for r in results].count("duplicate") == 19
    for kind, key in (("bot", ""), ("night", ""), ("relationship", le_event.context.account_id)):
        assert (await le_store.get_state(le_event.context, kind, key)).version == 1
    assert (await le_store.query_records(le_event.context, "emotion"))["total"] == 1


async def test_api_read_applies_elapsed_recovery_without_new_events(le_store, le_event):
    api = facade(le_store)
    await api.ingest_event(replace(le_event, signals=("conflict",)))
    before = (await api.get_bot_state(le_event.context))["data"]
    assert before["stress"] > 0
    stored = await le_store.get_state(le_event.context, "bot")
    counts = (await le_store.health())["counts"]
    le_store.clock = lambda: le_event.occurred_at + 86400
    later = (await api.get_bot_state(le_event.context))["data"]
    assert later["stress"] < before["stress"] / 100, {
        "before_stress": before["stress"], "after_24h_stress": later["stress"],
    }
    assert await le_store.get_state(le_event.context, "bot") == stored
    assert (await le_store.health())["counts"] == counts


async def test_application_behavior_snapshot_uses_same_readonly_recovery_as_api(tmp_path):
    app, host, _ = await app_fixtures.application(tmp_path)
    try:
        message = app_fixtures.Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        now = app.store.clock()
        event = Event("conflict", "verification", "message", context, "human",
                      now, "conflict", actor_id=context.account_id, signals=("conflict",))
        assert (await app.api.ingest_event(event))["status"] == "accepted"
        before = (await app.api.get_bot_state(context))["data"]["stress"]
        assert before > 0
        original = await app.store.get_state(context, "bot")
        app.store.clock = lambda: now + 86400
        current = await app.current_snapshot(context)
        public = (await app.api.get_bot_state(context))["data"]
        assert current.affect.stress == public["stress"] < before / 100
        assert await app.store.get_state(context, "bot") == original
        assert host.sends == 0
    finally:
        await app.terminate()


async def test_application_interaction_trace_expression_behavior_and_mode_controls(
    tmp_path, record_property,
):
    app, host, native = await app_fixtures.application(tmp_path, {
        "timezone": "UTC", "night_schedule_enabled": False,
    })
    now = 1_800_000_000
    app.store.clock = lambda: now
    provider_lookups = []

    async def no_provider(route):
        provider_lookups.append(route)
        raise AssertionError("C08 must not request a model")

    host.get_current_chat_provider_id = no_provider
    message = app_fixtures.Message(identifier="c08-native-source", body="Synthetic interaction.")

    async def expression():
        request = SimpleNamespace(extra_user_content_parts=[SimpleNamespace(text="native block")])
        await app.on_llm_request(message, request)
        assert len(request.extra_user_content_parts) == 2
        block = request.extra_user_content_parts[-1].text
        assert block.startswith(app_fixtures.SUFFIX)
        return json.loads(block.split("\n", 2)[2])

    try:
        await app.on_message(message)
        assert message.extra["livingemotion:ingest"] == "accepted"
        context = Context.from_dict(message.extra["livingemotion:context"])
        native.update(autonomy_enabled=True, autonomy_scopes=context.scope_key)
        await app.refresh_config()
        before = (await app.api.get_bot_state(context))["data"]
        before_expression = await expression()
        before_evaluation = await app.behavior.evaluate(context)
        assert before_evaluation.score is not None
        event = Event(
            "c08-conflict", "verification", "message", context, "human", now,
            "c08-conflict-source", actor_id=context.account_id, signals=("conflict",),
        )
        assert (await app.api.ingest_event(event))["status"] == "accepted"
        after = (await app.api.get_bot_state(context))["data"]
        assert after["stress"] > before["stress"]
        after_expression = await expression()
        assert after_expression["bot"]["stress"] == after["stress"]
        assert before_expression["bot"]["stress"] == before["stress"]
        after_evaluation = await app.behavior.evaluate(context)
        assert after_evaluation.score is not None
        assert after_evaluation.score != before_evaluation.score
        records = await app.store.query_records(context, "emotion")
        trace = next(
            item["value"] for item in records["items"]
            if item["value"]["event_id"] == event.event_id
        )
        assert trace["event_key"] == event.idempotency_key
        assert trace["before"]["stress"] == before["stress"]
        assert trace["after"]["stress"] == after["stress"]
        assert trace["holder_id"] == context.bot_id and trace["subject_id"] == context.account_id
        assert trace["rule_version"] == "emotion-1" and "rule_conflict" in trace["reason_codes"]

        native["mode"] = "observe_only"
        await app.refresh_config()
        observed = app_fixtures.Message(identifier="c08-observe", body="Another synthetic source.")
        count = (await app.store.health())["counts"]["events"]
        await app.on_message(observed)
        assert observed.extra["livingemotion:ingest"] == "accepted"
        assert (await app.store.health())["counts"]["events"] == count + 1
        request = SimpleNamespace(extra_user_content_parts=[
            SimpleNamespace(text="native block"), SimpleNamespace(text=app_fixtures.SUFFIX + "old"),
        ])
        await app.on_llm_request(observed, request)
        assert [part.text for part in request.extra_user_content_parts] == ["native block"]
        result = await app.behavior.execute(context, intent_id="c08-observe-rejected")
        assert result.status == "rejected" and "observe_only" in result.reason_codes
        assert not provider_lookups and host.sends == 0

        native["enabled"] = False
        await app.refresh_config()
        assert app.runtime.health()["workers"] == 0 and app._scheduler is None
        disabled = app_fixtures.Message(identifier="c08-disabled")
        await app.on_message(disabled)
        assert "livingemotion:context" not in disabled.extra
        record_property("measurements", json.dumps({
            "before_stress": before["stress"], "after_stress": after["stress"],
            "before_behavior_score": before_evaluation.score,
            "after_behavior_score": after_evaluation.score,
            "expression_uses_current_state": True, "trace_matches_event": True,
            "observe_only_records_without_injection": True, "disabled_workers": 0,
            "provider_lookups": len(provider_lookups), "send_stub_calls": host.sends,
        }))
    finally:
        await app.terminate()


async def test_correlation_records_and_health_exclude_private_body_and_exception(
    le_store, le_event, real_history_behavior, caplog, capsys,
):
    marker = "SYNTHETIC_PRIVATE_BODY_NOT_FOR_DIAGNOSTICS"
    api = facade(le_store)
    event = replace(le_event, body=marker, signals=("care",))
    assert (await api.ingest_event(event))["status"] == "accepted"
    records = await le_store.query_records(event.context, "emotion")
    assert records["total"] == 1
    assert records["items"][0]["event_key"] == event.idempotency_key
    assert records["items"][0]["value"]["reason_codes"]
    runtime = BackgroundRuntime(le_store, Config())
    await runtime.start()

    async def fail():
        raise RuntimeError(marker)

    try:
        assert (await runtime.submit("synthetic-request-c53", event.context, 0, fail))[
            "status"
        ] == "queued"
        await runtime.join()
        diagnostic = runtime.health()
        assert diagnostic["outcomes"] == [{
            "job_id": "synthetic-request-c53", "status": "failed", "reason_code": "job_failed",
        }]
        h = real_history_behavior
        h.outcome = None

        async def generated(_request):
            return marker

        h.on_model = generated
        result = await h.execute("synthetic-intent-c53")
        intents = await h.store.query_records(h.context, "behavior")
        assert result.status == "unknown" and intents["items"][0]["id"] == result.intent_id
        assert intents["items"][0]["reason_code"]
        plain = json.dumps([records, diagnostic, intents, await le_store.health()])
        captured = capsys.readouterr()
        assert marker not in plain + caplog.text + captured.out + captured.err
    finally:
        await runtime.stop()


async def test_expired_and_out_of_order_observation_does_not_rejuvenate(le_store, le_event):
    api = facade(le_store)
    await api.ingest_event(replace(le_event, signals=("sadness",)))
    first = (await api.get_observation(le_event.context))["data"]
    old = replace(le_event, source_id="late", event_id="late",
                  occurred_at=le_event.occurred_at - 100, signals=("anger",))
    assert (await api.ingest_event(old))["status"] == "accepted"
    assert (await api.get_observation(le_event.context))["data"] == first
    le_store.clock = lambda: le_event.occurred_at + 7201
    assert (await api.get_observation(le_event.context))["data"] is None
    assert (await api.ingest_event(old))["status"] == "duplicate"
    assert (await api.get_observation(le_event.context))["data"] is None


async def test_retained_source_ledger_can_unbind_after_all_events_deleted(tmp_path):
    now = [150.0]
    provider = fakes.Provider()
    identities = IdentityAdapter(lambda: provider)
    event = fakes.Event()
    identity = await identities.resolve(fakes.context(), event=event)
    first = identity.context
    second = replace(first, platform="bili", account_id="linked", scene_id="linked")
    store = SQLiteStore(tmp_path / "sources.db", clock=lambda: now[0])
    await store.open()
    try:
        api = facade(store)
        for i, context in enumerate((first, second)):
            await store.register_context(context)
            assert (await api.ingest_event(Event(
                f"e{i}", "verification", "message", context, "human", 150,
                f"s{i}", actor_id=context.account_id, signals=("care",),
                body="Synthetic retained-ledger source.",
            )))["status"] == "accepted"
        original_rows = {
            c.account_key: await store.relationship_ledger(c) for c in (first, second)
        }
        now[0] += 31 * 86400
        await store.cleanup()
        await store.close()
        store = SQLiteStore(store.path, clock=lambda: now[0])
        await store.open()
        assert (await store.health())["counts"]["events"] == 0
        sources = await store.list_contexts()
        assert {c.account_key for c in sources} == {first.account_key, second.account_key}
        ledger = []
        for source in sources:
            rows = await store.relationship_ledger(source)
            assert rows == original_rows[source.account_key]
            assert all("body" not in row for row in rows)
            for row in rows:
                ledger.append((source, RelationshipContribution(**{
                    name: row[name] for name in (
                        "source_id", "account_id", "occurred_at", "delta",
                        "reason_code", "day", "dimension",
                    )
                })))
        granted = await identities.project_sources(identity, sources, event=event)
        bound = project_relationship(
            ledger, context=first, authorized_account_keys=[c.account_key for c in granted],
            identity_revision=first.identity_revision,
        )
        assert bound.score == 6
        provider.bound, provider.revision = False, provider.revision + 1
        assert await identities.project_sources(identity, sources, event=event) == ()
        current = await identities.resolve(first, event=event)
        granted = await identities.project_sources(current, sources, event=event)
        unbound = project_relationship(
            ledger, context=current.context,
            authorized_account_keys=[c.account_key for c in granted],
            identity_revision=current.context.identity_revision,
        )
        assert unbound.score == 3
        assert sum(r["delta"] for r in await store.relationship_ledger(second)
                   if r["dimension"] == "score") == 3
    finally:
        await store.close()


@pytest.mark.parametrize("change", [
    {"bot_id": "another"}, {"persona_id": "another"}, {"instance_id": "another"},
    {"platform": "another"}, {"adapter_id": "another"}, {"scene_id": "another"},
    {"scene_kind": "group"}, {"scene_kind": "public_comment", "route": None},
])
async def test_state_reason_and_material_isolation_matrix(le_store, le_event, change):
    api = facade(le_store)
    event = replace(le_event, signals=("sadness",))
    assert (await api.ingest_event(event))["status"] == "accepted"
    foreign = replace(event.context, **change)
    assert (await api.get_bot_state(foreign))["data"] == json.loads(
        json.dumps(BotAffect().__dict__, default=list)
    )
    assert (await api.get_observation(foreign))["data"] is None
    assert (await api.get_relationship(foreign))["data"]["score"] == 0
    assert (await le_store.query_records(foreign, "emotion"))["total"] == 0
    assert await le_store.read_window(foreign) == []
    gateway = MemoryGateway(clock=le_store.clock)
    material = Material(EvidenceRef(
        "livingemotion", event.source_id, event.context, event.actor_id,
        event.context.bot_id, "interaction", event.occurred_at, event.occurred_at + 1000,
        source_ids=(event.source_id,),
    ), "Synthetic private material.")
    try:
        result = await gateway.recall(MemoryRequest(
            "isolated-request", "diary", foreign, "",
        ), available=(material,))
        assert result.materials == ()
    finally:
        await gateway.close()


@pytest.fixture
async def real_history_behavior():
    h = behavior_fixtures.BehaviorTests()
    await h.asyncSetUp()

    async def history(context, period, exclude):
        return BehaviorHistory(**await h.store.behavior_history(context, period, exclude))

    h.history = history
    h.service.history = history
    try:
        yield h
    finally:
        await h.asyncTearDown()
        h.doCleanups()


async def test_unknown_real_history_survives_reopen_retention_and_clear(real_history_behavior):
    h = real_history_behavior
    h.outcome = None
    assert (await h.execute("unknown-1")).status == "unknown"
    h.now += 7201
    assert (await h.execute("unknown-2")).status == "unknown"
    assert len(h.platform_calls) == 2
    await h.restart()
    assert (await h.execute("unknown-1")).status == "unknown"
    assert len(h.platform_calls) == 2
    h.now += 31 * 86400
    await h.store.cleanup()
    await h.store.clear_scope(h.context, 0, actor_id="synthetic-admin")
    await h.restart()
    day = datetime.fromtimestamp(h.now, timezone.utc).date().isoformat()
    history = await h.store.behavior_history(h.context, day)
    assert history["unanswered_count"] == 2
    preview = await h.service.evaluate(h.context)
    assert not preview.eligible and "unanswered_backoff" in preview.reason_codes
    assert len(h.platform_calls) == 2


class IdentityProvider:
    def __init__(self):
        self.revision = 1

    async def resolve_identity_context(self, event, persona_id=""):
        account = event.get_sender_id()
        return {
            "platform": "qq", "account_id": account, "source_account": f"qq:{account}",
            "one_id": "synthetic-person", "person_id": "synthetic-person",
            "identity_revision": self.revision, "owner_account": "qq:bot-account",
            "owner_one_id": "synthetic-bot", "scene_kind": "private", "scene_id": account,
            "persona_id": persona_id, "origin_session_id": event.unified_msg_origin,
            "audience": "self_private", "is_bound": True,
            "bound_accounts": [{"platform": "qq", "account_id": account}],
        }


async def test_application_bound_relationship_read_reprojects_retained_ledger(
    tmp_path, record_property,
):
    app, host, _ = await app_fixtures.application(tmp_path)

    class BoundProvider(IdentityProvider):
        bound = True

        async def resolve_identity_context(self, event, persona_id=""):
            value = await super().resolve_identity_context(event, persona_id)
            return {**value, "is_bound": self.bound, "bound_accounts": [
                {"platform": "qq", "account_id": "human"},
                {"platform": "qq", "account_id": "linked"},
            ] if self.bound else []}

    provider = BoundProvider()
    host.get_registered_star = lambda name: (
        SimpleNamespace(activated=True, star_cls=provider)
        if name == "astrbot_plugin_livingmemory" else None
    )
    try:
        messages = [app_fixtures.Message(identifier=f"source-{account}", account=account)
                    for account in ("human", "linked")]
        contexts = []
        for message in messages:
            await app.on_message(message)
            contexts.append(Context.from_dict(message.extra["livingemotion:context"]))
        values = [(await app.store.get_state(c, "relationship", c.account_id)).value["score"]
                  for c in contexts]
        assert values == [0.5, 0.5]
        original = [await app.store.relationship_ledger(c) for c in contexts]
        now = app.store.clock() + 31 * 86400
        app.store.clock = lambda: now
        await app.store.cleanup()
        events_after_cleanup = (await app.store.health())["counts"]["events"]
        assert events_after_cleanup == 0
        bound = (await app.api.get_relationship(contexts[0]))["data"]["score"]
        provider.bound, provider.revision = False, provider.revision + 1
        await app.on_message(messages[0])  # Duplicate source updates identity, not the ledger.
        current = Context.from_dict(messages[0].extra["livingemotion:context"])
        unbound = (await app.api.get_relationship(current))["data"]["score"]
        assert [await app.store.relationship_ledger(c) for c in contexts] == original
        assert (bound, unbound) == (sum(values), values[0]), {
            "local_scores": values, "bound_api_score": bound, "unbound_api_score": unbound,
        }
        assert host.sends == 0
        record_property("measurements", json.dumps({
            "local_scores": values, "bound_api_score": bound, "unbound_api_score": unbound,
            "events_after_31_days": events_after_cleanup, "ledger_unchanged": True,
            "send_stub_calls": host.sends,
        }))
    finally:
        await app.terminate()


@pytest.mark.parametrize("target_change", [
    {"scene_kind": "group", "scene_id": "room", "route": "qq-instance:GroupMessage:room",
     "audience": ("group:room",)},
    {"scene_kind": "public_comment", "scene_id": "comment-1", "route": None,
     "audience": ("public",)},
    {"instance_id": "other-host"},
])
async def test_identity_grant_does_not_turn_private_account_binding_into_scene_access(
    target_change,
):
    private = fakes.context()
    target = replace(private, **target_change)
    provider = fakes.Provider()
    event = fakes.Event(target)
    provider.return_identity = {
        **await provider.resolve_identity_context(event, target.persona_id),
        "audience": "group:room" if target.scene_kind == "group" else "self_private",
    }
    identities = IdentityAdapter(lambda: provider)
    identity = await identities.resolve(target, event=event)
    granted = await identities.project_sources(identity, (private,), event=event)
    assert granted == (), {
        "target_kind": target.scene_kind.value, "target_instance": target.instance_id,
        "granted_private_sources": len(granted),
    }


@pytest.mark.parametrize("change", ["persona", "identity", "human", "clear", "unchanged"])
async def test_application_inflight_generation_uses_live_persona_and_identity(tmp_path, change):
    app, host, native = await app_fixtures.application(tmp_path)
    provider = IdentityProvider()
    original_discover = host.get_registered_star
    host.get_registered_star = lambda name: (
        SimpleNamespace(activated=True, star_cls=provider)
        if name == "astrbot_plugin_livingmemory" else original_discover(name)
    )
    entered, release = asyncio.Event(), asyncio.Event()
    task = None
    try:
        message = app_fixtures.Message(body="Synthetic real source.")
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert context.identity_revision == "livingmemory:1"
        record = await app.store.get_state(context, "relationship", context.account_id)
        assert (await app.store.correct_relationship(
            context, 0, expected_version=record.version, actor_id="synthetic-admin",
            reason="Set eligible relationship", score=700,
        )).accepted
        native.update(autonomy_enabled=True, autonomy_scopes=context.scope_key,
                      timezone="UTC", dnd_start="00:00", dnd_end="00:01")
        await app.refresh_config()

        async def model(_request):
            entered.set()
            await release.wait()
            return "Synthetic content from the original persona and identity."

        app.behavior.model = model
        task = asyncio.create_task(app.behavior.execute(context, intent_id="live-change"))
        await asyncio.wait_for(entered.wait(), 3)
        if change == "persona":
            host.prompt = "Changed native persona"
        elif change == "identity":
            provider.revision += 1
        elif change == "human":
            newer = app_fixtures.Message(identifier="new-human")
            await app.on_message(newer)
        elif change == "clear":
            await app.store.clear_scope(context, 0, actor_id="synthetic-admin")
        release.set()
        result = await task
        if change == "unchanged":
            assert result.status == "unknown" and host.sends == 1
        else:
            assert result.status == "cancelled" and host.sends == 0
    finally:
        release.set()
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await app.terminate()


@pytest.mark.parametrize("mode", ["none", "local_lite", "external"])
async def test_live_mode_switch_keeps_core_states_and_sleep(tmp_path, mode):
    app, host, native = await app_fixtures.application(tmp_path)
    try:
        message = app_fixtures.Message(body="Synthetic source.")
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        before = (await app.api.get_relationship(context))["data"]["score"]
        native["memory_mode"] = mode
        await app.refresh_config()
        newer = app_fixtures.Message(identifier="after-switch")
        await app.on_message(newer)
        context = Context.from_dict(newer.extra["livingemotion:context"])
        assert (await app.api.get_relationship(context))["data"]["score"] > before
        await app.advance_scope(context, action="night.sleep")
        assert (await app.api.get_availability(context))["available"] is False
        # The v2 switch selects external or the local vector interface. Legacy
        # local_lite records remain readable through that interface.
        assert app.memory.capabilities().mode == (
            "external" if mode == "external" else "local_vector"
        )
        assert app.config.memory_read is False and app.config.memory_write is False
        assert host.sends == 0
    finally:
        await app.terminate()


async def test_experience_none_memory_real_loader_and_pin_survive_restart(tmp_path, le_context):
    le_context = replace(le_context, audience=("human-1", "bot-1"))
    now = [datetime(2026, 11, 5, 23, 30, tzinfo=timezone.utc).timestamp()]
    config = Config(diary_enabled=True, dream_enabled=True)
    store = SQLiteStore(tmp_path / "experience.db", config=config, clock=lambda: now[0])
    await store.open()
    runtime = BackgroundRuntime(store, config)
    await runtime.start()
    calls = []
    credential = object()

    async def model(request):
        calls.append(request.purpose)
        return {"body": "A synthetic sourced reflection."}

    async def guard(context, generation):
        return context == le_context and await store.get_generation(context) == generation

    async def access(value, operation, context):
        return value is credential and context == le_context

    async def night_guard(context, original):
        return original.sleep_stage == "REM"

    async def pin(old, new, generation):
        return await store.pin_experience(
            old, new, generation, actor_id="synthetic-admin", reason="Verification pin",
        )

    service = ExperienceService(
        store, runtime, model=model, count_tokens=lambda system, data: len(system) + len(data),
        guard=guard, authorize=access, load=store.load_experience,
        write_pin=pin, save_guarded=store.save_experience_guarded, night_guard=night_guard,
    )
    try:
        await store.commit_event(Event(
            "source", "verification", "message", le_context, "human", now[0] - 60,
            "source", actor_id=le_context.account_id, body="Synthetic source.",
        ), 0)
        diary = await service.queue_diary(le_context)
        assert diary["status"] == "queued", diary
        await runtime.join()
        assert service.outcome(diary["job_id"])["status"] == "created"
        loaded = await store.load_experience(diary["experience_id"])
        assert tuple(loaded[0].evidence[0].source_ids) == ("source",)
        dream = await service.queue_dream(le_context, NightState(
            phase="asleep", energy=50, updated_at=now[0], sleep_started_at=now[0] - 3600,
            wake_at=now[0] + 3600, sleep_stage="REM",
        ))
        await runtime.join()
        assert service.outcome(dream["job_id"])["status"] == "created"
        result = await service.set_pin(dream["experience_id"], le_context, credential, pinned=True)
        assert result["status"] == "updated"
        assert len(await store.audit_records(le_context)) == 1
        await runtime.stop()
        await service.close()
        await store.close()
        store = SQLiteStore(store.path, config=config, clock=lambda: now[0])
        await store.open()
        loaded, generation = await store.load_experience(dream["experience_id"])
        assert loaded.pinned and loaded.kind == "dream" and generation == 0
        now[0] += 8 * 86400
        await store.cleanup()
        assert await store.read_window(le_context) == []
        assert (await store.load_experience(dream["experience_id"]))[0].pinned
        assert calls == ["diary", "dream"]
    finally:
        await runtime.stop()
        await service.close()
        await store.close()
