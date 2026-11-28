"""Human-labelled cases with scripted Provider output; no real semantic accuracy claim."""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import ActorRole, Relationship
from astrbot_plugin_livingemotion.domain.emotion_shadow import SHADOW_SYSTEM, parse_shadow
from astrbot_plugin_livingemotion.runtime import emotion_shadow as observer
from astrbot_plugin_livingemotion.storage.console_data import write_relationship_override
from test_application import Message
from test_context_emotions import group_ingest, ingest
from test_context_semantics import appraisal, no_network, semantic_app, turn


HELP = "路由超时那回，多亏你出手才解决。"
DENIAL = "你从没帮我解决路由超时。"
SHORT = "好？"
BLAME = "这故障不是你造成的，可他们问起来我还是会把账算给你。"
BLAME_QUESTION = "你知道故障不是我造成的，可还是要让我替你背责任，对吗？"
BLAME_PARAPHRASE = "这次配置没经我改，你心里清楚，却还准备把责任算到我头上，是吧？"
HARM = "你就是个废物。"
REPAIR = "刚才拿你整个人开刀那段，是我没分寸；那话不作数。"
BOUNDARY = "以后咱俩别往那种关系上聊了。"
AGENDA = "接下来先把讨论范围限制在证书续期这一项。"
WRONGED = "wronged:increase:devalued_contribution"
BLAMED = "wronged:increase:admitted_unfair_blame"
REPAIRED = "hurt:decrease:direct_devaluation"


def install_script(app, provider, monkeypatch):
    calls, differences = [], []
    monkeypatch.setattr(observer, "logger",
                        SimpleNamespace(info=lambda _fmt, *args: differences.append(args)))

    def install(respond, *, before_result=None):
        async def generate(system, data, output_tokens, timeout):
            shadow, payload = system == SHADOW_SYSTEM, json.loads(data)
            calls.append((shadow, payload, output_tokens))
            rows, boundary = respond(payload)
            if shadow:
                if before_result:
                    await before_result()
                return {"context_appraisals": rows, "boundary": boundary}
            legacy_rows = []
            for row in rows:
                legacy = {key: value for key, value in row.items() if key != "prior"}
                if "prior" in row:
                    legacy["context_refs"] = [row["prior"]["ref"]]
                legacy_rows.append(legacy)
            return {"context_appraisals": legacy_rows}
        monkeypatch.setattr(provider, "generate", generate)
    return install, calls, differences


async def setup(app, native, clock, previous, *, enabled=True):
    native["emotion_model_enabled"] = False
    await app.refresh_config()
    keys = {}
    for i, (body, account) in enumerate(previous):
        clock[0] += 1
        msg, _, _ = await ingest(app, f"previous-{i}", body, account=account)
        keys[body] = msg.extra["livingemotion:event_key"]
    native.update(emotion_model_enabled=True, context_emotion_shadow_enabled=enabled)
    await app.refresh_config()
    clock[0] += 1
    return keys


def suggestion(kind, body, keys=None, *, prior=None, basis=None, action="increase", **fields):
    row = appraisal(kind, body, action=action, **fields)
    if prior is not None:
        row["prior"] = {"ref": keys[prior], "evidence": prior, "relation": basis}
    return row


@pytest.mark.asyncio
@pytest.mark.parametrize("prior,body,kind,rel,action,expected", [
    pytest.param(HELP, DENIAL, "wronged", "confirmed_same_contribution", "increase", WRONGED,
                 id="paraphrased-help"),
    pytest.param(BLAME, SHORT, "wronged", "supports_current_reading", "increase", BLAMED,
                 id="contextual-short-question"),
    pytest.param(HARM, REPAIR, "hurt", "repairs_active_incident", "decrease", REPAIRED,
                 id="paraphrased-repair"),
    pytest.param(None, BOUNDARY, None, None, None, "boundary:set", id="implicit-boundary"),
])
async def test_fixed_pipeline_blind_spots(tmp_path, monkeypatch, prior, body, kind, rel, action, expected):
    app, _, native, clock, _, provider = await semantic_app(tmp_path)
    try:
        keys = await setup(app, native, clock, [(prior, "human")] if prior else [])
        install, calls, differences = install_script(app, provider, monkeypatch)
        row = suggestion(kind, body, keys, prior=prior, basis=rel, action=action) if kind else None
        if rel == "confirmed_same_contribution":
            row["cause_code"] = "devalued_contribution"
        install(lambda _: ([row] if row else [], None if kind else {"evidence": body}))
        message, _, _, expression = await turn(app, "implicit", body)
        assert await app._context_shadow_task == ("scored", (expected,))
        event_key, baseline_status, baseline, candidate = differences.pop()
        assert event_key == message.extra["livingemotion:event_key"]
        assert baseline == "-" and candidate == expected
        assert baseline_status == ("context_neutral" if body == SHORT else
                                   "context_no_stimulus" if body == BOUNDARY else
                                   "context_appraisals_invalid")
        assert [shadow for shadow, _, _ in calls].count(False) == int(body != SHORT)
        _, payload, tokens = calls[-1]
        assert calls[-1][0] and tokens <= 512
        if prior is not None:
            assert keys[prior] in {r["ref"] for r in payload["recent_dialogue"]}
        if body == DENIAL:
            assert not calls[0][1]["context_support_refs"]  # The old wire gate denies the same receipt.
        if body == REPAIR:
            assert expression["bot"]["context_emotions"][0]["kind"] == "hurt"
        else:
            assert not expression["bot"].get("context_emotions")
        assert all(source not in str((event_key, baseline_status, baseline, candidate))
                   for source in (body, prior) if source)
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("question,body,fixture_answer,short,status", [
    pytest.param(BLAME_QUESTION, "嗯。", "confirm", True, "scored", id="archived-miss"),
    pytest.param(BLAME_PARAPHRASE, "行。", "confirm", True, "scored", id="paraphrased-confirmation"),
    pytest.param(BLAME_PARAPHRASE, "行？", "misread_question", True, "model_output_invalid",
                 id="bot-question-cannot-prove-a-human-admission"),
    pytest.param("排查完备份以后，咱们明天再安排上线，对吗？", "嗯。",
                 None, True, "scored", id="same-answer-technical-question"),
    pytest.param("我看到故障单了，一会儿会再看日志。", "嗯。",
                 None, True, "scored", id="same-answer-acknowledgment"),
    pytest.param(BLAME_QUESTION, "嗯？", None, True, "scored", id="question-is-not-agreement"),
    pytest.param(BLAME_QUESTION, "不是。", None, False, "scored", id="denial-is-not-agreement"),
    pytest.param("明天上线吗？还有，明明不是我改的，你也要让我担责吗？", "嗯。",
                 None, True, "scored", id="multiple-questions"),
    pytest.param(BLAME_QUESTION, "嗯。", "wrong_ref", True, "model_output_invalid",
                 id="candidate-must-reference-a-sent-question"),
])
async def test_short_confirmation_and_controls(tmp_path, monkeypatch, question, body, fixture_answer,
                                               short, status):
    """Exercise the real wire and checks with fixed answers, not model comprehension."""
    app, host, native, clock, context, provider = await semantic_app(tmp_path)
    try:
        await setup(app, native, clock, [])
        _, event = await app.bridge.normalize(Message("bot-question", question), clock[0])
        event = replace(event, actor_role=ActorRole.BOT, actor_id=context.bot_id,
                        producer="livingemotion.host", event_type="bot_reply_submitted")
        assert (await app.store.commit_event(event, 0)).accepted
        clock[0] += 1
        install, calls, differences = install_script(app, provider, monkeypatch)

        def respond(payload):
            if "short_turn" not in payload or fixture_answer is None:
                return [], None
            ref = "not-sent" if fixture_answer == "wrong_ref" else event.idempotency_key
            return [suggestion("wronged", body, {question: ref}, prior=question,
                               basis="supports_current_reading")], None

        install(respond)
        message, _, _, expression = await turn(app, "short-answer", body)
        expected = (BLAMED,) if fixture_answer == "confirm" else ()
        assert await app._context_shadow_task == (status, expected)
        [payload] = [p for shadow, p, _ in calls if shadow]
        assert payload["message"] == body and payload["short_turn"] is short
        assert any((r["role"], r["text"], r["ref"]) == ("bot", question, event.idempotency_key)
                   for r in payload["recent_dialogue"])
        if expected:
            assert differences == [(message.extra["livingemotion:event_key"], "context_neutral",
                                    "-", BLAMED)]
        else:
            assert not differences
        assert not expression["bot"].get("context_emotions") and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("prior,account,body,response,status,dispatch", [
    pytest.param("这个变量叫 timeout。", "human", SHORT, "none", "no_context", False,
                 id="same-short-question-technical"),
    pytest.param(HELP, "other", DENIAL, "proof", "model_output_invalid", True,
                 id="same-denial-wrong-person"),
    pytest.param("谢谢你帮我修好打印机。", "human", DENIAL, "proof", "model_output_invalid", True,
                 id="same-denial-wrong-task"),
    pytest.param("谢谢你帮我修好打印机。", "human", DENIAL, "mislabeled", "model_output_invalid",
                 True, id="denial-cannot-bypass-proof-as-blame"),
    pytest.param(f"同事说：『{HELP}』", "human", DENIAL, "proof", "model_output_invalid", True,
                 id="help-quote-is-not-the-speakers-proof"),
    pytest.param("多亏你明天愿意接手路由超时。", "human", DENIAL, "proof", "model_output_invalid", True,
                 id="intent-is-not-completed-help"),
    pytest.param(HELP, "human", '同事说：「你从没帮我解决路由超时。」', "proof",
                 "model_output_invalid", True, id="quoted-current-denial"),
    pytest.param("这次路由还得复核。", "human", "这里用的是秒，你填成毫秒了。", "none",
                 "scored", True, id="reasonable-correction"),
    pytest.param("之前是你帮我排查故障。", "human", "是我没分寸；那话不作数。", "repair",
                 "model_output_invalid", True, id="repair-without-active-incident"),
    pytest.param("接下来只聊工作，保持专业。", "human", "我想离你再近一点。", "warm",
                 "model_output_invalid", True, id="boundary-blocks-warmer-candidate"),
    pytest.param("今晚要把上线文档敲完。", "human", AGENDA, "agenda", "model_output_invalid", True,
                 id="technical-agenda-does-not-set-boundary"),
])
async def test_paired_controls(tmp_path, monkeypatch, prior, account, body, response, status, dispatch):
    app, _, native, clock, context, provider = await semantic_app(tmp_path)
    try:
        if response == "warm":
            await write_relationship_override(app.store, context, expected_version=1,
                actor_id="offline-test", reason="high relationship for boundary test", score=60)
        keys = await setup(app, native, clock, [(prior, account)])
        install, calls, differences = install_script(app, provider, monkeypatch)
        row = None
        if response == "proof":
            row = suggestion("wronged", body, keys, prior=prior, basis="confirmed_same_contribution")
            row["cause_code"] = "devalued_contribution"
        elif response == "mislabeled":
            row = suggestion("wronged", body)
        elif response == "repair":
            row = suggestion("hurt", body, keys, prior=prior, basis="repairs_active_incident", action="decrease")
        elif response == "warm":
            row = suggestion("shyness", body)
        install(lambda _: ([row] if row else [], {"evidence": body} if response == "agenda" else None))
        await turn(app, "control", body)
        assert await app._context_shadow_task == (status, ())
        assert sum(shadow for shadow, _, _ in calls) == dispatch
        if account != "human":
            assert prior not in str(calls)
        assert not differences
    finally:
        await app.terminate()


@pytest.mark.parametrize("body,kind,span,expected", [
    pytest.param(DENIAL, "wronged", "解决路由超时", "", id="cropped-denial-is-not-blame"),
    pytest.param(DENIAL, "hurt", DENIAL, "", id="denial-is-not-personal-devaluation"),
    pytest.param(AGENDA, None, "证书续期这一项", "", id="cropped-agenda-is-not-relationship"),
    pytest.param(DENIAL.rstrip("。") + "，" + BLAME, "wronged", BLAME, BLAMED,
                 id="independent-implicit-blame-in-same-sentence"),
    pytest.param(DENIAL.rstrip("。") + "，" + HARM, "hurt", HARM, "hurt:increase:direct_devaluation",
                 id="independent-insult-in-same-sentence"),
    pytest.param(AGENDA.rstrip("。") + "，" + BOUNDARY, None, BOUNDARY, "boundary:set",
                 id="independent-implicit-boundary-in-same-sentence"),
])
def test_veto_uses_the_selected_clause(le_event, body, kind, span, expected):
    reply = {"context_appraisals": [suggestion(kind, span)] if kind else [],
             "boundary": None if kind else {"evidence": span}}
    payload = {"recent_dialogue": [], "active_incidents": [], "short_turn": False,
               "relationship_boundary": ""}
    assert parse_shadow(reply, replace(le_event, body=body), Relationship(), {}, payload) == (
        ("scored", (expected,)) if expected else ("model_output_invalid", ()))


@pytest.mark.asyncio
async def test_user_dimension_does_not_borrow_private_proof_in_group(tmp_path, monkeypatch):
    app, _, native, clock, _, provider = await semantic_app(tmp_path, context_emotions_dimension="user")
    try:
        keys = await setup(app, native, clock, [(HELP, "human")])
        install, calls, differences = install_script(app, provider, monkeypatch)
        row = suggestion("wronged", DENIAL, keys, prior=HELP, basis="confirmed_same_contribution")
        row["cause_code"] = "devalued_contribution"
        install(lambda _: ([row], None))
        await group_ingest(app, "ingroup", DENIAL, "12345", "human")
        assert await app._context_shadow_task == ("model_output_invalid", ())
        assert len(calls) == 2 and all(HELP not in str(payload) for _, payload, _ in calls)
        assert not differences
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_matching_applied_local_result_is_not_logged(tmp_path, monkeypatch):
    app, _, native, clock, _, provider = await semantic_app(tmp_path)
    try:
        await setup(app, native, clock, [])
        install, calls, differences = install_script(app, provider, monkeypatch)
        install(lambda _: ([suggestion("hurt", HARM)], None))
        _, _, _, expression = await turn(app, "same", HARM)
        assert expression["bot"]["context_emotions"][0]["kind"] == "hurt"
        assert await app._context_shadow_task == ("scored", ("hurt:increase:direct_devaluation",))
        assert len(calls) == 2 and not differences
    finally:
        await app.terminate()


async def database_snapshot(app):
    tables = ("events", "states", "owner_states", "event_traces",
              "relationship_ledger", "quota_reservations", "runtime_meta")
    return await app.store._run(lambda db: {
        table: [tuple(r) for r in db.execute("SELECT * FROM " + table)] for table in tables
    })


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension,body", [("conversation", SHORT), ("user", "收到？")])
async def test_pending_observer_does_not_join_reply_or_modify_sqlite(tmp_path, monkeypatch, dimension, body):
    app, host, native, clock, _, provider = await semantic_app(
        tmp_path, context_emotions_dimension=dimension)
    try:
        keys = await setup(app, native, clock, [(BLAME, "human")])
        install, calls, differences = install_script(app, provider, monkeypatch)
        started, release = asyncio.Event(), asyncio.Event()

        async def pause():
            started.set()
            await release.wait()

        install(lambda _: ([suggestion("wronged", body, keys, prior=BLAME,
                                      basis="supports_current_reading")], None), before_result=pause)
        reply = asyncio.create_task(turn(app, "nonblocking", body))
        await asyncio.wait_for(started.wait(), 2)
        msg, _, _, expression = await asyncio.wait_for(reply, 0.5)
        assert not expression["bot"].get("context_emotions")
        assert msg.extra["livingemotion:event_key"] not in getattr(app, "_refinement_tasks", {})
        assert not app._context_shadow_task.done()
        before = await database_snapshot(app)
        release.set()
        assert await app._context_shadow_task == ("scored", (BLAMED,))
        assert before == await database_snapshot(app)
        assert len(calls) == len(differences) == 1 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_timeout_charges_only_one_shadow_attempt_and_never_retries(tmp_path, monkeypatch):
    app, _, native, clock, _, provider = await semantic_app(tmp_path)
    try:
        monkeypatch.setattr(observer, "DAILY_LIMIT", 1)
        await setup(app, native, clock, [(BLAME, "human")])
        install, calls, differences = install_script(app, provider, monkeypatch)

        async def timeout():
            raise asyncio.TimeoutError

        install(lambda _: ([], None), before_result=timeout)
        await turn(app, "timeout", SHORT)
        assert await app._context_shadow_task == ("task_timeout", ())
        clock[0] += 1
        await turn(app, "budget", SHORT)
        assert await app._context_shadow_task == ("daily_limit", ())
        assert len(calls) == 1 and calls[0][0] and not differences
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_disable_cancels_inflight_suggestion(tmp_path, monkeypatch):
    app, _, native, clock, _, provider = await semantic_app(tmp_path)
    try:
        keys = await setup(app, native, clock, [(BLAME, "human")])
        install, calls, differences = install_script(app, provider, monkeypatch)
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def pending():
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        install(lambda _: ([suggestion("wronged", SHORT, keys, prior=BLAME,
                                      basis="supports_current_reading")], None), before_result=pending)
        await turn(app, "cancel-shadow", SHORT)
        await asyncio.wait_for(started.wait(), 2)
        task = app._context_shadow_task
        native["context_emotion_shadow_enabled"] = False
        await app.refresh_config()
        assert cancelled.is_set() and task.cancelled() and not differences
        assert app._context_shadow_task is None and len(calls) == 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_opt_in_scope_and_six_technical_turns(tmp_path, monkeypatch):
    app, _, native, clock, _, provider = await semantic_app(tmp_path)
    try:
        await setup(app, native, clock, [(BLAME, "human")], enabled=False)
        install, calls, _ = install_script(app, provider, monkeypatch)
        install(lambda _: ([], None))
        await turn(app, "off", SHORT)
        assert getattr(app, "_context_shadow_task", None) is None and not calls
        native["context_emotion_shadow_enabled"] = True
        await app.refresh_config()
        clock[0] += 1
        await ingest(app, "unaddressed", DENIAL, group="12345")
        for index, body in enumerate((
            "接下来是普通技术讨论。", "把第二项列出来。", "这里使用默认端口。",
            "这个变量叫 timeout。", "我记下这个参数了。", "继续下一项。",
        )):
            clock[0] += 10
            await turn(app, f"technical-{index}", body)
        assert getattr(app, "_context_shadow_task", None) is None and not calls
    finally:
        await app.terminate()
