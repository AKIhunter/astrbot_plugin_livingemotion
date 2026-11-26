"""Local evidence adapters. SQL selects safe columns, never business bodies."""
from datetime import date
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
    "night_policy_version", "fatigue_start", "deep_sleep_at", "wake_at",
    "nap_enabled", "nap_start", "lie_in_max_minutes",
    "closing_enabled", "closing_random", "closing_lead_minutes", "closing_provider_id",
    "energy_reply_cost", "behavior_daily_limit",
    "catchup_enabled", "catchup_reply_enabled", "wake_autocatchup_enabled", "wake_greeting_enabled",
    "dream_enabled", "dream_provider_id", "dream_per_night", "dream_owner_notify",
    "diary_enabled", "diary_at", "diary_backfill_yesterday", "diary_provider_id",
    "autonomy_enabled", "group_autonomy_enabled", "proactive_native_yield",
    "scheduler_seconds", "model_input_tokens", "model_output_tokens",
    "emotion_provider_id", "context_emotions_enabled",
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

# 只记录调用点主动提供的字段；不从宿主日志收集任意参数。
_RUNTIME_FIELDS = {
    "dream_skip": ("scope_key", "reason_code"),
    "closing_merge_failed": ("intent_id", "stage", "status", "exception_type",
                             "reason_code", "closing_random"),
    "scheduler_tick_failed": ("at", "stage", "exception_type", "site", "first_at", "count"),
}
QUEUE_FAILURE_CODES = frozenset((
    "runtime_stopped", "observe_only", "duplicate_job", "model_disabled", "token_limit",
    "missing_token_budget", "invalid_timeout", "queue_full",
))
QUOTA_FAILURE_CODES = frozenset((
    "quota_exhausted", "quota_cooldown", "reservation_exists", "stale_generation",
))
# 梦境门禁、准备阶段和自动生成只公开已有的固定原因码。
DREAM_SKIP_CODES = QUEUE_FAILURE_CODES | frozenset((
    "context_changed", "daily_content_preserved", "dream_requires_live_rem", "dream_success_limit",
    "experience_attempt_limit", "experience_exists", "experience_preparation_unavailable",
    "experience_service_limit", "generation_disabled", "generation_in_progress",
    "input_budget_too_small", "input_token_limit", "model_or_tokenizer_unavailable",
    "model_preflight_http_error", "model_preflight_timeout", "model_preflight_unavailable",
    "model_result_unknown", "model_unavailable", "multi_scope_commit_unsupported",
    "night_guard_error", "night_guard_rejected", "night_guard_unavailable",
    "night_revalidation_unavailable", "night_state_stale", "night_state_unavailable",
    "no_qualified_material", "not_asleep", "offline_recovery", "persona_text_invalid",
    "persona_unavailable", "provider_budget_contract_unavailable",
    "provider_budget_contract_unsupported", "provider_changed", "sleep_too_short",
    "sleep_window_ended", "sleep_window_missing", "source_unavailable",
))
_JOB_STATUSES = frozenset(("queued", "running", "succeeded", "failed", "cancelled", "unknown"))
_AUTO_STATUSES = _JOB_STATUSES | frozenset((
    "created", "duplicate", "rejected", "skipped", "unavailable", "unsupported",
))
_ATTEMPT_STATUSES = frozenset(("reserved", "succeeded", "failed", "cancelled", "unknown"))
_JOB_CODES = frozenset((
    "queued", "generating", "queue_full", "reload_before_dispatch", "reload_after_dispatch",
    "private_archive_updated", "input_token_limit", "persona_or_model_changed",
    "entry_changed", "job_changed", "stale_generation", "generation_failed",
    "model_body_invalid", "model_sources_invalid", "model_body_unsafe", "model_error_envelope",
    "model_preflight_http_error", "model_preflight_timeout", "model_preflight_unavailable",
    "model_output_invalid", "model_response_invalid", "provider_result_unknown",
    "model_timeout", "model_result_unknown",
))
_AUTO_CODES = DREAM_SKIP_CODES | QUOTA_FAILURE_CODES | frozenset((
    "queued", "runtime_restarted", "diary_not_due", "diary_backfill_out_of_range",
    "context_or_evidence_changed", "evidence_changed", "experience_saved", "generation_failed",
    "generation_cancelled", "model_timeout", "model_output_invalid", "model_response_invalid",
    "provider_result_unknown",
))
_MODEL_RESULT_CODES = frozenset((
    "model_response_too_large", "model_body_missing", "model_error_envelope",
    "duplicate_key", "invalid_number", "model_object_required", "model_body_invalid",
    "model_body_unsafe", "model_sources_invalid", "model_json_invalid",
))


def known_code(value, allowed):
    return value if type(value) is str and value in allowed else "unknown"


def _iso_day(value):
    if type(value) is str and len(value) == 10:
        try:
            if date.fromisoformat(value).isoformat() == value:
                return value
        except ValueError:
            pass
    return None


def _http_status(value):
    return value if type(value) is int and 100 <= value <= 599 else None


def _manual_job_metadata(row, redactor):
    # 请求 ID 由客户端提供，只保留可关联的别名。
    row["request_id"] = redactor.alias(row["request_id"])
    row["day"] = _iso_day(row["day"])
    row["status"] = known_code(row["status"], _JOB_STATUSES)
    reason = row["reason_code"]
    code, separator, http = reason.partition(":") if type(reason) is str else ("", "", "")
    if separator:
        status = _http_status(int(http)) if len(http) == 3 and http.isascii() and http.isdecimal() else None
        if status is None:
            code = ""
        elif code in _JOB_CODES:
            row["http_status"] = status
    row["reason_code"] = known_code(code, _JOB_CODES)
    return row


def record_runtime(store, operation, **values):
    recorder = getattr(store, "diagnostics", None)
    fields = _RUNTIME_FIELDS.get(operation)
    if recorder is None or fields is None:
        return
    try:
        recorder.record(operation, {key: values[key] for key in fields if key in values})
    except Exception:
        # 诊断失败不影响门禁、晚安账本或调度器。
        return


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


def scheduler_snapshot(app):
    task = getattr(app, "_scheduler", None)
    if task is None:
        task_state = "absent"
    elif not task.done():
        task_state = "running"
    else:
        task_state = "cancelled" if task.cancelled() else "done"
    state = getattr(app, "_scheduler_state", None) or {}
    fault = state.get("fault")
    return {
        "task_state": task_state,
        "configured_interval_seconds": app.config.scheduler_seconds,
        "task_fault": getattr(app, "_task_fault", ""),
        "stage": state.get("stage"),
        "in_flight": state.get("in_flight", False),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "last_success_at": state.get("last_success_at"),
        "fault": dict(fault) if fault else None,
    }


def prepare(app):
    path = app.data_dir / "livingemotion.sqlite3"
    settings = {key: getattr(app.config, key, None) for key in SETTING_FIELDS}
    settings["dream_owner_qq_set"] = bool(app.config.dream_owner_qq)
    environment = runtime_environment(app.host, local_plugin_version(Path(__file__).resolve().parents[1]), settings)
    environment.update(closed=app.closed, mode=app.effective_mode())
    environment["scheduler"] = scheduler_snapshot(app)
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

    def experiences(start, end):
        for row in rows(
            """SELECT 'entry' AS source,e.owner_key,e.kind,d.day,
                      CASE WHEN d.origin IN ('auto','manual') THEN d.origin END AS origin,
                      d.revision,e.experience_id,e.period,e.created_at,e.expires_at,e.pinned,
                      COALESCE(d.updated_at,e.created_at) AS updated_at
               FROM experiences e
               LEFT JOIN experience_daily d
                 ON d.owner_key=e.owner_key AND d.kind=e.kind AND d.experience_id=e.experience_id
               WHERE e.kind IN ('diary','dream')
                 AND e.created_at<? AND COALESCE(d.updated_at,e.created_at)>=?
               ORDER BY updated_at DESC""", start, end):
            row["day"] = _iso_day(row["day"])
            yield row
        for row in rows(
            """SELECT 'job' AS source,request_id,owner_key,kind,day,status,reason_code,
                      experience_id,attempted_at AS started_at,finished_at,
                      COALESCE(finished_at,attempted_at) AS updated_at
               FROM experience_jobs
               WHERE kind IN ('diary','dream')
                 AND attempted_at<? AND COALESCE(finished_at,attempted_at)>=?
               ORDER BY updated_at DESC""", start, end):
            yield _manual_job_metadata(row, app.diagnostics.redactor)
        # 投影状态元数据，损坏的 JSON 单独计数，不让它中断其它记录。
        for row in rows(
            """WITH auto AS (
                   SELECT owner_key,kind,attempted_at,
                          CASE WHEN json_valid(value_json) THEN value_json END AS payload
                   FROM experience_auto_status
                   WHERE kind IN ('diary','dream') AND attempted_at<?
               ), projected AS (
                   SELECT owner_key,kind,attempted_at AS started_at,
                          json_type(payload)='object' AS valid,
                          json_extract(payload,'$.status') AS status,
                          json_extract(payload,'$.reason_code') AS reason_code,
                          json_extract(payload,'$.model_reason_code') AS model_reason_code,
                          json_extract(payload,'$.http_status') AS http_status,
                          json_extract(payload,'$.day') AS day,
                          CASE WHEN json_type(payload,'$.finished_at') IN ('integer','real')
                               THEN json_extract(payload,'$.finished_at') END AS finished_at
                   FROM auto
               )
               SELECT 'auto' AS source,owner_key,kind,started_at,valid,status,reason_code,
                      model_reason_code,http_status,day,finished_at,
                      COALESCE(finished_at,started_at) AS updated_at
               FROM projected
               WHERE COALESCE(finished_at,started_at)>=?
               ORDER BY updated_at DESC""", start, end):
            if not row.pop("valid"):
                yield None
                continue
            row["status"] = known_code(row["status"], _AUTO_STATUSES)
            row["reason_code"] = known_code(row["reason_code"], _AUTO_CODES)
            if row["model_reason_code"] is not None:
                row["model_reason_code"] = known_code(row["model_reason_code"], _MODEL_RESULT_CODES)
            row["day"] = _iso_day(row["day"])
            row["http_status"] = _http_status(row["http_status"])
            yield row
        for row in rows(
            """SELECT 'attempts' AS source,purpose,period,status,COUNT(*) AS count,
                      MIN(created_at) AS at,MAX(created_at) AS updated_at
               FROM quota_reservations
               WHERE pool='experience_attempt' AND purpose IN ('diary','dream')
                 AND created_at<? AND created_at>=?
               GROUP BY purpose,period,status
               ORDER BY updated_at DESC""", start, end):
            row["status"] = known_code(row["status"], _ATTEMPT_STATUSES)
            yield row

    return app.diagnostics, {"environment": environment, "settings": settings}, {
        "events.jsonl": events, "emotion.jsonl": emotion,
        "behavior.jsonl": behavior, "promises.jsonl": promises,
        "experiences.jsonl": experiences,
    }
