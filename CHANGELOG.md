# 更新日志

本项目遵循语义化版本规范：热修与小补丁只升第三位，兼容新增升第二位，破坏性变更升第一位。

## 未发布

### 🔧 改进

- 近 3 天诊断包可区分梦境跳过原因、晚安并入失败阶段，以及后台调度最近一次成功和故障位置。
- 设置快照补齐睡眠、晚安、补答和日记梦境相关设置。诊断包新增日记与梦境的归档、手动任务、最新自动结果和尝试预留数，不附正文或原始通知号码。

### 🧩 兼容

- 仍从控制台顶部点击「导出诊断日志（近3天）」。无需修改配置或迁移数据库；晚安、梦境和调度的原有行为保持不变。各字段的含义见[诊断日志](docs/diagnostics.md)。

## 0.10.2 - 2026-11-27

### 🐛 修复

- 情绪不再长期停在「满足 + 警觉」：模型分析把基准抬高后，基准此前只升不降，情绪一直钉在高位。现在被抬离默认值的基准按 12 小时半衰期回到默认值，四个维度共用；基准贴顶时，约 8 小时后不再显示「警觉」，约 27 小时后不再显示「满足」。没被模型分析写过的状态行为不变。

### 🧩 兼容与验证

- 情绪基准回落沿用已有基准字段：无配置迁移、无表结构变更，情绪规则版本仍为 `emotion-3`。
- 验证使用合成数据、打桩 Provider 和虚拟时间，不代表线上真实模型表现。

## 0.10.1 - 2026-11-26

### 🐛 修复

- 「用主模型自动填写」失败时不再把原因并成一句「模型不可用或生成失败」。模型调用结束却没有返回正文时，单独提示「模型没有返回正文」，建议调大「模型输出上限」或换个模型；等待超时提示可以重试；其余失败仍是模型不可用或生成失败。
- 后端日志同步分开：没有返回正文记录原因码与用时，超时记录上限秒数；此前「没有正文」会被记成「模型响应超时」。

### 🧩 兼容与验证

- 无配置迁移、无表结构变更。管理路由 `POST console/style-summary-draft` 新增两个错误码：等待超时返回 `504 timeout`，没有返回正文返回 `502 empty_response`；没有可用模型或生成失败仍返回 `503 unavailable`。
- 验证使用合成数据、打桩 Provider 和虚拟时间，不代表线上真实模型表现。

## 0.10.0 - 2026-11-26

### ✨ 新增

- 设置页顶部增加「新手引导」：六步清单依次是人格、关系、长夜、提示词注入、风格摘要、模型选择。每步标出「已配置」或「默认」，点「去设置」跳到对应分区并定位字段；清单只读，不改配置，展开状态在自动刷新后保留。
- 「模型选择」一步列全 9 个模型项：默认生成、备用生成、情绪、主动行为、补课、收尾、日记、梦境和原生向量模型。原生向量模型留空是「未配置」，其余留空即跟随主模型。
- 「风格摘要」增加「用主模型自动填写」：按当前人格的设定生成一份说话风格摘要，只填进输入框当草稿，点「保存摘要」才生效。输入框里有没保存的修改时，需再点一次确认覆盖。

### 🔧 改进

- TA 页「情绪与五维指标说明」改名「情绪与指标说明」，新增九项情绪一张表：每一项什么情况升高、什么情况减弱、多久回落，问号里是通俗解释。
- TA 页移除「可用性与来源」「依赖健康」两块折叠内容；后端接口字段保留，调用方不受影响。
- 「参与中」「运行模式」两处旧说法统一为设置页的实际字样「工作模式」→「参与表达与行动」，涉及配置说明、情绪谱提示、中英文 README 与相关文档。

### 🐛 修复

- 风格摘要输入框在页面 60 秒自动刷新后被统一禁用，修改或自动填写的草稿超过一分钟就存不了；现在该输入框自行管理禁用状态。

### 🧩 兼容与验证

- 无配置迁移、无表结构变更；新增一项管理路由 `POST console/style-summary-draft`，原有 22 项不变。
- 自动填写每次调用一次主模型，可能产生模型费用；不计入每日额度，只写审计日志 `style_summary.draft`。
- 验证使用合成数据、打桩 Provider 和虚拟时间，不代表线上真实模型表现。

## 0.9.0 - 2026-11-26

### ✨ 新增

- 「设置 → 快速开始」增加「对象情绪维度」：会话维度（默认）下各群和私聊各自独立，行为与 0.8.0 一致；用户维度下同一个 QQ 号共用一份委屈、受伤、害羞，在群里受的委屈会带到私聊。关系、日记和记忆仍按会话隔离。
- 用户维度下 TA 页的会话对象下拉按 QQ 合并为一项，并标注「私聊 + N 个群聊」；选中后显示该 QQ 共用的对象情绪。

### 🔧 改进

- 回复前等待对象情绪分析缩短为最多 1 秒；超时先回复，分析任务不再取消，结果在后台写回，下一次回复和 TA 页生效。该会话来了新消息时，迟到结果仍被拒绝写回。
- 每次对象情绪分析输出一行终态日志 `[LE-对象情绪]`，含对象、会话、模型判定、是否写入、原因码与耗时，便于核对“未采集”的原因。
- 补 `emotion_provider_id` 的配置帮助与示例。

### 🧩 兼容与验证

- 无配置迁移、无表结构变更：用户维度复用现有 `owner_states` 表新增一种记录类型；升级后默认仍为会话维度，不会自行改变行为。切换维度不迁移已有数据。
- 回退到 0.8.0 无需清理配置：旧版读取配置时忽略未知键，人级记录保留在库中但不被读取。
- 对外接口 `get_current_emotion` 的返回字段不变，LivingHello 无需同步升级。
- 验证使用合成数据、打桩 Provider 和虚拟时间，不代表线上真实模型表现。

## 0.8.0 — 2026-11-25

### 新增

- 控制台顶部增加「导出诊断日志（近3天）」：管理员通过宿主下载 ZIP，包含仍可用的事件、情绪及对象情绪、主动行为、承诺状态与版本设置快照。
- 采集在业务提交后执行，异常不影响已提交结果；正文剔除、凭据脱敏、账号一致别名化，模拟记录与实际行为明确区分。
- 页面沿用统一三语言实例，打包期间防重复点击，完成、失败或超时后恢复；权限不足、下载繁忙和宿主能力不足有明确提示。

### 留存与兼容

- 独立记录最多32 MiB，单文件1 MiB或跨小时轮转；每条写前删除最旧文件腾出容量，每60秒清理超过72小时的记录，无新日志时也执行。
- 同时最多一个打包或下载任务；临时 ZIP 在下载结束、失败、取消及卸载后清理，启动清理异常退出残留，清理期间保护正在导出的文件。
- 无配置或数据库迁移，情绪及承诺行为不变；配套 LH 2.10.0 提供独立诊断入口，不新增彼此运行依赖。
- 离线与固定宿主验收使用合成数据和打桩 Provider；容量及时间边界通过虚拟时间验证，缺失和超限在清单中标明，不代表完整72小时生产覆盖。

用法、权限及内容边界见[诊断日志](docs/diagnostics.md)。

## 0.7.1 — 2026-11-23

### 修复

- 保留 LH 的失败原因码、异常类型和请求状态；权限或参数预检拒绝不再混成“已请求但结果未知”。
- 用户修改图片需求时，模型预算与事件 ID 按调整轮次隔离；同一轮仍去重，A→B→A 不再被历史额度误挡。
- 已发起请求、回执丢失或投递未知时停止自动生图；保留原事项，用明确的核对说明收尾。
- 对齐承诺自动重试的 schema 与运行时默认值为5；原保存值保持优先，不修改已有配置。

### 兼容与验证

- 配套 LH 2.9.6；原 SQLite v9、承诺状态和重试计数沿用，无需数据迁移。
- 已有取消、未完成名额上限、24小时等待期限和画面要点保护继续生效。
- 离线回归及真实双方门面全打桩，不代表付费提供方实测。详见[重试说明](docs/promise-retry.md)。

## 0.7.0 — 2026-11-20

### 新增与调整

- 委屈、受伤、害羞在开启模型细化后按近期同对象对话、语气和已有情绪判断产生、
  增强、缓解或清除，不再以固定词汇作为模型结果的生效条件。复用联合分析；
  仅其冷却在实际调用前拒绝时可补一次专用分析，仍占每日总额度。
  回复前最多等待5秒，超时取消并拒绝迟到写回；失败或未知结果不再调用一次模型。
- 掌控感以至少0.75置信度更新，调节愤怒、悲伤和恐惧及普通回复、主动聊天、模拟的表达。
  中性0.5保留旧公式；不改变四维、开心预算、关系分、主动发送评分或工具权限。
  详细公式及副作用见[掌控感说明](docs/control-integration.md)。
- TA对象选择跨自动刷新保留，下拉最多10个会话候选，输入精确账号ID优先定位私聊。
  关系筛选独立；日列表按配置时区每日00:00更新、精确好感度降序，实时3D与编辑
  使用当前值及CAS版本。详情隐藏信任/边界，底层字段保留。

### 修复与兼容

- 插件日志统一使用 `astrbot.api.logger`，保留原日志级别、内容及异常栈；
  离线工具与测试使用隔离记录器，不再依赖内置 `logging` 或生产日志兜底。
- 简介补充规则情绪无需模型、自动刷新保留草稿及独立功能开关；
  声明 QQ OneBot、QQ 官方、Telegram 与 Discord 的基础接入及各自投递边界。
- 模型选择显示可读名称，自动刷新更新标签但保留Provider ID与表单草稿。
  模型诊断只忽略持久目录丢弃的route，其余身份和来源字段仍严格核对。
- 承诺管理DTO补齐结果、等待时间及重试计数；页面读取不重复执行任务。
  模拟提示词明确素材事实边界，完成不等于提交、交付或确认。
- SQLite自动迁移至v9，仅新增可空的历史`control/control_at`；旧历史按中性计算并标记缺口，
  不回填、不重写已有状态或关系。日快照复用`runtime_meta`。无新增配置键，原开关值保留。
- 保留0.6.3的模型输入精度与0.6.2的定时问候让行；离线和浏览器复测入口见[检查分层](docs/delivery-notes.md)，
  不将打桩结果视为真实模型语义或平台投递实测。

## 0.6.3 — 2026-11-20

### 修复

- 主回复、情绪细化、主动聊天、内心感想、模拟发送、日记与梦境的模型情绪输入
  统一为最多3位小数，不补无意义的零；主回复状态块中文直接输出。
- 只舍入指定字段的输出副本；数据库、内部状态、时间戳、证据和原始关系分数保留原精度，
  梦境与短期情绪阈值仍先按未舍入值判断，素材预算沿用原口径。
- 无新增配置或数据迁移；新增17项离线消息体回归，模拟天气回归同时核验页面和存储保真。
  入口与边界见[模型情绪输入精度](docs/prompt-precision.md)。

## 0.6.2 — 2026-11-20

- 修复宿主早安任务使随机主动全天让行：仅同一真实会话在定时问候前后各15分钟暂停，
  其余时段恢复原随机机会检查；08:00早安对应07:45–08:15。
- 使用宿主保存的下一次及最近执行时间，无时区日期按UTC解释；缺失目标、坏时间与其他会话
  不产生全局让行，全部匹配任务均参与判断。
- 保留冷却、概率、免打扰与错过机会不补发；承诺和晚安不受影响。原开关默认与存量配置不变。
- 新增33项离线回归，逻辑及复测入口见[定时问候让行](docs/native-proactive-yield.md)。

## 未发布 — 基于 0.6.0 迁入 R3

- TA 改为九项情绪谱；委屈、受伤、害羞可按具体会话查看，缺失值显示未采集，
  有效采集的零值和低于表达阈值的衰减值如实展示。移除概览历史曲线。
- 对象情绪采集默认关闭，只在参与中按人格、平台、会话和对象隔离；
  证据、关系边界、有效期与重复事件由规则校验，模型复用原细化调用。
- 行为模拟补齐关爱、委屈、受伤、害羞，共 12 项；记录和正式情绪分开，
  重复 request_id 不新增模型调用。
- 编辑期间继续自动读取状态，保留设置、模拟与关系草稿的节点、焦点和选区；
  关系保存仍使用原版本，冲突后明确复核才能采用新版本。
- 保留 0.6.0 图片改词重试、归属锁、待办并发名额/取消和配置 trace TTL；
  旧群聊空收件人图片不注入个人事实，同轮交付事实只注入一次。
- 存量配置与 SQLite 保留，新能力存入可选状态字段，不重建历史数据。
  本项为本地迁入，版本仍为 0.6.0，验证记录不代表生产已部署。

## 0.6.1 — 2026-11-19

- 承诺自动重试支持0–10次，图片改词与确定失败延迟重试共用LE预算，并取LH改词上限的较小值。
- 修复发送失败的免计数标志反向传递，正常失败按预算收尾，睡眠等待不消耗次数。
- 等待调整或核对最长1–168小时；旧任务沿用原等待时间，到期结束并释放名额，保留原请求与未知结果。
- 提供方错误、额度耗尽和结果未知都有一次追问；页面和聊天均可取消后续处理，页面自动读回。
- 详见 [承诺重试与收尾](docs/promise-retry.md)；离线矩阵覆盖0/10、跨重启、未知不补发及取消竞争。

## 0.6.0 — 2026-11-19

- 新增原图片事项领取与结算，状态/交付trace同事务保存；共用宿主归属锁，
  request_id、账号、人格修订和代次不一致拒绝，成功回执幂等且不降级。
- 明确拒绝与新版映射许可允许原ID有限改词，准备候选可恢复；
  生成或投递未知保持暂停，不因升级重复收费或补发。
- allow_sleep成为唯一睡眠总开关；关闭清醒100%，重开不补扣关闭时间，
  兼容旧idle和共享状态。退役night_schedule_enabled不再显示或授予许可。
- 承诺页面展示全部事项和总数，自动刷新保持详情展开；
  提示词编辑分为人物与通用说明，页眉紧凑显示版本。
- 天气过渡允许0秒；交付片段缓存1–168小时、步进0.1并贯通回执TTL。
- README仅介绍当前产品；全部133项配置用法由schema、Console与同源帮助生成，
  技术判断、21项管理API、已知接口缺口与手册对齐；历史专题见下方索引。
- 配套LH 2.9.0，存量配置和SQLite保留；未合入独立未提交的重试策略，
  未知结果取消限制保持。验证为隔离离线与合成页面，不代表生产已升级。

## 0.5.0 — 2026-11-19

### 新增与修复

- 配套 **LivingHello 2.8.0**，对明确生图内容拒绝或超长描述使用自身 `closing`
  模型提出等义局部调整，最多两次；同一图片承诺保留原文、尝试计数和准备候选。
- 成功用词由 LH 按实际模型记录复用；需改变画面、无合适调整或次数耗尽时等待用户。
  新画面沿用原任务并重置预算；准备候选恢复不重复调用模型，生成与投递未知不补发。
- 修复承诺取消的容错与原子批量处理，等待图片不重复占用承诺名额。
  不新增 LE 配置项，不重置已有 SQLite；新候选信息保存在原动作结果字段。

### 验证

- 可移植回归 2239 项与 197 个子测试通过；显式 LH / LE 生图矩阵 17 项通过。
  双插件矩阵使用固定 LH 源码和全打桩模型、图片及发送接口，付费 API 测试为 0 次。
- 双插件矩阵在 CI 显式运行，独立默认 pytest 不依赖相邻插件，不用缺依赖跳过冒充通过。
  [状态与复测入口](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/image-prompt-retry.md)。

## 0.4.2 — 2026-11-19

### 新增与修复

- 提供可编辑预置提示词，并保留独立的 LLM 请求挂钩；配套 LH 2.7.11 的共享提示词契约。
- 恢复消息提交接口的布尔返回值，内部保留拒绝详情，避免已拒绝的消息被调用方误判为成功。
- 承诺重复交接保留重试计数；关闭注入时不泄漏承诺提示。高并发下压缩状态证据，避免状态体积越界丢消息。
- SQLite 原数据保留；新增提示词字段缺失时采用默认值，不要求重置配置。
- 离线 Python 回归 2193 通过，UI 单元 16 通过，合成浏览器 30 场景通过。详见[提示词与边界说明](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/stability-0.4.2.md)。

## 0.4.1 — 2026-11-18

### 新增

- 图片承诺被内容规则拒绝后，主动用日常说法问怎样调整或是否取消，拍照、自拍、画图共用；
  用户改过画面仍被拒绝时，再说明已按新想法尝试，让用户继续选择。
- 到期失败保持原承诺等待，存量等待图片缺少追问记录时补问一次；通知状态持久化，
  重启、未知发送和旧轮次迟到回执不会触发盲目重复追问。
- 用户明确换人物、场景或风格时恢复原文生图承诺；选择“算了 / 不拍了 / 不画了”可取消。
  多张图片需明确选择，纯确认、重试口令与取消用语不算调整。

### 兼容与验证

- 沿用 `livingemotion.image-followup.v1`，保留 LH 已问回执，避免两边重复说明。
  完整即时失败交接需 **LivingHello 2.7.8**；新版本不增加配置项。
- 旧 SQLite 承诺表自动增加三个通知字段，保留原记录、状态和额度；
  限流继续按既有延期处理，生成或发送结果未知不自动重试，图生图不强行恢复。
- 新增 LE 60 项、LH 8 项离线矩阵实测通过；LE 原有相关回归改前、改后均
  91 通过、11 失败，失败名称一致。该结果不代表全量 CI 通过，真实付费 API 测试为 0 次。
  逻辑、迁移与复测命令见 [主动调整说明](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/promise-adjustment-20261118.md)。

## 0.4.0 — 2026-11-17

### 新增

- 开心增加滚动 300 秒预算：事件带来的上涨累计最多 5 个百分点、下降最多
  10 个百分点，正负独立。逐条即时处理，普通互动、无明确对象和中性纠错
  不再抬高开心；自然衰减与天气加成另算。规则与模型细化使用同一限幅入口。
- 好感度计分 V2：明确指向 Bot 的当前言行才计分，单条非零自动变化为
  0.5–1 显示分；普通聊天、转述、否定及主体不明保持 0。夸奖/道歉/有依据纠错
  为 +0.5，实质帮助/履约为 +1，冒犯和辱骂按强度扣分。
- 关系设置新增五阶段个人生图及新图片承诺婉拒概率，默认依次为
  90% / 60% / 30% / 10% / 5%，可分别调整到 0–100。同一请求只判定一次，
  已有待办继续履行；配套 LivingHello 通过公开契约读取。
- 长夜新增平铺开关：白天自动恢复精力、补觉按起床时间截止，以及补觉最长时长。
  默认白天不恢复、补觉沿用下一次实际起床；关闭按起床截止后默认最长 120 分钟。
- 延迟生图保存生成与发送检查点，并接入 LivingHello 统一投递回执；
  `promise` 与 `future_task` 按会话、发起人、时间和内容保守仲裁归属，
  交给宿主的事项标记 `delegated`，减少重复执行。

### 调整与修复

- 普通关系最高仍为 99 分，100 分由管理员设置；冻结与手动编辑保留。
  正负日预算独立，各 2.4 显示分；不足 0.5 分余量不写回小尾数。
- 睡眠精力按 0.1 点结算并保存时间余数；困/恍惚安静 30 分钟后补觉，
  补觉严格超过 20% 转小憩，固定夜间沉睡在实际起床前不会因满精力提前结束。
  新安装默认回复耗能 2 点、疲劳 0.5 点/分钟、恢复 1 点/分钟、唤醒 10 次；
  旧配置显式数值继续生效。
- 正常睡醒后的同周期在途回复可以完成；重复、过期、跨身份和跨代际票据
  仍拒绝，分段或重复回调不会重复扣精力。
- 图片已生成时重试发送原图；生成或发送结果不确定时停止自动重试，
  避免重复收费或重复发送。`sent` 仅表示宿主受理，cron 完成摘要不是平台送达证据。
- 对齐 metadata、源码注册号、双语 README 与使用手册版本；
  补充开心窗口、好感、婉拒概率、睡眠与任务协作文档。

### 升级与验证边界

- 情绪/关系审计规则分别为 `emotion-3` / `relationship-3`，与插件版本号独立。
  不重写历史情绪、好感或预算；旧状态没有 `joy_window` 时按空窗口兼容。
- 承诺存储按已有迁移机制补充动作/宿主归属字段，旧文字任务继续运行；
  旧 LivingHello 没有图片能力契约时等待恢复，文字功能独立可用。
- 本版整理已上线源码，验证采用隔离 Provider、虚拟时间和临时 SQLite；
  不以离线通过证明真实模型、真实图片付费请求或平台最终送达。
  同环境回归须逐项比较既有失败名称，不宣称全量测试已经全部通过。

## 0.3.3

### 修复
- 即时请求被误记成承诺：记账契约改为「先分清即时与延迟」。能这一轮立刻
  做到的（直接回答、当场调生图工具给照片/自拍/图片/语音）直接做、不写
  记账指令；只有「晚点」「稍后」「六点过」「10分钟后」这类明确延后才落
  `<!--promise:...-->` 标记。
- 生图工具被无条件禁用：删掉契约里「现在绝对不要调用生图或发图工具」
  这条一刀切禁令——它每一轮都注入，模型读到就永远不敢当场出图，实测
  「拍一张自拍给我」只回文字不给图。普通聊天轮次生图、发图工具随意用；
  到点兑现的那一轮才按需收紧。

### 文档
- `docs/promise.md` 新增「即时与延迟」判定表与背景说明。

## 0.3.2

### 新增
- 承诺兑现带上下文：建立时把最近几轮对话压成概要写进 `context_summary`，
  到点生成不再只有一句"发一张自拍"。
- 召回前置：外部记忆后端只认真实事件授权，承诺落库时先取一次材料快照
  （`promise_traces.kind=prefetch`），到点消费；本地向量后端还能再补一次。
- 召回租约：`on_llm_request` 本轮召回出的材料按会话暂存十分钟，
  承诺落库优先复用（零额外检索），不再依赖回复提交事件能否被外部后端授权；
  取不到才回退到用当前事件检索。
- 多气泡：兑现正文保留模型自己的断句与换行，发送层按行拆成多条气泡。
- 片段缓存：兑现后留 24 小时（可配 `promise_trace_ttl_hours`），
  用户追问直接命中，不再跑向量检索；到期自动释放。
- 主动聊天单一入口：只读探测宿主 `cron_jobs`，检测到「主动找主人聊话题」
  时 LivingEmotion 让行，并在「功能耦合」里显示；关掉宿主那条后自动接管。

### 修复
- 承诺正文被 `strip_stops` 把标点全换成空格，读起来像电报。

## 0.3.1

### 修复
- 承诺提醒不准点：说「2 分钟」被档位随机成 4 分钟，现在档位支持
  `2分钟 / 90秒 / 1小时 / 半小时` 这类确切延后，落点分毫不差。
- 承诺到点不发：`awaiting` 并轨会让提醒一直等到用户下次开口，
  已恢复为到点直发；tick 60 秒 → 15 秒，实测 2 分钟的承诺 5 秒内发出。
- 兑现文案退化成死模板：`purpose_model` 与选模型两层都用严格版
  `validate_context`，无实时事件时 170ms 就抛 `context_changed`；
  新增 `delivery=True` 走放宽版。
- 页面倒计时看不出秒：改为 `时:分:秒`，并按本地时钟每秒递减。
- 主动行为的多段正文挤在一个气泡里：发送器按换行拆成多个气泡。

### 调整
- 承诺兑现改用独立 `promise` 额度池，不占 `behavior_daily_limit`；
  情绪、随机、记忆话题、承诺衍生闲聊仍照常计数。

## 0.3.0（承诺兑现）

### 新增

- **承诺任务**：回复里的 `<!--promise:档位:描述-->` 会被记成带时间的待办，
  到点由插件自己把话说完。五档时间（马上/一会儿/待会/今晚/明天·过几天），
  单会话最多 3 条，同措辞合并成一条，24 小时内不重复提醒。
- 聊天里的追问、确认、取消与提前：说「不用了」直接取消（只有一条时不追问，
  多条才问编号），说「还有什么没做的」列清单，说「早点给我」提前执行（单日有上限）。
- 「主动行为」页新增当前承诺挂载区：档位、剩余时间、描述、排队中/正在发送，
  以及被提前过几次。
- 承诺兑现的内容会写入长期记忆，事后追问「你刚才说什么」能答上来。
- 控制台「记忆接入」的写入能力改为读真实后端状态，不再借用「导出体验」能力。

### 调整与修复

- **重启后承诺发不出去**：上下文校验、行为身份、夜间静默、发送路由、事件登记
  五处都要求「此刻必须有实时来源」。逐一补上「允许来源由会话表重建」的通道
  （`validate_delivery` + 桥接层按 `adapter_id`/`scene_kind`/`scene_id` 重建 route）。
- **原生通道回执不可信**：反向 WS 适配器的 `send_private_msg` 返回 ok 和 message_id，
  消息却没有落地。承诺固定走宿主 `send_message`，回执只到 unknown，
  按「适配器已接手」记 sent。
- **夜间误伤承诺**：作息表只该约束主动闲聊。承诺兑现不看作息表；确实发不出去时
  用 `no_penalty` 推迟到醒来，不再重试三次就判死。
- **重试撞旧记录**：同一承诺每次重试换意图世代（`#1`、`#2`…），
  避免 `INSERT OR IGNORE` 撞上第一次失败的行，导致永远返回 unknown。
- **孤儿承诺空转**：会话已不存在时直接取消，不再每 60 秒 defer 一次。
- **唤醒会话孤儿**：周期缺失、已过期或唤醒额度为 0 的账本就地作废，
  修复「精力满却一直不回」。
- **承诺兑现漏写记忆**：补上 `auto_memory.ingest`；写入守卫、归属账号解析、
  原生归档作用域三处允许来源重建，否则消息发了、日志有、记忆没有。
- 每日发送额度默认从 6 提到 20；closing / promise / behavior 共用同一个 `send` 池。
- 测试基线：全量 `pytest tests` = 33 failed / 1784 passed，与升级前的既有债务一致。

## 0.2.0（改版候选）

### 新增

- 九区生活控制台、全局/私聊/群聊筛选、圆形扩散双主题、集中设置。
- TA 大字号情绪与真实基准雷达；关系二维力图、平台账号搜索、0.1步进好感修改与冻结。
- 同人格共享或会话独立状态，切换保留历史和保守睡眠限制。
- 清醒/小憩/恍惚/困/沉睡、持久赖床随机、低精力唤醒点数、回复轮数和窗口。
- 最近24小时精力曲线与事件表，状态和日志同事务，旧历史明确未采集。
- Bot 第一人称天气日记、日梦二级查看、按用途原生模型选择和共享预算。
- 私人日记与梦境可置顶/取消置顶，确认、来源复核与冲突校验共用管理接口。
- LivingMemory 两种公开门面、本地原生向量接口与异步收录，保留旧显式记录原期限。
- 随机主动聊天：持久等待、记忆回访、近况关心、久别问候、熟悉私聊中的轻微心情分享。
- 主动节奏、独立生成模型和会话勾选；聊天安静时间、素材避重、未回应降频与检查记录。
- 情绪改为四维计算、五维展示：新增只由模型写入的「底气」，页面雷达改五轴并移除六种派生情绪展示。
- 情绪强度三档（保守/平常/激进），只放大单次增量与同类刺激闸门，不改半衰期。

### 调整与修复

- 核心运行全部由插件自身实现：删除外部情感插件发现、冲突退让、旧库迁移与回退工具。
  模式仅由自身开关控制；补课耗时只使用 `livingemotion:wake_prepare_seconds`。
  保留自身额度、冷却、授权、数据和来源不明体验的七天硬期限。
- 清理旧耦合测试和历史参考材料，补充独立运行与升级说明；必需第三方版权声明保留。
- 插件帮助手册改为逐步上手说明，补齐保存生效核对、五轴解释、三档选择和常见问题；
  更正 router 指定上游支持、输入预算默认值及手动梦境开关说明，旧版安装参考折叠保留。
- 迁入完整未读补课流程：固定上界、长文尾部、成功块回执、跨批次三次补答上限。
- 回复提交只扣一次精力，第一次提交起算唤醒窗口；沉睡、新人消息与授权撤销可取消旧结果。
- 原生回复提前禁流式，末级请求再次缓冲；无可验证提交接点的 Live 模式拒绝。
- 晚安使用独立开关、持久意图与共享额度；随机关闭不额外调用生成模型。
- 主动机会错过或中断不补发，配置切回不复用机会；小憩、恍惚、困和沉睡不主动聊天。
- 管理 API 新增范围、关系和精力 DTO，写操作有身份复核、CAS 与不重试规则。
- 新配置默认规则2和人格共享；旧配置缺少字段保留规则1和会话独立。
- 旧 v2 状态在时区未配置时保持只读；初始化失败会清理部分创建的 worker、存储和 API。
- 原生 OpenAI 向量提供者读取实际模型标识；基础转换与逐值校验减少重复工作。
- 候选宿主范围限定4.29.1–4.29.4；最终兼容通过以本轮冻结宿主报告为准。
- 对方难过/焦虑时社交需求改为上升（更想靠近陪伴）；情绪说明表补齐升降条件与回落速度。
- 底气与四维时钟隔离：规则情绪变化不重置底气，旧状态缺省中性 0.5，无需迁移。
- 修复阴天等天气加成下页面标签长期显示「兴奋」：`surprise` 改为只统计唤醒超出基线（默认 0.3，优先动态基准）的增量，平静时为 0。

### 验证边界

- 合成模型/向量 transport 和临时消息用于测试，不代表真实费用、模型效果或平台投递。
- 原生提交不等于送达；未知发送不自动重试，不伪造成功回执。
- 部署验收、模型效果和平台送达需分别核对；插件市场上架或 hosted release 不由本地测试结果替代。

## 0.1.0（冻结候选，未发布）

### 新增

- 独立事件契约、Bot 感受/对方观察分型、来源关系账本、SQLite 原子提交与预算。
- 原生人格/身份适配器及 none、local_lite、external 记忆端口。
- 长夜与精力、有限醒后补课、单一主动执行服务、私人日记与梦境模块。
- 七区白昼/黑夜管理前端、管理路由保护模块及合成测试。
- Application、原生配置/消息钩子、`le_wake` 和五个管理端点。
- 离线迁移 CLI：`preview/import/verify/rollback-plan`，原期限与旧约束保守接管。
- 本地安装、架构、API、兼容性、来源许可文档；Linux Python 3.12/3.13 与 Node 22 CI 配置。

### 边界

- 模型细化、主动/群主动、日记、梦境和外部导出默认关闭。
- 独立安装默认 enabled/active，不改现有部署或消费者配置；上述用途须分别启用。
- AstrBot 原生 after-sent/send_message 布尔值不等于投递成功；unknown 不自动重发。
  无可靠确认时 settling 最多 120 秒后取消回清醒/困倦，页面明确显示 unsupported。
- 外部后台授权及幂等体验导出缺能力时明确降级，不穿透私有存储。
- 原生 ProviderOpenAIOfficial/Qwen 纯文本请求使用 UTF-8 字节+256 预算上界，
  不依赖 tiktoken，不宣称精确 usage；其他 Provider 未验证并拒绝。
- 原生 sandbox 下主题仅本次有效、刷新回系统；非 sandbox 持久化有合成浏览器证据。
- MIT 仅适用于自有新写内容；依赖及第三方素材遵守各自许可。

### 最终本地验证

- 固定 v4.29.4 最终 single222/four230/conflict245，共697条宿主断言 PASS；
  原生浏览器44 PASS（含28组布局）、0 pageerror，H01/H02/H03/C30均覆盖。
- 普通full 1273/1273、完整migration 84/84、V06 4/4 PASS；
  38项组件矩阵为29 PASS、9项限制、0 FAIL。集合重叠不相加。
- C50 31/31、F8 53/53 PASS，真实Provider/SDK经合成transport的16项实际执行、0 skip。
- 原完整C51 10000/10000成功、p95=48.801416ms，window11/11 PASS；
  <=50ms门槛余量2.40%，不代表生产余量充足。
- 历史C51 221.628ms、139.081ms、56.895041ms均为当时FAIL，保留原报告，不作当前结论。
- metadata 保守限定 ==4.29.4，不宣称最低版本或广泛兼容；未实测真实外部检索/导出和生产投递。
- CI 普通层排除显式宿主专项而非跳过测试；F6 的 performance_f6.py 纳入自动发现，
  performance_probe.py 和大样本 benchmark 仍是显式诊断/验收。
- 目标仓库为 PRIVATE，通过正常认证访问；实际提交与 CI 结果以仓库记录为准。
  本地验收不代表远端 Actions 通过，不包含商店发布或生产部署。
  本地执行的准确结果见 [delivery-notes.md](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/delivery-notes.md)。
- 仓库交付证据由交付者独立记录，本次不打tag或发release；
  BiliBot/LivingHello本地消费者改动不纳入新仓库提交。

## 历史专题与验证原件

旧专题的改动归入上面的版本记录，原文统一由以下固定Git来源追溯。
当前使用说明只在docs索引维护。旧验证数量仅证明当时范围，不能用于宣称
当前版本或生产通过；旧文内证据路径可能已撤下。原始文档也已本地独立归档。

| 原始专题 | 内容与追溯 |
| --- | --- |
| [T1 冻结接口 v1](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/CONTRACTS.md) | 存储接点（T2 实现）；R9 门面；边界决定 |
| [T3 情绪与关系领域交接](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/DOMAIN.md) | 集成必读；精确签名；冻结规则 V1；验证入口与边界 |
| [T1/T2 基础阶段交接](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/FOUNDATION.md) | 已实现；实际测试；下一阶段接线顺序；尚未验收 |
| [运行集成契约](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/INTEGRATION.md) | 生命周期与模式；消息与回复；模型与数据；接口与验收 |
| [API v1](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/api.md) | 进程内门面；来源与事件；状态与重试；图片失败交接；页面接口 |
| [架构与状态计算](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/architecture.md) | 架构与状态计算 |
| [主动行为测试与发送日志](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/behavior-console.md) | 主动行为测试与发送日志 |
| [T6 主动行为与唯一发送端](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/behavior.md) | 给父代理 / Foundation 的接点；公开调用方式；注入接口；默认规则与边界；执行与回执；并发、卸载与恢复 |
| [F8 后台 Job 取消修复交接](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/cancellation-fix.md) | 范围与归属；状态边界与不变量；反例与实现映射；实际执行；结果不明与限制；源码锚点与核心交接 |
| [兼容性与验证边界](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/compatibility.md) | 兼容性与验证边界 |
| [管理后端 T9 / F1](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/console.md) | 给核心集成者：立即可接的冻结接口；路由与兼容；授权边界；配置与动作职责；验证进度；实际验证证据 |
| [可选插件协作](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/consumers.md) | 可选插件协作 |
| [LivingHello / LivingEmotion 双插件协作契约（LE 0.4.0）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/cooperation-contract-20261116.md) | 接口与兼容；资源、回执与重试；验证与边界 |
| [交付与检查](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/delivery-notes.md) | 当前实现；检查分层；文档与发布包；线上部署 |
| [全局日记、梦境池与天气情绪](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/dream-paper.md) | 使用；情绪如何决定梦；天气加成；TA 的六维曲线；梦中惊醒消息；代码位置 |
| [五维情绪：四维计算、五维展示](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/emotion-five-dimension.md) | 结论；计算逻辑；维度与回落速度；强度三档；配置与页面位置；测试材料 |
| [私人日记与梦境（2026-11-09）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/experience.md) | T7 原始实现与交接；能力边界；精确接口；Foundation 接线要求；日期、预算与模型；来源、清晰度与分享 |
| [TA 的此刻心绪](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/feeling.md) | 生成与展示；授权与持久化；周期与失败处理；验证入口 |
| [未来事件任务：两类来源的定义、边界与需求说明](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/future-tasks.md) | 0. 结论先行；1. 两类任务对照；2. A 类：用户发起的未来任务；3. B 类：Bot 承诺的未来任务；4. 判别规则；5. 交叉与冲突 |
| [AstrBot 隔离宿主契约](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/host-contract.md) | 紧急接入警告；最小 Handler Guard；环境与边界；可立即接入的接口；环境一致性约束；已执行证据 |
| [C15/C16 身份授权与关系投影修复](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/identity-fix.md) | SHA-256 冻结；身份与权限；接入交接；验证记录 |
| [图片承诺的提示词调整](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/image-prompt-retry.md) | 离线复测 |
| [LivingEmotion 安装与升级](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/installation.md) | 安装前确认；获取并加载插件；设置与升级后检查；旧版安装与开发验证参考；0.1 原生安装与 Provider 参考；安装 |
| [P5 管理 API / DT0](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/internal-console-contract.md) | 范围；接口与 DTO；设置单一来源；认证、错误与重试；协调者挂接；实施检查 |
| [P4 内部接入契约](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/internal-memory-contract.md) | 配置字段；接口与责任；派生数据决策；实测证据；接入与缺口 |
| [P3 回复、收尾与完整补课接入](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/internal-reply-contract.md) | 回复票据；完整补课；睡前晚安；验证证据；最终整合验证 |
| [P1/P2 状态集成契约](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/internal-state-contract.md) | 配置；状态模式；回复与睡眠；控制台与存储；冻结验证 |
| [开心 5 分钟窗口（0.4.0）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/joy-window.md) | 方向与口径；实现与成本；离线验证 |
| [TA 的生活控制台](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/life-console.md) | 快速开始；页面与范围；情绪与关系；长夜计算；晚安与醒后补课；日记、梦境和记忆 |
| [LivingHello 群聊回复复核](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/livinghello-reply-protection.md) | LivingHello 群聊回复复核 |
| [独立运行与升级](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/local-runtime.md) | “本地化”包含什么；升级后怎么用；可选协作；验收与回滚 |
| [身份、人格与记忆适配](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/memory.md) | 改版记忆入口；当前使用边界；给父代理的接点；原生人格；三种模式；已核实的 LivingMemory 契约 |
| [T5 长夜与醒后补课交接](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/night.md) | 正确性边界；状态与规则；精确接口；补课窗口与来源；emotion_foundation 接线；验证证据 |
| [F6 第四轮领域数值热路径修复](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/performance-domain-fix.md) | 范围与假设；验证口径；进度；修改与功能回归；唯一一次增长诊断；失败与限制 |
| [F6 第三轮冻结交接（已实际修改，性能仍 FAIL）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/performance-fix.md) | 第三轮修前 Profile；第二轮即时观测；第二轮根因与进度；文件归属；原失败；数据库变更计划 |
| [AstrBot 插件帮助手册：LivingEmotion](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/plugin-manual.md) | 第一次使用；保存以后，怎么确认真的生效；五轴雷达怎么看；情绪强度该选哪档；常用功能；承诺任务 |
| [主动聊天：想起你时，自然开口](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/proactive-life.md) | 快速开始；TA 会怎样找话题；运行和故障边界 |
| [延迟生图与跨系统任务去重：0.4.0 实现说明](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/promise-actions-20261116.md) | 1. 承诺生图；2. 宿主 cron 生图；3. 跨系统归属；4. 中断与重试；5. 数据迁移与交付；6. 离线验证入口 |
| [承诺内容拒绝后的主动反问](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/promise-adjustment-20261118.md) | 执行逻辑；代码位置；升级与使用；发布验证 |
| [承诺取消修复（LE issue #1）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/promise-cancellation-20261119.md) | 承诺取消修复（LE issue #1） |
| [承诺名额与注入修复（LE issue #5）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/promise-limits-20261119.md) | 承诺名额与注入修复（LE issue #5） |
| [承诺兑现的上下文、多气泡与片段缓存](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/promise-memory.md) | 0. 一句话；1. 三条断裂；2. 第 4 点：主动聊天只留一个子系统；3. 承诺记忆链路；4. 数据结构；5. 交互细节对照 |
| [承诺任务：识别、兑现与取消](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/promise.md) | 一句话；标记与识别；时间档；状态机；兑现流程；夜间与配额 |
| [分阶段生图婉拒概率（0.4.0）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/relationship-image-refusal.md) | 生效范围；配置与验证 |
| [好感度计分 V2（0.4.0）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/relationship-scoring-v2.md) | 调用链；可追踪字段；存量兼容；验证边界 |
| [睡眠与精力规则（0.4.0）](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/sleep-energy-rules.md) | 状态与恢复；精力计算与配置兼容；唤醒窗口与在途回复；代码对应；正确性与离线验证 |
| [0.4.2 使用与边界说明](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/stability-0.4.2.md) | 0.4.2 使用与边界说明 |
| [P6/P7 UI 实施进度](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/ui-progress.md) | 当前预览；历史协调提示；前端冻结；最终联合复验 |
| [livingEmotion 生活控制台 UI](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/ui.md) | 当前页面与 CI 基线（2026-11-17）；P6/P7 历史冻结记录；页面与接线；图表与交互；保存与错误；文件责任 |
| [C50/F8 与 C22/F9 独立最终预算复验](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-budgets-final.md) | 结论；给父任务与 Docs 作者的接入通知；窄门禁；实际执行与证据；C50 与 F8 实测；C22 与 F9 实测 |
| [独立运行验收](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-local-runtime.md) | 改动；离线验证；线上验收口径 |
| [T11 C51 与 C22/F9 最终独立验收](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-performance-final.md) | 最新独立验收 20261105-03；历史独立验收 20261105-02（原文保留）；给父任务；本轮完整结果；门禁策略；命令与环境 |
| [T11 独立性能与资源验证](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-performance.md) | 最新最终复验（2026-11-05 22:20 UTC）；历史验证记录；最终复验结论：C51 失败，按停止条件交回；旧轮独立结论（历史失败证据，原文保留）；环境与复跑；C51 测量边界 |
| [LivingEmotion 关系、发送、滑块与情绪验证](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-relations-emotion-20261109.md) | 后端；前端；验证边界；已授权的生产部署与复验 |
| [0.2.0 改版验收](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-retro-final.md) | 实现范围；本轮失败及修复；证据分层；执行边界；最终本地回归与性能；四版原生宿主最终结果 |
| [P8 独立四版宿主验收](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-retro-host.md) | 当前状态；环境与身份；隔离与费用；已发现的真实宿主边界；最终检查矩阵；入口 |
| [surprise 基线修复：回归材料](https://github.com/AKIhunter/astrbot_plugin_livingemotion/blob/7325129954c3f9ac26bfa7d9e2fe06ee469352ed/docs/verification-surprise.md) | 问题与修复；场景矩阵（离线实测）；测试结果（本地实测）；复现命令 |
