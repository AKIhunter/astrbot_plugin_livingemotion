"""Atomic night mutations, wake idempotency, and reply admission/submission."""

import json

from ..contracts import (
    Context, NightState, StateOwner, StateRecord, StateWrite, canonical_json, stable_key, to_dict,
)


class NightStore:
    async def reset_sleep_permission(self, instance_id):
        """Normalize all persisted nights in this instance, including idle scenes.

        Used when disabling and just before re-enabling: the new clock origin
        prevents charging for the closed interval. Other state kinds are kept.
        """
        from types import SimpleNamespace
        from ..domain.night import sleepless_state
        now = self._now()

        def commit(db):
            def mutate():
                rows = list(db.execute(
                    """SELECT s.*, c.context_json FROM states s JOIN scopes c
                       ON c.scope_key=s.scope_key WHERE s.kind='night'
                       AND s.record_key='' AND json_extract(c.context_json,'$.instance_id')=?""",
                    (instance_id,),
                ))
                owners = list(db.execute(
                    """SELECT s.* FROM owner_states s JOIN state_owners o
                       ON o.owner_key=s.owner_key JOIN state_modes m
                       ON m.persona_key=o.persona_key WHERE s.kind='night' AND m.instance_id=?""",
                    (instance_id,),
                ))
                for row in (*rows, *owners):
                    owned = "owner_key" in row.keys()
                    key = row["owner_key"] if owned else row["scope_key"]
                    value = json.loads(row["value_json"])
                    before = self._night_value(value)
                    after = sleepless_state(before, now=now)
                    runtime = dict(value.get("_runtime", {}))
                    runtime.pop("manual_wake_until", None)
                    payload = {**value, **to_dict(after), "_runtime": runtime}
                    if payload == value:
                        continue
                    table, column = ("owner_states", "owner_key") if owned else ("states", "scope_key")
                    db.execute(
                        f"UPDATE {table} SET value_json=?,updated_at=?,version=version+1 "
                        f"WHERE {column}=? AND kind='night'" +
                        ("" if owned else " AND record_key=''"),
                        (canonical_json(payload), after.updated_at, key),
                    )
                    if (before.energy != 100 or before.phase != after.phase
                            or before.display_state != after.display_state):
                        # A global config change has no originating chat.
                        context = SimpleNamespace(scope_key=key)
                        self._append_energy(
                            db, context, key, stable_key("sleep-config", key, row["version"]),
                            "allow_sleep", before, after, ({
                                "occurred_at": after.updated_at, "category": "config",
                                "before_units": int(round(before.energy * 10)), "after_units": 1000,
                                "reason_code": "sleep_disabled",
                            },),
                        )
                return len(rows) + len(owners)
            return self._transaction(db, mutate)
        return await self._run(commit)

    async def night_operation(self, context, transform, *, operation="tick", reply_id=None,
                              event=None, ticket=None, expected_generation=None):
        """Run a pure transform under the same transaction as admission and logs.

        transform(state, runtime, now, admitted_attempt) -> (state, changes, details).
        details.allowed gates the side effect, but elapsed state still commits.
        """
        from .sqlite import _Rejected
        if operation not in ("tick", "reply_started", "reply_submitted", "reply_failed",
                             "wake", "manual", "dream_wake"):
            raise ValueError("invalid night operation")
        if operation.startswith("reply_") and (
            not isinstance(reply_id, str) or not reply_id.strip() or len(reply_id) > 512
        ):
            raise ValueError("invalid reply ID")
        if operation == "wake" and (event is None or event.context != context):
            raise ValueError("wake source mismatch")
        owner = self.state_owner(context)
        now = self._now()

        def commit(db):
            def mutate():
                generation = self._generation(db, context)
                self._check_generation(db, context, generation if expected_generation is None
                                       else expected_generation)
                self._check_owner(db, context, owner)
                reply_key = stable_key("reply", context.scope_key, reply_id) if reply_id else None
                attempt = None
                if reply_key:
                    attempt = db.execute("SELECT * FROM reply_attempts WHERE reply_key=?",
                                         (reply_key,)).fetchone()
                if operation == "reply_started" and attempt:
                    return {"allowed": False, "status": "duplicate", "reason_code": "reply_exists"}
                if operation == "reply_failed" and (attempt is None or attempt["status"] != "started"):
                    return {"allowed": False, "status": "duplicate" if attempt else "rejected",
                            "reason_code": "reply_not_started"}
                if operation == "reply_submitted":
                    if attempt is None or attempt["status"] != "started":
                        return {"allowed": False, "status": "duplicate" if attempt else "rejected",
                                "reason_code": "reply_not_started"}
                    if ticket is None or ticket.get("reply_key") != reply_key or (
                        ticket.get("started_at") != attempt["started_at"]
                    ):
                        raise _Rejected("reply_ticket_required")
                    if attempt["source_generation"] != generation:
                        raise _Rejected("stale_generation")
                    admitted_owner = StateOwner(**json.loads(attempt["owner_json"])) if (
                        attempt["owner_json"]
                    ) else None
                    self._check_owner(db, context, admitted_owner)
                    previous = Context.from_dict(json.loads(attempt["context_json"]))
                    if previous != context:
                        raise _Rejected("reply_context_changed")
                if operation == "wake":
                    prior = db.execute("SELECT accepted,reason_code FROM wake_attempts "
                                       "WHERE event_key=?", (event.idempotency_key,)).fetchone()
                    if prior:
                        return {"allowed": False, "status": "duplicate",
                                "reason_code": "duplicate_wake"}
                if owner is not None:
                    record = self._owned_record(db, context, "night", owner)
                else:
                    row = db.execute("SELECT * FROM states WHERE scope_key=? AND kind='night' "
                                     "AND record_key=''", (context.scope_key,)).fetchone()
                    record = StateRecord("night", json.loads(row["value_json"]), row["version"],
                                         row["generation"], row["updated_at"]) if row else None
                value = dict(record.value) if record else {}
                state = self._night_value(value) if record else NightState(updated_at=now)
                runtime = dict(value.get("_runtime", {}))
                if (state.policy_version == 2 and state.wake_session
                        and state.wake_replies_used >= state.wake_reply_limit):
                    pending = db.execute(
                        "SELECT COUNT(*) FROM reply_attempts WHERE status='started' "
                        "AND wake_session=? AND cycle_id=?",
                        (state.wake_session, state.cycle_id),
                    ).fetchone()[0]
                    if pending == 0:
                        # 重启/取消已经清掉全部在途票据，末轮不能永远卡在唤醒窗口。
                        from ..domain.night import finish_life_wake
                        state = finish_life_wake(state, now=now)
                admitted = dict(attempt) if attempt else None
                if admitted and admitted["wake_session"]:
                    # 共享作息下跨会话的已获准回复也属于同一唤醒窗，不能提前截断。
                    admitted["pending_wake_replies"] = db.execute(
                        "SELECT COUNT(*) FROM reply_attempts WHERE status='started' "
                        "AND wake_session=? AND cycle_id=? AND reply_key<>?",
                        (admitted["wake_session"], admitted["cycle_id"], reply_key),
                    ).fetchone()[0]
                after, changes, details = transform(state, runtime, now, admitted)
                allowed = details.get("allowed", True)
                reason = details.get("reason_code", "night_committed")
                write = StateWrite("night", {**to_dict(after), "_runtime": runtime},
                                   record.version if record else 0, owner=owner,
                                   energy_events=tuple({
                                       **change, "source_id": event.source_id if event else
                                       reply_id or operation,
                                   } for change in changes))
                versions = self._write_states(db, context, generation, (write,), now)
                if operation == "reply_started":
                    db.execute(
                        """INSERT INTO reply_attempts VALUES(?,?,?,?,?,?,?,?,NULL,?,?)""",
                        (reply_key, context.scope_key, reply_id, generation,
                         canonical_json(owner) if owner else None, after.cycle_id,
                         after.wake_session, now, "started" if allowed else "denied",
                         canonical_json(context)),
                    )
                elif operation == "reply_submitted":
                    db.execute("UPDATE reply_attempts SET submitted_at=?,status=? "
                               "WHERE reply_key=?",
                               (now if allowed else None, "submitted" if allowed else "denied",
                                reply_key))
                elif operation == "reply_failed":
                    db.execute("UPDATE reply_attempts SET status='failed' WHERE reply_key=?",
                               (reply_key,))
                elif operation == "wake":
                    db.execute("INSERT INTO wake_attempts VALUES(?,?,?,?,?,?)",
                               (event.idempotency_key, owner.owner_key if owner else
                                context.scope_key, after.cycle_id, now, int(allowed), reason))
                return {
                    **details, "allowed": allowed,
                    "status": "accepted" if allowed else "rejected", "reason_code": reason,
                    "night": after, "versions": versions,
                    "ticket": {"reply_key": reply_key, "started_at": now,
                               "source_generation": generation, "owner": to_dict(owner)}
                    if operation == "reply_started" and allowed else None,
                }
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return {"allowed": False, "status": "rejected", "reason_code": exc.reason}
        return await self._run(commit)

    async def reply_failed(self, context, reply_id):
        from ..domain.night import finish_life_wake

        def transform(state, runtime, now, attempt):
            if (state.policy_version == 2 and state.wake_session
                    and state.wake_session == attempt["wake_session"]
                    and state.wake_replies_used >= state.wake_reply_limit
                    and attempt.get("pending_wake_replies", 0) == 0):
                state = finish_life_wake(state, now=now)
            return state, (), {"allowed": True, "reason_code": "reply_failed"}
        result = await self.night_operation(context, transform, operation="reply_failed",
                                           reply_id=reply_id)
        return result.get("allowed") is True

    async def reply_ticket(self, context, reply_id):
        key = stable_key("reply", context.scope_key, reply_id)
        def read(db):
            row = db.execute("SELECT * FROM reply_attempts WHERE reply_key=?", (key,)).fetchone()
            if not row or row["status"] != "started":
                return None
            return {"reply_key": key, "started_at": row["started_at"],
                    "source_generation": row["source_generation"],
                    "owner": json.loads(row["owner_json"]) if row["owner_json"] else None}
        return await self._run(read)

    async def archived_event(self, context, event_key):
        from ..contracts import Event
        def read(db):
            row = db.execute("SELECT metadata_json FROM events WHERE scope_key=? AND event_key=?",
                             (context.scope_key, event_key)).fetchone()
            if not row:
                return None
            data = json.loads(row[0])
            data["body"] = ""
            original = Context.from_dict(data["context"])
            data["context"] = {**to_dict(original), "route": context.route}
            if Context.from_dict(data["context"]) != context:
                return None
            return Event.from_dict(data)
        return await self._run(read)
