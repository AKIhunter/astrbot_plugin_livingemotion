"""Offline continuous dialogue through LE and the real AstrBot request serializer."""

import asyncio
import hashlib
import json
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest
from astrbot.api.message_components import At, Plain
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import StarTools
from astrbot.core.agent.message import TextPart
from astrbot.core.message.message_event_result import MessageEventResult, ResultContentType
from astrbot.core.pipeline.context_utils import call_event_hook
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.platform_metadata import PlatformMetadata
from astrbot.core.star.star_handler import EventType, star_handlers_registry

from astrbot_plugin_livingemotion.contracts import Context, account_person_key
from astrbot_plugin_livingemotion.domain.context_emotion import POLICIES, expression_items
from astrbot_plugin_livingemotion.main import LivingEmotionPlugin
from astrbot_plugin_livingemotion.runtime.application import SUFFIX
from astrbot_plugin_livingemotion.runtime.projector import stored_context_emotions
from astrbot_plugin_livingemotion.storage.console_data import write_relationship_override


CASES = Path(__file__).resolve().with_name("realtime_emotion_cases.json.fixture")
FIXTURE = json.loads(CASES.read_text(encoding="utf-8"))
TEXT = FIXTURE["utterances"]
PROBES = FIXTURE["probes"]
# The original explicit denial settles locally; use this wording to exercise late calibration.
PARAPHRASE = PROBES["late_denial"]
HURT_PROBE = PROBES["hurt"]
MIXED = PARAPHRASE + HURT_PROBE
EMPTY_PROBE = PROBES["failed_response"]
WARM_PROBE = PROBES["late_warmth"]
OTHER_REPAIR = PROBES["other_repair"]
ORIGIN = datetime(2026, 11, 28, 12, tzinfo=timezone.utc).timestamp()
REPLAY_TIMEOUT = 3.0
REALTIME_REQUEST_BUDGET_MS = 750


class OfflineHost:
    persona_manager = conversation_manager = property(lambda self: self)

    def get_config(self):
        return {}

    def get_registered_star(self, name):
        return None

    async def get_curr_conversation_id(self, route):
        return None

    async def resolve_selected_persona(self, **kwargs):
        return "offline-persona", {"prompt": "Offline acceptance persona."}, None, False

    async def get_current_chat_provider_id(self, route):
        pytest.fail("unexpected host provider lookup")

    async def send_message(self, *args):
        pytest.fail("unexpected platform send")


class OfflineEvent(AstrMessageEvent):
    async def send(self, *args):
        pytest.fail("unexpected native event send")


def event_at(name, text, at, *, actor="a", group="", mention=True):
    msg = AstrBotMessage()
    msg.type = MessageType.GROUP_MESSAGE if group else MessageType.FRIEND_MESSAGE
    msg.message_id, msg.message_str, msg.timestamp = name, text, at
    msg.self_id, msg.group_id = "offline-bot", group
    msg.sender = MessageMember(user_id=actor, nickname=actor)
    msg.message = ([At(qq=msg.self_id)] if group and mention else []) + [Plain(text=text)]
    return OfflineEvent(
        text, msg, PlatformMetadata(
            name="aiocqhttp", description="Synthetic only, no platform instance", id="offline",
        ), session_id=group or actor,
    )


def appraisal(kind, evidence, *, refs=()):
    return {
        "kind": kind, "evidence": evidence, "context_refs": list(refs),
        "cause_code": {"wronged": "devalued_contribution", "hurt": "direct_devaluation",
                       "shyness": "warm_attention"}[kind],
        "holder": "bot", "target": "current_interlocutor",
        "action": "increase", "confidence": .9, "strength": .6,
    }


class ScriptedProvider:
    fingerprint = "offline-acceptance"

    def __init__(self):
        self.calls = []
        self.routes = []
        self.replies = {}
        self.gates = {}
        self.started = {}
        self.timeouts = set()
        self.active = self.max_active = 0

    def hold(self, body):
        self.gates[body] = asyncio.Event()
        self.started[body] = asyncio.Event()

    def release(self, body):
        self.gates[body].set()

    @staticmethod
    def count(system, data):
        return len((system + data).encode("utf-8")) + 256

    async def generate(self, system, data, output_tokens, timeout):
        packet = json.loads(data)
        body = packet["message"]
        rows = self.replies.get(body, [])
        object_only = "不要四维delta" in system
        self.calls.append(call := {
            "message": body, "path": "object" if object_only else "joint",
            "history": packet.get("recent_dialogue", []),
            "support_refs": packet.get("context_support_refs", []),
            "rows": rows, "status": "pending",
        })
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if body in self.gates:
                self.started[body].set()
                await self.gates[body].wait()
            if body in self.timeouts:
                call["status"] = "timeout"
                raise TimeoutError("synthetic model timeout")
            call["status"] = "returned" if body in self.replies else "empty"
            if body not in self.replies:
                return ""
            result = {"context_appraisals": rows}
            if not object_only:
                # A late joint response must not apply these shared changes.
                result.update(rule_version="emotion-3", delta={"pleasure": .1, "stress": .1},
                              confidence=.9, control=.8, appraisals=[])
            return json.dumps(result, ensure_ascii=False)
        except asyncio.CancelledError:
            call["status"] = "cancelled"
            raise
        finally:
            self.active -= 1


def intensities(items):
    return {row["kind"]: row["intensity"] for row in items}


def snapshot_bytes(assembled):
    return json.dumps(assembled, ensure_ascii=False, sort_keys=True).encode()


@dataclass
class Turn:
    event: OfflineEvent
    context: Context
    key: str
    origin: dict
    request: ProviderRequest
    wire: bytes
    expressed: dict
    stored: dict
    evidence: dict


class Replay:
    def __init__(self, plugin, clock, monkeypatch):
        self.plugin, self.app, self.clock = plugin, plugin.application, clock
        self.monkeypatch = monkeypatch
        self.provider, self.turns, self.diagnostics = ScriptedProvider(), [], []

    async def dispatch(self, event, hook_type, *args):
        # Bind the decorated handlers as AstrBot's plugin loader does, without loading a platform.
        handlers = star_handlers_registry.get_handlers_by_event_type(
            hook_type, plugins_name=event.plugins_name,
        )
        assert handlers
        completed = []
        record = event.trace.record

        def observe(action, **fields):
            record(action, **fields)
            if action == "handler_end":
                completed.append((fields["handler"], fields["status"]))

        with self.monkeypatch.context() as patch:
            patch.setattr(event.trace, "record", observe)
            for handler in handlers:
                assert handler.handler_module_path == LivingEmotionPlugin.__module__
                patch.setattr(handler, "handler", getattr(self.plugin, handler.handler_name))
            assert not await call_event_hook(event, hook_type, *args)
        assert completed == [(handler.handler_name, "success") for handler in handlers]
        return [name for name, _ in completed]

    async def stored(self, context):
        record = await self.app.store.context_emotion_record(context)
        return stored_context_emotions(
            record, context, now=self.clock[0],
            fingerprint=self.app.context_emotion_fingerprint(context),
            epoch=self.app._context_emotion_epoch,
        )

    async def start(self, name, text, *, step=1, **source):
        self.clock[0] += step
        event = event_at(name, text, self.clock[0], **source)
        event.plugins_name = ["astrbot_plugin_livingemotion"]
        await self.plugin.observe_message(event)
        assert event.get_extra("livingemotion:ingest") == "accepted"
        context = Context.from_dict(event.get_extra("livingemotion:context"))
        # Take the persisted origin snapshot before the main request hook.
        origin = intensities(expression_items(
            await self.stored(context), context, now=self.clock[0],
        ))
        return event, context, origin

    async def request(self, started):
        event, context, origin = started
        req = ProviderRequest(prompt=event.message_str)

        async def inject():
            hooks = await self.dispatch(event, EventType.OnLLMRequestEvent, req)
            pending = [c["message"] for c in self.provider.calls if c["status"] == "pending"]
            return hooks, pending

        start = time.monotonic()
        hooks, pending_at_injection = await asyncio.wait_for(inject(), REPLAY_TIMEOUT)
        elapsed = round((time.monotonic() - start) * 1000, 1)
        assembled = await req.assemble_context()
        parts = [p for p in req.extra_user_content_parts if p.text.startswith(SUFFIX)]
        wire = snapshot_bytes(assembled)
        content = assembled["content"]
        blocks = [b for b in content if b.get("text", "").startswith(SUFFIX)] \
            if isinstance(content, list) else []
        expressed = intensities(json.loads(blocks[0]["text"].splitlines()[-1])["bot"].get(
            "context_emotions", [],
        )) if len(blocks) == 1 else {}
        stored = intensities(expression_items(
            await self.stored(context), context, now=self.clock[0],
        ))
        evidence = {
            "id": event.message_obj.message_id, "actor": context.account_id,
            "t": self.clock[0] - ORIGIN, "origin": origin, "expressed": expressed,
            "stored": stored, "state_blocks": len(blocks), "request_ms": elapsed,
            "state_bytes": sum(len(block["text"].encode()) for block in blocks),
            "serialized_request": wire.decode(),
            "wire_sha256": hashlib.sha256(wire).hexdigest(),
            "native_request_hooks": hooks,
            "pending_at_injection": pending_at_injection,
        }
        self.turns.append(evidence)
        assert assembled["role"] == "user"
        assert len(parts) == len(blocks) == 1, (event.message_str, assembled)
        assert isinstance(parts[0], TextPart) and blocks[0]["_no_save"] is True
        assert blocks[0]["text"] == parts[0].text
        assert content[0] == {"type": "text", "text": event.message_str}
        return Turn(event, context, event.get_extra("livingemotion:event_key"),
                    origin, req, wire, expressed, stored, evidence)

    async def turn(self, name, text, **source):
        return await self.request(await self.start(name, text, **source))

    async def close_job(self, turn):
        row = getattr(self.app, "_refinement_tasks", {}).get(turn.key)
        if row is not None:
            await asyncio.wait_for(asyncio.shield(row.get("completion", row["task"])), REPLAY_TIMEOUT)

    async def submit(self, turn):
        result = MessageEventResult().message("Synthetic reply, not sent.")
        turn.event.set_result(result.set_result_content_type(ResultContentType.LLM_RESULT))
        hooks = await self.dispatch(turn.event, EventType.OnDecoratingResultEvent)
        lease = turn.event.get_extra("livingemotion:reply_lease")
        archive = await self.app.store._run(lambda db: db.execute(
            "SELECT 1 FROM events WHERE producer='livingemotion.host' "
            "AND event_type='bot_reply_submitted' AND scope_key=? "
            "AND json_extract(metadata_json,'$.event_id')=?",
            (turn.context.scope_key, lease["attempt_id"]),
        ).fetchone())
        assert archive is not None
        turn.evidence["submitted"] = True
        turn.evidence["native_submission_hooks"] = hooks

    async def seed_relationship(self, context):
        await write_relationship_override(self.app.store, context, expected_version=0,
                                          actor_id="offline", reason="fixture", score=50)

    async def assert_pending(self, turn, body):
        await asyncio.wait_for(self.provider.started[body].wait(), REPLAY_TIMEOUT)
        matching = [c for c in self.provider.calls if c["message"] == body]
        assert len(matching) == 1 and matching[0]["status"] == "pending"
        assert not self.provider.gates[body].is_set()
        assert self.app._refinement_tasks[turn.key]["task"].done() is False
        turn.evidence["provider_pending"] = True
        return matching[0]

    async def assert_frozen(self, turn):
        assert snapshot_bytes(await turn.request.assemble_context()) == turn.wire
        turn.evidence["wire_unchanged_after_callback"] = True

    async def event_trace(self, turn):
        row = await self.app.store._run(lambda db: db.execute(
            "SELECT value_json FROM event_traces WHERE event_key=? AND scope_key=? "
            "AND kind='relationship'", (turn.key, turn.context.scope_key),
        ).fetchone())
        return json.loads(row[0])["context_emotions"] if row else {}


@pytest.fixture
async def make_replay(tmp_path, monkeypatch, record_property):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("network")
        pytest.fail("offline emotion acceptance may not open a connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    replays = []

    async def create(*, model=True, dimension="conversation"):
        clock = [ORIGIN]
        config = {
            "context_emotions_enabled": True, "context_emotions_dimension": dimension,
            "emotion_model_enabled": model, "allow_sleep": False, "timezone": "UTC",
            "emotion_quiet_start_hour": 0, "emotion_quiet_end_hour": 0,
            "catchup_enabled": False, "catchup_reply_enabled": False,
            "memory_read": False, "memory_write": False, "promise_enabled": False,
            "weather_factor_enabled": False, "diary_enabled": False, "dream_enabled": False,
            "autonomy_enabled": False, "closing_enabled": False,
        }
        with monkeypatch.context() as patch:
            patch.setattr(StarTools, "get_data_dir", lambda name: tmp_path / str(len(replays)))
            plugin = LivingEmotionPlugin(OfflineHost(), config)
        app = plugin.application
        await app.initialize()
        app.store.clock = app.memory.clock = lambda: clock[0]
        replay = Replay(plugin, clock, monkeypatch)
        replays.append(replay)
        assert app.config.context_emotions_dimension == dimension
        assert app.config.emotion_model_enabled == model

        async def binding(context, **kwargs):
            replay.provider.routes.append(kwargs.get("purpose", "default"))
            return replay.provider

        app.model_binding = binding
        original_analysis = app._analysis

        def analysis(event, status, reason_code, **fields):
            replay.diagnostics.append({
                "event": event.event_id, "status": status, "reason": reason_code,
            })
            return original_analysis(event, status, reason_code, **fields)

        app._analysis = analysis
        return replay

    yield create
    for replay in replays:
        await replay.app.terminate()
        record_property("replay", json.dumps({
            "turns": replay.turns, "stub_calls": replay.provider.calls,
            "stub_binding_lookups": replay.provider.routes,
            "diagnostics": replay.diagnostics, "network_attempts": len(attempts),
        }, ensure_ascii=False))
    assert not attempts


def assert_snapshot(turn, *kinds):
    assert set(turn.origin) == set(turn.stored) == set(turn.expressed) == set(kinds), (
        turn.evidence
    )
    for kind in kinds:
        assert turn.origin[kind] == pytest.approx(turn.stored[kind], abs=.001)
        assert turn.expressed[kind] == pytest.approx(turn.stored[kind], abs=.001)


async def held_denial(replay, *, body=PARAPHRASE, extra=()):
    proof = await replay.turn("ack", TEXT["help"])
    assert_snapshot(proof)
    replay.provider.hold(body)
    replay.provider.replies[body] = [appraisal("wronged", PARAPHRASE, refs=[proof.key]), *extra]
    first = await replay.turn("delayed", body)
    call = await replay.assert_pending(first, body)
    assert body in first.evidence["pending_at_injection"]
    assert first.evidence["request_ms"] < 1500
    assert_snapshot(first)
    assert call["support_refs"] == [proof.key]
    assert any(row["ref"] == proof.key and row["role"] == "human"
               and row["text"] == TEXT["help"] for row in call["history"])
    assert call["rows"][0]["context_refs"] == [proof.key]
    return first


@pytest.mark.parametrize("model", [False, True], ids=["model-off", "model-on"])
async def test_A_confirm_deny_continue_minimize_repair(make_replay, model):
    r = await make_replay(model=model)
    help_turn = await r.turn("ack", TEXT["help"])
    if model:
        r.provider.hold(TEXT["deny"])
        r.provider.replies[TEXT["deny"]] = [
            appraisal("wronged", TEXT["deny"], refs=[help_turn.key]),
        ]
    deny = await r.turn("deny", TEXT["deny"])
    if model:
        assert deny.evidence["request_ms"] < REALTIME_REQUEST_BUDGET_MS
        r.provider.release(TEXT["deny"])
        await r.close_job(deny)
        assert intensities((await r.stored(deny.context))["items"]) == pytest.approx(
            deny.origin, abs=.001,
        )
    cont = await r.turn("continue", TEXT["continue"], step=120)
    minimize = await r.turn("minimize", TEXT["minimize"], step=15)
    if model:
        r.provider.hold(TEXT["repair"])
    repair = await r.turn("repair", TEXT["repair"], step=15)
    if model:
        assert repair.evidence["request_ms"] < REALTIME_REQUEST_BUDGET_MS
        r.provider.release(TEXT["repair"])
        await r.close_job(repair)
    after = await r.turn("after", TEXT["finish"], step=120)
    assert_snapshot(help_turn)
    for turn in (deny, cont, minimize, repair, after):
        assert_snapshot(turn, "wronged")
    assert deny.origin["wronged"] >= .45
    prior = deny.origin["wronged"]
    for turn, seconds in ((cont, 120), (minimize, 15)):
        assert turn.origin["wronged"] == pytest.approx(prior * 2 ** (-seconds / 1800), abs=.001)
        prior = turn.origin["wronged"]
    assert .20 <= repair.origin["wronged"] < minimize.origin["wronged"] - .08
    assert .20 <= after.origin["wronged"] < repair.origin["wronged"]
    if not model:
        assert not r.provider.calls


async def test_B_other_person_cannot_borrow_evidence(make_replay):
    r = await make_replay()
    scope = {"group": "same-group"}
    a = await r.turn("a-help", TEXT["help"], **scope)
    a_deny = await r.turn("a-deny", TEXT["deny"], **scope)
    b = await r.turn("b-deny", TEXT["deny"], actor="b", **scope)
    assert_snapshot(a_deny, "wronged")
    assert_snapshot(b)
    # A semantic adversary returns the actual foreign ref, not a fabricated ID.
    r.provider.replies[PARAPHRASE] = [appraisal("wronged", PARAPHRASE, refs=[a.key])]
    foreign = await r.turn("b-paraphrase", PARAPHRASE, actor="b", **scope)
    assert_snapshot(foreign)
    await r.close_job(foreign)
    call, = [c for c in r.provider.calls if c["message"] == PARAPHRASE]
    assert call["status"] == "returned"
    assert a.key not in call["support_refs"]
    assert a.key not in {row["ref"] for row in call["history"]}
    assert not intensities((await r.stored(b.context))["items"])
    again = await r.turn("a-again", TEXT["finish"], **scope)
    assert_snapshot(again, "wronged")


@pytest.mark.parametrize("case,submit,intervening", [
    ("C", True, None), ("D", True, "continue"),
    ("E", True, "repair"), ("E-other-topic", True, "other-repair"), ("J", False, None),
], ids=["C-submitted", "D-ordinary-turn", "E-repaired", "E-other-topic", "J-not-submitted"])
async def test_late_causal_chain(make_replay, case, submit, intervening):
    r = await make_replay()
    first = await held_denial(r)
    origin_at = first.event.message_obj.timestamp
    assert not (await r.stored(first.context))["items"]
    if submit:
        await r.submit(first)
    if intervening:
        inserted = await r.turn(
            "intervening", OTHER_REPAIR if intervening == "other-repair" else TEXT[intervening],
            step=3,
        )
        assert_snapshot(inserted)
        assert not (await r.stored(first.context))["items"]
        await r.assert_pending(first, PARAPHRASE)
        if case == "E":
            assert PARAPHRASE in inserted.evidence["pending_at_injection"]
            assert inserted.evidence["request_ms"] < REALTIME_REQUEST_BUDGET_MS
    r.clock[0] = origin_at + 4
    bot = await r.app.store.get_state(first.context, "bot")
    ledger = await r.app.store.relationship_ledger(first.context)
    r.provider.release(PARAPHRASE)
    await r.close_job(first)
    assert [c["status"] for c in r.provider.calls if c["message"] == PARAPHRASE] == ["returned"]
    assert await r.app.store.get_state(first.context, "bot") == bot
    assert await r.app.store.relationship_ledger(first.context) == ledger
    await r.assert_frozen(first)
    trace = await r.event_trace(first)
    first.evidence["writeback_trace"] = trace
    assert trace["deferred"] is True
    later = await r.turn("after", TEXT["finish"])
    if case == "E":
        assert_snapshot(later)
        assert "context_cause_already_repaired" in trace["reason_codes"]
        assert not trace["before"] and not trace["after"]
    else:
        assert_snapshot(later, "wronged")
        assert "context_wronged" in trace["reason_codes"]
        assert "context_cause_already_repaired" not in trace["reason_codes"]
        item, = (await r.stored(first.context))["items"]
        assert item["started_at"] == origin_at
        assert item["expires_at"] == origin_at + POLICIES["wronged"][2]
        later.evidence["event_anchored_ttl"] = item["expires_at"] - origin_at


@pytest.mark.parametrize("late_warmth", [False, True], ids=["empty", "late-shyness"])
async def test_F_boundary_is_realtime_with_provider_pending(make_replay, late_warmth):
    r = await make_replay()
    first = await r.turn("first", TEXT["first"])
    await r.seed_relationship(first.context)
    warm = await r.turn("warm", TEXT["warm"])
    assert_snapshot(warm, "shyness")
    assert warm.origin["shyness"] >= .4
    if late_warmth:
        r.provider.hold(WARM_PROBE)
        r.provider.replies[WARM_PROBE] = [appraisal("shyness", WARM_PROBE)]
        pending = await r.turn("warm-probe", WARM_PROBE)
        await r.assert_pending(pending, WARM_PROBE)
    r.provider.hold(TEXT["boundary"])
    boundary = await r.turn("boundary", TEXT["boundary"])
    assert_snapshot(boundary)
    assert boundary.evidence["request_ms"] < REALTIME_REQUEST_BUDGET_MS
    if late_warmth:
        assert WARM_PROBE in boundary.evidence["pending_at_injection"]
        r.provider.release(WARM_PROBE)
        await r.close_job(pending)
        assert [c["status"] for c in r.provider.calls if c["message"] == WARM_PROBE] == ["returned"]
        await r.assert_frozen(pending)
    after = await r.turn("after-boundary", TEXT["finish"])
    assert_snapshot(after)
    assert "shyness" not in intensities((await r.stored(after.context))["items"])
    r.provider.release(TEXT["boundary"])
    await r.close_job(boundary)
    # The implementation may skip a redundant boundary call; any call gets no useful response.
    assert [c["status"] for c in r.provider.calls if c["message"] == TEXT["boundary"]] in ([], ["empty"])
    assert_snapshot(await r.turn("new-warm-under-boundary", TEXT["warm"]))


@pytest.mark.parametrize("timed_out", [False, True], ids=["G-empty", "timeout"])
async def test_G_unusable_result_does_not_retry_or_erase(make_replay, timed_out):
    r = await make_replay()
    await r.turn("ack", TEXT["help"])
    deny = await r.turn("deny", TEXT["deny"])
    assert_snapshot(deny, "wronged")
    ordinary = await r.turn("ordinary", TEXT["continue"], step=120)
    assert_snapshot(ordinary, "wronged")
    # The original neutral line is now skipped; use an ambiguous line for the failure branch.
    if timed_out:
        r.provider.timeouts.add(EMPTY_PROBE)
    unknown = await r.turn("unknown", EMPTY_PROBE, step=60)
    await r.close_job(unknown)
    after = await r.turn("after", TEXT["finish"], step=60)
    assert_snapshot(unknown, "wronged")
    assert_snapshot(after, "wronged")
    before = deny.origin["wronged"]
    for turn, seconds in ((ordinary, 120), (unknown, 60), (after, 60)):
        assert turn.stored["wronged"] == pytest.approx(
            before * 2 ** (-seconds / 1800), abs=.001,
        )
        before = turn.stored["wronged"]
    call, = [c for c in r.provider.calls if c["message"] == EMPTY_PROBE]
    assert call["status"] == ("timeout" if timed_out else "empty")
    assert not any(c["message"] in (TEXT["continue"], TEXT["finish"]) for c in r.provider.calls)


async def test_H_six_neutral_turns_in_fifty_seconds(make_replay):
    r = await make_replay()
    for index, text in enumerate(FIXTURE["neutral"]):
        turn = await r.turn(f"neutral-{index + 1}", text, step=10 if index else 0)
        await r.close_job(turn)
        assert_snapshot(turn)
    assert r.turns[-1]["t"] - r.turns[0]["t"] == 50
    assert len(r.provider.calls) <= 1


async def test_shadow_short_turn_leaves_native_request_and_persisted_state_untouched(make_replay):
    from astrbot_plugin_livingemotion.domain.emotion_shadow import SHADOW_SYSTEM

    r = await make_replay(model=False)
    prior = "这故障不是你造成的，可他们问起来我还是会把账算给你。"
    context_turn = await r.turn("prior-blame", prior)
    r.app.native_config.update(emotion_model_enabled=True, context_emotion_shadow_enabled=True)
    await r.app.refresh_config()
    started, release = asyncio.Event(), asyncio.Event()

    async def generate(system, data, output_tokens, timeout):
        assert system == SHADOW_SYSTEM and output_tokens <= 512
        payload = json.loads(data)
        assert payload["short_turn"] and payload["message"] == "好？"
        assert any(row["ref"] == context_turn.key for row in payload["recent_dialogue"])
        started.set()
        await release.wait()
        return json.dumps({"boundary": None, "context_appraisals": [{
            "kind": "wronged", "cause_code": "admitted_unfair_blame", "action": "increase",
            "holder": "bot", "target": "current_interlocutor", "confidence": .9, "strength": .5,
            "evidence": "好？", "prior": {
                "ref": context_turn.key, "evidence": prior, "relation": "supports_current_reading",
            },
        }]}, ensure_ascii=False)

    r.monkeypatch.setattr(r.provider, "generate", generate)
    awaitable = asyncio.create_task(r.turn("shadow-short", "好？"))
    await asyncio.wait_for(started.wait(), REPLAY_TIMEOUT)
    turn = await asyncio.wait_for(awaitable, .5)
    assert_snapshot(turn)
    assert turn.key not in getattr(r.app, "_refinement_tasks", {})
    trace = await r.event_trace(turn)
    stored = await r.stored(turn.context)
    release.set()
    assert await r.app._context_shadow_task == ("scored", ("wronged:increase:admitted_unfair_blame",))
    assert trace == await r.event_trace(turn)
    assert stored == await r.stored(turn.context)
    await r.close_job(turn)


async def test_I_offline_same_evidence_contrast(make_replay):
    r = await make_replay(model=False)
    assert_snapshot(await r.turn("a-help", TEXT["help"]))
    a = await r.turn("a-deny", TEXT["deny"])
    assert_snapshot(a, "wronged")
    b = await r.turn("b-deny", TEXT["deny"], actor="b")
    assert_snapshot(b)
    assert not (await r.stored(b.context))["items"]
    repaired = await r.turn("a-repair", TEXT["repair"])
    assert_snapshot(repaired, "wronged")
    assert .20 <= repaired.origin["wronged"] < a.origin["wronged"] - .08
    assert not r.provider.calls


async def test_same_person_different_topic_or_reported_speech_is_not_proof(make_replay):
    r = await make_replay(model=False)
    await r.turn("ack", TEXT["help"])
    for name, line in [
        ("other-topic", "你从没帮我修好证书续期。"),
        ("quote", "我在转述同事的话：『你从没帮我解决路由超时』。"),
        ("hypothesis", "假如你从没帮我解决路由超时。"),
    ]:
        assert_snapshot(await r.turn(name, line))
    denied = await r.turn("deny", TEXT["deny"])
    assert_snapshot(denied, "wronged")
    other_repair = await r.turn("other-repair", OTHER_REPAIR)
    assert_snapshot(other_repair, "wronged")
    assert other_repair.origin["wronged"] == pytest.approx(denied.origin["wronged"], abs=.001)
    hurt = await r.turn("insult", PROBES["direct_insult"])
    assert_snapshot(hurt, "wronged", "hurt")
    unrelated_apology = await r.turn("unrelated-apology", PROBES["unrelated_apology"])
    assert_snapshot(unrelated_apology, "wronged", "hurt")
    for kind, value in hurt.origin.items():
        assert unrelated_apology.origin[kind] == pytest.approx(
            value * 2 ** (-1 / POLICIES[kind][1]), abs=.001,
        )
    repaired = await r.turn("repair", TEXT["repair"])
    assert_snapshot(repaired, "wronged", "hurt")
    assert repaired.origin["wronged"] < hurt.origin["wronged"] - .08
    assert repaired.origin["hurt"] == pytest.approx(hurt.origin["hurt"], abs=.001)


async def test_reported_acknowledgement_cannot_supply_help_proof(make_replay):
    r = await make_replay()
    reported = await r.turn("reported-ack", PROBES["reported_ack"])
    assert_snapshot(reported)
    assert not (await r.stored(reported.context))["support"]
    direct = await r.turn("unsupported-deny", TEXT["deny"])
    assert_snapshot(direct)
    r.provider.replies[PARAPHRASE] = [appraisal("wronged", PARAPHRASE, refs=[reported.key])]
    semantic = await r.turn("unsupported-paraphrase", PARAPHRASE)
    await r.close_job(semantic)
    call, = [call for call in r.provider.calls if call["message"] == PARAPHRASE]
    assert call["status"] == "returned" and reported.key not in call["support_refs"]
    assert_snapshot(await r.turn("after-reported-ack", TEXT["finish"]))
    assert not (await r.stored(reported.context))["items"]


async def test_boundary_withdrawal_cannot_restore_old_shyness(make_replay):
    r = await make_replay(model=False)
    first = await r.turn("first", TEXT["first"])
    await r.seed_relationship(first.context)
    assert_snapshot(await r.turn("warm", TEXT["warm"]), "shyness")
    boundary = await r.turn("work-boundary", PROBES["work_boundary"])
    assert_snapshot(boundary)
    state = await r.stored(first.context)
    assert state.get("boundary") is True and not state["items"]
    assert_snapshot(await r.turn("insult", PROBES["direct_insult"]), "hurt")
    for probe in ("reported_release", "technical_release", "unrelated_release"):
        assert_snapshot(await r.turn(probe, PROBES[probe]), "hurt")
        assert (await r.stored(first.context)).get("boundary") is True
        assert_snapshot(await r.turn(f"{probe}-warm-still-blocked", TEXT["warm"]), "hurt")
    assert_snapshot(await r.turn("direct-withdrawal", PROBES["direct_release"]), "hurt")
    assert not (await r.stored(first.context)).get("boundary")
    assert_snapshot(await r.turn("neutral-after-withdrawal", TEXT["finish"]), "hurt")
    assert_snapshot(await r.turn("new-warm", TEXT["warm"]), "hurt", "shyness")


@pytest.mark.parametrize("dimension", ["conversation", "user"])
async def test_partial_staleness_duplicate_and_storage_scope(make_replay, dimension, monkeypatch):
    r = await make_replay(dimension=dimension)
    calibrate = r.app.store.calibrate_context_emotions
    callbacks = []

    async def capture(*args, **kwargs):
        outcome = await calibrate(*args, **kwargs)
        if outcome.accepted:
            callbacks.append((args, kwargs))
        return outcome

    monkeypatch.setattr(r.app.store, "calibrate_context_emotions", capture)
    first = await held_denial(r, body=MIXED, extra=[
        appraisal("hurt", HURT_PROBE),
    ])
    repair = await r.turn("repair", TEXT["repair"])
    assert_snapshot(repair)
    origin = first.event.message_obj.timestamp
    r.clock[0] = origin + 240
    r.provider.release(MIXED)
    await r.close_job(first)
    await r.assert_frozen(first)
    trace = await r.event_trace(first)
    first.evidence["writeback_trace"] = trace
    assert "context_cause_already_repaired" in trace["reason_codes"]
    assert "context_hurt" in trace["reason_codes"]
    (args, kwargs), = callbacks
    before = await r.app.store.context_emotion_record(first.context)
    duplicate = await calibrate(*args, **kwargs)
    assert not duplicate.accepted and duplicate.reason_code == "duplicate_event"
    assert await r.app.store.context_emotion_record(first.context) == before
    assert await r.event_trace(first) == trace
    first.evidence["duplicate_callback"] = duplicate.reason_code
    await r.app.on_message(first.event)
    assert first.event.get_extra("livingemotion:ingest") == "duplicate"
    after = await r.turn("after", TEXT["finish"])
    assert_snapshot(after, "hurt")
    assert len([c for c in r.provider.calls if c["message"] == MIXED]) == 1
    record = await r.app.store.context_emotion_record(first.context)
    assert record.kind == ("context_emotion" if dimension == "user" else "relationship")
    item, = (await r.stored(first.context))["items"]
    assert item["started_at"] == origin
    assert item["expires_at"] == origin + POLICIES["hurt"][2]
    assert item["intensity"] == pytest.approx(.54 * 2 ** (-241 / 1800), abs=.002)
    same_user = await r.turn("other-scene", TEXT["finish"], group="other-scene")
    assert account_person_key(same_user.context) == account_person_key(first.context)
    assert same_user.context.account_key != first.context.account_key
    assert_snapshot(same_user, *(("hurt",) if dimension == "user" else ()))
    assert_snapshot(await r.turn("other-person", TEXT["finish"], actor="b"))


async def test_unaddressed_group_broadcast_is_not_a_stimulus(make_replay):
    r = await make_replay()
    for name in ("help", "deny", "warm"):
        assert_snapshot(await r.turn(name, TEXT[name], group="broadcast", mention=False))
    assert not r.provider.calls


async def test_queue_preserves_two_distinct_candidates_and_merges_duplicates(make_replay):
    r = await make_replay()
    _, context, _ = await r.start("seed", "收到")
    await r.seed_relationship(context)
    first = await held_denial(r)
    r.provider.hold(HURT_PROBE)
    r.provider.hold(WARM_PROBE)
    r.provider.replies[HURT_PROBE] = [appraisal("hurt", HURT_PROBE)]
    r.provider.replies[WARM_PROBE] = [appraisal("shyness", WARM_PROBE)]
    await r.start("queued-hurt", HURT_PROBE)
    # A different transport ID alone is not new evidence.
    await r.start("duplicate-queued-hurt", HURT_PROBE)
    assert_snapshot(await r.turn("neutral-between", TEXT["continue"]))
    await r.start("queued-shyness", WARM_PROBE)
    assert_snapshot(await r.turn("neutral-after", TEXT["finish"]))
    await r.assert_pending(first, PARAPHRASE)
    assert not any(r.provider.started[text].is_set() for text in (HURT_PROBE, WARM_PROBE))

    r.provider.release(PARAPHRASE)
    await asyncio.wait_for(r.provider.started[HURT_PROBE].wait(), REPLAY_TIMEOUT)
    assert not r.provider.started[WARM_PROBE].is_set()
    assert r.provider.active == 1
    r.provider.release(HURT_PROBE)
    await asyncio.wait_for(r.provider.started[WARM_PROBE].wait(), REPLAY_TIMEOUT)
    assert r.provider.active == 1
    r.provider.release(WARM_PROBE)
    await asyncio.wait_for(asyncio.shield(
        r.app._refinement_tasks[first.key]["task"],
    ), REPLAY_TIMEOUT)
    assert r.provider.max_active == 1
    last = await r.turn("after-drain", TEXT["finish"])
    full = intensities((await r.stored(last.context))["items"])
    last.evidence["all_stored_kinds"] = full
    last.evidence["max_provider_concurrency"] = r.provider.max_active
    assert set(full) == {"wronged", "hurt", "shyness"}
    assert_snapshot(last, "wronged", "hurt")  # The native prompt carries only the top two.
    assert [c["message"] for c in r.provider.calls if c["message"] != TEXT["help"]] == [
        PARAPHRASE, HURT_PROBE, WARM_PROBE,
    ]
