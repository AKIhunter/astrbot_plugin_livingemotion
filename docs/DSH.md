# LivingEmotion for DSH · 0.1.0-alpha.1

独立原生 Host 插件，tag 为 `dsh/v0.1.0-alpha.1`。复用 LE 0.7.1
（`6e57978620b2e5e416ad6f5307abedef463c33ef`）的 Python 情绪、关系核心，
通过 Cordis 入口接入 DSH。AstrBot 的 metadata、配置与数据不迁移。

## 版本与安装

限定 DSH `0.2.1-rc.2`、Cordis `4.0.5`、schemastery `3.18.5`。
需要本机 Node.js 22.19+、Python 3.11+；Python 部分仅用标准库。
QQ 桥接按 `@xmanrui/dsh-im` 5.10.0 / 源码
`0694642e9fe5dd3af9a4f9516334d6ac288b2759` 的公开接口适配。
其他 DSH RC / master 不在本版兼容声明内。

在 DSH Host 的依赖目录安装发布附件：

```sh
npm install /path/to/akihunter-dsh-livingemotion-0.1.0-alpha.1.tgz
```

通过 DSH 插件安装入口应用包内 `cordis.patch.yml`，或在 Host 的插件配置
中登记该补丁中的 `id` 与 `name`。本版没有 npm 公共注册表发布；
不能用不存在的远端包版本替代附件。macOS / Linux 命令行环境必须能执行
`python3`；桌面启动环境找不到时，在本插件 `python` 字段填写绝对路径。
这一步的 DSH 桌面安装 UI 尚未实测，Cordis 直接加载与附件安装另有离线验证。

## 首版能力

| 能力 | 实现与边界 |
| --- | --- |
| 会话情绪 | 接入 `agent/pre-step` 接受的 user-source 输入，复用原情绪规则和去重 |
| 动态上下文 | 每个 Agent 独立注册 livingEmotion context，使用 DSH admission refresh；不替换人格 |
| 原生关系接口 | `ctx.livingEmotion.ingestNative` 接受可信 Host 传入的身份与 targeting，复用关系核心 |
| 主动文字入口 | `sendText` 调用桥接公开 `send`；默认关闭，需可信 Host 发起 |
| 数据与卸载 | 独立 SQLite；Cordis effect 管理工作进程，卸载终止子进程 |

自动情绪只归属于当前 DSH 会话；`session-user` 是逻辑参与者标识，
不是 QQ Open ID，也不是从正文推断的人。它不会自动计个人好感或写个人观察。
`describeConversationSync.senderId` 是桥接最近作者，不能证明本轮身份，所以不使用它。

原生事件与逻辑会话使用独立状态范围。`ingestNative` 返回该原生范围的情绪、
关系和 prompt，并在调用时刷新当前 Agent context；随后的普通 DSH 输入或
`snapshot` 会回到逻辑会话范围。需要稳定个人关系提示的集成方必须逐轮提供
可信原生事件并在其自己的准入环节使用返回 prompt。本版不声称 QQ 自动关系闭环。

未包含：日记、梦境、作息、承诺、自动主动调度、模型轮询、原 AstrBot 控制台、
旧数据迁移、QQ 未提及群聊旁听。掌控感字段沿用核心中性默认，不自动模型分析。

## 平铺配置

| 字段 | 默认 | 效果与设置位置 |
| --- | --- | --- |
| enabled | true | 本插件开关；关闭不启动工作进程、不更新、不注入 |
| python | python3 | 本插件填写 Python 可执行文件；需要 Python 3.11+ |
| dataDir | .dsh/livingemotion | 本插件填写独立目录；不要填写 AstrBot 业务目录 |
| proactiveEnabled | false | 开启后由可信 Host 调用 sendText；不产生自动计划或额外模型调用 |

绝对 dataDir 是本版状态 instance 命名空间的一部分，移动目录会形成新状态范围。
升级时保留该路径；未提供旧 QQ 号 → Open ID 的映射或导入工具。
共享插件包可以，多个 Host 进程不要同时写同一状态目录。

## Host 契约 v1

调用者必须是同进程可信插件；本版不注册 HTTP API 或向模型暴露身份写入工具。
其他插件需通过 Cordis `inject: ['livingEmotion']` 声明服务依赖。

```js
await ctx.livingEmotion.ingestNative({
  agentId, channel: 'qq', botId, conversationId, senderId, sourceId,
  text, sceneKind: 'group', targeting: 'bot-mention', occurredAt: Date.now() / 1000,
}, signal);
```

身份必须来源于真实通道事件，不能来自用户正文。`targeting` 只能是
`bot-mention` / `bot-reply` / `other` / `unknown`。
群聊未知目标不计关系；同一 sourceId 去重。
消息 ID 与身份字段最长 512 字符，text 最长 32000 字符。
本版不自动绑定 DSH-IM 的内部 RPC origin。

```js
const result = await ctx.livingEmotion.sendText({
  deliveryId: 'stable-intent-id', botId, targetId, text: '你好',
}, signal);
```

targetId 必须是桥接已登记目标的 ID，由集成方通过桥接公开目标管理接口取得。
`accepted` 只表示桥接 `{sent:true}`，不等于取得平台消息 ID 或确认用户已读。
网络错误记 `unknown`；SQLite 在发送前占用 deliveryId，重载后也不自动重试。
未知发送应先人工核对；不得换 deliveryId 绕过未知状态。
更换相同 deliveryId 的 bot / target / text 会报冲突。
调用者可传 signal 取消；插件卸载也会取消在途发送，状态不明时仍不重发。

`snapshot(agentId, signal)` 是逻辑会话只读状态入口，不调用模型。

## 验证与回退

仓库执行 `npm test`。固定版本真实 Cordis / AgentRegistry / SystemPrompt，
伪 Agent、假桥接、真实 Python 工作进程；零付费 API。
覆盖并发会话、动态上下文刷新、拒绝不更新、内部输入过滤、媒体对象保留、
原生群关系目标门槛、跨重载发送去重、故障启动和 PID 退出。
真实 QQ 投递、DSH 完整 AgentLoop、桌面安装 UI 未验证。

卸载本插件即回退；独立 SQLite 保留给后续恢复。不删除 AstrBot 配置或数据库。
代码恢复使用 Git tag / commit。取消与未知发送无需新增服务器副本。
