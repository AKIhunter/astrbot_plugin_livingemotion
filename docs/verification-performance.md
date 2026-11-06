# T11 独立性能与资源验证

## 最新最终复验（2026-11-05 22:20 UTC）

双冻结后仅执行一次原完整基准 `local-state-final-20261105-02`：
**C51 FAIL，exit 1**，10000/10000 accepted，p50/p95/p99=
**45.081 / 56.895041 / 86.094875ms**，门槛仍为 <=50ms。
主提交wall=23.831715s、CPU=20.709852s；预填10000/10000、读取10000/10000。
随后独立window lane **F9 11/11 PASS，0 failed/skip，exit 0**，
物理静默scope计数 **[2,2,2]**。WAL/FULL、满窗口/双trace/状态计数符合要求；
源码前后12/52文件与跨lane共同11文件一致。
**C22容量/window通过，迁移TTL引用 `verification-final.md` 阶段证据，最终full待跑。**
C50 31/31、F8 53/53引用 `verification-budgets-final.md`，本轮未重跑。
完整命令、分布、事务核验边界、Frozen Ownership及原始证据hash见
[最终性能验收](verification-performance-final.md)。测试已结束，不修产品、不择优重跑。
下方221.628/139.081ms及历史预算/窗口失败全部保留，不作为当前快照结论。

## 历史验证记录

验证日期：2026-11-05。仅负责 C50、C51、C22；未参与产品实现。
仅写 `tests/performance/`、`tests/budgets/` 与本文，不修改产品、父规格，不操作 Git。
全部输入为合成数据，数据库使用自动清理的临时目录；禁止网络连接、真实模型和发送。

## 最终复验结论：C51 失败，按停止条件交回

新独立验收者于 **2026-11-05 21:50:07 UTC** 启动原完整 benchmark，
唯一 label 为 `local-state-final-20261105-01`，退出码 **1**。
没有修改 benchmark、产品、他人测试或父规格，没有 Git、网络、真实模型或消息操作。
本次只新增 JSON 证据并更新本文；保留下方全部旧失败记录。

| 检查项 | 本轮状态 | 实测 / 未执行边界 |
| --- | --- | --- |
| C51 | **FAIL** | 满窗口提交 10000/10000 成功，p95=139.081ms > 50ms；三类 API 读取共 10000/10000 成功且 p95 均 < 5ms |
| C50 | **未复验，不放行** | 按“fail 立刻 doc + 返回”停止，未执行 budgets runner 或 F8 的 53 项命令；实现者自测不能替代独立取消证据 |
| C22 | **容量子项 PASS；整项未放行** | 主阶段前后物理正文均 10000、每 scope 最大 200；F9 静默 scope 的 4→2 cleanup、TTL、引用原测试本轮尚未复跑 |

### 本轮原命令与主指标

工作区根目录执行，使用原有隔离 Python 3.12，没有安装依赖：

```bash
env PYTHONDONTWRITEBYTECODE=1 .livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/performance/bench_local_state.py \
  --output 插件/astrbot_plugin_livingemotion/tests/performance/evidence/local-state-final-20261105-01.json
```

证据：[`local-state-final-20261105-01.json`](../tests/performance/evidence/local-state-final-20261105-01.json)。
原 10000 次真实 API 预填充 + 10000 次真实 API 测量，50 scope / 20 worker，
10000 条满正文窗口，单条 256 字符，50ms 门槛均未改变。
保留原 worker 分配，尾部约 20% 降至 10 worker 的原限制仍存在；
不以短 probe 的 40.406ms 替代本轮，不重跑择优。

| 操作 | 成功数 / 尝试数 | p50 ms | p95 ms | p99 ms | max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| API + Projector 提交 | 10000/10000 | 117.727416 | **139.081000** | 155.683083 | 180.191250 |
| API Bot 读取 | 3334/3334 | 4.407708 | 4.661125 | 5.102916 | 6.973625 |
| API 关系读取 | 3333/3333 | 4.512708 | 4.783584 | 5.258458 | 7.132209 |
| API 对方观察读取 | 3333/3333 | 4.385875 | 4.640417 | 5.096000 | 6.968167 |

预填充与测量均为 **100%** 成功、0 duplicate / rejected，每阶段 40000 个状态写入。
主提交阶段 60.154448s，约 166.24 成功提交/s，进程 CPU 56.536418s。
5ms 事件循环探针 9559 样本：p50=1.477458ms、p95=2.586959ms、
p99=3.504667ms、max=13.960500ms；全程峰值 RSS=69,451,776 bytes。
模型及发送调用均为 0，后台 worker 未启动。

物理计数：主阶段前后 events=event_keys 从 10000 到 20000；
emotion/relationship trace 各从 10000 到 20000；
四类状态各自 version 总和从 10000 到 20000，states 始终 200。
body_window 始终 10000 行、每 scope 最大 200 行、总正文 2,560,000 字符。
最终附加诊断后 events=event_keys=21200、双 trace 各 21200、正文仍 10000。
各次检查均 WAL、synchronous=2（FULL）、busy_timeout=5000、page_size=4096、
wal_autocheckpoint=1000。没有放松原子事务或持久性；这些计数不替代故障注入原子性测试。

纯存储附加读取：get_state/read_window 各 1000/1000 成功，
p95 分别 21.018542/22.002208ms。热点附加提交 200/200 成功、0 拒绝，
p95=139.706167ms；不纳入主阶段样本，也不把热点消除拒绝称为延迟达标。

### P-C51-FINAL-01：稳定冻结源码下原完整基准仍超标

最小失败锚点为原命令产物的
`failures[0] = "api_commit:ingest_event:p95_exceeds_50ms"`，
`api_commit.successful_latency.ingest_event.p95_ms = 139.081`。
相对旧 221.628ms 已改善，但仍约为门槛的 2.78 倍，C51 不能勾选。

现有基准自带的 1000 次诊断全部成功，只有 2000 次存储访问，说明批量读取已经生效：
锁 + 线程等待 p95=66.301125ms；读取操作 p95=0.384667ms；
提交操作 p50=1.927000ms、p95=2.256875ms、p99=11.345667ms。
裁剪累计 15.442536ms / 提交操作累计 2256.540798ms，约 0.68%，
不再是旧证据中的 53.5%。这些插桩段只供定位，不能与主指标相加或替代它。

父修定位起点：`api.py:117-168` 的投影/提交，
`runtime/projector.py:62-66` 的 `read_projection`，
`storage/sqlite.py:145-148` 的共享串行锁及 `:237/:298` 的读/提交。
本轮只能证明等待仍高，未进一步插桩确定其全部成因；本验收者不改产品。
特别注意：原 benchmark 的 `diagnostic.global_window_prune_query_plan` 仍解释
测试内硬编码的旧 `NOT IN` SQL，**不是当前 F6 裁剪 SQL 的执行计划**，
不得拿它再次宣称当前实现仍全窗口双扫描。

### 复验 SHA256 与环境

JSON 中 12 个受检路径的 before/after 全部相同，
`source_changed_during_run=false`，包括 models 与 INTEGRATION；
F6 三文件与 F8 background 均匹配其交接冻结值。

| 文件 | 本轮 SHA256 |
| --- | --- |
| storage/sqlite.py | `92d218a4a33d82b586a2a4c1a638eb1bc18dbd72d27d48fcc64a6fedcd33e8f7` |
| runtime/projector.py | `64c51c315d508e5b1d29d8636002142a466161e2c11dac9122871a02f86662a8` |
| api.py | `a54e017aba4d6330da2980b8b7bf7fa7c49728f76c1c542d360ff36f8a867b41` |
| runtime/background.py | `e413824c41c4040c465f7b47e2c96a52ad2cb791f3ed413ca570ec5207e7690d` |
| runtime/models.py | `562abfda94bac5fc5ef5783c846cdde24b2c40d51d4c4af1174bd8c77508eddd` |
| tests/performance/bench_local_state.py | `4f3c1a4ffedf388af9262c7eb4cb073d3cfed24e73483bb6587e09b4678d03c4` |

环境仍为 Apple M4 Pro / 14 逻辑核 / 48GiB、macOS 15.6.1、
CPython 3.12.16、SQLite 3.53.1。benchmark 不使用 pytest。
只读核对 `.venv-ci`：Python 3.12.16、pytest 8.4.2、
pytest-asyncio **1.4.1.post1**、pytest-timeout 2.4.0；
openai/httpx 均未安装。F8 使用的既有 `/tmp/le-t11-test-deps.x1ctHY`
仍存在，其文档记录 pytest-asyncio **1.2.0**；不能混称两个环境相同。
本轮未发生测试收集/执行异常，C51 为性能门槛失败，不是 pytest 基础设施错误。

### CI 分层与待父协调事项

静态核对发现 `tests/budgets/conftest.py:10` 无条件将插件目录外、工作区内的
`.livingemotion-host-t1/AstrBot` 加入 sys.path。它不是字面量个人主目录
绝对路径，但确实隐含本机目录布局。`budget_support.py::Wire` 才延迟导入
真实 Provider、OpenAI SDK 和 HTTPX；普通 Rig/runtime/window 用例不因此必然依赖宿主。
普通 CI 无宿主可移植性本轮**未执行证明**，不能仅凭本机存在该路径标通过。

当前 `pyproject.toml` 已明确排除 `tests/budgets/test_model_payload.py`，
CI 工作流也声明单独的 native-host 层；本验收者未改这些他人文件。
**I-C50-CI-01：`tests/budgets/run_evidence.py:81-85` 继承该 addopts，
未显式覆盖排除项，因此原完整证据命令有漏掉 Provider/SDK 用例的风险。**
另 `:94-96` 无条件读取 openai/httpx 包版本，不能作为 `.venv-ci` 的独立便携 runner。
这是测试基础设施风险，与 C51 产品性能失败分开记录，不以 skip 掩盖。

当前会话无可用 agent 消息接口，尚未与父或最终 components 代理完成协商；
请父转达并确认：普通 CI 保留全部便携预算断言；宿主专属验证由显式 runner
校验宿主路径/版本及 SDK 依赖，显式包含全部 Provider 用例、禁止网络且只用 MockTransport，
产物注明 CI 层级和收集数，缺宿主应明确失败而非 skip/pass。
后续独立复验须先保证完整 runner 不受普通层排除项影响，再复跑原 budgets、
F8 53 项和 F9 原反例；不得用缺少真实 transport 取消例的绿色结果放行 C50。

按本次明确停止条件，现交回 P-C51-FINAL-01 与 I-C50-CI-01；
未等待父修、未重跑重型基准、未运行其他全量测试，释放本验收任务。

## 旧轮独立结论（历史失败证据，原文保留）

| 检查项 | 状态 | 已实测 / 尚缺 |
| --- | --- | --- |
| C51 | **FAIL** | 满窗口真实 API 提交 p95=221.628ms，门槛保持 50ms；状态读取通过该延迟门槛 |
| C50 | **FAIL** | 29 passed / 2 failed；两个失败用例共同证明在途调用方取消未传到工作/Provider，请求仍继续并记 succeeded |
| C22 | **FAIL** | 10 passed / 1 failed；默认容量、TTL、引用清理通过，但调小每场景上限后 inactive scope 实际正文仍超限 |

父任务已确认 C51 保留 FAIL 并安排 F6。本轮不等待修复，不降低阈值，
不重跑重型基准冒充修复后验收。已完成当前独立验证并交接。

## 环境与复跑

Apple M4 Pro，14 逻辑核，48GiB 内存；macOS 15.6.1 / Darwin 24.6.0 arm64；
CPython 3.12.16，SQLite 3.53.1。WAL、synchronous=FULL(2)、
busy_timeout=5000ms、page_size=4096、wal_autocheckpoint=1000，未降低持久性设置。

从工作区根目录执行，约数分钟；未达标退出码为 1：

```bash
env PYTHONDONTWRITEBYTECODE=1 .livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/performance/bench_local_state.py \
  --output 插件/astrbot_plugin_livingemotion/tests/performance/evidence/local-state-02.json
```

首轮机器可读证据：[`local-state-01.json`](../tests/performance/evidence/local-state-01.json)。
文件只含环境、配置、计数、统计、源码 SHA256 与查询计划，无原文/账号/密钥/数据库文件。
`bench_local_state.py` 不符合 pytest 默认测试文件名；
`tests/performance/` 在普通 pytest 中仅收集两个轻量计量单测。

## C51 测量边界

- 真正调用 `LivingEmotionAPI.ingest_event -> Projector -> SQLiteStore.commit_event`，
  包括解析、generation、四类状态读取、规则计算、四类状态写入、事件与双 trace 原子提交。
  读取真正调用门面 Bot、关系、对方观察快照，要求 snapshot 且 version>0。
- 使用 50 个独立场景、每场景一个生产者，20 个闭环异步工作者；
  每条正文 256 字符，有人类账号及 sadness 信号以覆盖观察投影。
- 先经真实 API 写入 10000 条，50×200 满窗口，再测额外 10000 条提交和 10000 次读取。
  预填充独立记录，不冒充满库时延；最后约 20% 提交因场景分配不均降至 10 个工作者。
- 使用 nearest-rank 百分位；失败、重复、未投影 accepted、baseline 读取不算成功。
  没有客户端重试；产品 API 自身最多三次 CAS 重算计入时延。
- 不含 Application 配置同步/宿主消息钩子/HTTP，也不测真实模型。
  单进程单库合成负载不能代表生产表现、极限吞吐、开放环流量或容量余量。

### 主指标

单位 ms：

| 操作 | 成功样本 | p50 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| API+Projector 提交 | 10000 | 184.695 | **221.628** | 251.231 | 294.413 |
| API Bot 状态读取 | 3334 | 4.151 | 4.384 | 4.511 | 4.623 |
| API 关系读取 | 3333 | 4.258 | 4.498 | 4.628 | 4.744 |
| API 对方观察读取 | 3333 | 4.157 | 4.389 | 4.518 | 4.636 |

提交阶段 95.935s，约 104.24 成功提交/s；进程 CPU=89.616s。
事件循环 5ms 探针，16338 样本：p50=0.694ms、p95=2.062ms、
p99=2.971ms、max=17.348ms。全程进程峰值 RSS=69,369,856 bytes。
后台生成未启动，模型和发送调用均为 0。

计数交叉核验：预填充/测量结束事件数 10000/20000，幂等键数相同；
emotion trace 和 relationship trace 均由 10000 增至 20000。
每阶段 10000 个 domain_applied、40000 个状态写入成功，主阶段无拒绝。
四类状态各自 version 总和由 10000 增至 20000，非空库/SELECT 1。
正文窗口始终 10000、每场景最多 200；正文共 2,560,000 字符。

### 纯存储指标（不可替代主指标）

另跑 20 并发，1000 次 `get_state` 与 1000 次 `read_window` 交替负载。
窗口读取每次均返回 200 条，状态均存在。

| 操作 | p50 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: |
| store.get_state | 17.707 | 34.062 | 45.177 | 54.761 |
| store.read_window | 19.751 | 36.449 | 50.902 | 60.566 |

### FAIL 交接锚点

1. **P-C51-01：满窗口提交超过 50ms。**
   `runtime/projector.py:47-58` 逐个读取四类状态，
   `api.py:114-143` 再进行 generation 与提交，
   `storage/sqlite.py:108-116` 使用同一串行锁。
   独立 1000 次诊断提交均成功，6000 次存储访问的锁+线程等待
   p95=97.985ms；提交事务自身 p50=5.130ms、p95=8.654ms。
2. **P-C51-02：每事件全窗口裁剪放大串行工作。**
   `storage/sqlite.py:285,312-327` 每次提交调用 `_prune_window`，
   全库 `DELETE ... seq NOT IN (... LIMIT 10000)` 查询计划包含两次
   `SCAN body_window`。1000 次裁剪累计 2994.46ms，
   提交事务累计 5600.08ms（包含裁剪，不能相加），裁剪占约 53.5%。
   建议父任务分配存储/调度专项修复并用同命令复验；本代理不改实现或规格。
3. **P-C51-03：热点附加场景有明显拒绝，不算性能成功。**
   单场景 20 并发 200 次提交，30 成功、170 `version_conflict`。
   成功 p95=274.070ms，拒绝 p95=273.998ms。
   锚点 `api.py:115,149` 三次 CAS 上限；该附加诊断不能宣传为 200 次成功。

源码一致性限制：首轮执行期间 `runtime/models.py`、`storage/sqlite.py` 文件
SHA256 改变，前后值均在证据中。Python 已导入模块不会热更新，本轮反映开始时的实现；
不是修改后的最终快照验收。产品持续集成期间不据此标 PASS，修复后须新进程复跑。

## C50 预算验证

### 命令与证据

从工作区根目录执行。指定的 Python 3.12 宿主环境没有 pytest；
测试依赖安装在临时目录，不改宿主 venv 或产品依赖。下列安装是测试准备，
测试执行本身由 socket 审计钩子禁止网络：

```bash
T11_DEPS="$(mktemp -d /tmp/le-t11-test-deps.XXXXXX)"
.livingemotion-host-t1/venv/bin/python -m pip install \
  --target "$T11_DEPS" --no-compile --no-cache-dir \
  pytest==8.4.2 pytest-asyncio==1.2.0 pytest-timeout==2.4.0
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T11_DEPS" \
  .livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/budgets/run_evidence.py \
  --output 插件/astrbot_plugin_livingemotion/tests/budgets/evidence/budgets-rerun.json
```

最终机器证据：[`budgets-03.json`](../tests/budgets/evidence/budgets-03.json)。
**41 passed / 3 failed / 0 skipped，6.22s，退出码 1**。
其中 C50 为 29 passed / 2 failed，C22 为 10 passed / 1 failed，
计量口径单测 2 passed。不运行其他 C 项全量测试。
文件只保存合成计数、原因码、版本、相对测试名和源码 SHA256，
不保存请求原文、密钥、绝对路径、数据库或异常日志。
被测源码与测试文件在本次执行前后 SHA256 一致。

环境沿用上文硬件、Python/SQLite；真实宿主源码为 AstrBot 4.29.4，
OpenAI SDK 3.46.0、HTTPX 0.28.1，pytest 8.4.2、pytest-asyncio 1.2.0、
pytest-timeout 2.4.0。唯一警告为宿主导入 audioop 的弃用提示。

测试记录沿革：`budgets-01.json` 为 25 passed / 15 failed，
包含测试夹具将 Config 当回调传给 Projector、以及尚未排队就取消的同步错误，
不把这些失败算成产品缺陷。修正夹具后 `budgets-02.json` 为 38 passed / 2 failed；
最后补充真实请求取消、日记跨场景、梦跨午夜和 TTL 调小，得到上述 44 项最终结果。

### 已验证范围

| 场景 | 实际结果 |
| --- | --- |
| 并发 1、队列 100 | 1 active + 100 queued，下一项 queue_full；排空 101 次调用，peak_active=1。此例日限额设 200，仅隔离队列测试；默认 48 另测 |
| 输入/输出上限 | 四种用途各 5 个越界/非法预算在派发前拒绝；4096 输入、1024 输出边界可执行。真实 behavior 组装输入字节上界恰好 4096，通过；4097 与输出 1025 均未上 wire |
| 请求局部 payload | 真实 Generation/Refinement/LiveExperienceService → BackgroundRuntime → OpenAIBinding → 真实 Provider.text_chat/_query → SDK → MockTransport。四用途均实测，不替换被测方法 |
| Provider 隔离 | 行为样本 max_tokens=23，其他用途 1024；n=1、两条 system/user 消息，无历史/tools。移除配置中的消息/模型/Token 覆盖，Qwen thinking=false；宿主配置、client、双 key 列表保持不变 |
| 全局日限额 48 | 48 个场景轮流使用四用途，各 12 次；24 成功 + 24 失败占满 48。重开、clear、cleanup 后第 49 次仍 quota_exhausted；次日可重新派发 |
| 情绪间隔 300s | 重开并 clear，跨 UTC 午夜后第 2s、299s 拒绝，第 300s 可调用 |
| 日记用途 | 一次成功后重开为 experience_exists；清除来源场景后换同人格其他场景仍拒绝。显式发起的失败/unknown 最多 3 次，跨重开不归零，无隐式重试 |
| 梦用途 | 一夜成功最多 2 次；失败/unknown 也消耗 2 次。同一 sleep_started_at 跨午夜及重开仍 experience_attempt_limit |
| 超时/unknown/异常 | Runtime 1s 超时、显式 unknown、普通异常均只执行一次；HTTP 503、ReadTimeout、4 字节输出上限收到 5 字节，各仅一次 wire 调用，记 unknown；不转 fallback、不退款 |
| 停止与排队取消 | runtime.stop 能取消实际 Provider transport，落 cancelled；尚在队列中的调用方取消不派发、不收费 |
| 在途跨进程退出 | 子进程真实 run_model 派发后 os._exit，SQLite 已持久 reserved；新进程 recover_inflight 改 unknown，日限额 1 拒绝下一请求，恢复后调用数 0 |
| 空闲 | 已启动 worker 无队列时无调用、无配额；不等同于完整 scheduler 的空闲验收 |

### FAIL 与最小修复建议

**P-C50-01：在途调用方取消没有取消底层工作。**

两个独立用例：

- `test_runtime_budgets.py::test_active_caller_cancel_stops_work`
- `test_model_payload.py::test_active_generation_caller_cancel_reaches_transport`

等 work/真实 transport 的 entered 信号后取消调用方 Task，等待 50ms，
再释放桩响应并 join。均只派发 1 次，但 work/transport 收到取消的次数为 **0**；
持久配额状态变成 **succeeded**。这是取消失效，不是配额退款或隐式重试。
当前配额仍消费 1，runtime.stop 的对照用例确实收到取消。

锚点：`runtime/background.py:82-91` 的 `run_model` 只 await completion；
`:99-101` 只在出队前检查 cancelled；`:119-126` 工作执行期间没有监听
调用方取消，并把全部 CancelledError 作为 worker 停止抛出。

给核心的最小建议：在每个 job 内将 completion 的取消显式关联到该 job 的
work Task，并等待取消完成；清理完成后解除关联。区分“当前 job 被调用方取消”
与“runtime.stop 取消 worker”，前者不能退出唯一 worker。
已派发请求保持配额消耗，不退款、不重试；落可观测 caller_cancelled
（若上游是否执行未知，保留相应 unknown 语义），不得落 succeeded。
还应覆盖 reserve_quota 等待期间取消，避免出队检查之后的派发竞态。
本代理仅建议，未修改实现。

### 限制

- 宿主身份/人格选择、legacy 授权、night guard 是合成边界桩；
  不是 Application 主入口、真实聊天、scheduler、平台发送或 F1 联验。
- 模型网络响应完全由 MockTransport 合成，真实模型请求、发送均为 0。
  本测试证明 SDK 序列化参数和本地计数/背压行为，不证明远端服务执行限额或实际计费。
- 输入计数按被测 `OpenAIBinding.count` 的 UTF-8 字节加模板余量口径；
  不把它称为真实 tokenizer 实测，不推断所有模型/私有推理 Token 都受同一保证。
  当前只验证原生 OpenAI Provider 类型及合成 Qwen 文本请求。
- 最新源码已由早期 tiktoken/GPT 描述改为字节上界；
  INTEGRATION 仍有旧描述，核心需同步文档，不能以旧说明代替此次源码证据。

## C22 窗口验证

默认 10000 全库 / 200 每场景来自 C51 满窗口实测；以下新增 11 个轻量用例
均使用真实 SQLite，正文数据全部经真实 API + Projector 写入，
不直接插入 body_window。

| 场景 | 实际结果 |
| --- | --- |
| 调小容量后持续写入 | per_scope=3/global=5，16 次成功事件投影后实际条数 5，各场景最多 3；重开不反弹 |
| 单条正文 | 输入 7999/8000/8001 字符，落库 7999/8000/8000；调小为 17 后新正文落 17 |
| TTL 严格边界 | 按 occurred_at 而非接收时间算 7 天；已过期及恰好 cutoff 不入窗口，cutoff+1 在时钟前进 1s 后不可读且 cleanup 物理删除 |
| 引用不延长正文 | 已置顶日记引用源事件，源正文 7 天到期后不可读；cleanup + 重开实际源正文 0，日记与来源 ID 仍保留 |
| 调小全库上限 | 已有 12 条，重开改 global=5 并 cleanup，实际余 5 |
| 调小 TTL | 7 天改 1 天后 cleanup，2 天前正文被删除，未过期正文保留 |
| 硬上限 | 8 天 / 201 每场景 / 10001 全库 / 8001 单条配置均被拒绝 |
| 调小每场景上限 | **FAIL**：已有 3 个场景各 4 条，重开改 per_scope=2 并 cleanup，实际仍为 [4,4,4]；read_window 仅返回 2，不能当作存储达标 |

**P-C22-01：inactive scope 清理不执行调小后的场景上限。**

用例：`test_window_budgets.py::test_lower_scope_limit_cleanup_prunes_inactive_scopes`。
锚点：`storage/sqlite.py` 的 `_prune_window`（当前约 `:365-380`）
只有传入 scope_key 才裁剪每场景数量；
`cleanup`（当前约 `:456-461`）调用时不传 scope_key。
范围内没有新消息时，旧正文会继续占用超过新配置的存储。

给核心的最小建议：在明确的 cleanup/配置缩小路径枚举现存 scope，
或用按 scope 分区的裁剪 SQL，对全部场景执行最新上限；
保持 TTL 与全库上限同事务，并确认无新写入时重开也收敛。
不要把全场景重扫再加到每条事件提交热路径，以免放大 C51 已测热点。
本轮未评估存量正文随 body_max_chars 调小是否必须重截断；
只证明新正文遵循新值，不把该点标成通过。

## 给核心的交接

1. C50 只需先闭合 job 级取消传播，保留已收费/unknown，不修改 Provider 共享对象、
   不增加重试；两个失败用例均应转绿，runtime.stop/队列取消对照不得回归。
2. C22 在 cleanup/配置缩小路径补全场景裁剪，不用读 limit 掩盖落库超限。
3. F6 优先消除 `_prune_window` 每次提交的全库双扫描；
   可从只删超出阈值的行、减少重复窗口计数入手，保持提交原子性与 FULL/WAL。
   再评估将 Projector 四次状态读取合并为一次受锁快照读取以减少排队，
   但仍保留版本校验、事件/投影/幂等原子提交。上述是候选优化，不能保证达标。
4. 修复后用原 1 万事件、20 并发、满 1 万正文窗口复测，p95 门槛仍为 50ms。
   当前基准最后约 20% 因 50 个场景分配到 20 worker 不均降到 10 worker；
   F6 可先在测试端改为均衡分配并显式记录，不能减少负载来放宽验收。

只复跑新增三个失败用例（沿用上面的 `$T11_DEPS`）：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T11_DEPS" \
  .livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/budgets/run_evidence.py \
  -k 'active_caller_cancel or active_generation_caller_cancel or lower_scope_limit' \
  --output 插件/astrbot_plugin_livingemotion/tests/budgets/evidence/failures-rerun.json
```

未改产品代码、父规格或其他代理文件；无 Git 操作。
以上结论限定于所附快照与合成测试，不等待或代表后续核心修复。
