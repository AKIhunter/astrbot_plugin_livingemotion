"""Strict, bounded transport validation; the application owns final transactions."""

import json
import math
import re
from dataclasses import fields

from ..config import Config
from .errors import ConsoleError

MAX_BODY_BYTES = 32 * 1024
SCOPE_FIELDS = frozenset({"persona_id", "view_scope", "context_id", "platform"})
KINDS = frozenset({"emotion", "behavior", "diary", "dream"})
ACTIONS = frozenset({
    "night.sleep", "night.wake", "diary.generate", "dream.generate", "behavior.send",
    "experience.pin",
})
QUERY_FIELDS = {
    "state": SCOPE_FIELDS,
    "records": SCOPE_FIELDS | {"kind", "page", "page_size", "query"},
    "scopes": SCOPE_FIELDS,
    "relationships": SCOPE_FIELDS | {"page", "page_size", "query", "limit"},
    "energy": SCOPE_FIELDS | {"page", "page_size", "event_type"},
    "settings-options": frozenset(),
}
BODY_FIELDS = {
    "config": frozenset({"context_id", "expected_revision", "patch", "reason"}),
    "preview": frozenset({"context_id"}),
    "action": frozenset({"context_id", "action", "expected_revision", "reason", "confirmed",
                         "entry_id", "pinned", "expected_pinned"}),
    "relationship": frozenset({"persona_id", "platform", "account_id", "context_id",
                               "score", "frozen", "expected_version", "reason"}),
}


def invalid() -> None:
    raise ConsoleError("validation_error")


def text(value, maximum: int, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        invalid()
    if required and not value.strip():
        invalid()
    return value


def revision(value) -> str | int:
    if type(value) is int and 0 <= value <= 2**63 - 1:
        return value
    return text(value, 256)


def positive_query_integer(value: str, maximum: int) -> int:
    if not re.fullmatch(r"[0-9]{1,7}", value):
        invalid()
    number = int(value)
    if not 1 <= number <= maximum:
        invalid()
    return number


def query_parameters(operation: str, query) -> dict:
    values = {}
    for key in query.keys():
        items = query.getlist(key)
        if key not in QUERY_FIELDS[operation] or len(items) != 1:
            invalid()
        values[key] = items[0]
    if operation == "settings-options":
        return {}
    use_selection = operation in ("scopes", "relationships", "energy") or bool(
        values.keys() & {"persona_id", "view_scope", "platform"})
    selection = {}
    if use_selection:
        selection = {
            "persona_id": text(values.get("persona_id", ""), 512, required=operation != "scopes"),
            "view_scope": values.get("view_scope", "global"),
            "platform": text(values.get("platform", ""), 512, required=False),
        }
        if selection["view_scope"] not in ("global", "private", "group"):
            invalid()
    context_id = text(values.get("context_id", ""), 512,
                      required=not use_selection and operation != "state")
    if operation == "scopes":
        return {"context_id": context_id, **selection}
    if operation == "state":
        return {"context_id": context_id, **selection}
    page = positive_query_integer(values.get("page", "1"), 1000000)
    page_size = positive_query_integer(values.get("page_size", "10"), 10)
    if page_size != 10:
        invalid()
    if operation == "relationships":
        return {"context_id": context_id, **selection, "page": page, "page_size": page_size,
                "query": text(values.get("query", ""), 200, required=False),
                "limit": positive_query_integer(values.get("limit", "200"), 200)}
    if operation == "energy":
        event_type = text(values.get("event_type", ""), 64, required=False)
        if event_type and event_type not in {
                "reply", "fatigue", "recovery", "sleep", "wake", "manual", "config"}:
            invalid()
        return {"context_id": context_id, **selection, "page": page,
                "page_size": page_size, "event_type": event_type}
    kind = values.get("kind")
    if kind not in KINDS:
        invalid()
    return {
        "context_id": context_id, **selection, "kind": kind, "page": page, "page_size": 10,
        "query": text(values.get("query", ""), 200, required=False),
    }


def unique_object(pairs: list[tuple]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            invalid()
        value[key] = item
    return value


def reject_constant(_value: str):
    invalid()


def validate_patch(patch) -> dict:
    if not isinstance(patch, dict) or not patch:
        invalid()
    known = {item.name: item for item in fields(Config)}
    if patch.keys() - known.keys():
        invalid()
    # Do not construct Config from a partial patch: defaults would incorrectly
    # reject cross-field changes valid against the user's current native config.
    for key, value in patch.items():
        default = known[key].default
        if (type(default) is float and type(value) not in (int, float)) or (
                type(default) is not float and type(value) is not type(default)):
            invalid()
        if isinstance(value, str):
            text(value, 8192, required=False)
        if type(default) is float:
            try:
                if not math.isfinite(value):
                    invalid()
            except OverflowError:
                invalid()
    return patch


async def body_parameters(operation: str, request) -> dict:
    if request.query:
        invalid()
    media_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        invalid()
    lengths = request.headers.getlist("Content-Length")
    if len(lengths) > 1:
        invalid()
    if lengths:
        if not re.fullmatch(r"[0-9]{1,8}", lengths[0]) or int(lengths[0]) > MAX_BODY_BYTES:
            invalid()
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        invalid()
    try:
        values = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        invalid()
    if not isinstance(values, dict) or values.keys() - BODY_FIELDS[operation]:
        invalid()
    context_id = text(values.get("context_id", ""), 512,
                      required=operation not in ("config", "relationship"))
    if operation == "preview":
        return {"context_id": context_id}
    if operation == "relationship":
        from decimal import Decimal
        expected_version = values.get("expected_version")
        if type(expected_version) is not int or not 0 <= expected_version <= 2**63 - 1:
            invalid()
        score, frozen = values.get("score"), values.get("frozen")
        if not ({"score", "frozen"} & values.keys()):
            invalid()
        if "score" in values:
            if type(score) not in (int, float) or not 0 <= score <= 100 or not math.isfinite(score):
                invalid()
            scaled = Decimal(str(score)) * 10
            if scaled != scaled.to_integral_value():
                invalid()
        if "frozen" in values and type(frozen) is not bool:
            invalid()
        return {"context_id": context_id, "persona_id": text(values.get("persona_id"), 512),
                "platform": text(values.get("platform"), 512),
                "account_id": text(values.get("account_id"), 512),
                "score": score, "frozen": frozen, "expected_version": expected_version,
                "reason": text(values.get("reason"), 1000).strip()}
    expected_revision = revision(values.get("expected_revision"))
    reason = text(values.get("reason"), 1000).strip()
    if operation == "config":
        return {
            "context_id": context_id, "expected_revision": expected_revision,
            "reason": reason, "patch": validate_patch(values.get("patch")),
        }
    action = values.get("action")
    if not isinstance(action, str) or action not in ACTIONS or values.get("confirmed") is not True:
        invalid()
    result = {
        "context_id": context_id, "action": action, "expected_revision": expected_revision,
        "reason": reason, "confirmed": True,
    }
    if action == "experience.pin":
        pinned, expected = values.get("pinned"), values.get("expected_pinned")
        if type(pinned) is not bool or type(expected) is not bool or pinned == expected:
            invalid()
        result.update(entry_id=text(values.get("entry_id"), 512),
                      pinned=pinned, expected_pinned=expected)
    elif values.keys() & {"entry_id", "pinned", "expected_pinned"}:
        invalid()
    return result
