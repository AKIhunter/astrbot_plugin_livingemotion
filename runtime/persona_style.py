"""模型调用的人格文本：已保存摘要优先，否则回退原生人格截断。

LivingEmotion 不改原生人格；摘要只是它自己使用的一份副本，可由控制台手改。
"""

from ..storage.persona_style import read_style, style_key

STYLE_FALLBACK_CHARS = 1500


class PersonaStyle:
    async def persona_style(self, persona_id, prompt=""):
        saved = ""
        if persona_id:
            try:
                saved = await read_style(self.store, style_key(self.instance_id, persona_id))
            except Exception:
                saved = ""
        if saved.strip():
            return saved
        return (prompt or "").strip()[:STYLE_FALLBACK_CHARS]
