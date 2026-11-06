# T11 C51 与 C22/F9 最终独立验收

## 最新独立验收 20261105-03

**完成/退出声明：原 C51 与 window 测试命令均已结束，前后hash核验完成，
测试CPU已释放；父可立即启动最终组件+宿主，不必等待下方证据整理。**
**原 C51 完整主样本 PASS，exit 0；F9 window 11/11 PASS，exit 0。**
无活动测试或后台诊断，不再执行同版本重测或新增实验；本轮证据整理已完成。
window 于22:46:57.544070 UTC完成，collected=selected=executed=call_executed=11，
failed/skipped/deselected=0，静默scope物理计数精确 `[2,2,2]`。
全产品、原bench/measurement/测试、历史证据及冻结文档在完整性清单内；
前后4898项逐项核验全部OK，前后SHA256清单字节相同，exit 0。
这是扩展文件清单，含既有环境及生成物，不是4898项测试。
**父任务即时结果：提交10000/10000 accepted，rejected/duplicate=0，
p50/p95/p99 = 38.960583 / 48.801416 / 52.982417ms；
主提交wall=21.308206s、CPU=18.665252s。**
原50ms门槛通过，p95余量1.198584ms（2.40%），不宣称稳定充足余量。

| 主读取 | 成功 / 尝试 | p50 ms | p95 ms | p99 ms |
| --- | ---: | ---: | ---: | ---: |
| Bot | 3334/3334 | 4.330292 | 4.499625 | 4.881875 |
| 关系 | 3333/3333 | 4.434042 | 4.607041 | 5.001709 |
| 对方观察 | 3333/3333 | 4.309625 | 4.479875 | 4.844000 |

读取wall=2.189794s、CPU=1.651109s，unsuccessful=0。
整进程 `/usr/bin/time -l`：45.53s real、29.88s user、9.04s sys；
原始JSON/log保留于 `tests/performance/evidence/local-state-final-20261105-03.*`。
预填10000/10000 accepted、40000状态写入，主提交也是40000状态写入；
WAL/FULL(2)、正文物理10000/每scope最大200/2560000字符/单条最大256、
双trace及四状态version增量均符合原计数。原runner前后12文件hash一致。
本节是最新结果，下方历史失败原文全部保留。

父已明确全部产品所有者冻结、无其他重测试。已核对核心
22:18:24 UTC、storage/API/Projector 第三轮22:35:47 UTC、
domain/emotion.py 第四轮22:41:45 UTC的冻结声明与产品SHA256；
原bench、measurement、预算runner/window及三份历史C51 JSON也匹配原hash。
原解释器CPython 3.12.16 / SQLite 3.53.1，原参数与50ms门槛不变。
输出使用执行前不存在的 `local-state-final-20261105-03.json/.log`，
仅执行一次。随后单独执行了 `window-final-20261105-03`，
未跑full、Provider或预算全套。
前置完整性清单保留于本地ignore目录的同名前缀 `.before.sha256`。
本轮仅允许编辑本文并生成自己的证据，不修改产品、bench、测试、其他文档或Git。
第四轮1155项功能通过和成熟400样本49.423083ms不替代本次原C51。

### 03 本轮完整结果

C51开始于 **2026-11-05 22:45:49.251319 UTC**，整进程45.53s，exit 0；
failures为空。20worker/50scope/256字符、预填/测量/读取各10000，
原成功定义、分桶尾部并发限制与nearest-rank计量均未调整。
JSON的methodology/config与历史02逐字段相同；没有SQL预填或主样本插桩。
环境仍为Apple M4 Pro/14逻辑核/48GiB、macOS15.6.1 arm64。
预填p50/p95/p99=29.750167/46.216458/49.797416ms，不作为主门禁。

| 阶段 | wall s | process CPU s |
| --- | ---: | ---: |
| 预填 | 17.910995 | 15.059935 |
| 主提交 | 21.308206 | 18.665252 |
| API读取 | 2.189794 | 1.651109 |
| 原附加纯存储读取 | 1.364908 | 1.257804 |
| 原附加1000诊断提交 | 2.095882 | 1.823168 |
| 原附加200热点提交 | 0.388329 | 0.341208 |

主提交事件循环5ms探针4019样本，p50/p95/p99/max=
0.206875/1.184458/1.561459/14.269334ms。
原JSON max_rss_bytes=68829184；time-l最终峰值68845568 bytes。

| 物理核验 | 预填后 | 主测量后 | 全部附加后 |
| --- | ---: | ---: | ---: |
| events/event_keys（各） | 10000 | 20000 | 21200 |
| emotion/relationship trace（各） | 10000 | 20000 | 21200 |
| event_traces总数 | 20000 | 40000 | 42400 |
| bot/night/observation/relationship version和（各） | 10000 | 20000 | 21200 |
| states | 200 | 200 | 200 |
| body_window / 每scope最大 | 10000 / 200 | 10000 / 200 | 10000 / 200 |
| body_chars / 单条最大 | 2560000 / 256 | 2560000 / 256 | 2560000 / 256 |

三次均WAL、synchronous=FULL(2)、busy_timeout=5000、page_size=4096、
wal_autocheckpoint=1000。原JSON逐项派生校验true、exit 0，未补写原JSON。
这些是成功提交及持久化计数证据；原bench不提供账本总数、integrity_check或
断电/故障原子性实验，本轮没有新增实验，也不声称实测这些能力。

原runner自带诊断1000/1000 accepted、0 rejected/duplicate，
API p50/p95/p99=37.723666/48.213917/48.435708ms；不混入主10000样本。

| 原诊断分段 | n | p50 ms | p95 ms | p99 ms | 累计 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 锁与线程等待 | 2000 | 17.289750 | 29.019500 | 30.141416 | 35612.445627 |
| SQLite read操作 | 1000 | 0.292042 | 0.332083 | 0.360000 | 311.349066 |
| SQLite commit操作 | 1000 | 0.883583 | 0.984500 | 10.217708 | 1144.751674 |
| commit内窗口裁剪 | 1000 | 0.012958 | 0.016417 | 0.018875 | 13.334667 |

commit操作不等于独立SQL COMMIT/fsync；裁剪已包含于commit，不能相加；
并发累计等待不等于wall。原硬编码NOT IN查询计划不代表冻结产品，不据此归因。
附加热点200/200 accepted，p50/p95/p99=37.957458/42.716333/42.902167ms；
纯存储get_state/read_window各1000成功，p95=20.983750/21.880000ms，仅附加指标。

### 03 F9 与范围

window开始/结束为22:46:57.170490/22:46:57.544070 UTC，
pytest **11 passed in 0.14s**，runner elapsed=0.373438s，exit 0。
expected/collected/selected/executed/call_executed均11，全部setup/call/teardown passed；
failed/skipped/deselected=0、collection errors/gate_failures为空。
静默scope物理 `[2,2,2]`，不是read limit；小容量16次投影后全库5、scope `[3,2]`；
默认正文长度 `[7999,8000,8000]`、调小后 `[17]`；
发生时间TTL边界物理2->1，置顶来源正文0且体验/引用保留；
全库/TTL调小物理5/1，四个硬上限原反例全部通过。

沿用 `.venv-ci` CPython3.12.16/SQLite3.53.1，pytest8.4.2、
pytest-asyncio1.4.1.post1、pytest-timeout2.4.0。
清除PYTHONPATH/PYTHONHOME并禁user site；openai/httpx不可用，
host_modules_loaded=false。两个runner均离线合成临时库，模型/网络/发送均0。
C22仅容量/window PASS，迁移TTL与最终full由另一专项补齐；
C50 31/31、F8 53/53引用既有独立结果，本轮未复跑。

### 03 实际命令

工作区根目录执行；两项JSON/log执行前均不存在，noclobber保护日志，
C51额外检查JSON不存在。bench参数仍只有 `--output`。

```bash
env WORKSPACE="$PWD" /bin/bash -o noclobber -c 'test ! -e "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/performance/evidence/local-state-final-20261105-03.json" && exec /usr/bin/time -l env PYTHONDONTWRITEBYTECODE=1 "$WORKSPACE/.livingemotion-host-t1/venv/bin/python" "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/performance/bench_local_state.py" --output "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/performance/evidence/local-state-final-20261105-03.json" > "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/performance/evidence/local-state-final-20261105-03.log" 2>&1'
env WORKSPACE="$PWD" /bin/bash -o noclobber -c 'exec env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 "$WORKSPACE/插件/astrbot_plugin_livingemotion/.venv-ci/bin/python" "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/budgets/run_evidence.py" --lane window --output "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/budgets/evidence/window-final-20261105-03.json" > "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/budgets/evidence/window-final-20261105-03.log" 2>&1'
```

### 03 冻结与证据完整性

本轮原runner前后12文件、window前后52文件一致，共同11产品文件跨lane一致。
与02相比仅api.py、runtime/projector.py、storage/sqlite.py、domain/emotion.py变化，
精确对应第三/四轮冻结；核心5路径与22:18:24 UTC冻结表逐项一致。
三份历史C51 JSON、原bench/measurement/预算runner/window均执行前核对原hash，
并包含于前后清单。未用一次瞬时hash替代父明确的所有者冻结。

| 当前冻结文件 | 前=后 SHA256 |
| --- | --- |
| api.py | `a88ef0fe7af62428710c4cd7a8f587e070e6b6ad2a6660348d7238986c11e9c9` |
| runtime/projector.py | `cb1051be1814573a1b24f95cf1f5511aa2c48cf82adf0eaadbfd400045a24c79` |
| storage/sqlite.py | `599cec9c29caa8c69f84bb27ed88c027a7fdf548ea11442153021d49199eb116` |
| domain/emotion.py | `f79c1ef6dac5a50d4fdaf72ba8d00e40156abbe070007a91c80e4ad8d6876fc0` |
| docs/INTEGRATION.md | `5cf59855d51f52d3ccdbb9e3c4ff08ce79d4fe1735db617374523bcefc7a2132` |
| docs/performance-fix.md | `a61a4933d26bd8363e564126dbf78acb89169f1393b4586c7e5e64efcdab113a` |
| docs/performance-domain-fix.md | `3f6eaa719697526f3d3c13f27171c801efe7f12a9dce83283da3e5d9be1b9710` |

完整清单在 `tests/performance/evidence/local-state-final-20261105-03.before.sha256`
及 `.after.sha256`，各4898项；`shasum -a 256 -c`全部OK，
`cmp`两清单exit 0。清单也保护既有 `verification-performance.md`，本轮未编辑它。
比对在释放CPU声明前完成；父随后启动的最终验收不属于本次执行窗口。
两次只读 `jq -e` 分别校验主基准计数/PRAGMA/成功/门槛和window全阶段/物理计数，
均true、exit 0，输出保留为同前缀 `.integrity-check.log` /
`.window-integrity-check.log`；没有新增测试入口。

| 本轮原始产物（相对插件根） | SHA256 |
| --- | --- |
| tests/performance/evidence/local-state-final-20261105-03.json | `fe472b2c72d3254a0bbd16977a38a66ca4eeeffea0ff7177027a1b97127d6f14` |
| tests/performance/evidence/local-state-final-20261105-03.log | `879e501c69f0a10ecea1c8fc0952b613b57fb1adb37f1034b70dd67f7d4a1b12` |
| tests/performance/evidence/local-state-final-20261105-03.before.sha256（after相同） | `c531241ad8febff49cde1d47e76f169bff89b68e9dc681a8f08031d2823e1024` |
| tests/budgets/evidence/window-final-20261105-03.json | `cb799b5d2543372dbc758e8cabce8bb1a21d01baa999c4cdcab1b6f3b770e775` |
| tests/budgets/evidence/window-final-20261105-03.log | `1f08c234cbcaefb85f94ff0955be35cc43f0fe2c51ad19ff67ff085cba98b92d` |

全部原始输出位于既有ignore目录，正文只写脱敏相对路径与结论。
本轮仅修改本文，未改产品、原benchmark、任何测试、其他docs、父spec或Git；
未安装依赖、访问网络、真实模型/平台或部署。历史失败及三轮修复记录全部保留。
独立验收交接完成，原C51仅此一次，不以附加诊断替代、不再重跑择优。

## 历史独立验收 20261105-02（原文保留）

状态：**C51 完整 10000 样本 FAIL，exit 1；F9 11/11 PASS，exit 0；C22 最终 full 待跑。**
**父任务即时结果：`local-state-final-20261105-02` 测量 10000/10000 accepted，
p50/p95/p99 = 45.081 / 56.895041 / 86.094875ms，原门槛 <=50ms 未达标。**
唯一 failure：`api_commit:ingest_event:p95_exceeds_50ms`。
预填 10000/10000、API 读取 10000/10000 成功，拒绝/重复均 0；
测量 wall=23.831715s、CPU=20.709852s。原 runner 12 个文件前后 hash 一致。
WAL/FULL(2)、正文物理 10000/每 scope 最大200、双 trace 与四状态版本增量符合预期。
原始证据：`tests/performance/evidence/local-state-final-20261105-02.json` 与同名 `.log`。
F9 collected=selected=executed=call_executed=11，failed/skip/deselected=0，
静默 scope 物理计数 **[2,2,2]**；52 文件前后 hash 一致，两 lane 共同11产品文件一致。
两项执行和证据整理均已结束，释放测试 CPU；不再重跑基准、不修产品。
任务日期：2026-11-05。本验证者未参与产品实现。
仅持有 `tests/performance/` 与性能验收文档；未改产品、原 benchmark、
其他测试、父规格或 Git。`tests/budgets/` 源码只读，仅通过其既有 runner
生成本地原始证据，未编辑该目录源码。

## 给父任务

父本次确认双冻结、全部其他测试代理/宿主/浏览器已停止，本验证者独占测试 CPU。
已核对 F6 `performance-fix.md` 的 **2026-11-05 22:16:52 UTC** 与
核心 `INTEGRATION.md` 的 **22:18:24 UTC** 冻结声明及对应产品 SHA256。
原完整 C51 仅执行一次，使用执行前未存在的 `local-state-final-20261105-02`；
结果已即时置顶，随后单独执行 `window-final-20261105-02`。没有其他测试或新诊断。
C51 失败已保留并报告 p50/p95/p99、成功/拒绝计数、CPU、原 runner 自带分段及原文件；
未修产品、降低门槛或重复择优。F9 按独立授权单列，不以 C51 延迟失败冒充窗口失败。

本会话没有可用的代理消息接口，以本文顶部交接完整结果。
所有者冻结与父授权均已收到，不以瞬时 hash 未变替代冻结。

| 检查项 | 当前结论 | 最终所需证据 |
| --- | --- | --- |
| C51 | **最终 FAIL：56.895041ms，exit 1** | 完整 10000/10000 accepted；读取全部通过，提交 p95 超过50ms |
| F9 | **冻结版 PASS，exit 0** | window 11/11，0 failed/skip，静默 scope 物理计数精确 `[2,2,2]` |
| C22 | **容量/window PASS；聚合最终待验** | 迁移 TTL 引用组件阶段证据，最终冻结版 full 待跑，不勾整项 |
| C50/F8 | **引用已交付独立结果，不复跑** | `verification-budgets-final.md` 的 31/31、53/53，Provider 16 实际执行、取消一次、已派发 quota 不退 |

C51 历史 P-C51-01 为 **221.628ms**；`local-state-final-20261105-01`
为 **139.081ms**、exit 1，均保留且原 JSON hash 未变。
首轮 400 次短 SQL 预置诊断40.406ms 不代验；
F6 第二轮成熟400样本54.616417ms仍 FAIL，也不替代本次完整56.895041ms。

## 本轮完整结果

C51 开始于 **2026-11-05 22:20:55.200795 UTC**，原命令进程 exit **1**；
不是环境/收集失败。参数固定为10000预填/10000测量/10000读取/20 worker/
50 scope/256字符，全部主提交 domain_applied，0 duplicate/rejected，未使用成功率缩水。

| 操作 | 成功 / 尝试 | p50 ms | p95 ms | p99 ms | max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 预填（非门禁样本） | 10000/10000 | 32.406375 | 50.815416 | 60.874333 | 73.071959 |
| 主 API + Projector 提交 | 10000/10000 | 45.081000 | **56.895041** | 86.094875 | 145.286666 |
| Bot 读取 | 3334/3334 | 4.331292 | 4.511667 | 4.833542 | 6.201916 |
| 关系读取 | 3333/3333 | 4.433875 | 4.620666 | 4.978000 | 6.304750 |
| 对方观察读取 | 3333/3333 | 4.309875 | 4.490167 | 4.807875 | 6.179875 |

| 阶段 | wall s | process CPU s |
| --- | ---: | ---: |
| 预填 | 19.203114 | 16.010711 |
| 主提交 | 23.831715 | 20.709852 |
| API 读取 | 2.194092 | 1.656725 |
| 原附加纯存储读取 | 1.398227 | 1.248020 |
| 原附加1000诊断提交 | 2.446348 | 2.097131 |
| 原附加200热点提交 | 0.491235 | 0.393564 |

`/usr/bin/time -l`：整进程49.88s real、32.78s user、9.44s sys；
原 JSON 在末尾采样的 max_rss_bytes=69844992，time 的最终峰值为69861376。
主提交5ms事件循环探针4472样本，p50/p95/p99/max=
0.223417/1.215416/1.619958/14.173167ms。
CPU独占由父确认；未另起宿主/浏览器/其他负载，也未增加系统负载采样。

### 原 runner 自带提交分布

仅附加1000次真实提交的插桩，不加入主10000样本，不新增诊断。

| 分段 | count | p50 ms | p95 ms | p99 ms | max ms | 累计 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| API 提交 | 1000 | 43.684792 | 56.440791 | 86.772667 | 89.955334 | 不单列 |
| 锁与线程等待 | 2000 | 19.304625 | 31.398792 | 43.881375 | 67.958042 | 41008.240164 |
| SQLite 读取操作 | 1000 | 0.314292 | 0.392958 | 0.540667 | 2.572084 | 335.798088 |
| SQLite commit 操作 | 1000 | 1.001125 | 1.508416 | 10.684792 | 17.116583 | 1355.205716 |
| commit 内窗口裁剪 | 1000 | 0.014250 | 0.023167 | 0.134708 | 0.327125 | 17.882165 |

commit 操作包含事务内工作与提交，不是单独 SQL `COMMIT`/fsync 的计时。
裁剪已包含于 commit，累计占约1.319517%，不能相加；等待为并发累计，不能当墙钟。
硬编码旧 `NOT IN` 查询计划不代表冻结产品查询计划，不据此归因。
热点200/200成功、0拒绝，p50/p95/p99=47.592625/59.404875/68.161583ms；
纯存储 get_state/read_window 各1000/1000，p95=22.001542/22.471750ms，均仅附加指标。

### 持久性与 Atomic 核验

`fullDurability` 是只读派生核验，不向原 JSON 补字段；计数/PRAGMA 条件全部满足：

| 指标 | 预填后 | 主测量后 | 全部附加后 |
| --- | ---: | ---: | ---: |
| events / event_keys（各） | 10000 | 20000 | 21200 |
| emotion / relationship trace（各） | 10000 | 20000 | 21200 |
| event_traces 总数 | 20000 | 40000 | 42400 |
| bot/night/observation/relationship version 和（各） | 10000 | 20000 | 21200 |
| states | 200 | 200 | 200 |
| body_window / scope 最大 | 10000 / 200 | 10000 / 200 | 10000 / 200 |
| body_chars / 单条最大 | 2560000 / 256 | 2560000 / 256 | 2560000 / 256 |

三次均 WAL、synchronous=FULL(2)、busy_timeout=5000、page_size=4096、
wal_autocheckpoint=1000；预填与主测量各40000状态写入。
静态核对冻结 `storage/sqlite.py:180-188,214-247,324-405`：
`BEGIN IMMEDIATE` 内做代际/CAS、四状态、幂等键、事件、trace、正文、关系账本及裁剪，
成功才 commit，`BaseException` rollback。**事务结构与成功计数核验通过**；
原 benchmark 没有账本总数、故障注入或断电测试，本轮没有补跑，不冒称实测崩溃原子性。

### F9 实际窗口结果

执行时间 **22:22:07.244244 至 22:22:07.851716 UTC**；
pytest **11 passed / 0.21s**，runner总耗时0.607331s。
expected/collected/selected/executed/call_executed 全为11，deselected/failed/skipped为0，
collection errors与gate_failures为空，全部setup/call/teardown passed，完整lane PASS。

| 覆盖 | 实际证据 |
| --- | --- |
| 静默scope调小上限 | persisted_per_scope_counts精确 `[2,2,2]`，不是读limit假象 |
| 小容量真实投影 | 16次投影；全库5条，scope计数 `[3,2]` |
| 正文长度 | 默认 `[7999,8000,8000]`；调小后 `[17]` |
| 按原发生时间TTL及边界 | 物理2->1，read_visible=1 |
| 置顶引用 | remaining_source_bodies=0，体验和来源引用保留 |
| 全库/TTL调小 | 分别物理剩5条/1条 |
| 四个硬上限参数 | 8天/201/10001/8001全部拒绝 |

无宿主、openai/httpx不可用，host_modules_loaded=false；
真实网络/模型/平台发送均0，仅合成临时SQLite，未安装任何依赖。

## 门禁策略

主专项 `testing-and-quality-gates`，置信度高。产物为发布前独立性能与物理窗口证据，
不是产品修改、通用代码审查或生产验收。

| 风险 | 检查与阶段 | 停止条件 |
| --- | --- | --- |
| 满载尾延迟或拒绝伪快 | 发布前原 API -> Projector -> SQLite 基准，预填/测量分别计数 | p95 >50ms、任何失败或主提交不足10000成功即 FAIL |
| 持久性/容量被削弱 | 比对 PRAGMA、事件/幂等/双 trace/状态版本与正文物理计数 | 任一约束不符不能仅凭 C51_status 放行 |
| 静默场景不收敛 | 冻结后便携 window lane | 收集/执行不足11、skip、物理 `[2,2,2]` 不符即 FAIL |
| 旧快照误通过 | 唯一输出名，源码与 runner 前后 SHA256，禁止缓存替代 | 源码漂移列明路径和影响，不能宣称最终快照 PASS |
| 测量资源争用 | 原重基准单进程串行运行，window 随后执行 | 记录已知并行负载；不重跑择优 |

本轮不重组 CI 套件。普通 CI 保留便携测试；重基准是独立发布前阻断项；
生产/上线探针不执行。仅合成数据、临时 SQLite，禁止网络、真实 Provider 请求和发送。
没有 CI 历史 p95，不能虚构耗时预算；沿用原测试 timeout，报告实际 wall/CPU。
关键覆盖目标是原测量/持久性约束全满足和 window 11/11，不代表全产品代码覆盖率。
任何复跑不一致均报父为阻塞，48 小时内分配处理，不自行隔离或降低门槛。
静态安全/依赖全量扫描不在本授权，现有 CI 分层与隐私配置仅只读核对。

## 命令与环境

下列是**本轮实际执行命令**，均从工作区根目录运行。
执行前 `ls -l tests/performance/evidence tests/budgets/evidence` 确认两项 `-02` 均未存在，
无需使用 `-03`。保留原解释器与 benchmark 参数，日志/JSON 均是本地生成物。
原 runner 只支持 `--output`，没有 `--events` 参数；10000 预填、10000 测量、
10000 API 读取、20 worker、50 scope、每条256字符均为原代码固定值。
原 worker 分桶尾部约20%降至10 worker 的限制保留，不调整负载或成功判定。

```bash
env WORKSPACE="$PWD" /bin/bash -o noclobber -c 'exec /usr/bin/time -l env PYTHONDONTWRITEBYTECODE=1 "$WORKSPACE/.livingemotion-host-t1/venv/bin/python" "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/performance/bench_local_state.py" --output "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/performance/evidence/local-state-final-20261105-02.json" > "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/performance/evidence/local-state-final-20261105-02.log" 2>&1'
```

C51 **exit 1**，先置顶完整结果，随后执行以下命令，**exit 0**。
未加 `-k`，未重跑31/53项预算：

```bash
env WORKSPACE="$PWD" /bin/bash -o noclobber -c 'exec env -u PYTHONPATH -u PYTHONHOME PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 "$WORKSPACE/插件/astrbot_plugin_livingemotion/.venv-ci/bin/python" "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/budgets/run_evidence.py" --lane window --output "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/budgets/evidence/window-final-20261105-02.json" > "$WORKSPACE/插件/astrbot_plugin_livingemotion/tests/budgets/evidence/window-final-20261105-02.log" 2>&1'
```

沿用现成环境，执行结果确认下列版本，未安装依赖：

| 项目 | 实际值 |
| --- | --- |
| 硬件 | Apple M4 Pro，14逻辑核，51539607552 bytes内存（48GiB） |
| 平台 | macOS 15.6.1，arm64 |
| 原 benchmark 解释器 | CPython 3.12.16，SQLite 3.53.1；benchmark 不依赖 pytest |
| window 解释器 | `.venv-ci`，CPython 3.12.16，SQLite 3.53.1 |
| window 测试依赖 | pytest 8.4.2，pytest-asyncio 1.4.1.post1，pytest-timeout 2.4.0 |
| 普通环境隔离 | 清空 PYTHONPATH/PYTHONHOME，禁 user site；astrbot/openai/httpx 均不可导入 |

window 与预算作者的宿主环境不同；其 pytest-asyncio 为1.2.0，
不能混称为同一环境。window 无需真实 Provider 或宿主源码。

## 原始基准完整性

以下6个路径均已用 `shasum -a 256` 在本轮执行前/后复核，完全一致，命令 exit 0。
历史 JSON 不改写，原 benchmark、计量断言和预算 runner 未作任何编辑。

| 文件 | SHA256 |
| --- | --- |
| tests/performance/bench_local_state.py | `4f3c1a4ffedf388af9262c7eb4cb073d3cfed24e73483bb6587e09b4678d03c4` |
| tests/performance/test_measurement.py | `5f9d4d153f7f31c5f69bbf4a723159b8d6e73365810246b6cd546dea5b0188a1` |
| tests/performance/evidence/local-state-01.json | `296daa772951c8bad2ad156608072e2b1296b521e3986c03b8b9d37208bcd560` |
| tests/performance/evidence/local-state-final-20261105-01.json | `e4987d0063f8d139d1f6e59d286791a13464cfe947c19bd7eb50a56fed8c0d07` |
| tests/budgets/run_evidence.py | `676bcabc5a0c0c328616cb21e2496c086e02f119c6a3ec64f5328a881850de19` |
| tests/budgets/test_window_budgets.py | `5e19474a297e6d1984eb8b54aad6f207332c21cb4fbc172a2d721ac92323f12a` |

### Frozen Ownership

冻结依据是父明确确认及两份所有者文档的时间/释放声明，不仅是瞬时hash。
以下10个路径的执行前/后 SHA256 完全一致，且产品匹配各自最新冻结表：

| 归属 / 文件 | SHA256（前=后） |
| --- | --- |
| F6 storage/sqlite.py | `b83c7c8d4a982e107c5024c8a18c3960f07ff0b5b51ac407b17a28c377954688` |
| F6 runtime/projector.py | `310621e8d71a27589f9a33f815299b28fc8d40198632cb57156647e43464af8f` |
| F6 api.py | `a54e017aba4d6330da2980b8b7bf7fa7c49728f76c1c542d360ff36f8a867b41` |
| core main.py | `62783b1c1a4a24231bb839e56e74c8ecfe4f40949b2e2b0ef96557633f9e0e87` |
| core runtime/application.py | `79b30e76cfaaf899e1d3297b0822d18f496a60aa4786e791e94f0709e95adc99` |
| core runtime/console.py | `219d8239453e2bf0257380c72c3eba4a488e352927cea29b2823f0708b91f833` |
| core services/behavior.py | `000308b54bf601e2ede77ead39f44643e715fb0d037bfa0bf4456dbb115b479e` |
| core引用 adapters/astrbot.py | `e513eff14ac4196bfbf3e5893ad02868c1f480e776056e0385afdfd97f621b49` |
| F6 docs/performance-fix.md | `6aadbb9ca0d58457eafe9d6f4ac72bb79797d5d79098d906a333a8e599f1e3a1` |
| core docs/INTEGRATION.md | `5cf59855d51f52d3ccdbb9e3c4ff08ce79d4fe1735db617374523bcefc7a2132` |

原 benchmark 12文件、window 52文件各自 `source_sha256_before == source_sha256_after`，
共同11产品文件跨lane一致；差异列表为空。完整逐路径hash均在两个原JSON中，
INTEGRATION属于benchmark覆盖，另以手工前后hash覆盖F6冻结文档与核心边界。
`runtime/background.py`=`e413824c41c4040c465f7b47e2c96a52ad2cb791f3ed413ca570ec5207e7690d`、
`runtime/models.py`=`562abfda94bac5fc5ef5783c846cdde24b2c40d51d4c4af1174bd8c77508eddd`，
与已交付C50/F8记录相同；不将本次window说成重验全部预算。

实际手工hash命令（插件根，前/后均exit 0）：

```bash
shasum -a 256 api.py runtime/projector.py storage/sqlite.py main.py runtime/application.py runtime/console.py services/behavior.py adapters/astrbot.py docs/performance-fix.md docs/INTEGRATION.md tests/performance/bench_local_state.py tests/performance/test_measurement.py tests/performance/evidence/local-state-01.json tests/performance/evidence/local-state-final-20261105-01.json tests/budgets/run_evidence.py tests/budgets/test_window_budgets.py
```

后测同命令另追加以下4个产物，exit 0；仅本地ignore，无个人目录写入Markdown：

| 相对路径 | SHA256 |
| --- | --- |
| tests/performance/evidence/local-state-final-20261105-02.json | `5035c579f969919da8d8abe7165e12879a7a1312be2e02312ef57e139c4caae8` |
| tests/performance/evidence/local-state-final-20261105-02.log | `cdded04662419d80a3603a79869f5e798dad7d884097a77ffd3cbac3abf88522` |
| tests/budgets/evidence/window-final-20261105-02.json | `b635fe8b61cddff1222e975ef0f077f1ffb7e735fb55e6bff2ef5fdeb0779ab4` |
| tests/budgets/evidence/window-final-20261105-02.log | `0c01d7e210ade1312cfa59297b915090e98217865848f8742b11bdc7c8697331` |

只读 `jq -s` 比对两JSON，12/52/共同11、cross_lane_changed=[]；
另两次 `jq -e` 分别逐项核验上述C51计数/PRAGMA/唯一失败和F9全收集/全阶段/
精确物理计数/零网络，均输出true、exit 0。这是证据一致性检查，不把C51 FAIL改为PASS。

交付前再次比对证据与当前磁盘，以下实际命令分别 **12/12 OK、52/52 OK，exit 0**：

```bash
jq -r '.source_sha256_after | to_entries[] | "\(.value)  \(.key)"' tests/performance/evidence/local-state-final-20261105-02.json | shasum -a 256 -c -
jq -r '.source_sha256_after | to_entries[] | "\(.value)  \(.key)"' tests/budgets/evidence/window-final-20261105-02.json | shasum -a 256 -c -
```

Markdown隐私检查用 `rg -n` 检索两份文档的个人主目录前缀，
**exit 1表示无匹配**，不是测试失败；不把匹配模式本身写入文档。

## C22 聚合与隐私

组件 `verification-final.md` 已报告 V02：
`test_imported_bounded_window_does_not_keep_body_after_retention` 的8天正文清理通过，
对应 `t11-final-f3-ci-20261105-01`（整体80 passed/4 failed，四失败属 V06）。
其源码早于本轮 sqlite 更改；本次已补齐默认满窗口及冻结版window/F9，
但迁移TTL只引用上述**阶段证据**，最终冻结版 full 尚待组件验证者执行。
本验证者未代跑迁移、不改其测试，不用旧局部PASS掩盖最终快照未验。

`.gitignore` 已覆盖 `tests/**/evidence/*`、tests XML与log；
CI 拒绝非白名单原始证据及 Markdown 个人目录路径。
本轮没有 Git 操作，仅检查磁盘文件和规则，不声称已核对暂存/追踪清单或远端 CI。
新证据只留本地，交付摘要使用相对路径或 `$WORKSPACE`。
本次实际仅编辑本文件与 `verification-performance.md`；
无需新增runner基础设施，未改产品、原benchmark参数/断言、其他测试或父spec。

准备阶段发现两处其他所有者的 Markdown 隐私待办，未越权修改：
`docs/cancellation-fix.md:67`、`docs/identity-fix.md:103`。
请父转给各自作者脱敏。`verification-performance.md` 无实际个人目录路径，
前预检仅将其通用个人主目录示例改为文字描述，本次新增最终摘要；
旧失败数字与原始 JSON 未改。
