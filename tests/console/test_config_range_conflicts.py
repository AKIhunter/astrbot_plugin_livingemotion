"""Legal boundaries must survive save/readback without unrelated changes."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.page_api.validation import validate_patch
from astrbot_plugin_livingemotion.runtime.console import ApplicationError
from astrbot_plugin_livingemotion.runtime.promise_service import PromiseService
from astrbot_plugin_livingemotion.runtime.weather_factor import WeatherFactor
from test_configuration_receipt import SaveConsole


@pytest.mark.parametrize("key,value", [
    ("weather_transition_seconds", 0), ("weather_transition_seconds", 1),
    ("weather_transition_seconds", 7200), ("promise_trace_ttl_hours", 1),
    ("promise_trace_ttl_hours", 100.1), ("promise_trace_ttl_hours", 168),
])
async def test_legal_boundaries_save_readback(le_store, le_context, key, value):
    app = SaveConsole(le_store, le_context)
    before = dict(app.native_config)
    result = await app.update_config(validate_patch({key: value}),
        expected_revision=app.config_revision, reason="", actor_id="synthetic-admin", receipt="config")
    assert app.native_config.saved[key] == getattr(app.config, key) == result["config"]["values"][key] == value
    assert {k: v for k, v in app.native_config.saved.items() if k != key} == {
        k: v for k, v in before.items() if k != key}
    assert Config.from_mapping(app.native_config.saved) == app.config


@pytest.mark.parametrize("key,value", [
    ("weather_transition_seconds", -1), ("weather_transition_seconds", 7201),
    ("weather_transition_seconds", True), ("weather_transition_seconds", "0"),
    ("promise_trace_ttl_hours", 0.9), ("promise_trace_ttl_hours", 168.1),
    ("promise_trace_ttl_hours", 100.11), ("promise_trace_ttl_hours", True),
    ("promise_trace_ttl_hours", float("nan")), ("promise_trace_ttl_hours", float("inf")),
])
async def test_invalid_boundaries_do_not_save(le_store, le_context, key, value):
    app = SaveConsole(le_store, le_context)
    before, config = dict(app.native_config), app.config
    with pytest.raises(ApplicationError) as caught:
        await app.update_config({key: value}, expected_revision=app.config_revision,
                                reason="", actor_id="synthetic-admin", receipt="config")
    assert caught.value.code == "validation_error"
    assert dict(app.native_config) == before and app.config == config
    assert app.replacements == 0 and await le_store.audit_records() == []


async def test_schema_matches_console(le_store, le_context):
    schema = json.loads((Path(__file__).parents[2] / "_conf_schema.json").read_text())
    controls = {f["key"]: f for f in SaveConsole(le_store, le_context).config_dto()["fields"]}
    for key, bounds in {"weather_transition_seconds": (0, 7200, 1),
                        "promise_trace_ttl_hours": (1, 168, 0.1)}.items():
        assert tuple(schema[key]["slider"][k] for k in ("min", "max", "step")) == bounds
        assert tuple(controls[key][k] for k in ("min", "max", "step")) == bounds
        assert schema[key]["default"] == getattr(Config(), key)
    assert controls["promise_trace_ttl_hours"]["unit"] == "小时"


def test_runtime_ttl_includes_full_week():
    service = object.__new__(PromiseService)
    for hours in (1, 100.1, 168):
        service.app = SimpleNamespace(config=replace(Config(), promise_trace_ttl_hours=hours))
        assert service._trace_ttl() == hours * 3600


def test_zero_weather_transition_is_immediate():
    config = Config(weather_transition_seconds=0)
    factor = WeatherFactor(config=lambda: config, weather=None, clock=lambda: 1000)
    factor._previous, factor._target, factor._changed_at = (0.0,) * 4, (0.5,) * 4, 999
    assert factor._interpolate(1000, config) == factor._target


def test_unrelated_bounds_remain():
    with pytest.raises(ValueError):
        Config(energy_reply_cost=100.1)
    with pytest.raises(ValueError):
        Config(scheduler_seconds=0)
