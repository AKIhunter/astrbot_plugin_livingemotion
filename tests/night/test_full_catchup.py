"""Full unread migration regressions: synthetic archive, clock and transports."""

import json
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import ActorRole, ContentKind, Context, Event, EvidenceRef
from astrbot_plugin_livingemotion.services.catchup import FullCatchupService, transcript_parts
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.storage.catchup import CatchupArchive


CONTEXT = Context("bot", "persona", "adapter", "qq", "private", "human",
                  account_id="human", audience=("qq:bot", "qq:human"))


async def make_archive(tmp_path):
    store = SQLiteStore(tmp_path / "state.db", config=Config(), clock=lambda: 2000)
    await store.open()
    await store.register_context(CONTEXT)
    archive = CatchupArchive(store)
    await archive.open()
    return store, archive


async def append(archive, identifier, body="message", context=CONTEXT):
    event = Event(identifier, "astrbot", "message", context, ActorRole.HUMAN,
                  1000, identifier, actor_id=context.account_id, body=body)
    await archive.append(event, await archive.store.get_generation(context))
    return event


async def allowed(context, generation, revision):
    return True


async def no_send(*args):
    raise AssertionError("read-only catchup must not send")


def service(archive, reader, *, reply_enabled=False, sender=no_send):
    async def reply(*args):
        return "historical answer"
    return FullCatchupService(archive, read_model=reader, reply_model=reply,
                             send=sender, guard=allowed, reply_enabled=reply_enabled)


def test_long_message_tail_and_unicode_have_complete_fragments():
    body = "前" * 8000 + "TAIL-MUST-BE-READ"
    parts = transcript_parts([{"seq": 1, "source_id": "old", "body": body}], byte_budget=512)
    assert len(parts) > 10
    assert all(len(part.encode()) <= 512 for part in parts)
    recovered = "".join(part.split("]\n", 3)[-1] for part in parts)
    assert recovered == body


@pytest.mark.asyncio
async def test_1001_unread_rows_all_read_frozen_upper_and_late_arrival(tmp_path):
    store, archive = await make_archive(tmp_path)
    try:
        for index in range(1001):
            await append(archive, str(index))
        await append(archive, "trigger")
        calls = 0

        async def reader(context, text, key, include_items):
            nonlocal calls
            calls += 1
            if calls == 1:
                await append(archive, "late-arrival")
            return json.dumps({"summary": "完整读过", "items": []})
        result = await service(archive, reader).prepare(
            CONTEXT, exclude_source_id="trigger", wake_key="wake-1", revision="rev-1")
        assert result.read_count == 1001 and not result.has_more
        generation = await store.get_generation(CONTEXT)
        batch = await archive.begin(CONTEXT, generation, exclude_source_id="",
                                    wake_key="wake-2", revision="rev-1")
        remaining = await archive.rows(CONTEXT, batch)
        assert [row["source_id"] for row in remaining] == ["trigger", "late-arrival"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_reading_failure_and_restart_preserve_upper_and_reuse_successful_chunks(tmp_path):
    store, archive = await make_archive(tmp_path)
    for index in range(100):
        await append(archive, str(index))
    await append(archive, "trigger")
    count = 0

    async def failing(context, text, key, include_items):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("synthetic reading failure")
        return {"summary": "cached chunk", "items": []}
    with pytest.raises(ValueError, match="synthetic"):
        await service(archive, failing).prepare(
            CONTEXT, exclude_source_id="trigger", wake_key="wake-1", revision="rev")
    batch = await archive.begin(CONTEXT, 0, exclude_source_id="", wake_key="wake-2", revision="rev")
    upper = batch["upper_seq"]
    await store.close()
    store, archive = await make_archive(tmp_path)
    try:
        await append(archive, "later")
        new_batch = await archive.begin(CONTEXT, 0, exclude_source_id="", wake_key="wake-3",
                                        revision="rev")
        assert new_batch["upper_seq"] == upper

        async def succeeds(*args):
            return {"summary": "read", "items": []}
        result = await service(archive, succeeds).prepare(
            CONTEXT, exclude_source_id="", wake_key="wake-3", revision="rev")
        assert result.read_count == 100
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_unknown_historical_send_never_replays_or_marks_read(tmp_path):
    store, archive = await make_archive(tmp_path)
    sends = 0
    try:
        await append(archive, "old", "question?")
        await append(archive, "trigger")

        async def reader(*args):
            return {"summary": "old question", "items": [
                {"source_id": "old", "targets_me": True, "answered": False, "expired": False}]}

        async def sender(*args):
            nonlocal sends
            sends += 1
            return "unknown"
        flow = service(archive, reader, reply_enabled=True, sender=sender)
        first = await flow.prepare(CONTEXT, exclude_source_id="trigger",
                                   wake_key="wake-1", revision="rev")
        assert first.blocked and sends == 1
        second = await flow.prepare(CONTEXT, exclude_source_id="trigger",
                                    wake_key="wake-2", revision="rev")
        assert second.blocked and sends == 1
        batch = await archive.begin(CONTEXT, 0, exclude_source_id="", wake_key="wake-3",
                                    revision="rev")
        assert [row["source_id"] for row in await archive.rows(CONTEXT, batch)] == ["old"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_generation_changed_during_read_cannot_commit(tmp_path):
    store, archive = await make_archive(tmp_path)
    try:
        await append(archive, "old")
        await append(archive, "trigger")

        async def reader(*args):
            await store.clear_scope(CONTEXT, 0, actor_id="test", reason_code="delete")
            return {"summary": "late summary", "items": []}

        async def guard(context, generation, revision):
            return await store.get_generation(context) == generation
        flow = service(archive, reader)
        flow.guard = guard
        result = await flow.prepare(CONTEXT, exclude_source_id="trigger",
                                    wake_key="wake", revision="rev")
        assert result.reason == "context_changed" and result.read_count == 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_same_platform_number_different_scope_not_read(tmp_path):
    store, archive = await make_archive(tmp_path)
    try:
        group = replace(CONTEXT, scene_kind="group", scene_id="group",
                        audience=("group:synthetic",))
        await store.register_context(group)
        await append(archive, "private")
        await append(archive, "group", context=group)

        async def reader(context, text, key, include):
            assert "source=private" not in text
            return {"summary": "group only", "items": []}
        result = await service(archive, reader).prepare(
            group, exclude_source_id="", wake_key="wake", revision="rev")
        assert result.read_count == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_history_reply_limit_is_shared_across_batches_and_restart(tmp_path):
    store, archive = await make_archive(tmp_path)
    generated = []

    async def reader(context, text, key, include):
        import re
        return {"summary": "questions", "items": [
            {"source_id": identifier, "targets_me": True, "answered": False, "expired": False}
            for identifier in re.findall(r"source=([^\]\n]+)", text)
        ]}

    async def reply(context, body, key):
        generated.append(key)
        return "answer"

    async def confirmed(*args):
        return "confirmed"

    def flow():
        value = service(archive, reader, reply_enabled=True, sender=confirmed)
        value.reply_model = reply
        return value

    try:
        await append(archive, "first")
        await append(archive, "trigger-1")
        assert (await flow().prepare(
            CONTEXT, exclude_source_id="trigger-1", wake_key="wake", revision="rev",
        )).read_count == 1
        await archive.mark_consumed(CONTEXT, 0, "trigger-1")
        for identifier in ("second", "third", "fourth", "trigger-2"):
            await append(archive, identifier)
        result = await flow().prepare(
            CONTEXT, exclude_source_id="trigger-2", wake_key="wake", revision="rev",
        )
        assert len(generated) == 3 and result.has_more
        await store.close()
        store, archive = await make_archive(tmp_path)
        retry = await flow().prepare(
            CONTEXT, exclude_source_id="trigger-2", wake_key="wake", revision="rev",
        )
        assert retry.has_more and len(generated) == 3
        next_wake = await flow().prepare(
            CONTEXT, exclude_source_id="trigger-2", wake_key="new-wake", revision="rev",
        )
        assert next_wake.read_count == 1 and len(generated) == 4
    finally:
        await store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["identity", "expired", "derived"])
async def test_changed_identity_and_expired_or_derived_history_remain_unread(tmp_path, invalid):
    store, archive = await make_archive(tmp_path)
    try:
        context = replace(CONTEXT, identity_revision="old") if invalid == "identity" else CONTEXT
        evidence = () if invalid == "identity" else (EvidenceRef(
            "synthetic", "reference", context, context.account_id, context.bot_id,
            ContentKind.FACT if invalid == "derived" else ContentKind.INTERACTION,
            1000, expires_at=1001 if invalid == "expired" else 3000,
        ),)
        event = Event("old", "astrbot", "message", context, ActorRole.HUMAN,
                      1000, "old", actor_id=context.account_id, body="private", evidence=evidence)
        await archive.append(event, 0)

        async def forbidden(*args):
            raise AssertionError("invalid history must not reach a model")
        result = await service(archive, forbidden).prepare(
            CONTEXT, exclude_source_id="", wake_key="wake", revision="rev",
        )
        assert result.read_count == 0
        batch = await archive.begin(CONTEXT, 0, exclude_source_id="", wake_key="wake", revision="rev")
        assert len(await archive.rows(CONTEXT, batch)) == 1
    finally:
        await store.close()
