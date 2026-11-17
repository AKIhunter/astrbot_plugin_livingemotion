"""新增睡眠配置贯通 schema、DTO、原生保存和运行时读回。"""
import json
from dataclasses import fields
from pathlib import Path

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.runtime.console import ApplicationError
from test_configuration_receipt import SaveConsole

DEFAULTS = {"energy_daytime_recovery_enabled": False,
            "recovery_follow_wake_at": True, "recovery_max_minutes": 120}


def test_schema_runtime_defaults_and_old_configs_agree():
    schema = json.loads((Path(__file__).parents[2] / "_conf_schema.json").read_text())
    old = Config.from_mapping({"timezone": "UTC", "energy_recovery_per_minute": 0.7})
    for name, default in DEFAULTS.items():
        assert schema[name]["default"] == getattr(Config(), name) == getattr(old, name) == default
    assert old.energy_recovery_per_minute == 0.7
    assert len({field.name for field in fields(Config)}) == len(fields(Config))


async def test_new_controls_are_flat_and_in_energy_subsection(le_store, le_context):
    app = SaveConsole(le_store, le_context)
    dto = app.config_dto()
    by_key = {field["key"]: field for field in dto["fields"]}
    for name in DEFAULTS:
        field = by_key[name]
        assert field["section"] == "night" and field["subsection"] == "energy"
        assert field["parent"] == "" and field["level"] == 0 and not field["advanced"]
        assert not field.get("readonly")
    assert (by_key["recovery_max_minutes"]["min"], by_key["recovery_max_minutes"]["max"],
            by_key["recovery_max_minutes"]["step"]) == (1, 1440, 1)


async def test_save_roundtrip_changes_only_requested_sleep_keys(le_store, le_context):
    app = SaveConsole(le_store, le_context)
    before = dict(app.native_config)
    patch = {"energy_daytime_recovery_enabled": True,
             "recovery_follow_wake_at": False, "recovery_max_minutes": 60}
    result = await app.update_config(patch, expected_revision=app.config_revision,
                                    reason="", actor_id="synthetic-admin", receipt="config")
    for name, value in patch.items():
        assert app.native_config.saved[name] == result["config"]["values"][name] == getattr(app.config, name) == value
    assert {k: v for k, v in app.native_config.saved.items() if k not in patch} == {
        k: v for k, v in before.items() if k not in patch}
    assert (await le_store.audit_records())[-1]["value"]["fields"] == sorted(patch)


@pytest.mark.parametrize("key,value", [
    ("energy_daytime_recovery_enabled", 1), ("energy_daytime_recovery_enabled", "false"),
    ("recovery_follow_wake_at", 0), ("recovery_follow_wake_at", "true"),
    ("recovery_max_minutes", 0), ("recovery_max_minutes", 1441),
    ("recovery_max_minutes", True), ("recovery_max_minutes", 1.5),
    ("recovery_max_minutes", "120"),
])
async def test_invalid_sleep_config_cannot_be_saved_or_applied(le_store, le_context, key, value):
    app = SaveConsole(le_store, le_context)
    before, config = dict(app.native_config), app.config
    with pytest.raises(ApplicationError) as error:
        await app.update_config({key: value}, expected_revision=app.config_revision,
                                reason="", actor_id="synthetic-admin", receipt="config")
    assert getattr(error.value, "code", "") == "validation_error"
    assert dict(app.native_config) == before and app.config == config
    assert app.replacements == 0 and await le_store.audit_records() == []


@pytest.mark.parametrize("minutes", [1, 120, 1440])
async def test_duration_bounds_survive_save_and_readback(le_store, le_context, minutes):
    app = SaveConsole(le_store, le_context)
    result = await app.update_config({"recovery_max_minutes": minutes},
                                    expected_revision=app.config_revision, reason="",
                                    actor_id="synthetic-admin", receipt="config")
    assert result["config"]["values"]["recovery_max_minutes"] == minutes
