"""Independent runtime and provenance expiry; synthetic sources only."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import ContentKind, EvidenceRef, Experience
from astrbot_plugin_livingemotion.services.output import public_text_allowed
from test_application import Message, application


async def test_optional_plugin_registry_cannot_disable_local_reply(tmp_path):
    app, host, native = await application(tmp_path)
    try:
        message = Message()
        await app.on_message(message)
        original = host.get_registered_star
        lookups = []

        def registry(name):
            lookups.append(name)
            return original(name)

        host.get_registered_star = registry
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        assert len(request.extra_user_content_parts) == 1
        assert (await app.api.get_capabilities())["mode"] == "active"
        assert all("memory" in name.lower() or "hello" in name.lower() or "at_guard" in name
                   for name in lookups)
        native["mode"] = "observe_only"
        await app.refresh_config()
        await app.on_llm_request(message, request)
        assert request.extra_user_content_parts == []
        native["enabled"] = False
        await app.refresh_config()
        assert (await app.api.get_capabilities())["mode"] == "disabled"
    finally:
        await app.terminate()


@pytest.mark.parametrize("pinned", [False, True])
@pytest.mark.parametrize("source_kind,expired", [
    (ContentKind.LEGACY_UNKNOWN, True),
    (ContentKind.INTERACTION, False),
])
async def test_unknown_provenance_keeps_seven_day_limit(
    le_store, le_context, pinned, source_kind, expired,
):
    now = le_store.clock()
    created = now - 604800
    ref = EvidenceRef("synthetic.snapshot", "source", le_context, "human", "bot",
                      source_kind, created, expires_at=now + 86400)
    entry = Experience("entry", le_context, ContentKind.DIARY, "synthetic-day",
                       created, "Synthetic reflection.", (ref,), now + 86400, pinned)
    assert (await le_store.save_experience(entry, 0))["status"] == "created"
    assert (await le_store.load_experience(entry.experience_id) is None) == expired
    assert (await le_store.query_records(le_context, "diary"))["total"] == int(not expired)
    updated = await le_store.pin_experience(
        entry, replace(entry, pinned=not pinned), 0, actor_id="synthetic-admin", reason="test",
    )
    assert updated["status"] == ("rejected" if expired else "updated")
    assert (await le_store.cleanup())["experiences"] == int(expired)


@pytest.mark.parametrize("text", [
    "<!--livingemotion:state:v1-->secret",
    "<!--other_plugin:private-->secret",
])
def test_public_output_rejects_internal_markers_without_plugin_dependency(text):
    assert not public_text_allowed(text)
    assert public_text_allowed("今天有点开心。")
