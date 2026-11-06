# T11 最终验收汇总：组件部分

## 最终组件结论：实跑完成，已释放

**V06 4/4、完整migration 84/84、普通full 1273/1273 PASS，产品失败0。
38项组件矩阵：29项PASS、9项限制、0项FAIL；额外C08 PASS，不计入38项。
这是组件范围结论，不是全部宿主、真实外部服务或T11/T12总验收通过。**
普通full只跑一次，0 failed/error/skip/deselected，23条JUnit格式warning；
51个产品文件跨三轮、各轮前后及收尾复核一致。唯一全清单异常是未收集的
`tests/host/final_provenance.py` 在full期间新增，详见下方，原记录未改写。
所有本验证者启动的测试与扫描均已结束，无服务或等待进程，无真实模型/平台发送。
父最新交接：宿主single222/four230/conflict245、browser44/28布局全部通过并释放，
输入hash一致至2026-11-05 23:55:49 UTC。这里只引用父报告，不冒充本验证者执行。
父已启动README/metadata/gitignore及7篇docs收尾；本轮节点与hash结论绑定既有执行窗口，
不把后续交付文档变化归为产品失败，也不声称后续候选仍与原121项清单完全一致。
最终候选来源及隐私交T12，本轮不再新增扫描、测试或重复full；下方原历史不作当前状态。

本轮接替者按父明确授权实际验收，没有等待或轮询父消息。父确认所有产品冻结：
core 22:18:24、storage/api/projector 22:35:47、domain/emotion 22:41:45 UTC；
原 C51 `local-state-final-20261105-03` PASS（p95=48.801416ms）、
`window-final-20261105-03` 11/11 PASS，4898项前后hash相同，
测试CPU于22:46:57 UTC释放。另一独立宿主在不同目录验收，不混用其结果。

- [x] 读取 SEM `testing-and-quality-gates`、准备矩阵与最新核心/领域/性能/预算交接。
- [x] 原 V06 四proven、完整migration、一次普通full串行实跑，新label且保留旧证据。
- [x] 核对逐节点结果、38项矩阵及额外C08、前后产品hash。
- [x] 新候选有限来源扫描；分列宿主、外部能力、C50/C51边界；交接释放。

沿用现成普通 `.venv-ci`，清空 `PYTHONPATH/PYTHONHOME/PYTEST_ADDOPTS`，
禁user site和字节码写入；原runner禁pytest缓存。只用合成材料、临时SQLite、
模型/发送桩，不安装或借宿主依赖。本轮没有产品失败或验证器错误，未改runner、
原测试语义或其他测试；写入仅为自有evidence与两份组件文档，父spec及Git不动。

### 实际执行与收集

以下均为实际执行，不是collect-only；三个label执行前不存在，由原runner拒绝覆盖。
wall取原JSON `duration_seconds`，含pytest子进程初始化/退出，保留六位小数；
pytest时间取原日志。各行XML和JSON均逐节点通过，重复节点0；不能将重叠套件相加。

| label | 开始UTC（2026-11-05） | collected / executed | deselected / skipped | passed / failed / error | pytest s | wall s | exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `t11-v06-finalexec-ci-20261105-01` | 23:31:31.170791 | 84 / 4 | 80 / 0 | 4 / 0 / 0 | 1.56 | 3.199536 | 0 |
| `t11-migration-finalexec-ci-20261105-01` | 23:46:55.897514 | 84 / 84 | 0 / 0 | 84 / 0 / 0 | 5.33 | 5.957449 | 0 |
| `t11-full-finalexec-ci-20261105-01` | 23:47:32.790858 | 1273 / 1273 | 0 / 0 | 1273 / 0 / 0 | 17.64 | 18.319883 | 0 |

证据：`tests/verification/evidence/<label>.json/.log/.xml`。
JSON的 `junit.cases` 保存每个classname/name/outcome，日志保存完整pytest nodeid，
XML保存各节点时间与测量属性。三个 `collect_only/timed_out` 均false。
23条warning均为 `record_property` 与默认xunit2格式的兼容提醒，
不是测试失败或丢失属性；本轮已从原XML实际解析V04/C08测量，不改格式隐藏warning。

普通full的实际分层计数如下，全部PASS、0 skip；是目录计数，不冒称互斥测试层级：

| 目录 | 执行数 | 关键集合 |
| --- | ---: | --- |
| domain | 601 | 新数值563 + 原emotion35 + persistence3，未漏旧38项 |
| contracts | 17 | 原契约边界 |
| identity | 98 | identity/persona/relationship/projection access/read |
| memory | 49 | 公开协议、来源、缓存与失效 |
| night | 88 | 领域、回执、重开、catchup |
| behavior | 52 | 策略、路由、确认、unknown及取消 |
| experience | 91 | 日记、梦、分享、置顶与导出协议 |
| storage | 55 | 原F6 18 + sqlite25 + sustained普通12 |
| runtime | 22 | background14 + caller cancellation8 |
| integration | 36 | Application24 + 新main入口7 + Projector5 |
| migration | 74 | constraints28 + import46 |
| budgets | 39 | runtime15 + window11 + runner13，无Provider |
| performance | 2 | 计量单测，不启动benchmark |
| verification | 49 | 跨模块31 + CLI10 + 工具自检8 |

`full=["tests"]` 保持原配置，不另加筛选或覆盖addopts。F6显式文件名规则仍生效。
`tests/host`、console宿主文件、Provider payload文件属于原配置独立层，
没有被算成skip或PASS；本轮未运行浏览器、宿主、Provider、增长诊断或完整benchmark。
环境实测CPython3.12.16、pytest8.4.2、pytest-asyncio1.4.1.post1、
pytest-timeout2.4.0；三个进程的astrbot/httpx/openai均不可导入，
PYTHONPATH/PYTHONHOME为空、PYTHONNOUSERSITE=1，没有安装依赖或读取生产材料。

实际命令，cwd为插件根；full终端输出通过 `tail -n 45` 限长并用pipefail保留退出码，
原runner写入的日志完整，测试参数未受影响：

```bash
env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py migration \
  --match 'test_imported_behavior_restriction_blocks_after_restart and proven' \
  --label t11-v06-finalexec-ci-20261105-01
env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py migration \
  --label t11-migration-finalexec-ci-20261105-01
/bin/bash -o pipefail -c 'env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-ci/bin/python tests/verification/run_checks.py full --label t11-full-finalexec-ci-20261105-01 | tail -n 45'
```

### 关键节点结果

P=`tests/verification/test_cross_module.py`，M=`tests/verification/test_migration_cli.py`。
以下每个节点在最终full均实际PASS，不拿作者自测替代；M另在完整migration通过。

| 检查 | 原节点或参数 | 实测结果与边界 |
| --- | --- | --- |
| V06/F12 cooldown | M `test_imported_behavior_restriction_blocks_after_restart[proven-cooldown]` | 计数0/0/0、last_attempt_at=None；恰好800秒后恢复，模型/发送桩各1次 |
| V06/F12 scope | 同节点 `[proven-scope_quota]` | 计数2/2/0、last_attempt_at=None；次日恢复，模型/发送桩各1次 |
| V06/F12 global | 同节点 `[proven-global_quota]` | 计数6/0/0、last_attempt_at=None；次日恢复，模型/发送桩各1次 |
| V06/F12 unanswered | 同节点 `[proven-unanswered]` | 计数0/0/2、last_attempt_at=None；新人类事件恢复，模型/发送桩各1次 |
| 未证明限制 | 同节点四个 `unresolved-*` | 次日仍拒绝，模型/发送桩0；所有8例真实CLI重复导入新增0、只读源hash不变 |
| V04/C15 | P `test_application_bound_relationship_read_reprojects_retained_ledger` | XML：local=[0.5,0.5]，bound=1.0，unbound=0.5；31天events=0、ledger_unchanged=true、send_stub_calls=0 |
| V05/C16 | P `test_identity_grant_does_not_turn_private_account_binding_into_scene_access[target_change0/1/2]` | 群、公开评论、另一实例三例各PASS，grant均为空；未发生真实数据泄露或外发 |
| F5/C09 | P `test_api_read_applies_elapsed_recovery_without_new_events`、`test_application_behavior_snapshot_uses_same_readonly_recovery_as_api` | 无新事件推进24小时，stress低于原值1/100；API/行为一致，持久状态不写回 |
| C18/F7 | P `test_live_mode_switch_keeps_core_states_and_sleep[none/local_lite/external]` | 三例均执行到切换后断言并PASS；不再停在首次关系读取 |
| F6/C49 | `tests/storage/performance_f6.py` 全部18节点 | 200热点全成功、双门面/异账号、clear活动与排队、取消/锁交接、异场景、CAS、trace原子性、tuple、3组seq空洞、查询计划与冷场景全部PASS |
| 数值快路 | `tests/domain/test_numeric_fast_path.py` 全部563节点 | 精确float兼容、子类/异常、IEEE754样本、完整192行逐值guard均PASS；原domain38项也实际执行 |
| 新core入口 | `tests/integration/test_main.py` 全部7节点 | 读失败正常聊天而停自主、admin四参数True/False/字符串true/整数1、注册叫醒、取消传播全部PASS |
| C30 typed | `tests/night/test_night.py::ReceiptTests` 全部12节点；integration收尾节点 | 匹配typed成功才入睡；非成功/异范围/错ID不收尾，重复不重置，截止时限拒绝；不等于原生平台成功 |
| C30 降级 | `test_console_reports_native_reply_confirmation_unsupported`、`test_settling_timeout_cancels_instead_of_sleeping` | 组件unsupported展示与120秒取消PASS；真实宿主afterhook/bool/None、HTTP/页面及不重发由另一验收者负责 |

额外C08：P `test_application_interaction_trace_expression_behavior_and_mode_controls`
**PASS**。XML实际测量stress `0.0 -> 0.10501750000000001`，
行为score `0.238375 -> 0.232124`；expression当前状态与trace事件对应均true。
observe_only仍记录但不注入/不自主，禁用后workers=0、调度器停止，
provider_lookups=0、send_stub_calls=0。真实Application/API/Projector/SQLite闭环，
输入与宿主表面为合成桩；不计入38行，也不替代宿主pipeline验收。

### 冻结与漂移

三个原JSON各有121个受检文件hash，三个执行前清单彼此相同。
V06和migration的 `changed_during_run=[]`。full唯一变化路径为
`tests/host/final_provenance.py`，属于明确排除的宿主辅助文件，不是产品或普通收集节点。
精确分列：三轮before均不存在该键；full运行后原runner将其列入变化集合；
收尾全键集合核对为121→122，仅新增此文件，removed=[]、modified=[]。
该文件收尾SHA256为
`884deab3108070f57885e76cde934dacbb76fd7a0d8fa77b69f1fb51d4ac57c3`；
原runner没有保存完整after表，因此此值标为收尾值，不冒充结束瞬间摘要。
早期收尾摘要只比较既有键，误写为瞬态变化后恢复；本次已用键集合差分纠正，
未修改原runner、原证据或测试语义。宿主报告也说明它只记录输入哈希。
不撤销其他验收者工作，不声称full全清单完全稳定；这不是产品反例，
原121项与全部51产品文件稳定，未因此扩大重跑。

产品集合为原hash表中的domain/storage/adapters/services/runtime/ports/tools/page_api/pages
及根入口、contracts/config/schema，共51文件。各轮变更集合均不含它们，
三轮执行前及收尾逐路径比对全相同。原runner只保存before和变化列表，
不冒称它保存了完整after表；前=后判断来自原比较，收尾另做第三次读取核对。
这不以瞬时hash替代父授权。全部51项摘要可在任一原JSON的 `source_sha256` 查到。
将该51项字典按sort_keys、紧凑分隔符、ensure_ascii序列化后的SHA256为
`72628876ffdd9e8eb09efe948b720f51313c6cc474292148b0558454456da392`。

| 关键冻结路径 | 本轮前=后SHA256 |
| --- | --- |
| main.py | `62783b1c1a4a24231bb839e56e74c8ecfe4f40949b2e2b0ef96557633f9e0e87` |
| runtime/application.py | `79b30e76cfaaf899e1d3297b0822d18f496a60aa4786e791e94f0709e95adc99` |
| runtime/console.py | `219d8239453e2bf0257380c72c3eba4a488e352927cea29b2823f0708b91f833` |
| services/behavior.py | `000308b54bf601e2ede77ead39f44643e715fb0d037bfa0bf4456dbb115b479e` |
| api.py | `a88ef0fe7af62428710c4cd7a8f587e070e6b6ad2a6660348d7238986c11e9c9` |
| runtime/projector.py | `cb1051be1814573a1b24f95cf1f5511aa2c48cf82adf0eaadbfd400045a24c79` |
| storage/sqlite.py | `599cec9c29caa8c69f84bb27ed88c027a7fdf548ea11442153021d49199eb116` |
| domain/emotion.py | `f79c1ef6dac5a50d4fdaf72ba8d00e40156abbe070007a91c80e4ad8d6876fc0` |
| tests/domain/test_numeric_fast_path.py | `8cdf21b866562708dd7178c16fa00da7565c4fb429d3f3736e525231399e7b56` |
| tests/storage/performance_f6.py | `33452716af3cfc409ebfefab715a27fd8aaf326d99b1ff3b6cf5c6bb80e769ba` |
| tests/integration/test_main.py | `6df28501a959a8f6154ad5d093bb9c1fa1ac8f86011c5df0e53d92d371b2f474` |
| tests/verification/run_checks.py | `f74acac4ea5c42f85e826db6ee85694ab9802e710f438081d85c4b3560407725` |

普通测试、runner、配置的hash均未变，未修验证器或降低任何断言。
full与原C51 final-03共有11个产品文件、与window-03共有37个产品文件，
逐项hash一致，允许关联本轮迁移TTL与该冻结版容量证据。

### 最终38项证据表

PASS仅指本行具名组件风险，不替代“仍需父核”列。限制表示组件协议/拒绝路径已通过，
但完整C项包含本轮不能证明的来源、真实宿主或外部能力；父不能据此勾完整成功能力。
本表是当前唯一状态索引，下方旧38项矩阵及失败保留为历史。
除P/M外，下列目录/文件均相对 `tests/`；所有列举节点在full原日志可定位。

| C | 最终状态 | 本轮实际证据 | 仍需父核 / 限制 |
| --- | --- | --- | --- |
| C02 | 限制（有限检查PASS） | P `test_domain_ast_has_no_host_private_plugin_or_sql_access`；新候选176/13精确重合0 | 不是版权授权、全历史或最终Git清单证明 |
| C07 | PASS | domain `test_sadness_is_observed_not_copied_to_bot`；integration `test_default_chat_without_model_and_unique_suffix` | 分型及默认聊天为合成入口 |
| C09 | PASS | P两项F5当前时间恢复及 `test_expired_and_out_of_order_observation_does_not_rejuvenate` | 无新事件/不写回，不刷新TTL |
| C10 | PASS | domain601/601含新563；`test_invalid_numbers_rejected`、`test_invalid_models_all_fall_back_to_rules` | 模型解析为桩，无真实模型 |
| C11 | PASS | P `test_actual_projector_duplicate_race_applies_all_state_once`；domain刺激预算、storage冷场景 | 20并发1 accepted/19 duplicate，不代C51 |
| C12 | PASS | identity/relationships32/32；`test_positive_and_negative_changes_never_refund_daily_budget` | 绝对日预算与无记忆熟悉度，不依赖外部事实 |
| C13 | PASS | integration `test_management_correction_ledger_audit_and_stale_generation`；migration不造信任 | 管理主体为合成认证入口 |
| C14 | 限制（组件PASS） | identity98/98含同值别名、未绑定隔离、坏提供者 | 真实跨平台OneID绑定/解绑未由本轮执行 |
| C15 | PASS | P V04真实Application：31天events=0、ledger不变、0.5→1→0.5 | 合成身份提供者；旧V04 FAIL保留 |
| C16 | PASS | P V05三越界各PASS及八维状态/材料隔离 | 不声称历史已发生真实泄露；旧FAIL保留 |
| C17 | PASS | P在途identity；memory解绑召回失效；behavior整份生成废弃 | 真实身份服务另核 |
| C18 | PASS | P `test_live_mode_switch_keeps_core_states_and_sleep` 三模式各PASS | external缺后端保守降级；最终宿主另验 |
| C19 | 限制（组件PASS） | memory `test_external_read_write_independence_and_background_degradation`、读开关失效 | LM真实后台检索/导出unsupported，不宣称后端成功生命周期 |
| C20 | 限制（协议PASS） | memory `test_external_real_public_contract_and_final_validation`；identity不造假event | 协议桩成功不证明LM有合格后台来源门面 |
| C21 | 限制（协议PASS） | memory provenance、single-flight、解绑与最终验证失效节点 | 无LM真实后台材料/最终授权凭据正例 |
| C22 | PASS（离线聚合） | M8天正文TTL；full window11/11；独立window-03 11/11和C51默认满容量 | 合并依据见下；不含生产数据或未声明的存量正文重截断保证 |
| C23 | PASS | P `test_experience_none_memory_real_loader_and_pin_survive_restart`；experience无依据跳过 | 模型桩、真实临时SQL材料与重开 |
| C24 | PASS | experience视角/原来源/容错JSON节点，目录91/91 | 不保证任意损坏文本恢复 |
| C25 | PASS | experience REM、衰减、置顶/解绑、想象来源；迁移原期限 | 引用和置顶不延长原正文TTL |
| C26 | PASS | experience `test_mixed_private_diary_share_regenerates_only_authorized_material`、最终整份丢弃 | 无真实群发送 |
| C27 | 限制（协议PASS） | experience `test_livingmemory_export_explicitly_unsupported`、幂等/部分重试/防反馈 | LM后台幂等导出unsupported，不宣称真实写入成功 |
| C28 | PASS | night五阶段、时间推进与独立性，目录88/88 | 夜间领域是唯一精力写者 |
| C29 | PASS | night跨午夜/回退/重开；experience离线REM不补发 | 固定时钟、临时库 |
| C30 | 限制（组件PASS） | ReceiptTests12/12、Application typed端口/unsupported展示、120秒取消 | typed成功与无可靠原生回执分列；最终宿主不重发另验 |
| C32 | PASS | night/catchup高水位、来源与水位原子提交、摘要过期 | 合成材料，不读真实聊天 |
| C33 | PASS | behavior默认关闭/群独立开关/只读preview；experience默认无模型 | 无真实费用或外发 |
| C34 | PASS | behavior硬否决/发送前最终复核；M proven/unresolved八例 | 已补V06迁移硬闸，非仅原生策略PASS |
| C35 | 限制（组件PASS） | identity不猜route；behavior缺失/伪造route拒绝 | 无真实平台投递成功证明 |
| C36 | PASS | P在途human取消；behavior Bot/tool回执不自取消 | 合成人类时间线 |
| C37 | PASS | P `test_unknown_real_history_survives_reopen_retention_and_clear`；崩溃/unknown不重试 | 真SQL/运输桩，非远端处理结果证明 |
| C38 | PASS | behavior确认成功/partial/unknown/事件落库失败节点 | 运输桩，不冒称平台成功 |
| C49 | PASS | 原F6 18/18；P六表事务回滚、20并发、在途clear | 普通一致性回归，不等同断电实验 |
| C53 | PASS | P `test_correlation_records_and_health_exclude_private_body_and_exception` | 事件/请求/意图关联和正文隐私；真实宿主日志另验 |
| C54 | PASS | migration只读快照/WAL拒绝/同文件拒绝；M真实CLI源hash不变 | 临时库，不证明生产停机 |
| C55 | PASS | migration字段分型/原TTL/实际实例/坏来源拒绝 | 不造Bot状态或新关系维度 |
| C56 | PASS | M四proven恢复及四unresolved持续拒绝；原74迁移全部PASS | V01/V06旧失败保留，不再虚构计数/原生尝试 |
| C57 | PASS | migration事务中失败、硬退出、重复零新增；M CLI二次导入0 | 临时库原子/幂等证据 |
| C58 | 限制（CLI PASS） | M `test_cli_rollback_preserves_new_event_and_requires_stopped_target` | CLI计划/停机拒绝/新事件保留；宿主实际停用/消费者回退由另一人验 |

### 专项合并与来源边界

**C22离线聚合完成。** 本轮M的8天cleanup后窗口为空且legacy_import正文副本0，
迁移74项原时间/引用/置顶约束通过；最终full同时通过window11项。
独立 `window-final-20261105-03` 11/11提供静默scope物理 `[2,2,2]`、
小容量16次投影后全库5/scope `[3,2]`、发生时间TTL物理2→1、
置顶来源正文0/引用保留、全库与TTL调小、正文长度/硬上限证据。
原C51 final-03提供默认满10000/每scope200/正文2560000字符及WAL/FULL(2)证据。
共有产品hash核对一致；不再拿旧TTL快照拼接新存储。存量正文在调小
body_max_chars后是否重截断不在上述既有断言内，未扩大成新保证。

C51只引用已完成的原10000主样本：10000 accepted、0 rejected/duplicate，
p50/p95/p99=38.960583/48.801416/52.982417ms，原50ms门槛PASS，
主提交wall=21.308206s/CPU=18.665252s。2.40%余量不等于稳定充足余量；
本轮未执行benchmark或增长诊断。旧56.895041ms/139.081ms等FAIL保留。

C50/F8引用 `verification-budgets-final.md` 的独立31/31、53/53，不重复Provider16。
本轮full新执行portable runtime15、caller取消8和background14；没有真实Provider。
与F8证据比较，background/models摘要仍一致，但api/domain emotion/console/projector/sqlite
五路径已不同，不能把53/53冒充本轮完整冻结快照的新执行结果。
取消只证明本地协作式传播，已派发quota不退，不保证远端未处理/未计费。

有限来源扫描实际命令：

```bash
env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/check_source_overlap.py \
  --candidate --reference ../astrbot_plugin_congling --label t11-source-finalexec-20261105-01
```

原JSON记录UTC为2026-11-05 23:51:53.669561，exit0；176候选/13参考、
746个不少于10行Python函数体、77个至少120字符字面量及整文件精确重合均0。
`changed_during_scan=[]`、`inventory_changed_during_scan=false`；
原证据及manifest在 `tests/verification/evidence/t11-source-finalexec-20261105-01.*`。
manifest SHA256=`170bc70643b8961b7a0a345ba6cb7603f43a2a7f61da8f761eb5471b4e53ec6c`。
这是扫描时候选快照：包括报告，本次回填与其他验收者后续报告编辑会改变文档摘要，
不据此认定产品漂移，不将它冒充最终不可变包或Git暂存清单。非Python只比整文件；
不覆盖改写/相似复制/全上游历史，不是版权证明，不输出参考原文或秘密。

### 交接门禁

主专项 `testing-and-quality-gates`，高置信度；目标为38项关键风险均有可定位证据或
明确限制，不用行覆盖率替代行为验收。没有重组测试或以成本删除检查。
普通组件/本地契约阻断失败；完整性能与宿主为独立发布前门禁；生产探针未运行。
原runner 240秒、pytest每例60秒，普通full实测wall18.319883秒；
无远端CI历史，不能宣称CI p95。超时/收集缺口/skip/产品漂移均需留证交父，
不自动重跑到绿；任何复跑结果不一致按flake阻断，24小时内交父分配处理，
本轮单次full不能估计长期flake率。原cacheprovider关闭，唯一label拒覆盖，
不会以旧缓存满足新源码。静态检查仅本轮领域依赖AST和有限来源扫描，
不冒称新lint/安全审计/依赖扫描或远端CI通过。

本轮未发现需交父修复的产品最小反例；旧80pass/4fail、668collection、
V01-V06及历次失败原记录全部保留。原evidence继续受现有ignore规则保护，
不发布原JSON/日志/XML，不写个人路径或凭据进报告，没有Git操作或父清单勾选。
父可按上表合并组件证据，再结合另一独立者最终宿主结果处理限制项。
本验证者工作完成并释放，无遗留服务、测试、发送或轮询。

## 历史准备与阶段证据（原文保留）

状态：**草稿，阻塞中，不是总验收 PASS**。独立验证者未参与产品实现。
父级清单为 `.trae/specs/extract-livingemotion-plugin/checklist.md`；本文不修改父清单。
GitHub、提交及远端 CI 属于 T12，本轮未执行。日期标识沿用任务日 2026-11-05；
实际运行时间以证据 JSON 的 UTC 时间为准。

## 给父任务：静态准备完成，等待明确开跑

本次接替验证者未参与产品实现；已加载 `testing-and-quality-gates`，
读取父 checklist/tasks、本文38项矩阵、`INTEGRATION.md`、
`verification-budgets-final.md` 与 `verification-performance-final.md`。
**本次仅静态准备，测试执行数为0；没有启动 pytest（含 collect-only）、基准、
宿主、浏览器或模型/平台发送。没有可用代理消息接口，以本节通知父任务。**

核心已于 **2026-11-05 22:18:24 UTC** 冻结；按本次父交接，
第三轮 F6 的 storage/api/projector 仍由 `emotion_latency_last_mile` 独占 CPU，
随后父安排原10000样本 benchmark 独占。上一轮性能报告的释放/冻结声明
只适用于上一轮，不能授权本次组件执行。
**启动条件：父明确通知第三轮性能已 freeze、原完整 benchmark 已结束，
并允许本验证者开跑。三者未齐不执行任何测试，不凭 hash 不变自行启动，
也不轮询进程、冻结文档或源码。**

静态准备结果，不是新 PASS：

| 门禁 | 已核对的原入口/断言 | 获准后的检查与失败响应 |
| --- | --- | --- |
| V06/F12 | M 的4个 proven 参数；真实计数、`last_attempt_at=None`、800秒/次日/新人类消息恢复、模型和发送桩各1次 | 先原4例，再完整 migration；产品反例原样交父，不修产品或降断言 |
| C22/C54-C58 | M 的8天正文清理、真实CLI、重开、重复导入0新增、只读源哈希、回退保留；`tests/migration` 未缩集合 | 新标签迁移结果及前后源码一致性交父与独立 window 验证者；不能用旧TTL结果放行新存储 |
| V04/C15 | P 的真实 Application、31天 events=0、ledger不变、各0.5绑定为1再解绑为0.5 | 必须在 full 实际执行，不能用纯服务或实现者自测代替 |
| V05/F5 | P 的群/公开评论/其他实例3例；API及行为24小时恢复、不写回原状态 | 全部逐例核对，失败保留原始结果并交所属者 |
| F6/C49 | 原 `tests/storage/performance_f6.py` 及配置中的显式文件名规则 | full中原18例全部实际执行；新 `test_sustained_latency.py` 普通用例随原full收集，不运行其显式诊断入口，不代C51 |
| 入口/取消/C08 | `tests/integration/test_main.py` 故障降级、4个admin参数、叫醒、取消传播；P 的事件/trace/表达/行为评分/observe_only/禁用闭环 | 核对逐例结果及C08测量属性；C08额外列出，不计入38行 |
| C30 | typed成功/非成功/异范围/截止时限；integration确认能力unsupported展示 | 组件成功端口与宿主无可靠回执、120秒取消且不重发分列；最终宿主三场景由另一验证者执行 |
| 环境/证据 | 原runner的 `full=["tests"]`、唯一label、逐例JUnit、禁pytest缓存、源码前后比较 | 普通环境不可导入astrbot/httpx/openai；超时/收集错误/skip/源码漂移均不得当PASS，不能借宿主环境补绿 |

现成 `.venv-ci` 的静态目录与metadata显示 Python 3.12.16、
`include-system-site-packages=false`，五项直接开发依赖与声明版本一致，
site-packages无astrbot/httpx/openai条目。本次未运行解释器或导入探针，
这些目录事实不替代获准后runner记录的运行时环境。

获准后仅使用原runner，按下列顺序串行执行；**以下均未执行**。
label为计划值，启动前必须确认尚未存在，碰撞则换新后缀，不覆盖旧证据。
额外清空 `PYTEST_ADDOPTS` 只为避免继承隐藏筛选；保留当前pyproject普通层配置，
不另加ignore、`-k`、`-x`或覆盖配置来缩小full。

```bash
env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py migration \
  --match 'test_imported_behavior_restriction_blocks_after_restart and proven' \
  --label t11-v06-independent3-ci-20261105-01

env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py migration \
  --label t11-migration-independent3-ci-20261105-01

env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py full \
  --label t11-full-independent3-ci-20261105-01
```

原runner保存 `source_sha256` 与前后集合比较 `changed_during_run`；
只有空差异才可将该源码哈希关联到结果，仍不等于收到冻结授权。
每轮记录实际收集/执行/失败/错误/跳过及逐例JUnit，V04/C08属性从原XML读取。
旧80/4、668项collection及历史失败全部保留，668不作为新full的硬编码总数。
本次未改runner、测试、产品、原benchmark或门槛，仅更新两份验证文档；
验证器错误只可在自有目录修正并解释，不反向改产品或他人测试。

C50/F8引用已交付独立31/31与53/53，不重复宿主Provider；C51由独立性能者负责。
LivingMemory后台检索与导出仍为unsupported，不能以协议桩成功宣传真实能力。
38项最终状态及额外C08均待实跑；有新候选来源需求时再用
`check_source_overlap.py --candidate` 和新label，有限169候选/13参考扫描不是版权证明。
原evidence仅本地ignore保留，不删、不发布；报告仅用相对路径、不含凭据。
**静态准备已完成并释放，不启动等待进程；下一动作只由父明确开跑消息触发。**

## 上一阶段交接记录

以下历史记录保留；冻结状态和启动条件以本文顶部为准。
上一阶段父交接：核心接替为 `emotion_finish_core / arun_6aecfb3308a3b52e23bb1346`，
先修 F7/H02/H03，父后追加 F12/V06 行为端口与 F13 宿主确认能力；
性能修复 `arun_6aecfb3308a3b52e23bb1347` 独占
store/api/projector。**最终 full 必须等待两方冻结通知**，不将旧 core 的状态视为冻结。
新 C50 独立者为 `arun_6aecfb3308a3b52e23bb1348`。
本阶段已完成独立可执行项并交接释放；父会在冻结后 follow-up 本验证者，
不持续占位或刷测。

## 检查策略与边界

主专项 `testing-and-quality-gates`，高置信度。按冻结状态分阶段执行：

| 阶段 | 检查与风险 | 失败处理 |
| --- | --- | --- |
| 已执行 | F3 真实 CLI 导入、重开、History、行为闸门、正文 TTL | 保留原断言和新标签，父安排修复 |
| 环境预检 | 普通 `.venv-ci`、交付 requirements-dev、测试实际收集 | 缺依赖/私有宿主路径作为环境阻塞，不 skip |
| 父确认性能冻结、原完整基准结束并明确开跑后 | V06原4例、完整migration、一次普通全套；V04/V05、F5、F6 18项与C08实际执行 | 产品失败交所有者，验证器错误只在独占目录修正 |
| 独立专项 | C22/C50/C51、真实宿主 | 消费专项证据，不重复重基准或运行 tests/host |
| T12 | 远端提交、仓库可见性、GitHub CI | 本文不代验 |

全程只用合成材料、临时 SQLite、模型/发送桩；真实模型及平台发送为零。
测试报告逐次新 label，旧 447 pass、442 pass/1 fail/1 skip 和所有反例均保留。
原始 evidence 仅本地保留、不进入 T12 提交；文档只保留脱敏结果和复跑入口。
不以有限来源扫描证明版权授权，不读取或输出原文秘密。
本轮执行权限以顶部三项启动条件为准。`current_relationship` 已由核心交接说明冻结，
V04仍待独立实跑；不把核心自测通过记成本验证者的新结果。

未改造测试层级或压缩套件。普通组件/契约/本地集成为小中型离线检查，
宿主与完整性能分道且仍为独立门禁。CI job 现配 10 分钟，runner 上限 240 秒；
没有远端历史，不虚称 p95。超时记 124 并保留输出，不自动重跑到绿。
本轮通过目标是 38 个组件检查点逐项有证据或明确边界，不以行覆盖率替代行为证据。
任何重跑不一致均为阻塞，父在 24 小时内分配处理，不自行隔离或降低门槛。

## 当前运行

解释器：插件 `.venv-ci/bin/python`，Python 3.12.16。
该 venv 以已有独立 Python 发行版为 base，但不继承宿主 site-packages；
`PYTHONPATH/PYTHONHOME` 清空、`PYTHONNOUSERSITE=1`。

| label | 实际结果 | 说明 |
| --- | --- | --- |
| `t11-final-f3-ci-20261105-01` | **80 passed / 4 failed / 5.58s**，exit 1 | 84 项收集；源码运行期间未变 |
| `t11-final-ci-environment-20261105-01` | **1 error / 0.08s**，exit 1 | 夹具初始化缺 httpx；源码运行期间未变 |
| `t11-final-tools-ci-20261105-01` | 4 passed / 3 failed / 0.15s，exit 1 | 验证器夹具误拦 platform 子进程，不是产品缺陷 |
| `t11-final-tools-ci-20261105-02` | **7 passed / 0.07s**，exit 0 | 修正验收夹具隔离；原断言保留 |
| `t11-final-collection-ci-20261105-01` | **668 tests collected / 0.42s**，exit 0 | 仅收集，0 error/0 skip；不是 668 passed |
| `t11-final-v05-ci-20261105-01` | **3 passed / 27 deselected / 0.15s**，exit 0 | 原三越界授权反例；源码稳定 |
| `t11-stage-probes-ci-20261105-01` | **26 passed / 3 failed / 1 deselected / 0.80s**，exit 1 | 明确排除未接 V04；三模式首个关系读取仍受 H01/F7 阻塞；源码稳定 |
| `t11-final-tools-ci-20261105-03` | **8 passed / 0.07s**，exit 0 | 加入候选清单/证据白名单自测；源码稳定 |
| `t11-source-candidate-20261105-01` | **169 候选 / 13 参考，精确重合 0**，exit 0 | 728个Python长函数体、77个长字面量；扫描期间内容/清单稳定 |

证据位于 `tests/verification/evidence/<label>.json/.log/.xml`。
完整命令：

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py migration \
  --label t11-final-f3-ci-20261105-01
```

### V06：F3 已证明范围的历史计数与冷却不保真

最小节点：
`tests/verification/test_migration_cli.py::test_imported_behavior_restriction_blocks_after_restart`，
参数 `[proven-cooldown]`、`[proven-scope_quota]`、`[proven-global_quota]`、
`[proven-unanswered]`。夹具通过真实 CLI 指定原范围、UTC、实例/场景额度，
重开目标库后由真实 `BehaviorService` 消费公开 SQL history。

- cooldown：应为 0/0/0 的真实计数变成三个 `2147483647`。
- 其余三项：真实计数检查通过，但没有原生尝试时 `last_attempt_at=1799992799`，
  应为 `None`。测试在这里停止，不能宣称到期/次日/新人类消息恢复已通过。
- 四个 unresolved 参数拒绝通过；正文 TTL 原 V02 通过；迁移原 74 项通过。
- 锚点：`storage/sqlite.py:behavior_history` 的 `legacy.allowed != True` 异常路径
  将拒绝压成虚构大计数和当前时间；正常路径用
  `cooldown_until - behavior_cooldown_seconds` 反推原生尝试时间。
- 必须保留真实计数、原绝对冷却和明确拒绝原因，不能通过虚构计数冻结运行。
  修复由父协调存储/核心/行为所有者，本验证者不改产品和他人测试。
  父已获阶段交接；新 store/api/projector 所有者须核对本文 V06，
  性能修复不能顺带掩盖该历史语义失败。

#### 给核心的精确反例契约

固定 `NOW=1800000000`，时区 `UTC`，原日为该 Unix 秒的 UTC 日期。
每例只选 `proactive.sessions` 与 `proactive.global` 两条 KV：
session 原键为 `old-session`，两条都显式指定当前 `context.account_key`，
`constraint_binding.timezone=UTC`，session `quota_scope=scope`，
global `quota_scope=instance`。先入库一条 `NOW-400` 的合成人类消息；
没有任何原生发送尝试。经 preview/import/import/verify CLI 后重开再测，
重复导入新增数为0、源文件哈希不变是每例共同断言。

下表计数顺序固定为 `global_used / scope_used / unanswered_count`：

| pytest 参数 | 唯一有效旧限制 | 初始 history 期望 | 本轮实际失败 | 解除后必须满足 |
| --- | --- | --- | --- | --- |
| `proven-cooldown` | `last_at=NOW-200`，`next_ok_at=NOW+800`，旧计数全0 | `0/0/0`，`last_attempt_at=None`；原绝对冷却仍有效 | `2147483647/2147483647/2147483647`，在计数断言处失败 | 时钟恰好推进800秒即 eligible，不能重新计算冷却起点 |
| `proven-scope_quota` | session `sent_today=2`，global `sent_today=0`；同原日 | `2/2/0`，`last_attempt_at=None`；不能将global+scope重复相加 | 计数正确，但 `last_attempt_at=1799992799` | 推进86400秒到次日，eligible |
| `proven-global_quota` | global `sent_today=6`，session `sent_today=0`；同原日 | `6/0/0`，`last_attempt_at=None` | 计数正确，但 `last_attempt_at=1799992799` | 推进86400秒到次日，eligible |
| `proven-unanswered` | session `unanswered=2`，发送计数全0 | `0/0/2`，`last_attempt_at=None` | 计数正确，但 `last_attempt_at=1799992799` | 新增当前范围、`occurred_at=NOW` 的人类事件后 eligible；Bot/tool不能冒充回复 |

后三例共同旧 `last_at=NOW-10000`、`next_ok_at=NOW-1`，所以不应带来有效冷却。
所有例初始 `evaluate` 均须不 eligible，`execute` 不调用模型/发送桩；
解除后 `execute` 必须 succeeded，模型与发送桩各恰好1次。
本轮失败发生在解除检查之前，**解除路径尚未通过**。
对应四个 `unresolved-*` 没有绑定证明，次日也必须继续拒绝且模型/发送为0；
它们本轮已通过，不应随修复变宽。V02 8天正文清理也已通过，必须保持。

责任方法及修复边界：

- `storage/sqlite.py:SQLiteStore.behavior_history`：公开历史的真实计数、原生尝试时间；
  原失败快照范围约 `985-1013`，特别是拒绝转大计数分支和绝对冷却反推尝试分支。
- `runtime/legacy.py:evaluate_legacy`：纯评估器已提供 `allowed`、原因、
  `cooldown_until` 和 legacy floors；本轮原74项通过，不应由测试代理改写。
- `services/behavior.py:BehaviorHistory` / `BehaviorService._gates`：
  公开 History 如何表达拒绝与原绝对冷却须由父协调所属者确认，
  同时保留 native 与 legacy 的来源区别。
- `runtime/application.py:behavior_history/legacy_constraints` 是装配点；
  **仅修 Application 不足以修复这个反例**，因为它直接调用真实 Store history
  再构造真实 `BehaviorService`，必须保障公开端口消费者也不绕过约束。

修复后最小独立复跑（尚未执行；必须用未存在的新 label）：

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py migration \
  --match 'test_imported_behavior_restriction_blocks_after_restart and proven' \
  --label t11-v06-recheck-ci-01
```

4项通过后再用新标签跑完整 migration，覆盖 unresolved/TTL/幂等/回滚；
普通 full 仍等待核心和性能两方最终冻结，不能拿最小4项替代。

### E01：普通 CI 环境实跑失败

交付开发依赖实装版本与 `requirements-dev.txt` 五项一致；
普通 venv 中 `astrbot/httpx/openai` 均不可导入。
`tests/budgets/conftest.py` 硬编码加入工作区私有宿主源码路径，
`budget_support.Wire` 使用真实宿主 Provider 和 SDK。该路径不能作为可携 CI 依赖；
普通全套不准借用宿主环境伪造通过。

实跑 `run_checks.py ci-environment --label t11-final-ci-environment-20261105-01`，
现有节点 `tests/budgets/test_model_payload.py::test_real_provider_request_local_wire_payload`
在 `budget_support.py:108` 夹具初始化失败：
`ModuleNotFoundError: No module named 'httpx'`，没有执行模型/发送。
这是环境错误，不是产品断言失败。仅补 httpx 也不能证明宿主依赖可携；
`conftest.py:10` 私有路径、真实 Provider 与 SDK 都需正确分层或声明。
父协调文档 CI 和预算所有者，本验证者不改其依赖或测试。

随后文档代理已将原生 Provider 和 console 文件明确移到单独宿主层，
不安装宿主依赖、不忽略整个 budgets；`pyproject.toml` 保留独立宿主显式命令。
新普通层收集为 668 项，无错误/跳过；以下收集确认以日志为证，
**尚不能取代最终普通环境实际执行，也不能关闭原生 Provider 宿主门禁**。
后续只读确认预算所有者已移除 conftest 的私有宿主路径注入，Wire 改为显式
`--budget-host-source`；此变更不由本验证者实施，最终便携 full 尚待两方冻结。

### 普通层实际收集

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/run_checks.py full --collect-only \
  --label t11-final-collection-ci-20261105-01
```

- `tests/storage/performance_f6.py` 实际收集 **18 项**，原路径/断言不变。
  包括批量快照、200 次热点成功、双门面、同场景异账号、clear 活动/排队、
  取消及锁交接、跨场景不阻塞、CAS 重算、trace 原子性、tuple 兼容、3 个 seq
  空洞参数、裁剪查询计划、冷场景收缩。
- `tests/budgets/test_runtime_budgets.py`、`test_window_budgets.py`、
  `tests/migration`、`tests/verification` 均实际收集。
- `tests/host`、`tests/console/test_console.py`、
  `tests/budgets/test_model_payload.py` 按新配置属于独立宿主层，没有隐式 skip。
- `performance_probe.py`、完整 benchmark、`run_provider_payload.py` 不自动执行。
- `pip check` 实跑为 `No broken requirements found`；只证明已安装依赖一致，
  不证明未声明的宿主依赖可用。

### 验证器变更

独占 runner 新增环境发行包/解释器信息、JUnit 逐例结果、收集标识，
超时保留部分输出并记 exit 124、成功进程无有效 XML 记 exit 125。
7 项验收工具测试通过，加入交付候选清单保护后8项通过；首轮自身夹具错误已保留。
V04 原断言进一步明确为两账号各 0.5，并新增结果属性及发送桩零次断言，
没有扩大容差或替换真实 Application。尚未执行该新版 V04。
来源扫描支持明确交付文件清单、新唯一标签和路径边界；
摘要只输出哈希/行号，不输出原文；父已给出候选范围并完成下节扫描，
最终 Git 清单仍由 T12 另核。

### C02 交付候选有限来源扫描

父明确允许无需 Git 初始化，按当前新插件全部源码/tests/docs及交付配置扫描。
本轮候选清单169个文件，包含声明的3个JSON与8张截图，11项均存在；
排除虚拟环境、CI临时目录、node_modules、缓存、DS_Store、原始evidence、
日志/XML及宿主运行目录。旧 `source-overlap.json` 保持不变。

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  .venv-ci/bin/python tests/verification/check_source_overlap.py \
  --candidate --reference ../astrbot_plugin_congling \
  --label t11-source-candidate-20261105-01
```

本地证据：
`tests/verification/evidence/t11-source-candidate-20261105-01.json`、
`t11-source-candidate-20261105-01.manifest.json`。
扫描器对Python AST中不少于10行的728个函数体、至少120字符的77个字面量做精确摘要比较，
并对全部169个候选文件做整文件字节摘要比较；13个参考路径及哈希均保留。
三类精确重合均0，候选内容与清单在本次扫描期间均未变化。未打印/复制原文秘密。

边界：JS/CSS/HTML/Markdown/图片只做整文件相等检查，不宣称做了函数级或相似度检测；
仅13个选定参考文件，不覆盖全部上游历史、改名/改写复制或其他依赖。
因此 C02 仅为**有限来源/依赖检查 PASS**，不是版权授权证明。
当前还有产品修复及报告更新，不能把该候选哈希称为最终冻结或最终暂存清单。

### 阶段 probes 的 F7 连带失败

父允许阶段 probes 后，显式排除 V04，执行其余 29 项。
`test_live_mode_switch_keeps_core_states_and_sleep[none/local_lite/external]`
三项在 `test_cross_module.py:492` 首次
`(await app.api.get_relationship(context))["data"]` 处失败，尚未进入切换断言。
该轮快照中 API 已调用 `Application.current_relationship`，但 Application 尚无该方法；
与宿主 H01 同一已知接线缺口，不另认定为三种记忆模式实现缺陷。
这轮保留失败，不再于接线完成前重跑上述依赖。F5 两项恢复、V05 三越界、
诊断隐私/事务/在途取消等共 26 项通过；V04 的 1 deselected 不算通过。

## 38 项组件矩阵

“历史 PASS”仅指 `verification-components.md` 已有独立离线证据，不代表当前冻结版
已通过；当前全套尚未运行。P=`tests/verification/test_cross_module.py`，
M=`tests/verification/test_migration_cli.py`。宿主边界项交指定代理，不由组件推定。

### 精确状态索引

- **本阶段已复验完整组件风险 PASS：C09、C16、C17、C53、C54、C55、C57。**
  全部仍需最终冻结 full；不表示相应宿主组合/真实服务或整个 T11 已通过。
- **本阶段限定组件 PASS：C02、C58**。C02为169候选文件的有限来源/领域依赖检查；
  C58为CLI回退计划/拒绝/新记录保留，宿主另有隔离演练，不是生产回退。
  法律来源及完整宿主边界由父结合证据判定。
- **本阶段 FAIL：C18、C56**。C18 是该轮 H01/F7 首次关系读取失败，
  不是已进入切换后的状态丢失；C56 为 V06 四限制语义失败。
- **C15：旧 V04 FAIL，核心已冻结，最终独立复验未执行**；已知未接阶段没有重跑 V04。
- **局部风险已通过但不列全项 PASS：C11、C22、C23、C25、C36、C37、C49**。
  对应并发重复、迁移TTL、有依据日记/置顶、在途新人类取消、
  unknown恢复、事务/清除；其余分支或专项最终证据待补。
- **其余组件点仅历史证据，待冻结 full：C07、C10、C12、C13、C14、C19、C20、
  C21、C24、C26、C27、C28、C29、C30、C32、C33、C34、C35、C38。**
  C30按新R7/F13验证原生确认不可用降级，不要求伪造成功；C34的迁移限制受V06阻塞。

以上 7+2+2+1+7+19=38，互不重复。C08 是额外宿主/纯组件补充，不计入38行。

| C | 当前证据状态 | 最终复验入口/具名风险 | 宿主或专项边界 |
| --- | --- | --- | --- |
| C02 | **有限检查 PASS** | P 领域依赖；169候选/13参考，函数体/长字面量/整文件精确重合0 | 不证明全历史及版权授权；最终Git清单另核 |
| C07 | 历史 PASS，待全套 | domain 悲伤观察；integration 分型默认聊天 | 合成宿主 |
| C09 | F5 阶段 PASS，待冻结 full | P API/行为只读恢复、过期/乱序 | 不刷新版本/TTL |
| C10 | 历史 PASS，待全套 | domain 无效数字/模型/固定时钟序列 | 不调用真实模型 |
| C11 | 历史 PASS，待全套 | P 20 并发重复；domain 刺激预算；storage 冷场景 | 不代 C51 |
| C12 | 历史 PASS，待全套 | relationship 绝对日预算、无记忆熟悉度 | 无外部事实依赖 |
| C13 | 历史 PASS，待全套 | integration 人工修正/审计；migration 不造维度 | 管理主体合成 |
| C14 | 历史 PASS，待全套 | identity 同值别名、未绑定隔离、坏提供者 | 真实绑定服务交宿主 |
| C15 | 历史 FAIL V04，核心已冻结、待独立实跑 | P Application 31 天 events=0、ledger 保留、0.5→1→0.5 | 不能用服务 PASS 替代 |
| C16 | V05 阶段 PASS，待冻结 full | P 群/公开评论/另一实例三越界；八维隔离 | 旧失败保留；授权口，不声称真实泄露 |
| C17 | 阶段 PASS，待冻结 full | P 在途身份变更、旧生成整份废弃 | 真实服务交宿主 |
| C18 | **阶段 FAIL，H01/F7 连带** | P 三模式在首次关系读取即失败，未执行切换断言 | 宿主阶段运行矩阵 PASS 属不同快照，不覆盖本轮失败 |
| C19 | 历史 PASS，待全套 | memory 读写独立、降级、不删旧数据 | 真实后端生命周期待宿主 |
| C20 | 历史 PASS，待全套 | memory 公开门面及最终验证、无伪造事件 | 真实后台缺能力明确降级 |
| C21 | 历史 PASS，待全套 | memory provenance、single-flight、授权失效 | 真实凭据待宿主 |
| C22 | V02 TTL 本轮 PASS | M 8 天正文副本清理；migration 原期限 | **最终由性能代理汇总** |
| C23 | 历史 PASS，待全套 | P none 真实本地材料与重开；experience 无依据跳过 | 模型桩 |
| C24 | 历史 PASS，待全套 | experience 视角/引用/容错 JSON | 不保证任意损坏文本 |
| C25 | 历史 PASS，待全套 | experience REM/遗忘/置顶/想象类型 | 迁移原期限本轮通过 |
| C26 | 历史 PASS，待全套 | experience 授权再生成与最终失效 | 无真实群发送 |
| C27 | 历史 PASS，待全套 | experience 默认关闭/幂等/防反馈 | LivingMemory 导出 unsupported |
| C28 | 历史 PASS，待全套 | night 五阶段/时间推进/独立性 | 唯一精力写者 |
| C29 | 历史 PASS，待全套 | night 午睡/跨午夜/时钟回退/重启 | 不补发历史动作 |
| C30 | typed端口组件历史 PASS；新R7/F13降级待验 | 匹配typed成功/失败取消他范围不收尾；最终验证120秒取消settling且不重发 | 固定宿主afterhook失败也触发/bool仅找到平台，必须显示确认能力unsupported；不要求或宣称生产成功投递 |
| C32 | 历史 PASS，待全套 | night/catchup 有界高水位与来源事务 | 不读真实聊天 |
| C33 | 历史 PASS，待全套 | behavior 默认关闭/群开关/只读模拟 | 无收费与真实外发 |
| C34 | 历史 PASS，F3 阻塞 | behavior 原生硬否决/最终复核；V06 | 不以原生 PASS 代迁移约束 |
| C35 | 历史 PASS，待全套 | identity/behavior 不猜 route | 平台实际路由交宿主 |
| C36 | 历史 PASS，待全套 | P 人类变更取消；behavior Bot/tool 不自取消 | 合成时间线 |
| C37 | 历史 PASS，待全套 | P unknown 重开/跨期/clear；behavior 崩溃窗口 | 真 SQL，运输桩 |
| C38 | 历史 PASS，待全套 | behavior success/partial/unknown/落库失败 | 无真实外发 |
| C49 | 历史 PASS，待全套 | P 事务故障六表回滚、并发、在途 clear | F6 18 项应实际收集 |
| C53 | 阶段 PASS，待冻结 full | P 事件/请求/意图关联与诊断不带正文 | 宿主日志交宿主代理 |
| C54 | 本轮 PASS | migration 一致快照/WAL/只读哈希；M CLI | 不是生产停机证明 |
| C55 | 本轮 PASS | migration 分型与原时间/TTL | 不造 Bot 状态/新维度 |
| C56 | **FAIL V06** | M proven 四限制失败；unresolved 四项通过 | 旧 V01 保留，不宣称修复完成 |
| C57 | 本轮 PASS | migration 原子回滚/硬退出/重复零新增 | 临时库 |
| C58 | 本轮组件 PASS；宿主阶段 PASS | M rollback-plan 保留新事件；宿主原生停用→Bili 回退→新记录25→25 | 隔离演练，不是生产回滚；最终快照仍待父 |

## 非组件归属

- C08：宿主阶段规则/trace/表达、观察不注入不自主、总开关停任务 PASS；
  已读新 core `tests/integration/test_main.py`，覆盖 H02/H03/叫醒/取消传播。
  新增 P `test_application_interaction_trace_expression_behavior_and_mode_controls`：
  真实事件→API/Projector/SQLite→trace/表达/行为评分；观察继续记录但不注入不发送，
  总开关停 worker/调度。**尚未执行，等两方冻结**；不加入阶段PASS列表。
  新增测试可能改变最终收集总数，668只是此前的准确时间点记录，F6仍须18项实际执行。
- C01/C03-C06/C08/C18/C30-C31/C39-C48/C52/C58/C64-C65：
  由宿主代理提供最终证据；本文没有执行 `tests/host`。
- C22/C50/C51 的旧完整复验者 `arun_6aecf96e08a3b52e23bb1202`
  曾按 C51 失败停止，不能称其执行过 C50/F9。
  后续独立 C50/F8 已交付31/31与53/53；第二轮性能独立者另完成原基准及window，
  详见下表。第三轮C51仍由父安排独立重基准，本验证者不重复；
  C22将本轮迁移TTL结果交父与独立window验证者汇总，不单方关闭整项。
- C59 文档/依赖/CI 由文档代理收敛；C60-C62 属于 T12；C63 由父汇总全清单。

### 已接收专项结论

以下是读取其他独立者产物后的边界摘要，不是本验证者重跑：

| 专项 | 实际证据 | 状态 / 尚缺 |
| --- | --- | --- |
| C51 | `verification-performance-final.md`，`local-state-final-20261105-02`；10000/10000 accepted，哈希稳定 | **FAIL：p95=56.895041ms > 50ms**；旧139.081ms/221.628ms保留，第三轮待独立原基准 |
| C50/F8 | `verification-budgets-final.md`，独立31/31、53/53，Provider16实际执行 | **限定已测快照PASS**；取消一次、已派发不退款；不重跑宿主Provider，不冒充本轮full |
| C22/F9 | `verification-performance-final.md`，`window-final-20261105-02` 11/11、物理 `[2,2,2]`；本组件历史迁移TTL通过 | 第二轮存储快照窗口PASS；第三轮受影响窗口与本轮迁移TTL待合并，整项不放行 |
| H01/C39 | `verification-host.md` 最新矩阵；关系API unavailable/storage_failed | FAIL，待新核心 F7 |
| H02/C52 | 历史四插件读故障模型1→0；父清单F10现记录独立窄复验恢复模型/发送各1、状态块0 | 窄复验PASS，最终宿主三场景待另一验证者；历史失败不删除 |
| H03/C31 | 历史可信管理员豁免未接；父清单F11现记录原生admin、可信标记、正常回复独立窄复验 | 窄复验PASS，最终宿主矩阵待另一验证者；不由组件代验 |
| C30 | 原生None/True/False均不误入睡；typed成功只直接调用Application端口 | **按新R7/F13验证降级**：unsupported展示、120秒取消到清醒/困倦、无重发，父安排host；不要求不可靠原生成功路径 |
| 宿主其余 | `final-conflict-aib5zqwq` 207 pass/2 fail；原生浏览器40 pass/0 fail、28布局 | 不同快照不拼为全绿；C14真实绑定未验，C19-C21/C27仅部分降级能力 |

### C30 最新规格引用

已读取父 spec R7 新宿主能力边界、checklist C30和tasks F13。
固定v4.29.4没有可靠原生成功回执时，明确显示不可用是兼容策略，不是免测或伪造成功：
afterhook即使失败也触发，send_message布尔值只说明找到平台。
组件继续保留匹配typed success的合成正例、失败/取消/其他范围反例；
独立宿主须实测unsupported、120秒上限取消settling回清醒/困倦、不自动重发。
没有待回复的计划睡眠、手动睡眠仍可用。不新增发送器，不要求生产投递成功。
这些F13新增条件目前**尚未由本验证者执行**，不能沿用旧typed成功直接放行。

## 交接清单

- [x] 读取父 spec/checklist/tasks 与冻结交接。
- [x] 普通 CI 环境 F3 联合复验，记录 V06。
- [x] 普通环境最小实跑，将 E01 交父协调。
- [x] 分层调整后普通收集预检 668 项，F6 18 项在内。
- [ ] 最终冻结后 E01 分层的普通实际执行及独立宿主结果。
- [x] 阶段 V05 和 probes 已执行，F7 连带失败已交接。
- [ ] 父通知核心/性能两方冻结后普通 full、V04/V05/F5。
- [x] F6 18 项实际收集，不执行 performance_probe.py；最终 full 仍须确认执行结果。
- [x] 父指定169文件交付候选有限来源扫描，38项矩阵更新；最终Git清单另核。
- [x] 接收宿主和性能阶段矩阵及未验边界，不宣称总验收 PASS。
- [ ] 收到最终冻结及交付清单后更新最终38项结果，交父释放。

## 阶段释放

本阶段停止执行，所有本验证者启动的命令均已结束，无遗留服务。
只修改 tests/verification 与两份自有verification文档；个人路径检查通过，
原始失败/evidence留本地不改；没有Git、产品修改、真实模型或平台发送。

父follow-up后顺序（以顶部启动条件为准，不自行轮询）：
1. 父明确性能freeze、原10000基准完成并允许开跑后，先V06原4参数，再完整migration；
   失败原证据保留，迁移TTL结果交父与独立window验证者。
2. 核对前后哈希，一次普通`.venv-ci` full，确认F6原18项实际执行，
   新core入口测试、V04/V05/F5、C08闭环均在结果中；不能借宿主环境补绿。
3. 如需独立定位，使用新label窄复验，不覆盖full失败，不自行改产品。
4. 接收C22/C50/C51和新C30宿主降级最终证据，再更新38项与边界；T12由父另核。
