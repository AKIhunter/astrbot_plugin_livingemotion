# T1 冻结接口 v1

共享类型唯一入口：`astrbot_plugin_livingemotion.contracts`。同插件内使用
`from ..contracts import ...`（根模块使用 `.contracts`）。无 AstrBot 依赖。

- `Context(bot_id, persona_id, adapter_id, platform, scene_kind, scene_id,
  account_id="", persona_revision="0", identity_revision="0", audience=(), route=None,
  instance_id="local")`。
  `scene_kind` 是 `private/group`。`scope_key` 含宿主实例、Bot、人格、适配器、平台、场景类型/ID；
  `account_key` 额外包含来源账号。修订号不改变存储键。route 必须由宿主核实，字符串本身不是授权。
  新增 instance_id 为末尾兼容字段；local 仅用于纯领域构造/测试，不代表真实宿主。
  宿主通过 `SQLiteStore.get_instance_id()` 获取持久随机 ID（同库重启不变）；
  `plugin.api.get_capabilities()["instance_id"]` 提供给 adapter/消费者组装 Context。
  实际生命周期的 facade 拒绝不匹配实例，不把默认 local 自动提升为当前宿主。
- `Event(event_id, producer, event_type, context, actor_role, occurred_at,
  source_id, actor_id="", body="", signals=(), confidence=1, evidence=(),
  reliable_source=True, rule_version="1")`；`DomainEvent` 同值别名。
  `actor_role=bot/human/unknown`，事件来源复合键不使用正文或秒时间。
- `EvidenceRef(provider, source_id, context, subject_id, holder_id, kind,
  occurred_at, expires_at=None, sensitive=True, exportable=False,
  authorization=None, source_ids=())`。context 持有受众、人格和身份修订号；
  summary 必须携带原始 source_ids。authorization 是提供者凭据，不是 admin 标记。
- 分型快照：`BotAffect`（pleasure/arousal/stress/social_need，不含精力），
  `HumanObservation`（subject_id/labels/confidence/occurred_at/expires_at），
  `Relationship`（score 0..1000/normalized/未知维度/身份修订号），
  `NightState`（phase/energy/绝对时间/回执 ID/未读水位）。
- `RelationshipContribution(source_id, account_id, occurred_at, delta,
  reason_code, day, dimension="score")` 是不含正文的来源账本。
- `BehaviorIntent(intent_id, context, purpose, created_at, expires_at,
  generation, status=pending, human_watermark=0, evidence=(), reason_codes=())`。
  状态为 pending/reserved/generating/sending/succeeded/failed/cancelled/unknown。
  对照规格的粗粒度命名：attempting 对应 sending，sent 对应 succeeded；
  reserved/generating 细分 pending，不增加第二个发送所有者。
- `Experience(experience_id, context, kind, period, created_at, body, ...)`，
  kind 仅 diary/dream；period 由体验服务使用人格时区的日期/夜 ID。
- 所有时间是 UTC Unix 秒，有限非负；修订号是不可解释的字符串。
  `to_dict` 用于边界输出，`canonical_json` 严格拒绝 NaN/Infinity。

## 存储接点（T2 实现）

`storage.SQLiteStore(path, ...)`，异步 `open()/close()`。
`get_generation(context)`；清除后所有在途写入必须携带原 generation。
`get_state(context, kind, record_key="") -> StateRecord | None`。
`commit_event(event, expected_generation, writes=(), contributions=()) -> CommitResult`：
事件、幂等标记、多个状态和关系证据同一事务；仅提交后 accepted。
`StateWrite(kind, value, expected_version=0, record_key="")` 是 CAS 更新。
kind 白名单 bot/observation/relationship/night；对方及关系必须用 account_id 作 record_key。
状态计算在事务外进行；版本冲突后调用方重新读取/计算，不能盲重发旧增量。
`write_states(context, expected_generation, writes)` 给时间/后台更新使用。
`clear_scope(context, expected_generation, *, reason_code="operator_clear")` 原子清除并加代际。
`read_window(context, *, after_seq=0, limit=200)` 返回按递增 seq 排列的有限正文及来源。
`human_watermark(context)` 只统计 human 事件；`relationship_ledger(context, *, day=None)`
只读当前 account_id 来源贡献，不在存储层做身份合并。

`reserve_quota(reservation_id, context, expected_generation, *, period, purpose,
limit, units=1, pool="model", global_limit=None, scope_limit=None,
min_interval_seconds=0)` 在副作用之前调用。
返回 status=reserved/duplicate/rejected，只有 reserved 允许首次执行；
同一 pool/period 的全局上限和 purpose/scoped 上限同事务检查。
min_interval_seconds 按原来源场景跨重启检查；运行时情绪细化默认 300 秒，
失败或清除不返还间隔。
`finish_quota(reservation_id, *, status, reason_code)` 只标记结果，失败/取消/unknown 不退款；
`quota_usage(*, period, pool="model", purpose=None)` 用于诊断。

`create_intent(intent)`、`get_intent(context, intent_id)`、
`transition_intent(context, intent_id, expected_generation, *, expected_status,
status, reason_code, reservation_id=None)`；pending→reserved 必须带已持久预留的额度 ID；
generating→sending 校验原人格/身份/路由令牌、新人类消息和过期时间。
这些是存储闸门而不是宿主授权，行为服务还须最终授权及硬否决检查。
`recover_inflight()` 启动时取消旧待发任务、sending→unknown，保守占用原额度，不重发。
`save_experience(experience, expected_generation)` 仅存储，不生成、不分享；
diary period 必须是人格本地日期，dream period 使用夜 ID + 次数编号。
`cleanup()` 清理过期正文/事件/未置顶体验；`backup(new_path)` 使用 SQLite backup。

状态和事件返回 `CommitResult`（status/reason_code/event_key/generation/versions）；
其余写方法返回相同 status/reason_code 风格字典。
`runtime.BackgroundRuntime.submit(job_id, context, generation, work, *,
purpose="local", model=False, input_tokens=0, output_tokens=0)` 返回 queued/rejected，
不会把仅排队说成 accepted。work 是零参 async factory，不要预先创建 coroutine。
模型调用服务须传准确 Token 计数，并把模型实际输出上限落实到 Provider 请求；
本运行时只负责声明额度校验、超时、取消和并发，不能替代 tokenizer/Provider 限制。

## R9 门面

`api.LivingEmotionAPI`，全部 async：
`get_capabilities()`、`ingest_event(event)`、`get_bot_state(context)`、
`get_observation(context)`、`get_relationship(context)`、
`get_availability(context)`、`preview_behavior(context)`、`get_health()`。
返回 JSON-compatible dict，含 api_version、结构化状态和 reason_code(s)。
T1/T2 只接持久事件和安全默认快照，领域处理器尚未接线时明确降级。
`LivingEmotionAPI(..., project_event=async_callable)` 的投影回调接收 Event，
返回 `(Sequence[StateWrite], Sequence[RelationshipContribution])`。
回调在事务外纯计算，版本冲突最多重读计算 3 次，clear 代际不重取。
宿主发现插件后使用 `plugin.api`；不要直接访问生命周期的 store/config。
进程内门面不是 HTTP 管理鉴权；任何 `admin=true` 不构成权限。

## 边界决定

状态：沿用已批准的独立模块化重实现。目标是无宿主领域测试、持久原子性和来源隔离；
不新增服务。内存存储不能跨重启幂等，JSON 文件不能原子提交多实体，
因此采用 SQLite WAL + 短事务。优势是单库一致与可备份，代价是串行写者及迁移维护。
主链用本地提交，模型走有界后台队列；数据库失败拒绝更新并停止自主，不影响原聊天。
此选择可通过存储端口替换；多宿主同时写同一状态是重新评估边界的触发条件。
责任：T1/T2 工程与存储代理；验收入口 `tests/contracts/`、`tests/storage/`、`tests/runtime/`。
真实宿主生命周期/人格/页面/鉴权由 host_contract 核查，尚不宣称验证通过。
