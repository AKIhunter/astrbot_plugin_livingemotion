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
    "configuration": SCOPE_FIELDS,
    "records": SCOPE_FIELDS | {"kind", "page", "page_size", "query"},
    "scopes": SCOPE_FIELDS,
    "relationships": SCOPE_FIELDS | {"page", "page_size", "query", "limit", "graph_scope"},
    "energy": SCOPE_FIELDS | {"page", "page_size", "event_type"},
    "settings-options": frozenset(),
    "persona-description": frozenset({"persona_id"}),
    "style-summary": frozenset({"persona_id"}),
    "emotion-images": frozenset(),
    "emotion-image": frozenset({"mood", "index"}),
    "experience-task": frozenset({"request_id"}),
}
BODY_FIELDS = {
    "config": frozenset({"context_id", "expected_revision", "patch", "reason", "receipt"}),
    "preview": frozenset({"context_id"}),
    "action": frozenset({"context_id", "action", "expected_revision", "reason", "confirmed",
                         "entry_id", "pinned", "expected_pinned"}),
    "relationship": frozenset({"persona_id", "platform", "account_id", "context_id",
                               "score", "frozen", "note", "expected_version", "reason"}),
    "memory-sync": frozenset({"context_id"}),
    "behavior-simulate": frozenset({"context_id", "persona_id", "emotion", "request_id"}),
    "emotion-image-save": frozenset({"mood", "data_url", "index", "remove"}),
    "experience-generate": frozenset({"request_id", "persona_id", "kind"}),
    "style-summary-save": frozenset({"persona_id", "text", "reason"}),
}
# 上传走 JSON 的 base64 而不是 multipart：宿主的页面桥只转发 JSON，
# 图片本体在 storage 层再做类型与 512 KB 上限校验。
MAX_IMAGE_BYTES = 700 * 1024
MOODS = frozenset({
    "calm", "neutral", "happy", "joyful", "sad", "anxious", "angry", "tired", "excited",
    "caring", "lonely", "content", "strained", "tense", "concerned", "subdued", "alert",
    "seeking_company",
})


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
    if operation in ("persona-description", "style-summary"):
        return {"persona_id": text(values.get("persona_id"), 512)}
    if operation == "experience-task":
        return {"request_id": request_identity(values.get("request_id"))}
    if operation == "emotion-images":
        return {}
    if operation == "emotion-image":
        mood = values.get("mood")
        if mood not in MOODS:
            invalid()
        index = values.get("index", "")
        if index and (not index.isdigit() or not 2 <= int(index) <= 6):
            invalid()
        return {"mood": mood, "index": int(index) if index else None}
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
                      required=not use_selection and operation not in ("state", "configuration"))
    if operation == "scopes":
        return {"context_id": context_id, **selection}
    if operation in ("state", "configuration"):
        return {"context_id": context_id, **selection}
    page = positive_query_integer(values.get("page", "1"), 1000000)
    page_size = positive_query_integer(values.get("page_size", "10"), 10)
    if page_size != 10:
        invalid()
    if operation == "relationships":
        graph_scope = values.get("graph_scope", "matched")
        if graph_scope not in ("matched", "neighbors"):
            invalid()
        return {"context_id": context_id, **selection, "page": page, "page_size": page_size,
                "query": text(values.get("query", ""), 200, required=False),
                "graph_scope": graph_scope,
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


def request_identity(value):
    value = text(value, 64)
    if not re.fullmatch(r"[a-zA-Z0-9_-]{16,64}", value):
        if not re.fullmatch(r"[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}", value):
            invalid()
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
    # 图片走 base64 JSON，单次上限单独放宽；其余接口仍然只有 32 KB。
    limit = MAX_IMAGE_BYTES + 32 * 1024 if operation == "emotion-image-save" else MAX_BODY_BYTES
    lengths = request.headers.getlist("Content-Length")
    if len(lengths) > 1:
        invalid()
    if lengths:
        if not re.fullmatch(r"[0-9]{1,8}", lengths[0]) or int(lengths[0]) > limit:
            invalid()
    raw = await request.body()
    if len(raw) > limit:
        invalid()
    try:
        values = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        invalid()
    if not isinstance(values, dict) or values.keys() - BODY_FIELDS[operation]:
        invalid()
    if operation == "style-summary-save":
        body = values.get("text")
        if not isinstance(body, str) or len(body) > 2000 or "\x00" in body:
            invalid()
        return {"persona_id": text(values.get("persona_id"), 512), "text": body,
                "reason": text(values.get("reason") or "控制台编辑风格摘要", 1000).strip()}
    if operation == "experience-generate":
        if values.get("kind") not in ("diary", "dream"):
            invalid()
        return {"request_id": request_identity(values.get("request_id")),
                "persona_id": text(values.get("persona_id"), 512), "kind": values["kind"]}
    if operation == "behavior-simulate":
        emotion = values.get("emotion", "current")
        if emotion not in ("current", "calm", "joy", "sadness", "anger", "fear", "surprise", "disgust"):
            invalid()
        return {"context_id": text(values.get("context_id", ""), 512, required=False),
                "persona_id": text(values.get("persona_id", ""), 512, required=False),
                "emotion": emotion, "request_id": request_identity(values["request_id"])
                if "request_id" in values else ""}
    if operation == "emotion-image-save":
        mood = values.get("mood")
        if mood not in MOODS:
            invalid()
        index = values.get("index")
        if index is not None and (type(index) is not int or not 1 <= index <= 6):
            invalid()
        remove = values.get("remove", False)
        if type(remove) is not bool:
            invalid()
        if remove:
            return {"mood": mood, "index": index, "remove": True}
        data_url = values.get("data_url")
        if not isinstance(data_url, str) or len(data_url) > MAX_IMAGE_BYTES * 2:
            invalid()
        return {"mood": mood, "index": index, "data_url": data_url}
    context_id = text(values.get("context_id", ""), 512,
                      required=operation not in ("config", "relationship", "memory-sync"))
    if operation == "memory-sync":
        return {"context_id": context_id}
    if operation == "preview":
        return {"context_id": context_id}
    if operation == "relationship":
        from decimal import Decimal
        expected_version = values.get("expected_version")
        if type(expected_version) is not int or not 0 <= expected_version <= 2**63 - 1:
            invalid()
        score, frozen = values.get("score"), values.get("frozen")
        note = values.get("note")
        if score is None and frozen is None and note is None:
            invalid()
        if note is not None and (not isinstance(note, str) or len(note) > 1000
                or any((ord(c) < 32 and c not in "\n\r\t") or 127 <= ord(c) < 160 for c in note)):
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
                "score": score, "frozen": frozen, "note": note, "expected_version": expected_version,
                "reason": text(values.get("reason") or "控制台编辑关系", 1000).strip()}
    expected_revision = revision(values.get("expected_revision"))
    # 保存配置不要求填写原因：留空（含 null）由应用层补一条固定审计说明；
    # 其他写操作仍然必须有原因。
    raw_reason = values.get("reason", "")
    if operation == "config" and raw_reason is None:
        raw_reason = ""
    reason = text(raw_reason or "控制台操作", 1000).strip()
    if operation == "config":
        receipt = values.get("receipt", "state")
        if receipt not in ("state", "config"):
            invalid()
        return {
            "context_id": context_id, "expected_revision": expected_revision,
            "reason": reason, "patch": validate_patch(values.get("patch")),
            **({"receipt": receipt} if "receipt" in values else {}),
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
