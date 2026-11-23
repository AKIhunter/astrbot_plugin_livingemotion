# 模型情绪输入精度

适用 LivingEmotion 0.7.1；精度规则始于0.6.3。

LE 发给模型的情绪数值最多保留 3 位小数。只处理输出副本，数据库、内部状态和判定阈值保留原精度。

例如 `0.0046154795463250325` 输出为 `0.005`，`0.24951` 输出为 `0.25`；不补无意义的零，`0.1` 仍为 `0.1`。归一化数值的最大舍入误差为 `0.0005`，折算百分制为 `0.05` 点。

## 处理位置

`prompt_precision.py` 提供统一的 `PROMPT_DECIMALS = 3`，只舍入指定字段，不递归舍入所有浮点数。

| 模型入口 | 处理的数值 | 实现位置 |
| --- | --- | --- |
| 主回复状态注入 | 四维情绪、每日六情绪、短期情绪强度、人类观察置信度、精力 | [prompt_injection.py](../prompt_injection.py)、[application.py](../runtime/application.py) |
| 异步情绪细化 | 四维情绪、四个基准值、底气、关系归一化维度 | [refinement.py](../runtime/refinement.py) |
| 主动聊天 | 情绪值、亲近度、信任度、边界 | [models.py](../runtime/models.py) |
| 内心感想 | 六情绪 | [feeling.py](../runtime/feeling.py) |
| 控制台模拟发送 | 六情绪及语气说明中重复的同一组数值 | [behavior_simulation.py](../runtime/behavior_simulation.py) |
| 手动日记、梦境 | 情绪均值、梦境情绪值 | [manual_experience.py](../services/manual_experience.py) |
| 自动日记、梦境 | 四维情绪、当前六情绪、情绪均值、梦境情绪值 | [experience.py](../services/experience.py) |
| 随机晚安收尾 | 精力 | [application.py](../runtime/application.py) |

时间戳、证据、关系原始分数、整数、布尔值和空值保持原样。页面的六情绪及保存的情绪快照继续沿用原精度；`expression_items` 的短期情绪输出统一为 3 位。

统一精度工具位于 [prompt_precision.py](../prompt_precision.py)，短期情绪输出位于 [context_emotion.py](../domain/context_emotion.py)。

梦境主情绪、语气和事件仍先用未舍入值判定，再舍入模型输出。例如最高值 `0.24951` 仍低于 `0.25` 的触发阈值，输出虽然显示 `0.25`，梦境主情绪仍按原值判为平静。短期情绪的显示阈值也先按原值过滤。

自动体验的素材预算继续使用原始 payload 与既有 `canonical_json` 口径，避免精度变化引起素材选择变化。

## 中文序列化

主回复的状态块改用 `prompt_json`，中文直接输出，不再变为 `\uXXXX`。状态标记、块位置、临时消息属性、字段和键排序保持一致。

`canonical_json` 本身不变，稳定键、哈希、落库及原有预算口径不变。本次中文修正针对主回复状态块。

## 离线验证

[消息体回归测试](../tests/integration/test_prompt_precision.py) 使用合成模型和临时 SQLite，覆盖实际提示词入口、细小浮点数、阈值附近的值、中文 JSON 等价、时间与证据保真，以及原始对象不被修改。

天气模拟的旧回归同步改为比较模型的 3 位输出，并继续验证页面数值和数据库状态保持原样。

复测命令：`python -m pytest -q tests/integration/test_prompt_precision.py tests/behavior/test_console_simulation.py`。这些用例不调用真实模型。
