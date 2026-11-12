# F6 第三轮冻结交接（已实际修改，性能仍 FAIL）

**2026-11-05 22:35:47 UTC 产品与测试冻结，释放本轮五文件写权。
三处等价修改已落地，受影响592 passed / 15.62s，最终专项12 passed / 0.70s。
最新真实API成熟400/400成功，
0拒绝/重复，p50/p95/p99 = 45.323333 / 61.968958 / 71.754458ms，
wall 0.964753s、CPU 0.820744s，仍未达到50ms，不挑选更好短跑。**
本轮不再写产品、不重跑负载；父另派原完整 C51 独立者。
精确SHA与复跑命令见本文末尾“第三轮最终冻结与移交”。
本轮没有代理消息工具，本文顶部与当前对话作为即时交接，不声称已发送代理消息。

本轮获准独占 `storage/sqlite.py`、`runtime/projector.py`、`api.py`、
`tests/storage/test_sustained_latency.py` 与本文；其余 core/F7/原独立基准冻结只读。
最新独立 `local-state-final-20261105-02` **FAIL**：
10000/10000 accepted，0 拒绝/重复，p50/p95/p99 =
**45.081 / 56.895041 / 86.094875ms**，wall **23.831715s**，
CPU **20.709852s**；读 10000 全成功。唯一失败 commit p95 >50ms。
WAL/FULL、正文 10000/每 scope 200、双 trace/四状态版本及原 12 文件 hash 正确。

已读完整第二轮发现，原完整 C51 与窗口验收均已结束；进程检查无本地重测试。
专业 `performance-and-capacity`，目标真实 API commit p95 <=50ms，不降门槛。
只用真实 API 400 -> 9600 -> 400 合成临时库增长诊断，新增自身 CPU/调用者输出；
不重查已排除的 prune、线程派发或 scope 竞争，不采用无依据组提交。
不改 domain/guard/TTL/容量/持久性/Behavior 协议，无生产/网络/付费/Git 操作。
本轮后续实质发现即时更新于此；下方旧失败及冻结原文全部保留。

## 第三轮修前 Profile

父再次确认独立 C51/window 已结束、无其他重测试或产品写者。
同一真实 API 增长诊断成功 10400/10400、拒绝/重复 0：

| 阶段 | p50 ms | p95 ms | p99 ms | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: |
| cold 400 | 17.592959 | 19.585250 | 22.786000 | 0.360359 | 0.309737 |
| growth 9600 | 31.943292 | 54.361542 | 63.846666 | 18.781723 | 15.688282 |
| mature 400 | 46.490583 | **58.434125** | 59.430042 | 0.953679 | 0.809205 |

成熟 guard 均192、状态大小与前轮一致、四状态版本各10400、trace20800、
body10000/单scope200、FULL/WAL/integrity 正确，产品 SHA 与第二轮冻结一致。
附加40请求 profile：`_prepare_guard` 80次累计0.036s；
worker `_state_data` 33280次/0.019s、JSON encode 0.019s、
decode 0.011s、commit 0.016s。累计包含子调用，不相加或当未插桩时延。
下一窄假设：成熟输出可能仍与本次快照相同，重复编码可省；
必须用本次读取的原始 JSON 做严格等价判定，保留全量 domain 验证与每次 CAS/commit。
尚未实现或声称有收益，禁止跨请求缓存。

### 当前决策与剩余步骤

成熟真实 API 第201条投影的四状态与库内 JSON 全部逐字节相同，但安全的
“解析原始 JSON + 严格类型/有符号零递归比较”微实验更慢：
1000次四状态编码前/后对照0.650949/0.656298s，候选0.830704s。
**排除该方案，不向产品加入原文缓存或复用未经检查的状态**。
当前主 CPU 成本仍为完整 guard 校验，以及状态 JSON 转换/编码；
可修改范围内只优化后者与 Projector 重复转换，不复制或跳过 domain 实现。
已选精确内建标量叶字典免复制路径：1000次四状态编码
0.641088/0.634929s前后对照，候选0.575915s；整树预检0.617439s不选。
另复用本次 domain trace 已转换的 Bot/Relationship after 快照（深拷贝保持隔离），
将既有 Event/Context 局部 key 复用延伸到本次 API 提交，宿主回调仍接原 Event。
三者不改变领域/存储协议，保留自定义对象回退。
修前反例、最小实现、同命令增长、原子性/代际/取消回归及SHA冻结均已完成。
无组提交、无跨请求缓存；性能仍不闭合，最终原bench由父另派独立者。

### 第三轮已实现与修后结果

- 精确内建标量叶字典免转换复制；键类型不符/Enum/自定义容器仍回原转换。
  ASCII/排序/NaN拒绝/65536上限不变；无状态或JSON跨请求缓存。
- 内置API到提交阶段共用本次Event/Context key视图；原事件不变，
  宿主校验/remember/refinement和自定义Projector仍得到原对象；CAS重算读新状态。
- Projector写Bot/Relationship时深拷贝本次domain trace after；
  不重复dataclass转换，不复用可变输出树，不复制或跳过领域计算。

新反例修前：leaf复制、重复快照转换两项失败；key用例首跑因本轮新夹具
未带sadness只有三状态而失败（不是产品失败证据），修正夹具后真实命中
同请求key调用2次而非1次：1 failed / 0.10s。修后三项与原窄套件33项通过。

修后同命令增长，真实10400/10400成功、0拒绝/重复、每事件四状态：

| 阶段 | p50 ms | p95 ms | p99 ms | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: |
| cold 400 | 17.683667 | 19.351167 | 25.022625 | 0.360921 | 0.307843 |
| growth 9600 | 33.540708 | **56.126417** | 91.368625 | 19.699189 | 16.070889 |
| mature 400 | 45.323333 | **61.968958** | 71.754458 | 0.964753 | 0.820744 |

不能据较低的p50或微实验宣称实际尾延迟改善：本轮成熟p95与CPU未改善。
确定消除的冗余为40请求profile中stable_key **480->280次**、
Projector `to_dict` **160->80次**，worker不再重复计算scope key；
总调用730118->691118。`_state_data`自身0.019->0.018s（全路径），
worker0.018->0.016s，收益小于阶段运行波动。
成熟完整commit累计526.554627ms，worker CPU422.896290ms；
实际COMMIT累计229.314176ms、CPU125.916907ms，prune6.244080ms。
这是包含关系；不把差额归为纯fsync，不因尾部波动引入组提交。
最终（含独立40+40 profile）events=event_keys=10480、traces=20960、
四状态version各10480、states200、ledger300、body10000/每scope200；
guard192、原状态大小、WAL/FULL/integrity均不变，三个产品hash前后一致。
探测候选代码已从测试文件移除，保留全量数字与最终可复跑增长诊断。

### 剩余热点与必要授权（未实施）

当前边界不能合理绕过剩余领域热路径。40请求profile：
`domain/emotion.py:_prepare_guard` 80次/0.038s，
`_number` **46520次/0.019s**，`contracts.finite` **56080次/0.016s**；
其中46520次finite来自_number。JSON编码0.022s、解码0.015s仍不可忽略。
这些是插桩累计时间，不能视为可全部消除的下限或50ms不可达证明。

给父的最窄后续授权路径：**domain/emotion.py 的 `_number`**，
保持domain原算法，可测试精确内建float的严格快路径：
仍逐值执行isfinite与low/high检查，成功直接返回原float；
其余类型走原finite+float路径。它能省去热路径重复的bool/isinstance检查、
一层函数调用与float(float)转换，而不是减少seen/stimuli扫描或跳过验证。
必须保持bool拒绝、NaN/±Inf、上下界含等号、-0.0、超大int溢出、
float/int子类与异常消息/类型；需修前后反例、完整domain及受影响套件、
相同成熟增长与最终独立C51。**仅为具体候选，收益未测，不承诺达标**。
本轮没有该文件写权，未修改domain/contracts/F7；不扩范围自行实现。

---

# F6 第二轮持续满载修复（已冻结交接，性能仍未闭合）

冻结时间：**2026-11-05 22:16:52 UTC**。停止产品与测试写入，释放三个产品文件。
最新受影响套件 **569 passed / 14.91s**；最新修后成熟段
p95=**54.616417ms**，仍高于 50ms，**不宣称 C51 通过**。
排除已知重型测试争用后的上一同版本复核为 53.393292ms；
全部旧分布（含 68.927750/114.035792ms）原样保留。
COMMIT 占阶段墙钟约 19%，未证明其为主瓶颈，**未引入组提交**。
保留每事件 durable commit、取消 drain、clear 代际和 CAS 语义。
父已安排独立原完整 C51 独占测试 CPU；本实现者未运行或修改该长基准。
API 未修改；全部原门槛与 WAL/FULL 保留。

第二轮由父明确授权独占 `storage/sqlite.py`、`runtime/projector.py`、`api.py`；
仅新增 `tests/storage/test_sustained_latency.py` 并更新本文。新 core 不写这三个文件。
下方首轮冻结与全部旧失败记录保留为历史，**不能视为第二轮交付或 C51 通过**。
父 spec、独立 `tests/performance/`、`tests/budgets/` 和 verification 均未修改。

## 第二轮即时观测

最新独立原完整基准 `local-state-final-20261105-01` 为 **FAIL**：
10000/10000 真实 API 提交成功，p95=139.081ms，CPU=56.536418s，
wall=60.154448s，前后 hash 稳定。诊断 1000 事件只有 2000 次存储访问，
commit p50=1.927ms、p95=2.256875ms；prune 占提交累计约 0.68%。
测试内硬编码的旧 NOT IN 查询计划不是当前产品 SQL，未据此误判。

窄专科 `performance-and-capacity`，高置信度。目标保持真实 API 本地状态边界
p95 <=50ms；独立原 1 万预填、1 万测量、20 并发、满 10000 正文、256 字符、
WAL/FULL 不变。实现者只做增长诊断，最终长基准留独立者，不择优短跑放行。
不新增拒绝/降级/后台清理；容量余量、开放环极限和故障域恢复不在本次证明范围。

新增诊断全部通过真实 API 增长：50 scope / 原 worker 分桶 / 20 worker；
先 400 次，再 9600 次形成满库，再 400 次测量。临时库，无 SQL 预置。
下面是修复前一次运行的完整三段分布，单位 ms：

| 阶段 | accepted / 尝试 | API p50 | API p95 | API p99 | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cold，历史 0→8/场景 | 400/400 | 25.869375 | 51.245084 | 53.280708 | 0.611983 | 0.468380 |
| growth，历史 8→200/场景 | 9600/9600 | 71.615291 | 115.355792 | 134.173833 | 42.033690 | 37.000928 |
| mature，真实 1 万预填后 | 400/400 | 117.921458 | **134.132584** | 138.925208 | 2.444025 | 2.240387 |

全部 domain_applied，每事件 4 状态写入。测量后 events=event_keys=10400，
traces=20800，states=200，各类状态 version 总和 10400，ledger=300；
body_window=10000，单 scope 最大 200，integrity=ok、WAL、synchronous=2。
bot/relationship/night guard 从 8 增至 **192** 行；
bot 状态从 3313–3352 增至 **55551–56160** 字符，
relationship 从 2656–2687 增至 **54896–55497**，
night 从 1186–1201 增至 **16590–16890**。短 SQL probe 没有这种状态历史。

满历史段 800 次存储访问：锁+线程等待 p95=68.477041；
线程派发 p95=0.038791、线程结束后回环 p95=0.082750；
读取 p95=0.379833，commit p50=1.933375/p95=6.667167，
prune 累计 6.509753 / commit 966.917784，约 0.67%。
等待主要来自串行工作累积，不能把总锁等待直接认成线程切换开销。
原分桶每 scope 单生产者，scope 锁并非本次并行负载的竞争来源。

## 第二轮根因与进度

- [x] 读取 C51、新独立 FAIL、首轮记录。
- [x] 用真实 API 状态增长复现短/长差异。
- [x] 新回归修前失败：单事件幂等键计算从 **9 次增至 388 次**，
  `test_mature_projection_key_work_is_independent_of_history`，1 failed / 0.77s。
- [x] CPU profile 指向历史 guard 逐行重算同一事件 key，以及状态 JSON 的逐标量类型检查。
- [x] 首版等价修复、修后分布与 V06 联合回归；所有超标记录保留。
- [x] 排除已知争用因素复核，取消无充分依据的组提交方案。
- [x] 最后窄优化的分布、必要受影响套件、V06 联合回归；成熟 p95 仍超标。
- [x] 最终 SHA256 冻结，交回父安排独立原完整基准；不勾 C51。

首次双 cProfile 同时启用触发 Python 3.12
`ValueError: Another profiling tool is already active`，40 个附加插桩请求被 API 拒绝。
之前三段统计正常完成；该 40 次不计入成功分布，整条诊断退出码 1，未隐去。
插桩随后改为分段启用。另用单 scope 200 次真实 API 累积 guard 后，
各 40 次 CPU profile（不是延迟验收）确认：

- 幂等键 getter 15520 次 / 40 事件；guard 的逐行 any 累计 0.433s，
  key getter 累计 0.424s。此解释了 192+192 行的重复哈希放大。
- 存储 worker profile 中 `_write_states` 累计 0.217s / 40 事件，
  `to_dict` 累计 0.205s，142680 次（含递归），JSON dumps 仅 0.021s。
  时间有包含关系，不相加，不与未插桩 p95 比较。

当前最小修复：Projector 内创建调用局部 Event 视图，仍用原 getter 算 key，
仅复用该次不可变事件的结果；无跨请求/身份/授权/代际缓存，原 Event 不被修改。
存储状态序列化对精确内建 JSON 标量与容器走等价转换，
合同对象/Enum/自定义 Mapping 仍交原 `to_dict`；键转字符串、
sort_keys、ASCII、分隔符、NaN 拒绝与 65536 字符上限不变。
scope 锁、两次存储访问、CAS、generation、事务和裁剪均未改。

### V06 小范围接线

父追加授权修 `behavior_history`，core 负责 `BehaviorHistory`/Application 闸门。
原 proven 四用例修前实跑 **4 failed / 1.61s**：
cooldown 把真实 0/0/0 变成 2147483647；其余虚构 last_attempt_at=1799992799。
存储侧已改为原生计数加 legacy floor，`last_attempt_at` 仅原生真实尝试；
无尝试保持 None，不从 cooldown 反推。新增给 core 的合同：

| 字段 | 默认值 / 语义 |
| --- | --- |
| `reason_codes` | 空 tuple；非空即硬拒绝，原样携带明确 legacy 原因 |
| `cooldown_until` | None；原始绝对期限 |

上述采用 core 最新 `docs/INTEGRATION.md` 顶部冻结协议，
取代初步沟通的 `legacy_*` 提议，不新增第三个布尔字段。
解析异常保留原生真实计数/尝试，
历史旧约束解析失败时不能通过时间流逝放行；该接点现已撤下。
存储与 core 新端口联合回归：原 `test_migration_cli.py` 全部 10 项通过，
包括 proven 四限制到期/次日/新人类消息后恢复及 unresolved 不恢复；
测试断言未修改。仅实现者复验，不代替最终独立验收。

### 第二轮首版修后诊断（仍超标，完整保留）

同一命令、真实 API 三阶段、每事件 4 状态写入，全部成功、0 拒绝：

| 阶段 | 尝试数 | p50 ms | p95 ms | p99 ms | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cold | 400 | 22.676917 | 26.350458 | 26.862375 | 0.466908 | 0.415976 |
| growth | 9600 | 42.084417 | 61.062167 | 71.335833 | 23.399474 | 19.881555 |
| mature | 400 | 52.312167 | **68.927750** | 83.178916 | 1.162107 | 1.000399 |

满历史 800 次访问，scope 锁 busy=False 400/400，锁+线程等待 p95=40.387125ms；
线程派发/回环 p95=0.042250/0.090583ms，读取 p95=0.409709ms，
commit p50=1.233250/p95=5.302416ms。prune 累计 7.253159ms，
commit 累计 659.726401ms。状态大小、guard 192、正文计数均与修前相同。
两段 40 事件 cProfile 均正常成功，未混入上述延迟；最终事件 10480，
trace 20960、body 10000，各类 version 总和 10480，FULL/WAL/integrity 均正确。

存储 profile：to_dict 142680→6560 次，累计 0.205→0.012s；
新 `_state_data` 仍有 136520 次调用/0.026s，40 次 `_write_states` 0.050s。
幂等 key 的历史放大已消失；下一步仅继续做调用局部 Context key 复用与
普通标量内联，保留全部规则投影，避免每标量递归函数调用。
首版修后 hash：sqlite=`0f027622d8e8c7bcacb14d3120f6847eb1b5cd0681cc284c22ca16df06ec9890`，
projector=`ed91d95e28997e50c720347fc69fdd85598779e3416841080f1a062d38679368`；
这是中间结果，不是最终冻结。

### 第二次等价优化诊断（仍超标，完整保留）

调用局部 Context key 复用与标量内联后，窄回归 29 passed / 1.53s。
同一增长命令仍 10400/10400 成功、0 拒绝，scope 锁无竞争：

| 阶段 | 尝试数 | p50 ms | p95 ms | p99 ms | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cold | 400 | 22.297542 | 26.125250 | 28.245917 | 0.454924 | 0.401456 |
| growth | 9600 | 38.342667 | 59.905542 | 75.693750 | 21.938870 | 18.259657 |
| mature | 400 | 48.033667 | **114.035792** | 121.973792 | 1.167198 | 0.925340 |

满历史 commit p50=1.141792/p95=6.026833ms，累计 689.537416ms；
读取 p95=0.396458ms，锁+线程等待 p95=58.776084ms；
派发/回环 p95=0.041875/0.097916ms。状态字符数、192 guard、计数不变。
不能用降低的 p50 覆盖较高尾延迟；不重跑同版本择优。
40 次 worker profile `_state_data` 32360 次/0.020s，
`_write_states` 0.043s，commit 0.017s；完整增长时仍有周期写入尾部。
计划有界组提交以分摊 FULL commit，不更改 WAL/FULL/检查点参数：
各事件 savepoint 隔离，外层 durable COMMIT 成功才完成请求；
必须验证部分失败、外层提交失败、取消/close 和 clear/CAS。

本轮源码：sqlite=`38df42ce376a25772f43ef20692e6333255bd4635fd44e13d3f9ac35605f189e`，
projector=`310621e8d71a27589f9a33f815299b28fc8d40198632cb57156647e43464af8f`。
另有 JSON 转换微实验，1000 次单状态编码，现实现 0.227s、
copy-on-convert 0.269s，后者更慢，未采用；不是 API 延迟验收。

### 排除已知重型测试争用后的同版本复核

父明确指出上次 114.035792ms 可能与 host C30/四插件两轮并行，
并确认 host/预算/components 重型任务均已停止。本次是预先声明的环境因素复核，
不是择优刷绿；三个产品文件 hash 与上次一致。诊断仅新增
`db.commit()` 与操作线程 CPU 计时，仍为原三阶段，10400/10400 成功、
0 拒绝、每事件四状态；两个附加 profile 各 40 次成功，不混入延迟分布。
运行前 CPU 列表未见其他测试进程；编辑器 renderer 约一个核心，故不宣称整机零负载。

| 阶段 | 尝试数 | p50 ms | p95 ms | p99 ms | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cold | 400 | 19.442375 | 22.667542 | 23.154167 | 0.432394 | 0.358019 |
| growth | 9600 | 37.881417 | 68.452209 | 84.964875 | 22.231298 | 18.649922 |
| mature | 400 | 44.268125 | **53.393292** | 62.400417 | 0.949710 | 0.843814 |

成熟段锁+线程等待 p95=30.711708ms，派发/回环 p95=0.031583/0.072125ms，
scope 锁无竞争。读取 p95=0.356584ms；完整提交 p50=1.049541、
p95=1.176167、p99=9.080292ms，累计 519.871459ms。
实际 `db.commit()` p50=0.204417、p95=0.289834、p99=8.246792ms，
累计墙钟 181.947739ms / 线程 CPU 115.645833ms；
prune 累计 5.777091ms。正文、guard、版本及完整性与先前一致。

进程 CPU/墙钟约 88.8%；实际 COMMIT 墙钟占阶段约 19.2%，
其非 CPU 时间差约 66.302ms，占阶段约 7.0%。COMMIT 包含写入、
WAL 同步和自动检查点；没有系统调用级证据，**不把 19.2% 或 7.0% 称为纯 fsync 比例**。
后续独立阶段仍可能遇到周期长提交，这里不能证明持续满载达标。
当前证据不支持引入组提交，取消该实现计划，保留现有每事件原子事务与取消/clear/CAS。
剩余 profile 仍见 guard 验证及状态/合同转换；只继续考虑小范围等价计算优化。

### 最后窄优化与最终自验

已有 scope 的 `_check_generation` 原来仍重算 key、编码 context 并做
`INSERT OR IGNORE`。改为在既有 `BEGIN IMMEDIATE` 内读取原生 generation，
仅无行时创建脱路由 metadata；不新增缓存或持久计数，不更新已有 scope metadata。
事件 metadata/trace 也使用与 `canonical_json` 等价的转换快路径；
失败回滚、大小/NaN 限制、排序、ASCII 和合同类型回退不变。

新增 `test_existing_scope_does_not_encode_ignored_context` 修前
**1 failed / 0.10s**，修后存储专项 **50 passed / 1.54s**。
它同时确认首次 metadata 去除 route，后续 route 变化不会覆写原有 scope metadata。
原成长幂等 key 9→388 次反例、canonical bytes、混合键/Enum/dataclass、
非法 payload 原子回滚及未解析 legacy 历史回归均保留。

最后同命令真实 API 三阶段，10400/10400 成功、0 拒绝、四状态完整投影；
两个附加 40 事件 profile 成功，不计入以下分布：

| 阶段 | 尝试数 | p50 ms | p95 ms | p99 ms | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cold | 400 | 17.015584 | 18.998209 | 22.469667 | 0.357477 | 0.305936 |
| growth | 9600 | 33.456333 | 51.815334 | 59.416834 | 19.319985 | 16.068220 |
| mature | 400 | 45.916208 | **54.616417** | 54.772416 | 0.965604 | 0.863565 |

成熟段锁+线程等待 p95=31.956292ms，派发/回环 p95=0.037167/0.079125ms；
scope 锁无竞争，仍每事件两次存储访问。读取 p95=0.399208ms；
完整提交 p50=1.038959、p95=1.276000、p99=9.783667ms，
累计 514.274528ms。实际 COMMIT p50=0.211167、p95=0.309875、
p99=9.059958ms，累计墙钟 183.734077ms / 线程 CPU 122.833915ms；
prune 累计 6.095541ms。进程 CPU/墙钟约 89.4%，COMMIT 墙钟约占 19.0%。
相对上一复核，增长 CPU 减少，成熟分布未闭合；不把插桩差异或增长段改善解释为通过。

最终 events=event_keys=10480、双 trace 合计 20960、states=200、
各类 version 总和 10480、ledger=300；正文 10000、单 scope 最大 200，
bot/relationship/night guard 均 192，状态字符数与各轮相同，
integrity=ok、WAL、synchronous=2，三个产品文件前后 SHA256 一致。
40 事件 worker profile 的 `to_dict` 6560→640 次，
`_check_generation` 累计约 0.004→0.001s；仍有状态转换、JSON 编解码、
guard 数值验证和周期 COMMIT 尾部。累计时间包含子调用，不相加当 API 总耗时。

最后另做 200 条真实 API 单场景成熟数据上的 JSON 微实验，各 1000 次四状态编码：
现实现前置对照 0.701206s、容器优先 0.639863s、
容器优先+frozenset 0.622413s、现实现后置对照 0.646305s。
收益相对后置对照仅约 3.7%，有运行波动，**未采用**，不作为 API 延迟证据。
至此不继续刷短样本或扩展事务语义。

最终受影响套件命令：

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv-ci/bin/python -m pytest \
  tests/storage/test_sustained_latency.py tests/storage/test_sqlite.py \
  tests/storage/performance_f6.py tests/domain tests/integration tests/migration \
  tests/verification/test_migration_cli.py tests/behavior tests/runtime tests/night \
  tests/experience tests/identity tests/budgets/test_window_budgets.py \
  -q --tb=short -p no:cacheprovider
```

结果 **569 passed / 14.91s**，包含原 V06 全 10 项、F3 TTL/旧约束、
F5/F7 接点、CAS/双连接竞争、clear/排队旧代际、取消后 worker drain、
event/trace/ledger 失败无半套、F9 静默 scope 窗口收缩。
不是普通全套、原完整预算或 C51 独立验收；未改以上既有测试断言。

### 第二轮最终冻结

| 文件 | SHA256 |
| --- | --- |
| storage/sqlite.py | `b83c7c8d4a982e107c5024c8a18c3960f07ff0b5b51ac407b17a28c377954688` |
| runtime/projector.py | `310621e8d71a27589f9a33f815299b28fc8d40198632cb57156647e43464af8f` |
| api.py（本轮未改） | `a54e017aba4d6330da2980b8b7bf7fa7c49728f76c1c542d360ff36f8a867b41` |
| tests/storage/test_sustained_latency.py | `9dd74dc4bb93aee0abf8f30b23111224faab75bd2dbbb1cc8f0636dde0259f82` |

未操作 Git、父 spec、独立 performance/budgets/verification 文件，
没有真实网络、模型或消息。只有合成临时库；无运行数据留存。
自验性能仍失败，交回时不下调 50ms、不把短诊断当验收，
不要求独立者重跑择优。后续原完整基准按父既定独占安排执行，
仍须保留 10000 真实 API 预填+10000 测量、20 并发、50 scope、
10000 正文/256 字符和四状态投影，核对开始/结束源码 hash。
如失败，当前定位证据供下一步决策；不能据本文解除 C51 阻塞。

复现命令（从插件根目录，无个人绝对路径）：

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv-ci/bin/python -m pytest \
  tests/storage/test_sustained_latency.py -q --tb=short -p no:cacheprovider
env PYTHONDONTWRITEBYTECODE=1 \
  ../../.livingemotion-host-t1/venv/bin/python tests/storage/test_sustained_latency.py
```

---

# 首轮 F6 存储性能修复交接（历史原文）

日期：2026-11-05。角色：实现者，不负责独立验收。
状态：F6/F9 实现与窄回归完成，三个产品文件冻结并释放；C51 完整独立基准待验。

## 文件归属

当前会话没有 agent 消息接口，未声称已发送消息。
接管依据是核心 `docs/INTEGRATION.md` 的明确冻结声明：
21:21:22 UTC 移交 sqlite.py / projector.py，21:29:17 UTC 移交 api.py。
F6 现在独占 `storage/sqlite.py`、`runtime/projector.py`、`api.py`；
核心继续 application/models/console。请父代理转达此接管记录。
不改父规格、独立验证、tests/performance、tests/budgets 或 verification。
父随后明确确认接管，并要求 F9 原反例复跑后冻结释放。
下方最终哈希为交付版本，本专项不再写三个产品文件。

接管前 SHA256：

| 文件 | SHA256 |
| --- | --- |
| storage/sqlite.py | 7be38808e663de7f2022c3375469fd5253f6df6e2814fc4cb5bf830794cfd031 |
| runtime/projector.py | 0cbdb1da2b1a5bb61860544e386ed3ce187dd7525e2fd5a85d55226d5c9c7969 |
| api.py | b1c6089040ad94c7d845afa67a91e9d3d4b4c25fcf531a3bfe70a4ee2e0e21a1 |

## 原失败

独立证据来自 `docs/verification-performance.md`，不是本专项重测：
50 scope / 20 并发 / 满 10000 正文窗口 / 10000 次真实 API 提交，
p95=221.628ms，目标仍为 <=50ms。事务裁剪约占 53.5%。
单 scope 附加 200 次只有 30 accepted、170 version_conflict；
拒绝不能计入成功延迟。旧结果与最终冻结源码不同，必须保留并复验。

## 数据库变更计划

主要专项 `database-operations`，置信度高；产物为窄热路径修复与回归证据。
不增加 schema、不迁移业务数据、不更改 F3 采用约束或 F5 恢复语义。

| 阶段 | 变更/确认点 | 停止及回退检查 |
| --- | --- | --- |
| 定位 | 四次独立状态读、generation 读、提交共六次串行线程访问 | 只读源码及旧独立证据 |
| 回归 | 热点成功数、事件/trace/幂等一致性、清除竞争、裁剪边界 | 小规模临时合成库，失败保留 |
| 实现 | 单语句读取 generation 与四类状态；按 scope 串行投影提交；索引阈值裁剪 | 不允许降低 WAL/FULL、CAS 或窗口上限 |
| 自测 | storage/domain/integration 与短诊断，记录真实成功和拒绝 | 不运行原一万事件基准，不改验证门槛 |
| 冻结 | 记录三个文件 SHA256，交父指定的新独立验证者；旧失败证据仍保留 | 独立完整基准前仍待验 |

| 风险 | 控制 |
| --- | --- |
| 锁与尾延迟 | 保留单连接线程外执行；批量快照缩短锁队列；scope 锁只串行同场景，跨账号共享 Bot/night 也互斥 |
| 清除与 CAS | generation 在排队前取得，不能在冲突重试时刷新到清除后代际；状态和快照代际必须一致；事务内仍检查 generation/version |
| 写放大与查询计划 | 使用现有主键、body_scope_seq、body_retention；scope 找第 N+1 新行，全库计溢出量找最老溢出阈值，DELETE 范围查找，无 NOT IN 全表成员测试 |
| 当时 F3/F5 接口 | 当时保留旧约束查询、历史清理、refine_emotion、current_affect、application.current_relationship 接点；旧约束接点现已撤下 |
| 连接/故障转移/副本 | 单机单连接，无网络、副本或控制面；跨连接竞争仍由事务/CAS 防护，不宣称跨进程公平调度 |
| 计数空间 | 沿用 INTEGER seq/version/generation；不新增持久计数器或依赖 seq 连续，清除/TTL/空正文造成的空洞必须测试 |
| 恢复 | schema 2 不变；源码可回退且原始库仍可读，不回滚业务数据；既有 WAL 备份/原子回滚测试复跑 |

兼容矩阵：当前 schema 2 -> schema 2，无 DDL/backfill/复制；旧新读写路径都使用
同一 SQLiteStore、本机同一文件权限，不新增对象/grant。导入器的精确 schema 指纹不变。
全部变更只在合成临时库执行，生产迁移/清理/授权检查不适用，也未作生产可用性承诺。
不新增后台维护或延迟清理，裁剪仍在原事件事务中完成，窗口不能瞬时超限后靠后台补救。

## 进度

- [x] 读取规格、核心与迁移交接、原独立失败。
- [x] 获得三个产品文件明确冻结移交。
- [x] 新增专项回归并记录修复前失败。
- [x] 完成产品修复，包括 F9 冷 scope 清理。
- [x] 必要回归及短诊断，F9 原反例通过。
- [x] 冻结文件/hash，交父指定的新独立验证者；释放本专项。
- [ ] 新独立验证者执行原完整 benchmark；本实现者不勾 C51。

本文件不替代独立验证文档，不修改父复选框。所有测试无网络、真实模型或消息发送。

修复前显式运行 `tests/storage/performance_f6.py`：5 failed / 6 passed，1.47s。
失败为四读而非一次快照、热点 30 accepted/170 version_conflict、
双 API 门面 3 accepted/17 rejected、同 scope 不同账号 3 accepted/17 rejected、
重开调小窗口后冷 scope 仍各保留 4 条而非 2 条。
没有修改旧独立测试或将失败改为 xfail。

## 最终修复机制

1. `SQLiteStore.read_projection(context)` 用一条 SQL 读取 generation 和精确四类
   scene/account 状态，避免四次线程/锁访问及拼接不一致快照。无账号只读 bot/night。
   `Projection.generation` 为向后兼容新增字段，不改 F3 或 schema 2。
2. API 使用同 store 共享的完整 scope 锁，两个门面/同场景不同账号也互斥；
   不同 scope 不共用此锁。弱引用只保留活跃锁，取消会释放，锁交接中的等待者计入 busy。
   无竞争的内置 Projector 只需两次存储访问（快照、提交）；排队/旧自定义投影器先取
   generation，再等锁。重算不刷新该 token；清除后在途/排队请求都不能复活内容。
   自定义 tuple 投影回调、三次 CAS 重算与事务内版本/代际校验保留。
3. 每条提交裁剪 TTL、当前 scope 和全库上限；采用范围 DELETE，不再建立 NOT IN
   全窗口集合。全库 COUNT 不依赖连续 seq，正确处理清除、空正文和 TTL 造成的空洞。
   只有 cleanup 枚举全部超限 scope，F9 无新消息的冷 scope 也收缩；未把全场景扫描
   加入每条事件热路径。
4. 每次提交复用已计算的 scope_key/event_key；每次状态写批次复用 scope_key。
   不缓存状态/身份/代际，不绕过 canonical_json 或 CAS，不修改领域计算。

F7 固定协议已读取：保留
`await application.current_relationship(scope, record=record)`，
None 仍映射 unavailable/context_changed。
`read_relationship_projection` 接线由核心完成；现有 get_state/get_generation/
list_contexts/relationship_ledger 未改签名。未重复实现 F3 或 F7，未处理另派的 C50 取消传播。

## 实测结果

插件根目录窄回归命令：

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/storage/performance_f6.py tests/storage tests/domain tests/integration \
  tests/contracts tests/migration -q --tb=short -o faulthandler_timeout=15
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/budgets/test_window_budgets.py::test_lower_scope_limit_cleanup_prunes_inactive_scopes \
  -q --tb=short -p no:cacheprovider
```

最终分别 **168 passed / 5.18s**、**1 passed / 0.06s**，Python 3.11.9。
既有环境缺 pytest-timeout，均有 1 条 unknown timeout 配置 warning，未改配置。
18 项本专项回归需显式指定 performance_f6.py，文件前缀不属于 pytest 默认发现规则。
覆盖 200/200 热点成功（旧 30/200）、双 API 门面、同 scope 不同账号、
清除活动/排队投影、取消及弱引用锁回收、锁交接、跨 scope 不阻塞、CAS 重算、
事件/双 trace/幂等/状态原子性、旧 tuple 回调、缺账号隔离、seq 空洞及裁剪查询计划。
F9 原独立测试未修改；本结果属于实现者复验，不代替独立验收。

短诊断命令：

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  ../../.livingemotion-host-t1/venv/bin/python \
  tests/storage/performance_probe.py
```

Python 3.12.16 / SQLite 3.53.1，同机器；临时库，单事务 SQL 合成 10000 条 body，
50 scope，每 scope 200 条、正文 256 字符；再 50 次真实 API 预热，
20 worker / 400 次真实 API -> Projector -> SQLite 测量。SQL 夹具没有领域预投影，
因此**不是原 10000 次真实预填充 + 10000 次测量的完整基准**。
不请求模型、不启动后台 worker、不发送；审计钩子禁止网络和子进程。

| 阶段 | 成功数 | API p95 ms | 说明 |
| --- | --- | --- | --- |
| 原独立基准 | 10000 | 221.628 | 旧失败，保持原证据 |
| 首版批量读/裁剪/串行 | 400/400 | 46.691 | 1200 次存储访问 |
| 去除无竞争重复代际读 | 400/400 | 60.408 | 800 次访问，仍有波动，不隐藏超标 |
| cProfile 定位 | 400/400 | 93.581 | 插桩有开销，不与正常时延比较；重复 stable_key/to_dict 热点 |
| 提交键复用 | 400/400 | 28.797 | 旧中间源码 |
| 最终锁交接保护版本 | 400/400 | **40.406** | 最终哈希如下；仍仅短诊断 |

最终 p50=26.342ms、p99=47.675ms，测量段 0.571s；
transaction p95=0.737ms，prune p95=0.018ms，占事务累计时间约 1.90%。
800 次存储访问，400 domain_applied，0 duplicate / rejected。
最终 events=event_keys=10450，双 trace 各 450，四类状态各自 version 总和 450；
body=10000、每 scope 最大 200，integrity_check=ok、WAL、synchronous=2。
这些计数包括 10000 SQL 夹具和 50 预热，绝不冒充 10450 次真实投影。

Ruff：projector 和两个新增测试文件通过；全三个产品文件加新增测试检查仍报告
9 项既有 BLE001/SIM102/SIM118/TRY004（API 异常边界和原存储非热路径）。
未为了本专项消警而改 F3、F7 或误将 sqlite3.Row.keys() 当普通 dict 修复。
不宣称全库 lint 通过。

## 冻结与移交

冻结日 2026-11-05，最终窄回归、短诊断和 F9 原反例对应以下 SHA256：

| 文件 | 最终 SHA256 |
| --- | --- |
| storage/sqlite.py | 92d218a4a33d82b586a2a4c1a638eb1bc18dbd72d27d48fcc64a6fedcd33e8f7 |
| runtime/projector.py | 64c51c315d508e5b1d29d8636002142a466161e2c11dac9122871a02f86662a8 |
| api.py | a54e017aba4d6330da2980b8b7bf7fa7c49728f76c1c542d360ff36f8a867b41 |
| tests/storage/performance_f6.py | 33452716af3cfc409ebfefab715a27fd8aaf326d99b1ff3b6cf5c6bb80e769ba |
| tests/storage/performance_probe.py | d677d6b56bdcdb7c84b05c52b50a590602f295f4ca0c40231934def618bd9e52 |
| storage/schema.py（未修改） | 09e48310efbaf48f5d21d4d16579ba58f32950edf52d6c13f0421d321a751de0 |

请父转交新独立验证者：先核对产品哈希，再按原 `tests/performance/bench_local_state.py`
完整命令执行，保持 10000 样本、20 并发、满正文窗口、50ms 门槛、全部成功计数及 FULL。
同时独立复验 F9 原反例。禁止覆盖旧失败证据，输出新的证据文件。
如核心后续改动上述三个文件，旧哈希即不再代表最终验收版本，须重新冻结。
本专项无 Git/生产/网络/真实模型/消息操作，未改父规格或独立验证文件；现在结束释放。

---

## 第三轮最终冻结与移交

本节是**第三轮最终**记录，优先于上方第一、二轮历史冻结。
产品/测试冻结时间：**2026-11-05 22:35:47 UTC**。
五个授权文件已结束写入，释放给父；没有活动测试、后台诊断或待结束命令。

| 文件 | SHA256 |
| --- | --- |
| storage/sqlite.py | `599cec9c29caa8c69f84bb27ed88c027a7fdf548ea11442153021d49199eb116` |
| runtime/projector.py | `cb1051be1814573a1b24f95cf1f5511aa2c48cf82adf0eaadbfd400045a24c79` |
| api.py | `a88ef0fe7af62428710c4cd7a8f587e070e6b6ad2a6660348d7238986c11e9c9` |
| tests/storage/test_sustained_latency.py | `6576838f1610a9bd88aebcf7b11f45e592c969e30b62b87bf090b24af046a715` |

三个产品hash与修后增长诊断完全相同。专项测试随后增加宿主原对象/自定义
Projector/Event子类兼容反例、补充自定义字符串键与有符号零样本，并移除未采用
微实验代码；最后仅删除一行未使用import，专项12项再次通过。
原有测试与断言没有改动，未调整失败计数、50ms门槛或任何负载参数。
已只读复核冻结的config/contracts/background/models/schema/domain三文件、
原bench与window测试SHA均与独立02证据一致。

受影响复跑命令（插件根目录）：

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv-ci/bin/python -m pytest \
  tests/storage/test_sustained_latency.py tests/storage/test_sqlite.py \
  tests/storage/performance_f6.py tests/domain tests/contracts tests/integration \
  tests/migration tests/verification/test_migration_cli.py tests/behavior \
  tests/runtime tests/night tests/experience tests/identity \
  tests/budgets/test_window_budgets.py -q --tb=short -p no:cacheprovider
```

**592 passed / 15.62s**：含CAS/双连接、clear活动与排队代际、取消worker drain、
事件/trace/ledger故障无半套、JSON规范/非法值回滚、F9窗口与V06原10项。
未改Behavior真实计数/绝对cooldown协议，F7身份与后台文件未动。
去除测试未使用import后仅复跑下面12项，**12 passed / 0.70s**，不重复负载：

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv-ci/bin/python -m pytest \
  tests/storage/test_sustained_latency.py -q --tb=short -p no:cacheprovider
```

本轮增长诊断唯一修后命令：

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  ../../.livingemotion-host-t1/venv/bin/python tests/storage/test_sustained_latency.py
```

真实API 400->9600->400，50scope/20worker/原分桶/256字符；
**10400/10400 accepted，0拒绝/重复，每事件四状态**。
成熟400样本p50/p95/p99 =
**45.323333 / 61.968958 / 71.754458ms**，
wall **0.964753s**、CPU **0.820744s**；前两段完整数字保留在顶部。
两段附加40次profile均全部成功，不混入延迟分布。
最终10480事件/幂等键、20960双trace、四类version各10480、300ledger、
10000正文/每scope最大200、guard192、WAL/FULL(2)/integrity=ok。

未解决项：**提交尾延迟仍超50ms**；总CPU/尾延迟未有稳定改善，
只证实重复key/快照转换减少与叶转换微实验收益。
最窄后续候选是上文`domain/emotion.py:_number`精确内建float严格快路径，
需要父另行授权领域文件，不代表已证明可消除全部0.019s或确保C51通过。
本次证据不足以宣称不可突破的性能下限；不把候选写进Projector、跳过guard，
不放宽门槛、不重复择优，也不把592功能通过或短诊断冒充完整C51。

完整C51留父安排独立原`tests/performance/bench_local_state.py`，实现者未运行它。
静态Ruff未运行：现成`.venv`/`.venv-ci`及PATH无ruff，未安装依赖；
不宣称全库lint通过。无Git/生产/付费/网络操作，所有库均合成临时库。
