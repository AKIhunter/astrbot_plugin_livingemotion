# P3 回复、收尾与完整补课接入

状态：已接入；后续1437项完整便携回归和23场景浏览器检查通过，
四版真实宿主及远端交付在本条记录时仍待完成。

真实消息仍以原 Context 登记，状态所有者不作为归档、记忆或发送来源。
`Application.on_message` 仅在 ingest 持久 accepted 后收录补课归档并异步派发
本地记忆；重复输入不会重复入队。群唤醒只读取原生 At 组件，不解析文本里的 @。

## 回复票据

`NightRuntime.reply_started(context, reply_id)` 返回 allowed/ticket，真正开始的
回复生成占一轮；`reply_submitted(context, reply_id, ticket=...)` 验证原来源、
状态模式代际、周期和截止时间，扣一次精力，并开始首次提交窗口。
Application 保有票据与真实事件 lease，客户端不能制造票据。

原生钩子 `on_decorating_result` 位于 LivingHello 最终修饰后；提交前重新检查
配置 revision、来源 generation、新人消息水位、长期记忆授权和沉睡截止。
末轮虽然显示困，只有已经持久准入的当前真实请求可以完成。
原生提交记录为 `bot_reply_submitted`，不制造送达或 bot_action_succeeded。
分段、图片、TTS附加与重复钩子不重新扣精力。
`observe_message` 在原生 process 读取选项前禁流式，末级 request hook再次缓冲。
Live模式无这一提交接点而被拒绝；stream finish和runner错误通知不计首次提交。
晚安生成后与提交持久化后重新验证记忆，最终校验异常清空结果并停止事件。

## 完整补课

`storage/catchup.py` 单独保存有界源归档，避免短提示窗口的200条上限影响遗留未读。
固定触发消息之前的上界；未完成批次不因新睡眠或重启替换。45条、80条硬限和
60分钟分块边界迁自用户修复；长正文再按字节预算分片，保留全部尾部。
每个成功分块有源哈希回执，失败保留未读；只有真正读过且完成必要补答的行被标记。
摘要仅供话题导航，不冒充完整原文。

读取摘要不占唤醒回复轮；历史补答每次唤醒最多3次生成，
持久额度跨批次和重启共用，失败仍计。真正开始补答生成时占唤醒轮。
同一原会话串行，所有补答交给 `BehaviorService.execute_control`，
共享执行者、持久发送标记和总发送额度。
发送结果未知保留阻断，重启或下一批都不自动重发。
正常回复提交只标记原触发消息已处理；身份变化、过期或派生素材保持未读且不入模型。
准备耗时使用 `livingemotion:wake_prepare_seconds`，同时兼容
LivingHello 既有 `congling:wake_prepare_seconds` 的读取口径。

## 睡前晚安

独立 closing 开关，仅正在回复或过去10分钟实际参与的会话可触发。
精力将低于10或疲劳前配置提前量内，优先并入宿主当前结果；无当前结果时
使用同一行为执行者。每周期、每真实会话有持久 intent，配额不因切模式复活。
随机关闭使用本地休息文案；开启单独调用 closing Provider 并共享生成总预算。
新人消息、人格/范围切换和沉睡均重新检查，失败不阻止作息推进。

## 验证证据

本次针对协调接点的合成检查：
`tests/night/test_full_catchup.py` 6 passed；
`tests/integration/test_retro_reply.py` 4 passed。
覆盖1001未读、Unicode长正文尾部、重启/失败、晚到消息、来源清除、
发送未知、首次提交窗口、末轮、沉睡优先、新人撤销与原生群@。
这些是新的合成检查，不是生产发送或四版宿主验收。

后续新增晚安合并/模型等待撤权/新人撤销/共享发送额度、跨批次与重启补答上限、
来源身份/TTL反例、stream finish不计费和Live阻断；
对应四份协调测试为 **31 passed**（1.16s）。
完整候选便携回归为 **1437 passed**（21.14s）。
旧6/4项数字仅记录早期窄检查，不与后续集合相加。

## 冻结来源

实施时冻结的用户当前修复副本：

| 文件 | SHA256 |
| --- | --- |
| 从绫 night/wake_flow.py | 0b68a30b34064af5a6dbbee995441debcbaa14419e6582c2605ede9f7e4ab66b |
| 从绫 night/crawl.py | 27cac5c6f8f751ac1af1e045d1d5f854f5c7911e348e95e2ea70eebb8a2783db |
| 从绫 night/rollup.py | ee3a366789ab907a4f4ea84a250272ebc19187040cb6b3ce0b52ccb444ad5ae4 |

前两份与计划核对时不同；使用执行时完整副本，没有回写或覆盖用户原目录。
这里只迁入流程语义，不复制私有SQL、人设或运行数据。

## 最终整合验证

此前1437项为阶段结果。最终完整可移植回归1451项通过；
原生GENERAL_RESULT/AGENT_RUNNER_ERROR错误文本不启动唤醒窗口，
不扣回复精力，生成失败仍消耗原尝试轮数。正常LLM_RESULT继续在最终提交时扣一次。
真实四版宿主与原生iframe证据见 [宿主验收](verification-retro-host.md)，
不与早期31项接点或合成发送桩相加。
