# 私人日记与梦境（2026-11-09）

控制台提供「设置 / 日记 / 梦境」三个二级菜单。切换时播放360ms局部翻页，
减少动效模式直接切换。刷新只重读状态、列表和已有任务，不生成或删除正文。

「生成私人日记」只生成当日日记；「生成梦境」只生成当日梦境。
日期取受理点击时的有效时区，缺失使用Asia/Shanghai，跨午夜完成仍归受理日。
按当前配置的原生人格存档，同人格当天同类型只有一份；成功后替换旧正文，
保留置顶，自动任务不覆盖当天手动结果。不同人格有不同档案。

手动操作不受插件停用/观察模式、自动开关、作息/REM、日次数与模型日额度阻止。
仍需要管理员鉴权、存在的原生人格、已配置且支持预算控制的模型。
无当日合法素材时日记写自省、梦境写想象；不退到昨天，不编造真实聊天。
只写私人档案，不发送消息；无原来源授权时外部记忆同步明确跳过。

服务使用独立执行器（1个运行任务、最多16个排队），每请求只派发一次模型。
输入上界32768 token，输出8192 token，派发超时90秒；正文取配置字数和8000中较小值。
天气查询最多5秒，失败显示未获取。模型结果无效、存储失败、清除/人格/修订冲突
均不删旧正文；清除成功的记录不会被旧任务写回。

专用接口为POST `console/experience-generate`（request_id/persona_id/kind）
及GET `console/experience-task`（request_id）。生成请求不接收日期、任意模型或绕过权限标志。
刷新、轮询、页面重载只用已有request_id查询；POST超时不自动重新派发。
执行结果unknown时明确提示可能已计费；用户再次点击才发起新请求。
宿主重载将未派发任务取消、运行任务标记unknown，不自动恢复模型请求。

迁移5只新增daily/jobs表和索引，不批量修改历史。首次手动覆盖仅归并可证明
同实例、同人格、同日、同类型的旧记录，新正文、daily修订和任务成功同事务提交。

以下为0.1原始自动体验服务的历史实现资料；旧限制不适用于上述控制台手动入口。

## T7 原始实现与交接

当前日记/梦境二级页面、各用途模型、程序生成的日期与住所天气页头见
[生活控制台](life-console.md#日记梦境和记忆) 与 [P4 契约](internal-memory-contract.md)。
模型正文围绕 Bot 第一人称的授权素材发挥，天气不单独构成经历。
下文保留0.1原始体验服务参考，其旧页头与页面布局不是新版展示契约。
新版已将置顶接入原管理 `console/action`：使用真实记录来源、预期置顶状态和
事务比较更新，冲突不重试。取消置顶不刷新原日期或期限；模型调用与发送均为0。

状态：体验服务及合成专项测试已实现。尚未接入宿主页面、定时器、真实模型或发送器。
仅新增 `services/experience.py`、`tests/experience/test_experience.py` 和本文档；
没有修改 storage、contracts、main、api、schema、配置或规格，没有 Git 提交。
没有读取或复制从绫实现及提示词。提示词为本任务独立编写，版本 `experience-1`。

## 能力边界

| 能力 | 本次实现 | 接入限制 |
| --- | --- | --- |
| 日记 | 本地真实互动、Bot 成功行为、Bot/作息状态、授权外部材料和记得的梦；无材料跳过 | 默认关闭；单来源可直接使用真实 SQLite 保存 |
| 唯一性与补写 | instance/Bot/人格/时区/日期稳定 ID；默认 23:00，仅显式允许补昨天 | 不自动扫描历史日期；时区切换的存储限制见下文 |
| 梦 | 仅当前 REM、每夜最多两次尝试、清晰度衰减、过期、置顶计算 | 必须提供实时 `night_guard`；离线恢复不补梦 |
| 私人读取 | 宿主授权后读取；普通聊天和 `admin=true` 不构成授权 | 当前 SQLite 缺读取接口，必须注入 `load` |
| 置顶 | 权限检查、冻结当前清晰度、比较旧快照的更新接点 | 当前 SQLite 缺更新接口；没有 `write_pin` 明确 unsupported |
| 分享 | 当前合格来源重新生成、最终再复核、一次性有期限草稿 | 默认关闭；没有发送代码，不能返回私人全文替代分享 |
| 导出 | 两份类型明确的记录、稳定来源键、部分成功可重试同键 | 独立关闭；现有 LivingMemory/local_lite 均不具备合格写能力 |
| 跨场景保存 | 采集所有来源代际，保留原始上下文 | 没有多来源原子提交回调时，收费前返回 unsupported |

## 精确接口

导入路径：`astrbot_plugin_livingemotion.services.experience`。
`Context`、`Experience`、`NightState`、`EvidenceRef` 来自共享 `contracts`；
`Material`、`MemoryPort` 来自已有 `ports.memory`，没有第二套公共领域类型。

```python
ExperienceService(
    store: SQLiteStore,
    runtime: BackgroundRuntime,
    *,
    model: Callable[[ModelRequest], Awaitable[Any]] | None = None,
    count_tokens: Callable[[str, str], int] | None = None,
    guard: Callable[[Context, int], Awaitable[bool]] | None = None,
    authorize: Callable[[object, str, Context], Awaitable[bool]] | None = None,
    load: Callable[[str], Awaitable[tuple[Experience, int] | None]] | None = None,
    write_pin: Callable[
        [Experience, Experience, int], Awaitable[Mapping[str, Any]]
    ] | None = None,
    save_guarded: Callable[
        [Experience, tuple[tuple[Context, int], ...]],
        Awaitable[Mapping[str, Any]],
    ] | None = None,
    night_guard: Callable[[Context, NightState], Awaitable[bool]] | None = None,
    memory: MemoryPort | None = None,
    policy: ExperiencePolicy = DEFAULT_POLICY,
)

async def queue_diary(
    context: Context, *, day: str | None = None, persona_text: str = "",
    materials: tuple[Material, ...] = (),
) -> dict: ...

async def queue_dream(
    context: Context, night: NightState, *, offline_recovery: bool = False,
    persona_text: str = "", materials: tuple[Material, ...] = (),
) -> dict: ...

async def local_materials(context: Context) -> tuple[Material, ...]: ...
def outcome(job_id: str) -> dict: ...

async def read_private(
    entry_id: str, context: Context, credential: object,
) -> dict: ...

async def set_pin(
    entry_id: str, context: Context, credential: object, *, pinned: bool,
) -> dict: ...

async def queue_share(
    entry_id: str, target: Context, credential: object, *,
    request_id: str, materials: tuple[Material, ...], persona_text: str = "",
) -> dict: ...

async def take_share(
    job_id: str, target: Context, credential: object,
) -> dict: ...

async def export(
    entry_id: str, context: Context, credential: object, *,
    materials: tuple[Material, ...] = (),
) -> dict: ...

async def close() -> None: ...
```

`queue_*` 返回 `status=queued`、`job_id`，生成任务另有拟写入的 `experience_id`。
queued 不是已保存，也不是已发送。`outcome(job_id)` 只返回状态/原因/ID，
最多保留 100 条；后台未执行、被全局预算拒绝或被取消时，会查询共享 runtime 的结果。
保存成功是 `created/experience_saved`，重复是 `duplicate/experience_exists`。
正文仅由 `read_private` 或最终通过复核的 `take_share` 返回。

常见原因码：`generation_disabled`、`diary_not_due`、
`diary_backfill_out_of_range`、`no_qualified_material`、
`experience_attempt_limit`、`input_token_limit`、`output_token_limit`、
`model_response_invalid`、`model_timeout`、`context_or_evidence_changed`、
`dream_requires_live_rem`、`share_authorization_changed`。
准备阶段与可选提供者异常只返回固定原因码，不返回异常正文。

辅助纯函数：`perspective(ref)`、`parse_entry(raw, allowed_sources=..., max_chars=2000)`、
`dream_clarity(experience, now=..., policy=...)`、`dream_view(...)`、
`dream_material(...)`。这些 Python 函数不构成鉴权接口，不能直接暴露成聊天工具。
`dream_material` 对已遗忘或混合来源的梦返回 None；合格梦保留 DREAM 类型、
原创建时间和来源映射。梦正文在分享素材路径中一律拒绝。

## Foundation 接线要求

1. 单实例共享已有 `SQLiteStore`、`BackgroundRuntime` 和已配置的 `MemoryGateway`。
   不新建第二个后台执行器或模型信号量，不调用其他插件私有存储。
   不注入 memory 时使用 none，只做自有材料验证，不检索长期记忆。
2. `guard(context, generation)` 必须实时检查原生人格令牌、身份修订号、实例、
   原始范围和清除代际。服务自己也读存储代际，但不能替代人格/身份权威。
   缺 guard 默认拒绝；本地证据保留的 Context.route 可能为空，桥必须通过受信
   来源索引解析上下文，不能根据裸账号猜路由，也不能回写篡改原证据。
3. `authorize(credential, operation, context)` 的 operation 为
   `private_read/pin/share/export`。credential 是宿主验证后的不透明凭据，
   不是聊天字段。分别实现管理登录、令牌用途、Bot 私人体会访问策略与当前受众检查。
   特别拒绝页面资源令牌。共享 Python 服务不是 HTTP 鉴权边界。
4. `load(experience_id)` 返回持久记录及其**保存时的 owner generation**，
   而不是当前 generation；不存在返回 None。清除、删除、过期清理后不可返回旧缓存。
   当前没有该回调时私人读取/分享/导出不能装成可用。
5. `write_pin(old, new, generation)` 必须在同一短事务中比较旧记录/代际、
   更新 JSON 与索引中的 pinned、写入已认证操作者的审计；冲突返回 rejected。
   审计主体通过宿主请求上下文传递，不能把模型文本当操作原因。
   服务不以 `save_experience` 的 INSERT OR IGNORE 冒充更新。
6. `save_guarded(experience, generations)` 必须在保存事务内检查列表中**所有**
   来源代际，再按与 `save_experience` 相同的 `created/duplicate/rejected` 语义返回。
   多来源时不提供它，返回 `multi_scope_commit_unsupported`，不调用模型。
   只在事务外循环检查再调用单来源 save 不是这个回调的合格实现。
7. `night_guard(context, original_night)` 必须从 T5 当前输入/快照重新判断：
   同一 `sleep_started_at`、仍为 ASLEEP/REM、未醒来且非恢复补梦。
   服务还验证原输入时间新鲜度、wake_at 和 REM；入队、模型调用前、保存前都检查。
   缺回调返回 `night_revalidation_unavailable`。没有 import T5 的领域实现，
   不拥有作息状态写者、不创建晚安/叫醒/发送逻辑。
8. 生命周期推荐先停接收并 `await runtime.stop()`，再 `await service.close()`、
   关闭共享 memory、关闭 store。service.close 清掉私人草稿并拒绝迟到模型结果，
   不擅自停止别人共享的 runtime/memory。重载创建新服务，不恢复分享草稿。

**未越界补齐的存储/运行时缺口：**

- 缺体验读取、CAS 置顶更新及原子操作审计；相关测试使用明确的回调夹具，
  不能据此宣称置顶已跨 SQLite 重启持久化或管理页已接通。
- 缺跨来源代际原子检查及保存接口；默认只开放现有单来源保存能力。
- 服务日期 ID 含 instance/Bot/人格/时区，不含场景/适配器；同一 ID 通过 SQLite 主键
  防止跨适配器重复。现有 SQLite 另有 `(owner_key, kind, period)` 唯一索引，
  owner_key 含 adapter/platform、period 只有本地日期，因此对同 owner 同日期切换时区
  的限制更严格。当前不要并行配置多个时区；更换时区须由 foundation 处理唯一键策略。
  period 不被本服务私自改成非日期。无 loader 时存储因该索引返回的 duplicate
  不能反查真实已有 ID，调用方不能把拟写 ID 当作已读出的记录。
- 成功保存与不含正文的完成标记是两次事务。崩溃在两者之间最多造成受限重试的
  额外预算消耗，唯一记录仍由数据库保证。注入 loader 可以提前发现已有记录。
- runtime 全局预留与服务尝试预留也是两步；在全局预留后、服务工作开始前崩溃，
  同一稳定任务 ID 可能被保守拒绝为 `reservation_exists`，不会自动退款或换 ID 重放。
  foundation 可补 durable job-result/预留关联接口改善恢复，不应绕过剩余配额。
- runtime 不直接回传 work 结果，结果查询目前依赖有界服务元数据和 runtime.health；
  重启后的私人列表/分页必须使用持久 load/list 接口，不能拿内存 outcome 当数据库。

## 日期、预算与模型

`ExperiencePolicy` 是模块参数，不是另一份持久配置。由 foundation 从统一配置映射，
未有原生配置字段的参数先保留安全默认，不在 T7 内新增 schema。

默认：时区 UTC、日记时间 23:00、补昨天关闭、重试 2 次（总尝试最多 3）、
每夜梦最多 2 次、分享和导出均关闭；材料最多 12 条、每条入模摘要片段最多 1200 字符、
模型正文最多 2000 字符（梦保存时另加想象标记）；输入 4096 token、输出 1024 token、25 秒超时。
日记保留 30 天，梦保留 7 天。实际 token 和超时上限取策略与共享 runtime 限额的较小值。
各参数构造时验证有限值、布尔类型、时区及范围；每夜次数和重试不能调大突破规格上限。

日记采用 ZoneInfo 本地日期边界，不用固定减 86400 秒计算本地日；测试覆盖 DST 25 小时日。
当日未到时间直接跳过，补写只接受当前本地昨天，材料按原 occurred_at 归日。
服务没有周期性循环、无事不会发空模型请求；调度器显式调用即可。

| 预算 | 持久实现 | 语义 |
| --- | --- | --- |
| 共享模型日预算 | runtime 原有 `pool=model` | 按实际派发的 UTC 日期计费，与其他模型用途共享；默认上限仍为 48 |
| 日记尝试 | `pool=experience_attempt`，period=稳定日记 ID | 含失败、取消和派发后不合格；默认最多 3 次，不退款 |
| 梦尝试 | 同一 pool，period=instance/Bot/人格/入睡时刻的夜 ID | 夜间跨午夜不重置，默认最多 2 次，失败也占用 |
| 完成标记 | `pool=experience_saved`，period=体验 ID | 非模型消费，仅是不含正文的持久去重标记；清除不能重开当天费用 |

模型工作全部经 `BackgroundRuntime.submit(model=True, purpose="diary"/"dream")`。
分享复用原 kind 的 runtime 模型用途，真实模型请求 purpose 为 `share_diary/share_dream`；
因此生成开关与共享日预算同样约束分享。队列满时没有服务预留和模型调用。
runtime 可能在服务最终前置校验拒绝时已经占用模型配额，这属于保守占用，不宣称真实收费。

`ModelRequest` 字段为 `purpose/system/data/input_tokens/max_output_tokens/timeout_seconds/
prompt_version`。`model(request)` 只返回原始文本或映射，不持有任何工具、发送或管理权限。
模型桥必须把输出 token 上限落实到真实 Provider，并响应取消；`count_tokens(system, data)`
必须使用实际模型 tokenizer 和消息模板计数，对 `system=""` 的输出计数允许保守高估。
测试计数器只是合成桩，不能拿字符除以四当生产 token 计量。缺模型或 tokenizer 拒绝。
真实调用次数、Provider usage、延迟等审计由模型桥关联 job/purpose 记录，不记录正文。

JSON 容错只恢复围栏、嵌入对象、字符串外尾逗号及 `entry` 正文字段别名，
不把任意纯文本错误当文章。拒绝 error/exception/refusal 包装、失败状态、重复 JSON 键、
NaN、未知引用、无正文、危险控制符、URL/图片/HTML。未提供引用列表时保留全部合格输入；
即使模型只声称用了一部分，持久 Experience 也保留全部入模引用。

## 来源、清晰度与分享

本地记录只能来自 `read_window/get_state`：human 消息主体必须匹配来源账号；
Bot 只接受 `bot_action_succeeded` 且 actor_id 匹配 Bot，失败/普通未确认 Bot 文本不认领。
每个本地素材在模型等待前后重新核对实际记录，不能用 `provider=livingemotion` 自封可信。
Bot 和 night 状态只提取有界结构字段，不搬 `_runtime` 或其他私人解释。

材料视角为 `own_action/own_state/other/dream/unknown/summary`。
SUMMARY 必须带 source_ids，不伪造成原始消息；材料携带原 subject/holder/Context、
受众、时间和引用，不把对方做的事当成 Bot 做的。模型资料中不附带 authorization 凭据。
所有引用保持原 TTL；保存日记不会延长原始正文窗口。

梦清晰度为 `clarity * 2 ** (-age / half_life)`，默认半衰期一天。
未置顶到 expires_at 清晰度为零；置顶冻结当时清晰度，不恢复已忘细节。
默认低于 0.5 不返回具体正文，低于 0.1 标为忘记；置顶也不能复活已忘的梦。
取消置顶保守按原创建时间继续计龄，不重置年龄，可能立即变淡或过期。
梦正文由服务增加 `Dream (imagined):`，输出和导出始终带 DREAM/imagined 类型。

分享需要当前受众有明确访问策略，不是管理员可读全文就自然允许往任意群发。
分享只选同时满足原来源关联和**当前目标授权**的素材，来源关联还比较 provider 和
原 account_key，不能把两个群内同号 source_id 当成同一事实。
模型看不到原日记/梦全文；既不能做删名字式“脱敏”，也不能把已生成梦正文作为分享输入。
混合来源梦不能被 `dream_material` 压成一个场景的素材。无当前授权材料就跳过。

分享结果保留最多 60 秒，`take_share` 再核验记录是否被删/改、梦是否遗忘、
全部材料、受众/路由令牌、人格、身份和来源代际，失败废弃整份结果。
草稿只能取一次，返回 `authorized_draft_not_sent`，并不发送。
T6 消费后若发生任何 await，仍须在它自己的单一发送边界重新授权；本服务的检查
不是永久发送许可，不负责撤回之前已经合法发出的内容。

## 独立导出

必须同时开启 `policy.export_enabled`、统一配置 `memory_export`，
且后端 `capabilities().append_experience=True`。还要求所有原引用 exportable、
完整匹配的当前材料、同一 account_key 范围及当前授权，混合私密全文默认不导出。
本地素材默认 exportable=False；不因打开总开关就静默改写旧来源授权。

每个体验输出两个稳定键：

- `le-export:{experience_id}:action`：BOT_ACTION，只有“写过日记/做过梦”这一真实行为。
- `le-export:{experience_id}:subjective`：DIARY/DREAM，正文带 subjective、imagined、
  `exclude_from_fact_extraction`、`exclude_from_experience_material` 标记。

二者均保留原 source_ids、主体、持有者和期限。日记及任意 `le-export:` 来源/祖先引用
不能作为下一轮体验材料；梦不能转 FACT。后端必须保留这些类型与血缘并在抽取端排除，
不能洗掉来源标签后重新承诺无反馈循环。

两次写入不是跨库事务：一次成功后失败返回 unknown；没有内部自动重试。
调用方显式重试仍使用同一组键，后端负责幂等确认，不能换新来源制造重复。
写后才发现授权改变时报告 unknown，不能假称外部副作用已撤销。
现有 LM 缺后台幂等 append/核实门面时返回
`idempotent_experience_export_unsupported`，并保留能力中的
`external_idempotent_export_unsupported` 原因。没有伪造事件、私有引擎调用或 SQL 穿透。

## 信任边界与验证策略

专项：`llm-application-security`，置信度高；产物是实现及来源/授权边界验证。
目标是管理私人主观体验，不是让模型操纵权限或发消息。不可接受的是跨 Bot/人格/
受众泄露、把梦认成事实、错误响应保存成日记和无界费用。授权失败交由管理页说明原因，
不让模型自行“修复授权”。

| 边界/权限 | 确定性控制 | 反例验证 |
| --- | --- | --- |
| 素材/人格 → 模型 | 独立 system/data、限长限 token、结构化来源、无工具权限 | 素材含命令仍仅在 data，未知模型引用拒绝 |
| 当前来源 → 私人记录 | guard、真实本地重读、类型/持有者校验、代际保存 | 伪造本地事件、跨 Bot/人格/实例、生成中清除 |
| 私人记录 → 群聊 | 不给模型全文，只给当前有权证据，最终复核 | 混合私聊、相同裸 source_id、模型等待及 ready 后撤权 |
| 输出 → 页面 | 仅纯文本结果，阻止 URL/HTML，宿主必须 textContent/转义 | URL、图片/标签和控制内容不进入正文 |
| 输出 → 外部记忆 | 显式权限、幂等键、两种类型、无工具调用 | 部分成功后同键重试、反馈来源拒绝、LM unsupported |
| 输出 → 命令/查询/发送 | 无这些输出执行路径 | 没有 shell、SQL 或 sender 接口 |

模型输出也可能语义上编造细节：确定性来源检查和短提示不能证明自然语言忠实。
本轮是合成模型桩的控制流/边界评估，不是已完成真实模型质量、内容审核或对抗红队。
上线桥还需按宿主内容政策处理输入/输出审核，不把模型自评作为授权。
没有使用训练、微调、外部索引或模型下载资源，故不产生此类供应链变更。
普通 outcome/runtime 健康不含正文；完整 prompt/response 默认不记录。
关闭 diary/dream/share/export 各开关可分别停用；停止 runtime 并 close 服务释放在途/草稿。

## 真实验证证据

环境：2026-11-05，macOS 15.6.1 (24G90)、arm64、Python 3.11.9；
使用已有 `/tmp/livingemotion-adapters-venv`。此版本只验证无宿主领域路径，
不宣称满足 AstrBot 的 Python 3.12 安装验证。

执行目录：`插件/astrbot_plugin_livingemotion`。

```bash
/tmp/livingemotion-adapters-venv/bin/python -m pytest tests/experience -q \
  -o asyncio_default_fixture_loop_scope=function --tb=short

/tmp/livingemotion-adapters-venv/bin/python -m pytest \
  tests/experience tests/storage tests/runtime tests/contracts \
  tests/memory/test_modes.py tests/identity/test_identity.py \
  tests/identity/test_persona.py -q \
  -o asyncio_default_fixture_loop_scope=function --tb=short

/tmp/livingemotion-adapters-venv/bin/ruff check services/experience.py tests/experience
/tmp/livingemotion-adapters-venv/bin/python -m compileall -q \
  services/experience.py tests/experience
```

最终结果：**体验专项 91 passed / 0.86s；联测 228 passed / 2.31s；
Ruff 全部通过；compileall 退出码 0。**

首轮 69 passed / 5 failed，失败来自测试误认为关闭后的 Store 可以复开、
误认为 health 包含 experiences 计数。已改为重新创建 Store/Runtime 打开同一临时库，
用公开 save 的 duplicate 与 cleanup 结果验证真实落库，后续全部复验通过。

| 验证目标 | 证据范围 |
| --- | --- |
| C23/C24 | none 下互动/状态成功生成；无来源/假本地/反馈跳过；成功回执视角、未知来源、摘要映射、JSON 反例 |
| C25/C29 | REM/醒来/过期/离线输入，跨午夜重启两次上限，衰减和置顶计算；置顶存储仅验证回调，不冒充真实持久化 |
| C26 | 原全文不入分享模型；来源同号跨场景；身份/人格/清除/删除/权限在两个异步阶段撤销；低清晰度不补细节 |
| C27 | 默认关闭、LM unsupported、幂等后端桩部分成功重试、来源反馈排除；不代表真实 LM 写入已支持 |
| C49/C50 | 实际临时 SQLite、共享 runtime、失败/取消计费、队列满、并发重复、真实重开库、token/timeout、午夜派发预算 |
| 清理/隐私 | 真实 SQLite 原正文 TTL/体验到期清理，健康结果无正文，伪造 admin 拒绝，关闭中迟到模型不能保存 |

fixture 的 load/pin 只服务于接口测试，不直接读写 SQLite 内部表。
真实持久化、唯一键、预算、重启和 cleanup 使用真实 SQLiteStore 公开方法。
不含真实用户素材、真实 Provider、真实发送、生产部署或完整宿主页面验证；
规格/验收复选框仍由集成者维护，本任务没有勾选它们。

已验证源文件 SHA-256：

```text
13f6c478d539dc7757e6929413a97423ac5fc33da920ac3bfe1f7e26746e623c  services/experience.py
a7de707029e3b4ddd736971b3adde91ab7ff3717efca609ee87f88ab4f234e05  tests/experience/test_experience.py
```
