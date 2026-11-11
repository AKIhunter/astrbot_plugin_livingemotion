"""Current native persona choices must not resurrect historical identities."""
from dataclasses import replace
from types import SimpleNamespace

from astrbot_plugin_livingemotion.runtime.console import Console
from astrbot_plugin_livingemotion.storage.console_data import query_scopes


class CatalogConsole(Console):
    def __init__(self, store, context, personas):
        self.store, self.instance_id = store, context.instance_id
        self.closed = False
        self.personas = personas

    async def console_settings_options(self):
        return {"personas": [{"value": value, "label": value} for value in self.personas]}


async def test_deleted_persona_is_not_selectable_but_history_is_preserved(le_store, le_context):
    deleted = replace(le_context, persona_id="deleted-persona")
    await le_store.register_context(deleted)
    app = CatalogConsole(le_store, le_context, ["current-persona"])
    result = await app.console_scopes()
    assert result["personas"] == [{"id": "current-persona", "name": "current-persona"}]
    historical = await query_scopes(le_store, le_context.instance_id, {})
    assert historical["personas"] == [{"id": "deleted-persona", "name": "deleted-persona"}]
    assert result["contexts"] == historical["contexts"]


async def test_catalog_reads_native_deletions_and_additions_on_every_request(le_store, le_context):
    await le_store.register_context(le_context)
    app = CatalogConsole(le_store, le_context, ["old", "kept", "kept"])
    assert [item["id"] for item in (await app.console_scopes())["personas"]] == ["old", "kept"]
    app.personas[:] = ["kept", "new"]
    assert [item["id"] for item in (await app.console_scopes())["personas"]] == ["kept", "new"]
    app.personas.clear()
    assert (await app.console_scopes())["personas"] == []


async def test_native_listing_failure_does_not_restore_history(le_store, le_context):
    await le_store.register_context(le_context)
    app = CatalogConsole(le_store, le_context, [])
    app.console_settings_options = Console.console_settings_options.__get__(app)
    app._settings_groups = lambda: []

    def unavailable():
        raise RuntimeError("native listing unavailable")

    app.host = SimpleNamespace(persona_manager=SimpleNamespace(get_all_personas=unavailable))
    assert (await app.console_scopes())["personas"] == []


class DescriptionConsole(Console):
    def __init__(self, getter):
        self.closed = False
        self.host = SimpleNamespace(persona_manager=SimpleNamespace(get_persona=getter))


async def test_persona_description_reads_native_system_prompt():
    prompts = {"big-miss": "大小姐人格说明" * 10}

    async def get_persona(identifier):
        if identifier not in prompts:
            raise ValueError("Persona does not exist.")
        return SimpleNamespace(system_prompt=prompts[identifier])

    result = await DescriptionConsole(get_persona).console_persona_description("big-miss")
    assert result == {"api_version": 1, "persona_id": "big-miss",
                      "description": prompts["big-miss"],
                      "characters": len(prompts["big-miss"]), "available": True}


async def test_missing_persona_is_reported_unavailable_without_raising():
    async def get_persona(_identifier):
        raise ValueError("Persona with ID gone does not exist.")

    result = await DescriptionConsole(get_persona).console_persona_description("gone")
    assert result["available"] is False and result["description"] == ""
    assert result["characters"] == 0 and result["persona_id"] == "gone"


async def test_oversized_persona_prompt_is_not_truncated():
    async def get_persona(_identifier):
        return SimpleNamespace(system_prompt="x" * 16001)

    async def at_limit(_identifier):
        return SimpleNamespace(system_prompt="x" * 16000)

    oversized = await DescriptionConsole(get_persona).console_persona_description("large")
    assert oversized["available"] is False and oversized["description"] == ""
    assert (await DescriptionConsole(at_limit).console_persona_description("edge"))["available"] is True


async def test_persona_manager_without_reader_degrades_to_unavailable():
    result = await DescriptionConsole(None).console_persona_description("any")
    assert result["available"] is False and result["description"] == ""
