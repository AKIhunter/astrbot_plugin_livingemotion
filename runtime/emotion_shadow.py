"""One independent, bounded diagnostic. It has no writeback or reply handle."""

import asyncio
import time
from collections import deque

from astrbot.api import logger

from ..contracts import prompt_json, to_dict
from ..domain.emotion import _event_problem
from ..domain.emotion_evidence import NEAR_SECONDS, SCAN_ROWS, pack_evidence, select_dialogue
from ..domain.emotion_shadow import SHADOW_SYSTEM, parse_shadow, trace_actions
from ..prompt_precision import RELATIONSHIP_FIELDS, prompt_numbers
from ..storage.console_data import read_relationship_override

DAILY_LIMIT = 12
WINDOW_SECONDS = 86400


def queue_shadow(app, event, generation, seed, projection, *, short, neutral, native):
    active = getattr(app, "_context_shadow_task", None)
    if active is not None and not active.done():
        return  # Never queue a shadow backlog behind live work.
    if _event_problem(event, app.store.clock(), NEAR_SECONDS):
        return
    relation_trace = next((row for row in projection.traces if row.get("kind") == "relationship"), {})
    comparison = {"event_key": event.idempotency_key, "status": "not_dispatched",
                  "actions": trace_actions(relation_trace.get("context_emotions", {}))}
    app._context_shadow_comparison = comparison
    task = app._context_shadow_task = asyncio.create_task(
        _inspect(app, event, generation, seed, comparison, app.revision,
                 short=short, neutral=neutral, native=native),
        name="livingemotion-context-shadow")

    def release(_):
        if app._context_shadow_comparison is comparison:
            app._context_shadow_comparison = None

    task.add_done_callback(release)


async def _inspect(app, event, generation, seed, comparison, revision, *, short, neutral, native):
    context, body = event.context, event.body
    relationship, state = seed["relationship"], seed["context_emotions"]

    async def authorized():
        if (not app.config.context_emotion_shadow_enabled
                or not app.config.emotion_model_enabled or not app.config.context_emotions_enabled
                or app.revision != revision or app._context_emotion_epoch != seed["context_epoch"]
                or app.in_quiet_hours() or app.effective_mode(context) != "active"
                or _event_problem(event, app.store.clock(), NEAR_SECONDS)
                or not await app.validate_context(context, generation)):
            return False
        source = app.bridge.source(context)
        if (not source or source.context.route != context.route
                or app.context_emotion_fingerprint(context) != seed["context_fingerprint"]):
            return False
        override = await read_relationship_override(app.store, context)
        return (override or {}).get("version", 0) == seed["override_version"]

    try:
        # Dispatch after the old path for this event. Do not occupy its worker,
        # quota, or awaited reply handle, and do not cancel it with this observer.
        live = getattr(app, "_refinement_tasks", {}).get(event.idempotency_key)
        if live:
            await asyncio.shield(live["completion"])
        if not await authorized():
            return "context_changed", ()
        rows = await app.store.emotion_dialogue_candidates(event, limit=SCAN_ROWS)
        if short and not any(row["text"] and not neutral(row["text"].strip())
                             and 0 <= event.occurred_at - row["at"] <= NEAR_SECONDS
                             for row in rows[-2:]) and not state["items"]:
            return "no_context", ()
        reply_id, reply_text = native
        active_incidents = [
            {"kind": item["kind"], "cause_code": item["cause_code"], "ref": item["evidence_refs"][0]}
            for item in state["items"] if item["evidence_refs"]
        ]
        dialogue = select_dialogue(
            body, rows, at=event.occurred_at, reply_id=reply_id, reply_text=reply_text,
            native_reply="native_bot_reply" in event.signals,
            semantic_refs={item["ref"] for item in active_incidents}, include_near=short,
        )
        if dialogue.unresolved:
            return "context_evidence_missing", ()
        source = app.bridge.source(context)
        if not source:
            return "context_changed", ()
        persona = app.emotion_persona(source.persona.prompt)[1]
        purpose = "emotion" if app.config.emotion_provider_id else ""
        binding = await app.model_binding(context, purpose=purpose)
        budget = min(8192, app.config.model_input_tokens)
        payload, _ = pack_evidence(
            SHADOW_SYSTEM, {
                "message": body, "relationship": prompt_numbers(to_dict(relationship), RELATIONSHIP_FIELDS),
                "relationship_boundary": seed["relationship_note"],
                "known_boundary": bool(state.get("boundary") or any(row.boundary for row in dialogue.rows)),
                "short_turn": short,
                "active_incidents": active_incidents,
            }, dialogue, (), contextual=True, persona_rules=persona,
            count=lambda prompt, pack: binding.count(prompt, prompt_json(pack)), budget=budget,
        )
        if payload is None:
            return "token_limit", ()
        # Possible sources are only the scoped rows actually delivered to the model.
        sent_refs = {row["ref"] for row in payload["recent_dialogue"]}
        payload["active_incidents"] = [
            item for item in active_incidents if item["ref"] in sent_refs]
        payload.pop("context_support_refs")  # The legacy phrase match is not the shadow model's proof.
        payload.pop("memories")  # First rollout uses dialogue, with no extra memory I/O.
        data = prompt_json(payload)
        if not await authorized():
            return "context_changed", ()

        now = time.monotonic()
        usage = getattr(app, "_context_shadow_usage", None)
        if usage is None:
            usage = app._context_shadow_usage = deque()
        while usage and now - usage[0] >= WINDOW_SECONDS:
            usage.popleft()
        if len(usage) >= min(DAILY_LIMIT, app.config.model_daily_limit):
            return "daily_limit", ()
        usage.append(now)  # A dispatched request counts even if timeout or output is invalid.
        timeout = app.config.model_timeout_seconds
        raw = await asyncio.wait_for(
            binding.generate(SHADOW_SYSTEM, data, min(512, app.config.model_output_tokens), timeout),
            timeout,
        )
        if (not await authorized()
                or (await app.model_binding(context, purpose=purpose)).fingerprint != binding.fingerprint):
            return "context_changed", ()
        status, actions = parse_shadow(
            raw, event, relationship, state, payload, dialogue_boundary=payload["known_boundary"])
        baseline = tuple(sorted(comparison["actions"]))
        if status == "scored" and baseline != actions:
            logger.info("[LE-emotion-shadow] event=%s baseline_status=%s baseline=%s candidate=%s",
                        event.idempotency_key, comparison["status"], ",".join(baseline) or "-",
                        ",".join(actions) or "-")
        return status, actions
    except asyncio.TimeoutError:
        return "task_timeout", ()
    except Exception:
        return "analysis_failed", ()
