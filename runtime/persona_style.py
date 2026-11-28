"""模型调用的人格文本：已保存摘要优先，否则回退原生人格截断。

LivingEmotion 不改原生人格；摘要只是它自己使用的一份副本，可由控制台手改。
"""

from functools import lru_cache

from ..domain.emotion_persona import extract_emotion_rules
from ..prompt_injection import character_text
from ..storage.persona_style import read_style, style_key

STYLE_FALLBACK_CHARS = 1500
_emotion_rules = lru_cache(maxsize=64)(extract_emotion_rules)


class PersonaStyle:
    def emotion_persona(self, prompt=""):
        """Follow the effective character prompt; leave other generators on the style API."""
        text = character_text(self.config).strip() if self.config.character_prompt_enabled else ""
        if text:
            source = "character_prompt:" + self.config.character_preset
        else:
            text = (prompt or "").strip()
            source = "astrbot" if text else "none"
        return source, _emotion_rules(text)

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
