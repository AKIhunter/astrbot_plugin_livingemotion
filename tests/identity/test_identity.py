from types import SimpleNamespace

import pytest
from astrbot_plugin_livingemotion.adapters.identity import (
    IdentityAdapter,
    context_from_event,
    same_value_alias,
)
from astrbot_plugin_livingemotion.tests.memory.fakes import Event, Provider, context


@pytest.mark.parametrize(
    "value",
    [
        {"one_id": "human"},
        {"person_id": "human"},
        {"one_id": "human", "person_id": "human"},
    ],
)
def test_oneid_same_value_compatibility(value):
    assert same_value_alias(value) == "human"


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"one_id": "a", "person_id": "b"},
        {"one_id": 42},
        {"one_id": " "},
    ],
)
def test_identity_alias_rejects_ambiguous_values(value):
    with pytest.raises(ValueError):
        same_value_alias(value)


async def test_unbound_accounts_never_merge_by_persona_platform_or_bot():
    adapter = IdentityAdapter()
    variants = (
        context(),
        context(account_id="bob"),
        context(platform="bili"),
        context(adapter_id="other"),
        context(bot_id="other"),
    )
    identities = [await adapter.resolve(item, event=Event(item)) for item in variants]
    assert len({item.one_id for item in identities}) == len(variants)
    assert all(item.person_id == item.one_id and len(item.accounts) == 1 for item in identities)
    assert await adapter.validate(identities[0], event=Event())


async def test_projection_preserves_original_sources_and_unlink_invalidates_snapshot():
    provider = Provider()
    adapter = IdentityAdapter(lambda: provider)
    event = Event()
    snapshot = await adapter.resolve(context(), event=event)
    assert snapshot.one_id == snapshot.person_id == "human"
    sources = [
        context(),
        context(platform="bili", account_id="linked"),
        context(account_id="mallory"),
        context(bot_id="another"),
    ]
    projected = snapshot.project_sources(sources)
    assert projected == tuple(sources[:2])
    assert projected[0] is sources[0] and projected[1] is sources[1]
    provider.bound = False
    provider.revision += 1
    assert not await adapter.validate(snapshot, event=event)
    current = await adapter.resolve(context(), event=event)
    assert current.project_sources(sources) == (sources[0],)
    assert sources[1].account_id == "linked"


@pytest.mark.parametrize(
    "change",
    [
        {"one_id": "bad", "person_id": "other"},
        {"identity_revision": None},
        {"platform": "bili"},
        {"account_id": "mallory"},
        {"scene_id": "elsewhere"},
        {"scene_kind": "group"},
        {"persona_id": "other"},
        {"origin_session_id": "forged"},
        {"source_account": "qq:bob"},
        {"audience": ""},
    ],
)
async def test_provider_malformed_or_mismatched_identity_falls_back_without_merge(change):
    provider = Provider()
    provider.return_identity = {
        **await provider.resolve_identity_context(Event(), "native"),
        **change,
    }
    snapshot = await IdentityAdapter(lambda: provider).resolve(context(), event=Event())
    assert snapshot.context.identity_revision.startswith("local:")
    assert snapshot.accounts == (("qq", "alice"),)
    assert snapshot.reason_codes


async def test_background_never_constructs_a_fake_event_and_service_loss_invalidates():
    provider = Provider()
    adapter = IdentityAdapter(lambda: provider)
    snapshot = await adapter.resolve(context(), event=Event())
    assert not await adapter.validate(snapshot)
    for event in (None, Event(synthetic=True), Event(context(route="cron:FriendMessage:alice"))):
        fallback = await adapter.resolve(context(), event=event)
        assert fallback.context.identity_revision.startswith("local:")
    adapter.provider = lambda: None
    assert not await adapter.validate(snapshot, event=Event())


def native_event(bot="bot", adapter="qq-instance", group=""):
    event = Event(context(route=f"{adapter}:{'GroupMessage' if group else 'FriendMessage'}:alice"))
    event.platform_meta = SimpleNamespace(id=adapter, name="aiocqhttp")
    event.get_self_id = lambda: bot
    event.get_group_id = lambda: group
    return event


def native_context(event, **changes):
    return context_from_event(
        event,
        **{
            "host_instance_id": "host-1",
            "platform": "qq",
            "persona_id": "native",
            "persona_revision": "r1",
            "audience": ("alice", "bot"),
            **changes,
        },
    )


def test_native_source_preserves_route_and_separates_host_bot_adapter():
    event = native_event()
    first = native_context(event)
    assert first.route == event.unified_msg_origin
    assert first.adapter_id == "qq-instance" and first.platform == "qq"
    assert first.account_id == "alice" and first.scene_id == "alice"
    scopes = {
        first.scope_key,
        native_context(native_event(bot="other")).scope_key,
        native_context(native_event(adapter="other")).scope_key,
        native_context(event, host_instance_id="other").scope_key,
        native_context(native_event(group="same-number")).scope_key,
    }
    assert len(scopes) == 5


@pytest.mark.parametrize("kind", ["self_missing", "adapter_missing", "route_mismatch", "synthetic"])
def test_native_source_never_guesses_missing_bot_or_route(kind):
    event = native_event(bot="" if kind == "self_missing" else "bot")
    if kind == "adapter_missing":
        event.platform_meta.id = ""
    if kind == "route_mismatch":
        event.unified_msg_origin = "other:FriendMessage:alice"
    event.synthetic = kind == "synthetic"
    with pytest.raises(ValueError):
        native_context(event)


async def test_no_identity_service_does_not_project_other_adapter_same_account():
    snapshot = await IdentityAdapter().resolve(context(), event=Event())
    assert snapshot.project_sources((context(adapter_id="other"),)) == ()


async def test_live_projection_rejects_old_snapshot_immediately_after_revision_change():
    provider = Provider()
    adapter = IdentityAdapter(lambda: provider)
    event = Event()
    snapshot = await adapter.resolve(context(), event=event)
    sources = (context(), context(platform="bili", account_id="linked"))
    assert await adapter.project_sources(snapshot, sources, event=event) == sources
    provider.revision += 1
    assert await adapter.project_sources(snapshot, sources, event=event) == ()
