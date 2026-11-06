# 架构与状态计算

读者：维护者；用途：理解模块、状态计算和失败边界。2026-11-05 按源码核对，
产品已冻结，最终组件与宿主验收完成。规则/服务测试、宿主探针和成品集成不能互相替代。
权威来源为本页列出的源码；相关代码变动时同步，每次交付复核，历史结果见[交接](delivery-notes.md)。

## 模块与数据归属

| 层 | 现有文件 | 责任 |
| --- | --- | --- |
| 宿主入口 | `main.py`、`runtime/application.py`、`runtime/lifecycle.py` | Application 编排、Star 生命周期、独立数据目录、持久实例 ID、取消任务后关闭 SQLite |
| 公共契约 | `contracts.py`、`api.py` | v1 门面、来源 Context、分型状态、原因码；不开放 store/cfg 给消费者 |
| 领域 | `domain/emotion.py`、`relationship.py`、`night.py` | 注入时钟的纯计算，无模型、网络、SQL；精力只有 night 写入 |
| 投影 | `runtime/projector.py` | 还原领域 runtime，计算状态/来源贡献/trace，交给同一事务 |
| 存储 | `storage/schema.py`、`sqlite.py` | WAL、短事务、CAS、清除代际、持久幂等、正文窗口、配额和意图 |
| 后台 | `runtime/background.py` | 有界排队、共享并发、用途额度、取消/超时；不把排队说成已保存 |
| 模型桥 | `runtime/models.py`、`refinement.py` | 原生 Provider 绑定、完整输入字节预算、受限请求副本和最终复核 |
| 适配器 | `adapters/persona.py`、`identity.py`、`memory/` | 原生人格、当前身份修订、三种可替换记忆端口 |
| 服务 | `services/behavior.py`、`catchup.py`、`experience.py` | 行为意图/回执、有限补课、私人体验与来源控制 |
| 页面 | `page_api/`、`pages/livingemotion/` | 宿主管理鉴权、结构化委托和七区双主题 UI；不另开生产 HTTP 服务 |
| 迁移 | `tools/migrate_legacy.py`、`storage/legacy_import.py`、`runtime/legacy.py` | 显式离线导入、原期限与约束评估，不续跑旧执行器 |

普通路径为：真实事件 → 可信来源/原生人格 → 规则投影 →
事件与全部状态原子提交 → 读取已就绪快照 → 有长度限制的状态补充。
模型细化、主动、日记和梦是独立后台用途，不应增加主对话同步模型请求。
`main.py` 已构造 Application、注册页面并接优先级 11000 的消息/LLM hook，
以及优先级 12000 的 `le_wake`。最终单插件、四插件与从绫冲突场景均通过，
包括受测故障下主聊天继续和消费者退让；范围见[兼容矩阵](compatibility.md)。

## 来源隔离

`Context.scope_key` 哈希包含 instance_id、bot_id、persona_id、adapter_id、
platform、scene_kind、scene_id；`account_key` 再加入原 account_id。
相同裸群号、同名人格或相同模型不是合并依据。route 只能来自真实宿主 UMO，
不从裸账号猜测；修订号不改变持久键，但会使在途任务和授权失效。
PUBLIC_COMMENT 单独隔离，禁止携带发送 route。

OneID/person_id 是同值别名，不建立第二套绑定表。关系证据留在原账号，
绑定/解绑只改变当前有权来源的投影；归属关系本身不授予跨场景材料读取权。
模型等待后必须重新核对人格、身份、受众、来源凭据和清除代际。
最终组件已验证绑定投影/解绑及跨场景授权隔离，H01 公开读取在最终三场景通过；
真实跨平台 OneID 绑定/解绑仍未执行，不将组件证据扩大为外部服务实测。

## Bot 感受与对方观察

`emotion-1` 的四维基线为 `(0, 0.3, 0, 0.3)`。
pleasure 范围 -1..1，其余为 0..1；精力不在 BotAffect 内。
衰减为 `baseline + (value - baseline) * 2**(-elapsed / half_life)`，
半衰期分别是 1800/1200/2400/3600 秒。

HumanObservation 保存主体、labels、置信度和期限，不是 Bot 状态。
例如 sadness 的 Bot 原始评估增量是 `(0, +0.03, +0.02, -0.02)`，
表示关心/注意，不把 Bot 愉悦直接设为负值。care 为
`(+0.12, -0.02, -0.06, -0.06)`，conflict 为
`(-0.12, +0.12, +0.14, +0.04)`；实际还受关系、能量、置信度和限幅影响。

单事件单维增量最多 0.15；相似刺激窗口 300 秒，最多 3 次，
累计最大维度变化 0.30。事件/观察 TTL 默认 7200 秒。
去重、相似刺激预算等 `_runtime` 必须随快照一起持久化，但不能公开到提示或普通日志。
正文仅识别保守第一人称自述，不对否定、引用、第三人称做简单子串判断。
模型只可建议有界增量；错误版本、NaN/Infinity、重复 JSON 键、未知字段回退规则。
公开 Bot 状态读取使用当前时间派生恢复，不伪造新事件或刷新持久版本。

`observe_only` 可保留观察计算，但不注入或自主发送；从绫冲突同样退让。
模式许可不是发送授权，所有行为硬闸门仍须通过。

## 关系与长夜

关系 score 为 0..1000，normalized=score/1000。
阶段阈值 100/300/600/850，依次为未建立、初识、熟悉、亲近、trusted 标签；
阶段不是独立 trust 维度的证据。
`relationship-1` 默认单事件绝对预算 6、时区日预算 24，
相似窗口最多累计 9；正负抵消和触顶也不返还预算。人工修改/冻结需理由、版本和审计。
未知维度保持未知，不从旧好感分制造来源。

night 状态为 awake/drowsy/settling/asleep/waking。
`energy=clamp(energy + elapsed/3600 * rate, 0, 100)`；
默认清醒 -4/小时、睡眠 +12/小时，跨醒来点分段结算。
5400 秒睡眠周期分 N1(0..300)、N2(300..1500)、N3(1500..3600)、REM(3600..5400)。
这是产品规则，不是心理或生理测量。
收尾等待 120 秒、醒后过渡 300 秒；只有匹配的真实成功回执才能完成待收尾。
固定宿主 after-sent 在发送失败后也触发，发送 bool 只表示找到平台，确认能力不可用；
健康行 `reply_confirmation=unavailable` 明示 unsupported，最终 HTTP/iframe 已验证。
待收尾超时取消回清醒/困倦，不自动重发；
无待回复的计划睡眠和手动睡眠可用。typed port 成功仅是组件证据，不代表生产投递。
补课有固定上界、高水位、原引用及字符限制，不重放离线积压发送。

## 行为与体验

主动先做硬否决，再按
`0.50*关系 + 0.30*社交需求 + 0.10*(愉悦+1)/2 + 0.10*(1-压力)` 评分。
默认主动/群主动关闭、白名单空、时区未配置；每日全局 6、每范围 2，
冷却 7200 秒、连续两次成功或 unknown 未获人类回复后停止。
这些参数已由原生 Config 映射；范围白名单按空白分隔的 `Context.scope_key` 解析，
不是页面 account_key。最终许可仍由来源、能力和发送前闸门决定。

意图状态：pending → reserved → generating → sending →
succeeded/failed/cancelled/unknown。sending 的持久 CAS 只允许一次分发尝试。
启动恢复取消旧待发意图，sending 变 unknown，额度保守占用，不自动重发。
宿主布尔发送结果不能生成成功行为事件，详见 [behavior.md](behavior.md)。

日记以 instance/Bot/人格/时区/日期形成稳定身份，有来源才生成；
梦要求实时 REM，每夜最多两次尝试。正文、自己的行为、他人言行、梦和未知来源分别标注。
私人分享必须按当前授权素材重新生成，不给模型原私人全文；
导出 action 与 subjective 两种记录使用稳定键，梦不变成 FACT。
目前外部合格后台/幂等写入缺能力，不能以功能开关替代接口能力。

## 持久化与故障

SQLite I/O 走线程，事务内不等待模型/网络。事件、幂等标记、多状态及关系来源贡献
原子提交；CAS 冲突重读重算，清除代际不允许重取新代际后回写旧内容。
默认正文 7 天、每场景 200 条、全库 10000 条，单条 8000 字符；
事件默认 30 天，非正文幂等、额度和关系来源账本不能因清理丢失撤销依据。
`none` 仍保存这些运行数据。

共享模型并发默认 1、队列 100、每日 48、输入/输出预算 4096/1024、
超时 30 秒；行为输出再限至 512。`OpenAIBinding` 仅接受原生
`ProviderOpenAIOfficial` 精确类型的纯文本 Chat Completions，不接受其他未验证 Provider。
Qwen 参数通过原生 Provider/SDK + 合成 transport 验证，不是生产模型调用证据。
输入为完整序列化 UTF-8 字节数加 system 字节数及 256 模板余量的上界，
不声称精确 usage，不依赖 tiktoken。请求副本限制 `max_tokens/n=1`、关闭重试和 Qwen thinking，
不发送 tools/图片/额外历史，不修改共享 Provider；返回正文同样按字节上界保守检查。
在途取消和额度见[最终预算证据](verification-budgets-final.md)：C50 31/31、F8 53/53，
真实 Provider 16 项实际执行、0 skip。新存储 window-03 11/11 与最终组件迁移 TTL
分别通过，见[最终性能证据](verification-performance-final.md)与[组件证据](verification-final.md)。

状态写失败时拒绝接受/停止自主，主聊天应能省略补充继续；
H02 读取故障及 H03 组合管理员豁免在最终三场景通过，历史失败保留，不承诺任意故障无影响。
备份须 SQLite backup 或停写后的一致快照；禁止只复制活动主库忽略 WAL。
迁移和回退见 [migration.md](migration.md)。F3 约束进入真实 History 和最终授权，
使用原绝对冷却及 native+legacy 用量，不伪造极大计数；未知约束明确拒绝。
迁移正文按原时间起最多七天，置顶不能延长迁移体验期限，非正文约束/幂等回执继续保留。
最终完整迁移84/84、V06四项已证明限制的阻断与恢复4/4通过；无生产迁移/回退实测。

原完整 C51-03：1万预填/1万测量/1万读取、20 worker，主提交10000/10000成功，
p95=48.801416ms，通过 <=50ms；余量1.198584ms（2.40%）不是生产充足保证。
历史 p95=221.628ms、139.081ms、56.895041ms 均为当时FAIL；
短诊断约40ms不代验，当前以[最终性能证据](verification-performance-final.md)为准。
