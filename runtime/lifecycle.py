"""Host-independent lifetime. One plugin instance owns its store and workers."""

import asyncio
from pathlib import Path

from ..config import Config
from ..storage import SQLiteStore
from .background import BackgroundRuntime


class Lifecycle:
    def __init__(self, data_dir: Path, config: Config):
        self.data_dir = Path(data_dir)
        self.config = config
        self.store: SQLiteStore | None = None
        self.runtime: BackgroundRuntime | None = None
        self.api = None
        self.instance_id: str | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        # Local import keeps the API/background runtime dependency acyclic.
        from ..api import LivingEmotionAPI

        async with self._lock:
            if self.store is not None:
                return
            store = SQLiteStore(self.data_dir / "livingemotion.sqlite3", config=self.config)
            runtime = BackgroundRuntime(store, self.config)
            try:
                await store.open()
                self.instance_id = await store.get_instance_id()
                await store.recover_inflight()
                await store.cleanup()
                await runtime.start()
                self.store, self.runtime = store, runtime
                self.api = LivingEmotionAPI(store, self.config, runtime,
                                            instance_id=self.instance_id)
            except BaseException:
                await runtime.stop()
                await store.close()
                raise

    async def terminate(self) -> None:
        async with self._lock:
            if self.api is not None:
                self.api.stop_accepting()
            try:
                if self.runtime is not None:
                    await self.runtime.stop()
            finally:
                if self.store is not None:
                    await self.store.close()
                self.store = None
                self.runtime = None
