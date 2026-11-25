"""Local evidence adapters. SQL selects safe columns, never business bodies."""
import json
from pathlib import Path
from astrbot.api import logger

from ..diagnostic_bundle import DiagnosticRecorder, credentials_from, runtime_environment, sqlite_rows, local_plugin_version

SETTING_FIELDS = (
    "enabled", "mode", "timezone", "persona_shared_state", "provider_id",
    "fallback_provider_id", "behavior_provider_id", "embedding_provider_id",
    "model_timeout_seconds", "window_days", "event_days", "promise_enabled",
    "promise_tick_seconds", "promise_trace_ttl_hours", "emotion_model_enabled",
    "behavior_emotional_share", "model_daily_limit", "coupling_promise_actions",
    "allow_sleep", "catchup_provider_id",
)
SUMMARY_FIELDS = frozenset((
    "kind", "status", "reason_code", "reason_codes", "before", "after", "delta",
    "pleasure", "arousal", "stress", "social_need", "confidence", "generation",
    "event_key", "event_id", "request_id", "intent_id", "promise_id", "scope_key",
    "account_id", "at", "created_at", "updated_at", "due_at", "retry_count",
    "provider_id", "api_type", "ms", "receipt_id", "transport_receipt",
    "sent", "attempted", "simulated", "from", "to", "current", "active",
    "accepted", "source_id", "purpose", "depth", "advance_count",
    "energy", "energy_state", "owner_key", "occurred_at", "processed_at",
    "control", "rule_version", "baseline_pleasure", "baseline_arousal",
    "baseline_stress", "baseline_social_need", "baseline_refined",
    "context_emotions", "items", "intensity", "cause_code", "expires_at",
    "trust", "attachment", "closeness", "phase",
))


def summary(value):
    if isinstance(value, dict):
        return {key: summary(item) for key, item in value.items() if key in SUMMARY_FIELDS}
    if isinstance(value, (tuple, list)):
        return [summary(item) for item in value[:96]]
    return value


def start(app):
    def credentials():
        return credentials_from(app.host.get_config()) + credentials_from(app.native_config)
    recorder = DiagnosticRecorder(app.data_dir, "astrbot_plugin_livingemotion",
                                  Path(__file__).resolve().parents[1], credentials=credentials)
    recorder.install(logger)
    recorder.record("lifecycle", {"status": "loading"})
    return recorder


def prepare(app):
    path = app.data_dir / "livingemotion.sqlite3"
    settings = {key: getattr(app.config, key, None) for key in SETTING_FIELDS}
    environment = runtime_environment(app.host, local_plugin_version(Path(__file__).resolve().parents[1]), settings)
    environment.update(closed=app.closed, mode=app.effective_mode())
    try:
        environment["coupling"] = app._coupling_dto()
    except Exception:
        environment["coupling"] = {"status": "unavailable"}

    def rows(query, start, end):
        yield from sqlite_rows(path, query, (end, start))

    def events(start, end):
        yield from rows(
            "SELECT event_key,event_id,producer,event_type,actor_role,account_id,"
            "scope_key,generation,occurred_at,received_at,received_at updated_at FROM events "
            "WHERE occurred_at<? AND received_at>=? ORDER BY received_at DESC", start, end)

    def emotion(start, end):
        yield from rows(
            "SELECT owner_key,generation,at,pleasure,arousal,stress,social_need "
            "FROM emotion_samples WHERE at<? AND at>=? ORDER BY at DESC", start, end)
        for row in rows(
                "SELECT event_key,scope_key,generation,occurred_at,kind,value_json "
                "FROM event_traces WHERE occurred_at<? AND occurred_at>=? "
                "ORDER BY occurred_at DESC", start, end):
            try:
                payload = summary(json.loads(row.pop("value_json")))
                yield {**payload, **row}
            except (ValueError, TypeError):
                yield None
        yield from rows(
            "SELECT event_id,occurred_at,owner_key,source_scope_key,category,"
            "before_units,after_units,delta_units,before_state,after_state,reason_code "
            "FROM energy_events WHERE occurred_at<? AND occurred_at>=? "
            "ORDER BY occurred_at DESC", start, end)

    def behavior(start, end):
        for row in rows(
                "SELECT intent_id,scope_key,generation,status,created_at,updated_at,"
                "expires_at,attempted_at,reason_code,"
                "json_extract(value_json,'$.transport_receipt.receipt_id') receipt_id,"
                "json_extract(value_json,'$.purpose') purpose FROM intents "
                "WHERE created_at<? AND updated_at>=? ORDER BY updated_at DESC", start, end):
            yield {**row, "simulated": False}
        for row in rows(
                "SELECT value FROM runtime_meta "
                "WHERE key LIKE 'console.behavior.simulation.v1:%' "
                "AND json_extract(value,'$.created_at')<? "
                "AND json_extract(value,'$.created_at')>=?", start, end):
            try:
                yield {**summary(json.loads(row["value"])), "simulated": True}
            except (ValueError, TypeError):
                yield None
        yield from rows(
            "SELECT reply_id,source_scope_key,source_generation,started_at,"
            "COALESCE(submitted_at,started_at) updated_at,status FROM reply_attempts "
            "WHERE started_at<? AND COALESCE(submitted_at,started_at)>=? "
            "ORDER BY started_at DESC", start, end)

    def promises(start, end):
        yield from rows(
            "SELECT promise_id,scope_key,generation,status,due_at,original_due_at,"
            "advance_count,depth,created_at,updated_at,sent_at,retry_count,"
            "CASE WHEN last_error='' THEN 'none' ELSE 'error_present' END error_state "
            "FROM promises WHERE created_at<? AND updated_at>=? "
            "ORDER BY updated_at DESC", start, end)

    return app.diagnostics, {"environment": environment, "settings": settings}, {
        "events.jsonl": events, "emotion.jsonl": emotion,
        "behavior.jsonl": behavior, "promises.jsonl": promises,
    }
