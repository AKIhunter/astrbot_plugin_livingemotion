# T8 消费者最小适配

状态：消费者专项实施完成（2026-11-05）；不宣称真实宿主总集成通过。
负责范围为 BiliBot 和 LivingHello 消费者；新插件 `api.py`、`main.py`、
共享契约、冲突检测与观察退让归 foundation / emotion_integration。
本文件是无消息工具时的交接入口。未复制旧插件代码到新仓，未提交或推送旧仓。

## 修改范围与工作树基线

2026-11-05 开始前，两个消费者仓库 `git status --short` 均为空；
下列既有文件的 `git diff HEAD -- <所选文件>` 为空。因此本任务差异相对于当时
working tree，也恰好相对于以下 HEAD。工作区根不是 Git 仓库。
从绫、LivingMemory 的 dirty 文件完全不在修改范围，详见 `source-baseline.md`。

BiliBot HEAD：`a0acfa9bd6b306a720bf6ccf133fd630ffd958f4`。

| 文件 | 修改前 SHA-256 | 实际修改范围 |
| --- | --- | --- |
| `core/emotion_bridge.py` | `cb64e307d1221d98096d202eaf05dda4d4c551ff58206dfec8e94ce8a4b9da1c` | provider 选择、v1 上报及只读关系对账 |
| `core/affection.py` | `a87a928a947ac6d6d94936bd11fb25a354c5ae8208ed879079028a054ac2a204` | 透传来源，不改本地写者 |
| `core/reply.py` | `2403111d928f563a9a419e18fc993370f04cef2259e56432699cba2727a25f0d` | 成功评论调用点传真实评论 ID |
| `core/private_messages.py` | `35aa082eba4f65125e396c1099f2c704bd3953ef6c33e71539dd9cf3cde05883` | 成功私信调用点传真实消息键、时间 |
| `_conf_schema.json` | `bc8667c7472a6845347cebb9f89138e9d0587884aed9e4eae1fea99918c56fea` | 可显式选择 provider |
| `tests/test_emotion_bridge.py` | 新文件 | 合成 v1、旧回退及调用点测试 |

LivingHello (`astrbot_plugin_at_guard`) HEAD：`e74d174ed6ccf6e8521a07151e25e80ec1e56d95`。

| 文件 | 修改前 SHA-256 | 实际修改范围 |
| --- | --- | --- |
| `main.py` | `21ac8b610544eecffcbb6a32ae31af535343d7e37e0cbae5beeda291439cc1f2` | 请求可用性硬否决、已有状态块供判定复用 |
| `guard_livingemotion.py` | 新文件 | 只读 v1 消费、namespace 识别 |
| `tests/test_livingemotion_handoff.py` | 新文件 | 状态/availability/组合与重载 |

只读保护基线：`guard_expression.py` =
`8a8ed83107415ff0a7082e4e953f399ac26fbf9426310d92bb58bb2be5ee32b5`；
`tests/test_congling_expression_handoff.py` =
`f98a150aeef6385c10ce39db9b615ba695b9c0ae03d73c58c24452f8f96f4c9d`。
不改图片、TTS、回复装饰、分句、延迟或发送执行者。

## 核心交接

以下是消费者需要的接点，不表示当前入口已经通过宿主验收。本任务不修改新插件 API
或入口；priority / 唯一 namespace 契约已由父代理转核心，不等待宿主总验收。

1. 在 LivingHello `on_llm_request(priority=10000)` 之前解析真实事件的原生人格、
   身份和受众，设置 `event` 的 `livingemotion:context` 为 v1 Context 字典
   （必须含实际 `route`、`instance_id`、`account_id`、场景、Bot、人格）。
   不接受正文或模型构造的 context，不把 `local` 自动提升成宿主实例。
2. 新插件是状态注入唯一所有者。只注入一份临时 TextPart，以
   `<!--livingemotion:state:v1-->` 开头；内容区分 Bot 状态和对方观察。
   LivingHello 仅把已有块提供给参与判定，不再复制到 `at_guard_memory`。
3. `plugin.api.get_capabilities()` 的 `mode` 必须反映当前有效模式（含从绫冲突
   后的 observe_only），不是仅原始配置；停止、禁用时应明确 unavailable。
   消费者每次重新发现激活实例并读 capabilities，不缓存插件实例。
4. `get_availability(context)` 维持 `api_version=1/status=ok`、
   布尔 `available/block_chat`。`available=False` 只否决普通自主参与，
   `block_chat=True` 才阻断普通聊天。失败不阻断原生聊天，不解释为自主授权。
   已认证管理/实际叫醒入口可由 foundation 设置
   `livingemotion:control_request="admin"/"wake"`，不可由任意 @ 或用户参数设置。
   非 LLM 管理命令仍由原生命令链处理。
5. 从绫同范围冲突检测、observe_only 不注入和不自主发送归 foundation；
   禁止修改从绫开关或猴子补丁。消费者不替代此判定，也不在新 provider 已选中后
   因拒绝、超时或 observe_only 再向从绫上报。
6. F2 已按当前 `INTEGRATION.md` 冻结门面接线，具体格式见下一节。核心仍负责
   public_comment 的记忆/导出/自主行为禁入，本任务仅验证 API 来源隔离与无发送资格。
   本地评分不当作 Bot 情绪或人类 care/conflict 证据；以后要消费评分，须新增版本化
   评估信号契约，不偷用 body 写分。

## F2 正式来源格式

每次后台操作重新发现当前激活实例，先 `plugin.api.get_capabilities()`，只消费 v1。
`resolve_producer_context` 的输入**精确为以下九个字段**，不传 instance/audience/route：

| 字段 | 实际构造 |
| --- | --- |
| producer | `bilibot` |
| bot_account | 配置中的登录账号 `DEDE_USER_ID`；缺失则跳过 |
| adapter_id | `bilibot:<bot_account>` |
| platform | `bili` |
| scene_kind | 私信为 `private`，公开评论为 `public_comment` |
| scene_id | 私信为真实对方账号；评论为 `comment:<comment_type>:object:<oid>:thread:<thread_id>` |
| account_id | 私信发送者 / 评论作者真实账号 |
| persona_id | 既有人格选择器解析的原生人格名；未启用人格为 `none` |
| persona_revision | 原生 prompt 与 B站附加 prompt 的内容指纹；不传原文 |

只在 `api_version=1/status=ok` 后使用返回的 `data` Context；核对实例、账号、场景、
人格字段和无 route，不自行补 Bot、受众或身份版本。解析前后重载则丢弃本次任务。
不兼容 producer context 或 public_comment 能力时明确降级，不伪装成私聊。

- 评论调用点位于已确认发送成功后的原关系记录入口，传入真实 `rpid`、对象 `oid`、
  `comment_type` 和真实根线程键（没有根回复时沿用原评论 ID）。上报
  `source_id="public_comment:<rpid>"`，完整复合来源由 Context 保留。
- 私信同一成功入口传入已规范化的 `msg_key`（原流程可取平台 `msg_seqno`）、
  消息时间（原采集流程缺时间时可能使用采集时间）；上报 `source_id="private:<msg_key>"`。
- 评论 `occurred_at` 是成功互动的观察时间，不冒充原帖创建时间；时间不参与 ID。
  event_id 是 producer / 完整 Context / source_id / human_interaction 的 SHA-256
  关联键；持久去重由 API 的来源复合键负责，不声称仅凭 event_id 获得幂等。
- 两种场景均为 `actor_role=human`、`event_type=human_interaction`、
  `body=""`、`signals=[]`；本地负分/正分/零分均不映射为情绪证据或最终分。
  中性互动可以由领域规则产生微小熟悉度变化，但不会制造“对方情绪”观察。
- 保留原 `ENABLE_AFFECTION` 调用开关、本地写者和旧从绫分支；旧分支零分不报。
  评论/私信来源不足、缺人格、解析失败、超时均不阻断主流程，也不补报第二提供者。
- 新分支日终只查当前人格下原账号私聊 relationship.normalized，不把它当作本地
  跨场景累计好感的等价值：`deviation=null/flagged=false`，不回写本地分。
  等待期间重载的旧关系结果丢弃，下一次操作才重新选择实例。

## 兼容决定

| 表面 | 分类 | 行为 |
| --- | --- | --- |
| BiliBot `EMOTION_PROVIDER` | 新增可选项 | 默认 auto，新插件 v1 优先，旧从绫回退；显式选择不串台 |
| 私信/评论来源参数 | 兼容的可选参数 | 完整真实来源才上报；缺失时跳过，不用秒时间造 ID |
| 新分支 ingest/query | v1 消费 | 只访问 `plugin.api`，不读取新 provider 的 cfg/store/SQL |
| 旧从绫分支 | 保留 | 旧 label/summary/配置/关系兜底不改；不承诺旧秒键 exactly-once |
| 本地好感 | 保留 | 本地写者不变，新关系仅作限定来源的对照 |
| LivingHello 状态 | 新增只读 | 复用 namespace 块，不作为长期记忆授权，不双注入 |
| LivingHello availability | 新增只读 | 仅增加否决，不放宽 mentions/重复/冷却等现有硬闸门 |

不添加自动重试。上报一旦调用即不切换 provider，结果 unknown/拒绝都只记录降级。
来源缺失不冒充持久幂等。新分支日志只记录机器原因码，不打印正文、账号或异常详情；
旧从绫分支原有日志/SQL 兜底保留，不把它们误称为新 v1 门面行为。
本适配没有集合型新 API、外部 HTTP、管理端点、模型调用或发送器。

## 验证

### 消费者专项

工作目录 `插件/BiliBot`，Python 3.11：

```bash
python3 -m unittest discover -s tests -p test_emotion_bridge.py -v
```

结果：**25 tests，OK，0 skipped**（0.239s）。覆盖显式/auto/off、缺失/禁用/不兼容
回退、加载顺序、后加载、等待中重载、observe_only 单目标、实际超时取消、
缺来源/缺能力、公开评论作者/对象/线程、零分中性事件、只读对账。
两个 AST 隔离用例执行真实评论/私信调用方法，验证桥异常后仍只有一次合成发送，
本地好感与关系计数仍写入；不启动宿主、不调用真实模型或平台。

其中 **3 项使用真实 LivingEmotionAPI + Projector + 临时 SQLite**，不是 API mock：
私信和公开评论 accepted 后重放为 duplicate，Bot/关系快照只更新一次，trace 仅一条；
公开评论不会改变已写入的私聊、群聊、另一平台状态，另一作者/线程/Bot 关系仍为基线；
公开场景无 route、available=false、block_chat=false、preview.eligible=false；
关闭 Store 后新建实例重新打开同一临时库，评论仍被去重。未启动后台 worker/模型/发送器。
无兄弟新插件源码时这 3 项会明确 skip，本次源码存在且全部实际执行。

工作目录 `插件/astrbot_plugin_at_guard`：

```bash
python3 -c 'import sys, unittest; from run_offline_tests import install_framework_stubs; install_framework_stubs(); sys.path.insert(0, "tests"); suite = unittest.defaultTestLoader.loadTestsFromName("test_livingemotion_handoff"); result = unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not result.wasSuccessful())'
python3 run_offline_tests.py
```

专项 **18 tests，OK，0 skipped**（0.057s）；既有离线回归 **424 tests，OK
(skipped=20)**（404 通过，2.731s）。覆盖只有新插件时复用一个 namespace、拒绝普通正文
冒充状态、availability 仅额外否决、私聊默认不阻断、block_chat 保留可信叫醒/管理、
原 mentions 硬闸不被绕过、shadow 下 reply/silence 均复核可用性、等待中重载/来源改变
丢弃旧结果、旧从绫状态分支保留。20 项跳过为现有测试缺宿主源码/可选依赖等，不算通过。
离线回归中的磁盘写失败和人格文件损坏日志为既有故障注入用例，命令 exit=0。

四插件用例使用**合成 registry/API/事件/发送器**，预置一个生产者状态块，
验证一次 ingest、状态不被 LivingHello 再复制、一次合成回复。它不启动四个真实插件，
不能证明核心 priority/冲突探测/真实主回复发送总集成。独立验证负责真实组合。

### 补充与失败记录

工作目录 `插件/BiliBot`：

```bash
python3 -m unittest discover -s tests -p test_config_schema_order.py -v
```

新增 EMOTION_PROVIDER 最初插在模型/人格设置中间导致既有顺序测试 1 项失败，
已移到好感区域前，不改既有测试断言。最终 **5 tests，OK，0 skipped**（0.005s）。

额外尝试（同目录，未完成测试收集）：

```bash
../astrbot_plugin_livingemotion/.venv/bin/python -m pytest tests/test_autonomous_ranges.py tests/test_write_result_safety.py tests/test_comment_context.py tests/test_config_schema_order.py -q
```

因该隔离环境缺 `aiohttp` 出现 **3 collection errors，exit=2**；不计为通过，
不修改其他代理虚拟环境，也不宣称 BiliBot 完整回归通过。系统 Python 无 pytest，
专项使用标准库 unittest，不需要安装依赖。
真实存储重载测试首跑 24 项时有 1 error：测试误对已关闭 Store 调用 open；
改为新 Store 实例后重跑通过，没有修改新插件存储实现。

### 交付边界

- 本任务仅修改上述 BiliBot 6 个文件、LivingHello 3 个文件和本文；
  未修改新插件 API/contracts/main、从绫、LivingMemory 或父规格。
- 两旧仓 `git diff --check` 已检查，受保护的 guard_expression.py 与既有从绫
  handoff 测试 SHA-256 与上述基线一致；没有 reset/checkout/commit/push。
- 不替父任务勾选完整 C39-C43 / F2。消费者 F2 接线与真实 API 隔离专项已有证据；
  核心 public_comment 记忆/自主禁入、动态冲突检测、真实 priority/唯一注入及四插件
  宿主组合仍由核心与独立验证负责。本任务不等待其完成。
