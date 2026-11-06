# 身份、人格与记忆适配

## 改版记忆入口

当前读取、向量模型、自动收录、删除与旧显式记录行为见
[生活控制台](life-console.md#日记梦境和记忆)、[P4 接入与实测](internal-memory-contract.md)。
LivingMemory 开关开启只使用公开门面；关闭提供本地向量接口，
读取与自动写入分别控制，复用 AstrBot 原生向量 Provider。
下文保留0.1的原始端口参考，三模式名称不代替新版接入开关。

## 当前使用边界

读者：记忆接入开发者与维护者。2026-11-05 依据 `adapters/memory/`、
`runtime/application.py` 和 `runtime/materials.py` 核对；接口变化时同步，每次交付复核。
Application 已构建三模式，local_lite 实际库名为 **`explicit_memory.sqlite3`**；
没有用户录入页面/命令，开启模式不自动抽取事实。
LivingMemory 后台检索与幂等导出仍为 unsupported，不伪造事件、不修改 LM。
真实宿主证据与最终待验状态统一见[兼容矩阵](compatibility.md)；
下方专项验证数量保留原证据，不代表最终源码或整体 T4 通过。

责任：T4 / `emotion_adapters`。共享类型只引用 `contracts.py`，未修改该文件、关系领域或旧插件。
本实现独立编写，没有复制从绫函数、提示词或素材。宿主调查采用 `host-contract.md` 的结果，
不把合成测试当作真实宿主加载、真实消息发送或生产兼容验证。

## 给父代理的接点

| 接点 | 实际实现 |
| --- | --- |
| 来源 | `adapters.identity.context_from_event`；读取真实 self_id、sender、platform_meta.id/name、UMO 与群字段。Bot 键含宿主实例、平台实例、适配器类型、平台、Bot 账号 |
| 人格 | `PersonaAdapter.resolve/validate`；所有前后台调用共用一个实例，模式 `follow/explicit/none`。`AstrBotPersonaSource` 调用已核对的原生 `resolve_selected_persona` |
| 身份 | `IdentityAdapter.resolve/validate/project_sources`，返回不可变快照和原来源键；投影入口先实时复核修订号。`one_id` 与 `person_id` 同值，冲突拒绝 |
| 记忆入口 | `MemoryGateway(backend=None)` 默认 none；`capabilities/recall/validate_evidence/append_experience` 对应 `ports.memory.MemoryPort` |
| local_lite | Application 构造 `LocalLiteMemory(data_dir / "explicit_memory.sqlite3")`，受信集成可通过 `remember(request, material)` 显式录入有来源、有期限文本；不是用户页面功能 |
| external | `LivingMemoryAdapter(provider_getter, read_enabled=..., export_enabled=...)`；getter 每次重新发现当前实例，不能缓存旧插件实例 |
| 生命周期 | 卸载时 `await gateway.close()` 取消并等待自有检索任务；local_lite 每次事务关闭连接，取消时等待线程完成 |

`context_from_event` 的 `platform` 是宿主桥提供的规范平台，`audience` 是宿主确认的当前受众。
这两个参数不可从聊天正文或模型输出获得。`adapter_id` 保存真实平台实例 ID，Bot 键同时保存
适配器类型的隔离信息；UMO 原样保存，绝不拼出发送路由。没有 Bot 账号、受众、路由或明确
私聊/群聊类型时拒绝创建来源。公开评论等其他场景尚不映射为私聊。

集成方先解析原生人格，再解析身份，将返回的 `snapshot.context` 放入 `MemoryRequest`。
发送端最终必须重读人格/身份并调用 `validate_evidence`，不能继续使用生成前的上下文。
可向 `MemoryGateway` 注入 `context_guard(context, event) -> await bool`，让它在外部等待前后
再次核实人格、身份、清除代际和当前发送范围。任何失败都废弃整份生成结果。
自有或 local_lite 材料若携带 `livingmemory:` 身份修订号但没有 guard，默认拒绝使用，
不能以本地材料为名绕过解绑。

入口 `main.py`、`api.py`、统一配置与发送器已有 Application 接线，最终集成验收另行记录。
配置层已有 `memory_mode/memory_read/memory_export`，应原样分别传入，不能因开启读而自动开启写。

## 原生人格

`AstrBotPersonaSource` 已按 host_contract 的 AstrBot 4.29.4 签名调用：

```python
await persona_manager.resolve_selected_persona(
    umo=route,
    conversation_persona_id=current_conversation_persona,
    platform_name=adapter_type,
)
```

会话配置优先级由原生管理器决定。当前 conversation 的读取、原生 Persona 对象正文渲染、
显式人格查找由宿主桥注入回调，不重复建立另一套优先级，不只读 default_persona。
`[%None]` 保留原生无人格语义。宿主的 webchat 特殊默认人格尚无已验证渲染回调时返回
`native_webchat_special_rendering_required`，不能用固定角色或空白冒充。

人格版本包含模式、人格 ID、实际正文和原生 revision 的指纹，并为观察到的每次切换生成
新令牌；A→B→A 不复用旧 A 令牌。缓存最多 512 个来源，重新解析被淘汰的来源会使旧令牌失效。
普通请求只通过 `foreground_suffix` 附加有长度上限的状态，不再次复制原生人格正文。
后台使用同一个 `PersonaAdapter` 解析器，provider/model ID 从来不是人格或 Bot 身份。

## 三种模式

| 模式 | 读取 | 写入 | 自有材料 |
| --- | --- | --- | --- |
| none（默认） | 不查询长期记忆 | 不抽取、不导出 | 合格的真实互动、状态/行为引用仍可用 |
| local_lite | 当前完整来源范围内的关键词检索 | 仅显式文本录入；必须有 source_ids 和期限 | 继续可用 |
| external | 仅真实事件的合格公开门面；读开关独立 | 当前门面不具备合格幂等写入，明确拒绝 | 外部失效时仍可用 |

local_lite 只有一个可选轻量文本库，不包含向量、图谱、模型调用或自动事实抽取。
默认每来源账号范围最多 200 条、全库 1000 条、期限上限 30 天，正文每条最多 16000 字符。
按原 occurred_at/expires_at 保留，重复录入不会刷新 TTL。相同来源 ID 不同正文返回冲突。
删除、过期、容量淘汰后，先前拿到的缓存和引用也无法通过最终复核。
数据路径必须由 `StarTools.get_data_dir` 提供，不能放源码目录；不使用状态数据库或 LM 库。
local_lite 的单独事务不宣称与情绪事件事务原子。关闭模式不删除库，切换后端不迁移外部数据。

## 已核实的 LivingMemory 契约

只读调查入口为工作区 `插件/LivingMemory/main.py:151-181`，以及其公开契约文档和测试。
本任务没有访问运行期 initializer、引擎、私有存储或 SQL，没有修改 LM。

| 公开方法 | 真实输入/输出 | 使用限制 |
| --- | --- | --- |
| `resolve_identity_context(event, persona_id="")` | 真实事件 → dict；含 source_account、one_id/person_id、identity_revision、owner_account、场景、受众、bound_accounts | 缺 revision、来源不匹配、提供者失效时仅保留本地来源账号隔离 |
| `search_memories_for_event(query, event, *, persona_id="", k=4)` | 返回对象列表，条目包含 doc_id/content/metadata | 不接受本插件为后台任务构造的假事件 |
| `validate_identity_results(results)` | 原始结果列表 → 当前仍有效列表；也可能异常 | 模型等待结束后再次调用，数量、正文、来源、revision 任一变化整份作废 |

`project_identity` 是归属投影，不是后台读取授权；`search_context` 不具备此任务要求的完整
Bot 持有者、原始来源和最终授权契约，不能作为缺省回退。测试仅构造公开返回值的合成夹具，
不导入 LivingMemory 运行时代码。

**当前明确降级**：尚未确认基于持久来源的后台授权门面，也未确认带幂等键、
写后查重的体验写入门面。能力返回 `external_background_authorization_unsupported` 和
`external_idempotent_export_unsupported`；开启 export 配置也不会冒充支持或自动重试。
本任务不请求或自动增加 LM 门面。日记/梦/主动可先使用自有合格材料。

## 来源与授权

每个 Material 都有 `EvidenceRef`，不接受提示词字符串或旧 `congling:*` 块作为检索凭据。
外部适配的保守范围是原场景、原账号、原 Bot、原人格，不自动启用 LM 更宽的共享政策：

- `source_session_id` 必须存在且与真实事件 UMO 完全一致；据此确认原适配器与私群场景。
- `source_account`、`owner_account` 与真实事件身份快照一致；subject_accounts 必须明确且为单一主体。
- 原 persona_id、原 audience、合法整数 sensitivity、有限 create_time、当前 `_identity_revision` 必须存在。
- 类型必须显式给出，或由真实 source_window 识别为 SUMMARY；绝不把摘要直接标成 FACT。
- 摘要保留原 source_ids 或原会话消息窗口起止索引引用，不把摘要伪造成原始消息。
- 混合来源、过宽受众、缺持有者、缺时间等记录拒绝，原因是 `external_provenance_incomplete_or_out_of_scope`。

引用的 Context 保存完整 Bot/账号/适配器/平台/私群/人格/版本/受众，真实主体和持有者分别保存。
sensitive 保存布尔敏感标志，原始敏感级别及全部 LM 元数据保留在短期复核回执中；
authorization 是本进程有界回执句柄，不是可伪造的管理员标志，也不是跨重启令牌。
最多保留 256 个外部回执；过期/被淘汰、提供者重载或原始数据变更均拒绝复用。

同请求、用途、完整来源与后端实例组成缓存键；同键不同 query/limit 返回冲突。
最多 128 个缓存和 128 个在途查询；相同键并发合并为一次检索，不因复核失效再次检索旧请求。
已有合格材料优先复用，但每次仍复核。限额固定构造时校验；调整时替换 gateway 并关闭旧实例。

身份绑定只改变 `IdentityAdapter.project_sources` 返回的原始来源 Context 集合，不搬原事件、
关系原证据或数值。该集合仅表示当前归属，不授予跨场景读取权限；关系消费者还需应用自己的
场景/受众过滤。无身份服务时身份键含宿主 Bot、适配器、平台、账号，同名、同模型、同人格不合并。
外部修订号、绑定账号集合或提供者实例变化使旧快照失效；没有后台权限接口时不假造事件续权。

## 数据边界与运维

上下文传播：真实事件 → 原生人格 → 身份快照 → MemoryRequest → 来源过滤/回执 → 生成 →
当前上下文及最终复核 → 唯一发送器。任一步缺来源不放宽范围。
本模块不打印正文、日记、账号明文或提供者异常文本；返回结构化原因码，由父级按请求/用途 ID
关联审计。显式录入、删除、分享与导出的人机权限和操作审计属于宿主已认证入口责任，
不能直接向模型暴露这些 Python 方法；`admin=true` 不作为授权。
解绑是逻辑撤销，不撤回已发送消息或已交付给外部模型的数据。
清除全域自有状态时，父级应同时删除指定 local_lite 来源并使 context_guard 的清除代际失效。

## 历史专项验证（不替代最终验收）

专项测试命令：

```bash
/tmp/livingemotion-adapters-venv/bin/python -m pytest \
  tests/memory/test_modes.py tests/identity/test_identity.py \
  tests/identity/test_persona.py -q -o asyncio_default_fixture_loop_scope=function
```

最后一轮专项测试：**81 项通过，0.21 秒**，Python 3.11.9 隔离 venv；
pytest 9.2.0、pytest-asyncio 1.4.1.post1、Ruff 0.17.3。T4 文件 Ruff 检查通过。
此处 Python 3.11 只验证无宿主依赖的适配器，不用来宣称符合真实 AstrBot 的 Python 3.12 要求。
测试使用合成账号、临时 SQLite、可控时钟、公开门面桩；不连接平台、不调用模型、不真实发送。
覆盖三模式、TTL/限额/删除、请求用途并发去重、OneID 别名、无服务隔离、原证据不搬迁、
检索中解绑、最终复核中解绑、缓存/提供者失效、人格改文/切回、原生选择器参数及明确降级。

目录级首轮额外收集了其他代理的关系测试：95 passed、2 failed、29 subtests passed。
失败为 `tests/identity/relationships/test_relationship.py` 的晚到事件与人工修正、
绑定后 trust 维度叠加反例，已向父代理报告，T4 未修改这些文件。
真正的宿主人格对象渲染、插件加载及主发送链联调仍由 host_contract/父代理验收。
host-contract 最新记录的 v1 页面资产令牌越权风险必须由父代理的管理入口处理；
这里的 Python 数据端口没有提供或替代 HTTP 管理鉴权。
