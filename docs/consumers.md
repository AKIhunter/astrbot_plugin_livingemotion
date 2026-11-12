# 可选插件协作

LivingEmotion 核心无需其他插件。协作只通过公开接口，不跨插件读取私有配置或数据库。

| 插件 | 接点 | 失败行为 |
| --- | --- | --- |
| LivingHello | `livinghello.function-coupling.v1` 控制是否注入状态、记忆及执行补课 | 关闭协作时清除临时注入，保留普通聊天 |
| LivingMemory | 公开身份、关系投影及记忆门面，按开关分别读取和写入 | 无授权返回空，不穿透私有库 |
| BiliBot | `plugin.api` v1 的事件接入与能力查询 | 由消费者处理失败；本插件不修改消费者配置 |

`get_capabilities()` 的模式来自 LivingEmotion 自身配置。已选择本插件的消费者，
应在调用前查询能力并在失败后报告原因，不能把一次拒绝当作授权去写其他插件的数据。
自主发送仍须通过本插件自身的范围、路由、额度和授权校验。

LivingHello 补课计时只读取 `livingemotion:wake_prepare_seconds`。
旧版消费者升级前须核对该键及 API v1 支持；文件配置读回不能替代运行态验收。

合成协作回归入口：`tests/integration/test_livinghello_coupling.py`；
公开 API 与来源范围见 [api.md](api.md)、[记忆说明](memory.md)。
