# 本地安装与使用

## 改版安装入口

使用 Python >=3.12 与 `metadata.yaml` 允许的 AstrBot 版本，通过已授权账号获取
PRIVATE 仓库源码，放入宿主 `data/plugins/astrbot_plugin_livingemotion/` 并加载。
保留包、配置 schema 与完整 `pages/livingemotion/`（含本地 vendor），
不携带开发虚拟环境、node_modules 或运行数据；运行页无需 Node/CDN。
从插件页面进入“设置 → 快速开始”，按 [生活控制台](life-console.md)配置人格、
时区、五档作息、模型、城市与记忆。所有设置统一提交到 AstrBot 原生配置。

旧配置缺少新版字段时保留会话独立状态与规则1；
切换到规则2并设置时区后使用新的唤醒/沉睡规则。兼容与本轮验收见
[兼容矩阵](compatibility.md)，配置说明以 [生活控制台](life-console.md)为准。

## 0.1 原生安装与 Provider 参考

下文保留规则1的原始配置、固定版本证据与 CLI 参考，不代表新版五档作息。

读者：隔离环境的安装者和管理员。依据：`main.py`、`config.py`、`_conf_schema.json`、
`runtime/application.py`、`runtime/models.py`。2026-11-05 核对冻结源码及已完成的最终宿主报告。
维护者在入口/配置/宿主升级时同步本页，每次交付复核；过期标记规则见[交接](delivery-notes.md)。
不依赖从绫、LivingMemory、BiliBot、LivingHello 或 Bot Manager 才能加载核心插件。

## 安装

1. 准备隔离 AstrBot **v4.29.4**，实测 HEAD 为
   `61335414433db721b3f7ecc93f90deafe0a59d78`，Python >=3.12。
   metadata 的 `==4.29.4` 是保守版本闸门，不保证同版本的任意改版都兼容。
2. 使用新的数据根和合成配置，不连接真实平台，不复制生产聊天、密钥或数据库。
3. 将审核过的插件放入 `<ASTRBOT_ROOT>/data/plugins/astrbot_plugin_livingemotion/`。
   保留 `main.py`、`metadata.yaml`、`_conf_schema.json`、Python 包和 `pages/livingemotion/`；
   不带 `.venv*`、node_modules、缓存、运行报告、数据库或本地配置。
4. 在宿主插件管理中加载 livingEmotion，从插件页面入口打开 `livingemotion`。
   宿主扫描本地页面资源并由 `PageAPI` 注册管理端点，无需单独启动 Web 服务。
5. 确认页面健康及配置来源为 AstrBot native。新库无来源时正常显示空态；
   在隔离会话产生合成互动后选取对应来源，检查 Bot 感受、对方观察及无费用模拟。

运行数据由 `StarTools.get_data_dir("astrbot_plugin_livingemotion")` 定位到
`<ASTRBOT_ROOT>/data/plugin_data/astrbot_plugin_livingemotion/`。
主库 `livingemotion.sqlite3`；local_lite 库 `explicit_memory.sqlite3`，都不应在源码目录。
插件由宿主提供 AstrBot/PyJWT 等环境，`requirements-dev.txt` 只用于开发检查。
运行页面不需要 Node、外部 CDN 或 `tiktoken`。

目标仓库 `AKIhunter/astrbot_plugin_livingemotion` 必须为 **PRIVATE**。
取得仓库读取权限并确认所需提交可用后，在隔离宿主的 `data/plugins` 目录通过正常认证 clone；
也可使用审核过的本地源码：

```bash
git clone git@github.com:AKIhunter/astrbot_plugin_livingemotion.git
```

SSH需已授权账号与本机SSH key；也可使用
`https://github.com/AKIhunter/astrbot_plugin_livingemotion.git` 配合系统凭据管理器。
不把 token 放到 URL、配置示例或文档中。实际提交与 CI 结果以仓库记录为准，
本地冻结验收不替代远端检查；本次不包含生产部署。
独立安装默认 `enabled=true, mode=active`，不修改现有部署；
BiliBot/LivingHello的本地消费者改动不随新仓库提交，也不在本次部署。

## 按需启用

原生配置和页面使用同一个 AstrBotConfig。页面保存需当前 revision 和原因；
409 时刷新后人工复核，不能自动重试旧 patch。不要另建页面配置文件。

| 目的 | 配置与前提 |
| --- | --- |
| 人格 | 默认 `persona_mode=follow`；`explicit` 需有效原生 `persona_id`；`none` 不加人格。普通请求不重复原生人格全文 |
| 规则状态 | 默认 `enabled=true, mode=active, emotion_model_enabled=false`；`observe_only` 不注入或自主发送 |
| 模型细化 | 在 AstrBot 配好下述受支持 Provider，再启 `emotion_model_enabled` |
| 作息计划 | 设置 IANA `timezone`（如 `Asia/Shanghai`），核对 `sleep_at=01:00`、`wake_at=08:00`，再启 `night_schedule_enabled` |
| 睡眠阻断 | 默认 `night_block_chat=false`；H03 管理员豁免及叫醒在最终宿主通过，本次不启用生产阻断 |
| 主动 | 时区、完整范围白名单、路由、免打扰/配额均满足后先模拟；`autonomy_enabled` 默认 false，群另需 `group_autonomy_enabled` |
| 日记 | 有权素材、Provider 与时区齐备后启 `diary_enabled`；`diary_at=23:00`，`diary_backfill_yesterday=false` |
| 梦 | 启 `dream_enabled` 且当前处于实时 REM；每夜默认最多两次尝试，不补发离线旧梦 |
| 记忆读取 | `none` 不查询长期记忆；`local_lite` / `external` 另受 `memory_read` 控制。local_lite 当前无用户录入页面，不自动抽取 |
| 导出 | `memory_export=false`；当前 external 幂等导出 unsupported，打开也不能生效 |

`autonomy_scopes`、`muted_scopes` 是**用空格或换行分隔的 `Context.scope_key` 字符串**，
不是逗号列表、裸账号、群号、路由或页面 `context_id`（后者是 account_key）。
scope_key 须由受信宿主接入代码对当前真实 Context 读取，不能自行拼造或猜测。
当前页面没有 scope_key 选择器；拿不到经核实的值就保留空白和关闭主动。
用[进程内 API](api.md)返回的 Context 可解析其 scope_key，仅供受信管理集成：

```python
from astrbot_plugin_livingemotion.contracts import Context

# snapshot 来自当前宿主 plugin.api.get_bot_state(verified_context) 的成功响应。
scope_key = Context.from_dict(snapshot["context"]).scope_key
```

默认免打扰 `01:00..08:00`、活动时段 `00:00..23:59`；
行为每日全局 6、每范围 2、冷却 7200 秒、未回复上限 2。
开关和模拟 eligible 都不替代发送前再次授权。

### 入睡确认边界

固定宿主 v4.29.4 不提供可靠的通用发送回执：after-sent 在发送失败后也会执行，
`Context.send_message` 的 bool 只表示找到平台，不能用来结束待回复收尾。
有待回复时进入 `settling`，既有上限 120 秒后取消并回到 `awake/drowsy`，
不自动重发；无待回复的计划睡眠及手动睡眠仍可使用。
健康行 `reply_confirmation=unavailable` 明示 unsupported，真实HTTP和iframe已验证；
不能把页面未报错当支持确认。typed port 成功仅是组件证据，不证明生产投递。
当前结果见[最终宿主验收](verification-host-final.md)，支持边界见[兼容矩阵](compatibility.md)。

## Provider 与预算

`provider_id` 留空时使用当前会话原生聊天 Provider；可显式指定原生 ID。
`fallback_provider_id` 仅在绑定候选不可用时尝试，不是请求失败后的重试/切换。
凭据只在 AstrBot 原生配置中管理，本插件不另设 API key。

仅接受精确类型 `ProviderOpenAIOfficial` 的纯文本 Chat Completions 路径；
Qwen 使用关闭 thinking 的参数。原生 Provider/SDK 参数通过合成 transport 检验，
未验证生产模型效果、账单 usage 或其他 Provider；其他类型保守拒绝。
输入预算为**序列化完整正文的 UTF-8 字节数 + system 字节数 + 256 模板余量**，
不是精确 token usage，不依赖 `tiktoken`。不发送 tools、图片或额外历史。
默认共享输入/输出上限 4096/1024，行为输出再限至 512；
原生请求限制 `max_tokens`、`n=1`，关闭请求副本的隐式重试，
返回文本按 UTF-8 字节上界复核，可能比实际 token 数更保守。

共享模型并发 1、队列 100、每日 48 次、超时 30 秒，情绪同场景至少间隔 300 秒。
缺模型、来源或可验证预算时拒绝，不发空请求；已派发费用额度不因失败/重启退款。
取消传播见[最终预算证据](verification-budgets-final.md)：C50 31/31、F8 53/53，
其中真实 Provider 16 项均实际执行、0 skip；这不是生产调用或全产品通过。
取消不证明远端未处理或未计费。新SQLite已独立完成window-03 11/11，
最终组件补齐迁移TTL；详见[最终性能证据](verification-performance-final.md)。

## 页面与排障

白昼/黑夜仅改变视觉偏好。固定宿主原生 iframe sandbox 禁止 localStorage，
页面明确显示“仅本次页面有效”，刷新回系统主题；非 sandbox 的持久化仅有合成浏览器证据。
记录每页 10 条。生成/发送按钮不是模拟，可能收费或外发。

- 无状态：检查宿主来源/人格解析和 `domain_ready`，空库不补造记录。
- 无日记/梦：查开关、时区、时段、REM、素材、额度及 Provider，不把错误文本当文章。
- 外部后台检索/导出不可用：这是当前明确降级，不读取 LivingMemory 私有库或伪造事件。
- `unknown`：可能已经投递，不自动重发；宿主 True 不是可靠回执。
- 401/403：回宿主登录，资源 token、`admin=true`、客户端 actor_id 均不能授权管理。
- bridge 缺失：从宿主插件页面入口访问，不直接打开 HTML。
- 状态存储故障：H02 原读取故障反例已在最终三场景通过，不泛化为任意故障都不影响原生聊天。

## 迁移与回退

CLI 已存在，入口 `tools/migrate_legacy.py`，有 `preview/import/verify/rollback-plan`。
不自动搜旧库；先运行帮助，再按[迁移指南](migration.md#精确-cli)准备显式选择文件：

```bash
python3.12 tools/migrate_legacy.py --help
python3.12 tools/migrate_legacy.py preview --help
```

源必须是已确认的一致快照；目标必须先由插件初始化后停机，停止全部写者。
任何 WAL/SHM/journal 旁文件都拒绝，不能删旁文件绕过；通过 SQLite backup 制作独立快照。
先预览、核对来源与字段，再导入/对账。旧 pending 永不恢复，旧观察不等于 Bot 感受，
旧未知关系不跨账号聚合，不全量迁移事实/向量。

F3 保留原绝对冷却、原时区/范围声明、真实旧计数与导入人类消息水位；
正文最长原时间起七天，置顶不延长迁移体验期限。未知约束拒绝，开关不能绕过。
最终完整migration 84/84（含CLI）、V06已证明限制4/4通过，覆盖运行时阻断及恢复；
其测试与full重叠，不叠加计数，也不等于生产迁移完成。

回退先停新执行者和消费者，等自有任务退出，保留新数据及一致备份，
再恢复明确记录的消费者选择。`rollback-plan` 只出计划，不停启进程或改配置。
不能用旧整库覆盖新记录，也不能有损写回从绫。无生产迁移/回退实测。

## 开发检查

见[交接中的检查分层](delivery-notes.md#检查分层)及 [CI](../.github/workflows/ci.yml)。
普通 pytest 包含可移植组件与回归；真实宿主、ASGI 和原生 Provider payload 显式分层。
合成浏览器会更新证据文件，不能覆盖他人的独立验收输出。
