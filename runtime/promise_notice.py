"""承诺管理的固定文案：零模型直发，不带停顿标点，用空格断句。

写作用语刻意保持不一致：同一个意思给五到六种明显不同的说法，
由调用方按记录键取模选择，避免同一条会话里反复出现同一句。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# 中文停顿标点：这些一律不出现在文案里，统一换成一个或两个空格。
_STOPS = "，。、；：,.;:!！?？…\u2026\u3001\u3002\uff0c\uff1b\uff1a"


def tidy(text: str, *, limit: int = 40) -> str:
    """把任意片段压成一行可直接嵌进文案的短句。"""
    value = str(text or "").replace("\n", " ").replace("\r", " ")
    keep = []
    for char in value:
        if char in _STOPS:
            keep.append(" ")
        elif char.isprintable():
            keep.append(char)
        else:
            keep.append(" ")
    cleaned = "".join(keep)
    # 连续空格压成一个，首尾留白去掉，再按字数截断。
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    cleaned = cleaned.strip()
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip()
    return cleaned


def pick(seed: str, count: int, *, salt: str = "") -> int:
    """稳定选择：同一件事多次处理落在同一个变体上，不同事则分散。

    salt 用来在“必须避开上一句”时换一个落点，而不是简单加一（那会形成 A B A B 的来回跳）。
    """
    if count <= 0:
        return 0
    material = f"{seed}|{salt}" if salt else str(seed or "")
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % count


def relative_eta(seconds) -> str:
    """相对说法比时间戳更像人话。"""
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return "过一会儿"
    if value <= 90:
        return "就这一两分钟"
    if value < 3600:
        return f"{max(1, int(round(value / 60)))} 分钟后"
    if value < 7200:
        return "一小时内"
    if value < 43200:
        return f"{max(1, int(round(value / 3600)))} 小时后"
    if value < 129600:
        return "明天"
    return f"{max(2, int(round(value / 86400)))} 天后"


@dataclass(frozen=True)
class Candidate:
    """一条待选承诺，只用展示需要的字段。"""

    number: int
    desc: str
    eta: str


def _lines(items) -> str:
    rows = []
    for item in items:
        body = " ".join(part for part in (item.desc, item.eta) if part)
        rows.append(f"{item.number} {body}".strip())
    return "\n".join(rows)


class Notice:
    """六类承诺管理文案。每类给足变体，措辞与句式刻意拉开距离。"""

    # ① 多候选时追问：必须先问清是哪一个
    ASK = (
        "嗯 你说的哪个 现在挂着这几件\n{lines}\n说编号最快 或者提个关键词我自己找",
        "我这儿有好几件事在排队呢\n{lines}\n你想撤哪件 说个编号就行",
        "等下 我有点懵 手上是这些\n{lines}\n你指的是第几件",
        "别急 我确认下 同时挂着的还有这些\n{lines}\n要砍哪个 报个数字给我",
        "手上攒了 {count} 件事没做完\n{lines}\n你要停掉哪一件 一句话点我一下",
        "嗯 我这边挂着不止一件\n{lines}\n说第几个 或者讲讲那事大概是啥 我来对上",
    )

    # ② 取消成功：一句话认下，不啰嗦
    CANCEL_ONE = (
        "行 {desc} 我不弄了",
        "好 那就撤了 不折腾了",
        "嗯 收到 {desc} 先放下",
        "知道了 我不提这事了 有别的心思随时喊我",
        "行吧 {desc} 就到这里",
        "好嘞 已划掉 不用惦记了",
    )

    # ③ 撤不回：实话实说，不装
    CANCEL_LATE = (
        "哎 {desc} 已经在发了 这会儿刹不住",
        "晚了点 刚才就送出去了 拦不回来",
        "这东西已经在路上 我只能看着它出去",
        "{desc} 已经动手了 现在停下也来不及",
        "你这话说慢了一步 它正往外走呢",
        "没辙 那一刻已经过了 下次早点跟我说",
    )

    # ④ 催促受阻：说明原因，给个替代
    ADVANCE_BLOCKED = (
        "今天排满了 {desc} 只能挪到明天",
        "今天真塞不下了 前面还有事排着 明天行吗",
        "不是我不想快 今天就剩这么点空间 {desc} 得等明天",
        "这会儿挤不进去 手上活还没清 明天帮你弄",
        "{desc} 今天满了 硬塞会出事 明天一早我先办这个",
        "今天没空位了 要不明天 要不你告诉我这事儿能等多久",
    )

    # ⑤ 批量操作要二次确认：越机械越安全
    CONFIRM_ALL = (
        "两件都撤 我念一遍你听着\n{lines}\n嗯一声我就全清掉",
        "一次清 {count} 件 你确定吗\n{lines}\n确认我就动手",
        "这几件一起放弃\n{lines}\n回个都撤我就办",
        "等等 一下撤这么多我有点担心\n{lines}\n真的都不要了吗",
        "{count} 件一起停 提醒你一句 撤了就没了\n{lines}\n还要继续就说一声",
        "手一抖就全没了哦\n{lines}\n确定要我全停",
    )

    # ⑥ 清单查询：纯数据罗列
    LIST = (
        "现在挂着这些\n{lines}\n要动哪件跟我说",
        "手头还有 {count} 件没做\n{lines}\n都在排队 没漏",
        "剩下的活儿\n{lines}\n有要改的现在说",
        "盘点一下 还有 {count} 件事压着\n{lines}\n不急 都在排",
        "这些还没办\n{lines}\n想撤想改都行",
        "任务清单在这儿\n{lines}\n看着安排",
    )

    EMPTY = (
        "现在一件都没挂 干干净净的",
        "手上空着呢 没承诺过啥",
        "没有待办 清空了",
        "暂时没攒着事 挺清净",
        "我这儿是空的 没在等什么",
        "没什么挂着的 都办完了",
    )

    WHERE = {
        "ASK": ASK,
        "CANCEL_ONE": CANCEL_ONE,
        "CANCEL_LATE": CANCEL_LATE,
        "ADVANCE_BLOCKED": ADVANCE_BLOCKED,
        "CONFIRM_ALL": CONFIRM_ALL,
        "LIST": LIST,
        "EMPTY": EMPTY,
    }

    @classmethod
    def variants(cls, name: str) -> tuple[str, ...]:
        return cls.WHERE[name]

    @classmethod
    def choose(cls, name: str, seed: str, *, avoid_ids=()) -> int:
        """选出变体下标，并尽量避开最近用过的几个。

        调用方保存返回的下标即可实现“同一会话不重复”，不必比对渲染结果，
        因为模板含占位符，渲染后的文本无法反查回模板。
        """
        import random

        count = len(cls.variants(name))
        base = pick(seed, count)
        blocked = {int(i) for i in avoid_ids if isinstance(i, int)}
        if count <= 1:
            return base
        if base not in blocked:
            return base
        # 候选池里随机取一个，比顺序挪动覆盖得更散，不会退化成三句循环。
        pool = [i for i in range(count) if i not in blocked]
        if not pool:
            return base
        return random.choice(pool)

    @classmethod
    def render(cls, name: str, seed: str, *, avoid_ids=(), **fields) -> str:
        variants = cls.variants(name)
        items = fields.get("items") or ()
        has_items = isinstance(items, (list, tuple)) and bool(items)
        # 清单类在没有条目时不该印“0 件压着”，直接改用无待办的说法。
        if not has_items and name in ("LIST", "CONFIRM_ALL") and not fields.get("desc"):
            name = "EMPTY"
            variants = cls.variants(name)
        index = cls.choose(name, seed, avoid_ids=avoid_ids)
        template = variants[index]
        data = dict(fields)
        items = data.get("items") or ()
        if isinstance(items, (list, tuple)) and items:
            data["items"] = tuple(items)
            data["lines"] = _lines(data["items"])
            data["count"] = len(data["items"])
        else:
            data["lines"] = " 暂时空的"
            data.setdefault("count", 0)
        desc = data.get("desc")
        data["desc"] = tidy(desc) if isinstance(desc, str) and desc.strip() else "那件事"
        try:
            text = template.format(**data)
        except (KeyError, IndexError, ValueError):
            # 字段缺失时退回最朴素的说法，绝不把异常抛给发送链路。
            return f"现在挂着 {data.get('count', 0)} 件事 你要动哪件"
        return strip_stops(text).strip()


def strip_stops(text: str) -> str:
    """渲染后的兜底：极端字段也可能带标点，统一换成空格。

    只压缩行内连续空格，保留换行——清单类文案靠换行分行。
    """
    out = []
    for char in str(text or ""):
        out.append(" " if char in _STOPS else char)
    lines = []
    for line in "".join(out).split("\n"):
        while "  " in line:
            line = line.replace("  ", " ")
        lines.append(line.strip())
    # 去掉连续空行，只留单个换行。
    collapsed = []
    for line in lines:
        if not line and collapsed and not collapsed[-1]:
            continue
        collapsed.append(line)
    return "\n".join(collapsed).strip()


def ask_items(rows) -> tuple[Candidate, ...]:
    """把查询结果转成展示行，只保留编号 描述 时间。"""
    items = []
    for index, row in enumerate(rows, start=1):
        desc = tidy(row.get("description") or row.get("desc") or "", limit=28)
        eta = relative_eta(row.get("eta_seconds", 0))
        items.append(Candidate(index, desc, eta))
    return tuple(items)


__all__ = [
    "Candidate",
    "Notice",
    "ask_items",
    "pick",
    "relative_eta",
    "strip_stops",
    "tidy",
]
