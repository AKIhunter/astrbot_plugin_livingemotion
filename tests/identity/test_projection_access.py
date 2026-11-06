"""Synthetic grants must preserve scene and audience boundaries."""

from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.adapters.identity import IdentityAdapter
from astrbot_plugin_livingemotion.contracts import RelationshipContribution
from astrbot_plugin_livingemotion.domain.relationship import project_relationship
from astrbot_plugin_livingemotion.tests.memory.fakes import Event, Provider, context


@pytest.mark.parametrize("change", [
    {"instance_id": "other-instance"},
    {"bot_id": "other-bot"},
    {"persona_id": "other-persona"},
    {"scene_kind": "group", "scene_id": "alice", "audience": ("group:alice",),
     "route": "qq-instance:GroupMessage:alice"},
    {"scene_kind": "public_comment", "scene_id": "alice", "audience": ("public",),
     "route": None},
    {"scene_id": "other-private-thread"},
    {"audience": ("alice", "bot", "outsider")},
    {"audience": ()},
])
async def test_binding_never_authorizes_foreign_private_scope(change):
    private = context()
    target = replace(private, **change)
    provider = Provider()
    identities = IdentityAdapter(lambda: provider)
    event = Event(target)
    current = await identities.resolve(target, event=event)
    assert await identities.project_sources(current, (private,), event=event) == ()


@pytest.mark.parametrize("kind", ["group", "public_comment"])
async def test_binding_never_authorizes_another_room_or_thread(kind):
    target = context(scene_kind=kind, scene_id="room", route=None,
                     audience=("group:room",) if kind == "group" else ("public",))
    current = IdentityAdapter.local(target)
    source = replace(target, scene_id="another")
    assert current.project_sources((source,)) == ()
    row = RelationshipContribution("event", "alice", 100, 3, "interaction", "1970-01-01")
    assert project_relationship(
        [(source, row)], context=target, authorized_account_keys=[source.account_key],
        identity_revision=target.identity_revision,
    ).score == 0


async def test_bound_private_audiences_match_only_through_current_membership():
    target = context(audience=("qq:alice", "qq:bot"))
    linked = replace(target, platform="bili", account_id="linked", scene_id="linked",
                     audience=("bili:linked", "qq:bot"))
    provider = Provider()
    identities = IdentityAdapter(lambda: provider)
    event = Event(target)
    current = await identities.resolve(target, event=event)
    assert await identities.project_sources(current, (target, linked), event=event) == (
        target, linked)
    for audience in ((), ("bili:linked", "other-bot"),
                     ("bili:linked", "qq:bot", "outsider")):
        assert current.project_sources((replace(linked, audience=audience),)) == ()
    provider.bound = False
    provider.revision += 1
    assert await identities.project_sources(current, (target, linked), event=event) == ()
    refreshed = await identities.resolve(target, event=event)
    assert refreshed.project_sources((target, linked)) == (target,)


@pytest.mark.parametrize("change", [
    {"instance_id": "other-instance"},
    {"bot_id": "other-bot"},
    {"persona_id": "other-persona"},
    {"scene_kind": "group"},
    {"scene_kind": "public_comment", "route": None},
    {"scene_id": "other-private-thread"},
    {"audience": ("alice", "bot", "outsider")},
    {"audience": ()},
])
def test_domain_projection_rejects_foreign_scope_even_with_explicit_key(change):
    target = context()
    source = replace(target, **change)
    row = RelationshipContribution("event", "alice", 100, 3, "interaction", "1970-01-01")
    assert project_relationship(
        [(source, row)], context=target, authorized_account_keys=[source.account_key],
        identity_revision=target.identity_revision,
    ).score == 0


@pytest.mark.parametrize("revision", [None, "", " ", True, [], {}])
async def test_missing_or_invalid_provider_revision_never_authorizes_linked_source(revision):
    provider = Provider()
    event = Event()
    provider.return_identity = {
        **await provider.resolve_identity_context(event, "native"),
        "identity_revision": revision,
    }
    identities = IdentityAdapter(lambda: provider)
    current = await identities.resolve(context(), event=event)
    assert current.provider_token == 0
    assert current.project_sources((context(platform="bili", account_id="linked"),)) == ()
