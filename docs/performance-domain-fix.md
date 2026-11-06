# F6 第四轮领域数值热路径修复

**最终冻结：2026-11-05 22:41:45 UTC（产品/测试最终hash复核时点）。
本文为最终交接记录；已释放本轮写权与重测试CPU，停止全部后续写入及重测试。**

状态：最小等价修改已落地，修后合计 **1155 passed**，唯一一次增长诊断完成，
**10400/10400 accepted、0拒绝/重复**。成熟400的 p50/p95/p99 =
**37.766750 / 49.423083 / 51.706542ms**，wall **0.841573s**、CPU **0.735682s**。
相比第三轮成熟p95=61.968958ms有所下降，但距50ms仅 **0.576917ms（1.15%）**，
**余量不足，不能宣称完整C51通过或稳定达标**。没有同版本重跑择优。
profile证实 `_number` 仍46520次，`math.isfinite` 仍56080次，
仅 `finite` 调用56080 -> 9560；guard仍192，未跳过逐值校验。
性能测试与最终SHA核对均已结束，无活动测试或后台诊断。仅本文件顶部与当前对话交接，
没有代理消息接口，不声称已发送父消息。完整C51仍以旧FAIL为准，留父安排独立者。

## 范围与假设

- 已读 staff-engineer-mode 主技能及 performance-and-capacity 专项；高置信度。
- 用户边界：真实 API -> Projector -> SQLite，原完整 C51 p95 <=50ms。
  旧完整 10000/10000 accepted 的 p95=56.895041ms；第三轮成熟400的
  p95=61.968958ms、wall=0.964753s、CPU=0.820744s，旧记录全部只读保留。
- 第三轮40请求 profile：`_prepare_guard` 80次/0.038s，
  `_number` 46520次/0.019s，`finite` 56080次/0.016s，其中46520次来自 `_number`。
  累计时间含子调用，不相加，也不承诺可全部消除。
- 唯一产品写权 `domain/emotion.py`；新增
  `tests/domain/test_numeric_fast_path.py` 与本文。contracts、其他领域文件、
  storage/API/Projector/F7/父spec/原benchmark及旧文档全部冻结只读。
- 候选：在原异常包装内对精确内置 float 逐值执行 `math.isfinite`、low/high，
  成功返回原对象；其他类型保持 `finite` 加 `float`。不降低guard192，不改规则、
  TTL、刺激预算、关系或trace算法，不做跨请求缓存，不复制领域逻辑到Projector。
- 原产品 `domain/emotion.py` SHA256：
  `98aed32ba568119bca2eb3cbd53195c747177c28d0e8b5dd88f370b2ce5cea58`。

## 验证口径

先执行新边界回归，保留修前调用冗余反例；最小产品修改后执行受影响套件。
只执行一次原 `tests/storage/test_sustained_latency.py` 增长诊断：
合成临时SQLite、真实API 400 -> 9600 -> 400、50scope/20worker、
满10000正文/每scope200/256字符，另带原入口自身的40+40请求profile。
报告全部三段 p50/p95/p99、wall/CPU、成功/拒绝及状态/trace/正文/FULL/integrity。
该诊断有既有分段计时插桩，不能替代原完整C51；不新增大baseline或同版本择优跑。

余量比例未规定，目标争取明显低于50ms，不以49.9ms贴线声称充分。
USE沿用CPU、锁与线程等待、线程派发/回环和commit分段；无新增队列深度/队龄指标。
准入、优先级、背压保持原样，不引入拒绝换快；父确认当前唯一重测试使用者。
无后台维护负载或容量变更；开放环极限、故障域、恢复时长与成本不在本轮证明范围。
只用合成材料，无真实模型、外发、生产、Git、部署或依赖安装。

## 进度

- [x] 读取第三轮顶部/末尾冻结、独立最终FAIL、增长入口与原数值语义。
- [x] 新增差分兼容与全192行guard校验测试。
- [x] 修前回归与最小产品修改。
- [x] 修后边界及受影响套件。
- [x] 唯一一次同命令增长诊断，记录所有结果。
- [x] SHA核对与最终UTC冻结，停止全部写入及重测试。

## 修改与功能回归

产品仅增加 `import math` 与 `_number` 的7行精确float分支。
finite/range检查位于原try内，比较顺序和错误文本与contracts一致，
其他类型的原始路径及try外 `float(value)` 不动；没有改guard循环或算法。
候选SHA256：`f79c1ef6dac5a50d4fdaf72ba8d00e40156abbe070007a91c80e4ad8d6876fc0`。

新增563项：数值/类型/上下界组合差分、1024个固定种子IEEE754位模式、
自定义上下界异常包装、float/int子类转换顺序和异常链、精确float减少派发反例、
guard首尾非法值、过期历史仍校验及满192条逐值检查。
满guard调用数保持 last_event_at=1、seen.at=192、
stimulus.at=192、stimulus.amount=192；输入不变、输出拷贝，
同一runtime下一次被改成NaN必须拒绝，无跨请求缓存。

实际修前命令（插件根目录）：

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv-ci/bin/python -m pytest \
  tests/domain/test_numeric_fast_path.py -q --tb=short -p no:cacheprovider
```

修后实际命令与结果：

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv-ci/bin/python -m pytest \
  tests/domain/test_numeric_fast_path.py \
  tests/storage/test_sustained_latency.py tests/storage/test_sqlite.py \
  tests/storage/performance_f6.py tests/domain tests/contracts tests/integration \
  tests/migration tests/verification/test_migration_cli.py tests/behavior \
  tests/runtime tests/night tests/experience tests/identity \
  tests/budgets/test_window_budgets.py -q --tb=short -p no:cacheprovider
env PYTHONDONTWRITEBYTECODE=1 .venv-ci/bin/python -m pytest \
  tests/domain/test_emotion.py tests/domain/test_persistence_contract.py \
  -q --tb=short -p no:cacheprovider
```

第一条1117 passed / 14.26s。只读collect-only核对发现显式新文件与目录重叠，
旧domain两文件38项未收集；第二条专门补足38 passed / 0.63s。
合计1155项，覆盖第三轮592项与新增563项，不隐瞒收集缺口或重复计数。
包括CAS/双连接、clear代际、取消drain、事务失败无半套、F9物理窗口及V06。
未重跑完整C51或以功能通过代表性能达标。

## 唯一一次增长诊断

原命令未修改，exit 0；没有修前大baseline，直接引用第三轮冻结失败。
该入口对计数/成功及其原三个产品hash做断言，不以50ms为退出门禁。

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  ../../.livingemotion-host-t1/venv/bin/python tests/storage/test_sustained_latency.py
```

| 阶段 | 成功/尝试 | 拒绝/重复 | p50 ms | p95 ms | p99 ms | wall s | CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cold | 400/400 | 0/0 | 17.981625 | 19.956208 | 21.491542 | 0.366248 | 0.318303 |
| growth | 9600/9600 | 0/0 | 31.898750 | 49.701583 | 58.503084 | 17.986382 | 14.981999 |
| mature | 400/400 | 0/0 | 37.766750 | 49.423083 | 51.706542 | 0.841573 | 0.735682 |

每条均 `accepted:committed` 且 `domain_applied`，三段四状态写入数分别
1600/38400/1600；20worker沿用原分桶，尾部降并发限制不改。
原入口的40+40 profile均通过相同成功断言，未混入以上分布。
临时库由真实API逐条建立，未用SQL预置领域历史。

| 核验 | cold后 | growth后 | mature后 | 原40+40 profile后 |
| --- | ---: | ---: | ---: | ---: |
| events/event_keys（各） | 400 | 10000 | 10400 | 10480 |
| event_traces总数 | 800 | 20000 | 20800 | 20960 |
| 四类状态version和（各） | 400 | 10000 | 10400 | 10480 |
| states | 200 | 200 | 200 | 200 |
| relationship_ledger | 300 | 300 | 300 | 300 |
| body_window/单scope最大 | 400/8 | 10000/200 | 10000/200 | 10000/200 |
| bot/relationship/night guard（各） | 8 | 192 | 192 | 192 |

全部检查点均 WAL、synchronous=FULL(2)、integrity_check=ok。
原入口核验trace总数，不额外查询每种trace计数；双trace行为由受影响回归覆盖，
不把总数检查写成逐种实测。正文256字符来自未改的合成事件构造，
入口未单独查询正文字符总数，不冒称新增长度审计。
成熟状态字符范围与第三轮完全一致：
bot 55551–56160、relationship 54896–55497、night 16590–16890、
observation 739–753；observation没有guard历史。

### 调用与分段证据

40请求profile（累计包含子调用，非未插桩端到端耗时）：

| 热点 | 第三轮冻结 | 本轮 |
| --- | --- | --- |
| `_prepare_guard` | 80次/0.038s | 80次/0.022s |
| `_number` | 46520次/0.019s | 46520次/0.006s |
| `contracts.finite` | 56080次/0.016s | 9560次/0.003s |
| `math.isfinite` | 原逐值路径 | 56080次，其中46520来自_number |
| 全路径profile调用数 | 691118 | 551558 |

减少139560次调用，精确等于46520次finite派发及其两次isinstance检查；
仍逐值检查finite/range，guard调用数、历史长度和状态大小均不减少。
本轮worker profile共71480次调用：JSON encode 0.019s、decode约0.011s、
`_state_data` 0.016s、实际commit 0.018s。不据此越权改storage/contracts。

成熟400分段（耗时单位ms，原入口插桩）：

| 分段 | n | p50 | p95 | p99 | 累计 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 锁+线程等待 | 800 | 17.527125 | 28.783958 | 30.255125 | 14298.820320 |
| 线程派发 | 800 | 0.026875 | 0.032583 | 0.037125 | 22.463639 |
| 线程后回环 | 800 | 0.061416 | 0.070750 | 0.077833 | 49.506561 |
| read wall | 400 | 0.299334 | 0.349125 | 0.380875 | 127.230793 |
| commit操作wall | 400 | 0.885625 | 1.080083 | 9.814375 | 455.133842 |
| commit操作CPU | 400 | 0.861042 | 1.039042 | 4.579583 | 389.182709 |
| 实际COMMIT wall | 400 | 0.200417 | 0.276375 | 9.098500 | 177.164951 |
| 实际COMMIT CPU | 400 | 0.175583 | 0.246083 | 3.882041 | 111.414419 |
| prune | 400 | 0.012833 | 0.017167 | 0.019500 | 5.403743 |

三段scope锁busy均False。等待是并发累积，不当作阶段wall；
prune/实际COMMIT已包含于commit操作，不相加、不把wall-CPU称为纯fsync。
CPU下降及调用消除支持候选有效，但单次尾延迟也含I/O/调度波动，
不能把全部下降归因于8行修改。已排除方向不重做，不引入组提交。

## 失败与限制

- 修前563项中562通过，1项调用冗余反例按预期失败；修后该项通过。
- 修后首命令漏收集旧领域38项，已独立补齐，不冒充首命令全收集。
- 历史完整C51的56.895041ms和第三轮三段失败全部保留于原文档，
  本文不覆盖旧失败；本轮仅一个产品版本和一次增长诊断。
- 本轮没有新的功能失败或超50ms的阶段p95，按约定不再追加调优/重跑；
  成熟仅1.15%余量且p99>50ms，**足够余量目标未证明**。
- 未运行原完整10000测量C51，不宣称它通过；最终由父另派独立者。
  原入口附加profile不替代完整样本，未触碰验收门槛或benchmark。
- 未测开放环过载、故障域、断电恢复、背景争用或生产负载；
  回归不等价于断电原子性测试。未运行全库lint或安装工具。

## 最终冻结与复跑

最终产品SHA与增长诊断前一致，测试自修前反例起未改断言；
以下十个只读路径的修前/修后SHA完全相同。旧失败文档没有覆盖，
无Git/网络/生产/模型/部署操作，没有其他文件写权请求。

| 文件 | 最终SHA256 |
| --- | --- |
| domain/emotion.py（唯一产品修改） | `f79c1ef6dac5a50d4fdaf72ba8d00e40156abbe070007a91c80e4ad8d6876fc0` |
| tests/domain/test_numeric_fast_path.py（新增） | `8cdf21b866562708dd7178c16fa00da7565c4fb429d3f3736e525231399e7b56` |
| contracts.py（只读） | `b329e758674451807bdd938f4473027266bb00b643ab1e5467590b9191333292` |
| domain/relationship.py（只读） | `fca375101f7ed93bf49b6c9a89c56d4138fc07821b148bb0dfe2fbd79caad8b5` |
| domain/night.py（只读） | `83156464573e6cc83e3b54dda7390a472b3414a6f721e8f51e0d1c899face04c` |
| storage/sqlite.py（只读） | `599cec9c29caa8c69f84bb27ed88c027a7fdf548ea11442153021d49199eb116` |
| runtime/projector.py（只读） | `cb1051be1814573a1b24f95cf1f5511aa2c48cf82adf0eaadbfd400045a24c79` |
| api.py（只读） | `a88ef0fe7af62428710c4cd7a8f587e070e6b6ad2a6660348d7238986c11e9c9` |
| tests/storage/test_sustained_latency.py（只读） | `6576838f1610a9bd88aebcf7b11f45e592c969e30b62b87bf090b24af046a715` |
| tests/performance/bench_local_state.py（只读） | `4f3c1a4ffedf388af9262c7eb4cb073d3cfed24e73483bb6587e09b4678d03c4` |
| docs/performance-fix.md（只读） | `a61a4933d26bd8363e564126dbf78acb89169f1393b4586c7e5e64efcdab113a` |
| docs/verification-performance-final.md（只读） | `55425fb921ed675158c8e8a864fd1caf5975619f01d99923f5a97e9a61b14829` |

边界/受影响套件及原增长复跑入口见上方实际命令。
以后统一跑受影响套件时只列 `tests/domain` 目录，避免同时显式列其内部新文件。
增长解释器沿用宿主临时venv，功能回归沿用 `.venv-ci`，均未安装或修改环境。
完整C51由父另派独立者，保持原 `tests/performance/bench_local_state.py`、
10000真实预填/10000测量/10000读取/50scope/20worker/256字符/50ms门槛，
结果另起唯一证据名，不复用旧FAIL文件。本实现者未运行它，也不勾父spec。
