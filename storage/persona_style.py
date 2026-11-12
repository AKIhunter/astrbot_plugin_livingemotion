"""LivingEmotion 专属的人格风格摘要；原生人格始终不被改写。

摘要按 (实例, 原生人格 ID) 存在 runtime_meta，未保存时才回退到原生人格前缀。
"""

import json

from ..contracts import stable_key

PREFIX = "console.persona.style.v1:"
MAX_CHARS = 2000


def style_key(instance_id, persona_id):
    return PREFIX + stable_key(instance_id, persona_id)


async def read_style(store, key) -> str:
    def read(db):
        row = db.execute("SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()
        if not row:
            return ""
        try:
            value = json.loads(row[0])
        except (TypeError, ValueError):
            return ""
        text = value.get("text") if isinstance(value, dict) else None
        return text if isinstance(text, str) and text.strip() else ""

    return await store._run(read)


async def write_style(store, key, text):
    """空文本表示恢复默认：删掉存值，下次调用回退原生人格。"""
    now = store.clock()

    def write(db):
        if not isinstance(text, str) or not text.strip():
            db.execute("DELETE FROM runtime_meta WHERE key=?", (key,))
            return ""
        db.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (key, json.dumps({"text": text, "updated_at": now}, ensure_ascii=False)))
        return text

    return await store._run(write)
