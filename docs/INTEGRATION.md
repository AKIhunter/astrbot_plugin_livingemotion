# 核心集成交接

日期：2026-11-05。负责人：接替核心集成代理（旧核心已停止，无同时写者）。
本轮修改 `main.py`、`runtime/application.py`、`runtime/console.py`、
`tests/integration/`、本文，以及父追加 V06/F12 授权的必要 `services/behavior.py` 端口。
未修改 adapters、models、config、contracts、sqlite、projector、api、identity、
relationship、relationship_projection、background、旧消费者或独立验收测试。
不改父规格，不执行 Git、性能基准、整套宿主、生产模型或真实消息。

## 最新状态与文件冻结

**2026-11-05 22:18:24 UTC：核心产品与集成测试已完成并冻结，释放写入权。**
当前步骤已结束，无执行中的命令、无核心阻塞，不等待 C51。
父可立即启动冻结版独立宿主；普通 full 由父按其余所有者冻结情况统一安排。
以下哈希仅代表本核心边界，不能替代 F6 或整个插件的冻结清单。

| 文件 | SHA-256 |
| --- | --- |
| `main.py` | `62783b1c1a4a24231bb839e56e74c8ecfe4f40949b2e2b0ef96557633f9e0e87` |
| `runtime/application.py` | `79b30e76cfaaf899e1d3297b0822d18f496a60aa4786e791e94f0709e95adc99` |
| `runtime/console.py` | `219d8239453e2bf0257380c72c3eba4a488e352927cea29b2823f0708b91f833` |
| `adapters/astrbot.py`（未改） | `e513eff14ac4196bfbf3e5893ad02868c1f480e776056e0385afdfd97f621b49` |
| `services/behavior.py` | `000308b54bf601e2ede77ead39f44643e715fb0d037bfa0bf4456dbb115b479e` |
| `tests/integration/test_application.py` | `54afa60010873dada2ce1eb0e3aa0516c34cedf88f5ceb5fd1e04c3a5c9b8a03` |
| `tests/integration/test_main.py` | `6df28501a959a8f6154ad5d093bb9c1fa1ac8f86011c5df0e53d92d371b2f474` |
| `tests/integration/test_projector.py`（未改） | `059886ed8eec76456f2e2c7be84a5d6f544bd420fab5b7f55abbb990a5dc9013` |
| `tests/integration/run_provider_payload.py`（未改） | `4d9b1b71af9d5dff4927a7423bd5556459addb5b665091589a8737e94db8d281` |

本轮完成：

- F7/H01：`Application.current_relationship(context, *, record=None)` 从同一已验证
  source 取得 identity/event，调用已冻结投影服务。API、行为、表达、管理关系展示统一读取；
  None 不回退旧聚合。行为/表达/管理在后续 await 后仍复核上下文与清除代际。
- H02/F10：状态读取失败返回 `available=false, block_chat=false, state_unavailable`；
  消息边界隔离补充异常，请求移除旧 suffix 后省略补充，原生内容保留。
  自主快照失败返回 None；取消信号仍传播，不吞为普通失败。
- H03/F11：只有真实 `event.is_admin() is True` 写可信 admin 标记；
  非管理员清除伪 admin extra，普通 JSON 不获得权限，注册 `/le_wake` 正例保留。
- V06/F12：BehaviorHistory 增量与最终闸门见下文；Store 仍由 F6 独占，
  核心不重复叠加 floor，不虚构尝试时间。已只读核对 F6 新 Store 返回同名字段。
- F13：console health 新增 `reply_confirmation=unavailable`，中文明确 unsupported、
  120 秒收尾超时取消，after-sent/bool/None 都不算发送成功。没有新增发送器或确认钩子。

### 本轮实测

插件根目录，普通 `.venv-ci`，合成输入、临时 SQLite，不依赖宿主或旧插件目录：

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python -m pytest tests/integration tests/behavior \
  tests/verification/test_cross_module.py -q -p no:cacheprovider
# F13 展示字段变更前：118 passed in 5.53s

env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python -m pytest tests/integration -q -p no:cacheprovider
# 最终冻结源码，含 F13：36 passed in 0.68s
```

未修改的独立 `test_application_bound_relationship_read_reprojects_retained_ledger`
已通过：31 天 events=0，账本保留，两个 0.5 绑定后 1.0、解绑后 0.5，原账本不变。
覆盖投影 None、后续人格变化、OSError 普通入口/自主反例、真实 admin 标记与伪 JSON、
非 bool 管理身份、叫醒、取消传播、真实 history 值/绝对冷却/拒绝原因和 F13 展示。
入口测试只替换宿主导入表面，不冒充完整 Pipeline；实际宿主验证由独立者负责。

本轮历史保留：最初原集成加 V04 为 22 passed；新增自测首轮 32 passed / 2 failed，
失败为自测错误要求重解析后的 identity 与旧对象同一实例，已改为核对当前 source。
随后普通隔离回归 117 passed，再次为上述 118 passed；未降低独立断言。
定向 Ruff 命令因 `.venv-ci/bin/ruff` 不存在退出 127，未称静态检查通过，也未安装新依赖。
父报告宿主 H01/H02/H03 57/57、C30 51/51 及 F6 V06 308 passed 属独立/其他修复者
证据，不计入本代理自测，也不声明生产投递或全套验收通过。

### F12 与 C30 接口

给 F6 的固定增量协议：`store.behavior_history` 在原四字段之外返回
`cooldown_until: float | None` 和 `reason_codes: tuple[str, ...]`，默认 `None/()`。
`BehaviorHistory` 已承接；行为初评与最终发送检查均检查绝对冷却并保留拒绝原因。
三项计数由 Store 将真实 native + 已证明 legacy floor **仅相加一次**；
`last_attempt_at` 只保留真实原生尝试，不从 cooldown 或当前时间反推。
Application 不重复计算 floor；约束在 History 的统一行为闸门消费，不再在
current_snapshot 中提前变成无法解释的空快照。未知约束必须返回明确非空 reason_codes。
模型派发前已有 `legacy_constraints` guard 保留。V06 原四 proven 反例最终复验由独立者完成。

C30 原接口保持 `await application.confirm_reply(domain.night.ReplyReceipt(...))`，
仅可信传输确认所有者可用，需原 context、真实 succeeded、匹配 request_id/message_id。
`main.confirm_consumption` 只记已读，不等于发送确认。当前宿主无可靠公开回执，
不接 after-sent，不把找到平台的 bool 或 None 转换为 succeeded。
既有 pending settling 120 秒后取消回 awake/drowsy，不伪成功或自动重发；
无待回复的计划睡眠和手动睡眠不受此能力降级影响。未更改 night 状态机。

## 前代理历史记录（保留失败，不作当前状态）

**2026-11-05 21:29:17 UTC：api.py 也已冻结，可立即交 F6 独占。**
核心不再修改 `storage/sqlite.py`、`runtime/projector.py`、`api.py`。
api.py 最后变更只有关系读取接点：
`await application.current_relationship(context, record=record) -> Relationship | None`；
None 返回 unavailable/context_changed，非空再加 normalized。该只读方法由核心在
application 层完成，F6 保留调用即可，不需要等关系专项测试后才开始性能修复。
F3 专人报告纯模块/TTL 完成、74 项迁移测试通过；此处区分报告与核心联合实测。

**2026-11-05 21:21:22 UTC：sqlite.py / runtime/projector.py 已冻结并交性能修复代理。**
核心后续不再写这两个文件；性能修复必须保留 FULL、原子事件/trace/账本、清除代际、
F3 约束/清理、F5 current_affect、异步 refine_emotion CAS 公共接口，不改变 schema 2。
如确需协议调整先在本文交接，避免双方同时写文件。

本轮联合命令（无性能/宿主总验收）：
`.venv/bin/python -m pytest tests/integration tests/runtime tests/contracts/test_foundation.py
tests/storage tests/migration tests/verification/test_cross_module.py
tests/verification/test_migration_cli.py -q --tb=short`

最新 **179 passed / 4 failed / 6.81s**。4 项均为刚新增独立反例：
`test_application_bound_relationship_read_reprojects_retained_ledger`（核心 API 未接绑定投影）、
`test_identity_grant_does_not_turn_private_account_binding_into_scene_access[3 cases]`
（IdentityAdapter 将私聊绑定扩大到群/公开评论/其他实例；不在核心写权限）。
没有改独立测试断言。F3/F4/F5 已知反例在该轮通过，但不据此勾完整任务。
完整 Ruff 尚有宽异常边界/少量样式建议，未称全通过；已完成自有文件 import/unused 清理。

已落代码并有合成集成证据：共享 worker 的行为/日记/梦、排队及生成期间
human/persona/clear 废弃、体验多来源 CAS/置顶审计、unknown 历史跨日/clear 不重发、
醒后补课摘要原来源最终复核、计划睡眠待收尾只认完整成功回执、可选情绪细化。
细化用原事件前快照重算，CAS 替换该事件的 Bot 投影和 trace，不重放关系/能量/事件。
F5 API/页面/行为/状态 suffix 共用只读 current_affect，不伪造事件，不更新持久版本；
未采时间的旧 partial projection 保留旧接口形状，不从 timestamp=0 推测衰减。

模型最新方案取代本文旧版 GPT-only/tiktoken 说明：无需新增 tokenizer 依赖。
支持已核实原生 `ProviderOpenAIOfficial`（含 Qwen/兼容模型别名）的纯文本 Chat
Completions；输入预算是 **UTF-8 字节上界 + 256 模板余量**，绝非精确 usage。
适用标准 byte/subword 文本 tokenization、两条文本消息，无工具/图片/隐藏历史；
自定义服务端额外注入模板、非标准 tokenization 或不执行 max_tokens 的服务不在保证内。
其他原生协议/Provider 子类尚未核实，返回明确 unavailable；不伪用 GPT tokenizer。
request-local 副本只保留采样参数，禁 messages/model/n 等覆盖，固定 n=1/max_tokens，
Qwen 关闭额外 thinking；原生重试 max_attempts=1、SDK max_retries=0、外层 timeout。
fallback 仅派发前选择；派发后 503/未知返回/超时均不自动重试或切换 Provider。

真实宿主代码 payload 专项（不启动 HTTP/Dashboard/平台；httpx.MockTransport，
临时 ASTRBOT_ROOT，audit hook 禁 socket connect/bind/DNS/子进程）：

```bash
.livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/integration/run_provider_payload.py \
  --host-source .livingemotion-host-t1/AstrBot
```

实测 **7 tests OK / 0.159s**，v4.29.4 的真实 Provider + OpenAI SDK；
Qwen、兼容别名、真实 payload 限制/共享配置不变、503 一次、畸形返回 unknown、
输出超限、超时一次及其他 Provider 拒绝。真实外发与收费均为 0。
给交付代理：**撤销旧 tiktoken 必装通知**，安装不需要增加此依赖。

## F3 接点冻结（优先交接）

F3 专人独占 `runtime/legacy.py`、`storage/legacy_import.py` 和 `tests/migration/`；
核心只加下面的查询、清理及统一调用，不重复实现采用逻辑，不新增 schema。

```python
# SQLiteStore，只读；返回全库约束而非只读当前 scope，防止全局额度漏算。
await store.legacy_baselines(limit=2000) -> tuple[dict, ...]
# 每项：record_key, scope_key, generation, version, updated_at, value
# value 仅有 source_id/source_hash/classification/identity_resolved/target_context/
# baseline/activation_blockers/runtime_constraints；不返回 original 或正文。
# 超过 limit 或坏 JSON 抛异常，核心 fail closed。

# F3 runtime/legacy.py 请导出纯函数；本接点没有费用/发送/写入能力。
evaluate_legacy(rows, context, *, purpose, timezone, now, human_watermark) -> dict
# purpose: behavior / emotion / diary / dream / export
# dict 至少含 allowed: bool, reason_codes: tuple[str,...]；
# behavior 可加 global_used_floor/scope_used_floor/unanswered_floor: 非负 int、
# last_attempt_at: float|None、cooldown_until: float|None。
```

核心 `Application.legacy_constraints(context, purpose)` 是唯一装配入口，
行为历史、体验入队/最终 guard、模型派发前调用它。无迁移记录正常放行；
有记录但模块缺失、异常/无有效 allowed 时拒绝该后台用途。普通聊天规则状态不受阻。
按 F3 `docs/migration.md` 补充，Store.behavior_history 将 native_used + legacy_used_floor，
旧数据内部 global/session 重叠由纯评估去重；未回复采用相同相加规则。
不把旧值写成已发生的新发送。直接使用 Store 历史端口也受到约束，不只限制页面。
请 F3 在输出中处理全局/场景重叠、原时区/周期未知、身份未映射与新 human 的语义；
无法证明夜周期/时区，不因原生开关开启而自动放行。采用必须留来源和解释；
不能仅将 runtime_adopted 改为 true 或删除 blockers。

历史正文：F3 可在 legacy_import value 写 `history_expires_at`（绝对 Unix 秒，
不得晚于原正文 TTL），核心 cleanup 会在该时间或 `updated_at+7天` 的较早者
删掉 `original` 与 `baseline.pending_crawl` 并标记 `history_redacted=true`，
不删除非正文约束/幂等回执，避免清理后重新打开预算。没有 expiry 的旧档案同样有
7 天上限；缺 history_expires_at 的旧档案立即脱敏。congling.snapshot 原生体验
到原期限或 created_at+7天即失效，pinned 不豁免，load/query/pin/cleanup 同口径。
显式 clear_scope 仍按原契约清除该范围历史。此段是接口约定，
不代表 F3 实现或联合测试已经通过。

## 页面 Application 接口冻结 v1

以下接口已落入 `runtime/application.py` 与 `runtime/console.py`。
核心合成集成测试已通过；不能据此宣称真实宿主 HTTP/iframe 全链路已经验证。
页面代理请按此接线；不再读取 `.store/.config/._lifecycle` 或自己实现业务事务。

入口：`runtime.application.Application`，由 `main.py` 创建并提供
`plugin.application`。页面不自行构造 Application。

页面代理请导出 `page_api.PageAPI(host_context, application)`，同步 `register()`
注册 `console/state|records|config|preview|action`，同步 `stop_accepting()` 停止旧 handler。
最终入口先完成 application.initialize，再构造并 register；terminate 先关闭 page handler。
路由严格使用宿主插件扩展相对路径约定；同路径及 methods 重载替换。

所有 application 方法都是 async，返回 **data 对象**，页面仅包
`{"status":"ok","data":result}`。业务错误统一抛出
`runtime.application.ApplicationError(code, message)`，属性 `code/message/status_code`；
code 为 `validation_error/unauthorized/forbidden/version_conflict/unavailable`。
页面按 `ui.md` 添加 `[livingemotion:<code>]` message 前缀和正确 HTTP 状态。
异常内容不得回显宿主异常、私密正文或密钥。未知异常返回 unavailable。

```python
await application.console_state(context_id: str = "") -> dict
await application.console_records(
    context_id: str, kind: str, page: int = 1,
    page_size: int = 10, query: str = "",
) -> dict
await application.update_config(
    patch: dict, *, expected_revision: str | int,
    reason: str, actor_id: str, context_id: str = "",
) -> dict
await application.console_preview(context_id: str) -> dict
await application.console_action(
    context_id: str, action: str, *,
    expected_revision: str | int, reason: str,
    actor_id: str, confirmed: bool,
) -> dict
```

- `console_state` 返回 `ui.md` 的完整 State；空 context_id 选择最近可用范围；
  没有消息时返回空范围和真实配置/健康，绝不创建合成 Bot/关系/材料。
- context_id 由 application 生成并从 `contexts` 返回；未知值拒绝，不接受前端 Context。
- records 只接受 emotion/behavior/diary/dream，固定每页 10 条，page >= 1，
  query 最长 200 字符；按 created_at 降序、ID 决胜；total 是过滤后数量。
  页码是管理列表视图，不承诺跨并发更新的快照一致。
- update_config 是唯一页面配置写入口。严格字段/类型/版本校验，更新注入的原生
  AstrBotConfig 并调用其 save_config；成功返回刷新后的完整 State。
  revision 为不透明内容修订号；重复提交旧 revision 返回 409，不自动重试。
- application 在消息钩子和配置监视任务重读同一个原生配置对象；
  `await application.refresh_config()` 是集成者可调用的实时同步入口。
  enabled=false 停止接收及全部业务任务；配置监视器只检查恢复开关、不读消息、不调用模型。
  原生配置重新 enabled=true 能恢复，不要求依赖页面写操作。
- actor_id 必须取自 handler 重新验证的宿主管理身份，不取 JSON/body/query。
  该参数用于审计，不是 Python 内的鉴权凭证。所有私有读写均由成品 handler 执行 F1 guard。
- console_preview 永不调用模型或发送。console_action 只允许 State.actions 已声明且当前仍可用
  的操作；confirmed 必须严格为 True。不可用动作明确拒绝，不返回伪 accepted。
  生成/发送返回 queued/request_id，只有持久状态提交能叫 accepted；unknown 不重试。
- 初版不增加 HTTP 关系修正按钮；公开业务入口另提供
  `correct_relationship(context_id, *, expected_version, score=None, frozen=None, reason, actor_id)`，
  和 `clear_context(context_id, *, expected_generation, reason, actor_id)`。
  关系快照/来源账本/审计同事务；清除用代际阻止旧任务回写。

契约兼容：以上为新增 v1 承诺，只增可选字段，不复用字段改变语义；DTO 按 ui.md，
Bot pleasure 显式 `(x+1)/2`，night energy `/100`，对方观察绝不混入 Bot 状态。
进程内消费者继续使用 `plugin.api` 的 R9 v1，不获得管理页面权限。

## F1 联合验证

页面代理负责每个成品 handler 的严格 Dashboard Bearer 验签和 claims 白名单。
拒绝页面 asset token、未知/OAuth claims、无 token、过期/伪签及 admin=true。
核心代理负责最终注册并在真实 v4.29.4 legacy/v1 HTTP 两路径联合验收。
不能仅凭探针已有 13 项 guard 测试宣称成品通过。

## T8 Producer 与普通请求接点

新增 `SceneKind.PUBLIC_COMMENT = "public_comment"`；它不是 group/private，Context 禁止携带
route，availability 为 `available=false, block_chat=false`。原始 scene_id 必须是平台提供的
稳定公开讨论对象键，例如 `video:<oid>` 或真实 `thread:<root_id>`，不能使用裸作者账号、
正文哈希或时间戳替代。公开场景与私聊、群聊、其他平台在 scope_key 中独立。

消费者正式调用：

```python
result = await plugin.api.resolve_producer_context({
    "producer": "bilibot",
    "bot_account": verified_bot_account,
    "adapter_id": verified_adapter_instance,
    "platform": "bili",
    "scene_kind": "public_comment",  # 或 private；private.scene_id 必须等于 account_id
    "scene_id": verified_discussion_id,
    "account_id": verified_author_account,
    "persona_id": native_persona_id,
    "persona_revision": native_persona_content_fingerprint,
})
context = result["data"]  # 仅 status == ok 才使用，不自行补实例/路由/受众
```

该方法已落代码，返回 R9 envelope。要求字段精确如上；无需 audience、route 或 instance_id，
插件自行生成来源命名空间、公开受众标识及本地来源身份版本。进程内生产者是受信插件，
不是面向聊天/HTTP 的身份注册权限。人格由消费者已有原生选择器解析，不把 provider 当人格。
`get_capabilities()` 公开稳定 instance_id、scene_kinds 和 resolve_producer_context 操作。
实例不可用/禁用时方法拒绝。消费者每次动态发现，不保存旧插件对象。
事件继续用 `ingest_event`，公开评论只传中性真实 interaction、原始来源 ID 与时间，不将
本地 affection 映射为 care/conflict/Bot 分。无正文可留空；绝不伪造发送成功事件。
公开评论不参加记忆/自主/梦/日记/发送候选，普通状态和按作者关系独立记账。

LivingHello 接点按 `docs/consumers.md`：消息/请求 priority >10000 先写可信 extra
`livingemotion:context`；唯一临时 TextPart 前缀 `<!--livingemotion:state:v1-->`，
重复钩子替换本插件旧块，不复制原生人格；有效 capabilities.mode 含动态冲突退让。
管理/叫醒只由真实受控入口设置 `livingemotion:control_request`，普通消息参数不能设置。
这些钩子已完成核心接线和定向自测；完整组合验证以独立宿主冻结版记录为准。

## 当前接点

- [x] 阅读 spec/tasks/checklist 与 FOUNDATION/CONTRACTS/DOMAIN/memory/host-contract/ui。
- [x] 冻结页面 application 构造、方法、错误、配置实时更新契约。
- [x] 领域投影器、trace 原子提交和管理关系事务（公开存储/独立 facade 已测，主入口待接）。
- [x] 正常消息/LLM hook、唯一状态 suffix、同人格/身份最终复核（合成宿主桥测试）。
- [x] 动态插件发现、从绫冲突退让、三种记忆模式与生命周期（无真实模型）。
- [x] 长夜/补课/行为/体验接线（既有合成与 Provider 专项记录，非生产投递）。
- [x] 页面成品注册接线（独立阶段 HTTP 证据见 verification-host，非本代理复跑）。
- [x] F7/H01、H02/H03 定向修复及必要反例；F12 行为端口、F13 不支持展示。
- [x] 本核心文件哈希与精确冻结时间已置顶，无等待中的核心实现任务。
- [ ] 冻结版独立宿主与普通 full 验收（父协调，不由本核心重复运行）。

## 测试证据

第一阶段本代理实测（macOS，插件 .venv Python 3.11，合成数据与临时 SQLite）：

```bash
.venv/bin/python -m pytest tests/integration tests/contracts tests/storage tests/runtime \
  tests/domain tests/identity tests/memory -q -o faulthandler_timeout=15
```

结果 **212 passed in 2.86s**：原有 207 项加本代理 5 项集成测试。
新增覆盖原子领域/trace、CAS 整体回滚、管理关系+账本+审计、清除旧代际拒绝、
runtime 跨重启、正文保留期后 human 水位不回退、公开评论隔离及正式 producer context。
首次集成暴露新 Bot 初始 updated_at 误设为处理时间，导致首条稍迟到事件被跳过；
已改为领域基线时间，回归通过。数据库新增迁移 2，旧迁移回滚测试固定版本断言已更新为
当前迁移数量。共享 SCHEMA_VERSION=2，API_VERSION 仍为 1，属于兼容增量。

新增公开存储：`register_context/list_contexts`（持久上下文不保存路由），
`correct_relationship`（完整管理事务），`query_records/audit_records/append_audit`，
`behavior_history(context, period, exclude_intent_id)` 返回 T6 所需字段 dict，
`load_experience` 与 `save_experience_guarded`。后两者及行为历史的专项接线仍待服务验证。
主入口/宿主钩子/页面/模型/调度尚未完成；上述测试不是最终宿主验收。

## 第二阶段核心接线（持续更新）

已实现：

- `main.py` 构造 `Application(context, native_config, data_dir)`；`initialize()` 完成后，
  导出 `plugin.api`，再导入 `page_api.PageAPI` 并注册。terminate 先停页面再关 application。
  消息和 LLM 请求优先级 11000，高于 LivingHello 的 10000。
- `on_llm_request` 移除旧命名块再添加唯一临时 TextPart；不复制原生人格。
  `/le_wake` 是真实注册命令；显式 block_chat 时保留该入口和宿主认证管理员。
- `AstrBotBridge` 只使用原生 UMO、Bot self_id、adapter ID、人类账号与消息 ID；
  同一 instance_id 贯穿。人格走原生会话选择器，身份服务按次发现；
  没有长期持有原始消息正文（仅 bounded weakref 索引）。
- 开关/配置改变先取消并等待旧 scheduler、behavior、runtime、experience、memory，
  再创建新服务；禁用只留配置恢复监视器。有效冲突按 `congling.enabled_for(real_event)`
  判断，无法核实范围时保守观察，不读改从绫内部配置。
- Store 公共 `behavior_history`、`load_experience`、`save_experience_guarded`、
  `pin_experience(old,new,generation,actor_id=...,reason=...)` 已有真实 SQLite 实现。
  置顶完整记录 CAS + 审计同事务，多来源保存逐项代际校验与插入同事务；
  clear 保留非正文 human 水位用于 unknown 退避，不重开配额。
- 当前 schema 仍为 **2**，本阶段未新增 migration。T10 独占
  `tools/` 和 `storage/legacy_import.py`，未修改其文件。

原生配置可操作字段已补齐：persona_mode/persona_id，provider_id/fallback_provider_id，
timezone、完整 scope_key 白名单/静音表、免打扰与活动时段、全局/场景限额、冷却/未回复上限、
计划睡眠开关与入睡/醒来时间、日记时间/昨天补写/重试、每夜梦上限、
日记/梦保留天数、梦半衰期及正文长度。总开关/模式/记忆与资源限制保持同一原生对象。
空时区/空白名单拒绝主动；所有生成与自动计划睡眠默认关闭。

模型桥注意：固定宿主 OpenAI Provider 的 `_prepare_chat_payload()` 忽略 max_tokens kwargs。
`runtime/models.py` 使用**请求局部 Provider 副本**，通过已核实的 `custom_extra_body.max_tokens`
约束真实请求，隔离 client options，禁用副本重试，绝不改宿主共享 Provider。
目前只放行有已知 tokenizer 模板的原生 OpenAI GPT 模型；不支持的 Provider/模型明确拒绝。
fallback 仅限派发前选择失败，网络派发后不换 Provider 重试。普通聊天不需要模型。
生产使用该可选生成路径需要 `tiktoken`；缺失时 `model_or_tokenizer_unavailable`。
**给交付代理：请将可选生成所需 tiktoken 纳入最终依赖/安装说明，不把当前环境能力当成已安装。**

新增自测：

```bash
.venv/bin/python -m pytest tests/integration tests/contracts/test_foundation.py -q --tb=short
```

实测 **26 passed / 0.24s**。其中本阶段4项新集成覆盖：
无模型普通消息真实规则状态、唯一 suffix/主体隔离、配置 CAS/禁用/原生恢复、
三轮 Application 生命周期无遗留任务、动态同范围冲突/人格改变拒绝、
睡眠默认不拦及显式阻断、SQLite 多来源回滚与置顶跨重开持久化。
这是合成 Host + 真实 store，不冒充真实 AstrBot 加载/HTTP/iframe。
环境仅警告 pytest-timeout 未安装（未知 timeout 配置）；测试本身完成。

仍在闭合，不能按完成验收：

1. scheduler/experience/behavior 的生成桩全链路、Provider wire 参数专项与新 human/clear 废弃验证；
2. 置顶服务回调（storage 已实现）、醒后补课材料最终复核、可选情绪细化后台接线；
3. 持久 history 查询专项（含跨日、unknown、清除及全局其他 send purpose）；
4. 刚落盘的 page_api 最终接口核对；真实 HTTP/iframe/三reload 由独立验收代理负责，
   核心不重复运行全量。Application 构造与冻结接口未改。
