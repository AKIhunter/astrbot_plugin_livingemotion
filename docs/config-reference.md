# 配置参数参考

适用0.4.3。读者：管理员与集成维护者。来源：[`_conf_schema.json`](../_conf_schema.json)、
[`config.py`](../config.py)和[`runtime/config_help.py`](../runtime/config_help.py)；
2026-11-19核对。维护者在字段、默认值、校验、单位或UI帮助变化时同步，每次发布验证。

**全部32个布尔开关**在[使用手册](user-guide.md#全部功能开关)，本页列其余**101个参数**。
以下是全新安装默认值，显式存量值保留。页面字段、保存校验和运行限幅以源码为准；
旧兼容字段只供读取，不建议手工添加。保存过程见[排障](troubleshooting.md#保存与版本冲突)。

## 模式、人格与模型

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `mode` | `active` | `observe_only`仅观察；`active`参与表达与已授权行为 |
| `persona_mode` | `follow` | `follow`跟随、`explicit`指定、`none`不追加人格 |
| `persona_id` | 空 | 指定模式的原生人格ID，单独改ID不切换人格方式 |
| `timezone` | 空 | IANA时区，如Asia/Shanghai；城市名不能替代 |
| `provider_id` | 空 | 通用后台聊天模型；空值尝试当前真实会话模型 |
| `fallback_provider_id` | 空 | 请求派发前候选不可用时的备用，不用于未知请求重发 |
| `behavior_provider_id` | 空 | 主动聊天专用模型，空值沿用通用/当前会话 |
| `diary_provider_id` | 空 | 日记专用聊天模型 |
| `dream_provider_id` | 空 | 梦境专用聊天模型 |
| `catchup_provider_id` | 空 | 醒后补答专用聊天模型 |
| `closing_provider_id` | 空 | 随机晚安专用聊天模型 |
| `embedding_provider_id` | 空 | 本地向量记忆用原生embedding；LivingMemory模式不用此项 |
| `emotion_interval_seconds` | 600 | 同范围情绪模型最小间隔，秒；不是必调用周期 |
| `emotion_quiet_start_hour` | 3 | 情绪模型静默开始，本地小时0–23 |
| `emotion_quiet_end_hour` | 8 | 静默结束，本地小时0–23；等于开始时关闭静默 |
| `emotion_intensity` | `normal` | gentle×1.35 / normal×1.60 / intense×2.00；不改衰减速度 |

模型ID来自宿主候选，凭据在宿主管理。router指定上游编号会随列表调整变化，增删/排序后
应重新核对实际模型。聊天模型与向量模型不能互换。

## 主动范围、节奏与额度

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `autonomy_qq_ids` | 空 | 私聊QQ名单；逗号/空格等分隔，只匹配已有真实来源，空值不授权 |
| `autonomy_qq_group_ids` | 空 | 群号名单；空值覆盖已知真实QQ群，仍需群主动额外许可 |
| `muted_scopes` | 空 | 空格分隔真实scope_key，优先于允许名单，不是页面context_id |
| `active_start` | 00:00 | 主动活动时段开始，HH:MM，支持跨午夜 |
| `active_end` | 23:59 | 活动时段结束，不含边界，不得等于开始 |
| `dnd_start` | 01:00 | 主动免打扰开始，不阻止正常接收 |
| `dnd_end` | 08:00 | 主动免打扰结束，支持跨午夜 |
| `behavior_style` | `balanced` | gentle轻柔 / balanced自然 / lively活泼，不绕过硬额度 |
| `behavior_random_min_minutes` | 90 | 随机等待最短1–10080分钟，不大于最长 |
| `behavior_random_max_minutes` | 240 | 随机等待最长1–10080分钟 |
| `behavior_idle_minutes` | 20 | 至少安静1–1440分钟；群聊按全群活动 |
| `behavior_daily_limit` | 6 | 每日随机主动全局尝试额度；预留后失败也计入，当前承诺不占该额度 |
| `behavior_scope_daily_limit` | 2 | 同会话每日主动尝试额度 |
| `behavior_cooldown_seconds` | 7200 | 同会话主动尝试后冷却，秒 |
| `behavior_unanswered_limit` | 2 | 连续未回应达到上限后暂停；未知发送保守计入 |

## 作息、精力与醒后处理

以下时间按timezone解释。允许睡眠关闭时全部精力保持100%，参数保存不会隐式授权。

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `nap_start` | 13:00 | 计划午休开始，HH:MM |
| `nap_end` | 14:30 | 计划午休结束，不等于开始 |
| `fatigue_start` | 23:30 | 夜间疲劳开始 |
| `fatigue_end` | 07:00 | 疲劳消耗结束，不等于起床 |
| `deep_sleep_at` | 02:30 | 固定沉睡开始，须在夜间开始与基础起床之间 |
| `wake_at` | 08:00 | 基础起床，实际再加本周期赖床 |
| `lie_in_min_minutes` | 0 | 最少赖床，不大于最多 |
| `lie_in_max_minutes` | 90 | 最多赖床0–1440分钟，每周期只抽一次 |
| `wake_mode` | `chat` | chat私聊 / never禁聊天唤醒 / both私聊或群原生@；不唤醒沉睡 |
| `wake_reply_limit` | 10 | 聊天唤醒1–100次生成尝试，失败占轮数 |
| `wake_window_minutes` | 10 | 首次实际提交起固定窗口1–1440分钟，后续不续期 |
| `energy_reply_cost` | 2.0 | 0–100点/首次有效回复提交，0.1步进；重复/分段不多扣 |
| `energy_fatigue_per_minute` | 0.5 | 0–100点/分钟，夜间未睡眠消耗，0.1步进 |
| `energy_recovery_per_minute` | 1.0 | 0–100点/分钟，睡眠恢复；白天恢复另需开启 |
| `recovery_max_minutes` | 120 | 1–1440分钟，补觉不按起床截止时生效；只影响新周期 |
| `closing_lead_minutes` | 5 | 夜间开始前0–60分钟评估晚安 |
| `wake_greeting_texts` | 3条本地候选 | 用竖线分隔，随机取一条；可修改口吻 |

状态阈值、补觉和唤醒票据的严格边界见[睡眠规则](sleep-energy-rules.md)。

## 承诺

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `promise_max_active` | 3 | 旧配置字段，当前未接入执行；不能据此认为超过3条会拒绝登记 |
| `promise_max_depth` | 3 | 旧配置字段，当前未接入执行；不能据此保证限制拆分/续承诺 |
| `promise_advance_limit` | 3 | 旧配置字段，当前未接入执行；服务实际用固定3次提前上限 |
| `promise_tick_seconds` | 15 | 扫描到期承诺间隔，秒；最小15 |
| `promise_recall_limit` | 4 | 登记时预取合法记忆材料条数 |
| `promise_trace_ttl_hours` | 24.0 | 兑现后片段缓存小时数，到期回到普通检索 |
| `coupling_promise_actions` | `auto` | auto检测动作能力 / on动作模式 / off纯文字；缺能力不会伪造执行 |

实际时间档、去重、失败恢复与取消见[承诺说明](promise.md)和[延迟动作](promise-actions-20261116.md)。
上述三个数值仍可保存，但当前PromiseService/PromiseStore不读取这些配置。
这属于现有实现限制，本版只纠正文档与帮助，未改变登记、执行或额度。

## 日记与梦境

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `diary_at` | 23:00 | 当地计划评估时间，不保证准点生成 |
| `diary_retries` | 2 | 明确失败重试0–2次，每次占预算；未知结果不盲重试 |
| `diary_retention_days` | 30 | 未固定日记保留1–365天 |
| `dream_theme_pool` | 内置主题池 | JSON列表/逗号/换行，2–32项，每次两个不同主题 |
| `dream_owner_qq` | 空 | 一个通知接收人，必须已有真实私聊 |
| `dream_per_night` | 2 | 每睡眠周期尝试1–2次，失败计入 |
| `dream_retention_days` | 7 | 未固定梦境保留1–30天 |
| `dream_half_life_seconds` | 86400 | 梦境清晰度半衰期，秒 |
| `experience_body_chars` | 2000 | 日记/梦正文1–2000字符，标题/日期/天气不占正文额度；旧超限值按2000执行 |

## 天气

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `home_city` | 空 | 公开住所城市，不填私人详细地址，不替代时区 |
| `weather_poll_seconds` | 14400 | 实况抓取周期，秒；受抓取窗口和失败退避约束 |
| `weather_transition_seconds` | 900 | 天气权重指数过渡，秒；0立即生效 |
| `weather_weight_scale` | 1.0 | 四维回落目标天气偏移倍率，0不影响，2加倍 |
| `weather_stale_seconds` | 7200 | 缓存保鲜，秒；过期权重回中性 |
| `weather_forecast_days` | 7 | 一次预取预报天数 |
| `weather_forecast_refresh_seconds` | 21600 | 预报刷新周期，秒 |
| `weather_window_start_hour` | 6 | 本地抓取窗口开始小时 |
| `weather_window_end_hour` | 1 | 窗口结束小时，支持跨夜；等于开始表示全天 |
| `weather_degrade_after_failures` | 3 | 连续失败后转低频日粒度预报 |
| `weather_recover_after_successes` | 2 | 低频连续成功后恢复常规频率 |

这些值控制网络天气服务，不调用LLM；失败可能使用合法缓存、当天预报或中性回落。

## 关系

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `relationship_stage_names` | 反感/陌生/友好/亲近/独特 | 5项JSON数组；阈值11/25/45/100，普通互动最高99 |
| `relationship_stage_descriptions` | 4项空文本 | 前四档相处描述，4项JSON，每项最多1000字 |
| `relationship_special_description` | 空 | 100分独特关系说明最多1000字；对象备注优先 |
| `relationship_image_refusal_averse` | 90 | 反感阶段生图婉拒概率，0–100整数百分比 |
| `relationship_image_refusal_unfamiliar` | 60 | 陌生阶段概率，0–100 |
| `relationship_image_refusal_friendly` | 30 | 友好阶段概率，0–100 |
| `relationship_image_refusal_close` | 10 | 亲近阶段概率，0–100 |
| `relationship_image_refusal_unique` | 5 | 独特阶段概率，0–100 |

0不因关系随机拒绝，100必定婉拒。只对个人生图与新图片承诺抽样，
同请求一次；已有承诺继续履行。见[好感V2](relationship-scoring-v2.md)和[生图婉拒](relationship-image-refusal.md)。

## 归档与后台资源

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `window_days` | 7 | 正文素材保留1–7天，同时受条数限制 |
| `window_per_scope` | 200 | 单真实会话正文1–200条 |
| `window_global` | 10000 | 全部正文总数1–10000条 |
| `body_max_chars` | 8000 | 单条归档正文1–8000字符，超长截断 |
| `event_days` | 30 | 不含正文的事件保留天数 |
| `scheduler_seconds` | 60 | 后台评估1–3600秒，不等于每轮调用模型 |
| `model_concurrency` | 1 | 本插件后台模型并发1–8 |
| `queue_size` | 100 | 队列容量1–1000，不是每日额度 |
| `model_daily_limit` | 48 | 每日后台模型预留次数，失败计入 |
| `model_input_tokens` | 32768 | 名称为历史兼容；实际输入按UTF-8字节上界估计，1–32768，不是账单Token |
| `model_output_tokens` | 1024 | 普通后台请求输出1–8192 Token；日记/梦境独立8192，仍受上游限制 |
| `model_timeout_seconds` | 30 | 后台超时1–120秒，未知请求不自动重发 |

## 提示词文本

| 参数 | 默认 | 用途 / 单位与边界 |
| --- | --- | --- |
| `tone_prompt_text` | 内置情绪与毒舌预置 | 最多2000字，启用时不能为空 |
| `relationship_prompt_text` | 内置关系与行动边界预置 | 最多2000字，启用时不能为空 |
| `night_prompt_text` | 内置作息与收尾预置 | 最多2000字，启用时不能为空 |
| `character_preset` | `sarcastic` | sarcastic毒舌 / cute可爱 / gentle温柔 / custom自定义 |
| `character_custom_text` | 空 | 自定义性格，最多10000字，启用自定义时不能为空 |
| `character_preset_texts` | `{}` | JSON字符串保存三个内置预置的编辑稿，各最多10000字；页面分别编辑 |

文本字段不代表功能许可，注入开关见使用手册。配置层仍是平铺字段。

## 兼容字段与迁移

`LEGACY_FIELDS`的8项不在公开schema：`memory_mode`、`memory_export`、
`night_enabled`、`night_block_chat`、`sleep_at`、`night_policy_version`、
`autonomy_scopes`、`night_schedule_enabled`。保留读取是为了旧配置兼容，
不把旧字段当作新的独立权限开关；新页面拒绝保存已撤下的作息键。
缺少allow_sleep时才从旧作息许可迁移；显式allow_sleep始终优先。
旧配置缺少人格共享和规则版本时保留兼容识别，详见[技术说明](technical-guide.md#配置与升级)。
