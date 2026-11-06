# livingEmotion

![livingEmotion 原创 LE 字标与四维状态线](.github/img/Banner.png)

基于 AstrBot 原生人格的独立情绪与行为状态插件，区分 **Bot 感受**、
**对方情绪观察**、**关系证据**和**作息精力**。长期记忆可关闭，不依赖从绫或 Bot Manager。
这是可解释的角色状态系统，不宣称模型具有真实主观意识。

> **0.1.0 冻结候选，已完成本地分层验收，尚未发布或生产部署。**
> 仅在 AstrBot **v4.29.4 / `61335414433db721b3f7ecc93f90deafe0a59d78`** 上有实测。
> 最终宿主 single/four/conflict 为 222/230/245，共 697 条断言 PASS；
> 原生浏览器 44 PASS（含 28 组布局）、0 pageerror。普通组件 1273/1273、
> 迁移 84/84、V06 4/4 PASS，各层重叠不相加，限制见[兼容矩阵](docs/compatibility.md)。
> 目标仓库 [AKIhunter/astrbot_plugin_livingemotion](https://github.com/AKIhunter/astrbot_plugin_livingemotion)
> 必须 **PRIVATE**，通过正常认证访问；实际提交与 CI 结果以仓库记录为准。
> 本地验收不代表远端 CI 或生产部署。

## 能做什么

| 你希望 | 行为与边界 |
| --- | --- |
| 沿用原来的人设 | 默认跟随当前会话原生人格，也可显式选择或关闭；不带固定“绫”人设 |
| 感受持续变化 | 愉悦、唤醒、压力、社交需求经过规则、限幅和时间恢复；普通聊天不额外同步调用情绪模型 |
| 理解对方 | “我很难过”是对方观察，不直接覆盖 Bot 心情 |
| 关系可解释 | 0..1000 分、阶段、来源账本、每日绝对变化预算；绑定关系不等于跨场景读取权 |
| 长夜与精力 | 清醒、困倦、待收尾、睡眠、醒后过渡；有限窗口补课，不重放旧待发动作 |
| 有限地主动找人 | 白名单、免打扰、精力、配额、冷却及最终来源复核；实际发送默认关闭 |
| 私人日记与梦 | 依赖有来源素材，梦明确为想象；私人全文不直接分享到群聊 |
| 自选记忆 | `none` / `local_lite` / `external`，读与导出开关独立 |
| 独立管理 | 七区极简莱茵生命风格白昼/黑夜页面，自有字标，无外部 CDN |

不包含从绫工具箱、QQ 扩展或原事实/向量/图谱引擎，不自动读取旧数据库。
本地验收只覆盖报告列出的范围；动态能力不等于已获发送许可。
独立安装默认 `active`，不会修改现有部署或消费者配置；自主、群主动、日记、梦与外部写入须分别启用。

## 第一次使用

1. 按[安装说明](docs/installation.md)在隔离 AstrBot 中放置插件并加载。使用 Python >=3.12，
   核对固定宿主版本，不复制生产配置、数据库或凭据。
2. 保持模型细化、主动/群主动、日记、梦和导出关闭。规则状态无需模型；测试不连接真实平台。
3. 从 AstrBot 插件页面入口打开 `livingemotion`。空库显示空状态；在隔离会话产生合成互动后，
   选择该来源，查看 Bot 状态与对方观察。不要用测试 fixture 充当管理后台。
4. 先查看健康和能力，再运行“模拟”。应为 `model_calls=0`、`sends=0`；
   拒绝原因需处理，不能用反复点击绕过。
5. 按需配置原生人格、时区、Provider 和范围白名单，详见[按需启用](docs/installation.md#按需启用)。
   生成可能计费，发送可能外发；本次交付不授权生产启用。

### 默认开关

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `enabled` / `mode` | `true` / `active` | `observe_only` 观察但不注入或自主发送 |
| `emotion_model_enabled` | `false` | 普通规则状态不需要 Provider |
| `autonomy_enabled` / `group_autonomy_enabled` | 均 `false` | 还须有效时区、完整范围白名单、路由和硬闸门 |
| `diary_enabled` / `dream_enabled` | 均 `false` | 有权素材与受支持 Provider；梦另须实时 REM |
| `memory_mode` / `memory_read` / `memory_export` | `none` / `false` / `false` | 当前 LivingMemory 后台检索和幂等导出明确不支持 |
| `night_enabled` / `night_block_chat` / `night_schedule_enabled` | `true` / `false` / `false` | 默认不阻断普通聊天，不自动执行睡醒计划 |

配置定义以 [`config.py`](config.py) 和 [`_conf_schema.json`](_conf_schema.json) 为准；
页面使用同一个原生配置对象，保存带版本和原因，409 后刷新复核，不自动重试。

## 导航

- [安装、配置和故障处理](docs/installation.md)
- [架构与状态计算](docs/architecture.md)
- [进程内 API 和管理接口](docs/api.md)
- [兼容矩阵与证据边界](docs/compatibility.md)
- [记忆来源与授权](docs/memory.md)
- [迁移 CLI 与回退](docs/migration.md)
- [交付状态、CI 分层与历史证据](docs/delivery-notes.md)

以上为当前用户入口；`FOUNDATION`、`CONTRACTS`、`DOMAIN`、`INTEGRATION`、
各模块交接及 `verification-*` 保存阶段契约或证据，不作为另一份当前安装指南。
证据数量不可相加，也不能用旧通过覆盖新失败。

## 记忆与隐私

`none` 不检索或抽取长期记忆，但仍保留自身状态、关系、配额和短期正文窗口：
默认 7 天、每场景 200 条、全库 10000 条。它不是无痕模式。

`local_lite` 使用独立 `explicit_memory.sqlite3`，只接受有来源、有期限的显式录入，
不自动抽取事实。默认每来源 200 条、全库 1000 条、期限上限 30 天。
当前没有面向用户的录入页面/聊天命令，单纯切换模式不会自动积累长期记忆。

`external` 仅走 LivingMemory 的公开真实事件接口并复核来源；当前后台检索返回
`external_background_authorization_unsupported`，幂等导出返回
`external_idempotent_export_unsupported`。打开开关不会补出能力，不伪造事件或读取私有 SQL。
切换模式不删除外部旧记忆；自身合格素材仍可用于日记、梦和行为。

## 兼容性与页面

页面有七个分区，记录每页 10 条，白昼/黑夜切换不改业务状态。
**原生 v4.29.4 iframe 禁止 localStorage**：提示“仅本次页面有效”，刷新回系统主题。
正常非 sandbox 环境的主题持久化由 12 项合成浏览器场景证明，不冒充原生持久化证据。
认证失效清空私人视图；页面资源 token 不是管理凭据。

模型使用 AstrBot 原生 **`ProviderOpenAIOfficial` 的纯文本 Chat Completions 路径**；
Qwen 纯文本参数由原生 Provider + 合成 transport 验证，未请求生产模型。
输入以完整 UTF-8 字节数加 256 模板余量作保守上界，不是精确 token usage；
不需要 `tiktoken`。其他 Provider 未验证并拒绝生成。
默认共享并发 1、队列 100、每日 48 次，输入/输出预算 4096/1024、超时 30 秒；
不发送 tools、图片或历史，Qwen 关闭 thinking，服务可采用更严格上限。

## 失败边界

`queued` 只表示排队，事件 `accepted` 只表示本地事务提交，不代表生成或投递成功。
AstrBot `send_message` 的 False 被记为 rejected，其余返回值（包括 True）为 unknown。
unknown 不自动重发、不退款、不产生成功行为证据，也不能满足依赖成功回执的收尾。
原生 after-sent 在发送失败后也会触发，不能作为确认；待收尾最多 120 秒后取消回到
清醒/困倦，不自动重发。无待回复的计划睡眠和手动睡眠可用，详见[兼容矩阵](docs/compatibility.md)。

生成后仍复核人格、身份、受众、路由、清除代际及新的人类消息。
普通聊天在受测补充状态读取故障时继续，自主执行保守停止；
H01/H02/H03 及 C30 unsupported 展示已在最终三场景通过，不泛化为任意故障或生产投递保证。
本次不启用生产睡眠阻断。

最终原完整 C51 为 10000/10000 成功，提交 p95 **48.801416ms**，通过 <=50ms 门槛；
余量仅 **2.40%**，不是生产容量充足保证。新存储 window 11/11 PASS，
见[最终性能证据](docs/verification-performance-final.md)。

## 常见问题

**关闭记忆为何还有记录？** `none` 只关闭长期记忆，状态、关系、短期窗口和额度仍独立保存。

**开关已开为何拒绝生成？** 还须满足 Provider、时区、素材、授权、预算及旧迁移约束；
以具体原因码为准，不通过重复点击绕过。

**能直接复制从绫数据库吗？** 不能。使用[迁移 CLI](docs/migration.md)预览一致快照并选择导入，
不恢复旧 pending，也不能忽略 WAL。

## 使用指令与开发

已注册 `le_wake`，通常用 `/le_wake`，实际前缀以宿主配置为准。
没有 `/livingemotion ...` 命令族。受信插件通过 `plugin.api` v1 门面协作，
不能将 Python 参数 `admin=true` 当作管理身份，详见 [API](docs/api.md)。

从插件根目录检查：

```bash
python3.12 -m venv .venv-ci
.venv-ci/bin/python -m pip install -r requirements-dev.txt
.venv-ci/bin/python -m pytest -q
npm ci --prefix tests/ui --ignore-scripts --no-audit --no-fund
npm --prefix tests/ui test
tests/ui/node_modules/.bin/playwright install chromium
npm --prefix tests/ui run test:browser
```

普通 pytest 只运行可移植层；真实宿主、console ASGI 和原生 Provider payload
须[显式运行](docs/delivery-notes.md#检查分层)，不通过 skip 冒充通过。
浏览器命令会更新合成证据，不应覆盖其他验收者正在使用的产物。

## 更新日志与来源

0.1.0 尚未发布，见 [CHANGELOG.md](CHANGELOG.md)。
这是参考从绫行为需求的**非官方独立实现/衍生项目**，不声称上游背书或授权发行。
未复制上游函数、提示词或素材；上游未发现明确许可，MIT 仅适用于本项目权属明确的新写内容。
见 [LICENSE](LICENSE)、[来源说明](THIRD_PARTY_NOTICES.md)。
Logo/Banner 为原创几何 LE 与 livingEmotion 字标，仅参考极简留白、细线和黄绿配色，
不使用莱茵生命官方图案或上游素材。本次不包含商店上架或生产部署。
BiliBot/LivingHello 的消费者本地改动不进入新插件仓库提交；现有部署保持不变。
