# T5 长夜与醒后补课交接

范围：独立新写 `domain/night.py`、`services/catchup.py`、`tests/night/`、
本文档。共享类型、存储、入口、情绪/关系、规格复选框均未修改；未执行 Git 提交。
没有读取或复制从绫函数、提示词或素材。运行模块只依赖标准库与本插件 `contracts`，
没有 AstrBot、长期记忆、数据库、模型、系统时钟、后台循环或发送依赖。

实施阶段：已批准 apply。专项 `state-machine-correctness`，置信度高；
验证对象是时间推进、真实回执、来源范围与持久化边界，不是生产宿主联调。
生产接线责任交 `emotion_foundation`，实际发送仍只归 T6。

## 正确性边界

安全性：

- 精力唯一由 `domain/night.py` 写入；补课只改 `unread_watermark`。
- 所有输入时间为有限非负 UTC Unix 秒；每段 elapsed 只结算一次，精力保持 0..100。
- 收尾必须匹配真实成功回执。失败、取消、unknown、其他会话、旧修订或过期回执不入睡。
- 睡眠阶段只由绝对睡眠开始时间派生；重启不重放晚安、梦境或自主消息。
- 正文仅来自本地窗口中可靠的真实人类 `message`；摘要不能再次作为原始证据。
- 水位不回退，固定本次醒来上界；页数、来源数、字符数和持久载荷均有上限。
- 可选意图以摘要/代际生成稳定 ID；unknown 不重试，重复执行归 T6 的持久意图闸门。

活性：

- 到绝对 `wake_at` 自然醒；即使恢复记录缺少醒来时间，也受最大睡眠时长保护。
- 收尾超时取消待入睡，而不是假装发送成功。再次尝试须由调用方明确发起新请求。
- 醒后过渡到期必定结束，补课失败、无记忆、窗口为空都不能延长它。
- 重复叫醒、重复恢复和重复回执不会重置现有醒后截止时间。

时钟假设：回退时使用 `max(now, updated_at)`，不扣负时间、不重复回血、不反转阶段；
手动睡醒及回执在回退区间不新增转换。截止时间不往后移动。若宿主要求在系统 UTC
持续错误时仍按物理秒结束，须注入经单调时钟校正的 UTC；本模块无法从一个回退的
UTC 数值推断真实 elapsed，不能直接传 `monotonic()` 数字冒充 UTC。

## 状态与规则

| 起点/输入 | 结果 | 代码入口 |
| --- | --- | --- |
| 清醒，精力 <= 30 | 困倦 | `advance_night` / `apply_interaction` |
| 清醒/困倦，有待收尾回复 | 入睡待收尾 | `begin_sleep`，传 request/message ID |
| 清醒/困倦，无待收尾回复 | 直接睡眠 | `begin_sleep`，计划睡眠或 `manual=True` |
| 入睡待收尾，匹配成功回执 | 睡眠 | `apply_reply_receipt` |
| 入睡待收尾，失败/取消/unknown/其他范围 | 保持待收尾，直到成功或超时 | `apply_reply_receipt` |
| 入睡待收尾，超时或叫醒 | 取消收尾，回清醒/困倦 | `advance_night` / `wake_night` |
| 睡眠，到醒来时间/叫醒/手动醒来 | 醒后过渡 | `advance_night` / `wake_night` |
| 醒后过渡，补课完成/截止到期 | 清醒或低精力困倦 | `finish_waking` / `advance_night` |
| 任意状态，关闭作息 | 清醒，清理睡眠/待回执/截止字段 | `enabled=False` |

`night-1` 默认：清醒消耗 4 点/小时，睡眠恢复 12 点/小时；
最长睡眠 57,600 秒，收尾等待 120 秒，醒后过渡 300 秒。
入睡等待、困倦和醒后过渡按清醒速率计费。关闭作息先结算旧状态至当前时刻，
再清理控制字段；关闭期间不入睡、不计互动额外消耗，但继续结算清醒 elapsed。

精力公式为 `clamp(energy + elapsed / 3600 * rate, 0, 100)`。
跨醒来点必须先结算睡眠并限幅，再结算醒后清醒消耗，不能先净额相抵。
没有待收尾时使用绝对 `now < wake_at <= now + max_sleep_seconds` 表示睡眠窗口；
因此午睡、跨午夜不依赖日期字符串或 tick 次数。当地时区/DST 的计划转换归宿主，
这里只接明确的 UTC 窗口，不自行猜下一次作息计划。

阶段模型每 5,400 秒循环：`[0,300) N1`、`[300,1500) N2`、
`[1500,3600) N3`、`[3600,5400) REM`。这是产品规则，不是生理测量。
T7 读取已推进的 `NightState.sleep_stage`，自己执行 REM/每夜次数/预算限制。

`recovering=True` 只用于启动恢复：若保存时仍在睡眠、现在已过醒来点，精力仍按
历史睡眠/清醒分段结算，但给当前恢复一次 `now + waking_timeout` 的补课窗口。
保存状态本来已是 waking 时不能延长原 deadline。常规定时推进不用该标记，
跳过整个醒后窗口时直接结束过渡。所有入口都不生成或发送离线积压动作。

互动额外消耗默认每条 0.2 点、滑动 300 秒最多 2 点，事件 TTL 7,200 秒。
运行元数据包含 scope、最多 192 个去重键及 192 条非正文计费记录，不能丢弃仍有效
去重键来接收新事件；满额返回 `guard_capacity`。仅可靠人类 `message`、
来源账号与 actor 一致、当前 scope/修订/受众一致的事件计费。
睡眠/醒后消息不自动叫醒，也不额外扣精力。迟到但未过期的互动按接收时滑动预算
计费，过期事件拒绝；持久事件 exactly-once 仍依赖 `commit_event`。

## 精确接口

以下公开类位于 `domain/night.py`；全部函数同步、纯计算。
`Context/Event/NightState/Availability/IntentStatus` 使用冻结共享类型。

```python
NightPolicy(
    awake_cost_per_hour: float = 4.0,
    sleep_gain_per_hour: float = 12.0,
    drowsy_threshold: float = 30.0,
    max_sleep_seconds: float = 57600.0,
    settling_timeout: float = 120.0,
    waking_timeout: float = 300.0,
    interaction_cost: float = 0.2,
    interaction_window: float = 300.0,
    interaction_budget: float = 2.0,
    event_ttl: float = 7200.0,
    dedup_capacity: int = 192,
)

ReplyReceipt(
    context: Context, status: IntentStatus, occurred_at: float,
    request_id: str | None = None, message_id: str | None = None,
)

def sleep_stage(sleep_started_at: float, *, now: float) -> str: ...

def advance_night(
    state: NightState, *, now: float, policy: NightPolicy = NightPolicy(),
    enabled: bool = True, recovering: bool = False,
) -> NightState: ...

def begin_sleep(
    state: NightState, context: Context, *, now: float, wake_at: float,
    request_id: str | None = None, message_id: str | None = None,
    manual: bool = False, policy: NightPolicy = NightPolicy(), enabled: bool = True,
) -> NightState: ...

def apply_reply_receipt(
    state: NightState, receipt: ReplyReceipt, *, now: float,
    policy: NightPolicy = NightPolicy(), enabled: bool = True,
) -> NightState: ...

def wake_night(
    state: NightState, *, now: float, reason: str = "called",
    policy: NightPolicy = NightPolicy(), enabled: bool = True,
) -> NightState: ...

def finish_waking(
    state: NightState, *, now: float, policy: NightPolicy = NightPolicy(),
    enabled: bool = True,
) -> NightState: ...

def night_availability(
    state: NightState, *, now: float, block_chat: bool = False,
    exempt: bool = False, enabled: bool = True, policy: NightPolicy = NightPolicy(),
) -> Availability: ...

def apply_interaction(
    state: NightState, event: Event, *, context: Context, now: float,
    runtime: Mapping[str, Any] | None = None, policy: NightPolicy = NightPolicy(),
    enabled: bool = True,
) -> dict[str, Any]: ...
```

`apply_interaction` 返回 `night/runtime/applied/cost/reason_codes/rule_version`；
`applied=False` 仍可能结算时间或更新去重记录，须整体持久化。
首次新建状态必须使用 `NightState(updated_at=now)`，不要把默认时间 0 当本次启动。
`reason` 仅接受 `called/manual`。`manual=True` 不得同时提供回执 ID；
已有 settling/asleep/waking 时 `begin_sleep` 不替换其窗口或重置等待时间。

回执关联保存在冻结的 `awaiting_reply_id` 中，是带版本、注册时刻和两种散列键的
短 JSON，不是裸请求 ID。散列包含 scope（实例/Bot/人格/适配器/平台/场景）、
人格/身份修订及受众。可以只登记 request 或 message；两者均登记且回执均提供时，
两者必须一致；只提供其中一个时该键必须匹配。回执时刻须在注册之后、当前时间之前，
在截止时刻到达已算超时。延迟收到的成功回执从本次接受时入睡，不回改已结算的精力。

`ReplyReceipt` 是可信适配器传入的“传输已证实成功”，不是聊天正文的成功声明，
也不是模型生成完毕、入队或部分发送。可信边界外不能自行构造该对象获得推进权。
旧裸 `awaiting_reply_id` 无法证明完整关联，一律不匹配。取消待收尾可调用叫醒入口；
旧回执后到仍不会重新入睡。

`Availability.available=False` 表示自主行为此时不适合，并不等于阻断正常聊天。
**原生聊天消费者只消费 `block_chat`**，默认始终不因睡眠阻断；显式开启时
settling/asleep/waking 才阻断。叫醒和已认证管理入口由适配器设置 `exempt=True`；
用户消息中的 `admin=true` 不是认证。此层不执行发送或聊天拦截。

以下公开类和函数位于 `services/catchup.py`：

```python
CatchupPolicy(
    max_rows: int = 200, max_messages: int = 16,
    max_excerpt_chars: int = 160, max_summary_chars: int = 2048,
    max_batches: int = 3, max_age_seconds: float = 86400.0,
)

CatchupSummary(
    summary_id: str, body: str, evidence: EvidenceRef,
    sources: tuple[EvidenceRef, ...], generation: int,
    wake_key: str, through_seq: int, high_watermark: int,
)

def build_catchup(
    state: NightState, context: Context, rows: Sequence[Mapping[str, Any]], *,
    now: float, high_watermark: int, generation: int,
    runtime: Mapping[str, Any] | None = None,
    policy: CatchupPolicy = CatchupPolicy(),
) -> dict[str, Any]: ...

def catchup_intent(
    summary: CatchupSummary, state: NightState, context: Context, *,
    now: float, generation: int,
) -> BehaviorIntent | None: ...
```

`build_catchup` 返回 `night/runtime/summary/applied/has_more/reason_codes`；
处理一页时另有 `skipped_rows`。`summary` 为 `CatchupSummary | None`，
不是外部模型响应；`body` 是编号、截断、压缩空白的原话摘录，不推断事实。
每行编号对应 `sources` 的下标。它仍是未信任资料，不能作为系统指令注入。
非法输入抛 `ValueError`；不在醒后窗口时不消费水位。`applied` 仅表示游标前进，
不是事务 accepted；即使为 false，清理过期正文后的 runtime 也应保存。

## 补课窗口与来源

每次醒来默认最多 3 页，每页读取最多 200 行、收录最多 16 条、每条摘录最多
160 字符、每页最多 2,048 字符。醒来上界第一次取 `high_watermark` 后冻结，
之后新增消息留给正常对话，不无限追赶。按上限可配置为 8 页、32 条、
512 字符/条、4,096 字符/页；行数不得超过 200。

`rows` 必须是当前 scope 的 `read_window` 原样、按 seq 严格递增的第一页，
从当前 `unread_watermark` 之后读取；**不可预先过滤、截短或取尾部页**。
`read_window(limit=policy.max_rows)` 的实际分页上限必须与 policy 一致。
一整页不能证明窗口读完；短页或出现超过冻结上界的行才证明后面没有保留行，
这时允许越过清理形成的 seq 空洞到已知上界。不把“未读但超预算”的行标成已读。

页预算耗尽时停止本次补课，保留剩余未读水位供后续正常消费/下次醒来处理；
不会为追赶延长醒后 deadline。没有行也正常完成，不依赖长期记忆后端。

原始 `EvidenceRef` 使用 `provider=livingemotion.local`，
`source_id=event.idempotency_key`、`source_ids=(event.source_id,)`，保留原 Context、
人类 subject/holder 和有效期；路由从证据中移除。摘要 ref 使用
`provider=livingemotion.catchup`、`kind=summary`，subject/holder 为 Bot，
`source_ids` 映射到原始 ref。当前 scope/修订/受众不一致、来源行与事件键不一致、
伪造 actor、非 message、梦/日记/摘要、未来/过期素材全部跳过。
摘要有效期不超过任一原始引用，不因二次摘要刷新 TTL。

单个来源 JSON > 8,192 字符会跳过（保留可观测 skipped 计数）；
本页来源 JSON 累计 > 16,384 时停止本页；完整 `_catchup` 的严格 JSON
上限 32,768 字符，超限拒绝而不提交水位。只保留最后一页摘要，不积累正文历史。
离开 waking、到期或摘要来源到期时，再调用 `build_catchup(..., rows=[])`
会清理 transient summary；runtime 的完成标记仍保留，不能因此重新补课。

`catchup_intent` 只是可选 T6 交付物，不自动调用。要求当前 waking、未过期、
一致的醒来键/代际/来源修订/受众、有当前路由，且本地游标已覆盖摘要。
返回 `purpose="wake_catchup"`、`status=pending`，稳定键包含摘要 ID 和 generation；
`human_watermark` 是本次醒来冻结的上界，不是本页末尾 seq。
无路由返回 None，不猜发送目标；有路由字符串也不代表已经通过宿主授权。
不产生“正在爬楼”公告，没有任何第二发送器或模型调用。

## emotion_foundation 接线

1. 每个 `context.scope_key` 独立读取 `kind="night"`、`record_key=""`。
   同一 value 建议保存
   `{**to_dict(night), "_interaction": interaction_runtime, "_catchup": catchup_runtime}`；
   解码先移除这两个内部字段再构造 `NightState`。公开快照必须滤除内部正文、
   来源、去重键和 `awaiting_reply_id` 的内部关联内容，不作为普通提示直接公开。
2. 正常聊天链路必须维护“确实读过的消息 seq”。`unread_watermark` 不等于当前
   最新入站消息：不要一收到人类消息就把它标成已读。完成一次原生请求后只能确认
   该请求实际消费的连续范围；睡前保留这个游标。T5 不猜宿主已经读过哪些消息。
   入睡前后默认原生聊天仍可回复，所以正常链路的已读推进也要与补课共用 CAS。
3. 初次恢复读出状态后调用 `advance_night(..., recovering=True)` 一次并保存；
   常规 tick 使用默认 False。计划器负责一天/一个窗口只发起一次入睡请求，
   不得在收尾超时后每个 tick 自动重发晚安。本模块不持有计划器或晚安发送权。
4. 真实互动用 `apply_interaction`，与事件及 `_interaction` 一起 `commit_event`；
   仅提交 accepted 后视为更新成功。所有时间/手动/回执更新调用 `write_states`，
   使用旧 `generation` 和 `StateWrite(expected_version=record.version)`。
   CAS 冲突重读重算；清除代际变化直接丢弃旧任务，不重新获取代际继续写旧结果。
5. 开始补课先读 `human_watermark(context)`，再以当前游标读取
   `read_window(context, after_seq=state.unread_watermark, limit=policy.max_rows)`；
   把结果交 `build_catchup`。水位、冻结上界、页计数、摘要与来源必须在**同一次**
   `night` CAS 提交。不要先推进游标再另存摘要，也不要用未提交结果对外回复。
6. `has_more=True` 才继续下一页，每次重查当前 state/版本/原代际/作息开关。
   空页、预算耗尽或摘要失败均可结束；到期必须调用 `advance_night` 结束过渡。
   关闭作息、离开 waking、TTL 到期时调用空页清理并保存 runtime，避免摘要正文
   无限留在状态里。窗口清理与状态清理都由同一工程所有者接线。
7. 可选补答：只在已提交补课结果上创建稳定意图，`create_intent` 的实际成功状态
   是 `created`（不是事件的 accepted），重复为 `duplicate`。可先持久意图，
   再 `finish_waking` 让单一发送端评估正常 awake/drowsy 可用性。
   T6 必须继续检查自主开关、白名单、路由、配额、人格/身份/受众、新人类消息、
   夜间状态及来源 TTL；本意图不是绕过 waking 硬闸门的特权。
   重启后已有 pending/在途任务按 T2/T6 恢复策略取消或 unknown，不自动补发。
8. 默认没有模型依赖；当前仅实现本地摘录，没有额外记忆检索。若未来接可选外部材料，
   不能扩大本地已读游标或把摘要当成原始互动。

宿主认证、真实成功回执生产者、调度器、正常已读确认、配置入口和后台清理的实际
接线未在本次范围内实现。测试中的临时存储调用只是冻结端口验证，不代替生产接线。

## 验证证据

2026-11-05，macOS / Python 3.11.9；只使用合成数据和临时 SQLite，
没有收费模型、真实用户正文、网络发送或生产迁移。

在新插件根目录运行：

```bash
python3 -m unittest discover -s tests/night -q
.venv/bin/python -m pytest tests/night tests/domain tests/identity/relationships tests/contracts tests/storage tests/runtime -q
python3 -m compileall -q domain/night.py services/catchup.py tests/night
```

| 检查 | 最终实测 |
| --- | --- |
| T5 独立 unittest | 88 tests，0.633s，OK |
| T5 + 既有情绪/关系单独回归 | 158 passed，1.67s |
| T5 + 情绪/关系/契约/存储/运行时联合回归 | 214 passed，3.12s |
| compileall（仅自有模块及测试） | 退出码 0 |
| ruff | 未完成：项目虚拟环境和系统 Python 均没有该模块，未安装或修改依赖 |

T5 88 项组成：47 项长夜/回执/互动、34 项补课/来源/意图、
5 项临时 SQLite 接点、2 项 AST 所有权检查。
158 项含原有情绪/关系 70 项，联合回归数量包含这些测试，不应重复累加。
AST 检查确认两运行模块只导入标准库及共享契约，补课没有 energy 写入或发送调用。

一次中间联合回归出现 `test_schema_migration_failure_rolls_back` 断言
`2 == 1` 失败：并行工作已新增第二个迁移，但当时旧测试仍硬编码 1。
只读复核时该测试已更新为 `len(MIGRATIONS)`，随后 214 项联合回归全部通过。
本代理未修改存储、共享类型或该存储测试。

测试映射：

| 检查点 | 本地证据 |
| --- | --- |
| C28 精力单写、完整状态、阶段 | `test_night.TimeTests`、`test_boundaries.OwnershipTests` |
| C29 午睡/跨日/回退/重启 | `TimeTests`、`GeneratedTraceTests`、`test_persistence` |
| C30 成功回执关联 | `ReceiptTests`，全非成功状态及跨 scope/修订反例 |
| C31 过渡有界/原生聊天默认放行 | `ControlTests`、离线恢复 deadline 测试 |
| C32 有界未读/映射/去重 | `test_catchup` 的窗口/来源/意图测试及临时存储测试 |

固定 seed=20261105：2,000 步时钟/回执/睡醒交错；100 组随机时间分段与一次结算
等价性；100 组跨页重启/预算/来源不重复模拟。重复、乱序、回退、取消、unknown、
窗口过期空洞、CAS 冲突、清除代际、旧醒来摘要和无路由均有反例测试。

反例记录：初次存储意图用例因合成 Context 无 route 返回 `missing_route`，
测试还误期待 `accepted`。核对冻结实现后修正为测试专用核实路由和 `created`，
同时增加缺路由不生成意图的逻辑。旧醒来摘要可跨批次误用及 transient 正文保留风险
在实现检查中通过 wake_key/generation/已提交游标校验、过渡结束/TTL 清理收敛。

运行时观测建议只记录 phase、规则版本、reason_codes、scope 散列、seq/水位、页数、
CAS/代际拒绝和 deadline；不要打印回执关联正文、摘录、源账号或完整 runtime。
发现不合法数值、状态字段不完整、超限/乱序窗口时拒绝本次更新，保留原聊天链路。
本地通过不等于 C28-C32 的宿主全链路验收，规格复选框保持原状。
