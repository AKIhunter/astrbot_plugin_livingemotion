# P4 内部接入契约

状态：P4 实施完成，2026-11-06 收尾冻结。P4 不修改 Application、Materials、
Config、contracts、sqlite.py、schema、页面或其他仓库。本文件是主协调者和
Config 写者的接入依据；以下 P4 阶段全仓曾失败，后续协调整合结果单独记录。

## 配置字段

新增字段均用 getattr 默认值读取，旧字段继续可读。

| 字段 | 默认 | 含义 |
| --- | --- | --- |
| livingmemory_enabled | 未提供时按 memory_mode == external | 开启外部公开门面；禁止静默复制或本地兜底 |
| memory_read | False | 长期记忆查询开关 |
| memory_write | False | 本地自动收录开关，不代表外部写入权限 |
| embedding_provider_id | 空 | 原生 DashScope/OpenAI embedding Provider ID |
| diary_provider_id | 空 | 空值沿用 provider_id / 当前聊天模型 |
| dream_provider_id | 空 | 同上 |
| catchup_provider_id | 空 | 同上 |
| closing_provider_id | 空 | 同上 |
| home_city | 空 | Bot 住所；未配置必须标明未配置，不猜城市 |
| memory_max_records | 10000 | 本地上限，范围 1..10000 |
| memory_retention_days | 30 | 原文寿命，范围 1..30；索引换模型不续期 |
| memory_timeout_seconds | 2.0 | 正常聊天检索的短超时 |
| embedding_timeout_seconds | 5.0 | 单次向量调用超时，不重试 |

## 接口与责任

### 长期记忆读取

`MemoryGateway(backend, clock=store.clock, context_guard=...)` 保留 v1 接口。

- `await gateway.recall(request, event=event, available=materials)`。
- `await gateway.validate_evidence(request, materials, event=event)`。
- event 是宿主传入且与 request.context 路由、发送者一致的真实
  AstrMessageEvent，不构造、不持久化、不把 cron/agent_wakeup 当真人授权。
- 正常聊天将 on_llm_request 的真实 event 传到查询和注入前最终校验。
  任何校验后新的 await 均不能被当作永久授权；使用/提交前需重验。
- 后台 event=None：LivingMemory 返回后台授权不支持，仍可使用自身授权归档；
  不应把该结果显示成整个接入失败，不查询私有 engine/store。
- 两种公开门面：有 validate_identity_results 时最终校验正文和来源；
  缺少该方法时保存原查询，最终按当前身份重查同一查询，只接受 ID、正文、
  来源完全一致的候选。提供者重载、身份撤销、查询参数变化均拒绝旧材料。

### 本地向量与自动收录

实现文件：adapters/memory/local_vector.py、storage/vector.py、
adapters/embedding.py、runtime/memory.py。

- `NativeEmbedding(host, provider_id, timeout=5)`：复用原生提供者，无额外凭据；
  `await binding()` 返回含 namespace、dimension、fingerprint、embed(text) 的绑定。
- `LocalVectorMemory(store, embedding, ...)`：`await open()` 添加自有表；
  `remember(request, material)`、`recall(request, event=None)`、
  `validate_evidence(request, materials, event=None)`、
  `forget(context, source_id=None)`；另保留 Gateway 所需 fetch/validate。
- `await build_memory_backend(store, host, discover, config, guard=...)`：
  外部开关开启时仅返回 LivingMemoryAdapter；关闭时返回 LocalVectorMemory，
  并用 `store.path.with_name("explicit_memory.sqlite3")` 接入只读旧显式库。
  不依赖 Application 新增参数，不修改旧库，不扫描其他数据目录。
- `AutoMemoryIngestor(backend, runtime, config=lambda: config, guard=...)`：
  `await ingest(event, generation=accepted_generation)` 只入非模型后台队列；
  不在原回复路径等待 embedding，不调用摘要模型。
- Human：on_message 只有持久 ingest 返回 accepted 时派发；传入已经规范化的
  contracts.Event 和该次 accepted generation，不从正文重建身份。
- Bot：on_reply_submitted 持久记录提交正文后派发一次；使用稳定提交 ID，
  actor_role=BOT、event_type=bot_reply_submitted。提交不是平台送达；
  不虚构 bot_action_succeeded，不在 after_sent 重复入库。
- 收录身份保留实例/人格/平台/账号/真实会话/角色/来源 ID，不因全局状态合并。
- 切后端/模型、关闭写入或配置 revision 变化：停止旧 ingestor，取消旧任务；
  任务执行前后 guard 复核。forget 提升删除代际，store 清除代际也在事务内复核，
  迟到 embedding 不可写回。先 forget 再开始新收录；不要清完后补读旧事件。
- `await ingestor.close()` 先停收录并取消在途，关闭天气后再停止 runtime；
  `await gateway.close()` 清查询和后端任务，必须在 store.close 前完成。
  close 不关闭宿主 client。

### local_lite 显式 legacy 接入

已完成，实现文件：adapters/memory/legacy.py。

- 旧 `explicit_text` 通过 SQLite `mode=ro` 读取，不创建缺失旧库，不 cleanup，
  不迁移、不自动向量化、不续期、不写回旧文件或旧表。
- 无 embedding 时仍能读取旧记录；保留原 `local_lite` provider、正文、来源、
  occurred_at、expires_at 和非导出标记，不伪装成已建立向量索引。
- 继续按 account_key、人格/身份 revision、audience、holder 和原 TTL 授权。
  查询保留旧 casefold + 空白分词 + 包含匹配，最多扫描最新 200 条有效记录。
- 词匹配分数与余弦分数不混排：旧显式匹配优先，其后接新版向量结果；
  相同 source_id 去重。`memory_read=False` 仍关闭两类读取。
  旧 `memory_mode=none/local_lite` 本地分支统一使用新版后端，不据旧枚举禁读；
  `livingmemory_enabled=True` 则不接触旧库，更不以旧库兜底外部授权失败。
- validate 在 store._run 的最后事务边界重读旧正文及完整 EvidenceRef，
  并核对旧库 key/scope/occurred/expires 与证据一致；源撤销或正文变化拒绝使用。
- `forget(context, source_id)` 在自有 `le_memory_legacy_hidden` 持久化屏蔽，
  只隐藏指定账号/来源；`forget(context)` 隐藏该来源 scope 的全部旧记录。
  宿主 clear_scope 的 generation>0 同样拒绝该 scope 的所有旧记录。
  屏蔽和清除重启后保留，不通过重新收录恢复已删除的旧正文。
- 自有四表为 le_memory_epochs / le_memory_text / le_memory_vectors /
  le_memory_legacy_hidden，均由 storage/vector.py 通过 store._run 事务管理。

### 用途生成与天气

- `await Generation.model_binding(context, purpose="catchup")`：只选原生模型，
  返回现有 OpenAIBinding。调用者自行 runtime.run_model 也可，不重复扣预算。
- `await Generation.purpose_model(context, purpose, system, data, job_id,
  max_output_tokens=None)`：内部 runtime.run_model，共享并发队列、总额度和
  Token 限制；不要在另一 model=True 工作内部调用，避免嵌套队列死锁/重复扣费。
- diary/dream 的 ExperienceService 在自己已预算的 submit 工作内部直接生成，
  不再调用 purpose_model。closing/catchup 各自选择字段，但不产生新额度池。
- BackgroundRuntime 的 purpose 启用映射由其写者补 catchup/closing（协调者已确认新增），保留总额度。
  P4 不通过改名成 diary/behavior 绕过用途开关。
- Generation.experience_service 创建天气提供者；日记先筛选真实素材，再在后台
  读取对应日期天气。天气不是经历素材，不会单独触发空日记。
- `OpenMeteoWeather.get(city, day, timezone)` 返回 WeatherReport；
  1 小时成功缓存、短失败缓存、同键 single-flight、整体 5 秒超时。
  指定日期必须匹配 daily.time，不拿今天实时数据补昨天。
- 日期/住所/天气页头由程序添加；模型 DATA 指定 Bot 第一人称，不能改程序字段。
  失败显示未获取，日记仍可写。正文不分享到群，原私有读取权限不变。

## 派生数据决策

| 对象 | 键/写者/失效者 | 新鲜度与失败行为 |
| --- | --- | --- |
| 原文 | account_key + 来源 ID；accepted/提交钩子 | 最多 30 天、10000 条；冲突拒绝、重复不续期 |
| 旧显式原文 | v1 只读库；自有屏蔽表及宿主 scope generation 失效 | 保留原 TTL/来源/词匹配；无 embedding 也可读，绝不复制成向量 |
| 向量 | 原文键 + 提供者/模型/维度 namespace | 换模型新 namespace；删除/清除/停用拒绝迟到写回 |
| 查询 | 请求 ID + purpose + context + 后端 token | 每次使用最终校验；缺向量/慢查询为空，不冒充已建库 |
| 天气 | 城市 + IANA 时区 + 真实日期 | 成功 1 小时，失败短缓存；冷启动有界并发和超时 |

修复路径：先停收录，按来源 forget；重新开启只收新获授权事件。
不自动跨模型重嵌入历史，不恢复已过期正文。health 仅返回计数和原因码，
不含正文、向量、密钥或宿主异常字符串。

## 实测证据

2026-11-06，本仓库 `.venv-ci/bin/python`，合成输入和 pytest 临时 SQLite，
不连接生产、不调用收费模型、不真实发送。以下是独立运行结果，不相加冒充
全量通过；原生 transport 专项需显式运行，不在默认 pytest 收集列表中。

| 实跑命令 | 结果 |
| --- | --- |
| `.venv-ci/bin/python -m pytest tests/memory/test_p4_legacy.py tests/memory/test_p4_vector.py -q` | 40 passed，0.64s |
| `.venv-ci/bin/python -m pytest tests/memory tests/weather tests/experience -q` | 208 passed，2.23s |
| `.venv-ci/bin/python -m pytest tests/integration -q` | 41 passed，2.06s |
| `ASTRBOT_HOST_SOURCE="$PINNED_ASTRBOT_SOURCE" .venv-ci/bin/python -m pytest tests/memory/p4_native_transport.py -q` | 3 passed，0.10s；源码路径已脱敏 |
| `.venv-ci/bin/python -m pytest tests -q` | 1336 passed / 73 failed，22.55s，非全仓 PASS |

P4 文件及自有 tests 在独立工具环境执行 `ruff check`：
All checks passed；P4 路径 `git diff --check` 通过。

定向验收覆盖：

- 两公开 LM profile：真实事件门面查询；有 validate 时最终复核，无 validate
  时重查原 query/limit/profile，候选 ID/正文/全部来源一致；身份变化、重载、
  删除和 event=None 拒绝，不读私有 engine。
- 原生 OpenAI/DashScope 源码方法真实执行，SDK/HTTP transport 为合成替身；
  不是四版 AstrBot 全量真实宿主验收。验证模型/维度参数、OpenAI 零重试、
  宿主 client 不被修改、single-flight、超时、重载与持久命名空间一致。
- 向量 recall/remember/forget/validate、账号/实例/会话/人格隔离、
  模型/维度 namespace、原 TTL、容量、排队与 embedding 中途删除竞态，
  异步边界删除后的最终校验、配置关闭/切外部和 shutdown 拒绝迟到写回。
- legacy 无 embedding 读取、来源/TTL 隔离、删除/清空/到期、重启不复活、
  旧正文变更拒绝、读开关、外部不兜底、缺失旧库不创建、混合结果不伪装。
  legacy fixture 比较旧文件完整 bytes 与 st_mtime_ns，确认读取/删除/清空
  等操作未修改旧库内容或修改时间。
- Open-Meteo 单键并发缓存、成功 TTL、失败短缓存、超时、日期/单位校验、
  历史 archive、未来日期拒绝、close、UTC/GMT 零偏移别名；
  日记日期/城市/天气程序页头、Bot 第一人称、空素材不查询天气、
  天气 await 后授权重验；diary/dream/catchup/closing 独立选择共享总预算。

## 接入与缺口

收尾时只读检查主协调者的 runtime/application.py，确认已有：

- `_build_services` 构造 build_memory_backend、Gateway 与 AutoMemoryIngestor；
  本次 legacy 路径补充已由该现有调用自动接入。
- on_message 仅 accepted 事件派发自动收录；record_host_submission 持久化
  bot_reply_submitted 后派发一次，不伪造平台送达。
- 正常聊天查询和校验传真实 event；on_reply_submitted 已有最终记忆校验入口。
- `_stop_business` 关闭 ingestor / generation 天气资源，停止 runtime，
  关闭 Gateway 后才终止 lifecycle/store；配置重建使用同一关闭路径。

接线证据不等于生产验收。final validate 之后仍有 await 的风险明确交主协调者
修复：收尾所见 on_reply_submitted 在记忆校验之后还调用
maybe_close_conversation、context/watermark 查询及 record_host_submission。
任何这些 await 后的提交都需要重新授权或等价的提交时 guard；
P4 不改 Application/发送器，也不宣称上述竞态已由本子任务修好。

全仓 73 个失败交主协调者处理，不修改范围外旧 tests/迁移器：

- tests/migration 与 tests/verification/test_migration_cli 的
  `target_schema_incompatible`：storage/legacy_import.py 固定 SCHEMA_VERSION=2
  并核对完整 SQL schema hash。新版主 schema 和 P4 新增表/trigger 的兼容性
  需显式设计；不要取消守卫或把任意新增表当作可信目标。
- tests/night/test_boundaries 的旧 catchup 禁发送/禁止新依赖断言。
- tests/verification/test_cross_module 的两处旧 none/local_lite mode 断言；
  本次要求统一 LocalVectorMemory，但保留 local_lite 来源读取，两者不冲突。

未执行：生产连接/部署、收费模型、真实平台发送、四版真实宿主联合验收、
commit/push。未修改其他 repo 或 LivingMemory dirty 内容。
冻结后 P4 不再编辑上述独占实现与自有 tests；后续接线及跨模块验收由主协调者收口。

### 协调者后续整合

2026-11-06，主协调者修复最终授权检查后的晚安等待与持久化接点，
并修复跨模块迁移/边界失配。最新 `.venv-ci/bin/python -m pytest -q`
为 **1432 passed / 0 failed**，22.66s。此项是后续新运行，不覆盖上面的73个阶段失败。
四版真实宿主和远端 CI 在本条记录时尚未完成；该结果不是生产调用证据。

### 最终候选复验

以上73个阶段失败及1432项整合结果保留。最终完整可移植回归1451项通过；
记忆授权、删后迟到写回、Provider撤销、旧显式记录兼容与本地向量库回归包含在内。
同源真实宿主结果见 [宿主验收](verification-retro-host.md)；
收费模型、生产记忆、真实平台消息均未调用。
