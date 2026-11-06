"""Last-mile checks for autonomously generated public conversation text."""

import re

_PRIVATE = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._-]{12,}|sk-[A-Za-z0-9_-]{12,}|"
    r"(?:api[_ -]?key|access[_ -]?token|password|密码|密钥)\s*[:=：]\s*\S+|"
    r"/(?:Users|home|var/lib/astrbot)/|-----BEGIN .*PRIVATE KEY-----|"
    r"<!--(?:livingemotion|congling):|system[_ ]prompt\s*[:=]|"
    r"(?:qq号|uid|账号ID)\s*[:=：]\s*[0-9]{5,})",
    re.IGNORECASE,
)


def public_text_allowed(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip()) and _PRIVATE.search(value) is None
