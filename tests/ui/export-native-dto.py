"""Generate UI-only samples from the real Console with temporary synthetic storage."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BotAffect, Context, Event, NightState, SceneKind, StateWrite, to_dict
from astrbot_plugin_livingemotion.domain.emotion import EmotionPolicy
from astrbot_plugin_livingemotion.runtime.console import Console
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.storage.console_data import remember_qq_nickname


class FixtureConsole(Console):
    def __init__(self, store, contexts):
        self.store, self.instance_id = store, "local"
        self.config = Config(mode="observe_only", timezone="Asia/Shanghai", persona_shared_state=True)
        self.revision = "config-1"
        self.closed = False
        self._contexts = {c.account_key: c for c in contexts}
        self._config_fault = self._task_fault = ""
        self.memory = SimpleNamespace(capabilities=lambda: SimpleNamespace(
            recall=False, append_experience=False, reason_codes=("embedding_not_configured",)))
        self.bridge = SimpleNamespace(conflicts=lambda _: False, source=lambda _: None)
        self.behavior = SimpleNamespace(preview_behavior=self.preview)
        self.emotion_policy = EmotionPolicy()

    async def refresh_config(self):
        pass

    async def preview(self, _):
        return SimpleNamespace(eligible=False, reason_codes=("observe_only",))

    def effective_mode(self, _):
        return "observe_only"

    async def current_relationship(self, _):
        return None

    async def night_snapshot(self, _):
        return NightState(energy=74.1)

    async def availability(self, _):
        return SimpleNamespace(available=True, block_chat=False, reason_codes=())

    async def model_binding(self, _):
        raise ValueError("No synthetic model configured")


async def main():
    with tempfile.TemporaryDirectory(prefix="livingemotion-ui-") as directory:
        store = SQLiteStore(Path(directory) / "fixture.sqlite3", clock=lambda: 1_800_000_001.0)
        await store.open()
        try:
            context = Context("synthetic-bot", "fixture-persona", "synthetic-adapter",
                              "qq", SceneKind.PRIVATE, "synthetic-chat", "10001")
            contexts = [replace(context, account_id=str(10001 + i)) for i in range(23)]
            contexts.append(replace(context, platform="bilibili", scene_kind=SceneKind.GROUP,
                                    scene_id="synthetic-group"))
            for source in contexts:
                await store.register_context(source)
            owner = await store.initialize_state_mode(context, shared=True)
            # Real writes into temporary storage; numeric synthetic examples only.
            for index in range(13):
                at = 1_800_000_001.0 - 86400 + index * 7200
                store.clock = lambda at=at: at
                old = await store.get_state(context, "bot")
                affect = BotAffect(pleasure=(index % 5 - 2) * .35,
                    arousal=.2 + index % 4 * .2, stress=index % 3 * .2,
                    social_need=.3 + index % 4 * .15, updated_at=at)
                result = await store.write_states(context, 0, (
                    StateWrite("bot", to_dict(affect),
                        expected_version=old.version if old else 0, owner=owner),))
                assert result.accepted
            store.clock = lambda: 1_800_000_001.0
            message = Event("fixture-relationship", "synthetic", "message", context, "human",
                            1_800_000_000.0, "synthetic-relationship-source",
                            actor_id=context.account_id, body="我和@10002是朋友")
            assert (await store.commit_event(message, 0)).accepted
            await remember_qq_nickname(store, context, "小雨（合成QQ名字）", 0,
                                       occurred_at=1_800_000_000.0)
            app = FixtureConsole(store, contexts)
            selection = {"persona_id": context.persona_id, "view_scope": "global"}
            options = await app.console_settings_options()
            options["personas"] = [{"value": context.persona_id, "label": "真实 DTO · 合成人格"}]
            options["chat_providers"] = [{"value": "fixture-chat", "label": "合成聊天模型"}]
            options["embedding_providers"] = [{"value": "fixture-embedding", "label": "合成向量模型"}]
            state = await app.console_state(**selection)
            state["config"] = app.config_dto(options)
            samples = {
                "config": state["config"], "state": state, "options": options,
                "scopes": await app.console_scopes(),
                "relationships": await app.console_relationships(**selection),
                "energy": await app.console_energy(**selection),
            }
            sources = ("config.py", "contracts.py", "runtime/console.py", "runtime/config_help.py", "storage/schema.py",
                       "storage/sqlite.py", "storage/state_scope.py", "storage/console_data.py",
                       "domain/relationship_inference.py", "domain/proactivity.py",
                       "storage/proactivity.py")
            provenance = {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "field_count": len(state["config"]["fields"]),
                "scope": "real Console DTO / synthetic host / temporary database",
                "sources_sha256": {
                    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                    for name in sources
                },
            }
            target = Path(__file__).with_name("native-dto.mjs")
            target.write_text("// Generated from real Console; synthetic host, no model or sends.\n"
                              "export const nativeDTO = " +
                              json.dumps(samples, ensure_ascii=False, indent=2) + ";\n"
                              "export const nativeDTOEvidence = " +
                              json.dumps(provenance, ensure_ascii=False, indent=2) + ";\n")
            print(f"Real Console DTO generated: {len(state['config']['fields'])} native fields")
        finally:
            await store.close()


if __name__ == "__main__":
    asyncio.run(main())
