"""LivingMemory 只读接入层：把「别人家的记忆插件」读成统一的镜像行。

===== 给后来者（包括 AI）的接入说明 =====

本文件是 LivingEmotion 与 LivingMemory 之间**唯一**的耦合点。想换成别的记忆插件
（mem0、自研向量库、其他 AstrBot 记忆插件），只需要改这个文件里的三个函数：

    engine_of(plugin)                  -> 返回底层引擎对象
    persona_memory_counts(engine)      -> 返回 [(persona_id, count)]
    persona_memory_rows(engine, ...)   -> 返回标准化后的记忆行（见 _normalize_row）

上层（services/memory_sync.py、runtime/console.py、页面按钮）**不**知道
LivingMemory 的内部结构，因此替换实现时不需要改动它们。

已核对的 LivingMemory 公开结构（2.9.x / 2.10.x）：

    plugin = discover("astrbot_plugin_livingmemory")     # AstrBot 插件实例
    plugin.initializer.memory_engine                     # 记忆引擎
    engine.db_connection                                 # aiosqlite 连接
    engine.list_memories_page(...)                       # 官方分页接口（可选）

    documents 表：id / doc_id / text / metadata(JSON) / created_at / updated_at
    metadata 关键字段：persona_id、session_id、status、importance、create_time、
                       source_id、source_ids、adapter_id、source_account …

为什么直接读 documents 而不是调用 list_memories_page：
  1) 分页接口带「所有权 / 身份修订」过滤，管理端镜像不该走那套受众逻辑，
     否则同一条记忆会因调用者不同而时有时无；
  2) 全量镜像需要稳定游标（id > after_id）分批读取，避免一次性把上千条读进内存；
  3) 只读 SQL 不会触发生成、向量化、图关系写入，也不会改动对方的库。

安全边界（不要为了“跑通”而放宽）：
  * 只在本插件配置 livingmemory_enabled=True 时才允许调用；
  * 只读：不 INSERT/UPDATE/DELETE 对方的库，不调用 add_memory；
  * 只取 status=active 的行，persona_id 必须精确匹配；
  * text 截断到 _MAX_TEXT_CHARS，防止超长正文撑爆本地镜像；
  * 任何异常都转成 LivingMemoryUnavailable，由上层显示中文原因，不静默编造数据。
"""

from __future__ import annotations

import json
from collections.abc import Mapping

# 单条正文上限：镜像只用于管理端查看与统计，不复制无限长正文。
_MAX_TEXT_CHARS = 4000
# 单批读取上限：分批游标读取，避免一次把整库读进内存。
_MAX_BATCH = 500


class LivingMemoryUnavailable(RuntimeError):
    """LivingMemory 不可用或结构不匹配；message 为约定的诊断码。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def engine_of(plugin: object | None) -> object | None:
    """从 AstrBot 插件实例取出记忆引擎；结构不符合预期时返回 None。

    兼容两种挂载方式：plugin.initializer.memory_engine（当前版本）
    与 plugin.memory_engine（早期版本）。
    """
    if plugin is None:
        return None
    initializer = getattr(plugin, "initializer", None)
    engine = getattr(initializer, "memory_engine", None)
    if engine is None:
        engine = getattr(plugin, "memory_engine", None)
    return engine


def _field(row: object, key: str, index: int):
    """aiosqlite.Row / dict / tuple 三种返回形态都要能取值。"""
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]  # sqlite3.Row 支持按列名取值
    except (IndexError, KeyError, TypeError):
        pass
    try:
        return row[index]
    except (IndexError, KeyError, TypeError):
        return None


def _metadata(value) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", "replace")
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def probe(plugin: object | None) -> dict:
    """只读探活：返回可展示的状态，不抛异常、不改动对方数据。"""
    engine = engine_of(plugin)
    if engine is None:
        return {"available": False, "reason": "livingmemory_plugin_missing", "engine": None}
    if getattr(engine, "db_connection", None) is None:
        return {"available": False, "reason": "livingmemory_database_not_open", "engine": engine}
    return {"available": True, "reason": "", "engine": engine}


async def _fetch(engine, sql: str, parameters: tuple):
    connection = getattr(engine, "db_connection", None)
    if connection is None:
        raise LivingMemoryUnavailable("livingmemory_database_not_open")
    try:
        async with connection.execute(sql, parameters) as cursor:
            return await cursor.fetchall()
    except LivingMemoryUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - 结构不匹配统一转诊断码
        raise LivingMemoryUnavailable("livingmemory_query_failed") from exc


async def persona_memory_counts(engine) -> list[dict]:
    """按人格统计 memory_persona_counts。

    返回 [{"persona_id": "大小姐v2", "total": 1006}]，按数量降序。
    供设置页/记忆页显示「这个人格到底有多少条记忆」，不做任何剪裁。
    """
    rows = await _fetch(
        engine,
        "SELECT COALESCE(json_extract(metadata, '$.persona_id'), '') AS persona_id, "
        "COUNT(*) FROM documents WHERE json_valid(metadata) "
        "AND COALESCE(json_extract(metadata, '$.status'), 'active') = 'active' "
        "GROUP BY persona_id ORDER BY COUNT(*) DESC",
        (),
    )
    result = []
    for row in rows:
        persona_id = _field(row, "persona_id", 0) or ""
        total = _field(row, "total", 1)
        if isinstance(persona_id, str) and persona_id and isinstance(total, int) and total >= 0:
            result.append({"persona_id": persona_id, "total": total})
    return result


async def persona_memory_rows(
    engine, persona_id: str, *, after_id: int = 0, limit: int = _MAX_BATCH,
) -> list[dict]:
    """按 id 游标读取某个人格的一页记忆（只读、稳定顺序、可重复执行）。

    after_id：上一批最后一条的 memory_id；首批传 0。
    limit   ：本批上限，内部限制在 1.._MAX_BATCH。
    """
    if not isinstance(persona_id, str) or not persona_id:
        raise LivingMemoryUnavailable("livingmemory_persona_required")
    if type(after_id) is not int or after_id < 0:
        raise LivingMemoryUnavailable("livingmemory_cursor_invalid")
    size = max(1, min(_MAX_BATCH, limit if type(limit) is int else _MAX_BATCH))
    rows = await _fetch(
        engine,
        "SELECT id, text, metadata, created_at FROM documents "
        "WHERE json_valid(metadata) "
        "AND json_extract(metadata, '$.persona_id') = ? "
        "AND COALESCE(json_extract(metadata, '$.status'), 'active') = 'active' "
        "AND id > ? ORDER BY id ASC LIMIT ?",
        (persona_id, after_id, size),
    )
    return [_normalize_row(row, persona_id) for row in rows]


def _normalize_row(row, persona_id: str) -> dict:
    """统一行格式；其他记忆插件只需产出同样字段即可复用上层。"""
    metadata = _metadata(_field(row, "metadata", 2))
    body = _field(row, "text", 1)
    if not isinstance(body, str):
        body = "" if body is None else str(body)
    memory_id = _field(row, "id", 0)
    created = _number(_field(row, "created_at", 3))
    if created is None:
        created = _number(metadata.get("create_time"))
    session_id = metadata.get("session_id")
    return {
        "memory_id": int(memory_id) if isinstance(memory_id, int) else 0,
        "persona_id": persona_id,
        "text": body[:_MAX_TEXT_CHARS],
        "truncated": len(body) > _MAX_TEXT_CHARS,
        "session_id": session_id if isinstance(session_id, str) else "",
        "created_at": created,
        "metadata": {
            key: metadata[key] for key in (
                "importance", "memory_type", "source_account",
                "subject_accounts", "audience", "sensitivity",
            ) if key in metadata
        },
    }
