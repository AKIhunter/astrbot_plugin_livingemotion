# T11 独立组件验证

## 最终组件实跑完成，已释放

父明确全部产品冻结、C51 final-03与window-03已结束后，本轮使用现成普通
`.venv-ci` 串行完成原V06、完整migration、一次普通full；未安装或借宿主依赖。
**38项组件索引为29项PASS、9项限制、0项FAIL；额外C08 PASS。
逐C项最终证据表以 [verification-final.md](verification-final.md) 顶部为准。**
不是全部宿主、真实外部服务或T11/T12总验收通过。

| label | 收集 / 执行 / passed | skip / deselected | pytest / runner wall s | exit |
| --- | ---: | ---: | ---: | ---: |
| `t11-v06-finalexec-ci-20261105-01` | 84 / 4 / 4 | 0 / 80 | 1.56 / 3.199536 | 0 |
| `t11-migration-finalexec-ci-20261105-01` | 84 / 84 / 84 | 0 / 0 | 5.33 / 5.957449 | 0 |
| `t11-full-finalexec-ci-20261105-01` | 1273 / 1273 / 1273 | 0 / 0 | 17.64 / 18.319883 | 0 |

failed/error均0，非collect-only、无超时。full 1273个唯一节点、23条record_property/
xunit2格式warning；原XML实际保留并已解析测量属性，未为隐藏warning修改测试。
逐节点outcome、nodeid、时间保存在 `tests/verification/evidence/<label>.json/.log/.xml`，
不把重叠套件数量相加。旧80pass/4fail、668collection与V01-V06失败仍在下方保留。

关键结果：

- F6原 `performance_f6.py` 18/18，新domain563/563、原domain38/38，
  sustained普通12/12、新main入口7/7，均在full实际执行，没有显式文件/目录重叠漏收。
- V06四proven真实计数与last_attempt_at=None通过；800秒/次日/新人类消息解除后
  各模型和发送桩1次。四unresolved次日继续拒绝，模型/发送桩0。
- V04真实Application：[0.5,0.5]绑定为1.0再解绑为0.5，
  31天后events=0、ledger_unchanged=true、send_stub_calls=0。
- V05群/公开评论/另一实例三例各PASS；F5无新事件24小时恢复，
  API/行为当前快照一致、不写回原状态；C18三模式已跑到切换后断言。
- C08 stress 0.0→0.10501750000000001，行为score 0.238375→0.232124，
  trace/表达对应；observe_only记录不注入/不自主，禁用停worker与调度；
  provider_lookups=0、send_stub_calls=0。

PASS项（仅组件范围）：C07、C09-C13、C15-C18、C22-C26、C28-C29、
C32-C34、C36-C38、C49、C53-C57，共29项。
限制项：C02、C14、C19-C21、C27、C30、C35、C58，共9项。
C02有限来源扫描通过不等于版权；C14真实OneID未验；LM后台来源检索与幂等导出
unsupported，C19-C21/C27不能宣传真实成功。C30 typed成功/失败/异范围/截止时限
及组件120秒取消、unsupported展示PASS，最终宿主无可靠回执和不重发由另一人验证。
C35真实平台路由/投递、C58宿主实际停用/消费者回退另核。

C22离线聚合已完成：本轮迁移8天正文副本0及原期限约束、full window11/11，
独立window-03 11/11物理[2,2,2]和原C51默认满10000/每scope200证据。
full与window-03共有37产品hash相同，与C51 final-03共有11产品hash相同。
C51引用原10000主样本p95=48.801416ms PASS，不重跑、不过度宣称余量。
C50/F8继续引用已交付31/31、53/53，不重复Provider；background/models未变，
但其余五产品路径与旧F8快照不同，不能将旧Provider证据冒充本轮实跑。

三次执行前各121文件清单相同，51产品路径在各轮前后、跨轮和收尾复核一致；
产品紧凑JSON摘要SHA256为
`72628876ffdd9e8eb09efe948b720f51313c6cc474292148b0558454456da392`。
V06/migration无漂移；full原runner仅记录排除目录新增
`tests/host/final_provenance.py`：before无此键，收尾清单121→122，
仅新增1项、删除0项、修改0项。收尾SHA256为
`884deab3108070f57885e76cde934dacbb76fd7a0d8fa77b69f1fb51d4ac57c3`。
此前摘要只比较既有键，误写为瞬态变化后恢复，现已纠正；不改原runner/证据，
不回滚其他验收者工作，不声称全清单完全稳定。这不是产品FAIL，未扩大重跑。

新有限候选扫描 `t11-source-finalexec-20261105-01`：176候选/13参考、
746长函数体/77长字面量/整文件精确重合0、扫描期间内容和清单无漂移，exit0。
含报告的扫描时快照不是最终Git/版权证明；回填报告导致文档hash变化不归产品。
旧169/13和更早36/13记录保持不变。

只用合成材料、临时SQLite和模型/发送桩，真实模型/网络平台发送0。
未改产品、任何测试源码/runner、父spec或Git，仅生成自有evidence并更新两份报告。
原始证据仍本地ignore保留，文档无个人路径/凭据。全部命令已结束，无服务或轮询，
父按最终表结合独立宿主结果勾选。父最新报告single222/four230/conflict245、
browser44/28布局全部通过并释放，输入hash一致至2026-11-05 23:55:49 UTC；
这些是父交接的宿主结果，不冒充本轮组件执行。README/metadata/gitignore及7篇docs
后续收尾与本轮执行快照分开；最终候选来源及隐私交T12，本轮不再新增检查。
本节以下静态准备和旧矩阵均为历史，不是当前结论。

## 给父任务：本次静态准备完成

本次接替者未参与产品实现，已读取指定交接和原测试入口；**本次测试执行数为0**。
没有启动pytest（含收集）、基准、宿主、浏览器或真实模型/平台发送；
只更新本文及 `verification-final.md`，未改runner、原断言、其他测试或产品。
没有可用代理消息接口，详细准备矩阵和未执行命令已置于
[verification-final.md](verification-final.md) 顶部。

核心22:18:24 UTC已冻结；第三轮F6仍由 `emotion_latency_last_mile` 独占CPU，
其后父安排原10000样本benchmark独占。**必须等父明确通知性能freeze、
原benchmark完成并允许组件开跑**，才按原runner执行V06四proven、完整migration、
一次普通`.venv-ci` full。不因瞬时hash不变启动，不自行轮询。
V04的31天ledger、V05三越界、F5恢复、新入口/取消、F6原18项与额外C08均待实际结果；
668仅为旧收集数，新增普通用例按本轮逐例结果记录。

C50/F8已收到其他独立者31/31与53/53，不重复宿主Provider；
上一轮C51仍为56.895041ms FAIL，第三轮独立基准由父安排。
C22迁移TTL须与独立window按新快照汇总；C30 typed成功与宿主unsupported、
120秒取消且不重发分开，LivingMemory后台检索/导出unsupported不改口径。
本阶段已释放，等待明确消息；以下全部保留为历史证据，不是本次运行。

## 历史阶段交接

状态：阶段交接（非最终验收）。新独立者已开始最终复验，
最新证据与组件矩阵见 [verification-final.md](verification-final.md)。
普通 `.venv-ci` 的 `t11-final-f3-ci-20261105-01` 实跑为 **80 passed / 4 failed**；
正文 TTL 与 unresolved 限制通过，但 proven 四限制暴露 V06 的虚构计数/尝试时间，
F3 尚未通过。以下历史结果和原始失败全部保留，不由新结果覆盖。
最新阶段 `t11-final-v05-ci-20261105-01` 三项授权反例通过；
`t11-stage-probes-ci-20261105-01` 为26通过/3失败/1未选，三失败为C18首个关系读取
受H01/F7缺方法阻塞，V04未重跑。普通668项仅完成收集，其中F6有18项；
当时最终full等待新核心与新性能所有者两方冻结；本轮启动条件以顶部为准。
父指定的交付候选有限扫描已完成：169文件/13参考、精确重合0，原文不输出，
详见新汇总；最终Git清单另核。C30以父新R7/F13为准：typed成功仍属组件，
固定宿主验证unsupported、120秒取消settling及不重发，不假造生产成功回执。
只维护 `tests/verification/` 与本文，
不修改产品代码、父规格或 Git。下表不是最终全套通过声明。
验证者未参与主要实现。作者文档只用于寻找接点，不作为通过证据。

## 记录规则

- 检查范围：C02、C07、C09-C30（不含 C08）、C32-C38、C49、C53-C58。
- C50 预算、C51 性能由其他验证者负责，本文不作结论。
- PASS 只表示所列实际检查范围；宿主消息回执、真实外部后端等无证据项标待宿主。
- 所有运行使用合成资料、临时数据库、模型/发送桩，不读取生产凭据或真实用户内容。
- 命令以插件目录为 cwd，解释器为工作区 `.livingemotion-host-t1/venv/bin/python`。
- `tests/verification/evidence/*.json` 保留命令、退出码、时间、环境和源码 SHA-256；
  `.log/.xml` 保留实际测试明细，不能用作者测试数量替代本次运行。
- 原始 evidence 仅在本地保留，不纳入 T12 提交。本文命令中的 `WORKSPACE`
  表示本次工作区根目录；旧 JSON 的准确绝对命令与原始失败不作改写。
- 本文逐项映射的责任人均为父代理分配的模块维护者；修复/接口变化即重跑，
  合并前再跑全套。失败无豁免，不勾选父清单；待宿主项在对应真实宿主验证后刷新。

## 执行进度

- 已读父规格、任务、检查清单与模块接点文档。
- 已确认可写目录的父目录存在。
- 原组件集 `components-02`：447 passed / 7.88s，退出 0。
- 原迁移交接后 `migration-01`：47 passed / 5 failed，退出 1；F3 修复仍在实施，
  不在其完成交接前重复 CLI。V01/V02 原失败保留，不能提前标修复通过。
- 独立反例 `probes-05`：25 passed / 4 failed / 0.67s，退出 1；
  运行期间源码哈希未变化。V03 已在该次通过，新增 V04/V05 如下。
- 父要求最终全套在核心冻结后运行；目前没有独立全套通过证据，不做全量轮询。
- F3 迁移已完成交接；独立 `migration-base-01` 为 **47 passed / 2.05s / exit 0**，
  运行期间源码哈希未变化，只更新 C54/C55/C57/C58 证据。没有消费作者 74 passed
  作为独立结果，也没有提前认定 C22/C56 的最终核心硬闸通过。
- `diagnostics-recovery-01`：**3 passed / 27 deselected / 0.25s / exit 0**，
  源码运行期间未变。独立确认 C09 API/行为快照一致恢复且不写回，C53 生成正文、
  异常正文不进诊断。27 deselected 为显式 `-k` 选择，不能算全套通过。
- `source-overlap.json`：实读新源码 36 文件与选定参考源码 13 文件，
  >=10 行函数体、>=120 字符字面量、整文件精确重合均为 0。
  这是有限静态佐证，不是所有历史/改名代码/版权授权的证明。

## 最新阻塞交接

### V04：C15 真实 Application 关系读取未接绑定投影（FAIL）

责任：父分配核心 integration；需与身份模块协作，不能仅使领域测试通过。无豁免。

最小复跑：本文公共命令前缀下运行
`tests/verification/run_checks.py probes --label probes-05`。
用真实 Application/AstrBotBridge/API/SQLite，合成身份提供者明确绑定两个 qq 账号；
各收到一条真实结构 Message，各自关系贡献 0.5。31 天 cleanup 后 events=0，
账本保持原样，API 绑定时只返回 0.5（应为 1.0），解绑后仍为 0.5。
失败节点：`test_application_bound_relationship_read_reprojects_retained_ledger`。
证据 `probes-05.{json,log,xml}`；模型调用/外发均为 0。

定位：`api.py` 的 `_snapshot/get_relationship` 仅读取当前账号 State；
`runtime/application.py:current_snapshot` 同样读取本地关系；
`IdentityAdapter.project_sources` 和 `domain.relationship.project_relationship`
在当前应用读取链路没有调用者。需按当前身份授权重算，事件保留期后也有效。

### V05：C16 来源授权将账号绑定误当跨场景/跨实例授权（FAIL）

责任：父分配身份模块维护者，并由 integration 复验接入；优先级高。无豁免。

同次 `test_identity_grant_does_not_turn_private_account_binding_into_scene_access`
三参数实际均 `granted_private_sources=1`：目标为群聊、公开评论、另一实例。
群聊使用匹配 `qq-instance:GroupMessage:room` 的来源和合成公开身份协议；
公开评论无 route，走真实保守回退路径也仍获私聊来源。
没有真实用户材料或真实外发。已证明是授权端口放行，**不声称现有发送链已泄露正文**。

定位：`adapters/identity.py:130-140` 只判断 bot/persona/账号成员/adapter，
不判断 instance、scene_kind、场景受众；`domain/relationship.py:280-312`
依赖调用者 grant，仅再次判断 bot/persona。修 V04 接入前应先收紧 V05，
不能使原未接入缺口转成实际跨场景泄露。

## 已获证据矩阵

以下 PASS 均为真实执行的离线组件结论，不等于真实宿主通过。C50/C51 不在本表。
`P` = `tests/verification/test_cross_module.py`，`M` = `tests/verification/test_migration_cli.py`。
除显式 `P/M` 外，节点名在本行给出的 `tests/<目录>/` 下定位；
完整 nodeid 与实际结果见日志/XML。源码锚点使用函数名，避免并行修复造成行号漂移。

| 检查点 | 当前组件证据与结论 | 产品锚点 | 宿主/交付边界 |
| --- | --- | --- | --- |
| C02 | PASS（有限静态）：P `test_domain_ast_has_no_host_private_plugin_or_sql_access`；source-overlap 36/13 文件 0 精确重合 | `domain/`；`LICENSE`；`THIRD_PARTY_NOTICES.md` | 来源声明已存在；版权/所有历史复制无法由有限扫描证明，仍需交付审阅 |
| C07 | PASS：domain `test_sadness_is_observed_not_copied_to_bot`；integration `test_default_chat_without_model_and_unique_suffix` | `contracts.py:HumanObservation/BotAffect/Relationship/NightState`；`domain/emotion.py:apply_emotion` | 合成宿主，观察与 Bot 分型 |
| C09 | PASS（diagnostics-recovery-01）：P `test_api_read_applies_elapsed_recovery_without_new_events`、`test_application_behavior_snapshot_uses_same_readonly_recovery_as_api`；probes-05 的过期/乱序反例 | `storage/sqlite.py:current_affect`；`domain/emotion.py:decay_affect/observe_human` | V03 在 probes-04 仍失败，后续已复验；不伪造新刺激、不刷新持久版本，最终冻结需再验 |
| C10 | PASS：domain `test_invalid_numbers_rejected`、`test_invalid_models_all_fall_back_to_rules`、`test_seeded_clock_replay_and_signal_sequences_stay_finite` | `contracts.py` 校验；`domain/emotion.py:_model_delta/_number` | 无真实模型调用 |
| C11 | PASS：P `test_actual_projector_duplicate_race_applies_all_state_once`（20 并发仅 1 accepted）；domain `test_fifty_new_ids_do_not_bypass_similar_stimulus_budget`；storage `test_cold_scope_window_not_skipped_by_hot_scope` | `storage/sqlite.py:commit_event/read_window`；`domain/emotion.py:_stimulus_allowance` | 本地真实事务，不是吞吐指标 |
| C12 | PASS：identity/relationships `test_positive_and_negative_changes_never_refund_daily_budget`、`test_opposing_signals_in_one_event_charge_absolute_motion`、`test_real_interaction_without_memory_establishes_familiarity_only`；P 三模式 | `domain/relationship.py:apply_relationship/_budgets` | 与外部记忆无依赖 |
| C13 | PASS：integration `test_management_correction_ledger_audit_and_stale_generation`；migration `test_relationship_not_aggregate_or_invent_trust` | `storage/sqlite.py:correct_relationship/audit_records`；`domain/relationship.py:correct_relationship` | 操作主体由合成认证入口提供 |
| C14 | PASS：identity `test_oneid_same_value_compatibility`、`test_unbound_accounts_never_merge_by_persona_platform_or_bot`、`test_provider_malformed_or_mismatched_identity_falls_back_without_merge` | `adapters/identity.py:same_value_alias/resolve/local` | 真实 LivingMemory 插件组合待宿主 |
| C15 | FAIL V04：P `test_retained_source_ledger_can_unbind_after_all_events_deleted` 纯组合可 6→3；但 Application 节点实测 0.5→0.5，未接聚合 | `api.py:get_relationship`；`runtime/application.py:current_snapshot` | 不能拿领域/端口 PASS 代替应用链路 |
| C16 | FAIL V05：P 八维状态/材料矩阵通过，但来源 grant 三参数均越界放行 | `adapters/identity.py:IdentitySnapshot.project_sources`；`domain/relationship.py:project_relationship` | 未发生真实外发，授权缺口仍阻塞 |
| C17 | PASS：P `test_application_inflight_generation_uses_live_persona_and_identity[identity]`；memory `test_unbind_during_recall_or_validation_rejects_all_material`；behavior `test_unbinding_discards_whole_generation_not_only_citations` | `adapters/astrbot.py:current`；`services/behavior.py:_gates/_execute` | 合成提供者修订号变化；真实绑定服务待宿主 |
| C18 | PASS：P `test_live_mode_switch_keeps_core_states_and_sleep[none/local_lite/external]` | `runtime/application.py:_build_services/refresh_config` | external 缺提供者时保守降级，不代表真实外部可用 |
| C19 | PASS：memory `test_external_read_write_independence_and_background_degradation`、`test_read_switch_off_invalidates_cached_evidence` | `adapters/memory/` 的网关及外部适配器 | 外部旧库未触碰；真实后端生命周期待宿主 |
| C20 | PASS（端口）：memory `test_external_real_public_contract_and_final_validation`、identity `test_background_never_constructs_a_fake_event_and_service_loss_invalidates` | `adapters/memory/livingmemory.py`；`adapters/identity.py:resolve` | 待宿主：本次只有公开协议桩，不冒称真实后台门面可用 |
| C21 | PASS：memory `test_incomplete_external_provenance_is_never_filled_from_query`、`test_request_purpose_single_flight_and_available_reuse`、`test_external_metadata_change_invalidates_whole_generation` | `adapters/memory/` provenance/validation；`ports/memory.py` | 真实外部最终凭据待宿主 |
| C22 | FAIL V02，待 F3：storage 上限/TTL、experience 引用清理通过；M `test_imported_bounded_window_does_not_keep_body_after_retention` 失败 | `storage/sqlite.py:cleanup`；`storage/legacy_import.py` | 迁移正文副本不能以普通窗口为空冒充清理 |
| C23 | PASS：P `test_experience_none_memory_real_loader_and_pin_survive_restart`；experience `test_none_memory_real_local_interaction_diary`、`test_no_evidence_skips_without_charge` | `services/experience.py:local_materials/queue_diary` | 仅模型桩 |
| C24 | PASS：experience `test_success_only_bot_actions_and_perspectives`、`test_summary_original_sources_and_unknown_perspective`、`test_tolerant_json_valid_bodies` | `services/experience.py:perspective/parse_entry` | 合成容错样本，不对任意无结构文本保证恢复 |
| C25 | PASS：experience `test_dream_requires_rem`、`test_dream_decay_pin_faint_and_unpin_no_rejuvenation`、`test_diary_dream_source_stays_imagined_and_cannot_refresh_time`；P 真实 pin 持久化 | `services/experience.py:dream_clarity/dream_material/_night_allowed/set_pin` | 迁移体验 TTL 另属 C22/C56，待 F3 |
| C26 | PASS：experience `test_mixed_private_diary_share_regenerates_only_authorized_material`、`test_share_final_revalidation_discards_not_redacts` | `services/experience.py:queue_share/take_share` | 分享生成仅桩；未向群真实发送 |
| C27 | PASS（默认关闭/协议）：experience `test_livingmemory_export_explicitly_unsupported`、`test_export_source_idempotency_partial_retry_and_no_feedback` | `services/experience.py:export/_feedback`；`adapters/memory/` | 待宿主：LivingMemory 真实导出明确 unsupported，不能宣称真实写入可核实 |
| C28 | PASS：night `test_all_five_phases`、`test_sleep_stage_boundaries_and_cycle`、`test_elapsed_not_tick_count`、`test_imports_have_no_host_storage_memory_or_sender_dependencies` | `domain/night.py:advance_night/sleep_stage/apply_interaction` | 精力由夜间领域产生，投影只消费结果 |
| C29 | PASS：night `test_nap_across_midnight`、`test_rollback_does_not_double_charge_or_recharge`、`test_settling_reply_and_offline_wake_survive_restart`；experience `test_offline_or_nonlive_rem_never_backfills` | `domain/night.py:advance_night`；`runtime/night.py` | 固定时钟与临时库重开 |
| C30 | PASS（历史类型回执）：night `test_all_non_success_outcomes_leave_pending`、`test_other_scope_and_revision_never_settle`、`test_stale_future_missing_or_wrong_ids_rejected`；integration 收尾测试 | `domain/night.py:apply_reply_receipt`；`runtime/application.py` 确认端口 | 按新R7/F13待宿主验证确认能力unsupported、120秒取消收尾且不重发；bool/None/afterhook不算可靠成功，不要求伪造生产投递 |
| C32 | PASS：night `test_high_watermark_freezes_despite_new_messages`、`test_catchup_watermark_and_sources_commit_together`、`test_summary_expiry_purges_body_without_reopening_completed_batch` | `services/catchup.py:build_catchup/catchup_intent` | 不读取真实聊天历史 |
| C33 | PASS：behavior `test_default_disabled_and_preview_is_read_only`、`test_groups_need_separate_switch`；experience `test_defaults_no_model_no_charge` | `config.py` 默认值；`services/behavior.py:preview_behavior` | 无收费、无外发 |
| C34 | PASS（原生策略）：behavior `test_all_policy_hard_vetoes_precede_scoring`、`test_final_rechecks_sleep_energy_and_policy`、`test_last_async_refresh_cannot_hide_sleep_or_human_or_dnd_change` | `services/behavior.py:_gates/_execute` | 旧迁移限制仍由 C56 FAIL 阻塞 |
| C35 | PASS：identity `test_native_source_never_guesses_missing_bot_or_route`；behavior `test_missing_or_forged_route_is_rejected`、`test_route_is_never_synthesized_or_fallen_back_to_id` | `adapters/identity.py:context_from_event`；`adapters/behavior_sender.py:__call__` | 真实平台路由成功发送待宿主 |
| C36 | PASS：P 在途 `[human]`；behavior `test_bot_preface_and_tool_receipts_never_self_cancel` | `storage/sqlite.py:human_watermark`；`services/behavior.py:_gates` | 人类来源与 Bot/tool 桩分离 |
| C37 | PASS：P `test_unknown_real_history_survives_reopen_retention_and_clear`；behavior 并发/崩溃窗口系列；storage `test_intent_unknown_is_never_retried` | `storage/sqlite.py:recover_inflight/behavior_history`；`services/behavior.py:_execute` | 真实 SQL history，不靠测试目录缓存恢复 |
| C38 | PASS：behavior `test_success_requires_confirmation_and_persists_real_event`、`test_none_partial_and_timeout_are_unknown_without_success_evidence`、`test_success_event_commit_failure_is_reported_without_resend` | `services/behavior.py:_receipt_status/_execute`；`adapters/behavior_sender.py` | 成功/部分/未知均为可控运输桩 |
| C49 | PASS：P `test_api_fault_after_state_write_rolls_back_keys_trace_ledger_and_projection`（事务中 trigger 故障，6 表均零）、20 并发 API、在途 clear；runtime 队列满与 stale 代际测试 | `storage/sqlite.py:commit_event/_transaction`；`api.py:ingest_event` | 实际 accepted + 投影原子，不是只测空写 |
| C53 | PASS（diagnostics-recovery-01）：P `test_correlation_records_and_health_exclude_private_body_and_exception`；事件 key、request job_id、intent_id 和 reason 可关联，合成原始/生成/异常正文不进诊断/caplog/stdout | `runtime/background.py:_worker/health`；`storage/sqlite.py:query_records/health` | 组件诊断通过；真实宿主日志独立验证，本产物只合成数据 |
| C54 | PASS：migration `test_live_wal_refused_backup_snapshot_accepted`、`test_preview_readonly_hash_privacy_and_actual_instance`、`test_same_file_and_hardlink_refused`；M CLI 前后 SHA256 相同 | `storage/legacy_import.py` 快照验证；`tools/migrate_legacy.py` | 一致快照声明不等于工具已验证生产停机 |
| C55 | PASS（F3 后 migration-base-01）：migration `test_field_semantics_original_ttl_and_api_instance`、`test_bare_account_or_broken_source_never_human` | `storage/legacy_import.py` 分型映射 | 非运行期冷却/额度项，未外发 |
| C56 | FAIL V01，待 F3：M 四种限制真实 CLI→重开→history→BehaviorService 均放行；原迁移关系/引用/旧动作历史测试通过 | `runtime/legacy.py`；`storage/sqlite.py:behavior_history`；`services/behavior.py:_gates` | 修复必须验证原时间/周期、未知范围硬拒绝、无新 TTL |
| C57 | PASS（F3 后 migration-base-01）：migration `test_whole_transaction_rollback_after_partial_writes`、`test_hard_process_exit_recovers_without_partial_rows`、`test_no_facts_vectors_or_arbitrary_tables`；M 重复 import=0 | `storage/legacy_import.py` 导入事务/回执 | 无生产库 |
| C58 | PASS（CLI 演练）：M `test_cli_rollback_preserves_new_event_and_requires_stopped_target`；migration `test_rollback_dry_run_preserves_new_records_and_consumer_choices` | `tools/migrate_legacy.py:rollback-plan`；`storage/legacy_import.py` | 待宿主：只验证计划/拒绝/新数据保留，没有真实停执行器或改消费者配置 |

## 公共复跑命令

当前普通最终 full 必须使用插件根 `.venv-ci/bin/python`，清空 PYTHONPATH/PYTHONHOME，
禁user site，准确命令见 `verification-final.md`。
等待父明确性能freeze、原完整benchmark完成并允许开跑，不能只凭两份旧冻结记录。
普通层按当前配置排除 tests/host、原生 console 和 model_payload，F6 18项显式收集；
原生层由单独宿主命令执行，不代表全部层次通过。

以下仅是旧阶段的历史命令。工作目录：插件根。指定宿主 Python 3.12.16 原环境无 pytest；
当时使用现有 `.venv-ci`
只读提供 pytest 依赖，未安装/修改环境。没有运行 tests/host，真实宿主由其他代理验收。

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/.venv-ci/lib/python3.12/site-packages" \
"$WORKSPACE/.livingemotion-host-t1/venv/bin/python" \
tests/verification/run_checks.py probes --label probes-05
```

将 suite 换为 `components` / `migration` / `full`，使用新的唯一 label 保留历史。
原阶段的 `full` 遵循当时仅排除 `tests/host` 的配置；该排除清单已由交付代理更新。
不得以旧宿主解释器命令冒充普通 CI；未通过不勾选父清单，不从窄回归推断全套已通过。

本阶段另外两次准确命令（同上环境前缀）：

```bash
tests/verification/run_checks.py migration-base --label migration-base-01
tests/verification/run_checks.py probes --match 'correlation_records or readonly_recovery or api_read_applies_elapsed_recovery' --label diagnostics-recovery-01
```

来源检查历史准确命令保留在 `source-overlap.json`。当前工具已要求新标签，
下面是新的有限扫描复跑命令；最终扫描还须传入 `--manifest` 的交付清单，
格式为 `{"files": ["相对插件根目录的文件路径"]}`：

```bash
PYTHONDONTWRITEBYTECODE=1 \
"$WORKSPACE/.livingemotion-host-t1/venv/bin/python" \
tests/verification/check_source_overlap.py \
--reference "$WORKSPACE/插件/astrbot_plugin_congling" \
--label source-overlap-new-01
```

历史 label 不覆盖；复跑必须换新 label。所有 `tests/verification/evidence/*.json`
记录执行命令、环境、退出码及逐文件哈希，日志/XML 记录节点结果。
本轮 `awk '/^\| C[0-9]/ {n++} END {print n}' docs/verification-components.md`
核对矩阵为 **38** 行，无 C50/C51 冒认。

F3 完成交接后的迁移复验额外要求：四限制各分 unresolved/proven 两种真实 CLI 输入。
proven 明确绑定原范围/UTC，验证实际计数不虚构、原绝对冷却到期/原日结束/新 human 后
可恢复，且各只调用一次模型/发送桩；unresolved 次日仍拒绝。新测试已准备，
**尚未在 F3 完成前运行**，不作为当前 PASS 的依据。

## 失败交接

### V01：C56 旧冷却/额度没有运行期效力（FAIL）

优先级：高。修复分配：integration；迁移代理不越界接管。无豁免，复验前不得勾选 C56。

最小复跑：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/.venv-ci/lib/python3.12/site-packages" \
"$WORKSPACE/.livingemotion-host-t1/venv/bin/python" \
tests/verification/run_checks.py migration --label migration-01
```

实际结果：`5 failed, 47 passed in 3.73s`，退出码 1，运行期间源码未变；
其中原有迁移 46 项通过。证据：`tests/verification/evidence/migration-01.{json,log,xml}`。

新增 `test_imported_behavior_restriction_blocks_after_restart` 的四参数分别只启用：
尚余 800 秒的旧冷却、同日场景已用 2 次、全局已用 6 次、连续未回复 2 次。
先写合成来源消息，关闭目标库，经真实 preview/import/import/verify CLI 导入，
再新建 SQLiteStore、recover_inflight，真实 BehaviorService 消费真实 SQL history。
四例实际均为 `global_used=0, scope_used=0, last_attempt_at=None, unanswered_count=0`，
`eligible=True`，模型桩 1 次，发送桩 1 次。没有真实模型或真实外发。

定位：`storage/legacy_import.py:538-560` 仅写 baseline/runtime_adopted=false；
`storage/sqlite.py:805-839` 只消费 quota_reservations/intents；
`runtime/application.py:130-131` 直接委托该 history。
`activation_blockers` 出现在报告，但没有运行时禁用保护。修复应采用有来源、幂等、
可审计的接管或在接管前持久阻止自主，不能把 baseline 存档算作已生效。

### V02：C22 迁移短期正文绕过清理（FAIL）

优先级：高（数据保留）。修复分配：父代理协调迁移/integration；无豁免。

同一命令中的 `test_imported_bounded_window_does_not_keep_body_after_retention`：
只选择一条 7 天有界 msg_archive 记录，CLI 导入后将时钟推进 8 天并运行真实 cleanup。
公开 read_window 为空，但 `states.kind=legacy_import` 中仍有 1 条完整原文副本，
断言 `1 == 0` 失败。查询只读取测试临时库，日志只保留合成计数。

定位：`storage/legacy_import.py:490-491,563-573` 将窗口原文存为历史档案；
`storage/sqlite.py:403-420` 不清理 legacy_import 的 original 正文。
需定义并落实可执行的档案正文 TTL/清理，不能靠“只读历史”或引用延长原文寿命。

### V03：C09 修复前失败记录（现已独立复验 PASS）

原优先级：中。修复分配：integration；无需修改领域规则。
以下是修复前精确复现；修复后证据为 probes-05 与 diagnostics-recovery-01，
包含 API 与行为快照一致恢复、不增加事件、不改变持久快照版本。

最小复跑：上述相同环境前缀下执行
`tests/verification/run_checks.py probes --label probes-01`。
其中 `test_api_read_applies_elapsed_recovery_without_new_events` 用真实
API + Projector + SQLite，提交 conflict 后仅推进固定时钟 86400 秒，再读 API。
实际 `before_stress=0.10496967918955799`，
`after_24h_stress=0.10496967918955799`，未恢复。

定位：`api.py:151-188` 的 `_snapshot/get_bot_state` 直接返回持久快照；
`domain/emotion.py` 的衰减纯函数与普通请求 expression 路径虽有测试通过，
不能代替 API 当前状态与行为评估路径。需统一当前时间的派生快照读取。
`probes-01` 共 21 passed / 3 failed：另两项为验证器夹具错误
（遗漏标准库 unicodedata、默认 fixture 无受众），已修正后复跑，不能算产品缺陷。
