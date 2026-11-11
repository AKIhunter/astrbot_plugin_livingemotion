"""Portable P5 tests: real temporary storage, synthetic host, no model or sends."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.config import Config, LEGACY_FIELDS
from astrbot_plugin_livingemotion.contracts import (
    HumanObservation, NightPhase, NightState, Relationship, StateWrite, to_dict,
)
from astrbot_plugin_livingemotion.domain.emotion import EmotionPolicy
from astrbot_plugin_livingemotion.runtime.console import (
    ApplicationError, Console, night_display_state,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.storage.console_data import (
    ConsoleDataConflict, apply_relationship_override, query_console_records, query_relationships,
    query_scopes, read_relationship_override, selected_contexts, write_relationship_override,
)


def selection(context, **changes):
    return {"persona_id": context.persona_id, "view_scope": "global", "context_id": "",
            "platform": "", **changes}


async def test_scope_selection_keeps_real_context_and_instance(le_store, le_context):
    contexts = [le_context, replace(le_context, platform="qq", account_id="123"),
                replace(le_context, platform="bilibili", account_id="123"),
                replace(le_context, persona_id="other"),
                replace(le_context, instance_id="other-instance")]
    for context in contexts:
        await le_store.register_context(context)
    result = await query_scopes(le_store, "local", selection(le_context))
    assert result["counts"]["global"] == 3
    assert len(result["contexts"]) == 3
    assert all(c["view_scope"] != "global" for c in result["contexts"])
    chosen = await selected_contexts(le_store, "local",
                                     selection(le_context, platform="qq"))
    assert [(c.platform, c.account_id) for c in chosen] == [("qq", "123")]
    with pytest.raises(ValueError):
        await selected_contexts(le_store, "local", selection(
            le_context, context_id=contexts[1].account_key, platform="bilibili"))


async def test_relationship_platform_keys_override_restart_version_and_audit(
        le_store, le_context, tmp_path):
    qq = replace(le_context, platform="qq", account_id="123")
    bili = replace(qq, platform="bilibili")
    group = replace(qq, scene_kind="group", scene_id="real-group")
    for context in (qq, bili, group):
        await le_store.register_context(context)
    result = await query_relationships(le_store, "local", selection(qq))
    assert result["total"] == 2
    assert len({n["id"] for n in result["nodes"]}) == 2
    assert all(n["trust"] is None and n["boundary"] is None for n in result["nodes"])
    wrote = await write_relationship_override(
        le_store, qq, score=62.1, expected_version=0, actor_id="dashboard-admin", reason="manual")
    assert wrote["score"] == 621 and wrote["node"]["score"] == 62.1
    with pytest.raises(ConsoleDataConflict):
        await write_relationship_override(
            le_store, qq, score=90, expected_version=0, actor_id="dashboard-admin", reason="stale")
    assert len(await le_store.audit_records()) == 1
    audit = (await le_store.audit_records())[0]
    assert audit["actor_id"] == "dashboard-admin"
    assert audit["value"]["after"]["platform"] == "qq"
    assert audit["value"]["version"] == 1
    assert await read_relationship_override(le_store, bili) is None
    assert (await read_relationship_override(le_store, group))["score"] == 621
    projected = Relationship(score=5, trust=None, familiarity=0.25, boundary=None)
    effective = await apply_relationship_override(le_store, group, projected)
    assert effective.score == 621 and effective.stage == "stage_3"
    assert effective.trust is None and effective.familiarity == 0.25
    assert await apply_relationship_override(le_store, qq, None) is None
    # A separate store connection establishes persistence without in-memory cache.
    reopened = SQLiteStore(le_store.path, clock=le_store.clock)
    await reopened.open()
    try:
        assert (await read_relationship_override(reopened, qq))["version"] == 1
    finally:
        await reopened.close()


async def test_override_freeze_and_concurrent_cas(le_store, le_context):
    await le_store.register_context(le_context)
    await write_relationship_override(le_store, le_context, score=1.1, expected_version=0,
                                      actor_id="admin", reason="first")
    outcomes = await asyncio.gather(*[
        write_relationship_override(le_store, le_context, frozen=True, expected_version=1,
                                    actor_id="admin", reason="freeze") for _ in range(2)
    ], return_exceptions=True)
    assert sum(isinstance(x, ConsoleDataConflict) for x in outcomes) == 1
    effective = await apply_relationship_override(le_store, le_context, Relationship(score=999))
    assert effective.frozen is True and effective.score == 11
    assert len(await le_store.audit_records()) == 2


@pytest.mark.parametrize("value", [
    True, -0.1, 100.1, 1.01, float("nan"), float("inf"), "1", 10**400,
])
async def test_override_invalid_scores_never_write(le_store, le_context, value):
    with pytest.raises(ValueError):
        await write_relationship_override(le_store, le_context, score=value, expected_version=0,
                                          actor_id="admin", reason="invalid")
    assert await read_relationship_override(le_store, le_context) is None
    assert await le_store.audit_records() == []


async def test_relationship_graph_table_same_query_and_ten_pagination(le_store, le_context):
    for number in range(23):
        await le_store.register_context(replace(le_context, account_id=f"account-{number:02}"))
    first = await query_relationships(le_store, "local", selection(le_context), limit=20)
    assert first["total"] == 23 and first["displayed"] == 20
    assert first["items"] == first["nodes"][:10]
    assert all(edge["source"] == first["center"]["id"] for edge in first["edges"])
    third = await query_relationships(le_store, "local", selection(le_context), page=3)
    assert len(third["items"]) == 3 and third["total"] == 23
    found = await query_relationships(le_store, "local", selection(le_context), query="account-22")
    assert found["total"] == 1


async def test_emotion_query_does_not_load_diary(le_store, le_context, monkeypatch):
    await le_store.register_context(le_context)
    def seed(db):
        for number in range(23):
            for kind in ("emotion", "diary"):
                db.execute("INSERT INTO event_traces VALUES(?,?,?,?,?,?)",
                           (str(number), le_context.scope_key, 0, kind, number,
                            '{"label":"real emotion","body":"private diary"}'))
    await le_store._run(seed)
    app = ConsoleDouble(le_store, le_context)
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("emotion must never load experience")
    monkeypatch.setattr(le_store, "load_experience", forbidden)
    result = await app.console_records(persona_id=le_context.persona_id,
                                       view_scope="global", kind="emotion", page=3)
    assert result["total"] == 23 and len(result["items"]) == 3
    assert all("body" not in row and row["label"] == "real emotion" for row in result["items"])
    exact = await query_console_records(le_store, "local", selection(le_context),
                                        "emotion", query="real emotion")
    assert exact["total"] == 23


class ConsoleDouble(Console):
    def __init__(self, store, context):
        self.store, self.instance_id = store, context.instance_id
        self.config, self.revision = Config(), "revision-1"
        self.closed = False
        self._contexts = {context.account_key: context}
        self._config_fault = self._task_fault = ""
        self.memory = SimpleNamespace(capabilities=lambda: SimpleNamespace(
            recall=False, append_experience=False, reason_codes=()))
        self.bridge = SimpleNamespace(conflicts=lambda c: False, source=lambda c: None)
        self.behavior = SimpleNamespace(preview_behavior=self.preview)
        self.emotion_policy = EmotionPolicy()

    async def refresh_config(self):
        pass

    async def preview(self, context):
        return SimpleNamespace(eligible=False, reason_codes=())

    def effective_mode(self, context):
        return "observe_only"

    async def current_relationship(self, context):
        return None

    async def night_snapshot(self, context):
        return NightState(phase=NightPhase.AWAKE, energy=74.1)

    async def availability(self, context):
        return SimpleNamespace(available=True, block_chat=False, reason_codes=())

    async def model_binding(self, context):
        raise ValueError("synthetic model unavailable")


async def test_state_baseline_and_global_no_action_route(le_store, le_context):
    await le_store.register_context(le_context)
    app = ConsoleDouble(le_store, le_context)
    state = await app.console_state(persona_id=le_context.persona_id, view_scope="global")
    assert state["context_id"] == ""
    assert state["action_target"]["context_id"] == le_context.account_key
    assert not next(a for a in state["actions"] if a["id"] == "behavior.send")["enabled"]
    assert state["night"]["energy_percent"] == 74.1 and state["night"]["energy"] == 0.741
    assert state["bot_state"]["baseline"] == {
        "pleasure": 0.5, "arousal": 0.3, "stress": 0, "social_need": 0.3}
    assert state["night"]["display_state"] == "awake"
    assert state["observation"] is None
    with pytest.raises(ApplicationError):
        await app.console_preview("")


async def test_console_baseline_and_decay_share_actual_policy(le_store, le_context, monkeypatch):
    from astrbot_plugin_livingemotion.contracts import BotAffect
    await le_store.register_context(le_context)
    raw_baseline = (0.2, 0.5, 0.1, 0.4)
    monkeypatch.setattr(EmotionPolicy, "baseline", property(lambda self: raw_baseline))
    committed = await le_store.write_states(le_context, await le_store.get_generation(le_context), (
        StateWrite("bot", to_dict(BotAffect(updated_at=0))),
    ))
    assert committed.accepted
    state = await ConsoleDouble(le_store, le_context).console_state()
    expected = {"pleasure": 0.6, "arousal": 0.5, "stress": 0.1, "social_need": 0.4}
    assert state["bot_state"]["baseline"] == expected
    assert state["bot_state"]["dimensions"] == expected


@pytest.mark.parametrize("shared", [False, True])
async def test_legacy_default_keeps_real_account_observation_with_owner(
        le_store, le_context, shared):
    await le_store.register_context(le_context)
    owner = await le_store.initialize_state_mode(le_context, shared=shared)
    observation = HumanObservation(le_context.account_id, ("sad",), 1,
                                   le_store.clock(), le_store.clock() + 7200)
    committed = await le_store.write_states(le_context, await le_store.get_generation(le_context), (
        StateWrite("observation", to_dict(observation), record_key=le_context.account_id,
                   owner=owner),
    ))
    assert committed.accepted
    app = ConsoleDouble(le_store, le_context)
    state = await app.console_state()
    assert state["selection"] is None
    assert state["context_id"] == le_context.account_key
    assert state["observation"]["subject"] == le_context.account_id
    assert state["observation"]["label"] == "sad"
    global_state = await app.console_state(persona_id=le_context.persona_id, view_scope="global")
    assert global_state["observation"] is None


@pytest.mark.parametrize(("phase", "display"), [
    ("awake", "awake"), ("drowsy", "groggy"), ("settling", "drowsy"),
    ("asleep", "deep_sleep"), ("waking", "groggy"),
])
def test_legacy_phase_additive_dto(phase, display):
    assert night_display_state(NightState(phase=phase)) == display


def test_new_five_display_states_take_precedence():
    for display in ("awake", "nap", "groggy", "drowsy", "deep_sleep"):
        assert night_display_state(SimpleNamespace(display_state=display)) == display


async def test_config_float_chinese_units_readonly_and_groups(le_store, le_context):
    app = ConsoleDouble(le_store, le_context)
    dto = app.config_dto()
    fields = {f["key"]: f for f in dto["fields"]}
    for name in ("energy_reply_cost", "energy_fatigue_per_minute", "energy_recovery_per_minute"):
        assert fields[name]["type"] == "float" and fields[name]["step"] == 0.1
        assert fields[name]["label"] != name and fields[name]["section"] == "night"
    assert dto["readonly"][0]["value"] == 100 and dto["readonly"][0]["readonly"] is True
    assert all(f["value"] == dto["values"][f["key"]] for f in fields.values())
    quick = next(g for g in dto["groups"] if g["id"] == "quick_start")
    assert "home_city" in quick["field_keys"]
    assert not (LEGACY_FIELDS & fields.keys() or LEGACY_FIELDS & dto["values"].keys())
    assert all(f["help"] and f["details"] and f["example"] for f in dto["fields"])
    assert fields["nap_start"]["level"] == 2
    assert fields["nap_start"]["parent"] == "nap_enabled"


async def test_energy_missing_port_is_unavailable_not_empty_history(le_store, le_context):
    await le_store.register_context(le_context)
    app = ConsoleDouble(le_store, le_context)
    original_history = getattr(le_store, "energy_history", None)
    le_store.energy_history = None
    try:
        with pytest.raises(ApplicationError) as raised:
            await app.console_energy(le_context.persona_id)
        assert raised.value.code == "unavailable" and raised.value.status_code == 503
    finally:
        if original_history is None:
            del le_store.energy_history
        else:
            le_store.energy_history = original_history


async def test_energy_real_port_without_events_has_uncollected_history(le_store, le_context):
    await le_store.register_context(le_context)
    assert callable(le_store.energy_history)
    dto = await ConsoleDouble(le_store, le_context).console_energy(le_context.persona_id)
    assert dto["collected"] is False and dto["total"] == 0
    assert dto["points"] == [] and dto["items"] == []


async def test_energy_real_store_history_global_pagination_and_category(le_store, le_context):
    first = le_context
    second = replace(first, scene_id="second")
    for context in (first, second):
        await le_store.register_context(context)
    def seed(db):
        for number in range(25):
            context = first if number % 2 else second
            at = (le_store.clock() - 100 + number if number < 23 else
                  le_store.clock() - 86401 if number == 23 else le_store.clock() + 1)
            db.execute("INSERT INTO energy_events VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?)", (
                f"energy-{number}", at, context.scope_key,
                context.scope_key, f"source-{number}", "reply" if number % 2 else "recovery",
                500, 501, 1, "awake", "awake", "real_event"))
    await le_store._run(seed)
    app = ConsoleDouble(le_store, first)
    dto = await app.console_energy(first.persona_id)
    assert dto["window_start"] == le_store.clock() - 86400
    assert dto["window_end"] == le_store.clock()
    assert dto["total"] == 23 and len(dto["items"]) == 10 and dto["collected"]
    assert [i["id"] for i in dto["items"]] == [f"energy-{n}" for n in range(22, 12, -1)]
    assert len({p["owner_key"] for p in dto["points"]}) == 2
    assert all(p["energy"] == 50.1 and p["min"] == 50 for p in dto["points"])
    assert all(i["delta"] == 0.1 and i["after_energy"] == 50.1 for i in dto["items"])
    assert all(dto["window_start"] <= p["at"] <= dto["window_end"] for p in dto["points"])
    third = await app.console_energy(first.persona_id, page=3)
    assert [i["id"] for i in third["items"]] == ["energy-2", "energy-1", "energy-0"]
    selected = await app.console_energy(first.persona_id, event_type="reply")
    assert selected["total"] == 11 and all(i["kind"] == "reply" for i in selected["items"])


async def test_energy_shared_owner_is_read_once_not_scope_duplicated(
        le_store, le_context, monkeypatch):
    other = replace(le_context, scene_id="other-real-scene", scene_kind="group")
    for context in (le_context, other):
        await le_store.register_context(context)
        await le_store.initialize_state_mode(context, shared=True)
    owner = le_store.state_owner(le_context)
    assert owner.owner_key == le_store.state_owner(other).owner_key
    original = le_store.energy_history
    calls = []
    async def tracked(context, **kwargs):
        calls.append((context, kwargs))
        return await original(context, **kwargs)
    monkeypatch.setattr(le_store, "energy_history", tracked)
    def seed(db):
        db.execute("INSERT INTO energy_events VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?)", (
            "shared-reply", le_store.clock() - 10, owner.owner_key, other.scope_key,
            "real-reply-source", "reply", 500, 499, -1, "awake", "awake", "reply_submitted"))
    await le_store._run(seed)
    dto = await ConsoleDouble(le_store, le_context).console_energy(
        le_context.persona_id, event_type="reply")
    assert dto["collected"] is True and dto["total"] == 1
    assert dto["series_total"] == 1 and len(calls) == 1
    assert calls[0][1]["since"] == dto["window_start"]
    assert calls[0][1]["until"] == dto["window_end"]
    assert dto["items"][0]["source_scope_key"] == other.scope_key
    assert dto["items"][0]["source_id"] == "real-reply-source"
    assert dto["points"][0]["min"] == 49.9 and dto["points"][0]["max"] == 50


async def test_settings_options_use_native_lists_and_never_secrets(le_store, le_context):
    app = ConsoleDouble(le_store, le_context)
    class ProviderOpenAIOfficial:
        provider_config = {"api_key": "NEVER_RETURN"}

        def meta(self):
            return SimpleNamespace(id="native-provider")

        def get_model(self):
            return "native-model"
    class DashScopeEmbeddingProvider(ProviderOpenAIOfficial):
        pass
    app.host = SimpleNamespace(
        persona_manager=SimpleNamespace(get_all_personas=lambda: [
            SimpleNamespace(persona_id="native-persona", prompt="NEVER_RETURN")]),
        get_all_providers=lambda: [ProviderOpenAIOfficial()],
        get_all_embedding_providers=lambda: [DashScopeEmbeddingProvider()],
    )
    result = await app.console_settings_options()
    assert result["personas"] == [{"value": "native-persona", "label": "native-persona"}]
    assert result["chat_providers"] == [
        {"value": "native-provider", "label": "native-provider / native-model"}]
    assert result["embedding_providers"] == result["chat_providers"]
    assert "NEVER_RETURN" not in str(result)
