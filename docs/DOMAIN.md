# T3 情绪与关系领域交接

负责人：`/root/emotion_domain`。仅独立新写 `domain/emotion.py`、
`domain/relationship.py` 及对应测试；未修改共享类型、存储、入口、API 或规格复选框。
领域模块由本插件实现，没有 AstrBot 或长期记忆运行时依赖。

## 集成必读

- 共享快照只使用 `contracts.py` 的 `BotAffect`、`HumanObservation`、
  `Relationship`、`RelationshipContribution` 等类型。两个 `*Policy` 是模块内
  规则参数，不是第二套公共状态契约。
- 所有转换都是同步纯函数，无 SQL、网络、模型调用、系统时钟读取和发送。
  `now` 必须由应用层注入有限非负 UTC 秒；不使用随机选择。
- `NightState` 是可选的只读输入，只读取 `energy`；不依赖 `domain/night.py`。
- `runtime` 是必须跨重启保存的辅助元数据。遗漏它会丢失相似刺激计量和日预算。
  Bot runtime 归 `context.scope_key`，关系 runtime 归 `context.account_key`。
- 推荐与快照同一 `StateWrite.value` 保存：
  `{**to_dict(snapshot), "_runtime": result["runtime"]}`。读取时移除 `_runtime`，
  还原嵌套 `EvidenceRef.context`，再构造共享快照。公开查询必须过滤 `_runtime`，
  不将这些内部计量字段注入提示或交给普通聊天。
- Bot、观察、关系及关系贡献与原始事件一起调用 `commit_event`。
  关系和观察的 `record_key` 必须是原来源 `account_id`。CAS 冲突后重读并重算；
  清除代际必须沿用计算开始时的 generation。不能先单独写状态再标记事件。
- `applied=False` 不等于所有返回数据都没变：时间衰减、消费冻结事件、记录被限额
  的事件仍可能更新快照或 runtime。按结果整体持久化，保留原因码。
- 持久 exactly-once 归存储 `event_keys`。领域的有界去重只覆盖有效事件窗口，
  不宣称代替持久幂等。满额返回 `guard_capacity`，不驱逐仍有效的去重键。
- 管理修改需要宿主鉴权后，原子保存快照、版本、贡献和 `audit`。当前已读存储接口
  尚无这个完整管理事务入口；需 foundation/集成者补接，不能将 `actor_id` 当鉴权，
  也不能用两次独立写入冒充审计原子性。
- `resolve_mode(...).may_autonomous` 仅表示模式允许继续评估，不是发送许可。
  自主开关、睡眠、额度、路由、受众和发送前复核仍由行为执行者负责。

## 精确签名

以下类型均来自共享契约，`Mapping`、`Iterable`、`Any` 来自 `typing`。

```python
def apply_emotion(
    state: BotAffect, event: Event, *, now: float,
    observation: HumanObservation | None = None,
    relationship: Relationship | None = None, night: NightState | None = None,
    runtime: Mapping[str, Any] | None = None, model_suggestion: Any = None,
    policy: EmotionPolicy = EmotionPolicy(), enabled: bool = True,
    mode: str = "active", conflict: bool = False,
) -> dict[str, Any]: ...

def decay_affect(
    state: BotAffect, *, now: float,
    policy: EmotionPolicy = EmotionPolicy(),
) -> BotAffect: ...

def observe_human(
    event: Event, *, now: float, previous: HumanObservation | None = None,
    policy: EmotionPolicy = EmotionPolicy(),
) -> HumanObservation | None: ...

def expression_context(
    state: BotAffect, observation: HumanObservation | None, *, now: float,
    enabled: bool = True, mode: str = "active", conflict: bool = False,
    policy: EmotionPolicy = EmotionPolicy(),
) -> dict[str, Any]: ...

def resolve_mode(
    *, enabled: bool = True, mode: str = "active", conflict: bool = False,
) -> dict[str, Any]: ...

def event_signals(event: Event) -> tuple[str, ...]: ...

def apply_relationship(
    state: Relationship, event: Event, *, now: float,
    runtime: Mapping[str, Any] | None = None,
    policy: RelationshipPolicy = RelationshipPolicy(),
    enabled: bool = True, mode: str = "active", conflict: bool = False,
) -> dict[str, Any]: ...

def correct_relationship(
    state: Relationship, context: Context, *, now: float, actor_id: str,
    reason: str, expected_version: int, current_version: int,
    score: float | None = None, frozen: bool | None = None,
    policy: RelationshipPolicy = RelationshipPolicy(),
) -> dict[str, Any]: ...

def project_relationship(
    contributions: Iterable[tuple[Context, RelationshipContribution]], *,
    context: Context, authorized_account_keys: Iterable[str] | None = None,
    identity_revision: str,
) -> Relationship: ...

def relationship_stage(score: float) -> str: ...
```

`apply_emotion` 返回 `affect`、`observation`、`runtime`、`applied`、`control`、
`reason_codes`、`trace`。`apply_relationship` 返回 `relationship`、`runtime`、
`contributions`、`applied`、`reason_codes`、`trace`。trace 有事件关联键、发生/处理时间、
规则版本、前后状态；情绪额外记录持有者、观察对象、置信度，关系记录预算收费量。
trace 含私人状态和来源，只进入认证管理审计，不应打印到普通日志。

`correct_relationship` 返回 `relationship`、新 `version`、`audit`、`contributions`；
版本冲突、无理由、无操作主体、非法分值会抛 `ValueError`。人工操作不返还自动预算，
自动事件不能覆盖更新的人工修正。冻结和解冻也产生版本审计。

`project_relationship` 只能接收保留原 Context 的来源账本，不接受上次聚合快照作为
新证据。默认仅当前来源账号，显式空授权集合则没有来源；跨 Bot/人格一律不聚合。
授权集合来自身份适配器，调用者还需在发送前重新核验当前修订号。历史来源 revision
不是当前授权凭据。解绑只过滤来源，不搬账本。来源不明的 `legacy_score` 不聚合，
未知维度保持 `None`，UI 显示“未知”。

## 冻结规则 V1

情绪规则版本为 `emotion-1`，关系规则版本为 `relationship-1`。
默认 `EmotionPolicy`：观察/事件 TTL 均 7200 秒；四维半衰期依次为
1800/1200/2400/3600 秒；单维单事件增量上限 0.15；相似窗口 300 秒、最多 3 次、
累计最大维度变化 0.30；敏感度 1.0。基线为 `(0, 0.3, 0, 0.3)`。
衰减使用 `baseline + (value-baseline) * 2**(-elapsed/half_life)`。

默认 `RelationshipPolicy`：单事件绝对预算 6、时区日绝对预算 24、事件 TTL 7200 秒；
相似窗口 300 秒、最多 3 次、累计预算 9；时区 UTC。即使正负信号互相抵消、
分数碰到 0/1000 边界，仍收取拟议变化绝对值；不会退回预算。跨午夜迟到事件
按发生日收费，保留仍可接收事件的前一天额度。

两个模块默认去重容量均为 192，配置只能调小；这是为 64 KiB 状态载荷预留快照空间。
相似判定同时使用“来源账号 + 评估标签”和“来源账号 + 归一化正文哈希”，不持久化正文。
不同事件 ID、正文标点变化或模型标签变化不能重开同内容预算。

| 输入 | Bot 评估增量：愉悦/唤醒/压力/社交 | 关系拟议分 |
| --- | --- | --- |
| sadness | 0 / +.03 / +.02 / -.02，派生关心 | +.5 |
| care | +.12 / -.02 / -.06 / -.06 | +3 |
| gratitude | +.10 / +.02 / -.04 / -.05 | +2 |
| conflict | -.12 / +.12 / +.14 / +.04 | -5 |
| apology | +.05 / -.04 / -.08 / -.02 | +2 |
| promise_kept / promise_broken | 有界正向 / 负向评估 | +4 / -6 |
| boundary_respected / boundary_violated | 有界正向 / 负向评估 | +3 / -5 |

信任和边界仅由相应明确事件建立；旧高亲近分不生成这些维度。熟悉度由真实互动建立。
投影中的归一化维度按有证据来源均值计算，不能因绑定两个账号而直接相加到 1。
阶段阈值：`<100 unestablished`、`<300 acquainted`、`<600 familiar`、
`<850 close`、其余 `trusted`；它不是信任维度的替代值。

自由正文只识别少量完整的直接第一人称自述，例如“我很难过”；引用、否定、
第三人称和梦中叙述不作子串情绪识别。适配器可传明确 signals。
`human` 事件必须有与来源账号一致的 actor_id；`bot` 仅接受
`event_type=bot_action_succeeded` 的成功行为，不允许机器人自己给自己刷关系。
梦、日记、摘要、旧未知等来源不作为真实互动。此规则是保守产品逻辑，不是心理学模型。

模型建议格式：

```json
{"rule_version":"emotion-1","delta":{"pleasure":0.05},"confidence":0.8}
```

只接受四维有界增量，最多 4096 字符，可去除单层 JSON 代码围栏。
NaN、Infinity、bool 冒充数字、字符串数字、未知字段、重复 JSON 键、错误版本、
越界及模型错误正文均回退规则；不接受最终 Bot 分数或发送指令。
模型细化按权重的 0.5 混入后再次限幅；对方纯悲伤/焦虑不能直接造成 Bot 愉悦负增量。

## 验证入口与边界

```bash
python3 -m unittest discover -s tests/domain -v
python3 -m unittest discover -s tests/identity/relationships -v
```

2026-11-05 最终本地实测，macOS / Python 3.11.9：

| 命令 | 结果 |
| --- | --- |
| `python3 -m unittest discover -s tests/domain -v` | 38 tests，0.869s，OK |
| `python3 -m unittest discover -s tests/identity/relationships -v` | 32 tests，0.246s，OK |
| `python3 -m compileall -q domain/emotion.py domain/relationship.py tests/domain tests/identity/relationships` | 退出码 0 |

共 70 项：35 项情绪、32 项关系、3 项临时 SQLite 接点。包含 seed=20261105 的两组
各 1000 事件序列，以及原始失败后修复的同正文重分类、跨场景误用、
人工修正被旧事件覆盖、归一化维度叠加和 64 KiB 载荷反例。
`test_persistence_contract.py` 通过公开接口验证重启预算/去重、CAS 重算与清除代际；
测试未编写 SQL。领域模块的静态导入检查只有标准库、本插件共享契约及本地领域辅助函数。

这些测试均为合成数据，无真实用户内容、收费模型或外发消息。不表示真实宿主已联调，
也不表示管理鉴权/审计落库、完整 API 接线或生产部署已完成。
