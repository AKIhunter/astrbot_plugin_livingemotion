# T11 独立成品宿主验收

**最终冻结验收完成，释放宿主/浏览器/CPU 资源及 final 测试写入权；
文档专项可立即启动。产品与 final 测试不再写入，不重测成功场景。**

## 最新结果：最终真实宿主验收完成

single `final-single-3txvcu3v`：222 PASS / 0 FAIL；four
`final-four-az7ogq76`：230 PASS / 0 FAIL；均 exit 0，前后及共同源哈希一致。
conflict `final-conflict-fqecldcf`：245 PASS / 0 FAIL，浏览器 44 PASS / 0 FAIL，
28 组布局、0 pageerror，exit 0。合计 runner 697 条与 browser 44 条通过。
F13 每轮 HTTP 4 项、共 12/12，原生 iframe 4/4；原 H01/H02/H03、
C30/F1/布局断言未删改。三轮源文件与测试前后无漂移，停止任务 0、无写回，
宿主和浏览器进程均已结束。真实模型/平台投递/外部网络放行均为 0。

已收到全部产品 freeze、原 C51/window-03 完成及 CPU 释放的明确通知。
2026-11-05 23:47:56 UTC 基线至 23:55:49 UTC 末次校验一致；
原完整 single、four、conflict --browser 顺序完成，不带 focus、不重建环境。
详细逐 C 项 PASS/限制与完整哈希见 [`verification-host-final.md`](verification-host-final.md)。
以下“等待父明确开跑”及非冻结结果保留为历史，不代表本轮状态。

## 最新交接：F13 静态准备完成，等待父明确开跑

本阶段仅阅读及补充独占 final 测试，**未启动宿主、浏览器、pytest 或性能测试**。
核心于 2026-11-05 22:18:24 UTC 冻结的通知已核对；性能代理
`emotion_latency_last_mile` 仍独占 CPU 及 storage/api/projector，以父明确通知为准。
没有可用的父代理消息工具，故在此置顶交接：**宿主验收静态准备已完成，等待放行**。
不会因哈希暂时不变或其他文档出现性能结果而自行启动。

- 原 `final_run.py` 与环境保持不变；H01/H02/H03、C30、F1 和原浏览器断言全部保留。
- 已追加 F13：真实 legacy/v1 `console/state` 各 2 项，检查唯一
  `reply_confirmation=unavailable` 及中文无可靠回执、120 秒取消、禁止伪成功说明。
- 已追加 F13：原生 iframe 总览在 390/1280、白昼/黑夜下各 1 项，检查同一健康行
  可见、“不可用”文字及完整中文原因。只追加脚本，**尚无 HTTP/页面执行结果**。
- 静态校验：`final_checks.py` AST 解析与 `node --check final_browser.mjs` 均 exit 0；
  两份宿主报告的个人路径/JWT/私钥标记扫描零命中。没有导入产品或执行测试。
- 新最终报告为 [`verification-host-final.md`](verification-host-final.md)；
  当前新 run 数 0、产品/HTTP/浏览器执行断言数 0，不将历史 57/51 项算成最终通过。
- 收到父明确的“性能冻结且原完整 benchmark 已结束，可以开跑”通知后，
  按原命令顺序执行 single、four、conflict，至少 conflict 带 `--browser`，
  全部不带 `--focus`。三场景及每轮前后源码一致才可汇总，不重复择优。

以下为历史记录，旧失败及非冻结窄复验原样保留；其中“待 F13 落地”等描述只代表旧快照。

## 当前交接：非冻结窄复验完成，最终矩阵待冻结

新独立阶段完整命令、源码摘要和逐 C 项边界见
[`verification-host-independent-v2.md`](verification-host-independent-v2.md)。
当前阻塞仅交接为：F13 回执能力不可用展示接线、core 最终 freeze、
F6 第二轮最终 freeze；不以旧版性能交接中的冻结段落替代这两方通知。
复跑环境已确认在位；`node --check tests/host/final_browser.mjs` exit 0。
本轮文档/导出物的个人路径、JWT 与私钥标记扫描零命中；
所有本轮宿主子进程已结束，没有等待中的浏览器进程。

**修订 C30 已验证降级与超时：`final-c30-single-yl7oro9e`，51 PASS / 0 FAIL，
exit 0。**真实加载 LivingEmotion 成品，用宿主 `AiocqhttpMessageEvent` +
`RespondStage` 和合成平台口；spy 只记录并继续调用真实 hook 分发器，不替换产品。
None、False、发送异常、平台返回消息 ID 被丢弃这四例均实测 after-sent 调用，
产品仍 settling。每例精确 120 秒 deadline，以受控时钟推进至 +121 秒，返回
清醒/困倦、清空 pending、同窗口不重入、平台回复尝试保持 1、主动发送口尝试 0。
无 pending 的直接计划睡眠和手动睡眠正常。typed port 原成功/错消息/跨范围/
unknown/failed 及新增 cancelled、超时后迟到成功分别报告，不计为真实投递。
**C30 当前部分 PASS：安全降级/超时/不重发通过；F13 能力不可用展示尚待落地。**

**H01/H02/H03 非冻结复验已通过：`final-h01-h03-c30-four-u75159c6`，
57 PASS / 0 FAIL，exit 0，15.296s。**真实加载 LivingEmotion、LivingHello、
LivingMemory、BiliBot 四个成品实例及宿主内建插件。
H01 公开关系接口 `status=ok/reason_code=snapshot`；
H02 原 `get_state` 读故障反例中模型口 1 次、发送口 1 次、状态块 0 份；
H03 原生管理员 `is_admin=true/control_request=admin/stopped=false`，
模型口 1 次、发送口 1 次，原叫醒断言也通过。未修改三项原断言。
原生 after-sent 的新插件注册仍为空。typed receipt 原正反例及新增 cancelled 全通过，
匹配成功仅记直接 Application 端口层；真实投递未执行。
受控 Store 时钟推进至 deadline+1：120 秒收尾取消，返回 `awake/settling_timeout`，
迟到成功不入睡，同一计划窗口不再进入 settling；没有真实等待 120 秒。
4 次非回环 DNS 被拦截，放行外部调用/真实模型/真实平台投递均为 0，
停止后新插件任务 0，隔离拷贝源码前后一致。这不是双 freeze 最终矩阵。
父修订 C30/F13 的“能力不可用展示”尚待产品落地验证，C30 暂为部分 PASS。

**C30 实测结论已可交核心（`final-c30-contract-k1twarqq`）：49 PASS，exit 0。**
这是固定宿主真实 `RespondStage`、`AiocqhttpMessageEvent`、原生 hook 分发器，
加显式合成 listener/平台发送口；没有加载产品，不计为 C30 成品成功。
平台口返回消息 ID、None、False、抛异常、超时、分段部分成功、分段全失败时，
after-sent 都调用 1 次；取消时为 0 次并向上传播取消。
成功/None/False/部分成功均 `has_send=true`，故此标记也不能证明整条成功；
平台返回消息 ID 被适配器丢弃，hook 仅见原入站 message_id、无回执 extra。
本固定宿主通用发送/after-sent 接口**不提供可证明的完整成功回执能力**。
不要用 bool/None、trace 或 after-sent 冒充 receipt；不扩大到所有平台调查。
建议产品明确该能力 unsupported，并给 pending 收尾有界且不伪造成功的保护。
本轮将继续核实当前 pending/超时行为及 typed port 正反例；实际投递仍未执行。

父已允许先执行 H01/H02/H03 针对性宿主复验，不等待 V06；
该轮将标明非最终冻结，不执行完整浏览器/三场景矩阵。

本轮标签 `final-independent-v2`；旧轮数字及原始证据全部保留，不覆盖为新结果。
尚未收到完整 core freeze；F6 仍独占存储/API/projector 性能修复，
F3/V06 的真实计数与冷却接点仍在变化。只有两方均冻结且三场景源码哈希一致，
才能形成最终矩阵。当前没有最终 hash，也没有本轮独立 PASS 清单。

**C30 需父/核心处理的宿主接线缺口：**固定宿主的
`astrbot/core/pipeline/respond/stage.py:365-406` 捕获发送异常后仍执行
`OnAfterMessageSentEvent`，因此 hook 被调用不是成功依据；
`astrbot/core/star/context.py:665-696` 明确 bool 仅表示找到平台。
aiocqhttp 的 `send_message/_dispatch_send` 等待平台调用但不向事件暴露返回回执。
正在以真实宿主类和合成平台口补窄探针，核查可用证据边界；不自行补产品。
现有 `Application.confirm_reply` typed receipt 成功仍仅是组件端口证据。

本代理仅写独占 `final_*` / `test_final_*`、本文和新脱敏验收文档；
不改产品、其他代理测试、旧插件、宿主、父规格，不提交或部署。
沟通使用本文顶部交接；所有未冻结结果明确标为准备或窄复验。

状态：准备中，未将任何 fixture 结果计为成品通过。
独立验收者未参与产品实现；仅写 `tests/host/final_*`、
`tests/host/test_final_*`、本文与独立脱敏证据。不修改产品、旧插件、宿主或父规格。

## 验收边界

- 固定 AstrBot v4.29.4，HEAD `61335414433db721b3f7ecc93f90deafe0a59d78`。
- 全新隔离 ASTRBOT_ROOT；空平台/模型配置；全部用户、人格、消息和凭据为合成数据。
- 运行期仅回环网络，禁止真实模型、平台外发与运行期子进程。
- 真实宿主加载成品、真实 HTTP 与原生 Dashboard bundle；合成事件和 sender/provider
  桩单独标记，`send_message` 的 bool 结果必须保持 unknown。
- 原始运行日志和带凭据配置仅留隔离运行目录；交付只包含脱敏断言、数量及源码哈希。
- 当前 INTEGRATION 仍标记核心收尾中。准备工作不代表最终版本验收。

## 检查矩阵

| 阶段 | 风险 / 检查点 | 预期与失败处理 |
| --- | --- | --- |
| 成品加载 | C01/C03/C04 | 独立加载、三次 reload 单任务、停止无写回；失败阻止完整宿主兼容声明 |
| 原生请求 | C05/C06/C08/C18/C31/C39/C52 | 原生人格、唯一状态、三记忆模式、聊天与可用性；失败留最小复现给核心负责人 |
| 消费者组合 | C40-C43 | 四个真实实例、加载顺序、冲突退让；mock 注册不计四实例 |
| 私密管理 | C45/C46/F1 | 五 handler × legacy/v1 的合法与非法身份、原生配置 CAS；失败阻止页面私密验收 |
| 页面 | C44/C47/C48/C64/C65 | 原生 iframe+bridge、七区×双主题×390/1280、键盘与对比度 |

目标为本次负责检查点 100% 有实际证据或明确未验原因，而不是代码覆盖率百分比。
每轮运行有超时和资源清理；基础设施错误与产品断言失败分开记录。
没有 CI 历史，不能报告 CI p95；本地实际耗时随结果记录。
不采用重复运行直到通过；发生同输入复跑分歧时记录为不稳定并交负责人，48 小时内明确修复或
保留未验，不能静默隔离后宣称通过。每轮记录成品哈希，旧产物不可满足新代码验收。

## 问题与实际结果

初验运行 `final-single-bl0jk1do`：成品宿主/HTTP **160 断言通过，0 失败**。
真实登录、原生 iframe/bridge 与前 13 组布局已执行；浏览器 **15 通过、1 失败**后
遇宿主首次公告遮挡终止。不能将本轮称作浏览器完整通过。
旧运行器遗漏将浏览器非零退出传回父结果，已在独占运行器中修正。
宿主首次公告现按正常 UI 关闭，不修改宿主或插件页。

测试基础设施校正（不作为产品失败）：PersonaManager 不存在时抛 ValueError；
AstrBotConfig 文件有 UTF-8 BOM；Bot ID 是完整来源哈希而非裸 self_id；
人格 A→B→A 后必须重取修订上下文，旧修订被成品拒绝符合预期。
原始失败运行报告仍留隔离目录，没有重写或冒充全绿。

2026-11-05 最新轮 `final-single-83l80one`：

- 浏览器 **38 通过 / 0 失败，28 组完整布局，0 pageerror**。390px 为 iframe 实宽
  390；1280px 原生 Dashboard 保留侧栏，iframe 稳态实宽 1027。早先记录的 149px
  是宿主侧栏断点动画中间帧，不是390页面。现等待原生布局完成后测量。
- 原生首次公告用可见关闭按钮关闭；切换、分区及键盘测试不使用 DOM 修改或合成 bridge。
- 原生 iframe sandbox=`allow-scripts allow-forms allow-downloads`，存储不可用；
  页面显示“仅本次页面有效”，刷新回系统主题。不能声称原生 iframe 已证明持久偏好。
- 非回环页面请求 `cloud.astrbot.app`（宿主请求）被测试路由拦截，未放行；没有外部 CDN
  给插件提供资源。
- 同轮宿主 **160 通过 / 1 失败**：`C39.get_relationship`，正在定位返回码。
  前一快照通过不覆盖本轮失败，暂不通过 C39。
- 四真实实例加载初验 `final-four-mhv8oy5v` 已实际加载 LivingEmotion、LivingHello、
  LivingMemory、BiliBot；160断言通过。但尚未据此宣称完整普通回复pipeline通过。

### 阻断 H01：成品公开关系接口失败（C39）

最新独立复现 `final-single-rq8tg3qv`，**159通过 / 1失败**，退出码2。
真实插件管理器加载成品，三reload后通过真实原生人格与合成消息产生12条互动，
依次调用公开 `get_bot_state/get_observation/get_relationship/get_availability/preview_behavior`。
仅 `get_relationship(current_context)` 返回
`{"api_version":1,"status":"unavailable","reason_code":"storage_failed"}`。

准确锚点：`api.py:187-191` 的关系分支调用
`self._application.current_relationship(scope, record=record)`；
当前 `runtime/` 无该方法定义，Application 继承链未提供此方法。
异常由 `_snapshot` 宽异常分支转为 `storage_failed`。
请父代理分配核心集成者补齐真实关系投影接线后通知复验，不在验收代码 monkeypatch 修复。

复现（工作区根）：

```bash
.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist
```

### 阻断 H02：存储故障中断原生普通聊天（C52）

四真实插件 `final-four-_t3vbe99`，实际 PipelineScheduler 全部9阶段，Provider/发送
端口为显式合成桩。正常消息：模型1次、回复1次、状态块1份。
在同一成品 Store 的 `get_state` 注入 `OSError("synthetic storage read failure")` 后，
模型0次；唯一发送是宿主插件错误信息，不是普通回复，event 被停止。
这是真实失败注入，不是替换插件或跳过失败。

锚点：`main.py:44-46` 调用 `application.availability` 无异常降级；
`runtime/application.py:257` `night_snapshot` 的 get_state 异常穿透。
宿主 `pipeline/process_stage/method/star_request.py:90-125` 捕获后发送错误、stop_event，
因此不能依赖宿主兜底来满足“故障省略补充、原生对话继续”。
复现：上述命令加 `--scenario four`；断言 `C52.read_fault.one_provider_call` 为0。
验收代理不改产品；请父分配核心修复并保留本故障断言。

### 待复核 H03：四插件管理员睡眠豁免

同轮 `C31.native_admin_exempt` 失败，`/le_wake` 真命令通过。
疑似接点：LivingEmotion `main.py:42-43` 认 `event.is_admin()`，
但 LivingHello `guard_livingemotion.py:84` 只认 `livingemotion:control_request`；
入口没有把已认证管理员转成该可信 extra。正在补原生管理员role/调用数证据，
不以源码推断直接宣称最终根因。

本轮测试基础设施错误另记：BehaviorResult 字段应为 reason_codes；
BiliBot 注册名为 astrbot_plugin_bilibili_ai_bot；原生 Provider 会把 system prompt
放进 contexts 的 system message。已修独占测试，不修改产品，不把原报告改成通过。

H03 已于 `final-four-d21w6ng3` 独立复核：原生 admins_id 配置匹配，
`event.is_admin()=true`，但 `control_request=null`，event stopped=true，
模型0次、发送0次。对应 C31 组合失败；实际 `/le_wake` 命令仍通过。
父应将修复交核心/消费者边界负责人，不能在测试里手填可信 extra 冒充宿主接线。

该轮175通过/5失败；C06 已证明生成输出后切换原生人格导致 cancelled/context_changed、
模型桩1次/发送0次，旧范围状态保留。四真实实例正常pipeline三项通过，Bili真实
消费者优先新API并 accepted 公共中性事件；消费者/新插件交错reload后重发现通过。
额外发送 bool 用例在复用旧事件后 cancelled，尚未归因，不能计通过；下一轮使用
人格恢复后的新来源事件并保留结果原因。H01/H02/H03均未掩盖。

## 扩展宿主验收（冻结前，非最终 PASS）

`final-conflict-aib5zqwq`：**207通过/2失败，27.712s**；失败仍为 H01/H02。
另一个没有从绫的 four 场景仍有 H03，冲突场景通过不能覆盖该失败。
本轮真实实例为新插件、LivingHello、LivingMemory、BiliBot、从绫及宿主内建插件；
旧插件的降级路径保持原实现，没有拿 mock registry 等同五实例。

- 普通 pipeline 完整执行宿主9阶段，合成 Provider/平台发送口；一次模型、一次回复、
  唯一状态块与原生人格。未覆盖真实图片/TTS/节奏外发，不代表生产平台投递。
- 人格恢复后用新来源事件，真实 `Context.send_message` 找到合成平台并返回 True；
  行为结果 unknown/send_unconfirmed，1次发送，同 intent 再执行不重发。
- BiliBot 成品 `_apply_reply_result` / `_apply_private_reply_result`，
  仅替换平台发送口并对桥函数注入异常。两条流程各1次合成发送、好感+2写入原文件、
  positive_interactions=1。真实 EventRuntime/本地写者/记忆写入保持，未替换插件实例。
- C58：原生 `PluginManager.turn_off_plugin` 后所有新插件任务停止，
  Bili自动选择真实从绫 emotion 实例；目标数据字节在迟到消息后不变；
  新 Store 重新打开目标库，emotion记录 **25→25**。没有执行生产回滚或整库恢复。
- C30：真实 LLM response 钩子和 after-sent 钩子（合成 send 返回 None/True/False）
  均不让 settling 结束。真实 Application 的 typed receipt 端口拒绝错误消息、
  其他范围、unknown、failed，只有匹配 succeeded 才 asleep。
  **新插件实际 after-sent 注册列表为空**；confirm_reply 尚无已证明的原生成功回执
  接线，因此成功路径仅属直接端口层，C30完整宿主成功路径仍未验。
- external 显示 background_authorization/idempotent_export unsupported，无后台材料；
  当前运行使用关闭读取的默认配置。开启读/导出仍拒后台能力的补充断言待最终冻结轮。
  C14 的真实跨平台绑定/解绑正例未执行，不用降级状态替代身份聚合能力证明。

### 原生页面扩展结果

同轮 **40通过/0失败、28布局、0页面异常**。七分区×双主题×390/1280，
本轮每个分区展开真实配置控件后测量；正文最低 **5.8367:1**、
关键控件最低 **3.6703:1**。所有可见按钮有文字/ARIA标签、高度至少44px。
键盘焦点轮廓>=2px；浏览器保存 local_lite 并刷新后仍从服务器读到该业务配置；
切换主题与导航期间无业务写请求；记录确为10条，来源详情默认折叠。
已人工查看390白昼及1280黑夜原生截图：自有文字标识、编号、细线、留白与
黄绿色强调存在，无厚重嵌套装饰，Bot感受和对方观察分别展示。

原生iframe存储不可用，明确“仅本次页面有效”，刷新按系统dark回退。
**业务配置刷新保留已经通过；主题偏好刷新保留没有证明，不能混写。**
宿主cloud.astrbot.app请求被拦截；插件无外部CDN。没有修改sandbox绕过此限制。
宿主checkout `git status --short` 为空。

## 逐项交接矩阵（待最终冻结轮更新）

| C项 | 当前结论 | 已验证 / 边界 |
| --- | --- | --- |
| C01 | PASS（旧快照） | 单插件真实加载、无旧插件必需依赖；最终冻结后需重跑 |
| C03 | PASS（本轮） | 三reload单任务/五routes、数据目录、停止无写回 |
| C04 | PASS（本轮限定） | v4.29.4页面/人格/原生发送API；bool=unknown，未证明真实投递 |
| C05 | PASS（本轮） | 原生人格一次、Bot来源与人格分离 |
| C06 | PASS（本轮） | 生成后原生人格切换取消旧发送、旧状态保留 |
| C08 | PASS（本轮） | 规则互动/trace/表达，观察不注入、不自主，总开关停任务 |
| C18 | PASS（运行矩阵） | none/local_lite/external切换不关闭情绪、关系、长夜 |
| C30 | 未验（成功接线） | 原生无回执不入睡通过；typed成功仅直接Application端口 |
| C31 | FAIL | H03四插件管理员豁免；默认睡眠、显式阻断、真实叫醒通过 |
| C39 | FAIL | H01关系接口未接；其余v1门面和真实Bili ingest通过 |
| C40 | PASS（已测路径） | 真实Bili优先新提供者；停用后选从绫，旧上报未执行外发 |
| C41 | PASS | 真实评论/私信应用流程桥异常，本地写者与一次合成发送保留 |
| C42 | PASS（普通文本） | 四真实实例完整pipeline一次状态/一次回复；图像/TTS未投递 |
| C43 | PASS | 真从绫同范围观察退让、交错reload重发现，无自主资格 |
| C44 | PASS | 原生iframe+bridge七区、主体分离与来源/原因 |
| C45 | PASS | 原生API/文件同步、浏览器保存刷新、CAS、10条及默认折叠 |
| C46 | PASS | F1五handler×两路由，10正例/80负例，admin=true无权限 |
| C47 | PASS | 28布局、390/1280、键盘、文字状态和可见控件 |
| C48 | PASS | 原生模拟0模型/0发送，与真实动作分开，无Bot Manager/CDN依赖 |
| C52 | FAIL | H02读取故障逃出钩子，原生普通回复被插件错误替换 |
| C58 | PASS（隔离演练） | 原生停用→消费者回退；库25条新记录保留，不是生产回滚 |
| C64 | PASS | 原生截图人工核对留白/细线/编号/黄绿/自有字标 |
| C65 | PASS（异常路径限定） | 双主题/对比度/零业务写；原生主题存储失败回退，未证明持久偏好 |
| C14 | 未验 | 原生来源隔离可读，真实跨平台绑定/解绑未覆盖 |
| C19-C21/C27 | 部分PASS | 外部后台/幂等导出明确不支持，不声明真实后端检索/导出成功 |

## 命令与证据交付

以下均在工作区根运行，无生产配置、平台或收费模型；命令退出2是保留失败断言，
不是测试被跳过。每个 host.json 包含实际成品源码 SHA-256、测试 SHA-256、依赖版本、
断言、拦截操作与耗时。证据不包含运行日志、JWT、密码、主机名或本地部署路径。

```bash
# four-d21w6ng3：175 passed / 5 failed（含后续已校正的发送测试输入）
.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist --scenario four

# conflict-aib5zqwq：207 passed / 2 failed；浏览器40 passed / 0 failed
.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist --scenario conflict --browser

# 仅导出白名单结果和合成截图，不导出运行时目录
.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_export.py \
  .livingemotion-host-t1/runs/final-four-d21w6ng3 \
  .livingemotion-host-t1/runs/final-conflict-aib5zqwq \
  .livingemotion-host-t1/runs/final-single-83l80one
```

交付目录：`tests/host/final_evidence/`，每个run独立子目录与manifest；
上述原始失败数字保留，不把不同快照拼成全绿。当前新增的
`enabled_external_still_no_background_export` 断言仅准备完毕，尚未计入任何通过数字。
浏览器脚本 `node --check` 通过。所有本轮host/server/browser进程均已结束。

### 下一轮入口

父确认核心 `current_relationship`、H02/H03 及整套产品冻结后，先记录冻结源码哈希，
再用同一冻结源完成 single、four、conflict 三个场景；至少一个场景启用 `--browser`。
不只重跑失败用例：关系/入口变更会影响正常pipeline、三reload、原生配置、F1和页面状态。
每轮以独立拷贝的 source_hashes 为准，必须核对三个场景新插件哈希一致，再出最终表。
本次**不是冻结版最终full验收**，不得勾 C63 或据此发布。
验收代理只写独占final_*测试/证据及本文，未改产品、旧插件、宿主、父规格或Git。
