import asyncio
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

from astrbot_plugin_livingemotion.contracts import ContentKind, Context, EvidenceRef
from astrbot_plugin_livingemotion.ports.memory import Material, MemoryRequest


def context(**changes):
    value = Context(
        "host:qq:bot",
        "native",
        "qq-instance",
        "qq",
        "private",
        "alice",
        "alice",
        "persona-r1",
        "local-r1",
        ("alice", "bot"),
        "qq-instance:FriendMessage:alice",
    )
    return replace(value, **changes)


def request(ctx=None, **changes):
    return replace(MemoryRequest("request-1", "diary", ctx or context(), "tea"), **changes)


def own(ctx=None, **changes):
    ctx = ctx or context()
    ref = EvidenceRef(
        "livingemotion",
        "message-1",
        ctx,
        "qq:alice",
        ctx.bot_id,
        ContentKind.FACT,
        100.0,
        200.0,
        source_ids=("message-1",),
    )
    return Material(replace(ref, **changes), "explicit tea promise")


class Event:
    """A unit-test fixture, never constructed or sent by the runtime adapter."""

    def __init__(self, ctx=None, synthetic=False):
        self.context = ctx or context()
        self.unified_msg_origin = self.context.route
        self.synthetic = synthetic

    def get_sender_id(self):
        return self.context.account_id

    def get_self_id(self):
        return "bot"

    def get_extra(self, key):
        return self.synthetic if key == "cron" else None


class Provider:
    def __init__(self):
        self.revision = 7
        self.bound = True
        self.calls = 0
        self.validations = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()
        self.allow = True
        self.rows = None
        self.return_identity = None
        self.change_during_validation = False

    @property
    def initializer(self):
        raise AssertionError("private access forbidden")

    async def resolve_identity_context(self, event, persona_id=""):
        ctx = event.context
        value = {
            "platform": ctx.platform,
            "account_id": ctx.account_id,
            "source_account": ctx.platform + ":" + ctx.account_id,
            "one_id": "human" if self.bound else "person:qq:alice",
            "person_id": "human" if self.bound else "person:qq:alice",
            "identity_revision": self.revision,
            "is_bound": self.bound,
            "owner_account": "qq:bot",
            "owner_one_id": "bot-entity",
            "scene_kind": ctx.scene_kind.value,
            "scene_id": ctx.scene_id,
            "audience": "self_private",
            "origin_session_id": ctx.route,
            "persona_id": persona_id,
            "bound_accounts": [
                {"platform": "qq", "account_id": "alice"},
                {"platform": "bili", "account_id": "linked"},
            ]
            if self.bound
            else [],
        }
        return self.return_identity or value

    async def search_memories_for_event(self, query, event, *, persona_id="", k=4):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        if self.rows is not None:
            return deepcopy(self.rows)
        ctx = event.context
        return [
            SimpleNamespace(
                doc_id=1,
                content="external tea summary",
                metadata={
                    "source_account": "qq:alice",
                    "owner_account": "qq:bot",
                    "subject_accounts": ["qq:alice"],
                    "source_session_id": ctx.route,
                    "persona_id": persona_id,
                    "audience": "self_private",
                    "sensitivity": 2,
                    "_identity_revision": self.revision,
                    "create_time": 100.0,
                    "expires_at": 200.0,
                    "source_window": {"session_id": ctx.route, "start_index": 1, "end_index": 3},
                },
            )
        ]

    async def validate_identity_results(self, results):
        self.validations += 1
        if self.change_during_validation:
            self.revision += 1
        return results if self.allow else []
