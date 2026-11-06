# F8 后台 Job 取消修复交接

日期：2026-11-05。来源：父规格 R11 / C50 / F8，以及
`docs/verification-performance.md` 的 P-C50-01。
本文是实现者的修复与自测记录，不替代父任务安排的非实现者独立复验。

## 范围与归属

仅修改 `runtime/background.py`，新增
`tests/runtime/test_caller_cancellation.py` 和本文。
未修改父 spec/tasks/checklist、独立 budgets 测试、其他产品文件或旧插件；
未执行 Git 操作。核心继续拥有 application/models，存储专项继续拥有
sqlite/api/projector。本专项不改 Provider 共享对象、并发、队列或超时配置。

`background.py` 首次读取和 apply_patch 前 SHA256 一致，未发现该独占文件
在此期间有并发改动。其他专项文件的后续状态不由本专项冻结。

## 状态边界与不变量

SEM 仅加载 `state-machine-correctness`，置信度高。
模型限定为同一事件循环中的 caller、completion、worker、work 和配额预留；
不建模远端服务实际执行或计费。

安全性：

- caller 取消只关联当前 job 的 work，不能取消唯一 worker 或下一 job。
- 队列中取消不派发、不预留；出队后取消必须在实际调用前再次检查。
- 等待预留时取消不打断预留结果的接收。成功预留仍消耗额度，随后记取消；
  不派发模型、不退款、不隐式重试。
- work 吞掉取消后返回的值不能记为 succeeded；显式 `ModelResultUnknown`
  仍记 unknown，不能转换为成功。

活性：

- 对协作式可取消的 work，等待其清理结束后才记终态、释放 pending/队列计数，
  然后 worker 可继续下一 job。
- runtime.stop 仍取消 worker，并传播到其 work/transport，等待清理。
- caller 自身仍可立即收到 CancelledError；等待所有 job 清理使用 runtime.join，
  不让已取消 caller 阻塞队列中其他任务的推进。

没有新增租约、续期或重试机制。既有 job ID 去重、持久 reservation ID 去重和
重启 recover_inflight 的 unknown 处理保持不变。

## 反例与实现映射

原始两例均等 work/真实 SDK MockTransport entered 后取消 caller，
50ms 后释放响应。原实现只有 completion 被取消，work 取消计数 0，
仍可把结果记为 succeeded。

| 时序 | 修复位置与行为 | 回归证据 |
| --- | --- | --- |
| 已排队取消 | 保留 `_worker` 初始取消检查 | 原 `test_queued_caller_cancel_never_dispatches` |
| generation 查询中取消 | `_worker` 查询返回后检查，不进入预留 | 新 `test_cancel_after_dequeue_never_dispatches[generation]` |
| 预留等待/提交后返回前取消 | 先接收预留结果，再检查取消并按已预留状态收尾 | 新同名 `[reserve_before]` / `[reserve_after]` |
| work Task 创建后、首步执行前取消 | `_run_work.invoke` 在调用 work factory 前检查 | 新同名 `[dispatch_scheduled]` |
| work 已进入 | completion 回调仅取消当前 work；finally 解除关联并等待清理 | 原两个 C50 失败例；新 cleanup/下一 job 例 |
| work 吞取消或报告 unknown | 返回值前检查取消；保留 ModelResultUnknown 分支 | 新 `test_cancel_cannot_become_success_or_refund` 两参数 |
| caller 取消与 stop 重叠 | shield 隔离 worker 的取消传播，避免再次打断正在进行的 caller 清理 | 新 `test_stop_during_caller_cleanup_waits_without_second_cancel` |

`_worker` 用当前 worker Task 的 cancelling 状态区分自身停止与 work 取消。
前者记录 runtime_stopped 并退出；后者记录 caller_cancelled 后继续循环。
work 自身取消且没有 caller 取消时记录 task_cancelled，也不退出 worker。

## 实际执行

所有命令的工作目录为：
`$WORKSPACE/插件/astrbot_plugin_livingemotion`。
复用已有宿主 Python 和 `/tmp/le-t11-test-deps.x1ctHY` 的 pytest 依赖，
没有安装或修改依赖。禁写 pyc、禁用 pytest cache；SQLite 为 pytest 临时库。
budgets 自带禁止 socket 网络的夹具，模型链路使用真实 SDK 加 MockTransport；
新 runtime 测试只使用内存事件与临时 SQLite。

### 原两个失败的前后对照

以下完全相同的命令在修复前后各执行一次：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/le-t11-test-deps.x1ctHY ../../.livingemotion-host-t1/venv/bin/python -m pytest -p no:cacheprovider tests/budgets/test_runtime_budgets.py::test_active_caller_cancel_stops_work tests/budgets/test_model_payload.py::test_active_generation_caller_cancel_reaches_transport -q
```

- 修复前：**2 failed, 1 warning in 9.43s**，退出码 1；两例取消计数均为 0。
- 修复后：**2 passed, 1 warning in 4.23s**，退出码 0；两例均验证派发 1 次、
  work/transport 取消 1 次、持久状态 cancelled。

### Runtime 与 Budgets 回归

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/le-t11-test-deps.x1ctHY ../../.livingemotion-host-t1/venv/bin/python -m pytest -p no:cacheprovider tests/runtime tests/budgets/test_runtime_budgets.py tests/budgets/test_model_payload.py -q
```

结果：**53 passed, 1 warning in 8.93s**，退出码 0。
其中新增取消测试 8 项。除上述竞态外，原 runtime.stop、队列取消、超时、
unknown、不退款不重试、跨重启配额、并发上限和真实 Provider 请求隔离均通过。
唯一 warning 为宿主导入 audioop 的弃用提示。

## 结果不明与限制

- cancelled/caller_cancelled 是本地任务终态，不证明远端未处理请求或没有计费；
  保守保留配额，不自动重试。明确的模型结果不明仍为 unknown。
- 保留原超时阈值；等待清理不承诺固定耗时。Python 不能强制终止拒绝响应取消的
  协程，本专项不引入强杀或后台遗留任务机制。
- 预留尚未返回时 caller 取消，worker 会等该预留正常返回后收尾。
  不把“取消”虚构成数据库事务回滚；进程崩溃遗留预留仍由既有恢复路径处理。
- 未运行 1 万性能基准、普通全量、生产宿主发送或真实模型网络调用。
  runtime 测试不是整项 C50、宿主生命周期或 Application 联验的最终验收。

## 源码锚点与核心交接

`runtime/background.py`：

- 修复前 SHA256：`e81a42f6ae9922ea1746e8cb9d4760c570296f246db4259de8e7a98c4e49020b`
- 修复后 SHA256：`e413824c41c4040c465f7b47e2c96a52ad2cb791f3ed413ca570ec5207e7690d`

新增测试 SHA256：
`e20a54daed4da0b5a4d38029c43c9f073990aa77e1a1bfb2b150ab013607f416`。

交接核心 `arun_6aeca78908a3b52e23bb04e7`：F8 实现和本轮自测完成，
无需修改 application/models 或存储接口。请父任务在最终源码冻结后另派
非实现者复跑上述命令，并由父维护 F8/C50 的最终状态；本专项未勾验收清单。
