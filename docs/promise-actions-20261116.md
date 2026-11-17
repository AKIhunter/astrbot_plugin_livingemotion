# 延迟生图与跨系统任务去重：0.4.0 实现说明

本轮修复两个入口：LivingEmotion 承诺到期生图，以及 AstrBot `future_task`
到期调用 LivingHello 生图工具。图片必须完成生成和宿主发送调用，才记录已发送。
普通文字提醒沿用既有路径。

## 1. 承诺生图

```text
回复末尾的 promise 标记
  → 发送前摘除标记
  → 核对本条正文的全部组件发送成功
  → 创建 promises 记录
  → 到期扫描、领取任务
  → 检查代际 / 配置版本 / 路由 / 夜间守卫
  → 生成画面描述
  → 持久化 generating
  → 调 LivingHello 的公开图片契约
  → 持久化 generated 和图片路径
  → 再检查守卫
  → 持久化 sending
  → LivingHello 统一图片投递接口返回匹配请求的 sent 回执
  → 持久化 action_state=sent、任务 status=sent
  → 留存实际画面描述，供追问召回
```

新约定使用 `<!--promise:2分钟:生图：窗边的橙色猫自拍-->`。
已有明确包含自拍、照片、图片、绘制等词的图片约定兼容旧格式。
“提醒我拍照”仍属于文字提醒。

这里采用专门的生图动作接口，没有向后台模型开放任意工具循环。
画面描述仍由模型生成；图片连接、样式、每日额度及 API 超时仍由 LivingHello 管理。
不读取对端配置或 API Key。

## 2. 宿主 cron 生图

`future_task` 唤醒的主代理只运行工具循环，没有普通回复的发送阶段。
旧生图工具把图片挂在事件上等 `after_message_sent`，这条路径无法兑现。

现在 `GenerateImageTool.call()` 识别宿主的 `cron_job` 元数据，调用
`execute_deferred_image()`，生成后调用同一个 `deliver_deferred_image()` 投递接口。
普通聊天仍保持“文字先发、图片随后发”的既有行为。

一次性 cron 使用 `(session, cron_job.id)` 的持久记录去重。模型改写 prompt、
新事件 ID、进程重启都不会再收费。该记录独立于图片额度，不多扣一次额度。
周期 cron 每次唤醒是新的一轮，只限制同轮重复调用。
定时路径不支持使用已消失的用户参考图，只使用文生图。

## 3. 跨系统归属

| 场景 | 判定与结果 |
| --- | --- |
| 同轮先成功创建一个 `future_task`，又输出承诺标记 | 以真实工具回执为来源证据，承诺记录为 `delegated`，不再排入 LE 队列 |
| 同轮成功创建多个宿主任务，又输出标记 | 标记无唯一归属，返回 `host_owned_turn`；本轮只能使用一个调度入口 |
| 不同轮已有宿主任务 | 通过 `cron_manager.list_jobs()` 核对同会话、同发起人、启用的一次性任务、时间差不超过 90 秒及内容归一化 |
| LE 先建任务，后创建等价 `future_task` | 宿主创建成功后，LE 改为 `delegated`；宿主创建失败则保留原 LE 任务 |
| LE 已开始执行 | 包装后的工具返回“已在执行”，不再新建宿主任务 |
| 工具重复创建同一事项 | 返回已有宿主任务 ID |
| 其他群成员、其他会话、不同时间或不同事项 | 保持独立，不去重 |
| 宿主周期任务 | 保持宿主周期语义，不与一次性任务合并 |
| promise 标记写成周期任务 | 返回 `recurring_requires_future_task` |
| 到期前从其他入口新增了宿主任务 | 到期领取前再次查宿主并交出归属 |

正常模型请求在最后一个请求钩子里复制工具集并包装 `future_task`，
不修改宿主共享工具对象，不靠“工具前钩子抛异常”阻断执行：
宿主会吞掉这类钩子异常，不能作为安全的阻断机制。

同轮使用来源回执，因此不依赖模型复述时的同义词和随机档位。
不同轮只做保守的内容归一化及相似度判定，不声称能够识别所有自由改写。
宿主外部 API 与 LE 不共享数据库事务；外部 API 恰好在 LE 已领取后另建任务的
并发窗口，不属于本地工具锁可保证的范围。

## 4. 中断与重试

| 图片阶段 | 重启 / 再次扫描 |
| --- | --- |
| 尚未生成 | 按现有退避重试，最多首次加三次 |
| `generating` | 收费请求可能已发出，标为 `unknown`，禁止自动重新生图 |
| `generated` | 使用持久化路径发送已有图片 |
| `sending` | 用户可能已收到，标为 `unknown`，禁止自动重发 |
| `sent` | 只补任务最终状态，不重新发送 |
| 图片文件丢失 | 标为 `unknown`，不重新收费 |
| 宿主明确返回 False | 保存 `generated`，随后可重试发送原图 |
| 发送抛异常 | 结果不确定，标为 `unknown`，不自动重发 |

单进程扫描使用互斥锁，重叠 tick 直接跳过。
与 `future_task` 归属变更另共用领取锁。
生图动作整体有 600 秒期限；模型描述与图片请求各自仍受原有超时约束。
超时发生在可能收费/发送的阶段时停止自动重试。

时间保存为绝对时间戳，用户精确延后沿用既有解析，语义档按配置时区取值。
默认 tick 15 秒，正常无积压时有一轮扫描误差；有积压时按每轮限量依次补跑，
不承诺硬实时送达。重启后扫描已有到期项；未知副作用不参与补跑。
`updated_at`、`action_state`、`last_error`、`sent_at` 与图片路径用于排错。
中断阶段会输出核心 ID 和阶段日志。未新增独立“定时器完全不触发”报警器。

`sent` 指宿主适配器发送调用成功，仍不代表 QQ 等平台已给最终投递凭据。
宿主 cron 的 `completed` 摘要也不能替代实际图片发送证据。

## 5. 数据迁移与交付

`promises` 自动补充四个字段：`source_event_id`、`host_job_id`、
`action_state`、`action_result_json`。存量行默认空值，已有文字提醒继续运行。
`delegated` 是独立终态，不冒充 LE 已发送；它与其他终态一样参与历史清理。
`defer()` 不能再把已取消或已交给宿主的任务复活。

LivingHello 图片额度库新增 `deferred_runs`、`deferred_images` 表，旧额度记录保持原样。
后者绑定 request_id、session、path 和投递阶段，发送前写入 `sending`，
明确拒收可重试原资源，`sent` 与未知提交均阻止第二次发送。已发送状态不会被晚到的旧回调复活。
没有新增配置项，也没有改变现有配置、额度数值或 API 连接。

两个插件的配套代码应一起合入。没有图片契约的旧 LivingHello 时，LE 返回
`image_unavailable` 并退避，不用“图片给你了”的文字冒充完成。
支持前版 `deferred-image.v1` 的 LH 及升级前已生成的旧资源继续使用原发送/回调路径。
带新版 `delivery_contract` 的资源必须使用新版投递接口，接口暂时缺失时等待恢复；
不得退回直发而绕过持久去重。
0.4.0 纳入上述代码与对应迁移。升级前备份配置与 SQLite，并核对配套 LH
是否提供图片契约；已有文字承诺、图片额度和历史记录保留。

## 6. 离线验证入口

普通矩阵：

```bash
python -m pytest tests/integration/test_promise_actions.py -q
```

真实宿主类与跨插件契约：

```bash
ASTRBOT_NATIVE_SOURCE=/path/to/astrbot \
python tests/host/promise_actions_native.py --livinghello /path/to/astrbot_plugin_livingHello
```

该入口执行宿主源码中的 ToolSet、FunctionTool、FutureTaskTool、
MessageSession 和 CronMessageEvent，隔离宿主启动、Provider、HTTP 与平台。
验证图片路径、实际绘制摘要、发送调用和持久化状态；不发起真实收费请求。

当前发布的验证结果及基线失败名称对照随 GitHub Release 说明记录。
职责与接口兼容规则见 [双插件协作契约](cooperation-contract-20261116.md)。
