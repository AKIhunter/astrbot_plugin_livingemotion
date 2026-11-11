import ast
from collections import UserDict
from dataclasses import fields, replace
import json
from pathlib import Path

import pytest

from astrbot_plugin_livingemotion.config import Config, LEGACY_FIELDS, qq_numbers
from astrbot_plugin_livingemotion.contracts import (
    ActorRole, BotAffect, Event, HumanObservation, NightState, Relationship, canonical_json, to_dict,
)


def test_safe_config_and_schema_defaults_match():
    root = Path(__file__).parents[2]
    schema = json.loads((root / "_conf_schema.json").read_text())
    defaults = Config()
    assert {field.name for field in fields(defaults)} - LEGACY_FIELDS == set(schema)
    assert all(getattr(defaults, key) == value["default"] for key, value in schema.items())
    current_native = Config.from_mapping({key: value["default"] for key, value in schema.items()})
    assert current_native.night_policy_version == 2
    assert Config.from_mapping({}).night_policy_version == 1
    assert defaults.memory_mode == "none"
    assert defaults.mode == "active"
    for name in ("autonomy_enabled", "group_autonomy_enabled", "emotion_model_enabled",
                 "dream_enabled", "diary_enabled", "memory_read", "memory_export"):
        assert getattr(defaults, name) is False


def test_qq_lists_accept_separators_and_deduplicate_without_guessing():
    assert qq_numbers("12345678，23456789\n12345678；34567890") == (
        "12345678", "23456789", "34567890")
    assert qq_numbers("") == ()
    for value in ("@12345678", "群12345678", "01234567", "1234", "12345678 bad",
                  "1" * 21, ",".join(str(10000 + i) for i in range(101))):
        with pytest.raises(ValueError):
            Config(autonomy_qq_ids=value)


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


def test_nested_contract_wire_format_preserves_enums_and_custom_mappings():
    class Text(str):
        pass

    value = {
        "role": ActorRole.HUMAN,
        "nested": UserDict({7: (None, True, 0.1, Text("中文"))}),
    }
    assert canonical_json(value) == (
        '{"nested":{"7":[null,true,0.1,"\\u4e2d\\u6587"]},"role":"human"}'
    )
    assert to_dict(value)["nested"]["7"] == [None, True, 0.1, "中文"]
    assert isinstance(to_dict(value)["nested"]["7"][-1], Text)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nested_plain_number_still_rejected_by_canonical_encoder(value):
    with pytest.raises(ValueError):
        canonical_json({"runtime": [({"amount": value},)]})


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
