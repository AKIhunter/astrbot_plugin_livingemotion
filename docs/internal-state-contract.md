# P1/P2 状态集成契约

日期：2026-11-06。仅进程内可信集成；不把这些写端口开放给模型或未认证 HTTP。
`Context.scope_key` 与事件幂等保持原样。情绪/精力所有者按实例/人格共享或按真实会话；
观察、关系、消息、正文、记忆及额度仍按真实来源保存。

## 配置

- `persona_shared_state`：新配置默认 true；`Config.from_mapping` 缺少此字段时 false。
- `night_policy_version`：新配置默认 2；旧配置缺失字段解析为 1。
  版本 2 未设置 IANA `timezone` 时为待配置兼容路径，不启用五档；开启计划作息必须
  有时区。`allow_sleep=false` 不阻断聊天。
  已保存 v2 状态在关闭计划作息并清空时区后保持原精力、窗口与尝试，不退回 v1
  计算；睡眠仍启用时拒绝新回复并提示配置时区。恢复有效时区后继续绝对时间推进。
  启用计划作息却清空时区属于非法配置，沿用原关闭式失败处理。
- 版本 2 时间：`nap_enabled/nap_start/nap_end`，`fatigue_start/fatigue_end`，
  `deep_sleep_at`，既有 `wake_at`（基础起床）。恍惚转困取疲劳开始至沉睡的绝对时间中点。
- `lie_in_min_minutes/lie_in_max_minutes` 默认 0/90，只抽一次持久化。
- `wake_mode=chat|never|both`；both 的群唤醒必须由宿主认证原生 @Bot。
  `wake_reply_limit=3`，`wake_window_minutes=10`。
- `energy_reply_cost=4.0`、`energy_fatigue_per_minute=0.8`、
  `energy_recovery_per_minute=1.5`，0.1 步进；精力上限 100 不可配置。
- 集成字段：`catchup_enabled/catchup_reply_enabled`、`closing_enabled/closing_random/
  closing_lead_minutes`、`diary_provider_id/dream_provider_id/catchup_provider_id/
  closing_provider_id`、`home_city`、`embedding_provider_id/livingmemory_enabled/memory_write`。
  这些字段的实际模型/记忆/天气/收尾行为由对应 agent 接入，不由 P2 自动调用。

## 状态模式

1. 对真实 Context 调用 `await app.initialize_state_scope(context)` 或
   `await store.initialize_state_mode(context, shared=config.persona_shared_state)`。
   新人格首次初始化；已有模式不会被这个函数偷偷切换。
2. 配置修改按人格调用一次 `await store.switch_state_mode(context, shared=bool,
   expected_revision=owner.revision, actor_id=认证操作者, reason=...)`。
   返回 `status/reason_code/revision`；旧 revision 返回冲突，不自动重试。
3. `store.state_owner(context)` 返回 `StateOwner`，包含模式 revision 和 owner generation。
   `read_projection` 仍返回 `(来源generation, records)`；records.owner、StateRecord.owner
   是此次读取票据。`StateWrite(..., owner=该票据)` 在同一提交事务验证。
   内置Projector通过 `store.project_snapshot(context, calculate)` 在单SQLite worker
   完成读取和有界纯计算；回调不得包含模型、异步等待或其他I/O。原 `read_projection`
   返回结构保持。投影输出携带原读取票据，后续提交仍独立复核CAS与代际。
4. 未初始化的旧调用继续原场景路径，便于 v1 消费兼容。初始化之后，写入缺少 owner
   会拒绝（首次初始化、未切换的 v1 场景直写兼容）。投影、夜间运行时已挂接；
   其他异步 Bot 写者也必须传原始 owner，不能临写前取新票据。
5. 切换保存两套历史，另一模式首次从当前来源继承情绪数值；采用有效状态最保守阶段、
   最低精力、最长起床限制和已有回复窗口/轮数限制。取消旧在途行为，不删除额度。
   `clear_scope` 同时失效来源/所有者代际；共享数值不因清除一个来源恢复到满精力。

## 回复与睡眠

Application 必须删除自行定义、遮盖 NightRuntime 的 `night_snapshot/availability`。
`advance_scope(context, recovering=False, action=None)` 的 v1 路径保留原补课；
v2 仅驱动五档/精力，FullCatchupService 由 Application 独立接入。

- `await reply_started(context, reply_id, expected_generation=None)`：每次真正开始生成前
  调用，返回 `{allowed,status,reason_code,ticket,night}`。成功占一轮，不扣回复精力。
  调用失败也已经占轮；重复 ID 不再获准。判定/向量/日记/梦境/阅读摘要不调用。
- `await reply_submitted(context, reply_id, ticket=原票据)`：最终回复第一次进入宿主输出
  流程前调用，先复核模式/来源/人格/路由/沉睡/绝对窗口；成功扣一次精力并从首次提交
  开启窗口。不是送达确认。重复提交不再扣；分段/TTS/图片复用同一逻辑回复 ID。
- 最后一轮开始后不再开放下一轮，但原已开始票据可提交；到沉睡或窗口过期优先拒绝。
- `await store.reply_failed(context, reply_id)` 标记失败，不退轮，不开启窗口或扣回复精力。
- `begin_reply(context, attempt_id)` 与 `submit_reply(context, submission_id, attempt_id=None)`
  是 bool 包装；后者恢复持久票据。默认 submission_id 必须等于原 attempt_id。
- `await wake_attempt(context, normalized_event)`：真实人类消息，返回同形状 allowed。
  两骰仅首次低精力有效尝试抽取并保存和；之后 +1，>8 成功；重复消息不加一。
  沉睡既不抽骰也不累计。成功后低精力为 groggy，不强行改精力。
- bool 包装 `try_chat_wake(context,event_key,is_private,native_at_bot)` 先按原事件幂等键
  从自身归档复核来源；原生群 @ 标志只能由宿主可信入口传入。没有合格事件即拒绝。
- 管理员用已认证控制台调用 `advance_scope(action="night.wake"|"night.sleep")`；
  普通消息不能调用这个绕过端口。`exempt` 不绕过 v2 沉睡。
- `confirm_reply` 只保留 v1 送达后收尾语义，v2 不以它代替提交；`mark_request_read` 的
  v2 路径由 full catchup 接管。tick 推进前可选调用 `maybe_close_conversation(context)`。

`bot_reply_submitted` Event ingest 只归档；v2 人类消息也不扣精力。回复扣费只在提交端口。
`NightState.phase/energy` 保留 v1；新增 `display_state` 五档、cycle/lie-in/点数/轮数/窗口字段。
整数 `energy_units` 为 0..1000，`energy_remainder/energy_direction` 结算亚 0.1 时间余量。

## 控制台与存储

`await store.energy_history(context, owner=None, since=None, until=None,
category=None, page=1, page_size=10, buckets=1440)` 返回逐事件 `items`、桶极值 `curve`、
`total/page/page_size/collected/since/until/owner_key`。默认 24h，无历史为 collected=false。
category：reply/fatigue/recovery/sleep/wake/manual/config；默认 7 天、最多 20000 条。
数值事件与状态同一事务；来源只有真实 scope/ID，不含正文。
跨人格/多所有者的管理聚合由已认证 Console 选择真实 Context 后有界组合，不伪造全局路由。

关系 API agent 的 `storage/console_data.py` 为独立函数模块，无需类 mixin：
Application 在授权关系读取后调用 `apply_relationship_override`；该文件未由 P2 修改。
情绪 refinement 必须携带 Projector.refinement.state_owner；异步模型返回后与写事务再复核。

## 冻结验证

P1/P2 源码与接口已冻结；按主协调者要求暂停源码修改，只补本文验证记录。

- Python 3.12.16：负责范围 `tests/storage tests/night tests/contracts tests/migration
  tests/verification/test_migration_cli.py tests/integration/test_retro_reply.py` 303 项通过。
  其中迁移与 CLI 独立执行 92 项通过；数字不可相加。
- 新规则覆盖五档/午休/跨午夜、赖床重启不重抽、无效与沉睡消息不抽骰、
  两骰后递增、10%阈值、最后一轮可提交、首提窗口不续期、失败占轮、
  清除/切换/身份变化旧票据、重启不退轮、allow_sleep 与管理员操作。
- 来源测试覆盖共享数值但不共享私密证据/正文/观察，实例与人格隔离，
  模式切回不提高精力/缩短起床/重置额度，来源清除阻止另一场景旧 owner 写回。
- Ruff 对负责源码、新测试与迁移文件通过；源码编译通过。
- 添加式 schema v3 已固定；离线迁移只允许精确 v2/v3 指纹，未知版本、列、
  索引或触发器仍拒绝；旧 v2 导入/验证/随后运行时升级实测通过。

**下列为首轮性能失败记录，后续修复与最终复验另列，不删除旧结果。**

冻结报告：`.ci-results/p2-state-modes-performance-frozen.json`。
每模式 10000 真实 API 预热、10000 测量事件、50 会话、20 并发任务、
10000 API 读取。测量源码前后哈希一致，不含模型/网络/发送。

| 模式 | 测量提交 | 状态写入 | 提交 p95 | 50ms 门槛 |
| --- | --- | --- | --- | --- |
| 分场景 | 10000/10000 | 40000 | 54.677667ms | FAIL |
| 人格共享 | 10000/10000 | 40000 | 56.327875ms | FAIL |

读取 p95 均不超过 6.023ms；正文 10000 条、单会话 200 条，WAL、
synchronous=FULL（2）、integrity_check=ok 均保持。较早性能失败报告仍保留，
不以短诊断或先前单次达标替代本冻结结果。

首轮之后，`.ci-results/p2-state-modes-performance-final-3.json` 两模式完整通过：
分场景提交 p95 45.482417ms、共享 42.787542ms；各10000提交/40000状态写入，
读取最高 p95 4.258958ms，源前后不变，WAL/FULL、正文容量与 integrity=ok。
这是专用 worker 修复之前的结果，仍需和最终源码统一复验。

默认入口后续完整失败52.250125ms与53.606125ms均保留。
进一步修复减少基础数值分派及重复去重扫描，并让单连接使用单 worker；
逐值校验、192条历史、有界16MiB页缓存、取消 drain 和持久性均保留。
线程在关闭或初始化失败时释放。最终三种模式报告统一记录在
[改版验收](verification-retro-final.md)，产品修改后 P8 必须重新冻结。

### 本轮最终联合复验

2026-11-06：完整可移植回归1449项通过；三模式完整性能均通过，
旧入口47.454167ms、分场景44.336042ms、人格共享42.299291ms。
每种模式10000真实API预热/10000测量/40000状态写入及10000读取，
源码前后不变；有界16MiB页缓存、WAL/FULL与正文容量保持。
单worker完成纯投影和JSON编码，常规成熟状态使用原子版本UPDATE。
自定义值保留原深拷贝语义，取消期间读取仍等待在途纯投影完成；
清除、过期票据、旧版本及部分写入事务回滚回归均通过。
