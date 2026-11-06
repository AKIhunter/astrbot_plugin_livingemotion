# T11 最终独立宿主验收

**最终冻结验收完成，释放宿主/浏览器/CPU 资源及 final 测试写入权；
文档专项可立即启动，无需等待历史整理。产品与 final 测试不再写入。**
三场景结束、最终哈希一致、进程退出已确认；最终 28 项 C 矩阵和交接摘要已补齐。
末尾证据计数校验 exit 0；两份报告个人路径、JWT、令牌、私钥扫描零命中。

## 最终结果：真实宿主三场景完成

**原完整三场景全部完成：宿主 runner 697 PASS / 0 FAIL；
真实浏览器 44 PASS / 0 FAIL，28 组布局、0 pageerror；三轮均 exit 0。**
F13 实际执行 HTTP 4 项/轮，共 12/12，原生 iframe 4/4；
H01/H02/H03、C30、F1 和原布局断言均保留并通过。
截至 2026-11-05 23:55:49 UTC，三轮输入、隔离副本前后哈希全部一致；
停止后 LivingEmotion 任务均为 0，停止无写回，宿主/浏览器进程均已结束。
产品失败 0，不将 unsupported 能力或未执行真实投递改称完整能力成功。

| 场景 / run ID | runner PASS / FAIL | 浏览器 PASS / FAIL | elapsed_seconds / exit |
| --- | --- | --- | --- |
| single / `final-single-3txvcu3v` | 222 / 0 | 未安排 | 33.838s / 0 |
| four / `final-four-az7ogq76` | 230 / 0 | 未安排 | 21.501s / 0 |
| conflict / `final-conflict-fqecldcf` | 245 / 0 | 44 / 0 | 32.205s / 0 |

数字是断言执行次数，不是唯一用例数；697 含 1 条 browser 退出状态检查，
44 是 browser results 的独立检查数；28 布局已计入 44，不能再加。
本轮与历史组件/性能数不拼接。原报告内 `final_frozen_acceptance=false`
是未修改 runner 的固定字段，不是本轮冻结判定；实际三场景 `focus=full`，
冻结结论由父放行与独立前后清单支撑，原 JSON 不改写。

原断言未更改，也未重跑上述场景。哈希记录器第一次使用相对 audit 路径时，
在 JSON 已写入后打印路径发生 ValueError（exit 1）；原记录保留，
改用绝对路径、新 label `after-single-before-four-absolute-path` 成功，
未改测试源码、未将该基础设施错误计为产品失败。

父已明确授权立即执行：core 22:18:24、storage/api/projector 22:35:47、
domain/emotion 22:41:45 UTC 全部冻结；原 C51 final-03 与 window-03
结束，CPU 于 22:46:57 UTC 释放。以下旧“等待放行”文字仅保留为历史准备记录。

已于 2026-11-05 23:47:56 UTC 记录执行基线：
`runs/final-frozen-provenance-eb5oo65t/baseline.json`（隔离根内）。
Python 3.12.16、固定宿主 HEAD 已核对；未安装或重建。
新增测试侧 `final_provenance.py` 只记录输入哈希，不修改原 runner 或产品。
原完整 single、four、conflict --browser 已依次完成，不带 focus。
以下准备文本和未运行表格保留历史语义；最终结果以本节及后续最终矩阵为准。

## 最终 C 矩阵

S/F/X 分别为顶部 single/four/conflict 新 run。证据位于隔离根
`.livingemotion-host-t1/runs/<run ID>/report.json`；页面为 X 的
`browser-evidence/results.json`。PASS 仅覆盖表内实测范围，限制不伪装为成功。
本轮产品/HTTP/浏览器 FAIL 为 0。

| C项 | 最终判定 | 实测证据与必要边界 |
| --- | --- | --- |
| C01 | PASS | S 仅新插件及宿主内建插件，真实 PluginManager 初始化成功，无旧插件必需依赖 |
| C03 | PASS | S/F/X 原生数据目录、每轮三 reload 后各类任务唯一、五路由；停止任务 0、数据无写回、源码不变 |
| C04 | PASS / 限制 | 固定宿主人格、页面和 SDK 可用；真实 send_message 配合合成平台口返回 unknown，不以 bool 证明投递、不重试 |
| C05 | PASS | S/F/X 原生人格在真实 pipeline 中仅一次，Bot 与 persona 分离，原 system prompt 不替换 |
| C06 | PASS | 生成人格切换后 cancelled/context_changed、合成发送 0，旧范围状态保留 |
| C08 | PASS | 规则互动、trace 前后值、唯一状态块；观察模式无注入/自主，总开关停止业务 |
| C18 | PASS | none/local_lite/external 切换保留情绪、关系和作息 |
| C30 | PASS / 限制 | 每轮 41 条原检查通过；原生发送失败仍 afterhook，不伪确认，120 秒取消、不重发；F13 HTTP 与 iframe 实显不可用；typed 成功仅组件端口 |
| C31 | PASS | 默认睡眠不挡聊天；显式阻断、原 H03 真 admin 豁免及注册叫醒 pipeline 均通过 |
| C39 | PASS | 原 H01 get_relationship 返回 ok/snapshot，其他 v1 门面正常；F/X 真 Bili 中立上报 accepted/committed |
| C40 | PASS | F/X 真 Bili 优先且仅选 LivingEmotion；X 停用后选真实从绫 |
| C41 | PASS | F/X 真评论/私信流程桥故障仍各一次合成发送，本地原所有者好感值 2、正向互动 1 |
| C42 | PASS / 限制 | F 四个、X 五个真实成品实例；普通文本真实九阶段，模型桩 1、回复桩 1、状态块 1；无真实平台、图像/TTS 投递 |
| C43 | PASS | X 真从绫开启同范围冲突后观察退让、无自主；交错 reload 与 F/X 消费者重新发现均通过 |
| C44 | PASS | 原生登录、iframe/bridge 与七区；Bot/对方分栏、来源/原因；F13 健康说明真实页面可见 |
| C45 | PASS | 原生配置双向保存、旧 revision 409、审计；浏览器保存后刷新保留；10 条记录、详情默认 0 展开 |
| C46 | PASS | 每轮 F1 102 条，共 306；五 handler × legacy/v1，合法身份及七类非法身份、匿名 admin 输入全部原检查保留 |
| C47 | PASS | X 28 组布局、键盘/2px 焦点、可达有标签按钮；最小文字对比度 5.836687、控件 3.670319，无横向溢出 |
| C48 | PASS | 真 bridge 模拟调用返回模型 0/发送 0，无 action 请求；不依赖 Bot Manager 或外部 CDN |
| C52 | PASS | 原 H02 get_state OSError：真实 pipeline 模型桩 1、普通回复桩 1、状态块 0；未替换产品规避故障 |
| C58 | PASS / 限制 | X 原生停用任务 0、消费者回退真从绫、停用期间数据不变；重开新库记录 25→25；不等同生产回滚 |
| C64 | PASS | 人工核对 X 四张新截图：留白、细线、编号、黄绿、自有字标、无厚重嵌套层；不另加自动断言数 |
| C65 | PASS / 限制 | 原生双主题、390/1280 布局及对比度通过；禁 localStorage 显示“仅本次页面有效”，刷新回系统 dark；不声称原生持久偏好 |
| C14 | 限制 | 未执行真实跨平台 OneID 绑定/解绑；不以来源隔离替代 |
| C19 | PASS（降级）/ 限制 | 开关切换与明确能力原因通过；无真实外部检索/导出成功证据 |
| C20 | PASS（降级）/ 限制 | 已装真实 LM 仍无合格后台授权/幂等导出门面，明确 unsupported；未穿透私有引擎 |
| C21 | PASS（降级）/ 限制 | 开启 memory_read 后后台仍无材料，返回 external_background_authorization_unsupported；未验真实外部授权正例 |
| C27 | PASS（降级）/ 限制 | 开启 memory_export 后 append_experience=false、external_idempotent_export_unsupported；未伪造 accepted 或导出成功 |

### 发送边界

S/F/X 各自 41 条 C30 全部通过，共 123 次断言执行。其中每轮
26 条为真实 RespondStage/AiocqhttpMessageEvent/原生 hook 分发器配合合成
transport 和 Store 时钟：None、False、发送异常、消息 ID 被适配器丢弃四例
均实际调用 after-sent，却保留 settling；deadline 精确为 120 秒，推进到
deadline+1 后取消并清空 pending、回清醒/困倦、同窗口不重入，
每例回复尝试保持 1、主动发送尝试 0。无 pending 计划睡眠和手动睡眠通过。
这不是实际等待两分钟，也不是实际平台成功投递。

错消息、跨范围、unknown/failed/cancelled 与超时后迟到 succeeded 均不入睡。
匹配 succeeded 入睡仅为直接 Application typed receipt 组件端口证据。
不将 LLM 完成、after-sent、bool/None 或 has_send 转述成可靠确认。

F13 每轮 legacy/v1 各有唯一 `reply_confirmation=unavailable`，
HTTP 4/4 × 3；X 原生 iframe 的 390/1280 × light/dark 为 4/4。
真实 HTTP 与可见健康行均包含：
“unsupported：当前宿主无可靠回复确认；收尾 120 秒超时取消，
不将 after-sent/bool/None 视为发送成功。”

### 共同输入与前后哈希

下列 SHA256 是排序清单的摘要；产品清单采用原 runner 复制范围的全文件字节，
测试/宿主采用原 `hashes` 的源码扩展名范围，Dashboard 为既有 bundle 全文件。
这与父性能报告的 4898 项扩展清单口径不同，不冒充同一个清单。

| 输入 | 文件数 | SHA256（三轮前后同值） |
| --- | --- | --- |
| LivingEmotion 复制范围 | 1147 | `17bf1ddc3eb29d8443a9b270955452dc6138f43a1950fe78e3ac87dc1f6fc47c` |
| LivingHello 复制范围 | 33 | `8f61b1b689e822ccb1c0b3372b408c7500a7869a58022ea9124e4e170283e1cd` |
| LivingMemory 复制范围 | 229 | `c8d3de04fc9eafd51cbc8e07523965a75386af27dcf64eb89f3d0b9da450d913` |
| BiliBot 复制范围 | 101 | `841616e5e830d5d70856987aadd903f9099c785aac5c6ba350aea9d74479a0bf` |
| 从绫复制范围 | 127 | `a8285ed8d208c992b7a130fb3bd593774ac6c594cc2562d221e5ce56f040296f` |
| tests/host | 16 | `ff39eb8d4d502cd592e34802e99558fc40734387e879afddfb95e76b59047189` |
| 固定宿主源码 | 1032 | `21870864ef0b2ab6e7378f917ad80fb31b1e49aad33434e300be3d9362892d21` |
| final-dashboard/dist | 311 | `060414d679c2d7350bb393d3991394eab465e60f2131c54a65f079979c7d84ba` |

清单目录：`.livingemotion-host-t1/runs/final-frozen-provenance-eb5oo65t/`。
S：`baseline` → `after-single-before-four-absolute-path`；
F：该后置清单 → `after-four-before-conflict`；
X：该后置清单 → `after-conflict`。均 `changed_inputs=[]`、
`run_tests_match=true`、全部 `run_products_match=true`、
`run_source_before_matches_after=true`；每轮 report 中原 `C03.source_unchanged`
也通过。首次失败的 `after-single-before-four.json` 保留，不覆盖；
其错误只是输出路径显示，后续使用绝对 audit 路径，不重跑产品场景。

### 资源、隐私与历史

运行期只允许回环，真实模型调用 0、真实平台投递未执行（0 次）、
外部网络放行 0。三轮分别拦截非回环 DNS 3/3/6 次及运行期 subprocess
各 1 次；浏览器拦截宿主 cloud.astrbot.app XHR 1 次。
三轮停止后 LivingEmotion 任务均为空；stop 无写回断言通过，
父进程已回收宿主子进程，Chromium 已 close；进程匹配检查无残留。

Chrome 156.0.8078.80 / Node v25.6.0；390px iframe 实宽 390，
1280px 宿主含侧栏、iframe 稳态实宽 1027。四张新截图只用于 C64 人工视觉核对。
原生 iframe sandbox 为 `allow-scripts allow-forms allow-downloads`，
本次主题临时有效；业务配置服务器保存刷新成功与主题存储是不同证据。
历史 `tests/ui/evidence/browser-results.json` 合成可存储场景 12/12、
pageerror 0 另列保留，未在本轮重跑或加入 44。

原始配置、随机凭据、日志、报告及截图保留在仓库外隔离 runs，
不导出到产品或提交目录；本文只列相对路径和脱敏结果。
历史 H01/H02/H03、浏览器失败及本次记录器 ValueError 均保留；
本轮未修产品、未改旧插件/宿主/父 Spec，未删减断言或择优复测。
无安装、重建、部署、提交或 Git 写操作；启动前曾在非 Git 工作区误运行一次
只读 `git status --short`，exit 128、无修改，此后未运行 Git。
未重跑组件或性能；父交接的组件 1273/1273 不计入上述宿主数字。

## 历史准备：交接与门禁

**状态：静态准备完成，等待父明确开跑；不是最终验收通过报告。**
任务日：2026-11-05。标签：`final-host-frozen`（尚无运行）。
没有可用的父代理消息工具，本文与 `verification-host.md` 顶部作为准备完成交接。

核心 22:18:24 UTC freeze 已由 `INTEGRATION.md` 核对。性能代理
`emotion_latency_last_mile` 仍独占 CPU 与 storage/api/projector；
只有父明确通知“性能冻结且原完整 benchmark 已结束，可以开跑”后才执行。
源码哈希暂时不变、其他报告新增结果均不能替代该通知。
本阶段未启动宿主、浏览器、pytest、benchmark，没有新 run ID。

验收者未参与产品实现。本阶段只追加 `tests/host/final_checks.py`、
`tests/host/final_browser.mjs` 的 F13 检查及两份宿主报告，保留所有原断言。
不改产品、旧插件、宿主、父规格；不执行 Git、部署、真实模型或平台发送。

## 环境与执行

复用隔离 `.livingemotion-host-t1/`，不重建、不安装依赖：
AstrBot v4.29.4，HEAD `61335414433db721b3f7ecc93f90deafe0a59d78`，
既有 Python 3.12.16 venv、`final-dashboard/dist`、`runs`。
解释器/宿主运行期身份将在放行后的报告中再次记录，当前不冒充已实测。

下列命令仅为待执行入口，从工作区根运行；必须顺序执行，不带 `--focus`。
浏览器执行前加载 TRAE-browseruse。原 runner 每次创建新隔离根及 run ID，
保留全部失败结果，不覆盖、不反复择优。

```bash
.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist \
  --scenario single

.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist \
  --scenario four

.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist \
  --scenario conflict --browser
```

| 场景 | 新 run ID | 产品/HTTP 断言 | 浏览器断言 | 耗时/退出码 |
| --- | --- | --- | --- | --- |
| single | 未运行 | 0 执行 | 未安排 | 未产生 |
| four | 未运行 | 0 执行 | 未安排 | 未产生 |
| conflict | 未运行 | 0 执行 | 0 执行 | 未产生 |

以上 0 是未执行计数，不是 0 FAIL 或 PASS。没有本轮冻结源码摘要；
不能把不同快照的历史通过数拼成最终结果。

## 风险检查

| 阶段 | 风险与门禁 | 失败响应 |
| --- | --- | --- |
| 静态准备 | 追加 F13，不删除 H01/H02/H03、C30 与原 F1/页面断言 | 不改产品补假数据；留给所属修复者 |
| 放行前 | 性能 CPU 独占、存储/API/projector 仍可变化 | 等父明确通知，不抢跑或探测启动 |
| 发布前宿主 | 原单插件、四实例、冲突三场景全量检查 | 任一失败保留 run ID、源码及失败名，不声明全绿 |
| 发布前 HTTP | 两路由真实登录后的 health 唯一条目与中文原因 | F13 不可用状态或说明缺失即阻断相关项 |
| 发布前页面 | 原生 iframe，四种尺寸/主题组合中健康说明可见 | 不以源码、HTTP JSON 或合成 UI 代替页面通过 |
| 证据一致性 | 工作区与隔离源前后、三场景共有产品源一致，测试源一致 | 任一变动不汇总为冻结版；交父协调新冻结 |
| 启动与清理 | 原生加载、reload 单任务、停用无写回、子进程结束 | 基础设施错误单列，禁止残留负载影响后续任务 |
| 生产/外部 | 不部署、不放行外部网络，不调用真实模型/投递 | 不执行，不计生产成功 |

保持原 runner 的启动/HTTP/browser/停止超时，不为缩短执行时间使用窄 focus。
实际 wall time 取每轮 `elapsed_seconds`；无 CI 历史，不报告 CI p95 或虚构预算达标。
超时保留原始输出并停止子进程，检查资源清理后交父，不能删掉耗时检查换绿。
目标为本次负责 C 项 100% 有实测证据或明确限制，而非代码覆盖率数字。
同输入重复结果分歧率目标 0%；一旦分歧即标记不稳定，48 小时内由父协调修复或
注明期限和未验边界，不重跑到绿。旧失败作为不回退基线保留。
不在本通道新增安全/依赖扫描或性能测试，已有专项结论由父汇总，不代验。

### F13 新增检查

- HTTP：`F13.legacy.reply_confirmation_unavailable`、
  `F13.v1.reply_confirmation_unavailable` 检查真实 200 响应中仅一个
  `name=reply_confirmation` 且 `status=unavailable`。
- HTTP：两条 `F13.<route>.reply_confirmation_chinese_reason` 检查
  `unsupported`、当前宿主无可靠回复确认、收尾 120 秒超时取消、
  不将 after-sent/bool/None 视为发送成功。不是直接调用 Console 的组件证据。
- 页面：`F13.reply_confirmation_visible_<width>_<theme>` 共 4 项，
  用真实 iframe 总览的健康行，检查可见的“不可用”和上述中文原因。
  不注入 health、bridge、localStorage 或产品 DOM。

新增 4 项 HTTP 与 4 项页面检查目前均未执行，不预填最终通过数。

静态校验已实际执行：既有 Python 仅用 `ast.parse` 解析 `final_checks.py`，
`node --check tests/host/final_browser.mjs` 仅解析 JavaScript，两者 exit 0。
没有导入产品或启动浏览器。本文与 `verification-host.md` 的个人绝对路径、
Bearer/JWT、私钥、GitHub token 标记扫描零命中（`rg` exit 1 表示无匹配）。
这些静态结果不计入上述产品/HTTP/浏览器断言数。

### C30 分布式边界

继承原 `final_c30_product.py`：真实 RespondStage、AiocqhttpMessageEvent 和原生
hook 分发器，平台口使用合成桩。None、False、发送异常、返回消息 ID 被丢弃分别报告；
即使 after-sent 调用，产品仍不得结束 settling。每例 deadline 恰为 120 秒，
受控 Store 时钟推进至 deadline+1，取消回清醒/困倦、清空 pending、
同一窗口不重入、合成回复尝试保持 1、主动发送尝试为 0。不真实等待两分钟。
无 pending 的计划睡眠、手动睡眠另列，不能说成回复确认成功。

继承 `final_boundaries.py`：错消息、其他范围、unknown、failed、cancelled 不入睡，
超时后迟到成功不入睡；匹配 succeeded 的成功只属直接 Application typed receipt
端口，绝不宣称真实宿主投递成功。历史契约探针的分段/超时/取消结果保留为旧层次。

## 逐项矩阵

“待运行”均表示最终矩阵被开跑门禁阻断，不是已知产品失败或 PASS。

| C项 | 本轮状态 | 待验证或限制 |
| --- | --- | --- |
| C01 | 待运行 | 只装新插件与宿主真实加载，无旧插件必需依赖 |
| C03 | 待运行 | 数据目录、三 reload 单任务、停止无写回、源码不变 |
| C04 | 待运行/限制 | 固定版本页面/人格/发送 API；bool 仅找到平台，不等于投递 |
| C05 | 待运行 | 原生人格一次，Bot 主体和 persona 分离 |
| C06 | 待运行 | 生成人格切换取消旧发送、旧范围状态保留 |
| C08 | 待运行 | 规则互动与 trace/表达、唯一状态块、观察和总开关 |
| C18 | 待运行 | none/local_lite/external 不关闭情绪、关系、作息 |
| C30 | 待运行/限制 | 原生回执 unavailable、120 秒取消和不重发；typed 成功单列 |
| C31 | 待运行 | 默认睡眠不挡聊天；保留 H03 真 admin/真实叫醒原断言 |
| C39 | 待运行 | 保留 H01 公开关系原断言，其他 v1 门面及真实 Bili 上报 |
| C40 | 待运行 | Bili 只选一个提供者、优先新插件、停用后选真实从绫 |
| C41 | 待运行 | 桥故障时评论/私信仍一次合成发送、本地好感原所有者写入 |
| C42 | 待运行/限制 | 四真实实例九阶段普通文本一次注入/回复；图像/TTS 未投递 |
| C43 | 待运行 | 从绫冲突观察退让、不自主、交错 reload 不缓存旧实例 |
| C44 | 待运行 | 原生 iframe/bridge 七区、主体分离、来源/原因、F13 健康 |
| C45 | 待运行 | 原生配置 CAS、页面保存刷新、10 条、默认折叠 |
| C46 | 待运行 | 五 handler × legacy/v1，原有效/无效身份矩阵不减 |
| C47 | 待运行 | 390/1280、键盘、文字状态、操作可达和对比度 |
| C48 | 待运行 | 真实 bridge 模拟零模型/发送，不依赖 Bot Manager/CDN |
| C52 | 待运行 | 保留 H02 get_state 的 OSError；普通聊天继续且省略状态 |
| C58 | 待运行/限制 | 原生停用、消费者回退、重开新库记录保留；非生产回滚 |
| C64 | 待运行 | 新截图核对留白/细线/编号/黄绿/自有字标，无厚重套层 |
| C65 | 待运行/限制 | 原生双主题/布局/对比度；禁存储时仅本次有效、刷新回系统 |
| C14 | 限制 | 不覆盖真实跨平台 OneID 绑定/解绑；不以来源隔离冒充成功 |
| C19 | 待运行/限制 | 开关独立与明确降级；没有真实外部检索/导出成功证据 |
| C20 | 待运行/限制 | LM 后台检索/导出缺合格门面应明确 unsupported，不能穿透私有引擎 |
| C21 | 待运行/限制 | 开启读取仍无后台材料；缺真实外部来源/最终授权正例 |
| C27 | 待运行/限制 | 开启导出仍不支持后台幂等导出，不伪造 accepted 或成功记录 |

## 历史层次与隐私

| 历史证据 | 已有结果 | 不可替代项 |
| --- | --- | --- |
| `final-h01-h03-c30-four-u75159c6` | 57 PASS / 0 FAIL | 非最终冻结；不能替代三场景 |
| `final-c30-single-yl7oro9e` | 51 PASS / 0 FAIL | 非最终冻结；没有新 F13 HTTP/页面 |
| `final-c30-contract-k1twarqq` | 49 PASS / 0 FAIL | 宿主契约加合成 listener，无产品实例 |
| `tests/ui/evidence/browser-results.json` | 历史合成可存储场景 12/12，页面异常 0 | 不等于原生 iframe，不能证明其主题偏好可持久化 |

原生 iframe sandbox 禁 localStorage 的“仅本次页面有效、刷新回系统”和
合成可存储场景的主题持久化必须分开。业务配置服务器保存刷新与主题存储也分开。
旧完整运行的 H01/H02/H03 失败与早期浏览器失败继续保留在
`verification-host.md`，不删除或改写为成功。

仅使用合成身份/人格/消息与模型、平台发送桩，运行期只允许回环网络。
实际外发/模型/投递数量须由新 run 证据填入；本阶段未执行，真实外发为 0。
原始配置、随机凭据、日志、JSON 和截图留本地隔离 runs，不提交；
交付报告只记相对路径、脱敏断言、实际计数与源码摘要，无个人绝对路径或真实凭据。
本轮不运行旧 exporter，不将原始证据搬入交付目录或覆盖旧报告。
最终汇总以三场景新报告核对的共同源哈希和各自前后完整清单为准；
本报告不能作为 C63 或私有 GitHub 已交付的证明。
