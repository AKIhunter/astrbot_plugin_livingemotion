# T6 主动行为与唯一发送端

当前服务已接入持久历史、共享模型预算和主入口。随机闲置主动聊天、
设置与故障边界以[主动聊天指南](proactive-life.md)为准。
下文保留早期T6交接与阶段测试记录，其中“待接线”和文件归属说明属于当时阶段，
不代表当前集成状态；旧测试数量不作为本次功能验收。

## 给父代理 / Foundation 的接点

当前 `SQLiteStore` 有意图 CAS 和原子配额预留，但没有持久行为历史查询。
T6 不增加 SQL，不占用 bot/night/relationship 的状态字段。
需要 foundation 提供只读查询，再由集成者注入 `history` 回调：

```python
async def history(context: Context, period: str,
                  exclude_intent_id: str | None) -> BehaviorHistory: ...
```

查询必须使用 `pool="send", purpose="behavior"` 的持久 reservation / intent：

- `global_used`、`scope_used`：指定日期所有已消耗预留，含失败、取消、unknown。
  最终复核时只排除本意图在该日期的预留，不排除其他任务。
  全局应包含同 `send` pool 的其他用途；scope 统计固定 `behavior` purpose。
- `last_attempt_at`：本 scope 最近 sending / succeeded / unknown 或实际发送失败的尝试时间；
  不因重启、跨日或正文清理重置。排除当前意图，不能将模型失败算成已外发。
- `unanswered_count`：最新 human 水位之后的成功 / unknown 尝试数量；
  pending、生成失败不增加。计数来自持久人类消息水位，不看 Bot 前置文本或工具事件。
  不应依赖会被清理的正文/事件窗口重建全部历史。

缺少该回调时 `behavior_history_unavailable`，默认拒绝自主行为。
测试会以已知意图 ID 的目录读取真实 SQLite 行模拟这个缺失的只读索引，
不宣称成品存储已提供查询或已完成主入口接线。

其他需 foundation 评估的缺口：

1. 如要支持多进程同时执行同一个库，需要在 sending 事务内原子检查
   scope 冷却/退避。T6 只支持规格中的同进程单发送所有者，进程内同库执行串行。
2. 当前成功终态与成功事件是两个提交，没有事务性回执 outbox。
   两提交间崩溃会漏成功事件，但绝不重发；不能宣称端到端 exactly-once。
3. 意图创建后没有追加素材引用的公共方法；生成结果不落库，成功事件保留引用。
   若需失败意图的完整材料审计，由 foundation 增加有限引用附加接口。
4. 最近发送时间及回复重置水位需要非正文持久信息。当前 intent 的 `updated_at`
   是最近转换时间，不能还原所有发送阶段时间；可保守采用终态时间延后冷却，
   不要通过读取已被清理的事件来假设“没有未回复行为”。

并行期间 foundation 增加了 `reserve_quota(min_interval_seconds=...)`。
该间隔按预留时间计量，包含生成失败，并不替代本任务所需的发送历史/回复退避查询；
T6 没有改变它，也没有依赖私有连接。

## 公开调用方式

模块内端口/结果类型在 `services.behavior`；共享状态仍唯一来自 `contracts.py`。
没有新增第二套人格、身份、夜间或存储状态类型。`BehaviorSnapshot` 只是一次宿主读取的组合视图。

```python
service = BehaviorService(
    store,
    current=current_snapshot,
    validate_identity=identity_guard,
    validate_evidence=memory_gateway.validate_evidence,
    model=budgeted_generate,
    sender=guarded_sender,
    policy=read_behavior_policy,
    history=durable_history,
    # 可选：materials、availability、record_success、clock
)

evaluation = await service.evaluate(context)         # 含评分，无副作用
preview = await service.preview_behavior(context)    # contracts.BehaviorPreview
result = await service.execute(
    context, intent_id=logical_intent_id, purpose="proactive",
)
result = await service.execute_intent(pending_intent) # T5 等服务的未落库提案
await service.close()                               # 然后才能关闭 store
```

上面是接线示意，不是默认启用脚本。`execute` / `execute_intent` 才会调用模型及发送桩/适配器。
普通主回复不经过本服务。`purpose` 不影响额度桶，不能换名绕过限制。
调用者必须给跨重启稳定、全库唯一的逻辑 `intent_id`，最长 256 字符；
建议组合生产者、scope、用途、原事件/补课摘要 ID。不要以秒时间、正文摘要或每次新 UUID 重建同一意图。

`execute_intent` 只接受未落库的 `pending` 提案；保留它的 generation、
human_watermark、created_at、expires_at、evidence 和 reason_codes。
T5 可将 `catchup_intent(...)` 的结果交来，但它的 human_watermark 必须是真实
`SQLiteStore.human_watermark(context)` 的对应快照，不是包含 Bot/tool 的通用窗口游标。
不匹配就拒绝，不重新获取水位让旧补答继续执行。已落库的旧意图只返回已有状态，绝不接着发。
补课正文通过 `materials` 回调提供，保持 summary 的原始 source_ids 和完整最终授权；
提案中的 EvidenceRef 不是可直接发送的正文或授权。

`BehaviorResult` 字段：
`intent_id/status/reason_codes/score/model_calls/sender_calls/receipt_recorded`。
`sender_calls` 是调用发送端次数，不是送达数量；发送端授权拒绝时也可能为 1。
重复意图返回已有 status 和 `intent_exists`，本次计数为 0。
`succeeded + receipt_recorded=False` 表示发送确认存在，但成功事件落库未确认，
原因是 `success_event_not_recorded`；不能据此重新发送。

## 注入接口

| 回调 | 精确输入和结果 | 必须满足的契约 |
| --- | --- | --- |
| `policy()` | `BehaviorPolicy`，同步 | 每次读取当前不可变配置；不要维护第二套可写配置源 |
| `current(context)` | async → `BehaviorSnapshot \| None` | 从原始实际会话解析当前人格/身份/受众/路由；不把传入 Context 原样包装成已验证 |
| `validate_identity(context)` | async → `bool` | 只接受 `True`；重读当前绑定修订号，缺失/错误/异常拒绝 |
| `validate_evidence(request, materials)` | async → `ValidationResult` | 输入 `MemoryRequest`、`tuple[Material, ...]`；成功必须回传完整且相同的材料元组，禁止偷偷删引用继续发 |
| `materials(request)` | async → `RecallResult`，可选 | 同一请求/用途有界检索，最多 4 条；可接 MemoryGateway.recall；不可信检索结果仍需验证 |
| `availability(context)` | async → `Availability`，可选 | 当前自主可用性；若 snapshot 不提供 NightState，此回调必须包括睡眠和低精力判断，不能误用普通聊天是否阻断的结果 |
| `history(context, period, exclude_intent_id)` | async → `BehaviorHistory` | 上文持久查询；不能以默认零计数代替读取失败 |
| `model(request)` | async → `str` | `GenerationRequest(intent, snapshot, materials, max_output_tokens, max_output_chars)`；只返回正文，不决定收件人或路由 |
| `sender(request)` | async → `SendReceipt \| None` | `SendRequest(intent_id, context, text, authorize)`；分发前调用并服从 `await authorize()`，至多一次底层分发，不内部重试 |
| `record_success(event, generation)` | async → `CommitResult`，可选 | 默认 `store.commit_event`；集成者可原子提交事件与领域投影，但必须沿用原 generation |
| `clock()` | 有限非负 UTC Unix 秒，同步 | 应和 SQLiteStore 使用相同的时钟；测试可控 |

`BehaviorSnapshot(context, affect=BotAffect(), relationship=Relationship(), night=None,
persona_prompt="", route_verified=False, lifecycle_revision="")`：
必须提供当前已验证 Context、原生人格正文、路由核验结果及非空生命周期修订号。
人格正文改变即使 persona_revision 未更新，也会取消旧内容。`current` 返回的完整 Context
与目标不相等就拒绝，包括 Bot、实例、平台、适配器、人格、账号、受众和路由。
所有读取回调在 preview 下必须只读、无模型、无发送；不要在其中推进 night 或提交后台任务。

`model` 适配器负责接入共享 BackgroundRuntime / Provider 预算、准确 Token 计数、
用途配额和实际 Provider 输出上限。本服务限制材料条数、人格+材料字符总数、
输出字符数和调用超时；字符不是 Token。不能把 `queued` 当生成正文返回，
也不要在同一个单 worker 内阻塞等待自己再次提交的工作。
本服务发送预留最多约束本用途的生成次数，不替代其他用途共享的每日模型额度。
把材料当作带来源的数据，不把材料中的指令提升为人格、授权或路由。

## 默认规则与边界

`BehaviorPolicy` 默认：

| 项目 | 默认 |
| --- | --- |
| 总开关 / 模式 / 冲突 | enabled=True / active / conflict=False |
| 自主 / 群主动 / 白名单 | False / False / 空集合 |
| 时区 | None，未显式配置则拒绝 |
| DND / 活动时间 | 当地 01:00–08:00 / 全天 |
| 每日额度 | 全局 6，每 scope 2 |
| 冷却 / 未回复 | 7200 秒；连续 2 次成功或 unknown 后停止，直到人类回复重置 |
| 精力 / 评分门槛 | 20 / 0.35 |
| 意图 TTL / 排队 | 300 秒 / 同库最多 100 个在途及等待任务 |
| 普通依赖 / 模型 / 发送超时 | 10 / 30 / 30 秒 |
| 输入字符 / 输出字符 / 输出 Token 声明上限 | 12000 / 2000 / 512 |

白名单和静音集合均为包含实例/Bot/人格/适配器/平台/会话类型/会话 ID 的
`Context.scope_key`，不是裸群号。私聊的 account 与 audience 还会完整复核。
时段用当地分钟的半开区间，例如 `(60, 480)`，支持跨午夜 `(1320, 60)`；
空 active_hours 表示全时段禁止。可用性和硬否决先于评分，任何低优先级评分都不能越过它们。

评分版本 `behavior-1`：
`0.50 * relationship.normalized + 0.30 * social_need
+ 0.10 * (pleasure + 1) / 2 + 0.10 * (1 - stress)`，保留六位小数。
不直接读取 HumanObservation，不把对方情绪当 Bot 感受。
`evaluate` 硬否决时 score=None，正常评分不过门槛时 `below_score_threshold`。
这是可解释的保守选择规则，不是心理学测量。

未注入 `materials` 时，从自己的有限窗口选择当前同账号、同受众、同修订号的真实人类
互动/已确认 Bot 行为，最多 4 条；不依赖长期记忆。原始梦、日记、观察和未知角色不作真实素材。
长记忆 fact 和有 source_ids 的 summary 必须通过外部最终校验。
素材必须未过期、Bot 持有者匹配、当前受众属于原受众；跨源授权失败会废弃整段文案。
默认不支持将已绑定的其他账号素材自动提升到当前账号，宁可拒绝也不扩大 T4 既有边界。

## 执行与回执

| 阶段 | 代码映射及持久行为 |
| --- | --- |
| 硬否决 / 评分 | `_gates` / `behavior_score`；无模型，不预留 |
| 意图 / 预留 | `create_intent` → `reserve_quota` → pending→reserved；固定 pool=send / purpose=behavior |
| 素材 / 生成 | `_valid_materials`、`_review` → reserved→generating → 一次模型调用 |
| 最终复核 | 全套硬闸门、当前 Context、素材凭据、generation、human_watermark、到期与生命周期；异步验证后再读 |
| 唯一分发声明 | generating→sending 的 SQLite CAS；数据库再次核对人类消息/路由/身份/人格令牌 |
| 发送端授权 | 在 sending 之后再调用 `SendRequest.authorize()`；最后刷新后再次检查人类水位、精力、时区日及时段 |
| 回执 | 完整确认→succeeded；确定未发送→failed；None/timeout/异常/部分结果→unknown |
| 成功事件 | 只在完整确认且成功终态落库后产生 `actor_role=bot, event_type=bot_action_succeeded`，保留真实回执 ID 和素材引用 |

所有用途共用配额；失败、取消、在途和 unknown 都不退款。正在生成的任务跨越当地午夜，
或时区改变，取消旧意图；它占原日期额度，但不会用昨天的预留在今天外发。
之后需要新的有效意图重新评估，不继续旧文案。时钟倒退到创建时间之前、TTL 到期也取消。

`SendReceipt(intent_id, route, status="unknown", receipt_id=None,
confirmed_parts=0, total_parts=1)`：
只有 `status="confirmed"`、完整部分数、非空真实 receipt_id，且 intent_id/route 精确匹配、
发送端确实通过 authorize 时才成功。假 bool、负数、部分确认和不匹配回执全部 unknown。
`rejected` 的语义必须是可信发送端确认没有发送任何部分，不允许把超时/普通异常包装为 rejected。
部分结果不能补发剩余部分；后续重复调用返回持久终态。

小型 `AstrBotBehaviorSender(send_message, make_chain=..., recorded_route=...)`
只消费宿主实际记录的 UMO，重新核对 route 后构建一个文本消息链并授权一次，
不拼接裸 ID，不实现分句/TTS/图片/延迟。v4.29.4 的 `send_message` 返回 False
映射 rejected，True/None 映射 unknown；异常交给服务保守处理。
因此**仅靠这个宿主 API 不会产生成功行为事件**，也不能推进依赖真实成功的入睡收尾。
需要真实平台确认能力时，另注入有可靠相关回执的 Sender，不伪造 ack。

成功确认和成功事件提交之间崩溃可能丢失成功事件；当前没有 outbox 补偿，不自动发送或补造成功。
若发送终态落库失败，服务返回 `behavior_storage_fault`、停用该执行器，
启动恢复将遗留 sending 转为 unknown。普通日志不打印正文、人格提示或完整材料。

## 并发、卸载与恢复

同一事件循环内、相同解析后数据库路径的服务实例共用一条执行队列，含不同 SQLite 连接；
持锁期间可以等待模型/网络，但不持有 SQLite 事务。没有多进程租约或跨宿主执行权。
使用标准路径，不用硬链接/别名绕过同库识别；生产仍应只有一个生命周期所有者。

生命周期所有者启动时在获得独占权后调用 `store.recover_inflight()`；
不要在存活的执行器旁再运行恢复。pending/reserved/generating 被取消，
sending→unknown，既有预留保留。`close()` 先停止新任务、取消并等待已拥有任务；
取消传播不被吞掉。生成中取消→cancelled；进入发送调用后取消→unknown。
之后才能关闭 SQLite；没有后台 scheduler、守护任务或轮询循环需要额外清理。

不可撤销分发开始之后的人类消息不能保证撤回外部平台已接收的消息。
`authorize` 成功不是未来任意时刻的授权票据：发送端等待、排队、分段后必须重新复核，
不得缓存放行结果重用。宿主配置/身份失效通知应与最终分发串行化或更新权威修订号，
`current` 不能返回不可失效的旧缓存。不同系统的异步读与平台网络不是原子事务；
本服务不宣称消除了所有外部平台并发窗口，也不以重复异步读取冒充分布式原子授权。

## 正确性边界

- 安全：相同逻辑意图最多调用一次发送端；unknown 不重发、不退款；
  解绑、人格/路由/受众/清除代际/生命周期失效使整段内容取消。
- 活性：有权且符合硬闸门的任务，在依赖有限时间完成的前提下进入终态；
  异常或重启只收敛到失败、取消或 unknown，不自动恢复旧任务。
- 验证：使用固定时钟、真实临时 SQLite、可控异步交错和发送桩，
  搜索跨午夜、并发、超时、部分结果、人类消息和自我取消反例。
- 宿主边界：AstrBot v4.29.4 `send_message=True` 仅表示匹配平台，
  不是可靠成功回执。仅可信发送适配器提供完整确认才产生成功行为事件。

## 测试与限制

从插件目录执行：

```bash
python3 -m unittest discover -s tests/behavior -v
python3 -m unittest discover -s tests/domain -v
python3 -m unittest discover -s tests/identity/relationships -v
python3 -m compileall -q services/behavior.py adapters/behavior_sender.py tests/behavior
```

另外使用工作区 `.livingemotion-host-t1/venv/bin/python` 运行同一行为测试。
这只是使用宿主 Python 环境，没有启动 AstrBot 或连接任何消息平台。

本次 macOS 实际执行结果：

| 检查 | 环境 | 结果 |
| --- | --- | --- |
| `unittest discover -s tests/behavior -v` | Python 3.11.9 | 52 tests，4.080s，OK |
| 同一行为测试 | 隔离宿主 Python 3.12.16 | 52 tests，3.558s，OK |
| `unittest discover -s tests/domain -v` | Python 3.11.9 | 38 tests，0.847s，OK |
| `unittest discover -s tests/identity/relationships -v` | Python 3.11.9 | 32 tests，0.259s，OK |
| 仅本次代码和测试的 `compileall` | Python 3.11.9 | 退出码 0 |
| 本次实现/测试的宿主 import 与 SQL 文本静态搜索 | 本地 `rg` | 无匹配 |

两次行为测试是同一套 52 项，不计成 104 个不同测试。连同领域/关系回归共 122 个测试用例。
系统 Python 未安装 pytest，未为本任务安装依赖；以上命令全部使用标准库 unittest。

测试以临时 SQLite WAL 存储真实意图、预留、终态、水位和成功事件；
历史查询桩保留已知意图目录，读取公开 `get_intent/quota_usage/human_watermark`，
不创建新 SQL，不替代缺失的生产查询。不声称已覆盖 orphan reservation 索引、
所有清理历史组合或多进程互斥。崩溃窗口通过持久转换后关闭/重开 SQLite 构造，
不是操作系统 kill -9 或断电实验。

| 反例 / 验证 | 结果与修复 |
| --- | --- |
| 最后一次异步上下文读取时出现人类消息 / 跨入 DND | 初版回归断言失败；补刷新后的水位、当前时段及精力复核，复验通过 |
| identity 回调返回字符串 `"false"` | 初版误放行；改为仅接受布尔 True，复验通过 |
| None / 部分确认 / 超时 / 畸形回执 | unknown、额度不返还、无成功事件，跨重启不重新发送 |
| 同意图 20 路并发、同库双连接、不同 scope 并发 | 同逻辑意图一次发送调用；默认全局 6 / scope 2 / 冷却约束通过 |
| 生成中解绑 / 人格与路由变更 / clear / close | 整段内容失效；无旧内容外发；发送中取消保守 unknown |
| 固定种子 20261105 的 24 组交错、每组 3 次重复执行 | 人类/身份/clear 取消；Bot/tool 不自我取消；每意图至多一次发送 |

所有数据均为合成内容，模型与 Sender 都是桩；收费调用 0，真实消息 0。
此专项不修改父规格复选框，不宣称 T5 完整联调、真实发送回执、管理页面、共享模型预算接线、
全插件宿主加载或生产部署已验收；这些交由主集成者及独立验收完成。
