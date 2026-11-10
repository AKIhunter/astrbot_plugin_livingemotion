"""Manual one-way sync from an external memory plugin into a local read-only mirror.

设计要点（改动前请先读 integrations/livingmemory.py 的模块说明）：

* 只在配置 livingmemory_enabled=True 时可执行；关闭时按钮不可用、接口也直接拒绝。
* 只读对方数据库，不写回、不向量化、不触发对方生成。
* 本地镜像存 external_memories（按 persona_id + memory_id 去重），
  仅用于管理端展示与统计；真正的检索仍由 LivingMemory 实时接口负责。
* 结果使用稳定诊断码（reason_code），中文文案由 runtime/console.py 统一翻译。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..integrations.livingmemory import (
    LivingMemoryUnavailable,
    engine_of,
    persona_memory_counts,
    persona_memory_rows,
    probe,
)

PROVIDER = "astrbot_plugin_livingmemory"
DEFAULT_MAX_RECORDS = 20000
BATCH = 500


@dataclass(frozen=True)
class SyncOutcome:
    status: str
    reason_code: str
    persona_id: str
    read: int = 0
    stored: int = 0
    truncated: bool = False
    synced_at: float | None = None

    def as_dict(self) -> dict:
        return {
            "api_version": 1, "status": self.status, "reason_code": self.reason_code,
            "persona_id": self.persona_id, "read": self.read, "stored": self.stored,
            "truncated": self.truncated, "synced_at": self.synced_at,
        }


class MemorySyncService:
    """Bounded, idempotent, read-only import of one persona's memories."""

    def __init__(self, store, discover, config, *, max_records: int = DEFAULT_MAX_RECORDS):
        self.store = store
        self.discover = discover
        self.config = config
        self.max_records = max(1, min(DEFAULT_MAX_RECORDS, int(max_records)))

    def _plugin(self):
        try:
            return self.discover(PROVIDER)
        except Exception:  # noqa: BLE001 - discovery is optional and must not raise
            return None

    def status(self) -> dict:
        """Cheap, side-effect free: only reports whether the provider is reachable."""
        enabled = bool(getattr(self.config, "livingmemory_enabled", False))
        health = probe(self._plugin() if enabled else None)
        return {"enabled": enabled, "available": health["available"],
                "reason": health["reason"], "provider": PROVIDER}

    async def persona_counts(self, persona_id: str) -> list[dict]:
        if not bool(getattr(self.config, "livingmemory_enabled", False)):
            return []
        health = probe(self._plugin())
        if not health["available"]:
            return []
        try:
            return await persona_memory_counts(health["engine"])
        except LivingMemoryUnavailable:
            return []

    async def sync(self, context, *, persona_id: str = "") -> SyncOutcome:
        """Read every active memory of one persona and replace the local mirror."""
        target = persona_id or getattr(context, "persona_id", "") or ""
        if not bool(getattr(self.config, "livingmemory_enabled", False)):
            return SyncOutcome("rejected", "livingmemory_disabled", target)
        if not target:
            return SyncOutcome("rejected", "livingmemory_persona_required", target)
        health = probe(self._plugin())
        if not health["available"]:
            return SyncOutcome("unavailable", health["reason"] or "livingmemory_plugin_missing",
                               target)
        engine = engine_of(health["engine"]) or health["engine"]
        rows: list[dict] = []
        cursor = 0
        truncated = False
        try:
            while len(rows) < self.max_records:
                size = min(BATCH, self.max_records - len(rows))
                batch = await persona_memory_rows(engine, target, after_id=cursor, limit=size)
                if not batch:
                    break
                rows.extend(batch)
                cursor = max(cursor, max(row["memory_id"] for row in batch))
                if len(batch) < size:
                    break
            truncated = len(rows) >= self.max_records
        except LivingMemoryUnavailable as exc:
            return SyncOutcome("unavailable", exc.code, target, read=len(rows))

        synced_at = self.store.clock()
        written = await self.store.replace_external_memories(
            target, PROVIDER, rows, synced_at=synced_at, truncated=truncated,
        )
        return SyncOutcome("synced", "memory_synced", target, read=len(rows),
                           stored=written["stored"], truncated=written["truncated"],
                           synced_at=synced_at)
