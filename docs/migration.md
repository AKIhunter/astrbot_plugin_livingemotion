# T10 离线迁移与回退

## 当前入口与待验

读者：离线迁移操作者和运行约束维护者。2026-11-05，F3 已结束并交接；
本次仅更新说明，不修改迁移实现、测试或既有证据。
CLI 的 `preview/import/verify/rollback-plan` 已实现，
请从[安全决定](#安全决定)和[精确 CLI](#精确-cli)开始。
依据为 `tools/migrate_legacy.py`、`storage/legacy_import.py`、`runtime/legacy.py`；
维护者在映射/schema/约束变动时同步，每次迁移前及每次交付复核。

F3 专项 74 项通过；**History/最终 guard/启用开关后的独立联合验收仍待完成**。
原绝对冷却不续期，旧计数只计一次；未知范围/时区/梦周期拒绝，
迁移来源不因开启 export 自动获权。正文按原时间起最多七天，旧 pinned 不豁免，
清理只去正文，保留非正文约束和幂等回执。
下方 F3 交接、失败反例与旧命令保留为阶段证据，不能据此认定当前核心已全部修复。
当前总状态以[交接](delivery-notes.md)及[独立组件证据](verification-components.md)为准。
本文提到的 verification 原始日志/XML/JSON 仅本地保留，不随仓交付；
可按下方命令在隔离环境复跑，不能以缺少随仓原始产物抹掉历史失败。

## F3 核心协议（原专项交接保留）

**修复前独立反例，核心必须闭环：** 已读 `tests/verification/test_migration_cli.py`
及 `tests/verification/evidence/migration-01.log`：当轮 5 failed / 47 passed。
四种旧限制经 CLI 导入和重开后，直接 `BehaviorService + store.behavior_history`
仍 eligible，均调用一次桩模型和发送；八天 cleanup 仍留窗口正文。
测试不经过 Application，不能仅在 Application 前置判断修复。
请核心在公开 `SQLiteStore.behavior_history`/行为最终 guard 接入同一纯评估器：
已知旧计数/未回复/冷却必须进入真实 History；无法确认范围/时区的拒绝原因
必须由行为服务硬闸门消费（不要伪造极大用量或发送记录表达拒绝）。
若 Store 已合并，Application 不得再次相加。以上验收文件本代理只读、不改断言。

`runtime/legacy.py` 已完成，迁移专项 **74 passed**（原 46 + F3 28）。
**核心接线检查项**：实施中曾见 Store 失败兜底使用 `global_used=2**31-1`、
`unanswered_count=2**31-1`、`last_attempt_at=now` 会虚构计数并每次刷新冷却。
请核心统一给 `BehaviorHistory` 增加或采用语义等价的硬闸字段：
`legacy_reason_codes: tuple[str,...]=()` 与 `legacy_cooldown_until: float|None=None`，
Store 保留真实 native+legacy 计数，将纯函数 reason_codes/绝对冷却填入这两个字段；
BehaviorService 每次 `_gates`（包含最终 authorize）消费拒绝原因及绝对截止。
异常也用 `legacy_constraints_invalid` 明确硬拒绝，不伪造时间/数字。
纯函数的 `last_attempt_at` 故意保持 None，真实旧尝试时间在 `sources` 里仅作解释，
避免当前 cooldown 配置重新赋予旧尝试一段 TTL。F3 不修改服务或 Store 文件。

F3 独占迁移模块、迁移测试、新增 `runtime/legacy.py` 与本文；不修改核心文件。
已读真实 schema 2：`states` 无 expires 列，使用 value JSON 的绝对期限，不改指纹。

```python
await store.legacy_baselines(limit=2000) -> tuple[dict, ...]
# 全库一次只读；每项 record_key/scope_key/generation/version/updated_at/value。
# value 只含 source_id/source_hash/classification/identity_resolved/target_context/
# baseline/activation_blockers/runtime_constraints；baseline 必须排除 pending_crawl。
# 超限、坏 JSON、未知结构均抛异常，Application fail closed；不得截断后当作完整集。

evaluate_legacy(rows, context, *, purpose, timezone, now, human_watermark) -> dict
# F3 提供；用途 behavior/emotion/diary/dream/export；allowed + reason_codes。
# 亦可调用 evaluate_legacy_constraints(records, context, now, *,
#     purpose="behavior", timezone="", human_watermark=0)。
# 固定返回：
# allowed: bool；reason_codes: tuple[str,...]；rule_version="legacy_constraints_v1"；
# global_used_floor/scope_used_floor/unanswered_floor: 非负 int；
# cooldown_until: float|None（原绝对截止）；last_attempt_at: None；
# sources: tuple[dict,...]（来源 key/hash/scope/classification、旧计数与旧尝试时间）。
```

`allowed=True` 只表示旧约束可解释采用，不代表已经满足现行发送限额、身份或场景许可。
`allowed=False` 时同样可能带有已知用量和冷却：保留这些数据供解释，但不得执行。
未知/坏结构统一 `legacy_constraints_invalid`；重复同一来源行只算一次，
同键不同记录、重复旧会话或多安装来源无法证明互不重叠时均拒绝，不猜相加关系。

**核心必须配合的语义，不能只接一个开关：**

1. `*_used_floor` 是旧数据内部去重后的用量，不含新库 reservations。
   核心应 `native_used + legacy_used_floor`，不能 `max(native_used, legacy_used_floor)`；
   旧全局与旧场景在 F3 内按 `max(global, sum(distinct_sessions))` 计一次。
   未回复同样在新 human 之前加旧值；F3 在实际导入事务捕获该 scope 的
   `human_watermark`，以 `runtime_constraints.import_human_watermark` 持久保存；
   仅严格大于此水位的新 human 才解除旧未回复（不解除冷却/额度）。
   `cooldown_until` 是硬绝对截止，不得拿导入/读取时间重新计算 TTL。
2. 所有生成/外发/导出入口与最终 guard 都消费 `allowed`；模块缺失、读取失败、
   原范围/时区/夜周期不明必须拒绝。普通聊天规则状态不受影响。
3. cleanup 保留非正文 baseline、runtime_constraints、source_refs、来源/幂等回执；
   到 `min(history_expires_at, updated_at+604800)` 时清除 `original` 和
   `baseline.pending_crawl`，只设置 `history_redacted=true`，不删除整条约束。
   F3 档案的 updated_at/期限基于原记录时间；无 F3 期限的旧档案请立即保守脱敏，
   不从首次 cleanup 起续七天。显式清除 scope 按既有代际规则。
4. 原生迁移 Experience 同样有原始 created_at 起算的最长七天绝对 expires_at；
   provider=`congling.snapshot` 的体验在 load/query/cleanup 时必须让 expires_at
   优先于 pinned，pin 接口不得延长或跳过此期限。档案保存旧 pinned 仅为来源信息。
   否则只清 original 仍会通过 experiences 副本保留正文。

选择文件可增加每行 `constraint_binding={"timezone":"UTC","quota_scope":"scope"}`，
global 行须 `quota_scope="instance"` 且显式 context_id。这是运营核实的范围/旧时区声明，
纳入清单哈希；不是当前 runtime timezone 配置自动补证，也不改变裸 ID 映射限制。
`runtime_constraints` 使用 version=1、timezone/quota_scope 和导入事务水位，
不能从 activation_blockers 是否为空、runtime_adopted=true 推导授权。
仅当旧时区有效且与当前时区字符串完全一致，旧日 `quota_period` 为标准 YYYY-MM-DD，
才按该时区判断是否到下一日；过去日用量归零，当日保留，未来日明确拒绝。
旧全局范围未知或旧场景未映射会阻断全实例行为，避免窄 scope 查询漏掉旧全局额度。
不提供梦夜周期的猜测采用：旧 dream quota 非零或缺失时拒绝 dream，
明确返回 `legacy_dream_period_unresolved`，不因日期变化或新开关而放行。
梦额度与迁移导出按同 Bot/人格/适配器/平台 owner 隔离，不可通过更换 scene 绕过；
未知 owner 保守拒绝。迁移来源不能只因 export 开关开启而获得授权，
返回 `legacy_export_forbidden`。其他 Bot 的已映射档案不跨 owner 采用。
emotion/diary 不因无关的旧行为基线被阻断，但仍须过各自核心授权、素材、预算守卫。
未知来源关系仍不跨账号；旧 pending 永不恢复。

日期：2026-11-05。范围仅为 `storage/legacy_import.py`、`tools/migrate_legacy.py`、
新增 `runtime/legacy.py`、`tests/migration/` 和本文（CLI 本轮无需改动）。
没有修改核心 store/schema/contracts/main/api、其他 runtime 或 services、
其他集成文档、父规格复选框或既有插件，没有 Git 提交。

**四个 CLI 子命令已经实现并运行。当前是保守导入，不是旧执行器的无缝续跑。**
F3 已实现纯约束和有界正文保留，`activation_blockers` 仅作报告，运行拒绝来自纯评估结果。
核心负责公开读取/清理/真实 History 与最终 guard 接入；独立 components 负责开关启用后的
模型/发送/导出联合复验。本代理不等待、不冒充完成该验收。

## 安全决定

T10 原专项为 `database-operations`；F3 按 `migration-and-deprecation` 收敛替换与防绕过，
置信度高。对象是可选、停机、有限批次导入；
不替换旧库，不升级目标 schema，不触碰消费者运行配置。

| 阶段 | 检查与停止条件 | 回退 |
| --- | --- | --- |
| 准备 | 运营明确提供一致快照；停止目标插件及全部写者 | 无修改 |
| 预览 | 只读 schema、来源版本、选定行、来源证明、清单哈希 | 无修改 |
| 导入 | 核对快照/清单/实际实例、精确 schema、代际、冲突 | 任一失败整批事务回滚 |
| 对账 | 每个目标字段与回执比较；报告缺失/变更，不修复覆盖 | 保留新记录，人工决策 |
| 消费者回退 | 停新执行者，保留新库，再恢复明确的消费者选择 | 不将旧备份覆盖新库 |

源和目标均要求绝对路径、现有普通文件；不创建数据库，不搜索默认路径，不读取生产库。
源文件 SHA-256 在只读前后及提交前核对；源连接使用 `mode=ro&immutable=1`、
`query_only=ON`、`trusted_schema=OFF`。目标预览/对账同样只读。
两库同文件、硬链接同 inode、符号链接文件均拒绝。

任一 `-wal/-shm/-journal` 旁文件存在，即使为空也拒绝；**绝不能删除 WAL 来绕过检查**。
需要快照时由运营另行使用 SQLite backup 等一致性工具，关闭备份连接后交付独立文件。
本工具不提供“自动复制活动库”。测试用真实临时 WAL 写者和 SQLite backup 证明，
直接活动库被拒，备份包含已提交 WAL 中的数据。仅凭文件头不能证明一个手工复制的
主库没有遗漏历史 WAL；`--snapshot-confirmed` 是运营声明，不是密码学一致性证明。

锁/资源风险：单连接、`BEGIN EXCLUSIVE`、`timeout=0`、`synchronous=FULL`；
有竞争写者立即失败，不等待、不自动重试、不分段提交。一次最多 500 个旧记录、
合计映射写入 JSON 16 MiB、单记录 128 KiB、数据库文件 512 MiB。
独立导入不能与 runtime 写者竞争，停机声明是必要前提；SQLite 锁无法阻止导入结束后
被外部重启的 runtime，工具不冒充进程管理器。无副本/网络，复制延迟和故障转移不适用；
停机期间不得把目标当关键在线读写路径。事务崩溃恢复只在合成临时库演练。

## 精确 CLI

入口可以从任意目录用 Python 3.10+ 运行，无 AstrBot/模型/网络依赖；
实测版本是 Python 3.11.9。以下路径均为**操作示例**，本任务没有创建或访问这些数据库。
在插件根目录执行；各报告必须是尚不存在的新文件。

```bash
python3.12 tools/migrate_legacy.py preview \
  --snapshot /tmp/le-migration/old-consistent.sqlite3 --snapshot-confirmed \
  --target /tmp/le-migration/livingemotion.sqlite3 --target-stopped \
  --selection /tmp/le-migration/selection.json \
  --output /tmp/le-migration/manifest.json

python3.12 tools/migrate_legacy.py import \
  --snapshot /tmp/le-migration/old-consistent.sqlite3 --snapshot-confirmed \
  --target /tmp/le-migration/livingemotion.sqlite3 --target-stopped \
  --manifest /tmp/le-migration/manifest.json

python3.12 tools/migrate_legacy.py verify \
  --snapshot /tmp/le-migration/old-consistent.sqlite3 --snapshot-confirmed \
  --target /tmp/le-migration/livingemotion.sqlite3 --target-stopped \
  --manifest /tmp/le-migration/manifest.json

python3.12 tools/migrate_legacy.py rollback-plan \
  --target /tmp/le-migration/livingemotion.sqlite3 --target-stopped \
  --consumers /tmp/le-migration/consumers.json \
  --output /tmp/le-migration/rollback.json
```

退出码：0 成功/计划生成；2 参数、来源、schema、冲突或 I/O 拒绝；3 对账不一致。
JSON 报告独占创建、权限 0600，不覆盖输入/已有文件。预览包含主键、范围及来源标识，
须当敏感运维资料保管，但不输出日记、消息、原因正文。错误不打印原始 SQL/私密内容。
导入已提交但外部报告写出失败时，先 `verify`；重复 `import` 不会重放。

最小 `selection.json`：

```json
{
  "format": 1,
  "source_id": "operator-assigned-stable-old-installation-id",
  "rows": [
    {
      "table": "persona_state",
      "key": {"persona_id": "old-persona", "scope": "user", "subject_id": "human"},
      "context_id": "existing-target-context-id",
      "source_session_id": "old-session"
    },
    {
      "table": "affinity",
      "key": {"persona_id": "old-persona", "subject_key": "123"}
    },
    {
      "table": "kv", "key": {"k": "proactive.sessions"},
      "member": "old-session", "context_id": "existing-target-context-id"
    },
    {
      "table": "kv", "key": {"k": "night.dreams"}, "member": "original-dream-id"
    }
  ]
}
```

`rows: []` 可先仅查看 schema/表数量；空选择不能执行 import。
`key` 必须提供该表完整原主键；不支持任意 SQL、通配符或按裸账号扫描。
来源安装 ID 须在重复导入中保持不变，不要换 ID 绕过冲突。
`context_id` 必须来自目标已注册的真实上下文（管理页或公开来源注册结果），
工具读取 `source_contexts` 并校验 `Context.account_key/scope_key`。
它从目标 `runtime_meta.instance_id` 读取实际持久 ID，拒绝缺失、空或 `local`；
不会把一个默认 `local` 自动升级为真实宿主。目标需先由插件正常初始化并停机。
注册来源但尚无状态行时，代际为 0。省略 context_id 的记录逐原记录隔离到
`legacy_unknown` 范围，不登记可发送路由，不在真实账号间聚合。

`source_session_id` 是运营核实的旧会话映射，不是发送路由。
只有同一旧来源消息 ID、会话、sender、source_account 都匹配且目标账号明确时，
才视为人类观察；persona_state 还核对原 persona/subject 与引用事件。
缺引用/角色证据则保留 unknown。原生人格仅映射引用，不导入固定角色正文。

有限消息窗口必须同时提供选定 `msg_archive` 主键与
`"window":{"since":1800000000,"until":1800000600}`。
最大跨度 7 天、最多 200 行，每行时间必须落区间内。窗口仅作私人来源历史，
不会重放为 live event，不形成情绪刺激或补课队列。
`mem_atom`、向量、主体档案等表永不接受选择；未识别源列只报告名字，不复制内容。

选择文件顶层可选 `history_retention_seconds`，默认 604800，只允许整数 1..604800。
正文期限从 msg.ts、diary/dream.created_at、观察原时间等计算，并取旧 expires_at 的较早者；
缺原时间立即脱敏，旧 dream.expired=true 不保留正文。KV 容器更新、引用读取、重复 import
均不延长原正文。preview 报告 history_origin_at/history_expires_at；
实际 import 再检查当前时间，跨过期限则根本不 INSERT 正文/原生体验。
库内幂等回执保存 retention_checked_at 与导入 human 水位，不保存正文。
Python 测试端 `import_manifest/verify(..., now=...)` 可注入时间；CLI 始终读取真实当前时间，
不提供操作者倒退保留时钟的选项。

F3 没有改变 schema 2 指纹。映射内容增强后，F3 之前的清单需重新 preview；
旧回执内容不一致仍报冲突，不覆盖或偷偷升级既有行。无 F3 期限的历史档案交核心立即脱敏，
其未确认的约束继续由纯评估器拒绝。

## 字段与持久化

| 来源 | 实际目标与语义 |
| --- | --- |
| persona_state | 每字段保存在 `states.kind=legacy_import` 的 original/field_map；mood 只可为观察/unknown，energy/busy/agenda 不变 Bot affect |
| 情绪 | 有可靠来源和原 confidence/occurred_at/expires_at 才另写原生 observation；过期仍用原 expires_at，API 已验证不返回过期观察；缺 TTL 不推算新 TTL |
| affinity | original/baseline 保留原 score/stage/manual/source_key；来源账本 `dimension=legacy_score`，不写原生 relationship；trust/familiarity/boundary 未知，不参与自动聚合 |
| night.state | 明确 context 且 awake/asleep、睡眠起止完整时写原生 night；使用旧 last_tick/energy/sleep_at/wake_at，旧爬楼/待发动作只留历史；waking 不擅自续期 |
| proactive.sessions/global | baseline 映射 cooldown_until/last_attempt_at/unanswered_count/quota_period/quota_used；保留原绝对冷却及日期，不猜时区、不将全局和场景计数重复计费 |
| mem_diary | 未过期时写私人档案与 DIARY；原时间起算最长七天，原 pinned 仅留档，不豁免期限 |
| night.dreams | 始终 DREAM/imagined；明确原 expires_at 且未标 expired 才写原生体验；只有旧衰减参数、已过期或缺期限时仅私人历史，不让置顶复活旧梦 |
| proactive_log/night_dream_plan/proactive.state | `task_history_never_resume`；不写 intents，不恢复生成、外发或旧发送路由 |

所有选择均保存 `states(kind=legacy_import,record_key=<稳定来源行键>)`：
`original`、`baseline`、`classification`、`field_map`、`private=true`、
`exportable=false`、`history_only=true`、来源哈希、原主键与目标上下文。
原生体验 EvidenceRef 为 `provider=congling.snapshot`、`kind=legacy_unknown`、
subject/holder 未知、sensitive=true、exportable=false、无授权，`source_ids` 保留原引用。
未过期档案保留原始 refs（含对象）、分类和隐藏标记；脱敏时仅保留安全标量，
引用另提取为 source_refs ID，不把任意引用对象序列化进 EvidenceRef.source_ids 来夹带正文。
核心后续 cleanup 可以删除整个 original；非正文 baseline/source_refs/来源回执仍保存。
原生体验与档案正文的期限一致；不会因有引用或原 pinned 而延长。
普通分享/记忆检索不得将这些迁移引用升级成已授权材料。

精确兼容边界：

| 项 | 当前值/行为 |
| --- | --- |
| 目标版本 | `PRAGMA user_version=2` |
| schema 指纹 | `6a884b7faa9b138fce265e4dbcb18c109ded743e73a8bc97bb65003eb04b1ab6` |
| 指纹算法 | `stable_key` 包装非内部 sqlite_master 的 type/name/tbl_name/sql，按 type/name 排序 |
| 兼容变化 | 增列、表、索引、触发器或版本变化全部拒绝，包括同版本变化；不会动态信任导入时的新 schema.py |
| 写入表 | scopes、states、relationship_ledger、experiences、runtime_meta；只显式列 INSERT，不执行 DDL、不调用私有 store |
| 持久幂等 | runtime_meta 的 `legacy_import:entry:<identity>` 保存 digest/source_hash/manifest_hash/目标定位 |
| 唯一键 | 来源安装 ID+表+原主键+KV member；同键改内容/改映射为冲突，不用正文/秒时间代替身份 |
| 清单 | 路径、源 SHA-256、schema、实例、选择、逐项映射摘要共同纳入 manifest_hash；导入重算，不信任清单提供的 SQL |
| 已有记录 | 不覆盖、不 merge、不提高版本；同批多个状态目标、原生体验 owner/kind/period 冲突整批失败 |
| 清除/运行后 | 同代际重导零新增、不覆盖新状态；verify 报告变更。代际改变拒绝旧清单，不复活已清状态 |

正常期限清理不是对账损坏：verify 接受已到期体验缺失、到期 original/pending_crawl 脱敏
及相应版本递增；其他值或夜状态漂移仍报告 mismatch。重复导入只检查既有回执，
不会重新水化已清正文，也不会重置导入时的 human 水位。

这些哈希用于检测误改，不是签名授权；有本机文件写权限的恶意操作者不在此信任边界内。
整数计数不直接导入运行配额，标识使用 SHA-256，不消费新发送意图计数。
离线操作者需对快照只读、目标读写、报告目录创建权限；本机权限不是宿主管理认证。
查询只针对白名单表/原主键，选中行按 LIMIT 2 确认唯一；未建合适旧索引时可能扫描，
因此大库有硬文件上限但不承诺运行耗时。没有后台自动批处理或无限重试。

## 核心剩余接点

精确协议见本文开头，核心读取/清理已在并行实施，本代理不修改其文件。
独立 components 需验证这些路径，不能仅凭本代理 74 项单元/临时库测试标记 C56 全通过：

1. `behavior_history` 将真实 native 与旧基线加一次，并将拒绝原因/绝对冷却传到
   BehaviorService 评估、模型前与最终 authorize；移除虚构大计数及 now 冷却兜底。
2. 原生配置开启 autonomy/dream/export 后，未知范围/时区/梦夜周期仍拒绝；
   不依赖 Application 前置检查，也不能在最后 authorize 绕过。
3. core cleanup、load/query/pin 对迁移体验使用同一硬期限，立即清无期限旧档案；
   只删正文，不删旧约束或幂等回执。迁移专项已实测当前 core 的 cleanup/load，
   但不冒充私人管理页与后台调度清理均通过。
4. 关系 baseline 不可分解，不进入跨账号投影；历史列表、审计和显式清除管理
   仍经宿主认证，F3 未新增页面或修改关系所有权。

不等待核心持续运行，不执行生产迁移。本文为共享交接，父代理已代转核心读取。

## 回退演练

`consumers.json` 明确记录选择，不猜当前生产配置：

```json
{
  "format": 1,
  "consumers": {
    "BiliBot": {"current": "livingemotion", "restore": "congling"},
    "LivingHello": {"current": "livingemotion", "restore": "none"}
  }
}
```

`rollback-plan` 只读目标并生成有 plan_hash 的顺序计划，不停启真实进程、不修改配置：
先停新执行者和消费者，确认生成/发送/导出/注入任务已退出；保留新库及独立一致备份；
再恢复记录中的选择，检查唯一所有者后重启旧消费者；新记录继续只读保留。
禁止旧备份覆盖新库，禁止将不兼容新记录有损回写旧从绫，禁止恢复旧 pending 队列。
演练用临时库新增真实本地 event/body 后，模拟消费者选择恢复，并核对新库 SHA-256
和新增正文不变。它是合成控制模拟，不是生产停机/恢复实测。

## 验证结果

环境：macOS 15.6.1 arm64，Python 3.11.9，SQLite 3.45.1，pytest 8.4.2。
执行目录为插件根目录，只使用 pytest 临时目录、合成旧表和临时目标库；
目标初始化、API TTL、清除及回退新记录使用公开 SQLiteStore 方法，没有私有字段穿透。

```bash
.venv/bin/python -m pytest tests/migration -q --tb=short -o faulthandler_timeout=15
.venv/bin/python -m pytest tests/migration tests/storage tests/contracts \
  -q --tb=short -o faulthandler_timeout=15
/tmp/livingemotion-adapters-venv/bin/ruff check \
  storage/legacy_import.py runtime/legacy.py tools/migrate_legacy.py tests/migration
.venv/bin/python -m compileall -q \
  storage/legacy_import.py runtime/legacy.py tools/migrate_legacy.py tests/migration
```

本轮最终命令结果见下表；联合数量包含既有存储/契约测试，不重复计为本任务新增。

| 检查 | 实测 |
| --- | --- |
| F3 最终迁移专项 | 74 passed，2.31s；原 46 项保留 + 新增 28 项；1 个 pytest 配置 warning |
| T10 历史迁移专项 | 46 passed，1.67s（前代理当轮结果） |
| T10 历史迁移 + 存储 + 契约 | 88 passed，1.89s（前代理当轮结果，F3 未重跑联合） |
| Ruff | All checks passed |
| compileall | 退出码 0 |

warning 是现有环境缺 pytest-timeout 对当前 `timeout` 配置的识别；未修改配置或依赖。
F3 新增 28 项覆盖真实临时库导入/重开/受限读取，旧计数去重及跨场景隔离，
原冷却边界、原时区跨日、导入前 human 与之后 bot 不解除未回复、新 human 解除，
夜周期拒绝、同 owner 换场景不能绕过梦/导出、多来源冲突、坏类型/超限拒绝，
八天旧正文导入即不保存、preview/import 跨过到期点、换来源 ID 不延长原正文，
清理保留来源 ID/约束/回执、重导不恢复正文、原生迁移体验置顶仍失效。
本轮中间检查只有三处 TypeError 风格与一处 import 排序 lint 问题，均已修复后通过；
未修改独立验证断言或原 46 项迁移测试。

测试覆盖四子命令真实子进程、12 旧记录首次导入、重复 0 新增、逐字段对账、
WAL backup 与旁文件拒绝、同 inode 拒绝、清单/源变更、实例校验、TTL 不刷新及 API 过期过滤、
unknown 不写 Bot、关系不聚合、私密引用/梦分类、待发只 history、有限窗口/事实向量拒绝、
独占锁、同版本 schema 变动拒绝、部分 INSERT 后异常回滚、子进程 os._exit(73) 崩溃恢复、
新状态不覆盖、清除不复活、回退保留新 event/body 和消费者模拟恢复。

中间失败已修复：测试初次错误引用 PluginConfig；随后 25 failed/21 passed
定位为真实 register_context 可先于 scopes 创建，离线查询改为 LEFT JOIN/default generation 0
并核对 context_id/scope_key，复测通过。不是放宽目标实例或来源检查。

没有真实模型、外发、生产迁移、生产停启、真实消费者配置切换或宿主/前端验证。
未运行 1 万事件性能压测，未声称大库在线可用。父代理维护规格勾选与独立验收。
