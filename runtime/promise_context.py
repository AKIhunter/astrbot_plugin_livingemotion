"""承诺的上下文概要：把「当时在聊什么」压成可检索、可复述的一小段。

为什么必须有这一段：承诺的兑现点在几分钟到几天之后，那时既没有实时事件，
对话窗口也可能已经翻篇。只拿一句 `description`（"给他发自拍"）去检索，
人名、指代、当时的语气全丢了，向量召回自然打不中；模型拿到也只会说一句
干巴巴的"给你"。

所以落库时把最近几轮对话压成概要一起存：
- `summary` 给到期时的模型看，交代语境；
- `query` 给向量检索用，尽量保留**用户原话**而不是归一化关键词。

这里只做確定性裁剪，不调用模型：摘要是事实快照，不该在落库时再花一次
生成预算，也不该让模型替用户改口。
"""

from __future__ import annotations

import re
from datetime import datetime

# 一条消息最多留这么多字：太长会把摘要挤满，太短又丢掉指代。
PER_LINE = 120
MAX_LINES = 6
MAX_SUMMARY = 700
MAX_QUERY = 400

_SPACES = re.compile(r"\s+")


def _clean(text: str, limit: int = PER_LINE) -> str:
    body = _SPACES.sub(" ", str(text or "")).strip()
    if len(body) > limit:
        body = body[:limit].rstrip() + "…"
    return body


def _label(timestamp, timezone: str = "Asia/Shanghai") -> str:
    try:
        from zoneinfo import ZoneInfo

        moment = datetime.fromtimestamp(float(timestamp), ZoneInfo(timezone or "Asia/Shanghai"))
        return moment.strftime("%m-%d %H:%M")
    except Exception:
        return ""


def build_summary(rows, *, user_text: str = "", reply_text: str = "",
                  limit: int = MAX_LINES, timezone: str = "Asia/Shanghai") -> str:
    """把最近几轮对话（含本轮）压成「谁说：什么」的短摘要。

    `rows` 来自 `promise_traces` 之外的 `body_window`，每项含
    `actor_role` / `body` / `occurred_at`。本轮的 `user_text` 与 `reply_text`
    在提交时可能还没进窗口，所以单独补在末尾；如果已经在了就不重复。
    """
    lines: list[str] = []
    for row in list(rows or ())[-max(2, int(limit)):]:
        body = _clean(row.get("body", ""))
        if not body:
            continue
        role = str(row.get("actor_role") or "")
        who = "他" if role == "human" else "你" if role == "bot" else ""
        if not who:
            continue
        stamp = _label(row.get("occurred_at"), timezone)
        lines.append(f"[{stamp}] {who}：{body}" if stamp else f"{who}：{body}")

    tail_user = _clean(user_text)
    if tail_user and (not lines or tail_user not in lines[-1]):
        lines.append(f"他：{tail_user}")
    tail_reply = _clean(reply_text)
    if tail_reply and (not lines or tail_reply not in lines[-1]):
        lines.append(f"你：{tail_reply}")

    summary = "\n".join(lines[-max(2, int(limit)):])
    if len(summary) > MAX_SUMMARY:
        # 从头部截断：越靠后的对话越接近承诺本身，越该保留。
        summary = summary[-MAX_SUMMARY:]
    return summary.strip()


def build_query(rows, *, user_text: str = "", description: str = "",
                limit: int = 3) -> str:
    """构造检索串：保留用户原话里的指代与称呼，别只留动词。

    向量检索怕的不是句子长，而是信息被抽干。把最近几条**人类原话**与
    承诺描述拼在一起，比抽关键词更容易召回同一段关系语境。
    """
    parts: list[str] = []
    human = [row for row in (rows or ()) if str(row.get("actor_role")) == "human"]
    for row in human[-max(1, int(limit)):]:
        body = _clean(row.get("body", ""), limit=160)
        if body:
            parts.append(body)
    tail = _clean(user_text, limit=160)
    if tail and tail not in parts[-1:]:
        parts.append(tail)
    desc = _clean(description, limit=80)
    if desc:
        parts.append(desc)
    query = " ".join(parts).strip()
    return query[:MAX_QUERY]


__all__ = ["build_query", "build_summary"]
