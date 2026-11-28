# 导出近 3 天诊断日志

在 `livingemotion` 页面顶部点击「导出诊断日志（近3天）」，浏览器直接下载 ZIP。打包期间按钮禁用，完成或失败后自动恢复。登录失效、已有下载、宿主不支持下载时显示对应提示；中文、英文、日文均有文案。提交问题时附上 ZIP、发生时间和异常现象。

服务器固定选择导出时刻之前 72 小时，时间使用 Unix 秒和 UTC。跨越边界的任务保留已有因果链；环境和设置是当前快照。有记录不代表完整覆盖，升级前已清理的数据不能补回。

| 文件 | 内容 |
| --- | --- |
| `说明.txt`、`manifest.json` | 范围、条数、实际时间、缺失来源、损坏/截断计数及 SHA-256 |
| `environment.json`、`settings.json` | 本地版本、采集健康、调度状态、集成状态和白名单设置；Provider 的 `api_type` 未声明时为 `null` |
| `runtime.jsonl` | 原始事件分类、归档结果、回复准入和停止原因、宿主 Agent 开始与结束、发送前校验和发送回调，以及梦境/晚安/调度等后台事件 |
| `events.jsonl` | 事件 ID、角色、时间、代次与会话别名 |
| `emotion.jsonl` | 仍保留的情绪数值、受控投影追踪和精力变化 |
| `behavior.jsonl` | 主动行为状态、实际/模拟标记和已有投递回执 |
| `promises.jsonl` | 承诺状态、到期时间、重试次数与是否存在错误 |
| `experiences.jsonl` | 日记/梦境归档元数据、手动任务、最新自动结果和窗口内的尝试预留数 |

不导出完整配置、数据库、聊天正文、提示词、媒体、承诺描述/记忆片段、日记或梦境正文和标题。原生事件 ID、会话、账号和回复占位 ID 使用一致别名。日志处理器保留级别、文件行号、异常类别和栈帧位置，不采集模板、参数和异常原文。承诺的自由文本错误只输出存在状态。

排查无回复时，在 `runtime.jsonl` 按 `flow_id` 串起 `ingest` → `supplement_request` → `reply_admission` → `reply_submission` → `after_message_sent`，再用同一个 ID 查 LH 的诊断包。`native_post_type` 可区分普通消息、通知和平台请求；未知值标为 `other`，没有原始类型标为 `unavailable`。相同事件和回复占位别名、不同 `flow_id` 表示同一个原始消息 ID 进入了两个独立宿主事件。后一个事件记录 `reason_code=reply_exists` 时，可确认 LE 因占位已存在而停止。`reply_submission` 的 `status=submitted` 表示 LE 通过了发送前校验；`after_message_sent` 的 `status=observed` 表示看到宿主发送回调，不能证明对端收到消息。

`host_stop` 保留 AstrBot 已实际输出的停止标记。宿主日志携带已关联的 `host_trace_id` 时，也能收录同一流水线的其他插件停止和警告、错误位置。没有宿主追踪 ID 的停止标记只能按时间参考。`environment.json` 显示当前宿主追踪开关和日志收集状态；启动失败前未初始化的采集、宿主未输出的日志、轮转删除的记录无法补回。

`settings.json` 补充作息、晚安、补答、日记/梦境及主动行为的生效配置；`dream_owner_qq_set` 只表示是否填写通知号码。`environment.json` 的 `scheduler` 显示当前任务、阶段、开始/结束时间与最近成功时间。`in_flight` 表示该轮还没结束，单次快照无法判断是否卡死；一轮完成也不代表消息已送达。

`experiences.jsonl` 按 `source` 区分 `entry`、`job`、`auto` 和 `attempts`。其中 `auto` 是每类最近一次可用结果，正常的梦境门禁需查 `runtime.jsonl` 的 `dream_skip`。预留数按创建时间落在窗口内的账本行统计，不等同于真实模型调用次数或费用。缺少归档不等同于从未生成。

`runtime/diagnostics.py` 定义数据白名单与只读来源；`diagnostic_bundle.py` 负责采集、脱敏、留存、压缩和清理。业务提交成功后记录摘要，采集失败不会改变提交结果。持续记录独立于原有情绪 48 小时历史和承诺记忆片段 TTL，不延长业务留存。SQLite 导出使用独立只读事务，不复制数据库，也不占业务写入队列。

新增接口为 `GET console/diagnostics/export`，沿用严格管理员 JWT 校验，拒绝查询参数和页面资源令牌。二进制下载直接返回宿主流式响应，不经过 JSON DTO 校验。页面沿用原生下载桥；导出不调用模型、模型列表、天气或外部服务。

每插件诊断记录上限为 32 MiB，单文件达到 1 MiB 或跨小时后轮转。每条记录写入前检查总容量，不足时先删除最旧文件，为新记录腾出空间；超容量删除计数可见。启动、轮转、卸载及后台每 60 秒清理超过 72 小时的旧文件，无新日志时也会自动清理；导出逐条过滤时间。每次导出的原始内容预算为 64 MiB，在完整记录边界截断。采集队列为 256 项，写入异常和溢出计数可见。记录损坏、来源缺失或截断都会在 `manifest.json` 说明。

同插件同时只允许一个打包或下载。临时 ZIP 权限为 `0600`、目录为 `0700`；完成、发送失败、取消及卸载后清理文件和锁。启动时立即删除上次异常退出遗留的 ZIP；运行期间定期删除超过 1 小时的遗留 ZIP，不删除正在打包或下载的文件。诊断状态临时文件同时自动删除，不形成历史备份。清理仅作用于诊断目录内的 `records-*.jsonl`、`exports/*.zip` 和 `status-*.tmp`，不删除业务数据或原有日志。存储不可写时显示导出失败，不返回原文。

离线验证：

```bash
python -m pytest -q tests/test_diagnostic_bundle.py tests/test_diagnostics_sources.py \
  tests/integration/test_retro_reply.py tests/integration/test_submission_reason.py \
  tests/integration/test_retro_closing.py tests/experience/test_restart_private.py \
  tests/verification/test_logger_contract.py
npm --prefix tests/ui test
```

对照两个诊断包，可用固定宿主的解释器回放重复投递；复用实际 `AstrMessageEvent`、追踪和请求派发，在临时目录验证两个 ZIP 的 `flow_id`、`host_trace_id` 和 `reply_exists`：

```bash
python -B tests/host/diagnostic_flow.py --host-source /path/to/AstrBot --lh /path/to/LivingHello
```

原生联合验收需要固定版本 AstrBot 的完整解释器和同级 LH 工作树。以下服务仅监听本机，数据目录应使用临时路径：

```bash
python -B tests/console/diagnostics_browser_server.py --host-source /path/to/AstrBot --data-root /tmp/lhle-diagnostic-test --port 18945
DIAGNOSTICS_BASE_URL=http://127.0.0.1:18945 node tests/ui/diagnostics-browser.test.mjs
```

该层使用两个真实页面、宿主原生 HTML 注入/SDK/鉴权/下载端点；父页面是最小下载测试桥，不代表完整 Dashboard iframe 或真实平台收发。模型调用为 0。测试完成后停止服务并删除临时数据目录。
