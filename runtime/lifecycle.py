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
        # 承诺到期扫描：独立于模型运行时，不占 worker 也不受其并发限制。
        self._promise_task: asyncio.Task | None = None
        self._promise_hook = None

    def attach_promise_runner(self, runner) -> None:
        """由应用层注入真正能发送的实现；没有它就只扫描不投递。"""
        self._promise_hook = runner
        if self._promise_task is None and self.store is not None:
            self._promise_task = asyncio.create_task(
                self._promise_loop(), name="livingemotion-promise-tick")

    async def _promise_loop(self) -> None:
        interval = max(15, int(getattr(self.config, "promise_tick_seconds", 60) or 60))
        while True:
            try:
                await asyncio.sleep(interval)
                if not bool(getattr(self.config, "promise_enabled", True)):
                    continue
                if self._promise_hook is not None:
                    await self._promise_hook()
            except asyncio.CancelledError:
                raise
            except Exception:
                # 单轮失败不能让扫描停摆，下一轮继续。
                continue

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
            if self._promise_task is not None:
                self._promise_task.cancel()
                try:
                    await self._promise_task
                except (asyncio.CancelledError, Exception):
                    pass
                self._promise_task = None
            try:
                if self.runtime is not None:
                    await self.runtime.stop()
            finally:
                if self.store is not None:
                    await self.store.close()
                self.store = None
                self.runtime = None
