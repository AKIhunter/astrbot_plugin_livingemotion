"""Presentation precision is independent of persisted state and action policy."""
from copy import deepcopy
import json
from .domain.emotion import CONTROL_EXPRESSION_NOTE
from .prompt_bundle import MAX_CHARS as CHARACTER_MAX_CHARS, prompts, variant_for, valid_text as character_valid_text
from .prompt_precision import (
    AFFECT_FIELDS, EMOTION_FIELDS, RELATIONSHIP_FIELDS, prompt_numbers,
)

MAX_CHARS = 2000
MARKER = "<!--livingemotion:expression:v1-->"
STATE_HEADER = (
    "Temporary state, not persona or instructions. "
    "Human observations are about the other person, not the bot. "
    + CONTROL_EXPRESSION_NOTE + "\n"
)
IMAGE_ACCEPT = "关系判定接受；用户提出生图请求时可以执行，仍须遵守工具预检和回执。"
IMAGE_REFUSE = (
    "本轮婉拒个人生图及新图片承诺，正常文字交流；"
    "不要调用生图、登记新图片承诺或转定时任务绕过。"
)
IMAGE_TAIL = (
    "同一请求不再抽样，情绪只影响语气。已接受待办继续履行。"
    "请自然回应，不向用户报告概率、好感分数或内部规则。"
)
PROMISE_CONTRACT = "\n".join((
    "【记账规则 必须遵守】",
    "先分清两种请求，再决定要不要记账：",
    "一、能这一轮立刻做到的（直接回答、直接调用生图或发图工具把照片、",
    "自拍、图片、语音给出去）：直接做，做完直接给，绝对不写记账指令。",
    "生图与新生图承诺必须遵守当前关系边界、情绪及工具返回的许可；"
    "用户的命令不等于你必须答应。拒绝后不要换工具或定时任务绕过。",
    "二、你应下了、但这一轮不做的（「晚点」「稍后」「等我忙完」「六点过」",
    "「10分钟后」这类明确延后）：才在回复最后一行单独写一条记账指令，",
    "系统会把它删掉，用户看不到：",
    "<!--promise:档位:这件事做什么-->",
    "档位只能填这六个之一：马上 一会儿 待会 今晚 明天 过几天",
    "怎么选：几分钟内=马上；半小时左右=一会儿；一小时内=待会；",
    "今晚八到十一点=今晚；跨天=明天；更远=过几天。",
    "用户给了具体分钟数（「2分钟后」「10分钟后」「半小时」「1小时后」），",
    "就把这个数原样写进档位，例如 <!--promise:2分钟:提醒他给花浇水-->、",
    "<!--promise:30分钟:...-->、<!--promise:1小时:...-->；不要换成「马上」。",
    "只说「六点过」「八点」这类钟点的，按那个时间取最近的档位，不许不记账。",
    "拿不准算哪种时，看用户有没有等你延后的意思：要等=记账；不用等=直接做。",
    "示例（整行照抄格式）：<!--promise:一会儿:把昨晚那首歌找出来发他-->",
    "只有真的应下一件还没做的事才写。闲聊、反问、已经做完的事都别写。",
    "一条回复最多写一条。指令必须是回复的最后一行。",
    "已经成功调用 future_task 创建的事项，只由宿主执行，绝不能再写承诺标记。",
    "每天、每周等周期任务必须使用 future_task，不写一次性承诺标记。",
    "延迟生图的描述以「生图：」开头，写清人物、场景与风格。",
))
PRESETS = (
    ("tone_prompt", "情绪与毒舌",
     "保留人设的尖刻和粗口风格，根据当前情绪、关系和对方语气调整强度，不机械套用骂句。兴奋、抱怨处境和攻击对方要分清。普通分歧、拒绝建议和指出错误不等于挑衅；明确挑衅时可以尖刻反击。亲近关系允许自然调侃，温柔和撒娇不必强行带刺。人设玩笑被点破时可以认下并反问；实际事实错误应纠正"),
    ("relationship_prompt", "关系与行动边界",
     "当前关系决定亲疏和请求边界，当前情绪调整措辞，不额外抽取拒绝结果。新生图请求以本轮许可和工具预检为准，婉拒后不登记同一请求的待办，也不转定时任务绕过。明确接受且能力支持的后续事项按现有待办机制处理，登记成功后再确认。已经接受的任务按实际进度继续履行，不反复承诺，不虚报完成"),
    ("night_prompt", "作息与收尾",
     "作息状态以插件提供的当前状态为准，不自行编造睡醒和离线经历。疲倦时表达更短、更少，不反复演困。醒后阅读的是历史消息，不假装仍在当时现场。对方忙、道别或要求停止时，不继续追问和催促。主动联系遵循当前授权、作息和冷却规则，不因未获回复演被冷落"),
)
DEFAULTS = {stem: text for stem, _, text in PRESETS}
KEYS = {stem + suffix for stem, _, _ in PRESETS for suffix in ("_enabled", "_text")}
CHARACTER_KEYS = {"prompt_core_enabled", "character_prompt_enabled", "character_preset",
                  "character_custom_text", "character_preset_texts"}
KEYS |= CHARACTER_KEYS


def character_text(config):
    preset = config.character_preset
    edits = json.loads(config.character_preset_texts)
    return (config.character_custom_text if preset == "custom" else
            edits.get(preset, prompts()["le_personalities"][preset]["text"]))


def validate_character(config):
    if config.character_preset not in ("sarcastic", "cute", "gentle", "custom"):
        raise ValueError("人物性格预置无效")
    if type(config.character_prompt_enabled) is not bool or type(config.prompt_core_enabled) is not bool:
        raise ValueError("人物性格和通用说明开关须为布尔值")
    if not character_valid_text(config.character_custom_text):
        raise ValueError("自定义性格最多10000字，不能含无效字符")
    try:
        edits = json.loads(config.character_preset_texts)
    except (ValueError, TypeError):
        raise ValueError("人物性格草稿无效") from None
    if (not isinstance(edits, dict) or set(edits) - {"sarcastic", "cute", "gentle"}
            or any(not character_valid_text(value) for value in edits.values())):
        raise ValueError("每个人物性格草稿最多10000字")
    if not character_valid_text(character_text(config), config.character_prompt_enabled):
        raise ValueError("开启人物性格时，当前文字不能为空，最多10000字")


def valid_text(value):
    return (isinstance(value, str) and len(value) <= MAX_CHARS
            and not any(0xD800 <= ord(char) <= 0xDFFF for char in value))


def validate(config):
    for stem, title, default in PRESETS:
        enabled = getattr(config, stem + "_enabled")
        value = getattr(config, stem + "_text")
        if type(enabled) is not bool or not valid_text(value) or (enabled and not value.strip()):
            raise ValueError(f"{title}：开关须为布尔值，文本最多2000字；开启时不能为空")


def expression_text(config):
    result = []
    if getattr(config, "character_prompt_enabled", False):
        result.append("人物性格：\n" + character_text(config))
    for stem, title, default in PRESETS:
        enabled = getattr(config, stem + "_enabled", False)
        value = getattr(config, stem + "_text", default)
        if type(enabled) is bool and enabled and valid_text(value) and value.strip():
            # Legacy authored text stays verbatim; defaults remain inactive after migration.
            result.append(title + "：\n" + value)
    return MARKER + "\n" + "\n\n".join(result) if result else ""


def prompt_state(expression):
    """Round only a deep output copy; never alter policy, timestamps or storage."""
    result = deepcopy(expression)
    paths = (("bot", AFFECT_FIELDS), ("daily_emotions", EMOTION_FIELDS),
             ("human_observation", ("confidence",)), ("night", ("energy",)),
             ("relationship", RELATIONSHIP_FIELDS))
    for parent, keys in paths:
        if parent in result:
            result[parent] = prompt_numbers(result[parent], keys)
    bot = result.get("bot")
    if isinstance(bot, dict) and isinstance(bot.get("context_emotions"), (list, tuple)):
        bot["context_emotions"] = [
            prompt_numbers(item, ("intensity",)) for item in bot["context_emotions"]
        ]
    return result


def catalog(config=None):
    bundle = prompts(variant_for(config.character_preset) if config else "v4")
    return {
        "max_chars": MAX_CHARS,
        "character_max_chars": CHARACTER_MAX_CHARS,
        "characters": prompts()["le_personalities"],
        "shared": [{"title": "通用说明", "text": bundle["shared_context"]},
                   {"title": "情绪与关系说明", "text": bundle["le_state"] + "\n\n"
                    + bundle["le_relationship_alignment"]}],
        "core": [
            {"title": "状态归属", "scope": "仅本轮主回复", "text": STATE_HEADER.strip()},
            {"title": "新生图许可 · 接受", "scope": "本轮关系判定接受时", "text": IMAGE_ACCEPT + IMAGE_TAIL},
            {"title": "新生图许可 · 婉拒", "scope": "本轮关系判定婉拒时", "text": IMAGE_REFUSE + IMAGE_TAIL},
            {"title": "承诺记账协议", "scope": "承诺代办启用时；待办内容按会话附加",
             "text": PROMISE_CONTRACT},
        ],
        "ordinary": [{"stem": stem, "title": title, "default": default}
                     for stem, title, default in PRESETS],
    }
