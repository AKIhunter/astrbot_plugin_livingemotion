"""Strict, bounded transport validation; the application owns final transactions."""

import json
import math
import re
from dataclasses import fields

from ..config import Config
from .errors import ConsoleError

MAX_BODY_BYTES = 32 * 1024
KINDS = frozenset({"emotion", "behavior", "diary", "dream"})
ACTIONS = frozenset({
    "night.sleep", "night.wake", "diary.generate", "dream.generate", "behavior.send",
})
QUERY_FIELDS = {
    "state": frozenset({"context_id"}),
    "records": frozenset({"context_id", "kind", "page", "page_size", "query"}),
}
BODY_FIELDS = {
    "config": frozenset({"context_id", "expected_revision", "patch", "reason"}),
    "preview": frozenset({"context_id"}),
    "action": frozenset({"context_id", "action", "expected_revision", "reason", "confirmed"}),
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
    context_id = text(values.get("context_id", ""), 512, required=operation != "state")
    if operation == "state":
        return {"context_id": context_id}
    kind = values.get("kind")
    if kind not in KINDS:
        invalid()
    page = positive_query_integer(values.get("page", "1"), 1000000)
    page_size = positive_query_integer(values.get("page_size", "10"), 10)
    if page_size != 10:
        invalid()
    return {
        "context_id": context_id, "kind": kind, "page": page, "page_size": 10,
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
        if type(value) is not type(default):
            invalid()
        if isinstance(value, str):
            text(value, 8192, required=False)
        if type(value) is float and not math.isfinite(value):
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
    context_id = text(values.get("context_id", ""), 512, required=operation != "config")
    if operation == "preview":
        return {"context_id": context_id}
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
    return {
        "context_id": context_id, "action": action, "expected_revision": expected_revision,
        "reason": reason, "confirmed": True,
    }
