# P8 独立四版宿主验收

日期：2026-11-06。职责：独立验证，不实施产品。
依据：已批准的 `LivingEmotion-复古未来主义与生活状态改版计划-20261106.md`。

## 当前状态

**最终同一冻结清单在四版全部PASS。首轮及后续定位失败保留于历史区，不作为通过证据。**

最终清单：`.livingemotion-retro-host/freeze-20261106-parent-layout-final.json`。
汇总：`final-summary-1793974288133772000.json`，`four_version_final_acceptance=true`。
产品源SHA256：`802dc2f3f075091396e22fce2c1798a5e8cf97c671f6af64ca248121eeea3bb5`。
浏览器脚本SHA256：`a2e633cea5c0496b19c512acb46e0cd0dbeb4ee50e65bffa7dec86fa3bc22c68`。
Chrome `156.0.8078.80`。上述清单及原始报告仅本地保留。

| 宿主 | 宿主检查 | 浏览器检查 | 真实视图 | 报告目录 |
| --- | --- | --- | --- | --- |
| v4.29.1 | 424 PASS | 159 PASS | 36 | `final-v4.29.1-8g6n4nvi` |
| v4.29.2 | 424 PASS | 163 PASS | 36 | `final-v4.29.2-x66z98zo` |
| v4.29.3 | 424 PASS | 163 PASS | 36 | `final-v4.29.3-it7t8dce` |
| v4.29.4 | 424 PASS | 165 PASS | 36 | `final-v4.29.4-6sxjwff3` |

浏览器检查包含36视图与按版本加载的资源摘要；宿主检查包含浏览器汇总断言，
这些计数不相加。四版产品副本、宿主源、Dashboard和脚本前后均不变；
真实重载、置顶HTTP与刷新、管理员撤权清空均通过，停止后产品任务为0。
每版新增五次桌面/手机与双主题往返，等待原生侧栏布局稳定后普通点击，
不用force、点击重试或键盘替代。失败时保留父/子pointer事件和几何证据。
没有真实模型调用、生产平台投递或生产部署；远端CI以仓库交付记录为准。

- [x] 核实已有 v4.29.4 宿主、Python 3.12 和依赖。
- [x] 使用 `gh repo view/api/clone` 获取并核对 v4.29.1、v4.29.2、v4.29.3。
- [x] 新建 `tests/host/retro_*` 独立入口，不导入旧 host 验收脚本。
- [x] 四版真实宿主 core 初始化、原生人格、真实调度/流式反例、原生 Provider 合成 transport、真实登录、fixture 重载和清理准备探针。
- [x] 验收基础设施完整性自测 6 项通过。
- [x] 获取 `.1/.3/.4` 官方 Dashboard 并校验发布摘要；`.2` 按准确 tag 源和锁文件隔离构建。
- [x] 新增睡眠五档、跨午夜、低精力骰点/幂等/真实重载持久化、管理员沉睡唤醒、期限与失败计轮入口，尚未执行产品。
- [x] 按明确候选 `0.2.0` / `>=4.29.1,<=4.29.4` 真实加载四版，不绕过门禁。
- [x] 首轮冻结产品源、验收脚本及四版 Dashboard 清单，核对实际加载副本。
- [x] 完整 native runner、末级 hook、ticket、窗口和精力矩阵通过。
- [x] 十 console 入口全部通过：保留首轮空 selection 解析失败。
- [x] stop/reload 通过：保留首轮重载与worker失败。
- [x] 接入新 `retro_browser.mjs` 与四版真实 Dashboard，不使用七区旧脚本或合成响应替代。
- [x] 九区 iframe 双主题交互通过：每版36真实视图，首轮0视图失败保留。

旧 `tests/host/evidence-v4.29.4.json`、`final_*` 和既有验证文档不是本轮通过证据。
准备报告中 `product_executed=false`、`final_frozen_acceptance=false`。
`four_version_final_acceptance` 只有同一冻结产品源在四版全部成功才为 true。
当前任何准备计数都不代表产品四版加载或新页面/API 已通过。

## 环境与身份

工作区用环境变量 `WORKSPACE_ROOT` 指定；仓库相对路径为 `插件/astrbot_plugin_livingemotion`。
新隔离环境：`.livingemotion-retro-host/`，每次运行建立新的 0700 根目录。
v4.29.1–.3 源位于其 `hosts/<tag>/`；v4.29.4 复用只读的
`.livingemotion-host-t1/AstrBot/`。不修改宿主仓库源。

Python 入口：`.livingemotion-host-t1/venv/bin/python3.12`。
实际 Python：3.12.16。复用 155 个已安装 distribution，无增量安装。
共享只读依赖环境不代表共享 AstrBot 导入源或数据目录。
四版分别核对 `VERSION`、`astrbot.__file__`、真实 git HEAD/tag 和 tracked 源哈希。
venv 内的 AstrBot distribution metadata 不能替代当前宿主源版本。

| 宿主 | 实际 commit | tracked 源清单 SHA256 |
| --- | --- | --- |
| v4.29.1 | `dffe922773725e9c178392c423676ad65044748c` | `faca5b92e0bbbfc361f7a57e66b46a60d25bee71bb91bb457c174cf46c770425` |
| v4.29.2 | `38fc189d58758cc9ceda8585fbdee84eabf8a13a` | `08906843c4211881be2a06e3ac25ea9a3730d65a1d186a7c356405476087490a` |
| v4.29.3 | `f61a7f42696da6df25dc7a249ec9b8d54ed9da18` | `e7a93fa6ff91d134ad2fedc3abcf592482e6dacbfd119dd0d1030b832ff3198b` |
| v4.29.4 | `61335414433db721b3f7ecc93f90deafe0a59d78` | `0d74b4f1bc864df7a564deb9e5df2eb20fa84eac03014932b538a5586a6f0d29` |

哈希定义：按 git tracked 相对路径排序，逐文件 SHA256，再对 canonical JSON 清单做 SHA256。
每份报告保留完整逐文件清单，运行前后核对 tracked worktree 与源清单不变。
产品清单含入口、配置/metadata、领域/适配/运行/存储源和本地页面资源；
不混入旧报告、测试、运行数据库或其他插件。脚本自身另有逐文件 SHA256。
最终运行核对源 HEAD、冻结清单、加载路径及加载副本运行前后哈希。
freeze 同时记录 `harness_sha256` 和四版 Dashboard 身份，final 不接受脚本或产物变化。

最近准备阶段观察到产品 HEAD 为 `699e7b6e5f8cbbda853d14f54debfb7cb1af537e`，
dirty 工作树正在并行修改。准备观察源哈希不是最终冻结产品身份。

原生 Dashboard 位于 `.livingemotion-retro-host/dashboard/<tag>/dist/`，
每版有 `identity.json` 逐资源哈希。`.1/.3/.4` 来自相应官方 release；
`.2` 没有 release，使用其准确宿主源中 Dashboard、原 `pnpm-lock.yaml`、
`pnpm@10.28.2 --frozen-lockfile` 和原 build 命令，无源码修改，不冒称官方发布包。
`.2` 不复用其他版本 Dashboard。构建日志只保留本地。

## 隔离与费用

父进程只允许固定环境变量，丢弃继承的模型密钥、GitHub token、代理和生产配置。
每次运行单独设置 `ASTRBOT_ROOT`、HOME、TMPDIR、插件目录、数据库与合成管理员密码。
不加载其他业务插件；允许宿主内置本地 webchat，不配置外部平台或真实账号。
所有 Provider/天气/记忆自动工作默认不配置真实密钥。

运行前安装 audit guard，禁止非回环 connect/bind/DNS/sendto 与运行时 subprocess。
保护自测真实验证外部 DNS、保留地址连接、wildcard bind 和子进程被拒绝。
真实 HTTP 仅绑定 `127.0.0.1` 动态端口；客户端 `trust_env=False`。
宿主模型 metadata 更新等非回环企图会被拒绝并统计，不放宽 guard。
原始日志和临时凭据仅在隔离根目录，文档/报告不保存 asset token、JWT 或模型密钥。
原生浏览器由净化环境的父进程启动，使用系统 Chrome 与已有 Playwright，
仅放行当前 `127.0.0.1` origin 的 HTTP/WS；禁用 service worker 和后台网络，
DNS/proxy 限制将外部请求封闭到回环拒绝端口。截图只存隔离目录。
脚本通过原生登录表单获取认证，使用实际 sandbox iframe、资源映射与 SDK。
不注入替代 bridge，不合成页面 API 响应；role 撤销只修改隔离宿主管理员。

合成 transport 使用真实 OpenAI chat/embedding 类和 DashScope embedding 类，
只替换 HTTP wire / SDK 调用，不用产品 Provider 类替身。
最终分支另测产品 `OpenAIBinding` 的请求预算、单次 unknown 失败，
及 `NativeEmbedding` 的原生绑定、缓存与提供者撤销。
`real_model_calls=0`，真实平台投递未执行；合成 sender 返回值不作为送达证明。

## 已发现的真实宿主边界

### 每请求流式

四版 `pipeline/process_stage/method/agent_sub_stages/internal.py`：
`process()` 开头 175–177 行读取并缓存 `event.get_extra("enable_streaming")`，
260 行按缓存值构造 runner，307 行才调度 `OnLLMRequestEvent`。
`ProviderRequest` 没有 streaming 字段。request hook 才改 extra，或动态添加 req.stream，
不是可靠的 internal 每请求禁流式接口。

可信接点是在 `observe_message` 内，进入 agent process 或任何 `yield ProviderRequest`
之前设置 `event.set_extra("enable_streaming", False)`，不改宿主全局配置。
须保证后续消息处理器不改回 true；不能在缓存值已经读取后补救。
third-party runner 的读取顺序不同：在 request hook 后才读取该 extra。
`action_type="live"` 分支无条件流式，需显式拒绝或经过确认的降级。

`ResultDecorateStage` 对 `STREAMING_RESULT` 直接返回，不执行 decorating handler；
原生 streaming 输出已发生后才生成 `STREAMING_FINISH`。
finish hook 不能作为首次提交、起窗或扣回复精力的凭据。

准备的早期定位实验已在四版真实 runner 证实：
进入 runner 前 false 走非流式；request hook 才改 false 仍走流式并提前输出。
这些是宿主时序反例，不是产品成功证据。
现行 `retro_*` 已移除全部人工 `set_extra("enable_streaming", False)`：
最终产品路径先断言原生 event 未被 fixture 改写，真实 product observer 设置 false，
全局 streaming 仍为 true，再检查真实 runner 调用模式与最终 handler 执行顺序。

### Decorating 拒绝提交

四版实际探针均显示：handler 仅 `stop_event()` 时，仍可进入 RespondStage。
decorating 是 async generator，无 yield 返回时，scheduler 外层循环继续走下一 stage。
清空 result 再 stop 才在实际发送端得到零输出。
产品必须以真实发送端零输出和未扣能量验证拒绝，不能只断言 `is_stopped()`。

真实 registry 采用优先级降序。最终产品 handler 要验证
`priority=-sys.maxsize-1`，在 `-sys.maxsize` sentinel 后执行，并且注册序列为最后。
sentinel 模拟同优先级末端消费者，不代表已加载 LivingHello 本体。
其余业务插件不在本独立隔离宿主中运行。

### 版本入口

早期准备时产品 metadata 限制 `==4.29.4`。
4.29.1–.3 的真实 plugin manager 会执行版本检查并拒绝不匹配的 metadata。
最终候选必须包含可加载的 metadata；验收不使用 `ignore_version_check` 或修改副本绕过。
新配置、十路由、actor injection 与 final ticket 均需在最终冻结源上重新验证。

当前候选由主协调明确设置为 `0.2.0` / `>=4.29.1,<=4.29.4`。
新 `gate` 和 `final` 显式核对该范围与源码注册版本，要求四版实际加载；
不再把前三版拒载当作新候选的通过口径。
候选范围配置不等于兼容证明；仅同一冻结源四版行为/API/iframe 全部通过后才能宣称支持。
`gate` 不忽略版本门禁，不属于产品行为通过，`final_frozen_acceptance=false`。

首轮 `gate` 在 `.1` 观察到实际 manager 的准确拒载原因：
`AstrBot 4.29.1 does not satisfy plugin astrbot_version: ==4.29.4`。
但同时检测到 `main.py`、`runtime/application.py` 并行修改导致产品源漂移，
第二版复制阶段停止；该轮不是四版门禁通过，也不是稳定源的验收报告。
本地原始记录：`.livingemotion-retro-host/gate-v4.29.1-bg5n9d37/report.json`。
源稳定后需要重新执行，不以单版拒载观察扩大兼容结论。

## 最终检查矩阵

| 风险/检查 | 实际执行入口 | 通过口径与失败响应 |
| --- | --- | --- |
| 四版可加载 | 真实 core/plugin manager、模块 origin、source 清单 | 不绕过版本门禁；任一加载失败交入口写者 |
| 原生人格 | 原生 PersonaManager config/conversation/forced/none 及实际 product context | 不用 fixture DTO 代替人格解析；差异交宿主适配写者 |
| 十 console 管理入口 | state/records/config/preview/action/scopes/relationships/relationship/energy/settings-options，两种 HTTP alias | 登录成功、no-store；所有身份负例 401/403，写入 CAS 重放 409；失败交 API 写者 |
| 最终回复提交 | 实际 OnLLMRequest registry、ResultDecorateStage/RespondStage 与合成 sender | 真 ticket，末级 hook、首次提交起窗，重入不续窗/重复扣能量；失败交 P3 |
| 提交前撤销 | 固定时钟到沉睡、新人消息、伪造 attempt、finish 反例 | 真实零输出，未发生首次提交/回复扣费；失败保留反例 |
| 普通唤醒/管理员命令 | native AstrMessageEvent、原生 At 组件、真实 scheduler 权限分配 | 群普通/At 他人/伪造 extra 不醒，At Bot 按 both 唤醒，沉睡仅认证管理员能手动醒 |
| 五档与持久化 | 原生消息、合成绝对时钟/随机源、真实 SQLite 和 manager 重载 | 跨午夜/午休/赖床一次、满精力不提前醒；低精力双骰后逐次+1、重复不加、重载不重抽 |
| 期限/失败 | 真实请求 hook、scheduler Provider 异常与最终 output stage | 首次提交前不起窗，599秒可提交/600秒拒绝；失败计轮，不把宿主错误文本当 Bot 回复扣费 |
| Provider 预算和失效 | 原生类+MockTransport/SDK；产品 binding | wire cap、无宿主配置污染、unknown 不重试、缓存/撤销关闭式失败 |
| stop/reload | 真实 plugin manager、旧 API 引用、任务和路由清单 | 两轮重载无任务/路由重复；停止后旧页/API 拒绝，新任务不得写回 |
| 原生九区 iframe | 每版原生 Dashboard、resources 映射、实际 SDK、真实产品 console | 九区/双主题/390与1280/键盘、主题动效与减少动态；guard 身份负例，不合成 bridge/API 响应 |
| 证据完整性 | 源/副本/host/harness SHA256、dirty/HEAD 与阶段标记 | 不接受源漂移、脚本漂移、旧报告或准备阶段成功代替产品通过 |

所有数据都是合成数据。以具名风险反例覆盖为目标，不把 coverage 百分比当业务证明。
阻塞检查不自动刷重试；不同重跑结果按 flaky 保留，48 小时内定位或明确降级，
不得在未关闭风险时宣称兼容通过。每版总预算 600 秒，浏览器预算 270 秒；超时独立记为基础设施失败。
当前样本不足以声明 CI p95；实际 case 秒数和清理结果逐报告记录。
完整 UI 合成边界、200节点性能、全量性能和 1001 条补课反例由对应验证职责承担，
不在本入口中冒称已覆盖。本入口新增原生九区 iframe 联调，不把 API 成功写成 UI 通过。

## 入口

从插件仓库执行准备入口；环境变量指向已准备的宿主 Python 和新冻结清单文件。
个人机器绝对路径不写入仓库文档。
`prepare` 不会加载产品：

```bash
"$ASTRBOT_HOST_PYTHON" -B tests/host/retro_dashboard.py
"$ASTRBOT_HOST_PYTHON" -B tests/host/retro_run.py --phase prepare
"$ASTRBOT_HOST_PYTHON" -B tests/host/retro_selftest.py
"$ASTRBOT_HOST_PYTHON" -B tests/host/retro_run.py --phase gate
```

以下两步在实现与脚本停止写入后执行；最终已按同一冻结清单完整运行：

```bash
"$ASTRBOT_HOST_PYTHON" -B tests/host/retro_run.py --phase freeze --freeze-manifest "$RETRO_FREEZE_MANIFEST"
"$ASTRBOT_HOST_PYTHON" -B tests/host/retro_run.py --phase final --freeze-manifest "$RETRO_FREEZE_MANIFEST"
```

freeze 清单只允许新文件，不覆盖旧身份。final 每版复制同一冻结清单，
任何源文件/脚本/host 变化均使该报告失效。可用 `--tag v4.29.x` 定向定位，
单版成功不能成为四版最终通过。
新一轮 `RETRO_FREEZE_MANIFEST` 必须指向新文件，不能复用失效的
`freeze-20261106-candidate-020.json`。完整 `final` 默认四版并强制含真实 iframe，
准确入口为上方 `retro_run.py`，不调用任何旧 `final_*`。
Node/Chrome/Playwright 路径不同可传 `--node`、`--chrome`、`--playwright`；
子进程 Python 可显式传 `--python "$ASTRBOT_HOST_PYTHON"`。

## 历史准备证据

移除人工 streaming 覆盖后的四版准备探针，每版 27 项通过；
基础设施自测 6 项通过。此阶段未复制或执行产品。

准备汇总：`.livingemotion-retro-host/prepare-summary-1793968485873839000.json`。
逐版报告在同目录：
`prepare-v4.29.1-2zcugduk/report.json`、
`prepare-v4.29.2-wm2hz80a/report.json`、
`prepare-v4.29.3-hhwmd798/report.json`、
`prepare-v4.29.4-naxzzxj5/report.json`。

报告保存 host/依赖/harness 和当时产品观察身份，未冻结的新产品身份只供定位。
后续最终 run 的产品源 SHA256、四版实际加载/行为/HTTP结果需另记，
不得把本节准备结果改写成全部通过。

未修改产品、现有测试或其他业务仓库；不 commit、不 push、不操作生产。
现有 `tests/host/final_checks.py` 的并行修改不属于本验证者，不撤销、不纳入本轮脚本来源。

## 首轮初步结果

首轮冻结清单：`.livingemotion-retro-host/freeze-20261106-candidate-020.json`。
产品 HEAD：`699e7b6e5f8cbbda853d14f54debfb7cb1af537e`，dirty 候选，
产品源 SHA256：`7f14f3cff47868913d563c08e62358f274be68394b51c2c59c6d77039e220bb4`。
Node 浏览器脚本 SHA256：
`4c1a40e4830fa13f955624d9f24a7d235413b0dd904054447c0edcaa366e34dd`；
Chrome `156.0.8078.80`。脚本已因验收自身修正变化，该冻结不能继续使用。

| 宿主 | 通过 / 失败 | 源前后不变 | 实际 iframe 观察 |
| --- | --- | --- | --- |
| v4.29.1 | 115 / 10 | 是 | 登录成功；等待 native iframe 超时，疑似 welcome 导航竞态 |
| v4.29.2 | 115 / 10 | 是 | sandbox/资源/SDK 已载入；state 503，授权人格仍 disabled |
| v4.29.3 | 115 / 10 | 是 | sandbox/资源/SDK 已载入；state 503，授权人格仍 disabled |
| v4.29.4 | 115 / 10 | 否 | 同上；结束检测源变化，不自动重新冻结 |

四版宿主、加载副本、Dashboard 和首轮脚本前后哈希核对不变；
最后一版产品工作树变化使整轮冻结无效。原始文件不覆盖：

- 汇总：`.livingemotion-retro-host/final-summary-1793969695144682000.json`。
- `.1`：`final-v4.29.1-zjkjfzra/report.json`。
- `.2`：`final-v4.29.2-3rbpoz6y/report.json`。
- `.3`：`final-v4.29.3-15uwlwbx/report.json`。
- `.4`：`final-v4.29.4-68o8ws55/report.json`。
- 各目录保留 `runtime.log`、`browser-report.json`、加载副本与完整身份清单。

已证实但不能扩大为完整通过：四版候选实际初始化、原生人格、真实末级 request/
decorating registry、非流式提交顺序、早期/晚期 live 的零 Provider 调用与零发送、
早期 live 不占轮、窗口首次提交和多个撤销反例，以及部分五档/transport 观察。
首轮未完成九区任何视图组合，不可写成 UI 已通过；身份负例与重载也未通过。

### 阻塞归类

| 首轮阻塞 | 证据与边界 | 处理范围 |
| --- | --- | --- |
| 重复合成 Provider 注册 | `ValueError: ... retro_synthetic ... 已经注册`；打断失败计轮与 native controls | 验收脚本缓存已注册类，实例仍为真实 Provider；未重新运行 |
| 空 selection | `retro_http.py` 对 `selection=None` 调 `.get` 触发 AttributeError | 验收脚本按 native scope_selection/persona 解析；未重新运行 |
| 600 秒断言 | 用例在 600 秒又注入新真人消息，可合法重开 wake session | 只修正验收时序：599 秒前入队，600 秒提交既有结果；不归为已证实产品缺陷 |
| OpenAI embedding | 原生类设置 `.model`，继承 `get_model()` 返回空 `model_name`；产品 binding 抛 `embedding_model_invalid` | 产品适配写者；不得人工 `set_model` 掩盖差异 |
| 重载与 worker | 恢复空时区后 `_night_v2()` 关闭，旧 `advance_night()` 更新 energy 未同步 v2 energy_units，抛 `energy units mismatch`；失败初始化后残留 worker | 隔离配置恢复造成的夹具污染；产品旧规则/失败初始化风险交写者，不改产品 |
| native state 503 | `.2/.3/.4` 实际资源与 SDK 200，console state 503，scope-persona disabled | 与上项空时区恢复相关；新夹具在加载前配置 UTC/v2，避免跨用例旧规则污染，不冒称产品已修 |
| `.1` 无 iframe | UI 登录 200 后未完成 welcome 导航就转插件页 | 新脚本等待真实登录路由完成；不假造桥或响应 |

新夹具明确在隔离原生配置中设置 `timezone=UTC`、`night_policy_version=2`，
这是测试五档生活规则的必要前提，不修改产品 metadata/源或真实用户配置。
首轮暴露的未配置时区/v2 存量状态重载问题仍作为残余风险保留。
修正验收脚本不扩大测试范围；需新 manifest 才能重验。
当前不启动新 CPU 负载，等待主协双模式性能 bench 与统一新冻结通知。
