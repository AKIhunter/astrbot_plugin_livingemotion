from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.contracts import ActorRole, Context, Event, SceneKind
from astrbot_plugin_livingemotion.storage import SQLiteStore


@pytest.fixture
def le_context():
    return Context("bot-1", "persona-1", "adapter-1", "platform-1",
                   SceneKind.PRIVATE, "chat-1", "human-1", route="verified:test:chat-1")


@pytest.fixture
def le_event(le_context):
    return Event("event-1", "test-producer", "message", le_context, ActorRole.HUMAN,
                 1_800_000_000.0, "source-1", actor_id="human-1", body="synthetic test body")


@pytest.fixture
async def le_store(tmp_path):
    store = SQLiteStore(tmp_path / "livingemotion.sqlite3", clock=lambda: 1_800_000_001.0)
    await store.open()
    yield store
    await store.close()


@pytest.fixture
def le_event_factory(le_event):
    def create(number, **changes):
        return replace(le_event, event_id=f"event-{number}", source_id=f"source-{number}",
                       **changes)
    return create
