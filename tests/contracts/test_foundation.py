import ast
from dataclasses import fields, replace
import json
from pathlib import Path

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import (
    BotAffect, Event, HumanObservation, NightState, Relationship, canonical_json, to_dict,
)


def test_safe_config_and_schema_defaults_match():
    root = Path(__file__).parents[2]
    schema = json.loads((root / "_conf_schema.json").read_text())
    defaults = Config()
    assert {field.name for field in fields(defaults)} == set(schema)
    assert all(getattr(defaults, key) == value["default"] for key, value in schema.items())
    assert defaults.memory_mode == "none"
    assert defaults.mode == "active"
    for name in ("autonomy_enabled", "group_autonomy_enabled", "emotion_model_enabled",
                 "dream_enabled", "diary_enabled", "memory_read", "memory_export"):
        assert getattr(defaults, name) is False


@pytest.mark.parametrize("kwargs", [
    {"queue_size": 0}, {"enabled": "false"}, {"model_concurrency": True},
    {"window_days": 8}, {"window_per_scope": 201}, {"mode": "invalid"},
])
def test_config_rejects_unsafe_values(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_event_json_roundtrip_and_robust_keys(le_event):
    assert Event.from_dict(json.loads(canonical_json(le_event))) == le_event
    assert replace(le_event, event_id="different-producer-correlation").idempotency_key == (
        le_event.idempotency_key
    )
    for changed in (
        replace(le_event, producer="other"),
        replace(le_event, source_id="other"),
        replace(le_event, event_type="other"),
        replace(le_event, context=replace(le_event.context, bot_id="other")),
        replace(le_event, context=replace(le_event.context, adapter_id="other")),
        replace(le_event, context=replace(le_event.context, platform="other")),
        replace(le_event, context=replace(le_event.context, scene_kind="group")),
        replace(le_event, context=replace(le_event.context, instance_id="other-host")),
    ):
        assert changed.idempotency_key != le_event.idempotency_key


def test_identity_revision_does_not_migrate_storage(le_context):
    changed = replace(le_context, persona_revision="new", identity_revision="new")
    assert changed.scope_key == le_context.scope_key
    assert changed.account_key == le_context.account_key
    assert replace(le_context, account_id="another").scope_key == le_context.scope_key
    assert replace(le_context, account_id="another").account_key != le_context.account_key


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 2, True, "0.5"])
def test_affect_rejects_nonfinite_and_invalid_dimensions(value):
    with pytest.raises(ValueError):
        BotAffect(pleasure=value)


def test_role_types_are_separate():
    observation = HumanObservation("human", ("sad",), 0.8, 1, 2)
    assert observation.subject_id == "human"
    assert "energy" not in to_dict(BotAffect())
    assert NightState().energy == 100
    assert Relationship(score=500).normalized == 0.5
    assert Relationship().trust is None


def test_shared_kernel_has_only_stdlib_dependencies():
    import astrbot_plugin_livingemotion.contracts as contracts
    tree = ast.parse(Path(contracts.__file__).read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module.split(".")[0])
    assert set(imports) <= {"__future__", "dataclasses", "enum", "hashlib", "json", "math", "typing"}
