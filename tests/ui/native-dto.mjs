// Generated from real Console; synthetic host, no model or sends.
export const nativeDTO = {
  "config": {
    "revision": "3a97bdc532db1eece287d8deed200726050525200876702c9afa31a42aec412e",
    "source": "AstrBot native plugin configuration",
    "values": {
      "enabled": true,
      "mode": "observe_only",
      "memory_read": false,
      "autonomy_enabled": false,
      "group_autonomy_enabled": false,
      "emotion_model_enabled": false,
      "dream_enabled": false,
      "dream_theme_pool": "[\"赛博朋克\", \"绿野仙踪\", \"生活日常\", \"星际漫游\", \"海底王国\", \"古堡奇遇\", \"森林童话\", \"校园时光\", \"蒸汽幻想\", \"云端旅行\", \"四季庭院\", \"时光回廊\"]",
      "dream_owner_notify": false,
      "dream_owner_qq": "",
      "diary_enabled": false,
      "persona_mode": "follow",
      "persona_id": "",
      "timezone": "Asia/Shanghai",
      "provider_id": "",
      "fallback_provider_id": "",
      "autonomy_qq_ids": "",
      "autonomy_qq_group_ids": "",
      "muted_scopes": "",
      "night_schedule_enabled": false,
      "wake_at": "08:00",
      "diary_at": "23:00",
      "diary_backfill_yesterday": false,
      "scheduler_seconds": 60,
      "dnd_start": "01:00",
      "dnd_end": "08:00",
      "active_start": "00:00",
      "active_end": "23:59",
      "behavior_daily_limit": 6,
      "behavior_scope_daily_limit": 2,
      "behavior_cooldown_seconds": 7200,
      "behavior_unanswered_limit": 2,
      "behavior_random_min_minutes": 90,
      "behavior_random_max_minutes": 240,
      "behavior_idle_minutes": 20,
      "behavior_style": "balanced",
      "behavior_emotional_share": true,
      "behavior_provider_id": "",
      "diary_retries": 2,
      "dream_per_night": 2,
      "diary_retention_days": 30,
      "dream_retention_days": 7,
      "dream_half_life_seconds": 86400,
      "experience_body_chars": 2000,
      "model_concurrency": 1,
      "queue_size": 100,
      "model_daily_limit": 48,
      "emotion_interval_seconds": 600,
      "emotion_quiet_start_hour": 3,
      "emotion_quiet_end_hour": 8,
      "emotion_intensity": "normal",
      "model_input_tokens": 32768,
      "model_output_tokens": 1024,
      "model_timeout_seconds": 30,
      "window_days": 7,
      "window_per_scope": 200,
      "window_global": 10000,
      "body_max_chars": 8000,
      "event_days": 30,
      "persona_shared_state": true,
      "allow_sleep": true,
      "nap_enabled": true,
      "nap_start": "13:00",
      "nap_end": "14:30",
      "fatigue_start": "23:30",
      "fatigue_end": "07:00",
      "deep_sleep_at": "02:30",
      "lie_in_min_minutes": 0,
      "lie_in_max_minutes": 90,
      "wake_mode": "chat",
      "wake_reply_limit": 3,
      "wake_window_minutes": 10,
      "energy_reply_cost": 4.0,
      "energy_fatigue_per_minute": 0.8,
      "energy_recovery_per_minute": 1.5,
      "catchup_enabled": true,
      "catchup_reply_enabled": true,
      "closing_enabled": false,
      "closing_random": false,
      "closing_lead_minutes": 5,
      "diary_provider_id": "",
      "dream_provider_id": "",
      "catchup_provider_id": "",
      "closing_provider_id": "",
      "home_city": "",
      "embedding_provider_id": "",
      "livingmemory_enabled": false,
      "memory_write": false,
      "relationship_stage_names": "[\"反感\",\"陌生\",\"友好\",\"亲近\",\"独特\"]",
      "relationship_stage_descriptions": "[\"\",\"\",\"\",\"\"]",
      "relationship_special_description": "",
      "wake_autocatchup_enabled": true,
      "wake_greeting_enabled": true,
      "wake_greeting_texts": "刚醒，我看看之前你们说了什么。|我醒了，先把这几小时翻一翻。|醒了…看看都说了什么。",
      "relationship_edit_enabled": false
    },
    "fields": [
      {
        "key": "enabled",
        "label": "启用插件",
        "section": "quick_start",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "启用生活状态与配置功能。",
        "details": "关闭后停止接收新生活事件；开启后仍遵守运行模式和各模块开关。",
        "example": "想先观察状态：开启插件，运行模式选“仅观察”。",
        "parent": "",
        "level": 0
      },
      {
        "key": "mode",
        "label": "运行模式",
        "section": "quick_start",
        "value": "observe_only",
        "type": "enum",
        "advanced": false,
        "help": "选择正常运行或仅观察。",
        "details": "仅观察可记录状态，但不注入情绪表达或自主发送；正常运行也需要各行为开关和授权范围。",
        "example": "调试配置用“仅观察”；确认后再选“正常运行”。",
        "parent": "",
        "level": 0,
        "options": [
          {
            "value": "active",
            "label": "正常运行"
          },
          {
            "value": "observe_only",
            "label": "仅观察"
          }
        ]
      },
      {
        "key": "memory_read",
        "label": "允许读取记忆",
        "section": "memory",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "允许从所选记忆后端检索。",
        "details": "读取仍按会话来源、用途和身份权限过滤；不可用时不会回退读取私有记忆。",
        "example": "需要根据聊天经历找话题：开启读取；仅记录不检索：关闭。",
        "parent": "livingmemory_enabled",
        "level": 1
      },
      {
        "key": "autonomy_enabled",
        "label": "允许主动找人",
        "section": "behavior",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "允许 TA 等待合适时机主动开口。",
        "details": "需要正常运行、有效时区和号码范围；结合记忆、关系与情绪选话题，先检查作息、安静时间和额度。",
        "example": "填私聊QQ号码，设置随机90–240分钟，开启后保存；到点仍可能因不适合开口而等待。",
        "parent": "",
        "level": 0
      },
      {
        "key": "group_autonomy_enabled",
        "label": "允许群聊主动行为",
        "section": "behavior",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "允许在已授权的群聊主动发言。",
        "details": "群聊总开关独立于私聊；关闭时即使填了群号也不主动发送，不向群聊分享私聊情绪或私有记忆。",
        "example": "只希望主动私聊：保持关闭，群号可留空。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "emotion_model_enabled",
        "label": "模型辅助情绪分析",
        "section": "emotion",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "允许模型辅助细化情绪。",
        "details": "关闭时保留本地情绪规则；开启后按间隔和全局模型预算调用，情绪是主观状态而非事实。",
        "example": "只想低成本体验：关闭；需要细化语气：开启并设间隔300秒。",
        "parent": "",
        "level": 0
      },
      {
        "key": "dream_enabled",
        "label": "生成梦境",
        "section": "experience",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "睡眠期间允许生成梦境。",
        "details": "需要睡眠周期、素材、模型和预算；梦境是想象内容，不当作真实事实或人际证据。",
        "example": "想体验生活感：开启；只要实用记录：关闭。",
        "parent": "",
        "level": 0
      },
      {
        "key": "dream_theme_pool",
        "label": "梦境主题池",
        "section": "experience",
        "value": "[\"赛博朋克\", \"绿野仙踪\", \"生活日常\", \"星际漫游\", \"海底王国\", \"古堡奇遇\", \"森林童话\", \"校园时光\", \"蒸汽幻想\", \"云端旅行\", \"四季庭院\", \"时光回廊\"]",
        "type": "string",
        "advanced": false,
        "help": "每次随机抽取两个不同主题。",
        "details": "接受JSON列表或逗号、换行分隔的2–32个主题，每项最多40字；结合TA当日六维情绪决定梦的基调。",
        "example": "赛博朋克，绿野仙踪，生活日常，星际漫游，海底王国，古堡奇遇，森林童话，校园时光，蒸汽幻想，云端旅行，四季庭院，时光回廊",
        "parent": "dream_enabled",
        "level": 1
      },
      {
        "key": "dream_owner_notify",
        "label": "梦中惊醒给主人发消息",
        "section": "experience",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "夜间被愤怒或恐惧的梦惊醒时联系主人。",
        "details": "默认关闭。开启后只在自动梦境保存成功且仍处同一夜晚时，向已核验的主人私聊发一次消息；手动生成不会发送。此专用开关允许夜间联系，仍遵守静默、模式、身份和每日额度。",
        "example": "先填写主人QQ，确认存在真实私聊来源，再开启。",
        "parent": "dream_enabled",
        "level": 1
      },
      {
        "key": "dream_owner_qq",
        "label": "主人QQ",
        "section": "experience",
        "value": "",
        "type": "string",
        "advanced": false,
        "help": "接收梦中惊醒消息的主人QQ。",
        "details": "仅允许一个合法号码；不能凭手填号码创建发送路由，必须已经在宿主中建立此人格的真实QQ私聊。",
        "example": "填写主人的QQ号码。",
        "parent": "dream_enabled",
        "level": 1
      },
      {
        "key": "diary_enabled",
        "label": "生成日记",
        "section": "experience",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "自动生成私人日记。",
        "details": "只使用可用且符合来源权限的素材，生成消耗模型预算；日记属于主观经历。",
        "example": "开启后在本地23:00计划生成当天日记。",
        "parent": "",
        "level": 0
      },
      {
        "key": "persona_mode",
        "label": "人格选择方式",
        "section": "persona",
        "value": "follow",
        "type": "enum",
        "advanced": false,
        "help": "跟随聊天人格，或固定一个原生人格。",
        "details": "跟随模式使用当前会话人格；指定模式必须选择有效人格；不使用时不借用其他人格。",
        "example": "多个聊天各有角色：选“跟随会话人格”；固定角色：选“指定人格”并选择下方人格。",
        "parent": "",
        "level": 0,
        "options": [
          {
            "value": "follow",
            "label": "跟随会话人格"
          },
          {
            "value": "explicit",
            "label": "指定人格"
          },
          {
            "value": "none",
            "label": "不使用"
          }
        ]
      },
      {
        "key": "persona_id",
        "label": "原生人格",
        "section": "persona",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "指定模式使用的 AstrBot 人格。",
        "details": "从原生人格下拉选择；跟随模式下由会话决定，单独选此项不会切换选择方式。",
        "example": "先把人格选择方式改为“指定人格”，再选择“大姐姐”。",
        "parent": "persona_mode",
        "level": 1,
        "options": [
          {
            "value": "fixture-persona",
            "label": "真实 DTO · 合成人格"
          }
        ]
      },
      {
        "key": "timezone",
        "label": "本地时区",
        "section": "quick_start",
        "value": "Asia/Shanghai",
        "type": "string",
        "advanced": false,
        "help": "作息和每日额度使用的本地时区。",
        "details": "填写 IANA 时区；自动作息和主动调度需要有效时区。不是城市名或 UTC 偏移量。",
        "example": "中国大陆填 Asia/Shanghai，日本填 Asia/Tokyo。",
        "parent": "",
        "level": 0
      },
      {
        "key": "provider_id",
        "label": "默认生成模型",
        "section": "quick_start",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "各后台生成任务默认使用的聊天模型。",
        "details": "从 AstrBot 已配置的模型中选择；留空跟随会话模型。情绪细化使用此默认模型；日记、梦境、主动聊天、醒后补答和晚安等任务可用各自专用模型覆盖此默认值。",
        "example": "设置通用后台模型，再按需为日记或梦境单独选模型。",
        "parent": "",
        "level": 0,
        "provider_kind": "chat",
        "options": [
          {
            "value": "",
            "label": "跟随当前聊天模型"
          },
          {
            "value": "fixture-chat",
            "label": "合成聊天模型"
          }
        ]
      },
      {
        "key": "fallback_provider_id",
        "label": "备用生成模型",
        "section": "quick_start",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "请求发出前可使用的备用模型。",
        "details": "只在尚未发出请求时回退；超时或结果未知的请求不会自动重发，避免重复费用和行为。",
        "example": "主模型暂不可用时，选择已配置的备用聊天模型。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "provider_kind": "chat",
        "options": [
          {
            "value": "",
            "label": "跟随当前聊天模型"
          },
          {
            "value": "fixture-chat",
            "label": "合成聊天模型"
          }
        ]
      },
      {
        "key": "autonomy_qq_ids",
        "label": "主动私聊 QQ 号码",
        "section": "behavior",
        "value": "",
        "type": "string",
        "advanced": false,
        "help": "允许主动私聊的 QQ 号码。",
        "details": "手写号码或在输入框中选择建议；逗号、空格或换行分隔。只匹配已有真实QQ私聊，不会凭号码创建会话。空白不授权新私聊。",
        "example": "填 12345678, 23456789，允许主动联系这两位；从下拉选择会追加到现有名单。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "autonomy_qq_group_ids",
        "label": "主动发言 QQ 群号",
        "section": "behavior",
        "value": "",
        "type": "string",
        "advanced": false,
        "help": "限定允许主动发言的 QQ 群号。",
        "details": "填写群号码而非成员QQ号；只匹配已知真实QQ群，并且必须同时开启群聊主动行为。留空表示所有已知真实QQ群；群总开关、静默、时段及预算仍然生效。群号与私聊QQ号分开判断，私聊名单留空仍不授权私聊。",
        "example": "留空并开启群聊总开关可作用于所有已知真实QQ群；填写 34567890, 45678901 则只作用于这些群。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "muted_scopes",
        "label": "静默范围",
        "section": "behavior",
        "value": "",
        "type": "string",
        "advanced": false,
        "help": "暂停指定真实会话的主动行为。",
        "details": "填写现有完整范围标识，多个用空格分隔；静默优先于允许名单。通常先从号码名单移除即可。",
        "example": "临时停用一个范围：复制该真实会话scope_key填入；清空后仍需满足号码授权。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "night_schedule_enabled",
        "label": "自动作息",
        "section": "night",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "自动按作息维护睡眠周期。",
        "details": "启用前填写时区；自动作息与允许睡眠分别控制时间记录和聊天阻断。旧配置保持原行为，直至完成新规则迁移。",
        "example": "时区Asia/Shanghai，夜间23:30、沉睡02:30、基础起床08:00。",
        "parent": "",
        "level": 0
      },
      {
        "key": "wake_at",
        "label": "基础起床时间",
        "section": "night",
        "value": "08:00",
        "type": "string",
        "advanced": false,
        "help": "未加赖床时间的基础起床时刻。",
        "details": "每个夜晚只抽取一次赖床值并保存；刷新页面不会重新抽取，实际起床可能更晚。",
        "example": "08:00、赖床0–90分钟，实际起床在08:00至09:30。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "diary_at",
        "label": "日记生成时间",
        "section": "experience",
        "value": "23:00",
        "type": "string",
        "advanced": false,
        "help": "每天计划生成日记的本地时间。",
        "details": "24小时HH:MM；调度是评估机会，并非准点保证，缺少素材或预算时可能跳过。",
        "example": "23:00适合在一天结束时回顾。",
        "parent": "diary_enabled",
        "level": 1
      },
      {
        "key": "diary_backfill_yesterday",
        "label": "补写昨天日记",
        "section": "experience",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "允许补写昨天缺失的日记。",
        "details": "只补昨天，不遍历久远历史；仍受素材有效期、重试上限和模型预算限制。",
        "example": "昨天服务暂停，可开启以尝试补写昨天。",
        "parent": "diary_enabled",
        "level": 1
      },
      {
        "key": "scheduler_seconds",
        "label": "调度间隔",
        "section": "emotion",
        "value": 60,
        "type": "integer",
        "advanced": true,
        "help": "后台评估任务的间隔秒数。",
        "details": "范围1–3600；唤醒调度检查，不代表每轮都会调用模型或发送消息。",
        "example": "60表示每分钟评估一次；无需为随机主动行为改成很小的值。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "秒"
      },
      {
        "key": "dnd_start",
        "label": "免打扰开始",
        "section": "behavior",
        "value": "01:00",
        "type": "string",
        "advanced": false,
        "help": "主动行为免打扰的开始时间。",
        "details": "只限制自主发言，不阻止正常接收消息；支持跨午夜，免打扰优先于主动时段。",
        "example": "01:00至08:00，凌晨不主动打扰。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "dnd_end",
        "label": "免打扰结束",
        "section": "behavior",
        "value": "08:00",
        "type": "string",
        "advanced": false,
        "help": "主动行为免打扰的结束时间。",
        "details": "本地HH:MM，与开始时间配对；相同时间会被拒绝，避免把空区间当全天。",
        "example": "开始23:00、结束08:00，次日8点结束免打扰。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "active_start",
        "label": "主动时段开始",
        "section": "behavior",
        "value": "00:00",
        "type": "string",
        "advanced": false,
        "help": "每天允许主动行为的开始时间。",
        "details": "使用本地24小时HH:MM，与结束时间组成主动窗口；免打扰与睡眠限制仍优先。",
        "example": "09:00至22:00，表示只在白天与晚间尝试。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "active_end",
        "label": "主动时段结束",
        "section": "behavior",
        "value": "23:59",
        "type": "string",
        "advanced": false,
        "help": "每天允许主动行为的结束时间。",
        "details": "结束边界不包含在主动窗口内；开始晚于结束表示跨午夜。两端不能相同。",
        "example": "开始20:00、结束00:30，表示可延续到次日零点半之前。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "behavior_daily_limit",
        "label": "每日主动行为总额度",
        "section": "behavior",
        "value": 6,
        "type": "integer",
        "advanced": false,
        "help": "所有会话每天的主动尝试总额度。",
        "details": "按本地日统计；失败或结果未知的尝试也占用额度，不靠重试恢复配额。",
        "example": "填6表示所有私聊和群聊合计最多6次尝试。",
        "parent": "autonomy_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "behavior_scope_daily_limit",
        "label": "每个会话每日主动额度",
        "section": "behavior",
        "value": 2,
        "type": "integer",
        "advanced": false,
        "help": "一个真实会话每天的主动尝试额度。",
        "details": "与总额度同时生效；到达任一上限就停止当日尝试。",
        "example": "总额度6、每个会话2，单个好友当天最多2次。",
        "parent": "autonomy_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "behavior_cooldown_seconds",
        "label": "主动行为冷却",
        "section": "behavior",
        "value": 7200,
        "type": "integer",
        "advanced": false,
        "help": "同一会话主动尝试后的冷却时间。",
        "details": "单位秒；和随机等待共同约束，不会因为新话题立即绕过冷却。",
        "example": "7200表示至少冷却2小时。",
        "parent": "autonomy_enabled",
        "level": 1,
        "step": 1,
        "unit": "秒"
      },
      {
        "key": "behavior_unanswered_limit",
        "label": "未回应次数上限",
        "section": "behavior",
        "value": 2,
        "type": "integer",
        "advanced": false,
        "help": "连续未获回应后停止主动的次数。",
        "details": "已确认或结果未知的发送都会保守计入；对方回复后才可能重新获得机会。",
        "example": "填2，连续两次没有回应就先停下来。",
        "parent": "autonomy_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "behavior_random_min_minutes",
        "label": "随机等待最短时间",
        "section": "behavior",
        "value": 90,
        "type": "integer",
        "advanced": false,
        "help": "随机等待的最短分钟数。",
        "details": "每次机会后重新安排等待，范围1–10080分钟，最短不能大于最长。等待结束不保证发送。",
        "example": "90至240，表示随机等待1.5至4小时后再评估。",
        "parent": "autonomy_enabled",
        "level": 1,
        "step": 1,
        "unit": "分钟",
        "min": 1,
        "max": 10080
      },
      {
        "key": "behavior_random_max_minutes",
        "label": "随机等待最长时间",
        "section": "behavior",
        "value": 240,
        "type": "integer",
        "advanced": false,
        "help": "随机等待的最长分钟数。",
        "details": "这是下次评估机会的上界；到点仍会检查睡眠、活跃聊天、关系、话题和预算。",
        "example": "和最短都填120，评估间隔固定为2小时。",
        "parent": "autonomy_enabled",
        "level": 1,
        "step": 1,
        "unit": "分钟",
        "min": 1,
        "max": 10080
      },
      {
        "key": "behavior_idle_minutes",
        "label": "聊天结束后安静时间",
        "section": "behavior",
        "value": 20,
        "type": "integer",
        "advanced": false,
        "help": "聊天安静多久后才尝试主动。",
        "details": "范围1–1440分钟；私聊看当前会话，群聊看全群最近消息。活跃时先不插话。",
        "example": "20表示最近20分钟内仍有聊天就继续等待。",
        "parent": "autonomy_enabled",
        "level": 1,
        "step": 1,
        "unit": "分钟",
        "min": 1,
        "max": 1440
      },
      {
        "key": "behavior_style",
        "label": "主动节奏",
        "section": "behavior",
        "value": "balanced",
        "type": "enum",
        "advanced": false,
        "help": "选择轻柔、自然或活泼的主动节奏。",
        "details": "影响开口意愿和动机；随机等待、安静时间、额度等硬限制始终生效。",
        "example": "不喜欢打扰选“轻柔”；想多聊一些选“活泼”。",
        "parent": "autonomy_enabled",
        "level": 1,
        "options": [
          {
            "value": "gentle",
            "label": "轻柔"
          },
          {
            "value": "balanced",
            "label": "自然"
          },
          {
            "value": "lively",
            "label": "活泼"
          }
        ]
      },
      {
        "key": "behavior_emotional_share",
        "label": "允许分享心情",
        "section": "behavior",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "允许熟悉私聊关系中轻轻分享心情。",
        "details": "只在合适的私聊关系下使用；不索取安慰、不强求回复，也不把私聊情绪带入群聊。",
        "example": "可出现“今天有点累，想听听你今天的趣事”；关闭后少用此类动机。",
        "parent": "autonomy_enabled",
        "level": 1
      },
      {
        "key": "behavior_provider_id",
        "label": "主动聊天模型",
        "section": "behavior",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "主动聊天专用模型。",
        "details": "留空沿用默认或当前聊天模型；仍受全局模型预算与主动行为额度约束。",
        "example": "主动聊天选轻量模型，日常回复继续使用主模型。",
        "parent": "autonomy_enabled",
        "level": 1,
        "provider_kind": "chat",
        "options": [
          {
            "value": "",
            "label": "跟随当前聊天模型"
          },
          {
            "value": "fixture-chat",
            "label": "合成聊天模型"
          }
        ]
      },
      {
        "key": "diary_retries",
        "label": "日记重试次数",
        "section": "experience",
        "value": 2,
        "type": "integer",
        "advanced": false,
        "help": "日记失败后的重试上限。",
        "details": "范围0–2；每次尝试都消耗预算，未知结果不被随意视为失败重发。",
        "example": "0不重试；2允许在明确可重试失败后有限再试。",
        "parent": "diary_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "dream_per_night",
        "label": "每夜梦境上限",
        "section": "experience",
        "value": 2,
        "type": "integer",
        "advanced": false,
        "help": "每个睡眠周期的梦境尝试上限。",
        "details": "范围1–2；所有尝试计入本周期额度，失败不会让额度无限恢复。",
        "example": "1表示每晚最多尝试一次梦境。",
        "parent": "dream_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "diary_retention_days",
        "label": "日记保留时间",
        "section": "experience",
        "value": 30,
        "type": "integer",
        "advanced": false,
        "help": "未固定日记的保留天数。",
        "details": "范围1–365；到期清理未固定记录，已固定记录按保留规则处理。",
        "example": "30表示保留最近约一个月的未固定日记。",
        "parent": "diary_enabled",
        "level": 1,
        "step": 1,
        "unit": "天"
      },
      {
        "key": "dream_retention_days",
        "label": "梦境保留时间",
        "section": "experience",
        "value": 7,
        "type": "integer",
        "advanced": false,
        "help": "未固定梦境的保留天数。",
        "details": "范围1–30；与清晰度衰减分别控制保存时间和显示感受。",
        "example": "7表示保存约一周的未固定梦境。",
        "parent": "dream_enabled",
        "level": 1,
        "step": 1,
        "unit": "天"
      },
      {
        "key": "dream_half_life_seconds",
        "label": "梦境清晰度半衰期",
        "section": "experience",
        "value": 86400,
        "type": "integer",
        "advanced": false,
        "help": "梦境清晰度减半需要的时间。",
        "details": "单位秒；清晰度随时间衰减，不修改梦境为真实内容，也不替代保留期限。",
        "example": "86400表示一天后清晰度约减半。",
        "parent": "dream_enabled",
        "level": 1,
        "step": 1,
        "unit": "秒"
      },
      {
        "key": "experience_body_chars",
        "label": "日记与梦境字数上限",
        "section": "experience",
        "value": 2000,
        "type": "integer",
        "advanced": false,
        "help": "一篇日记或梦境的字数上限。",
        "details": "范围1–8000字符，用于限制生成记录体积；Token预算另行限制。",
        "example": "2000限制每篇正文最多约2000字符。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "model_concurrency",
        "label": "模型并发上限",
        "section": "emotion",
        "value": 1,
        "type": "integer",
        "advanced": true,
        "help": "后台模型任务同时执行的上限。",
        "details": "范围1–8；只限制本插件任务，与AstrBot普通聊天并发配置分开。",
        "example": "1适合轻量部署；2允许两个后台任务并行。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "queue_size",
        "label": "模型队列上限",
        "section": "emotion",
        "value": 100,
        "type": "integer",
        "advanced": false,
        "help": "等待执行的后台任务队列容量。",
        "details": "范围1–1000；队列有界，容量不是每日调用额度。",
        "example": "100表示最多排队100个任务。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "model_daily_limit",
        "label": "每日模型调用上限",
        "section": "emotion",
        "value": 48,
        "type": "integer",
        "advanced": true,
        "help": "每天后台模型调用的总预算。",
        "details": "正整数次；跨情绪、日记、梦境和行为共用，预留后的失败尝试也计入。",
        "example": "48表示每天最多预留48次本插件后台调用。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "emotion_interval_seconds",
        "label": "情绪分析间隔",
        "section": "emotion",
        "value": 600,
        "type": "integer",
        "advanced": false,
        "help": "同一范围情绪分析的最小间隔。",
        "details": "单位秒，控制模型细化频率；不会保证到点调用，必须有可用事件、模型和预算。静默时段不调用模型，只保留本地规则增量。",
        "example": "600表示至少隔10分钟再分析一次。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "秒"
      },
      {
        "key": "emotion_quiet_start_hour",
        "label": "情绪静默开始（小时）",
        "section": "emotion",
        "value": 3,
        "type": "integer",
        "advanced": false,
        "help": "情绪静默时段的开始小时。",
        "details": "按本地时区24小时制填写0–23；与结束小时相同表示不启用静默。静默只跳过模型分析，本地规则仍随聊天生效。",
        "example": "3表示03:00起不调用模型；想连凌晨也分析就与结束设为同一小时。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "时",
        "min": 0,
        "max": 23
      },
      {
        "key": "emotion_quiet_end_hour",
        "label": "情绪静默结束（小时）",
        "section": "emotion",
        "value": 8,
        "type": "integer",
        "advanced": false,
        "help": "情绪静默时段的结束小时。",
        "details": "按本地时区24小时制填写0–23，结束小时本身恢复分析。开始大于结束表示跨午夜。",
        "example": "8表示08:00恢复模型分析；开始22、结束6表示22:00到次日06:00静默。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "时",
        "min": 0,
        "max": 23
      },
      {
        "key": "emotion_intensity",
        "label": "情绪强度",
        "section": "emotion",
        "value": "normal",
        "type": "enum",
        "advanced": false,
        "help": "情绪起伏的三档强度。",
        "details": "只放大单次情绪增量与同类刺激的累计上限，不改半衰期和衰减速度；数值越大，回复时情绪变化越明显。",
        "example": "平常为推荐档；嫌情绪变化太快要选保守，嫌太平淡选激进。改完在设置页保存即可生效。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "options": [
          {
            "value": "gentle",
            "label": "保守"
          },
          {
            "value": "normal",
            "label": "平常"
          },
          {
            "value": "intense",
            "label": "激进"
          }
        ]
      },
      {
        "key": "model_input_tokens",
        "label": "模型输入上限",
        "section": "emotion",
        "value": 32768,
        "type": "integer",
        "advanced": true,
        "help": "每次后台模型任务的输入上限。",
        "details": "范围1–32768 Token；素材会受此预算限制，不是字符数或每日总量。",
        "example": "4096适合短任务；较长日记可以适度提高。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "Token"
      },
      {
        "key": "model_output_tokens",
        "label": "模型输出上限",
        "section": "emotion",
        "value": 1024,
        "type": "integer",
        "advanced": true,
        "help": "每次后台任务请求的输出Token上限。",
        "details": "范围1–8192；部分主动行为会采用更小的内部上限，以控制长度和打扰。",
        "example": "1024可用于日记；主动消息仍会更简短。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "Token"
      },
      {
        "key": "model_timeout_seconds",
        "label": "模型调用超时",
        "section": "emotion",
        "value": 30,
        "type": "integer",
        "advanced": true,
        "help": "后台模型任务的超时时间。",
        "details": "范围1–120秒；超时不证明上游没有执行，结果未知时不会自动重复发送。",
        "example": "30秒适合通常响应较快的模型；较慢模型可填60。",
        "parent": "emotion_model_enabled",
        "level": 1,
        "step": 1,
        "unit": "秒"
      },
      {
        "key": "window_days",
        "label": "聊天素材保留时间",
        "section": "memory",
        "value": 7,
        "type": "integer",
        "advanced": true,
        "help": "聊天正文素材保留多少天。",
        "details": "范围1–7；同时受每会话和全局条数上限约束，最早到达的限制生效。",
        "example": "7表示最多使用最近一周的正文素材。",
        "parent": "livingmemory_enabled",
        "level": 1,
        "step": 1,
        "unit": "天"
      },
      {
        "key": "window_per_scope",
        "label": "每个会话素材上限",
        "section": "memory",
        "value": 200,
        "type": "integer",
        "advanced": true,
        "help": "一个真实会话最多保留的素材条数。",
        "details": "范围1–200；与全局条数、保留天数共同限制，不跨群私合并正文。",
        "example": "200表示每个范围最多保留最近200条素材。",
        "parent": "livingmemory_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "window_global",
        "label": "全部素材上限",
        "section": "memory",
        "value": 10000,
        "type": "integer",
        "advanced": true,
        "help": "全部会话素材的总条数上限。",
        "details": "范围1–10000；到达上限时按清理规则裁剪，不代表无限保存平台消息。",
        "example": "10000表示全插件最多保留一万条正文素材。",
        "parent": "livingmemory_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "body_max_chars",
        "label": "单条素材字数上限",
        "section": "memory",
        "value": 8000,
        "type": "integer",
        "advanced": true,
        "help": "单条聊天正文的最大字符数。",
        "details": "范围1–8000；接收素材时截断超长正文，模型输入Token限制另行生效。",
        "example": "8000避免单条超长消息占满素材窗口。",
        "parent": "livingmemory_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "event_days",
        "label": "事件保留时间",
        "section": "memory",
        "value": 30,
        "type": "integer",
        "advanced": true,
        "help": "不含正文的事件记录保留天数。",
        "details": "正整数天；事件记录与正文素材、日记梦境各有保留规则。",
        "example": "30表示事件记录按约一个月清理。",
        "parent": "livingmemory_enabled",
        "level": 1,
        "step": 1,
        "unit": "天"
      },
      {
        "key": "persona_shared_state",
        "label": "同一人格共享状态",
        "section": "persona",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "同一人格共享情绪与精力数值。",
        "details": "共享只合并同一实例、同一人格的数值状态；聊天正文和关系来源仍按真实会话隔离。",
        "example": "希望私聊和群聊看到同一份精力：开启；希望分开作息：关闭。",
        "parent": "persona_mode",
        "level": 1
      },
      {
        "key": "allow_sleep",
        "label": "允许TA睡眠",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "允许睡眠状态影响聊天可用性。",
        "details": "关闭后继续记录精力，但不因睡眠阻断聊天；开启时还需自动作息和相应规则生效。",
        "example": "希望夜里仍随时回复：关闭；希望有真实作息：开启。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "nap_enabled",
        "label": "启用午休",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "启用午休时间段。",
        "details": "与午休开始和结束配合；允许睡眠关闭时仍不阻断聊天。",
        "example": "开启并设置13:00至14:30。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "nap_start",
        "label": "午休开始",
        "section": "night",
        "value": "13:00",
        "type": "string",
        "advanced": false,
        "help": "午休的开始时间。",
        "details": "本地24小时HH:MM；必须与午休结束不同，支持跨午夜但一般使用白天。",
        "example": "13:00表示下午一点开始午休。",
        "parent": "nap_enabled",
        "level": 2
      },
      {
        "key": "nap_end",
        "label": "午休结束",
        "section": "night",
        "value": "14:30",
        "type": "string",
        "advanced": false,
        "help": "午休的结束时间。",
        "details": "与午休开始配对，实际可用性还受精力和其他作息状态影响。",
        "example": "14:30表示下午两点半结束午休。",
        "parent": "nap_enabled",
        "level": 2
      },
      {
        "key": "fatigue_start",
        "label": "夜间疲劳开始",
        "section": "night",
        "value": "23:30",
        "type": "string",
        "advanced": false,
        "help": "夜间疲劳与睡眠周期的起点。",
        "details": "从此时开始夜间阶段；恍惚转困时间取起点与沉睡时间之间的中点。",
        "example": "23:30起点、02:30沉睡，则次日01:00转困。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "fatigue_end",
        "label": "夜间疲劳结束",
        "section": "night",
        "value": "07:00",
        "type": "string",
        "advanced": false,
        "help": "夜间疲劳消耗的结束时间。",
        "details": "停止这一段疲劳消耗，不代表可以退出沉睡；基础起床加本周期赖床值决定实际起床。",
        "example": "07:00停止疲劳消耗，但08:00起床配置仍有效。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "deep_sleep_at",
        "label": "沉睡时间",
        "section": "night",
        "value": "02:30",
        "type": "string",
        "advanced": false,
        "help": "进入沉睡的时间。",
        "details": "须位于夜间起点与基础起床之间，支持跨午夜；本地HH:MM，宿主校验时间顺序。",
        "example": "23:30→02:30→08:00合法；沉睡09:00会被拒绝。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "lie_in_min_minutes",
        "label": "最少赖床时间",
        "section": "night",
        "value": 0,
        "type": "integer",
        "advanced": false,
        "help": "本周期赖床的最少分钟数。",
        "details": "可设0；最少不得大于最多，实际抽取结果在本周期内固定。",
        "example": "0至30，允许准时起床或赖床最多半小时。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "step": 1,
        "unit": "分钟"
      },
      {
        "key": "lie_in_max_minutes",
        "label": "最多赖床时间",
        "section": "night",
        "value": 90,
        "type": "integer",
        "advanced": false,
        "help": "本周期赖床的最多分钟数。",
        "details": "范围0–1440分钟；与最少值组成随机区间，不是每次刷新重抽。",
        "example": "最少15、最多45，基础08:00则08:15至08:45起床。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "step": 1,
        "unit": "分钟"
      },
      {
        "key": "wake_mode",
        "label": "聊天唤醒方式",
        "section": "night",
        "value": "chat",
        "type": "enum",
        "advanced": false,
        "help": "谁可以通过聊天叫醒 TA。",
        "details": "仅私聊、不允许唤醒、私聊或群聊原生@Bot；普通文本里的@名字不等于原生提及。",
        "example": "不想群聊打断睡眠：选“仅私聊”。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "options": [
          {
            "value": "chat",
            "label": "仅私聊"
          },
          {
            "value": "never",
            "label": "不允许聊天唤醒"
          },
          {
            "value": "both",
            "label": "私聊或群原生@Bot"
          }
        ]
      },
      {
        "key": "wake_reply_limit",
        "label": "唤醒回复轮数",
        "section": "night",
        "value": 3,
        "type": "integer",
        "advanced": false,
        "help": "一次聊天唤醒可用的回复尝试数。",
        "details": "范围1–100；生成失败也计入，窗口时间到达同样停止。",
        "example": "3轮、10分钟，最多尝试3次并且不超过窗口。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "wake_window_minutes",
        "label": "唤醒窗口",
        "section": "night",
        "value": 10,
        "type": "integer",
        "advanced": false,
        "help": "一次聊天唤醒的最长窗口。",
        "details": "范围1–1440分钟，从第一次宿主提交开始固定计算，后续消息不无限延长。",
        "example": "10表示叫醒后最多维持10分钟的回复窗口。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "step": 1,
        "unit": "分钟"
      },
      {
        "key": "energy_reply_cost",
        "label": "每次回复精力消耗",
        "section": "night",
        "value": 4.0,
        "type": "float",
        "advanced": false,
        "help": "每次可见回复消耗的精力点数。",
        "details": "总精力固定100；数值0–100，步进0.1，每次可见回复只记一次。",
        "example": "4.0表示一条实际回复消耗4点。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "step": 0.1,
        "unit": "点/次"
      },
      {
        "key": "energy_fatigue_per_minute",
        "label": "疲劳精力消耗速率",
        "section": "night",
        "value": 0.8,
        "type": "float",
        "advanced": false,
        "help": "清醒疲劳阶段每分钟消耗精力。",
        "details": "数值0–100，步进0.1；只在适用疲劳状态消耗，不将子项相加冒充总变化。",
        "example": "0.8表示适用状态持续10分钟约消耗8点。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "step": 0.1,
        "unit": "点/分钟"
      },
      {
        "key": "energy_recovery_per_minute",
        "label": "精力恢复速率",
        "section": "night",
        "value": 1.5,
        "type": "float",
        "advanced": false,
        "help": "睡眠或非疲劳阶段每分钟恢复精力。",
        "details": "数值0–100，步进0.1；实际恢复受阶段和总上限100限制。",
        "example": "1.5表示适用状态10分钟约恢复15点，上限100。",
        "parent": "night_schedule_enabled",
        "level": 1,
        "step": 0.1,
        "unit": "点/分钟"
      },
      {
        "key": "catchup_enabled",
        "label": "醒后阅读未读",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "醒来后阅读已保存的未读消息。",
        "details": "从本插件有真实来源的未读归档读取；不等于访问平台全部历史，补答开关独立。",
        "example": "只希望醒后了解聊天：开启阅读、关闭历史补答。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "catchup_reply_enabled",
        "label": "醒后历史补答",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "阅读未读后允许有限历史补答。",
        "details": "需要醒后阅读、可用模型和预算；生成与发送仍受身份及可用性检查。",
        "example": "阅读与补答同时开启，醒后可对仍有意义的未读内容补充回复。",
        "parent": "catchup_enabled",
        "level": 2
      },
      {
        "key": "closing_enabled",
        "label": "睡前晚安",
        "section": "night",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "允许睡前在近期参与的会话道晚安。",
        "details": "只考虑真实且近期参与过的会话；不是向所有好友群发，发送仍需守卫允许。",
        "example": "夜间23:30开始、提前5分钟，可在23:25附近评估晚安。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "closing_random",
        "label": "道别语随机生成",
        "section": "night",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "使用模型生成睡前道别。",
        "details": "关闭时使用本地模板；开启时一次生成占用模型预算，不保证每次发送。",
        "example": "想减少模型调用：关闭；希望道别更有变化：开启。",
        "parent": "closing_enabled",
        "level": 2
      },
      {
        "key": "closing_lead_minutes",
        "label": "晚安提前量",
        "section": "night",
        "value": 5,
        "type": "integer",
        "advanced": false,
        "help": "夜间起点前多久评估晚安。",
        "details": "范围0–60分钟，以疲劳开始时间为基准；调度间隔影响实际评估时刻。",
        "example": "起点23:30、提前5分钟，计划在23:25附近评估。",
        "parent": "closing_enabled",
        "level": 2,
        "step": 1,
        "unit": "分钟"
      },
      {
        "key": "diary_provider_id",
        "label": "日记模型",
        "section": "experience",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "日记生成专用模型。",
        "details": "留空沿用默认模型；与梦境模型可分别配置。",
        "example": "日记用常用模型，梦境用更有创作风格的模型。",
        "parent": "diary_enabled",
        "level": 1,
        "provider_kind": "chat",
        "options": [
          {
            "value": "",
            "label": "跟随当前聊天模型"
          },
          {
            "value": "fixture-chat",
            "label": "合成聊天模型"
          }
        ]
      },
      {
        "key": "dream_provider_id",
        "label": "梦境模型",
        "section": "experience",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "梦境生成专用模型。",
        "details": "留空沿用默认模型；梦境必须保留想象属性，不能把虚构写成真实经历。",
        "example": "选择擅长简短叙事的已配置模型。",
        "parent": "dream_enabled",
        "level": 1,
        "provider_kind": "chat",
        "options": [
          {
            "value": "",
            "label": "跟随当前聊天模型"
          },
          {
            "value": "fixture-chat",
            "label": "合成聊天模型"
          }
        ]
      },
      {
        "key": "catchup_provider_id",
        "label": "补课模型",
        "section": "night",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "醒后补课与补答使用的模型。",
        "details": "留空跟随默认或会话模型，不会修改正常聊天所用模型。",
        "example": "未读较多时选支持较长上下文的已配置模型。",
        "parent": "catchup_enabled",
        "level": 2,
        "provider_kind": "chat",
        "options": [
          {
            "value": "",
            "label": "跟随当前聊天模型"
          },
          {
            "value": "fixture-chat",
            "label": "合成聊天模型"
          }
        ]
      },
      {
        "key": "closing_provider_id",
        "label": "收尾模型",
        "section": "night",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "睡前道别专用模型。",
        "details": "只在随机生成道别启用且有预算时使用；留空沿用默认模型。",
        "example": "选择轻量模型生成一句简短晚安。",
        "parent": "closing_enabled",
        "level": 2,
        "provider_kind": "chat",
        "options": [
          {
            "value": "",
            "label": "跟随当前聊天模型"
          },
          {
            "value": "fixture-chat",
            "label": "合成聊天模型"
          }
        ]
      },
      {
        "key": "home_city",
        "label": "Bot住所城市",
        "section": "experience",
        "value": "",
        "type": "string",
        "advanced": false,
        "help": "TA 的住所城市，用于天气背景。",
        "details": "填写可识别的公开城市名称，不填私人详细地址；城市信息不自动决定时区。",
        "example": "填“上海”，同时将时区设为Asia/Shanghai。",
        "parent": "",
        "level": 0
      },
      {
        "key": "embedding_provider_id",
        "label": "向量模型",
        "section": "memory",
        "value": "",
        "type": "enum",
        "advanced": false,
        "help": "本地向量记忆使用的原生向量模型。",
        "details": "仅本地向量记忆需要此项；启用 LivingMemory 时不需要配置本地 embedding（WebUI 中该项置灰）。它与后台聊天模型分开。",
        "example": "使用本地向量记忆时选择已配置的 AstrBot 向量提供商。",
        "parent": "livingmemory_enabled",
        "level": 1,
        "provider_kind": "embedding",
        "options": [
          {
            "value": "",
            "label": "未配置"
          },
          {
            "value": "fixture-embedding",
            "label": "合成向量模型"
          }
        ]
      },
      {
        "key": "livingmemory_enabled",
        "label": "使用LivingMemory",
        "section": "memory",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "使用已安装的 LivingMemory 记忆接口。",
        "details": "关闭时使用本地向量路径；开启仍需外部插件可用与权限通过，不会将固定资料替代动态记忆。",
        "example": "已安装LivingMemory并完成配置后开启；否则配置本地向量模型。",
        "parent": "",
        "level": 0
      },
      {
        "key": "memory_write",
        "label": "允许写入记忆",
        "section": "memory",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "允许写入聊天回复体验。",
        "details": "不按语义价值筛掉聊天回复；仍按真实来源隔离并遵守素材保留期。",
        "example": "需要记录聊天回复体验：开启；停止新增记录：关闭。",
        "parent": "livingmemory_enabled",
        "level": 1
      },
      {
        "key": "relationship_stage_names",
        "label": "关系阶段自定义名称",
        "section": "relationship",
        "value": "[\"反感\",\"陌生\",\"友好\",\"亲近\",\"独特\"]",
        "type": "string",
        "advanced": false,
        "help": "五档关系的自定义名称，留空使用默认名称。",
        "details": "0–10反感、11–24陌生、25–44友好、45–99亲近、100独特。普通互动最高99；旧11档配置自动兼容。",
        "example": "[\"反感\",\"陌生\",\"友好\",\"亲近\",\"主人\"]",
        "parent": "",
        "level": 0
      },
      {
        "key": "relationship_stage_descriptions",
        "label": "关系阶段描述",
        "section": "relationship",
        "value": "[\"\",\"\",\"\",\"\"]",
        "type": "string",
        "advanced": false,
        "help": "前四档关系的相处描述，留空沿用默认描述。",
        "details": "依次对应反感、陌生、友好、亲近；每项最多1000字。描述用于关系表达，不改变分数规则。独特档在同一行单独设置。",
        "example": "[\"保持距离，任务可靠\",\"礼貌谨慎，慢慢了解\",\"自然友善，肯定善意\",\"主动关心，尊重边界\"]",
        "parent": "emotion_model_enabled",
        "level": 1
      },
      {
        "key": "relationship_special_description",
        "label": "独特关系说明",
        "section": "relationship",
        "value": "",
        "type": "string",
        "advanced": false,
        "help": "100分独特关系的自定义说明。",
        "details": "管理员设置100分时使用，可填写相处方式；单个对象的关系备注优先。最多1000字。",
        "example": "例如：主人，温柔陪伴、主动关心，保留傲娇表达。",
        "parent": "emotion_model_enabled",
        "level": 1
      },
      {
        "key": "wake_autocatchup_enabled",
        "label": "自然醒后主动补答",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "自然醒后是否主动爬楼补答。",
        "details": "只对这一段睡眠期确有未读的会话生效；没有未读就不读不发，也不会重复补答。",
        "example": "希望它醒来自己看看群里的消息：开启；只想被动等消息：关闭。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "wake_greeting_enabled",
        "label": "先发一句刚醒的招呼",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false,
        "help": "爬楼前是否先发一句刚醒的招呼。",
        "details": "招呼只是一句话，用来交代「刚醒」；关闭后直接进入补答或继续安静。",
        "example": "不想它冒头时关闭。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "wake_greeting_texts",
        "label": "刚醒招呼候选句子",
        "section": "night",
        "value": "刚醒，我看看之前你们说了什么。|我醒了，先把这几小时翻一翻。|醒了…看看都说了什么。",
        "type": "string",
        "advanced": false,
        "help": "刚醒招呼的候选句子。",
        "details": "用竖线 | 分隔，每次随机取一条；留空则使用默认一句。",
        "example": "刚醒，我看看之前你们说了什么。|我醒了，先把这几小时翻一翻。",
        "parent": "night_schedule_enabled",
        "level": 1
      },
      {
        "key": "relationship_edit_enabled",
        "label": "允许在关系页修改好感",
        "section": "relationship",
        "value": false,
        "type": "boolean",
        "advanced": false,
        "help": "是否在关系页显示好感编辑。",
        "details": "默认关闭，关系页只读；打开后才会出现好感分数与冻结开关的编辑表单，保存写入真实关系记录并留审计。",
        "example": "日常只观察关系变化：保持关闭；需要人工校正某个账号的好感时才打开。",
        "parent": "emotion_model_enabled",
        "level": 1
      }
    ],
    "groups": [
      {
        "id": "quick_start",
        "label": "快速开始",
        "field_keys": [
          "enabled",
          "mode",
          "timezone",
          "provider_id",
          "fallback_provider_id",
          "home_city"
        ]
      },
      {
        "id": "persona",
        "label": "人格与状态模式",
        "field_keys": [
          "persona_mode",
          "persona_id",
          "persona_shared_state"
        ]
      },
      {
        "id": "emotion",
        "label": "情绪",
        "field_keys": [
          "emotion_model_enabled",
          "scheduler_seconds",
          "model_concurrency",
          "queue_size",
          "model_daily_limit",
          "emotion_interval_seconds",
          "emotion_quiet_start_hour",
          "emotion_quiet_end_hour",
          "emotion_intensity",
          "model_input_tokens",
          "model_output_tokens",
          "model_timeout_seconds"
        ]
      },
      {
        "id": "relationship",
        "label": "关系",
        "field_keys": [
          "relationship_stage_names",
          "relationship_stage_descriptions",
          "relationship_special_description",
          "relationship_edit_enabled"
        ]
      },
      {
        "id": "behavior",
        "label": "主动行为",
        "field_keys": [
          "autonomy_enabled",
          "group_autonomy_enabled",
          "autonomy_qq_ids",
          "autonomy_qq_group_ids",
          "muted_scopes",
          "dnd_start",
          "dnd_end",
          "active_start",
          "active_end",
          "behavior_daily_limit",
          "behavior_scope_daily_limit",
          "behavior_cooldown_seconds",
          "behavior_unanswered_limit",
          "behavior_random_min_minutes",
          "behavior_random_max_minutes",
          "behavior_idle_minutes",
          "behavior_style",
          "behavior_emotional_share",
          "behavior_provider_id"
        ]
      },
      {
        "id": "night",
        "label": "长夜",
        "field_keys": [
          "night_schedule_enabled",
          "wake_at",
          "allow_sleep",
          "nap_enabled",
          "nap_start",
          "nap_end",
          "fatigue_start",
          "fatigue_end",
          "deep_sleep_at",
          "lie_in_min_minutes",
          "lie_in_max_minutes",
          "wake_mode",
          "wake_reply_limit",
          "wake_window_minutes",
          "energy_reply_cost",
          "energy_fatigue_per_minute",
          "energy_recovery_per_minute",
          "catchup_enabled",
          "catchup_reply_enabled",
          "closing_enabled",
          "closing_random",
          "closing_lead_minutes",
          "catchup_provider_id",
          "closing_provider_id",
          "wake_autocatchup_enabled",
          "wake_greeting_enabled",
          "wake_greeting_texts"
        ]
      },
      {
        "id": "experience",
        "label": "日记与梦境",
        "field_keys": [
          "dream_enabled",
          "dream_theme_pool",
          "dream_owner_notify",
          "dream_owner_qq",
          "diary_enabled",
          "diary_at",
          "diary_backfill_yesterday",
          "diary_retries",
          "dream_per_night",
          "diary_retention_days",
          "dream_retention_days",
          "dream_half_life_seconds",
          "experience_body_chars",
          "diary_provider_id",
          "dream_provider_id",
          "home_city"
        ]
      },
      {
        "id": "memory",
        "label": "记忆",
        "field_keys": [
          "memory_read",
          "window_days",
          "window_per_scope",
          "window_global",
          "body_max_chars",
          "event_days",
          "embedding_provider_id",
          "livingmemory_enabled",
          "memory_write"
        ]
      }
    ],
    "readonly": [
      {
        "key": "energy_max",
        "label": "总精力",
        "type": "float",
        "value": 100.0,
        "step": 0.1,
        "unit": "点",
        "readonly": true,
        "section": "night",
        "parent": "night_schedule_enabled",
        "level": 1,
        "help": "总精力固定为100点。",
        "details": "只读上限，用于统一精力曲线和展示，不能通过配置修改。",
        "example": "当前74点表示上限100中的74点。"
      }
    ]
  },
  "state": {
    "environment": {
      "enabled": false
    },
    "feeling": {
      "text": "",
      "status": "unavailable"
    },
    "api_version": 1,
    "context_id": "",
    "action_target": {
      "context_id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
      "view_scope": "private",
      "platform": "qq",
      "label": "qq / private / synthetic-chat / 10022"
    },
    "contexts": [
      {
        "id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10022",
        "label": "qq / synthetic-chat / 10022"
      },
      {
        "id": "fa26f35ec2546c181ee72799f01b5aae504e5c4033b7b202d9abecf62d5f11ab",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10008",
        "label": "qq / synthetic-chat / 10008"
      },
      {
        "id": "dfb32f3bfc4be410769366615ff06d2c19e98932e1931081a830bb8ab15e1e79",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10003",
        "label": "qq / synthetic-chat / 10003"
      },
      {
        "id": "de24a467cea45b055f7f8def9fc56b4070e20ef6e76c9e97078bb1c6293ce863",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10005",
        "label": "qq / synthetic-chat / 10005"
      },
      {
        "id": "c639f0787f3e721670ce91c66ea83ae1f3643d241cf98a647895d77ed430d573",
        "scope_key": "fe330394d0b89a8abe88cfff5e0fc6a1154a3d274cb4efde352a7b88afb1b4ae",
        "persona_id": "fixture-persona",
        "platform": "bilibili",
        "view_scope": "group",
        "scene_id": "synthetic-group",
        "account_id": "10001",
        "label": "bilibili / synthetic-group / 10001"
      },
      {
        "id": "b6523e02ceff69b99ebe35a09d40dfcf4c6eaf0456ff317bfdffa7c4250efbd0",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10004",
        "label": "qq / synthetic-chat / 10004"
      },
      {
        "id": "b2843aaa258a1b53a0f8db7536d25dfa3b1e750fcc890b11c5c655c446a38226",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10010",
        "label": "qq / synthetic-chat / 10010"
      },
      {
        "id": "af4c64efe2bd84af88a5b125e64520e83d16c8bb664e2c9544f66edd5c0eca8c",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10001",
        "label": "qq / synthetic-chat / 10001"
      },
      {
        "id": "ac17a10a834bbd6546d9df4799a3fbf4180e0f0eb2330a229a24c5d17b6f87cd",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10012",
        "label": "qq / synthetic-chat / 10012"
      },
      {
        "id": "aa3c7b08efef0610f928e202a72bc946347131b4dd10858badb9498c48f82f74",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10016",
        "label": "qq / synthetic-chat / 10016"
      },
      {
        "id": "99e913771ab562575d758281889a84d5a651e9ed85199a933b1d36905ba60a43",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10015",
        "label": "qq / synthetic-chat / 10015"
      },
      {
        "id": "8bea336f974443c4c11057900f7ed8652adc31754428a84ee4b83b85b2fe44e1",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10011",
        "label": "qq / synthetic-chat / 10011"
      },
      {
        "id": "83f40e4790ac1906f7588f8b52e5b9e5c0db9368fc7d3b32aa2d9b392edd00ab",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10007",
        "label": "qq / synthetic-chat / 10007"
      },
      {
        "id": "6ed68c6b686c9951261dc5de9738b25019ab809bc0e703c1c626a17f14c6ad81",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10018",
        "label": "qq / synthetic-chat / 10018"
      },
      {
        "id": "6ec240f3ccf36a9e65f0f924da49e2b7f133782a030fc05cee5fd45c70f557d2",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10009",
        "label": "qq / synthetic-chat / 10009"
      },
      {
        "id": "6a31c17069f1faa088d70f67b863369c79c828ac93d8dc45f53e943b0d1faa20",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10019",
        "label": "qq / synthetic-chat / 10019"
      },
      {
        "id": "5887c46fe09940abadf7caa6cf01d5725f4de752431821268b675be39984d3c5",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10013",
        "label": "qq / synthetic-chat / 10013"
      },
      {
        "id": "54c518ff3fbeb5e9479c2941bd9b2f274fc8495e7acd1c60253fb9f315bdac71",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10002",
        "label": "qq / synthetic-chat / 10002"
      },
      {
        "id": "52e7028ab96e6d15771e356ec0cc141e9924f6d9c807f92056fabd22000acc42",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10006",
        "label": "qq / synthetic-chat / 10006"
      },
      {
        "id": "51511c831a5c7e9483c8524dd0d21c9cd5704388bbde5977b68c0b84b2c6e7d6",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10014",
        "label": "qq / synthetic-chat / 10014"
      },
      {
        "id": "3541c3e1eb5a73c2e9c3cff4062576aa8741454589a14ccac2b743235a818bed",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10017",
        "label": "qq / synthetic-chat / 10017"
      },
      {
        "id": "20e34e626946676301e279dd297c66c688b26bf3862adb3ff1457474292c8be5",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10021",
        "label": "qq / synthetic-chat / 10021"
      },
      {
        "id": "1ef1a91376e7269b4f41b29e3d2b8a50f54ce42f81bc7343bb04b473e71a4baf",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10023",
        "label": "qq / synthetic-chat / 10023"
      },
      {
        "id": "1ccd90c62355721865cacd5c9ecdb7d9c6e45962cde9fa9b49c085cdbbec2515",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10020",
        "label": "qq / synthetic-chat / 10020"
      }
    ],
    "updated_at": 1800000001.0,
    "mode": "observe_only",
    "mode_detail": {
      "effective": "observe_only",
      "configured": "observe_only",
      "reason": "observe_only",
      "reason_text": "仅观察：只记录状态，不主动发送。"
    },
    "revision": "config-1",
    "config": {
      "revision": "3a97bdc532db1eece287d8deed200726050525200876702c9afa31a42aec412e",
      "source": "AstrBot native plugin configuration",
      "values": {
        "enabled": true,
        "mode": "observe_only",
        "memory_read": false,
        "autonomy_enabled": false,
        "group_autonomy_enabled": false,
        "emotion_model_enabled": false,
        "dream_enabled": false,
        "dream_theme_pool": "[\"赛博朋克\", \"绿野仙踪\", \"生活日常\", \"星际漫游\", \"海底王国\", \"古堡奇遇\", \"森林童话\", \"校园时光\", \"蒸汽幻想\", \"云端旅行\", \"四季庭院\", \"时光回廊\"]",
        "dream_owner_notify": false,
        "dream_owner_qq": "",
        "diary_enabled": false,
        "persona_mode": "follow",
        "persona_id": "",
        "timezone": "Asia/Shanghai",
        "provider_id": "",
        "fallback_provider_id": "",
        "autonomy_qq_ids": "",
        "autonomy_qq_group_ids": "",
        "muted_scopes": "",
        "night_schedule_enabled": false,
        "wake_at": "08:00",
        "diary_at": "23:00",
        "diary_backfill_yesterday": false,
        "scheduler_seconds": 60,
        "dnd_start": "01:00",
        "dnd_end": "08:00",
        "active_start": "00:00",
        "active_end": "23:59",
        "behavior_daily_limit": 6,
        "behavior_scope_daily_limit": 2,
        "behavior_cooldown_seconds": 7200,
        "behavior_unanswered_limit": 2,
        "behavior_random_min_minutes": 90,
        "behavior_random_max_minutes": 240,
        "behavior_idle_minutes": 20,
        "behavior_style": "balanced",
        "behavior_emotional_share": true,
        "behavior_provider_id": "",
        "diary_retries": 2,
        "dream_per_night": 2,
        "diary_retention_days": 30,
        "dream_retention_days": 7,
        "dream_half_life_seconds": 86400,
        "experience_body_chars": 2000,
        "model_concurrency": 1,
        "queue_size": 100,
        "model_daily_limit": 48,
        "emotion_interval_seconds": 600,
        "emotion_quiet_start_hour": 3,
        "emotion_quiet_end_hour": 8,
        "emotion_intensity": "normal",
        "model_input_tokens": 32768,
        "model_output_tokens": 1024,
        "model_timeout_seconds": 30,
        "window_days": 7,
        "window_per_scope": 200,
        "window_global": 10000,
        "body_max_chars": 8000,
        "event_days": 30,
        "persona_shared_state": true,
        "allow_sleep": true,
        "nap_enabled": true,
        "nap_start": "13:00",
        "nap_end": "14:30",
        "fatigue_start": "23:30",
        "fatigue_end": "07:00",
        "deep_sleep_at": "02:30",
        "lie_in_min_minutes": 0,
        "lie_in_max_minutes": 90,
        "wake_mode": "chat",
        "wake_reply_limit": 3,
        "wake_window_minutes": 10,
        "energy_reply_cost": 4.0,
        "energy_fatigue_per_minute": 0.8,
        "energy_recovery_per_minute": 1.5,
        "catchup_enabled": true,
        "catchup_reply_enabled": true,
        "closing_enabled": false,
        "closing_random": false,
        "closing_lead_minutes": 5,
        "diary_provider_id": "",
        "dream_provider_id": "",
        "catchup_provider_id": "",
        "closing_provider_id": "",
        "home_city": "",
        "embedding_provider_id": "",
        "livingmemory_enabled": false,
        "memory_write": false,
        "relationship_stage_names": "[\"反感\",\"陌生\",\"友好\",\"亲近\",\"独特\"]",
        "relationship_stage_descriptions": "[\"\",\"\",\"\",\"\"]",
        "relationship_special_description": "",
        "wake_autocatchup_enabled": true,
        "wake_greeting_enabled": true,
        "wake_greeting_texts": "刚醒，我看看之前你们说了什么。|我醒了，先把这几小时翻一翻。|醒了…看看都说了什么。",
        "relationship_edit_enabled": false
      },
      "fields": [
        {
          "key": "enabled",
          "label": "启用插件",
          "section": "quick_start",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "启用生活状态与配置功能。",
          "details": "关闭后停止接收新生活事件；开启后仍遵守运行模式和各模块开关。",
          "example": "想先观察状态：开启插件，运行模式选“仅观察”。",
          "parent": "",
          "level": 0
        },
        {
          "key": "mode",
          "label": "运行模式",
          "section": "quick_start",
          "value": "observe_only",
          "type": "enum",
          "advanced": false,
          "help": "选择正常运行或仅观察。",
          "details": "仅观察可记录状态，但不注入情绪表达或自主发送；正常运行也需要各行为开关和授权范围。",
          "example": "调试配置用“仅观察”；确认后再选“正常运行”。",
          "parent": "",
          "level": 0,
          "options": [
            {
              "value": "active",
              "label": "正常运行"
            },
            {
              "value": "observe_only",
              "label": "仅观察"
            }
          ]
        },
        {
          "key": "memory_read",
          "label": "允许读取记忆",
          "section": "memory",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "允许从所选记忆后端检索。",
          "details": "读取仍按会话来源、用途和身份权限过滤；不可用时不会回退读取私有记忆。",
          "example": "需要根据聊天经历找话题：开启读取；仅记录不检索：关闭。",
          "parent": "livingmemory_enabled",
          "level": 1
        },
        {
          "key": "autonomy_enabled",
          "label": "允许主动找人",
          "section": "behavior",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "允许 TA 等待合适时机主动开口。",
          "details": "需要正常运行、有效时区和号码范围；结合记忆、关系与情绪选话题，先检查作息、安静时间和额度。",
          "example": "填私聊QQ号码，设置随机90–240分钟，开启后保存；到点仍可能因不适合开口而等待。",
          "parent": "",
          "level": 0
        },
        {
          "key": "group_autonomy_enabled",
          "label": "允许群聊主动行为",
          "section": "behavior",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "允许在已授权的群聊主动发言。",
          "details": "群聊总开关独立于私聊；关闭时即使填了群号也不主动发送，不向群聊分享私聊情绪或私有记忆。",
          "example": "只希望主动私聊：保持关闭，群号可留空。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "emotion_model_enabled",
          "label": "模型辅助情绪分析",
          "section": "emotion",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "允许模型辅助细化情绪。",
          "details": "关闭时保留本地情绪规则；开启后按间隔和全局模型预算调用，情绪是主观状态而非事实。",
          "example": "只想低成本体验：关闭；需要细化语气：开启并设间隔300秒。",
          "parent": "",
          "level": 0
        },
        {
          "key": "dream_enabled",
          "label": "生成梦境",
          "section": "experience",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "睡眠期间允许生成梦境。",
          "details": "需要睡眠周期、素材、模型和预算；梦境是想象内容，不当作真实事实或人际证据。",
          "example": "想体验生活感：开启；只要实用记录：关闭。",
          "parent": "",
          "level": 0
        },
        {
          "key": "dream_theme_pool",
          "label": "梦境主题池",
          "section": "experience",
          "value": "[\"赛博朋克\", \"绿野仙踪\", \"生活日常\", \"星际漫游\", \"海底王国\", \"古堡奇遇\", \"森林童话\", \"校园时光\", \"蒸汽幻想\", \"云端旅行\", \"四季庭院\", \"时光回廊\"]",
          "type": "string",
          "advanced": false,
          "help": "每次随机抽取两个不同主题。",
          "details": "接受JSON列表或逗号、换行分隔的2–32个主题，每项最多40字；结合TA当日六维情绪决定梦的基调。",
          "example": "赛博朋克，绿野仙踪，生活日常，星际漫游，海底王国，古堡奇遇，森林童话，校园时光，蒸汽幻想，云端旅行，四季庭院，时光回廊",
          "parent": "dream_enabled",
          "level": 1
        },
        {
          "key": "dream_owner_notify",
          "label": "梦中惊醒给主人发消息",
          "section": "experience",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "夜间被愤怒或恐惧的梦惊醒时联系主人。",
          "details": "默认关闭。开启后只在自动梦境保存成功且仍处同一夜晚时，向已核验的主人私聊发一次消息；手动生成不会发送。此专用开关允许夜间联系，仍遵守静默、模式、身份和每日额度。",
          "example": "先填写主人QQ，确认存在真实私聊来源，再开启。",
          "parent": "dream_enabled",
          "level": 1
        },
        {
          "key": "dream_owner_qq",
          "label": "主人QQ",
          "section": "experience",
          "value": "",
          "type": "string",
          "advanced": false,
          "help": "接收梦中惊醒消息的主人QQ。",
          "details": "仅允许一个合法号码；不能凭手填号码创建发送路由，必须已经在宿主中建立此人格的真实QQ私聊。",
          "example": "填写主人的QQ号码。",
          "parent": "dream_enabled",
          "level": 1
        },
        {
          "key": "diary_enabled",
          "label": "生成日记",
          "section": "experience",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "自动生成私人日记。",
          "details": "只使用可用且符合来源权限的素材，生成消耗模型预算；日记属于主观经历。",
          "example": "开启后在本地23:00计划生成当天日记。",
          "parent": "",
          "level": 0
        },
        {
          "key": "persona_mode",
          "label": "人格选择方式",
          "section": "persona",
          "value": "follow",
          "type": "enum",
          "advanced": false,
          "help": "跟随聊天人格，或固定一个原生人格。",
          "details": "跟随模式使用当前会话人格；指定模式必须选择有效人格；不使用时不借用其他人格。",
          "example": "多个聊天各有角色：选“跟随会话人格”；固定角色：选“指定人格”并选择下方人格。",
          "parent": "",
          "level": 0,
          "options": [
            {
              "value": "follow",
              "label": "跟随会话人格"
            },
            {
              "value": "explicit",
              "label": "指定人格"
            },
            {
              "value": "none",
              "label": "不使用"
            }
          ]
        },
        {
          "key": "persona_id",
          "label": "原生人格",
          "section": "persona",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "指定模式使用的 AstrBot 人格。",
          "details": "从原生人格下拉选择；跟随模式下由会话决定，单独选此项不会切换选择方式。",
          "example": "先把人格选择方式改为“指定人格”，再选择“大姐姐”。",
          "parent": "persona_mode",
          "level": 1,
          "options": [
            {
              "value": "fixture-persona",
              "label": "真实 DTO · 合成人格"
            }
          ]
        },
        {
          "key": "timezone",
          "label": "本地时区",
          "section": "quick_start",
          "value": "Asia/Shanghai",
          "type": "string",
          "advanced": false,
          "help": "作息和每日额度使用的本地时区。",
          "details": "填写 IANA 时区；自动作息和主动调度需要有效时区。不是城市名或 UTC 偏移量。",
          "example": "中国大陆填 Asia/Shanghai，日本填 Asia/Tokyo。",
          "parent": "",
          "level": 0
        },
        {
          "key": "provider_id",
          "label": "默认生成模型",
          "section": "quick_start",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "各后台生成任务默认使用的聊天模型。",
          "details": "从 AstrBot 已配置的模型中选择；留空跟随会话模型。情绪细化使用此默认模型；日记、梦境、主动聊天、醒后补答和晚安等任务可用各自专用模型覆盖此默认值。",
          "example": "设置通用后台模型，再按需为日记或梦境单独选模型。",
          "parent": "",
          "level": 0,
          "provider_kind": "chat",
          "options": [
            {
              "value": "",
              "label": "跟随当前聊天模型"
            },
            {
              "value": "fixture-chat",
              "label": "合成聊天模型"
            }
          ]
        },
        {
          "key": "fallback_provider_id",
          "label": "备用生成模型",
          "section": "quick_start",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "请求发出前可使用的备用模型。",
          "details": "只在尚未发出请求时回退；超时或结果未知的请求不会自动重发，避免重复费用和行为。",
          "example": "主模型暂不可用时，选择已配置的备用聊天模型。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "provider_kind": "chat",
          "options": [
            {
              "value": "",
              "label": "跟随当前聊天模型"
            },
            {
              "value": "fixture-chat",
              "label": "合成聊天模型"
            }
          ]
        },
        {
          "key": "autonomy_qq_ids",
          "label": "主动私聊 QQ 号码",
          "section": "behavior",
          "value": "",
          "type": "string",
          "advanced": false,
          "help": "允许主动私聊的 QQ 号码。",
          "details": "手写号码或在输入框中选择建议；逗号、空格或换行分隔。只匹配已有真实QQ私聊，不会凭号码创建会话。空白不授权新私聊。",
          "example": "填 12345678, 23456789，允许主动联系这两位；从下拉选择会追加到现有名单。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "autonomy_qq_group_ids",
          "label": "主动发言 QQ 群号",
          "section": "behavior",
          "value": "",
          "type": "string",
          "advanced": false,
          "help": "限定允许主动发言的 QQ 群号。",
          "details": "填写群号码而非成员QQ号；只匹配已知真实QQ群，并且必须同时开启群聊主动行为。留空表示所有已知真实QQ群；群总开关、静默、时段及预算仍然生效。群号与私聊QQ号分开判断，私聊名单留空仍不授权私聊。",
          "example": "留空并开启群聊总开关可作用于所有已知真实QQ群；填写 34567890, 45678901 则只作用于这些群。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "muted_scopes",
          "label": "静默范围",
          "section": "behavior",
          "value": "",
          "type": "string",
          "advanced": false,
          "help": "暂停指定真实会话的主动行为。",
          "details": "填写现有完整范围标识，多个用空格分隔；静默优先于允许名单。通常先从号码名单移除即可。",
          "example": "临时停用一个范围：复制该真实会话scope_key填入；清空后仍需满足号码授权。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "night_schedule_enabled",
          "label": "自动作息",
          "section": "night",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "自动按作息维护睡眠周期。",
          "details": "启用前填写时区；自动作息与允许睡眠分别控制时间记录和聊天阻断。旧配置保持原行为，直至完成新规则迁移。",
          "example": "时区Asia/Shanghai，夜间23:30、沉睡02:30、基础起床08:00。",
          "parent": "",
          "level": 0
        },
        {
          "key": "wake_at",
          "label": "基础起床时间",
          "section": "night",
          "value": "08:00",
          "type": "string",
          "advanced": false,
          "help": "未加赖床时间的基础起床时刻。",
          "details": "每个夜晚只抽取一次赖床值并保存；刷新页面不会重新抽取，实际起床可能更晚。",
          "example": "08:00、赖床0–90分钟，实际起床在08:00至09:30。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "diary_at",
          "label": "日记生成时间",
          "section": "experience",
          "value": "23:00",
          "type": "string",
          "advanced": false,
          "help": "每天计划生成日记的本地时间。",
          "details": "24小时HH:MM；调度是评估机会，并非准点保证，缺少素材或预算时可能跳过。",
          "example": "23:00适合在一天结束时回顾。",
          "parent": "diary_enabled",
          "level": 1
        },
        {
          "key": "diary_backfill_yesterday",
          "label": "补写昨天日记",
          "section": "experience",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "允许补写昨天缺失的日记。",
          "details": "只补昨天，不遍历久远历史；仍受素材有效期、重试上限和模型预算限制。",
          "example": "昨天服务暂停，可开启以尝试补写昨天。",
          "parent": "diary_enabled",
          "level": 1
        },
        {
          "key": "scheduler_seconds",
          "label": "调度间隔",
          "section": "emotion",
          "value": 60,
          "type": "integer",
          "advanced": true,
          "help": "后台评估任务的间隔秒数。",
          "details": "范围1–3600；唤醒调度检查，不代表每轮都会调用模型或发送消息。",
          "example": "60表示每分钟评估一次；无需为随机主动行为改成很小的值。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "秒"
        },
        {
          "key": "dnd_start",
          "label": "免打扰开始",
          "section": "behavior",
          "value": "01:00",
          "type": "string",
          "advanced": false,
          "help": "主动行为免打扰的开始时间。",
          "details": "只限制自主发言，不阻止正常接收消息；支持跨午夜，免打扰优先于主动时段。",
          "example": "01:00至08:00，凌晨不主动打扰。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "dnd_end",
          "label": "免打扰结束",
          "section": "behavior",
          "value": "08:00",
          "type": "string",
          "advanced": false,
          "help": "主动行为免打扰的结束时间。",
          "details": "本地HH:MM，与开始时间配对；相同时间会被拒绝，避免把空区间当全天。",
          "example": "开始23:00、结束08:00，次日8点结束免打扰。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "active_start",
          "label": "主动时段开始",
          "section": "behavior",
          "value": "00:00",
          "type": "string",
          "advanced": false,
          "help": "每天允许主动行为的开始时间。",
          "details": "使用本地24小时HH:MM，与结束时间组成主动窗口；免打扰与睡眠限制仍优先。",
          "example": "09:00至22:00，表示只在白天与晚间尝试。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "active_end",
          "label": "主动时段结束",
          "section": "behavior",
          "value": "23:59",
          "type": "string",
          "advanced": false,
          "help": "每天允许主动行为的结束时间。",
          "details": "结束边界不包含在主动窗口内；开始晚于结束表示跨午夜。两端不能相同。",
          "example": "开始20:00、结束00:30，表示可延续到次日零点半之前。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "behavior_daily_limit",
          "label": "每日主动行为总额度",
          "section": "behavior",
          "value": 6,
          "type": "integer",
          "advanced": false,
          "help": "所有会话每天的主动尝试总额度。",
          "details": "按本地日统计；失败或结果未知的尝试也占用额度，不靠重试恢复配额。",
          "example": "填6表示所有私聊和群聊合计最多6次尝试。",
          "parent": "autonomy_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "behavior_scope_daily_limit",
          "label": "每个会话每日主动额度",
          "section": "behavior",
          "value": 2,
          "type": "integer",
          "advanced": false,
          "help": "一个真实会话每天的主动尝试额度。",
          "details": "与总额度同时生效；到达任一上限就停止当日尝试。",
          "example": "总额度6、每个会话2，单个好友当天最多2次。",
          "parent": "autonomy_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "behavior_cooldown_seconds",
          "label": "主动行为冷却",
          "section": "behavior",
          "value": 7200,
          "type": "integer",
          "advanced": false,
          "help": "同一会话主动尝试后的冷却时间。",
          "details": "单位秒；和随机等待共同约束，不会因为新话题立即绕过冷却。",
          "example": "7200表示至少冷却2小时。",
          "parent": "autonomy_enabled",
          "level": 1,
          "step": 1,
          "unit": "秒"
        },
        {
          "key": "behavior_unanswered_limit",
          "label": "未回应次数上限",
          "section": "behavior",
          "value": 2,
          "type": "integer",
          "advanced": false,
          "help": "连续未获回应后停止主动的次数。",
          "details": "已确认或结果未知的发送都会保守计入；对方回复后才可能重新获得机会。",
          "example": "填2，连续两次没有回应就先停下来。",
          "parent": "autonomy_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "behavior_random_min_minutes",
          "label": "随机等待最短时间",
          "section": "behavior",
          "value": 90,
          "type": "integer",
          "advanced": false,
          "help": "随机等待的最短分钟数。",
          "details": "每次机会后重新安排等待，范围1–10080分钟，最短不能大于最长。等待结束不保证发送。",
          "example": "90至240，表示随机等待1.5至4小时后再评估。",
          "parent": "autonomy_enabled",
          "level": 1,
          "step": 1,
          "unit": "分钟",
          "min": 1,
          "max": 10080
        },
        {
          "key": "behavior_random_max_minutes",
          "label": "随机等待最长时间",
          "section": "behavior",
          "value": 240,
          "type": "integer",
          "advanced": false,
          "help": "随机等待的最长分钟数。",
          "details": "这是下次评估机会的上界；到点仍会检查睡眠、活跃聊天、关系、话题和预算。",
          "example": "和最短都填120，评估间隔固定为2小时。",
          "parent": "autonomy_enabled",
          "level": 1,
          "step": 1,
          "unit": "分钟",
          "min": 1,
          "max": 10080
        },
        {
          "key": "behavior_idle_minutes",
          "label": "聊天结束后安静时间",
          "section": "behavior",
          "value": 20,
          "type": "integer",
          "advanced": false,
          "help": "聊天安静多久后才尝试主动。",
          "details": "范围1–1440分钟；私聊看当前会话，群聊看全群最近消息。活跃时先不插话。",
          "example": "20表示最近20分钟内仍有聊天就继续等待。",
          "parent": "autonomy_enabled",
          "level": 1,
          "step": 1,
          "unit": "分钟",
          "min": 1,
          "max": 1440
        },
        {
          "key": "behavior_style",
          "label": "主动节奏",
          "section": "behavior",
          "value": "balanced",
          "type": "enum",
          "advanced": false,
          "help": "选择轻柔、自然或活泼的主动节奏。",
          "details": "影响开口意愿和动机；随机等待、安静时间、额度等硬限制始终生效。",
          "example": "不喜欢打扰选“轻柔”；想多聊一些选“活泼”。",
          "parent": "autonomy_enabled",
          "level": 1,
          "options": [
            {
              "value": "gentle",
              "label": "轻柔"
            },
            {
              "value": "balanced",
              "label": "自然"
            },
            {
              "value": "lively",
              "label": "活泼"
            }
          ]
        },
        {
          "key": "behavior_emotional_share",
          "label": "允许分享心情",
          "section": "behavior",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "允许熟悉私聊关系中轻轻分享心情。",
          "details": "只在合适的私聊关系下使用；不索取安慰、不强求回复，也不把私聊情绪带入群聊。",
          "example": "可出现“今天有点累，想听听你今天的趣事”；关闭后少用此类动机。",
          "parent": "autonomy_enabled",
          "level": 1
        },
        {
          "key": "behavior_provider_id",
          "label": "主动聊天模型",
          "section": "behavior",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "主动聊天专用模型。",
          "details": "留空沿用默认或当前聊天模型；仍受全局模型预算与主动行为额度约束。",
          "example": "主动聊天选轻量模型，日常回复继续使用主模型。",
          "parent": "autonomy_enabled",
          "level": 1,
          "provider_kind": "chat",
          "options": [
            {
              "value": "",
              "label": "跟随当前聊天模型"
            },
            {
              "value": "fixture-chat",
              "label": "合成聊天模型"
            }
          ]
        },
        {
          "key": "diary_retries",
          "label": "日记重试次数",
          "section": "experience",
          "value": 2,
          "type": "integer",
          "advanced": false,
          "help": "日记失败后的重试上限。",
          "details": "范围0–2；每次尝试都消耗预算，未知结果不被随意视为失败重发。",
          "example": "0不重试；2允许在明确可重试失败后有限再试。",
          "parent": "diary_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "dream_per_night",
          "label": "每夜梦境上限",
          "section": "experience",
          "value": 2,
          "type": "integer",
          "advanced": false,
          "help": "每个睡眠周期的梦境尝试上限。",
          "details": "范围1–2；所有尝试计入本周期额度，失败不会让额度无限恢复。",
          "example": "1表示每晚最多尝试一次梦境。",
          "parent": "dream_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "diary_retention_days",
          "label": "日记保留时间",
          "section": "experience",
          "value": 30,
          "type": "integer",
          "advanced": false,
          "help": "未固定日记的保留天数。",
          "details": "范围1–365；到期清理未固定记录，已固定记录按保留规则处理。",
          "example": "30表示保留最近约一个月的未固定日记。",
          "parent": "diary_enabled",
          "level": 1,
          "step": 1,
          "unit": "天"
        },
        {
          "key": "dream_retention_days",
          "label": "梦境保留时间",
          "section": "experience",
          "value": 7,
          "type": "integer",
          "advanced": false,
          "help": "未固定梦境的保留天数。",
          "details": "范围1–30；与清晰度衰减分别控制保存时间和显示感受。",
          "example": "7表示保存约一周的未固定梦境。",
          "parent": "dream_enabled",
          "level": 1,
          "step": 1,
          "unit": "天"
        },
        {
          "key": "dream_half_life_seconds",
          "label": "梦境清晰度半衰期",
          "section": "experience",
          "value": 86400,
          "type": "integer",
          "advanced": false,
          "help": "梦境清晰度减半需要的时间。",
          "details": "单位秒；清晰度随时间衰减，不修改梦境为真实内容，也不替代保留期限。",
          "example": "86400表示一天后清晰度约减半。",
          "parent": "dream_enabled",
          "level": 1,
          "step": 1,
          "unit": "秒"
        },
        {
          "key": "experience_body_chars",
          "label": "日记与梦境字数上限",
          "section": "experience",
          "value": 2000,
          "type": "integer",
          "advanced": false,
          "help": "一篇日记或梦境的字数上限。",
          "details": "范围1–8000字符，用于限制生成记录体积；Token预算另行限制。",
          "example": "2000限制每篇正文最多约2000字符。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "model_concurrency",
          "label": "模型并发上限",
          "section": "emotion",
          "value": 1,
          "type": "integer",
          "advanced": true,
          "help": "后台模型任务同时执行的上限。",
          "details": "范围1–8；只限制本插件任务，与AstrBot普通聊天并发配置分开。",
          "example": "1适合轻量部署；2允许两个后台任务并行。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "queue_size",
          "label": "模型队列上限",
          "section": "emotion",
          "value": 100,
          "type": "integer",
          "advanced": false,
          "help": "等待执行的后台任务队列容量。",
          "details": "范围1–1000；队列有界，容量不是每日调用额度。",
          "example": "100表示最多排队100个任务。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "model_daily_limit",
          "label": "每日模型调用上限",
          "section": "emotion",
          "value": 48,
          "type": "integer",
          "advanced": true,
          "help": "每天后台模型调用的总预算。",
          "details": "正整数次；跨情绪、日记、梦境和行为共用，预留后的失败尝试也计入。",
          "example": "48表示每天最多预留48次本插件后台调用。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "emotion_interval_seconds",
          "label": "情绪分析间隔",
          "section": "emotion",
          "value": 600,
          "type": "integer",
          "advanced": false,
          "help": "同一范围情绪分析的最小间隔。",
          "details": "单位秒，控制模型细化频率；不会保证到点调用，必须有可用事件、模型和预算。静默时段不调用模型，只保留本地规则增量。",
          "example": "600表示至少隔10分钟再分析一次。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "秒"
        },
        {
          "key": "emotion_quiet_start_hour",
          "label": "情绪静默开始（小时）",
          "section": "emotion",
          "value": 3,
          "type": "integer",
          "advanced": false,
          "help": "情绪静默时段的开始小时。",
          "details": "按本地时区24小时制填写0–23；与结束小时相同表示不启用静默。静默只跳过模型分析，本地规则仍随聊天生效。",
          "example": "3表示03:00起不调用模型；想连凌晨也分析就与结束设为同一小时。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "时",
          "min": 0,
          "max": 23
        },
        {
          "key": "emotion_quiet_end_hour",
          "label": "情绪静默结束（小时）",
          "section": "emotion",
          "value": 8,
          "type": "integer",
          "advanced": false,
          "help": "情绪静默时段的结束小时。",
          "details": "按本地时区24小时制填写0–23，结束小时本身恢复分析。开始大于结束表示跨午夜。",
          "example": "8表示08:00恢复模型分析；开始22、结束6表示22:00到次日06:00静默。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "时",
          "min": 0,
          "max": 23
        },
        {
          "key": "emotion_intensity",
          "label": "情绪强度",
          "section": "emotion",
          "value": "normal",
          "type": "enum",
          "advanced": false,
          "help": "情绪起伏的三档强度。",
          "details": "只放大单次情绪增量与同类刺激的累计上限，不改半衰期和衰减速度；数值越大，回复时情绪变化越明显。",
          "example": "平常为推荐档；嫌情绪变化太快要选保守，嫌太平淡选激进。改完在设置页保存即可生效。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "options": [
            {
              "value": "gentle",
              "label": "保守"
            },
            {
              "value": "normal",
              "label": "平常"
            },
            {
              "value": "intense",
              "label": "激进"
            }
          ]
        },
        {
          "key": "model_input_tokens",
          "label": "模型输入上限",
          "section": "emotion",
          "value": 32768,
          "type": "integer",
          "advanced": true,
          "help": "每次后台模型任务的输入上限。",
          "details": "范围1–32768 Token；素材会受此预算限制，不是字符数或每日总量。",
          "example": "4096适合短任务；较长日记可以适度提高。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "Token"
        },
        {
          "key": "model_output_tokens",
          "label": "模型输出上限",
          "section": "emotion",
          "value": 1024,
          "type": "integer",
          "advanced": true,
          "help": "每次后台任务请求的输出Token上限。",
          "details": "范围1–8192；部分主动行为会采用更小的内部上限，以控制长度和打扰。",
          "example": "1024可用于日记；主动消息仍会更简短。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "Token"
        },
        {
          "key": "model_timeout_seconds",
          "label": "模型调用超时",
          "section": "emotion",
          "value": 30,
          "type": "integer",
          "advanced": true,
          "help": "后台模型任务的超时时间。",
          "details": "范围1–120秒；超时不证明上游没有执行，结果未知时不会自动重复发送。",
          "example": "30秒适合通常响应较快的模型；较慢模型可填60。",
          "parent": "emotion_model_enabled",
          "level": 1,
          "step": 1,
          "unit": "秒"
        },
        {
          "key": "window_days",
          "label": "聊天素材保留时间",
          "section": "memory",
          "value": 7,
          "type": "integer",
          "advanced": true,
          "help": "聊天正文素材保留多少天。",
          "details": "范围1–7；同时受每会话和全局条数上限约束，最早到达的限制生效。",
          "example": "7表示最多使用最近一周的正文素材。",
          "parent": "livingmemory_enabled",
          "level": 1,
          "step": 1,
          "unit": "天"
        },
        {
          "key": "window_per_scope",
          "label": "每个会话素材上限",
          "section": "memory",
          "value": 200,
          "type": "integer",
          "advanced": true,
          "help": "一个真实会话最多保留的素材条数。",
          "details": "范围1–200；与全局条数、保留天数共同限制，不跨群私合并正文。",
          "example": "200表示每个范围最多保留最近200条素材。",
          "parent": "livingmemory_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "window_global",
          "label": "全部素材上限",
          "section": "memory",
          "value": 10000,
          "type": "integer",
          "advanced": true,
          "help": "全部会话素材的总条数上限。",
          "details": "范围1–10000；到达上限时按清理规则裁剪，不代表无限保存平台消息。",
          "example": "10000表示全插件最多保留一万条正文素材。",
          "parent": "livingmemory_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "body_max_chars",
          "label": "单条素材字数上限",
          "section": "memory",
          "value": 8000,
          "type": "integer",
          "advanced": true,
          "help": "单条聊天正文的最大字符数。",
          "details": "范围1–8000；接收素材时截断超长正文，模型输入Token限制另行生效。",
          "example": "8000避免单条超长消息占满素材窗口。",
          "parent": "livingmemory_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "event_days",
          "label": "事件保留时间",
          "section": "memory",
          "value": 30,
          "type": "integer",
          "advanced": true,
          "help": "不含正文的事件记录保留天数。",
          "details": "正整数天；事件记录与正文素材、日记梦境各有保留规则。",
          "example": "30表示事件记录按约一个月清理。",
          "parent": "livingmemory_enabled",
          "level": 1,
          "step": 1,
          "unit": "天"
        },
        {
          "key": "persona_shared_state",
          "label": "同一人格共享状态",
          "section": "persona",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "同一人格共享情绪与精力数值。",
          "details": "共享只合并同一实例、同一人格的数值状态；聊天正文和关系来源仍按真实会话隔离。",
          "example": "希望私聊和群聊看到同一份精力：开启；希望分开作息：关闭。",
          "parent": "persona_mode",
          "level": 1
        },
        {
          "key": "allow_sleep",
          "label": "允许TA睡眠",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "允许睡眠状态影响聊天可用性。",
          "details": "关闭后继续记录精力，但不因睡眠阻断聊天；开启时还需自动作息和相应规则生效。",
          "example": "希望夜里仍随时回复：关闭；希望有真实作息：开启。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "nap_enabled",
          "label": "启用午休",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "启用午休时间段。",
          "details": "与午休开始和结束配合；允许睡眠关闭时仍不阻断聊天。",
          "example": "开启并设置13:00至14:30。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "nap_start",
          "label": "午休开始",
          "section": "night",
          "value": "13:00",
          "type": "string",
          "advanced": false,
          "help": "午休的开始时间。",
          "details": "本地24小时HH:MM；必须与午休结束不同，支持跨午夜但一般使用白天。",
          "example": "13:00表示下午一点开始午休。",
          "parent": "nap_enabled",
          "level": 2
        },
        {
          "key": "nap_end",
          "label": "午休结束",
          "section": "night",
          "value": "14:30",
          "type": "string",
          "advanced": false,
          "help": "午休的结束时间。",
          "details": "与午休开始配对，实际可用性还受精力和其他作息状态影响。",
          "example": "14:30表示下午两点半结束午休。",
          "parent": "nap_enabled",
          "level": 2
        },
        {
          "key": "fatigue_start",
          "label": "夜间疲劳开始",
          "section": "night",
          "value": "23:30",
          "type": "string",
          "advanced": false,
          "help": "夜间疲劳与睡眠周期的起点。",
          "details": "从此时开始夜间阶段；恍惚转困时间取起点与沉睡时间之间的中点。",
          "example": "23:30起点、02:30沉睡，则次日01:00转困。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "fatigue_end",
          "label": "夜间疲劳结束",
          "section": "night",
          "value": "07:00",
          "type": "string",
          "advanced": false,
          "help": "夜间疲劳消耗的结束时间。",
          "details": "停止这一段疲劳消耗，不代表可以退出沉睡；基础起床加本周期赖床值决定实际起床。",
          "example": "07:00停止疲劳消耗，但08:00起床配置仍有效。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "deep_sleep_at",
          "label": "沉睡时间",
          "section": "night",
          "value": "02:30",
          "type": "string",
          "advanced": false,
          "help": "进入沉睡的时间。",
          "details": "须位于夜间起点与基础起床之间，支持跨午夜；本地HH:MM，宿主校验时间顺序。",
          "example": "23:30→02:30→08:00合法；沉睡09:00会被拒绝。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "lie_in_min_minutes",
          "label": "最少赖床时间",
          "section": "night",
          "value": 0,
          "type": "integer",
          "advanced": false,
          "help": "本周期赖床的最少分钟数。",
          "details": "可设0；最少不得大于最多，实际抽取结果在本周期内固定。",
          "example": "0至30，允许准时起床或赖床最多半小时。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "step": 1,
          "unit": "分钟"
        },
        {
          "key": "lie_in_max_minutes",
          "label": "最多赖床时间",
          "section": "night",
          "value": 90,
          "type": "integer",
          "advanced": false,
          "help": "本周期赖床的最多分钟数。",
          "details": "范围0–1440分钟；与最少值组成随机区间，不是每次刷新重抽。",
          "example": "最少15、最多45，基础08:00则08:15至08:45起床。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "step": 1,
          "unit": "分钟"
        },
        {
          "key": "wake_mode",
          "label": "聊天唤醒方式",
          "section": "night",
          "value": "chat",
          "type": "enum",
          "advanced": false,
          "help": "谁可以通过聊天叫醒 TA。",
          "details": "仅私聊、不允许唤醒、私聊或群聊原生@Bot；普通文本里的@名字不等于原生提及。",
          "example": "不想群聊打断睡眠：选“仅私聊”。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "options": [
            {
              "value": "chat",
              "label": "仅私聊"
            },
            {
              "value": "never",
              "label": "不允许聊天唤醒"
            },
            {
              "value": "both",
              "label": "私聊或群原生@Bot"
            }
          ]
        },
        {
          "key": "wake_reply_limit",
          "label": "唤醒回复轮数",
          "section": "night",
          "value": 3,
          "type": "integer",
          "advanced": false,
          "help": "一次聊天唤醒可用的回复尝试数。",
          "details": "范围1–100；生成失败也计入，窗口时间到达同样停止。",
          "example": "3轮、10分钟，最多尝试3次并且不超过窗口。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "wake_window_minutes",
          "label": "唤醒窗口",
          "section": "night",
          "value": 10,
          "type": "integer",
          "advanced": false,
          "help": "一次聊天唤醒的最长窗口。",
          "details": "范围1–1440分钟，从第一次宿主提交开始固定计算，后续消息不无限延长。",
          "example": "10表示叫醒后最多维持10分钟的回复窗口。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "step": 1,
          "unit": "分钟"
        },
        {
          "key": "energy_reply_cost",
          "label": "每次回复精力消耗",
          "section": "night",
          "value": 4.0,
          "type": "float",
          "advanced": false,
          "help": "每次可见回复消耗的精力点数。",
          "details": "总精力固定100；数值0–100，步进0.1，每次可见回复只记一次。",
          "example": "4.0表示一条实际回复消耗4点。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "step": 0.1,
          "unit": "点/次"
        },
        {
          "key": "energy_fatigue_per_minute",
          "label": "疲劳精力消耗速率",
          "section": "night",
          "value": 0.8,
          "type": "float",
          "advanced": false,
          "help": "清醒疲劳阶段每分钟消耗精力。",
          "details": "数值0–100，步进0.1；只在适用疲劳状态消耗，不将子项相加冒充总变化。",
          "example": "0.8表示适用状态持续10分钟约消耗8点。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "step": 0.1,
          "unit": "点/分钟"
        },
        {
          "key": "energy_recovery_per_minute",
          "label": "精力恢复速率",
          "section": "night",
          "value": 1.5,
          "type": "float",
          "advanced": false,
          "help": "睡眠或非疲劳阶段每分钟恢复精力。",
          "details": "数值0–100，步进0.1；实际恢复受阶段和总上限100限制。",
          "example": "1.5表示适用状态10分钟约恢复15点，上限100。",
          "parent": "night_schedule_enabled",
          "level": 1,
          "step": 0.1,
          "unit": "点/分钟"
        },
        {
          "key": "catchup_enabled",
          "label": "醒后阅读未读",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "醒来后阅读已保存的未读消息。",
          "details": "从本插件有真实来源的未读归档读取；不等于访问平台全部历史，补答开关独立。",
          "example": "只希望醒后了解聊天：开启阅读、关闭历史补答。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "catchup_reply_enabled",
          "label": "醒后历史补答",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "阅读未读后允许有限历史补答。",
          "details": "需要醒后阅读、可用模型和预算；生成与发送仍受身份及可用性检查。",
          "example": "阅读与补答同时开启，醒后可对仍有意义的未读内容补充回复。",
          "parent": "catchup_enabled",
          "level": 2
        },
        {
          "key": "closing_enabled",
          "label": "睡前晚安",
          "section": "night",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "允许睡前在近期参与的会话道晚安。",
          "details": "只考虑真实且近期参与过的会话；不是向所有好友群发，发送仍需守卫允许。",
          "example": "夜间23:30开始、提前5分钟，可在23:25附近评估晚安。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "closing_random",
          "label": "道别语随机生成",
          "section": "night",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "使用模型生成睡前道别。",
          "details": "关闭时使用本地模板；开启时一次生成占用模型预算，不保证每次发送。",
          "example": "想减少模型调用：关闭；希望道别更有变化：开启。",
          "parent": "closing_enabled",
          "level": 2
        },
        {
          "key": "closing_lead_minutes",
          "label": "晚安提前量",
          "section": "night",
          "value": 5,
          "type": "integer",
          "advanced": false,
          "help": "夜间起点前多久评估晚安。",
          "details": "范围0–60分钟，以疲劳开始时间为基准；调度间隔影响实际评估时刻。",
          "example": "起点23:30、提前5分钟，计划在23:25附近评估。",
          "parent": "closing_enabled",
          "level": 2,
          "step": 1,
          "unit": "分钟"
        },
        {
          "key": "diary_provider_id",
          "label": "日记模型",
          "section": "experience",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "日记生成专用模型。",
          "details": "留空沿用默认模型；与梦境模型可分别配置。",
          "example": "日记用常用模型，梦境用更有创作风格的模型。",
          "parent": "diary_enabled",
          "level": 1,
          "provider_kind": "chat",
          "options": [
            {
              "value": "",
              "label": "跟随当前聊天模型"
            },
            {
              "value": "fixture-chat",
              "label": "合成聊天模型"
            }
          ]
        },
        {
          "key": "dream_provider_id",
          "label": "梦境模型",
          "section": "experience",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "梦境生成专用模型。",
          "details": "留空沿用默认模型；梦境必须保留想象属性，不能把虚构写成真实经历。",
          "example": "选择擅长简短叙事的已配置模型。",
          "parent": "dream_enabled",
          "level": 1,
          "provider_kind": "chat",
          "options": [
            {
              "value": "",
              "label": "跟随当前聊天模型"
            },
            {
              "value": "fixture-chat",
              "label": "合成聊天模型"
            }
          ]
        },
        {
          "key": "catchup_provider_id",
          "label": "补课模型",
          "section": "night",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "醒后补课与补答使用的模型。",
          "details": "留空跟随默认或会话模型，不会修改正常聊天所用模型。",
          "example": "未读较多时选支持较长上下文的已配置模型。",
          "parent": "catchup_enabled",
          "level": 2,
          "provider_kind": "chat",
          "options": [
            {
              "value": "",
              "label": "跟随当前聊天模型"
            },
            {
              "value": "fixture-chat",
              "label": "合成聊天模型"
            }
          ]
        },
        {
          "key": "closing_provider_id",
          "label": "收尾模型",
          "section": "night",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "睡前道别专用模型。",
          "details": "只在随机生成道别启用且有预算时使用；留空沿用默认模型。",
          "example": "选择轻量模型生成一句简短晚安。",
          "parent": "closing_enabled",
          "level": 2,
          "provider_kind": "chat",
          "options": [
            {
              "value": "",
              "label": "跟随当前聊天模型"
            },
            {
              "value": "fixture-chat",
              "label": "合成聊天模型"
            }
          ]
        },
        {
          "key": "home_city",
          "label": "Bot住所城市",
          "section": "experience",
          "value": "",
          "type": "string",
          "advanced": false,
          "help": "TA 的住所城市，用于天气背景。",
          "details": "填写可识别的公开城市名称，不填私人详细地址；城市信息不自动决定时区。",
          "example": "填“上海”，同时将时区设为Asia/Shanghai。",
          "parent": "",
          "level": 0
        },
        {
          "key": "embedding_provider_id",
          "label": "向量模型",
          "section": "memory",
          "value": "",
          "type": "enum",
          "advanced": false,
          "help": "本地向量记忆使用的原生向量模型。",
          "details": "仅本地向量记忆需要此项；启用 LivingMemory 时不需要配置本地 embedding（WebUI 中该项置灰）。它与后台聊天模型分开。",
          "example": "使用本地向量记忆时选择已配置的 AstrBot 向量提供商。",
          "parent": "livingmemory_enabled",
          "level": 1,
          "provider_kind": "embedding",
          "options": [
            {
              "value": "",
              "label": "未配置"
            },
            {
              "value": "fixture-embedding",
              "label": "合成向量模型"
            }
          ]
        },
        {
          "key": "livingmemory_enabled",
          "label": "使用LivingMemory",
          "section": "memory",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "使用已安装的 LivingMemory 记忆接口。",
          "details": "关闭时使用本地向量路径；开启仍需外部插件可用与权限通过，不会将固定资料替代动态记忆。",
          "example": "已安装LivingMemory并完成配置后开启；否则配置本地向量模型。",
          "parent": "",
          "level": 0
        },
        {
          "key": "memory_write",
          "label": "允许写入记忆",
          "section": "memory",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "允许写入聊天回复体验。",
          "details": "不按语义价值筛掉聊天回复；仍按真实来源隔离并遵守素材保留期。",
          "example": "需要记录聊天回复体验：开启；停止新增记录：关闭。",
          "parent": "livingmemory_enabled",
          "level": 1
        },
        {
          "key": "relationship_stage_names",
          "label": "关系阶段自定义名称",
          "section": "relationship",
          "value": "[\"反感\",\"陌生\",\"友好\",\"亲近\",\"独特\"]",
          "type": "string",
          "advanced": false,
          "help": "五档关系的自定义名称，留空使用默认名称。",
          "details": "0–10反感、11–24陌生、25–44友好、45–99亲近、100独特。普通互动最高99；旧11档配置自动兼容。",
          "example": "[\"反感\",\"陌生\",\"友好\",\"亲近\",\"主人\"]",
          "parent": "",
          "level": 0
        },
        {
          "key": "relationship_stage_descriptions",
          "label": "关系阶段描述",
          "section": "relationship",
          "value": "[\"\",\"\",\"\",\"\"]",
          "type": "string",
          "advanced": false,
          "help": "前四档关系的相处描述，留空沿用默认描述。",
          "details": "依次对应反感、陌生、友好、亲近；每项最多1000字。描述用于关系表达，不改变分数规则。独特档在同一行单独设置。",
          "example": "[\"保持距离，任务可靠\",\"礼貌谨慎，慢慢了解\",\"自然友善，肯定善意\",\"主动关心，尊重边界\"]",
          "parent": "emotion_model_enabled",
          "level": 1
        },
        {
          "key": "relationship_special_description",
          "label": "独特关系说明",
          "section": "relationship",
          "value": "",
          "type": "string",
          "advanced": false,
          "help": "100分独特关系的自定义说明。",
          "details": "管理员设置100分时使用，可填写相处方式；单个对象的关系备注优先。最多1000字。",
          "example": "例如：主人，温柔陪伴、主动关心，保留傲娇表达。",
          "parent": "emotion_model_enabled",
          "level": 1
        },
        {
          "key": "wake_autocatchup_enabled",
          "label": "自然醒后主动补答",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "自然醒后是否主动爬楼补答。",
          "details": "只对这一段睡眠期确有未读的会话生效；没有未读就不读不发，也不会重复补答。",
          "example": "希望它醒来自己看看群里的消息：开启；只想被动等消息：关闭。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "wake_greeting_enabled",
          "label": "先发一句刚醒的招呼",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false,
          "help": "爬楼前是否先发一句刚醒的招呼。",
          "details": "招呼只是一句话，用来交代「刚醒」；关闭后直接进入补答或继续安静。",
          "example": "不想它冒头时关闭。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "wake_greeting_texts",
          "label": "刚醒招呼候选句子",
          "section": "night",
          "value": "刚醒，我看看之前你们说了什么。|我醒了，先把这几小时翻一翻。|醒了…看看都说了什么。",
          "type": "string",
          "advanced": false,
          "help": "刚醒招呼的候选句子。",
          "details": "用竖线 | 分隔，每次随机取一条；留空则使用默认一句。",
          "example": "刚醒，我看看之前你们说了什么。|我醒了，先把这几小时翻一翻。",
          "parent": "night_schedule_enabled",
          "level": 1
        },
        {
          "key": "relationship_edit_enabled",
          "label": "允许在关系页修改好感",
          "section": "relationship",
          "value": false,
          "type": "boolean",
          "advanced": false,
          "help": "是否在关系页显示好感编辑。",
          "details": "默认关闭，关系页只读；打开后才会出现好感分数与冻结开关的编辑表单，保存写入真实关系记录并留审计。",
          "example": "日常只观察关系变化：保持关闭；需要人工校正某个账号的好感时才打开。",
          "parent": "emotion_model_enabled",
          "level": 1
        }
      ],
      "groups": [
        {
          "id": "quick_start",
          "label": "快速开始",
          "field_keys": [
            "enabled",
            "mode",
            "timezone",
            "provider_id",
            "fallback_provider_id",
            "home_city"
          ]
        },
        {
          "id": "persona",
          "label": "人格与状态模式",
          "field_keys": [
            "persona_mode",
            "persona_id",
            "persona_shared_state"
          ]
        },
        {
          "id": "emotion",
          "label": "情绪",
          "field_keys": [
            "emotion_model_enabled",
            "scheduler_seconds",
            "model_concurrency",
            "queue_size",
            "model_daily_limit",
            "emotion_interval_seconds",
            "emotion_quiet_start_hour",
            "emotion_quiet_end_hour",
            "emotion_intensity",
            "model_input_tokens",
            "model_output_tokens",
            "model_timeout_seconds"
          ]
        },
        {
          "id": "relationship",
          "label": "关系",
          "field_keys": [
            "relationship_stage_names",
            "relationship_stage_descriptions",
            "relationship_special_description",
            "relationship_edit_enabled"
          ]
        },
        {
          "id": "behavior",
          "label": "主动行为",
          "field_keys": [
            "autonomy_enabled",
            "group_autonomy_enabled",
            "autonomy_qq_ids",
            "autonomy_qq_group_ids",
            "muted_scopes",
            "dnd_start",
            "dnd_end",
            "active_start",
            "active_end",
            "behavior_daily_limit",
            "behavior_scope_daily_limit",
            "behavior_cooldown_seconds",
            "behavior_unanswered_limit",
            "behavior_random_min_minutes",
            "behavior_random_max_minutes",
            "behavior_idle_minutes",
            "behavior_style",
            "behavior_emotional_share",
            "behavior_provider_id"
          ]
        },
        {
          "id": "night",
          "label": "长夜",
          "field_keys": [
            "night_schedule_enabled",
            "wake_at",
            "allow_sleep",
            "nap_enabled",
            "nap_start",
            "nap_end",
            "fatigue_start",
            "fatigue_end",
            "deep_sleep_at",
            "lie_in_min_minutes",
            "lie_in_max_minutes",
            "wake_mode",
            "wake_reply_limit",
            "wake_window_minutes",
            "energy_reply_cost",
            "energy_fatigue_per_minute",
            "energy_recovery_per_minute",
            "catchup_enabled",
            "catchup_reply_enabled",
            "closing_enabled",
            "closing_random",
            "closing_lead_minutes",
            "catchup_provider_id",
            "closing_provider_id",
            "wake_autocatchup_enabled",
            "wake_greeting_enabled",
            "wake_greeting_texts"
          ]
        },
        {
          "id": "experience",
          "label": "日记与梦境",
          "field_keys": [
            "dream_enabled",
            "dream_theme_pool",
            "dream_owner_notify",
            "dream_owner_qq",
            "diary_enabled",
            "diary_at",
            "diary_backfill_yesterday",
            "diary_retries",
            "dream_per_night",
            "diary_retention_days",
            "dream_retention_days",
            "dream_half_life_seconds",
            "experience_body_chars",
            "diary_provider_id",
            "dream_provider_id",
            "home_city"
          ]
        },
        {
          "id": "memory",
          "label": "记忆",
          "field_keys": [
            "memory_read",
            "window_days",
            "window_per_scope",
            "window_global",
            "body_max_chars",
            "event_days",
            "embedding_provider_id",
            "livingmemory_enabled",
            "memory_write"
          ]
        }
      ],
      "readonly": [
        {
          "key": "energy_max",
          "label": "总精力",
          "type": "float",
          "value": 100.0,
          "step": 0.1,
          "unit": "点",
          "readonly": true,
          "section": "night",
          "parent": "night_schedule_enabled",
          "level": 1,
          "help": "总精力固定为100点。",
          "details": "只读上限，用于统一精力曲线和展示，不能通过配置修改。",
          "example": "当前74点表示上限100中的74点。"
        }
      ]
    },
    "emotion_model_analysis": {
      "status": "uncollected",
      "reason_code": "uncollected",
      "applied": false
    },
    "behavior_model": {
      "available": false,
      "reason_code": "source_invalid"
    },
    "selection": {
      "persona_id": "fixture-persona",
      "view_scope": "global",
      "context_id": "",
      "platform": ""
    },
    "state_mode": "persona",
    "capabilities": [
      "config.write",
      "configuration.read",
      "config.receipt",
      "behavior.preview",
      "scopes.read",
      "relationships.read",
      "relationship.write",
      "energy.read",
      "settings-options.read",
      "memory.sync"
    ],
    "health": [
      {
        "name": "runtime",
        "status": "ok",
        "reason": "ready"
      },
      {
        "name": "configuration",
        "status": "ok",
        "reason": "native"
      },
      {
        "name": "ownership",
        "status": "ok",
        "reason": "exclusive"
      },
      {
        "name": "background",
        "status": "ok",
        "reason": "idle"
      },
      {
        "name": "reply_confirmation",
        "status": "unavailable",
        "reason": "unsupported：当前宿主无可靠回复确认；收尾 120 秒超时取消，不将 after-sent/bool/None 视为发送成功。"
      },
      {
        "name": "behavior_transport",
        "status": "degraded",
        "reason": "未核验到可确认的原生发送通道；发送结果可能未知。"
      }
    ],
    "memory": {
      "mode": "none",
      "backend": "未接入记忆后端",
      "provider": "",
      "provider_ready": false,
      "can_read": false,
      "can_write": false,
      "capabilities": [],
      "reasons": [
        "embedding_not_configured"
      ],
      "reason": "embedding_not_configured",
      "persona_id": "fixture-persona",
      "mirror": {
        "total": 0,
        "provider": "",
        "synced_at": null,
        "truncated": false,
        "items": []
      },
      "sync": {
        "enabled": false,
        "available": false,
        "reason": "",
        "provider": ""
      }
    },
    "experience": {
      "diary_enabled": false,
      "dream_enabled": false,
      "diary": null,
      "dream": null,
      "scope_global": true,
      "reason": "原生人格不可用，请检查设置。",
      "persona_id": ""
    },
    "actions": [
      {
        "id": "night.sleep",
        "enabled": false,
        "context_id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
        "reason": "仅观察：只记录状态，不主动发送。",
        "reason_code": "mode_unavailable"
      },
      {
        "id": "night.wake",
        "enabled": true,
        "context_id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
        "reason": "",
        "reason_code": ""
      },
      {
        "id": "behavior.send",
        "enabled": false,
        "context_id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
        "reason": "仅观察：只记录状态，不主动发送。",
        "reason_code": "mode_unavailable"
      },
      {
        "id": "diary.generate",
        "enabled": false,
        "reason_code": "model_or_persona_unavailable",
        "reason": "请配置可用的原生人格和日记/梦境模型。",
        "context_id": ""
      },
      {
        "id": "dream.generate",
        "enabled": false,
        "reason_code": "dream_disabled",
        "reason": "请先启用梦境生成。",
        "context_id": ""
      }
    ],
    "user_emotion": null,
    "persona": {
      "id": "fixture-persona",
      "name": "fixture-persona",
      "source": "AstrBot native",
      "revision": "",
      "description": "",
      "description_available": false
    },
    "bot_state": {
      "dimensions": {
        "pleasure": 0.5,
        "arousal": 0.2,
        "stress": 0.0,
        "social_need": 0.3,
        "control": 0.5
      },
      "baseline": {
        "pleasure": 0.5,
        "arousal": 0.3,
        "stress": 0.0,
        "social_need": 0.3,
        "control": 0.5
      },
      "label": "calm",
      "emotion_analysis": {
        "emotions": {
          "joy": 0.0,
          "anger": 0.0,
          "sadness": 0.0,
          "fear": 0.0,
          "surprise": 0.12,
          "affection": 0.105
        },
        "dimensions": {
          "valence": 0.5,
          "arousal": 0.2,
          "stress": 0.0,
          "social_need": 0.3,
          "control": 0.5,
          "certainty": 0.71
        },
        "basis": "local_affect_heuristic",
        "kind": "heuristic",
        "note": "仅根据 BotAffect 数值计算的启发式状态指标，仅供软件展示；情绪、控制感和确定感并非实测结果，不代表人的情绪，不是心理诊断",
        "weather_bonus": {
          "joy": 0.0,
          "anger": 0.0,
          "sadness": 0.0,
          "fear": 0.0,
          "surprise": 0.0,
          "affection": 0.0
        }
      },
      "reason": "这是私聊与群聊共享的人格情绪，不绑定具体会话。",
      "reason_codes": [],
      "updated_at": 1800000001.0,
      "version": 14,
      "source": "livingEmotion",
      "global_view": true
    },
    "observation": null,
    "emotion_analysis": {
      "bot": {
        "emotions": {
          "joy": 0.0,
          "anger": 0.0,
          "sadness": 0.0,
          "fear": 0.0,
          "surprise": 0.12,
          "affection": 0.105
        },
        "dimensions": {
          "valence": 0.5,
          "arousal": 0.2,
          "stress": 0.0,
          "social_need": 0.3,
          "control": 0.5,
          "certainty": 0.71
        },
        "basis": "local_affect_heuristic",
        "kind": "heuristic",
        "note": "仅根据 BotAffect 数值计算的启发式状态指标，仅供软件展示；情绪、控制感和确定感并非实测结果，不代表人的情绪，不是心理诊断",
        "weather_bonus": {
          "joy": 0.0,
          "anger": 0.0,
          "sadness": 0.0,
          "fear": 0.0,
          "surprise": 0.0,
          "affection": 0.0
        }
      },
      "human": {}
    },
    "relationship": null,
    "availability": {
      "available": true,
      "state": "awake",
      "display_state": "awake",
      "block_chat": false,
      "reasons": []
    },
    "night": {
      "state": "awake",
      "stage": null,
      "display_state": "awake",
      "energy": 0.741,
      "energy_percent": 74.1,
      "energy_max": 100,
      "sleep_at": null,
      "wake_at": null,
      "cycle_started_at": null,
      "drowsy_at": null,
      "deep_sleep_at": null,
      "base_wake_at": null,
      "cycle_kind": null,
      "lie_in_minutes": null,
      "reason": "",
      "schedule": {
        "schedule_enabled": false,
        "sleep_enabled": true,
        "allow_sleep": true,
        "fatigue_start": "23:30",
        "fatigue_end": "07:00",
        "deep_sleep_at": "02:30",
        "wake_at": "08:00",
        "nap_enabled": true,
        "nap_start": "13:00",
        "nap_end": "14:30",
        "lie_in_min": 0,
        "lie_in_max": 90,
        "wake_mode": "chat",
        "wake_reply_limit": 3,
        "wake_window_minutes": 10,
        "catchup_enabled": true,
        "catchup_reply_enabled": true,
        "timezone": "Asia/Shanghai"
      },
      "catch_up": {
        "enabled": true,
        "reply_enabled": true,
        "completed": 0,
        "total": 0,
        "reason": ""
      }
    },
    "behavior": {
      "enabled": false,
      "reason": "",
      "reason_codes": [],
      "eligible": null,
      "score": null,
      "min_score": null,
      "reasons": [],
      "candidates": [],
      "scope_key": "",
      "remaining": null,
      "daily_used": null,
      "scope_used": null,
      "backoff": null,
      "next_check_at": null,
      "last_check_at": null,
      "last_outcome": "waiting",
      "last_reason": "select_scene",
      "last_reason_text": [
        "选择私聊或群聊后查看具体节奏。"
      ],
      "last_motive": "全局人格视图",
      "random_interval": [
        90,
        240
      ],
      "config": {
        "enabled": true,
        "mode": "observe_only",
        "timezone": "Asia/Shanghai",
        "scheduler_seconds": 60,
        "provider_id": "",
        "fallback_provider_id": "",
        "autonomy_scopes": "",
        "autonomy_enabled": false,
        "group_autonomy_enabled": false,
        "autonomy_qq_ids": "",
        "autonomy_qq_group_ids": "",
        "muted_scopes": "",
        "behavior_style": "balanced",
        "behavior_provider_id": "",
        "behavior_daily_limit": 6,
        "behavior_scope_daily_limit": 2,
        "behavior_cooldown_seconds": 7200,
        "behavior_unanswered_limit": 2,
        "behavior_random_min_minutes": 90,
        "behavior_random_max_minutes": 240,
        "behavior_idle_minutes": 20,
        "behavior_emotional_share": true,
        "active_start": "00:00",
        "active_end": "23:59",
        "dnd_start": "01:00",
        "dnd_end": "08:00"
      },
      "style": "balanced",
      "model_ready": false,
      "cooldown_until": null,
      "motives": [
        "记忆回访",
        "关心近况",
        "轻松闲聊",
        "分享心情",
        "久别问候"
      ]
    },
    "representative_context_id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
    "emotion_curve": {
      "points": [
        {
          "at": 1799913900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0471,
            "sadness": 0.5498,
            "fear": 0.0,
            "surprise": 0.0824,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799914200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0446,
            "sadness": 0.4857,
            "fear": 0.0,
            "surprise": 0.093,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799914500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0417,
            "sadness": 0.4297,
            "fear": 0.0,
            "surprise": 0.1026,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799914800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0386,
            "sadness": 0.3805,
            "fear": 0.0,
            "surprise": 0.1114,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799915100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0355,
            "sadness": 0.3373,
            "fear": 0.0,
            "surprise": 0.1193,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799915400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0324,
            "sadness": 0.2992,
            "fear": 0.0,
            "surprise": 0.1263,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799915700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0295,
            "sadness": 0.2656,
            "fear": 0.0,
            "surprise": 0.1326,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799916000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0267,
            "sadness": 0.2359,
            "fear": 0.0,
            "surprise": 0.1382,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799916300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0242,
            "sadness": 0.2096,
            "fear": 0.0,
            "surprise": 0.1432,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799916600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0218,
            "sadness": 0.1863,
            "fear": 0.0,
            "surprise": 0.1476,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799916900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0196,
            "sadness": 0.1657,
            "fear": 0.0,
            "surprise": 0.1515,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799917200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0176,
            "sadness": 0.1474,
            "fear": 0.0,
            "surprise": 0.1549,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799917500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0158,
            "sadness": 0.1311,
            "fear": 0.0,
            "surprise": 0.1579,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799917800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0142,
            "sadness": 0.1167,
            "fear": 0.0,
            "surprise": 0.1605,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799918100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0127,
            "sadness": 0.1039,
            "fear": 0.0,
            "surprise": 0.1629,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799918400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0113,
            "sadness": 0.0925,
            "fear": 0.0,
            "surprise": 0.1649,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799918700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0101,
            "sadness": 0.0823,
            "fear": 0.0,
            "surprise": 0.1667,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799919000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0091,
            "sadness": 0.0733,
            "fear": 0.0,
            "surprise": 0.1683,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799919300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0081,
            "sadness": 0.0653,
            "fear": 0.0,
            "surprise": 0.1697,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799919600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0072,
            "sadness": 0.0581,
            "fear": 0.0,
            "surprise": 0.1709,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799919900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0064,
            "sadness": 0.0518,
            "fear": 0.0,
            "surprise": 0.172,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799920200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0057,
            "sadness": 0.0461,
            "fear": 0.0,
            "surprise": 0.1729,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799920500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0051,
            "sadness": 0.0411,
            "fear": 0.0,
            "surprise": 0.1738,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799920800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0046,
            "sadness": 0.0366,
            "fear": 0.0,
            "surprise": 0.1745,
            "affection": 0.105
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799921100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0562,
            "sadness": 0.2302,
            "fear": 0.11,
            "surprise": 0.1885,
            "affection": 0.1432
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799921400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0473,
            "sadness": 0.2082,
            "fear": 0.0994,
            "surprise": 0.1864,
            "affection": 0.1416
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799921700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0401,
            "sadness": 0.1879,
            "fear": 0.09,
            "surprise": 0.1845,
            "affection": 0.14
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799922000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0341,
            "sadness": 0.1693,
            "fear": 0.0817,
            "surprise": 0.183,
            "affection": 0.1384
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799922300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0292,
            "sadness": 0.1523,
            "fear": 0.0742,
            "surprise": 0.1817,
            "affection": 0.1368
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799922600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0251,
            "sadness": 0.1368,
            "fear": 0.0676,
            "surprise": 0.1807,
            "affection": 0.1354
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799922900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0216,
            "sadness": 0.1228,
            "fear": 0.0616,
            "surprise": 0.1798,
            "affection": 0.1339
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799923200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0187,
            "sadness": 0.1101,
            "fear": 0.0561,
            "surprise": 0.1792,
            "affection": 0.1326
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799923500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0163,
            "sadness": 0.0987,
            "fear": 0.0512,
            "surprise": 0.1787,
            "affection": 0.1312
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799923800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0142,
            "sadness": 0.0883,
            "fear": 0.0468,
            "surprise": 0.1783,
            "affection": 0.1299
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799924100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0124,
            "sadness": 0.079,
            "fear": 0.0428,
            "surprise": 0.1781,
            "affection": 0.1287
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799924400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0108,
            "sadness": 0.0707,
            "fear": 0.0391,
            "surprise": 0.1779,
            "affection": 0.1275
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799924700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0095,
            "sadness": 0.0632,
            "fear": 0.0358,
            "surprise": 0.1778,
            "affection": 0.1264
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799925000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0083,
            "sadness": 0.0565,
            "fear": 0.0328,
            "surprise": 0.1778,
            "affection": 0.1253
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799925300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0073,
            "sadness": 0.0504,
            "fear": 0.03,
            "surprise": 0.1778,
            "affection": 0.1243
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799925600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0065,
            "sadness": 0.0451,
            "fear": 0.0275,
            "surprise": 0.1778,
            "affection": 0.1233
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799925900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0057,
            "sadness": 0.0402,
            "fear": 0.0252,
            "surprise": 0.1779,
            "affection": 0.1224
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799926200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.005,
            "sadness": 0.0359,
            "fear": 0.023,
            "surprise": 0.178,
            "affection": 0.1215
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799926500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0044,
            "sadness": 0.032,
            "fear": 0.0211,
            "surprise": 0.1781,
            "affection": 0.1206
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799926800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0039,
            "sadness": 0.0286,
            "fear": 0.0193,
            "surprise": 0.1782,
            "affection": 0.1198
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799927100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0035,
            "sadness": 0.0255,
            "fear": 0.0177,
            "surprise": 0.1783,
            "affection": 0.119
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799927400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0031,
            "sadness": 0.0227,
            "fear": 0.0163,
            "surprise": 0.1784,
            "affection": 0.1183
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799927700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0027,
            "sadness": 0.0203,
            "fear": 0.0149,
            "surprise": 0.1785,
            "affection": 0.1176
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799928000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0024,
            "sadness": 0.0181,
            "fear": 0.0137,
            "surprise": 0.1786,
            "affection": 0.1169
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799928300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.2602,
            "surprise": 0.3314,
            "affection": 0.1742
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799928600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.2298,
            "surprise": 0.3074,
            "affection": 0.1718
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799928900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.2039,
            "surprise": 0.2871,
            "affection": 0.1695
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799929200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1818,
            "surprise": 0.2701,
            "affection": 0.167
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799929500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1627,
            "surprise": 0.2557,
            "affection": 0.1646
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799929800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1461,
            "surprise": 0.2437,
            "affection": 0.1622
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799930100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1316,
            "surprise": 0.2335,
            "affection": 0.1598
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799930400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1188,
            "surprise": 0.225,
            "affection": 0.1575
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799930700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1075,
            "surprise": 0.2179,
            "affection": 0.1552
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799931000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0975,
            "surprise": 0.2118,
            "affection": 0.1529
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799931300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0885,
            "surprise": 0.2068,
            "affection": 0.1507
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799931600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0805,
            "surprise": 0.2025,
            "affection": 0.1486
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799931900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0734,
            "surprise": 0.1989,
            "affection": 0.1465
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799932200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0669,
            "surprise": 0.1959,
            "affection": 0.1446
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799932500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.061,
            "surprise": 0.1934,
            "affection": 0.1426
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799932800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0557,
            "surprise": 0.1913,
            "affection": 0.1408
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799933100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0509,
            "surprise": 0.1895,
            "affection": 0.139
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799933400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0466,
            "surprise": 0.188,
            "affection": 0.1373
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799933700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0426,
            "surprise": 0.1867,
            "affection": 0.1357
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799934000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.039,
            "surprise": 0.1856,
            "affection": 0.1342
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799934300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0357,
            "surprise": 0.1847,
            "affection": 0.1327
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799934600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0327,
            "surprise": 0.184,
            "affection": 0.1313
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799934900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0299,
            "surprise": 0.1833,
            "affection": 0.1299
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799935200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0274,
            "surprise": 0.1828,
            "affection": 0.1286
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799935500,
          "emotions": {
            "joy": 0.3119,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.3537,
            "affection": 0.4564
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799935800,
          "emotions": {
            "joy": 0.2779,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.3287,
            "affection": 0.426
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799936100,
          "emotions": {
            "joy": 0.2476,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.3067,
            "affection": 0.3984
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799936400,
          "emotions": {
            "joy": 0.2206,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2876,
            "affection": 0.3734
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799936700,
          "emotions": {
            "joy": 0.1965,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2711,
            "affection": 0.3507
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799937000,
          "emotions": {
            "joy": 0.1751,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2569,
            "affection": 0.3302
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799937300,
          "emotions": {
            "joy": 0.156,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2447,
            "affection": 0.3115
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799937600,
          "emotions": {
            "joy": 0.139,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2344,
            "affection": 0.2946
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799937900,
          "emotions": {
            "joy": 0.1238,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2255,
            "affection": 0.2791
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799938200,
          "emotions": {
            "joy": 0.1103,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2181,
            "affection": 0.2651
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799938500,
          "emotions": {
            "joy": 0.0983,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2117,
            "affection": 0.2523
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799938800,
          "emotions": {
            "joy": 0.0875,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2064,
            "affection": 0.2407
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799939100,
          "emotions": {
            "joy": 0.078,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.2019,
            "affection": 0.23
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799939400,
          "emotions": {
            "joy": 0.0695,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1982,
            "affection": 0.2203
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799939700,
          "emotions": {
            "joy": 0.0619,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.195,
            "affection": 0.2115
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799940000,
          "emotions": {
            "joy": 0.0551,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1924,
            "affection": 0.2034
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799940300,
          "emotions": {
            "joy": 0.0491,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1902,
            "affection": 0.1959
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799940600,
          "emotions": {
            "joy": 0.0438,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1883,
            "affection": 0.1891
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799940900,
          "emotions": {
            "joy": 0.039,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1868,
            "affection": 0.1829
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799941200,
          "emotions": {
            "joy": 0.0347,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1855,
            "affection": 0.1772
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799941500,
          "emotions": {
            "joy": 0.0309,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1845,
            "affection": 0.172
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799941800,
          "emotions": {
            "joy": 0.0276,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1836,
            "affection": 0.1671
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799942100,
          "emotions": {
            "joy": 0.0246,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1829,
            "affection": 0.1627
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799942400,
          "emotions": {
            "joy": 0.0219,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1823,
            "affection": 0.1586
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799942700,
          "emotions": {
            "joy": 0.5838,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0899,
            "surprise": 0.0824,
            "affection": 0.4731
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799943000,
          "emotions": {
            "joy": 0.5231,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0839,
            "surprise": 0.093,
            "affection": 0.4349
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799943300,
          "emotions": {
            "joy": 0.4684,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0781,
            "surprise": 0.1026,
            "affection": 0.4005
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799943600,
          "emotions": {
            "joy": 0.4193,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0725,
            "surprise": 0.1114,
            "affection": 0.3696
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799943900,
          "emotions": {
            "joy": 0.3752,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0672,
            "surprise": 0.1193,
            "affection": 0.3418
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799944200,
          "emotions": {
            "joy": 0.3356,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0621,
            "surprise": 0.1263,
            "affection": 0.3168
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799944500,
          "emotions": {
            "joy": 0.3,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0573,
            "surprise": 0.1326,
            "affection": 0.2943
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799944800,
          "emotions": {
            "joy": 0.2682,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0529,
            "surprise": 0.1382,
            "affection": 0.2742
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799945100,
          "emotions": {
            "joy": 0.2396,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0487,
            "surprise": 0.1432,
            "affection": 0.2562
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799945400,
          "emotions": {
            "joy": 0.2141,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0449,
            "surprise": 0.1476,
            "affection": 0.24
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799945700,
          "emotions": {
            "joy": 0.1912,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0413,
            "surprise": 0.1515,
            "affection": 0.2255
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799946000,
          "emotions": {
            "joy": 0.1707,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.038,
            "surprise": 0.1549,
            "affection": 0.2126
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799946300,
          "emotions": {
            "joy": 0.1524,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0349,
            "surprise": 0.1579,
            "affection": 0.201
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799946600,
          "emotions": {
            "joy": 0.1361,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0321,
            "surprise": 0.1605,
            "affection": 0.1907
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799946900,
          "emotions": {
            "joy": 0.1214,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0295,
            "surprise": 0.1629,
            "affection": 0.1814
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799947200,
          "emotions": {
            "joy": 0.1084,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0271,
            "surprise": 0.1649,
            "affection": 0.1732
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799947500,
          "emotions": {
            "joy": 0.0967,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0248,
            "surprise": 0.1667,
            "affection": 0.1658
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799947800,
          "emotions": {
            "joy": 0.0862,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0228,
            "surprise": 0.1683,
            "affection": 0.1592
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799948100,
          "emotions": {
            "joy": 0.0769,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0209,
            "surprise": 0.1697,
            "affection": 0.1533
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799948400,
          "emotions": {
            "joy": 0.0686,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0192,
            "surprise": 0.1709,
            "affection": 0.148
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799948700,
          "emotions": {
            "joy": 0.0612,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0176,
            "surprise": 0.172,
            "affection": 0.1433
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799949000,
          "emotions": {
            "joy": 0.0546,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0162,
            "surprise": 0.1729,
            "affection": 0.1392
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799949300,
          "emotions": {
            "joy": 0.0487,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0148,
            "surprise": 0.1738,
            "affection": 0.1354
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799949600,
          "emotions": {
            "joy": 0.0434,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0136,
            "surprise": 0.1745,
            "affection": 0.1321
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799949900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.141,
            "sadness": 0.4289,
            "fear": 0.22,
            "surprise": 0.1466,
            "affection": 0.1319
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799950200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.1172,
            "sadness": 0.3904,
            "fear": 0.1988,
            "surprise": 0.1503,
            "affection": 0.1314
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799950500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.098,
            "sadness": 0.3544,
            "fear": 0.1801,
            "surprise": 0.1534,
            "affection": 0.1307
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799950800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0824,
            "sadness": 0.3209,
            "fear": 0.1634,
            "surprise": 0.156,
            "affection": 0.1301
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799951100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0697,
            "sadness": 0.2901,
            "fear": 0.1485,
            "surprise": 0.1582,
            "affection": 0.1294
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799951400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0593,
            "sadness": 0.2618,
            "fear": 0.1351,
            "surprise": 0.1601,
            "affection": 0.1286
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799951700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0506,
            "sadness": 0.2359,
            "fear": 0.1231,
            "surprise": 0.1618,
            "affection": 0.1278
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799952000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0434,
            "sadness": 0.2122,
            "fear": 0.1123,
            "surprise": 0.1634,
            "affection": 0.127
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799952300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0373,
            "sadness": 0.1908,
            "fear": 0.1025,
            "surprise": 0.1648,
            "affection": 0.1262
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799952600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0322,
            "sadness": 0.1713,
            "fear": 0.0936,
            "surprise": 0.1661,
            "affection": 0.1254
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799952900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0279,
            "sadness": 0.1537,
            "fear": 0.0856,
            "surprise": 0.1673,
            "affection": 0.1246
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799953200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0242,
            "sadness": 0.1378,
            "fear": 0.0782,
            "surprise": 0.1684,
            "affection": 0.1238
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799953500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.021,
            "sadness": 0.1235,
            "fear": 0.0716,
            "surprise": 0.1694,
            "affection": 0.123
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799953800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0183,
            "sadness": 0.1105,
            "fear": 0.0655,
            "surprise": 0.1703,
            "affection": 0.1223
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799954100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.016,
            "sadness": 0.0989,
            "fear": 0.06,
            "surprise": 0.1711,
            "affection": 0.1215
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799954400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.014,
            "sadness": 0.0885,
            "fear": 0.0549,
            "surprise": 0.1719,
            "affection": 0.1208
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799954700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0123,
            "sadness": 0.0791,
            "fear": 0.0503,
            "surprise": 0.1727,
            "affection": 0.1201
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799955000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0108,
            "sadness": 0.0707,
            "fear": 0.0461,
            "surprise": 0.1733,
            "affection": 0.1194
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799955300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0095,
            "sadness": 0.0632,
            "fear": 0.0422,
            "surprise": 0.1739,
            "affection": 0.1187
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799955600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0083,
            "sadness": 0.0565,
            "fear": 0.0387,
            "surprise": 0.1745,
            "affection": 0.1181
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799955900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0073,
            "sadness": 0.0504,
            "fear": 0.0355,
            "surprise": 0.175,
            "affection": 0.1175
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799956200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0065,
            "sadness": 0.045,
            "fear": 0.0325,
            "surprise": 0.1755,
            "affection": 0.1169
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799956500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0057,
            "sadness": 0.0402,
            "fear": 0.0298,
            "surprise": 0.1759,
            "affection": 0.1163
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799956800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.005,
            "sadness": 0.0359,
            "fear": 0.0273,
            "surprise": 0.1763,
            "affection": 0.1158
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799957100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0603,
            "sadness": 0.2172,
            "fear": 0.0,
            "surprise": 0.2711,
            "affection": 0.2041
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799957400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0498,
            "sadness": 0.1996,
            "fear": 0.0,
            "surprise": 0.2575,
            "affection": 0.1986
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799957700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0415,
            "sadness": 0.1824,
            "fear": 0.0,
            "surprise": 0.2456,
            "affection": 0.1933
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799958000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0347,
            "sadness": 0.166,
            "fear": 0.0,
            "surprise": 0.2353,
            "affection": 0.1884
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799958300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0293,
            "sadness": 0.1504,
            "fear": 0.0,
            "surprise": 0.2264,
            "affection": 0.1837
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799958600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0249,
            "sadness": 0.136,
            "fear": 0.0,
            "surprise": 0.2188,
            "affection": 0.1793
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799958900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0212,
            "sadness": 0.1226,
            "fear": 0.0,
            "surprise": 0.2123,
            "affection": 0.1751
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799959200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0182,
            "sadness": 0.1103,
            "fear": 0.0,
            "surprise": 0.2068,
            "affection": 0.1712
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799959500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0157,
            "sadness": 0.0991,
            "fear": 0.0,
            "surprise": 0.2021,
            "affection": 0.1674
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799959800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0136,
            "sadness": 0.0889,
            "fear": 0.0,
            "surprise": 0.1982,
            "affection": 0.1639
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799960100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0119,
            "sadness": 0.0796,
            "fear": 0.0,
            "surprise": 0.1949,
            "affection": 0.1606
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799960400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0103,
            "sadness": 0.0713,
            "fear": 0.0,
            "surprise": 0.1922,
            "affection": 0.1575
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799960700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.009,
            "sadness": 0.0638,
            "fear": 0.0,
            "surprise": 0.1899,
            "affection": 0.1546
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799961000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0079,
            "sadness": 0.057,
            "fear": 0.0,
            "surprise": 0.188,
            "affection": 0.1518
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799961300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.007,
            "sadness": 0.0509,
            "fear": 0.0,
            "surprise": 0.1864,
            "affection": 0.1492
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799961600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0062,
            "sadness": 0.0455,
            "fear": 0.0,
            "surprise": 0.1851,
            "affection": 0.1467
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799961900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0054,
            "sadness": 0.0406,
            "fear": 0.0,
            "surprise": 0.184,
            "affection": 0.1443
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799962200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0048,
            "sadness": 0.0362,
            "fear": 0.0,
            "surprise": 0.1832,
            "affection": 0.1421
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799962500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0042,
            "sadness": 0.0323,
            "fear": 0.0,
            "surprise": 0.1824,
            "affection": 0.14
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799962800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0038,
            "sadness": 0.0288,
            "fear": 0.0,
            "surprise": 0.1819,
            "affection": 0.1381
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799963100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0033,
            "sadness": 0.0257,
            "fear": 0.0,
            "surprise": 0.1814,
            "affection": 0.1362
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799963400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.003,
            "sadness": 0.0229,
            "fear": 0.0,
            "surprise": 0.181,
            "affection": 0.1345
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799963700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0026,
            "sadness": 0.0204,
            "fear": 0.0,
            "surprise": 0.1807,
            "affection": 0.1328
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799964000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0023,
            "sadness": 0.0182,
            "fear": 0.0,
            "surprise": 0.1805,
            "affection": 0.1313
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799964300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1501,
            "surprise": 0.4324,
            "affection": 0.2351
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799964600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1304,
            "surprise": 0.3923,
            "affection": 0.2288
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799964900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1139,
            "surprise": 0.3585,
            "affection": 0.2228
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799965200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1001,
            "surprise": 0.3301,
            "affection": 0.217
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799965500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0884,
            "surprise": 0.3062,
            "affection": 0.2114
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799965800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0785,
            "surprise": 0.2861,
            "affection": 0.2061
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799966100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.07,
            "surprise": 0.2692,
            "affection": 0.201
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799966400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0626,
            "surprise": 0.255,
            "affection": 0.1961
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799966700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0563,
            "surprise": 0.2431,
            "affection": 0.1914
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799967000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0507,
            "surprise": 0.2331,
            "affection": 0.1869
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799967300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0458,
            "surprise": 0.2246,
            "affection": 0.1826
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799967600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0414,
            "surprise": 0.2175,
            "affection": 0.1786
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799967900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0376,
            "surprise": 0.2116,
            "affection": 0.1747
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799968200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0341,
            "surprise": 0.2065,
            "affection": 0.171
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799968500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.031,
            "surprise": 0.2023,
            "affection": 0.1675
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799968800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0283,
            "surprise": 0.1988,
            "affection": 0.1642
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799969100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0258,
            "surprise": 0.1958,
            "affection": 0.161
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799969400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0235,
            "surprise": 0.1933,
            "affection": 0.158
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799969700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0215,
            "surprise": 0.1912,
            "affection": 0.1551
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799970000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0196,
            "surprise": 0.1894,
            "affection": 0.1524
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799970300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.018,
            "surprise": 0.1879,
            "affection": 0.1499
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799970600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0164,
            "surprise": 0.1866,
            "affection": 0.1474
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799970900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.015,
            "surprise": 0.1856,
            "affection": 0.1451
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799971200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0138,
            "surprise": 0.1847,
            "affection": 0.1429
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799971500,
          "emotions": {
            "joy": 0.2719,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1799,
            "surprise": 0.1059,
            "affection": 0.2626
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799971800,
          "emotions": {
            "joy": 0.2452,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1679,
            "surprise": 0.1153,
            "affection": 0.2472
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799972100,
          "emotions": {
            "joy": 0.2208,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1562,
            "surprise": 0.1235,
            "affection": 0.2331
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799972400,
          "emotions": {
            "joy": 0.1987,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.145,
            "surprise": 0.1307,
            "affection": 0.2203
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799972700,
          "emotions": {
            "joy": 0.1787,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1343,
            "surprise": 0.137,
            "affection": 0.2086
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799973000,
          "emotions": {
            "joy": 0.1605,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1242,
            "surprise": 0.1426,
            "affection": 0.198
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799973300,
          "emotions": {
            "joy": 0.1441,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1147,
            "surprise": 0.1474,
            "affection": 0.1884
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799973600,
          "emotions": {
            "joy": 0.1292,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.1058,
            "surprise": 0.1516,
            "affection": 0.1797
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799973900,
          "emotions": {
            "joy": 0.1158,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0975,
            "surprise": 0.1553,
            "affection": 0.1719
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799974200,
          "emotions": {
            "joy": 0.1038,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0898,
            "surprise": 0.1585,
            "affection": 0.1648
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799974500,
          "emotions": {
            "joy": 0.0929,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0826,
            "surprise": 0.1613,
            "affection": 0.1584
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799974800,
          "emotions": {
            "joy": 0.0832,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0759,
            "surprise": 0.1637,
            "affection": 0.1527
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799975100,
          "emotions": {
            "joy": 0.0744,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0698,
            "surprise": 0.1658,
            "affection": 0.1476
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799975400,
          "emotions": {
            "joy": 0.0666,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0641,
            "surprise": 0.1676,
            "affection": 0.143
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799975700,
          "emotions": {
            "joy": 0.0595,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0589,
            "surprise": 0.1692,
            "affection": 0.1389
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799976000,
          "emotions": {
            "joy": 0.0532,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0541,
            "surprise": 0.1706,
            "affection": 0.1352
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799976300,
          "emotions": {
            "joy": 0.0475,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0497,
            "surprise": 0.1718,
            "affection": 0.1319
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799976600,
          "emotions": {
            "joy": 0.0425,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0456,
            "surprise": 0.1728,
            "affection": 0.129
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799976900,
          "emotions": {
            "joy": 0.0379,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0419,
            "surprise": 0.1737,
            "affection": 0.1263
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799977200,
          "emotions": {
            "joy": 0.0339,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0384,
            "surprise": 0.1745,
            "affection": 0.124
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799977500,
          "emotions": {
            "joy": 0.0302,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0352,
            "surprise": 0.1752,
            "affection": 0.1219
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799977800,
          "emotions": {
            "joy": 0.027,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0323,
            "surprise": 0.1758,
            "affection": 0.12
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799978100,
          "emotions": {
            "joy": 0.0241,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0297,
            "surprise": 0.1763,
            "affection": 0.1183
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799978400,
          "emotions": {
            "joy": 0.0215,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0272,
            "surprise": 0.1768,
            "affection": 0.1168
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799978700,
          "emotions": {
            "joy": 0.6239,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1466,
            "affection": 0.5601
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799979000,
          "emotions": {
            "joy": 0.5558,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1503,
            "affection": 0.5131
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799979300,
          "emotions": {
            "joy": 0.4952,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1534,
            "affection": 0.471
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799979600,
          "emotions": {
            "joy": 0.4411,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.156,
            "affection": 0.4334
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799979900,
          "emotions": {
            "joy": 0.393,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1582,
            "affection": 0.3998
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799980200,
          "emotions": {
            "joy": 0.3501,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1601,
            "affection": 0.3697
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799980500,
          "emotions": {
            "joy": 0.3119,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1618,
            "affection": 0.3428
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799980800,
          "emotions": {
            "joy": 0.2779,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1634,
            "affection": 0.3187
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799981100,
          "emotions": {
            "joy": 0.2476,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1648,
            "affection": 0.2972
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799981400,
          "emotions": {
            "joy": 0.2206,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1661,
            "affection": 0.2778
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799981700,
          "emotions": {
            "joy": 0.1965,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1673,
            "affection": 0.2605
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799982000,
          "emotions": {
            "joy": 0.1751,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1684,
            "affection": 0.245
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799982300,
          "emotions": {
            "joy": 0.156,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1694,
            "affection": 0.2312
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799982600,
          "emotions": {
            "joy": 0.139,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1703,
            "affection": 0.2187
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799982900,
          "emotions": {
            "joy": 0.1238,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1711,
            "affection": 0.2075
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799983200,
          "emotions": {
            "joy": 0.1103,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1719,
            "affection": 0.1975
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799983500,
          "emotions": {
            "joy": 0.0983,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1727,
            "affection": 0.1885
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799983800,
          "emotions": {
            "joy": 0.0875,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1733,
            "affection": 0.1805
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799984100,
          "emotions": {
            "joy": 0.078,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1739,
            "affection": 0.1732
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799984400,
          "emotions": {
            "joy": 0.0695,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1745,
            "affection": 0.1667
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799984700,
          "emotions": {
            "joy": 0.0619,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.175,
            "affection": 0.1608
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799985000,
          "emotions": {
            "joy": 0.0551,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1755,
            "affection": 0.1556
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799985300,
          "emotions": {
            "joy": 0.0491,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1759,
            "affection": 0.1508
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799985600,
          "emotions": {
            "joy": 0.0438,
            "anger": 0.0,
            "sadness": 0.0,
            "fear": 0.0,
            "surprise": 0.1763,
            "affection": 0.1466
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799985900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.1617,
            "sadness": 0.4064,
            "fear": 0.1301,
            "surprise": 0.2108,
            "affection": 0.1891
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799986200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.1308,
            "sadness": 0.3757,
            "fear": 0.1149,
            "surprise": 0.2077,
            "affection": 0.1852
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799986500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.1067,
            "sadness": 0.3452,
            "fear": 0.102,
            "surprise": 0.2042,
            "affection": 0.1814
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799986800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0878,
            "sadness": 0.3155,
            "fear": 0.0909,
            "surprise": 0.2006,
            "affection": 0.1777
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799987100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0728,
            "sadness": 0.2872,
            "fear": 0.0813,
            "surprise": 0.1971,
            "affection": 0.1741
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799987400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0608,
            "sadness": 0.2606,
            "fear": 0.073,
            "surprise": 0.1939,
            "affection": 0.1707
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799987700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0511,
            "sadness": 0.2358,
            "fear": 0.0658,
            "surprise": 0.191,
            "affection": 0.1675
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799988000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0433,
            "sadness": 0.2129,
            "fear": 0.0594,
            "surprise": 0.1885,
            "affection": 0.1643
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799988300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0368,
            "sadness": 0.1918,
            "fear": 0.0538,
            "surprise": 0.1864,
            "affection": 0.1613
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799988600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0315,
            "sadness": 0.1725,
            "fear": 0.0487,
            "surprise": 0.1846,
            "affection": 0.1584
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799988900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0271,
            "sadness": 0.155,
            "fear": 0.0443,
            "surprise": 0.1831,
            "affection": 0.1557
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799989200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0234,
            "sadness": 0.139,
            "fear": 0.0403,
            "surprise": 0.1818,
            "affection": 0.1531
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799989500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0203,
            "sadness": 0.1246,
            "fear": 0.0367,
            "surprise": 0.1808,
            "affection": 0.1506
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799989800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0176,
            "sadness": 0.1116,
            "fear": 0.0334,
            "surprise": 0.18,
            "affection": 0.1482
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799990100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0154,
            "sadness": 0.0999,
            "fear": 0.0305,
            "surprise": 0.1794,
            "affection": 0.1459
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799990400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0134,
            "sadness": 0.0894,
            "fear": 0.0279,
            "surprise": 0.179,
            "affection": 0.1437
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799990700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0118,
            "sadness": 0.0799,
            "fear": 0.0255,
            "surprise": 0.1786,
            "affection": 0.1417
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799991000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0103,
            "sadness": 0.0714,
            "fear": 0.0233,
            "surprise": 0.1784,
            "affection": 0.1397
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799991300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0091,
            "sadness": 0.0638,
            "fear": 0.0213,
            "surprise": 0.1782,
            "affection": 0.1379
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799991600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.008,
            "sadness": 0.0569,
            "fear": 0.0195,
            "surprise": 0.1781,
            "affection": 0.1361
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799991900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0071,
            "sadness": 0.0508,
            "fear": 0.0178,
            "surprise": 0.1781,
            "affection": 0.1345
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799992200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0062,
            "sadness": 0.0454,
            "fear": 0.0163,
            "surprise": 0.1781,
            "affection": 0.1329
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799992500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0055,
            "sadness": 0.0405,
            "fear": 0.015,
            "surprise": 0.1781,
            "affection": 0.1314
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799992800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0049,
            "sadness": 0.0361,
            "fear": 0.0137,
            "surprise": 0.1781,
            "affection": 0.1299
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799993100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.1323,
            "sadness": 0.1641,
            "fear": 0.3003,
            "surprise": 0.3537,
            "affection": 0.2165
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799993400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.1033,
            "sadness": 0.157,
            "fear": 0.2607,
            "surprise": 0.3287,
            "affection": 0.2123
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799993700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0814,
            "sadness": 0.1483,
            "fear": 0.2278,
            "surprise": 0.3067,
            "affection": 0.2082
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799994000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0648,
            "sadness": 0.1386,
            "fear": 0.2002,
            "surprise": 0.2876,
            "affection": 0.204
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799994300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.052,
            "sadness": 0.1285,
            "fear": 0.1769,
            "surprise": 0.2711,
            "affection": 0.1999
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799994600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0421,
            "sadness": 0.1184,
            "fear": 0.157,
            "surprise": 0.2569,
            "affection": 0.1958
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799994900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0344,
            "sadness": 0.1085,
            "fear": 0.14,
            "surprise": 0.2447,
            "affection": 0.1918
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799995200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0284,
            "sadness": 0.099,
            "fear": 0.1253,
            "surprise": 0.2344,
            "affection": 0.1879
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799995500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0235,
            "sadness": 0.09,
            "fear": 0.1125,
            "surprise": 0.2255,
            "affection": 0.1841
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799995800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0197,
            "sadness": 0.0816,
            "fear": 0.1014,
            "surprise": 0.2181,
            "affection": 0.1804
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799996100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0166,
            "sadness": 0.0738,
            "fear": 0.0915,
            "surprise": 0.2117,
            "affection": 0.1768
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799996400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.014,
            "sadness": 0.0666,
            "fear": 0.0828,
            "surprise": 0.2064,
            "affection": 0.1734
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799996700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0119,
            "sadness": 0.06,
            "fear": 0.0751,
            "surprise": 0.2019,
            "affection": 0.17
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799997000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0102,
            "sadness": 0.054,
            "fear": 0.0682,
            "surprise": 0.1982,
            "affection": 0.1668
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799997300,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0088,
            "sadness": 0.0485,
            "fear": 0.0621,
            "surprise": 0.195,
            "affection": 0.1638
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799997600,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0076,
            "sadness": 0.0435,
            "fear": 0.0565,
            "surprise": 0.1924,
            "affection": 0.1608
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799997900,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0066,
            "sadness": 0.039,
            "fear": 0.0516,
            "surprise": 0.1902,
            "affection": 0.158
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799998200,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0057,
            "sadness": 0.035,
            "fear": 0.0471,
            "surprise": 0.1883,
            "affection": 0.1553
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799998500,
          "emotions": {
            "joy": 0.0,
            "anger": 0.005,
            "sadness": 0.0313,
            "fear": 0.043,
            "surprise": 0.1868,
            "affection": 0.1527
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799998800,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0043,
            "sadness": 0.028,
            "fear": 0.0393,
            "surprise": 0.1855,
            "affection": 0.1502
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799999100,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0038,
            "sadness": 0.025,
            "fear": 0.0359,
            "surprise": 0.1845,
            "affection": 0.1479
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799999400,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0033,
            "sadness": 0.0224,
            "fear": 0.0328,
            "surprise": 0.1836,
            "affection": 0.1457
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1799999700,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0029,
            "sadness": 0.02,
            "fear": 0.0301,
            "surprise": 0.1829,
            "affection": 0.1435
          },
          "basis": "recorded_decay"
        },
        {
          "at": 1800000000,
          "emotions": {
            "joy": 0.0,
            "anger": 0.0026,
            "sadness": 0.0179,
            "fear": 0.0275,
            "surprise": 0.1823,
            "affection": 0.1415
          },
          "basis": "recorded_decay"
        }
      ],
      "interval_seconds": 300,
      "window_start": 1799913601.0,
      "window_end": 1800000001.0,
      "timezone": "Asia/Shanghai",
      "basis": "recorded_state_decay_with_daily_weather",
      "collected": true
    }
  },
  "options": {
    "api_version": 1,
    "personas": [
      {
        "value": "fixture-persona",
        "label": "真实 DTO · 合成人格"
      }
    ],
    "chat_providers": [
      {
        "value": "fixture-chat",
        "label": "合成聊天模型"
      }
    ],
    "embedding_providers": [
      {
        "value": "fixture-embedding",
        "label": "合成向量模型"
      }
    ],
    "groups": [
      {
        "id": "quick_start",
        "label": "快速开始",
        "field_keys": [
          "enabled",
          "mode",
          "timezone",
          "provider_id",
          "fallback_provider_id",
          "home_city"
        ]
      },
      {
        "id": "persona",
        "label": "人格与状态模式",
        "field_keys": [
          "persona_mode",
          "persona_id",
          "persona_shared_state"
        ]
      },
      {
        "id": "emotion",
        "label": "情绪",
        "field_keys": [
          "emotion_model_enabled",
          "scheduler_seconds",
          "model_concurrency",
          "queue_size",
          "model_daily_limit",
          "emotion_interval_seconds",
          "emotion_quiet_start_hour",
          "emotion_quiet_end_hour",
          "emotion_intensity",
          "model_input_tokens",
          "model_output_tokens",
          "model_timeout_seconds"
        ]
      },
      {
        "id": "relationship",
        "label": "关系",
        "field_keys": [
          "relationship_stage_names",
          "relationship_stage_descriptions",
          "relationship_special_description",
          "relationship_edit_enabled"
        ]
      },
      {
        "id": "behavior",
        "label": "主动行为",
        "field_keys": [
          "autonomy_enabled",
          "group_autonomy_enabled",
          "autonomy_qq_ids",
          "autonomy_qq_group_ids",
          "muted_scopes",
          "dnd_start",
          "dnd_end",
          "active_start",
          "active_end",
          "behavior_daily_limit",
          "behavior_scope_daily_limit",
          "behavior_cooldown_seconds",
          "behavior_unanswered_limit",
          "behavior_random_min_minutes",
          "behavior_random_max_minutes",
          "behavior_idle_minutes",
          "behavior_style",
          "behavior_emotional_share",
          "behavior_provider_id"
        ]
      },
      {
        "id": "night",
        "label": "长夜",
        "field_keys": [
          "night_schedule_enabled",
          "wake_at",
          "allow_sleep",
          "nap_enabled",
          "nap_start",
          "nap_end",
          "fatigue_start",
          "fatigue_end",
          "deep_sleep_at",
          "lie_in_min_minutes",
          "lie_in_max_minutes",
          "wake_mode",
          "wake_reply_limit",
          "wake_window_minutes",
          "energy_reply_cost",
          "energy_fatigue_per_minute",
          "energy_recovery_per_minute",
          "catchup_enabled",
          "catchup_reply_enabled",
          "closing_enabled",
          "closing_random",
          "closing_lead_minutes",
          "catchup_provider_id",
          "closing_provider_id",
          "wake_autocatchup_enabled",
          "wake_greeting_enabled",
          "wake_greeting_texts"
        ]
      },
      {
        "id": "experience",
        "label": "日记与梦境",
        "field_keys": [
          "dream_enabled",
          "dream_theme_pool",
          "dream_owner_notify",
          "dream_owner_qq",
          "diary_enabled",
          "diary_at",
          "diary_backfill_yesterday",
          "diary_retries",
          "dream_per_night",
          "diary_retention_days",
          "dream_retention_days",
          "dream_half_life_seconds",
          "experience_body_chars",
          "diary_provider_id",
          "dream_provider_id",
          "home_city"
        ]
      },
      {
        "id": "memory",
        "label": "记忆",
        "field_keys": [
          "memory_read",
          "window_days",
          "window_per_scope",
          "window_global",
          "body_max_chars",
          "event_days",
          "embedding_provider_id",
          "livingmemory_enabled",
          "memory_write"
        ]
      }
    ],
    "reasons": [
      "get_all_personas_unavailable",
      "get_all_providers_unavailable",
      "get_all_embedding_providers_unavailable"
    ]
  },
  "scopes": {
    "api_version": 1,
    "selection": {
      "persona_id": "",
      "view_scope": "global",
      "context_id": "",
      "platform": ""
    },
    "personas": [],
    "platforms": [
      "bilibili",
      "qq"
    ],
    "contexts": [
      {
        "id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10022",
        "label": "qq / synthetic-chat / 10022",
        "nickname": ""
      },
      {
        "id": "fa26f35ec2546c181ee72799f01b5aae504e5c4033b7b202d9abecf62d5f11ab",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10008",
        "label": "qq / synthetic-chat / 10008",
        "nickname": ""
      },
      {
        "id": "dfb32f3bfc4be410769366615ff06d2c19e98932e1931081a830bb8ab15e1e79",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10003",
        "label": "qq / synthetic-chat / 10003",
        "nickname": ""
      },
      {
        "id": "de24a467cea45b055f7f8def9fc56b4070e20ef6e76c9e97078bb1c6293ce863",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10005",
        "label": "qq / synthetic-chat / 10005",
        "nickname": ""
      },
      {
        "id": "c639f0787f3e721670ce91c66ea83ae1f3643d241cf98a647895d77ed430d573",
        "scope_key": "fe330394d0b89a8abe88cfff5e0fc6a1154a3d274cb4efde352a7b88afb1b4ae",
        "persona_id": "fixture-persona",
        "platform": "bilibili",
        "view_scope": "group",
        "scene_id": "synthetic-group",
        "account_id": "10001",
        "label": "bilibili / synthetic-group / 10001",
        "nickname": ""
      },
      {
        "id": "b6523e02ceff69b99ebe35a09d40dfcf4c6eaf0456ff317bfdffa7c4250efbd0",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10004",
        "label": "qq / synthetic-chat / 10004",
        "nickname": ""
      },
      {
        "id": "b2843aaa258a1b53a0f8db7536d25dfa3b1e750fcc890b11c5c655c446a38226",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10010",
        "label": "qq / synthetic-chat / 10010",
        "nickname": ""
      },
      {
        "id": "af4c64efe2bd84af88a5b125e64520e83d16c8bb664e2c9544f66edd5c0eca8c",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10001",
        "label": "qq / synthetic-chat / 10001",
        "nickname": "小雨（合成QQ名字）"
      },
      {
        "id": "ac17a10a834bbd6546d9df4799a3fbf4180e0f0eb2330a229a24c5d17b6f87cd",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10012",
        "label": "qq / synthetic-chat / 10012",
        "nickname": ""
      },
      {
        "id": "aa3c7b08efef0610f928e202a72bc946347131b4dd10858badb9498c48f82f74",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10016",
        "label": "qq / synthetic-chat / 10016",
        "nickname": ""
      },
      {
        "id": "99e913771ab562575d758281889a84d5a651e9ed85199a933b1d36905ba60a43",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10015",
        "label": "qq / synthetic-chat / 10015",
        "nickname": ""
      },
      {
        "id": "8bea336f974443c4c11057900f7ed8652adc31754428a84ee4b83b85b2fe44e1",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10011",
        "label": "qq / synthetic-chat / 10011",
        "nickname": ""
      },
      {
        "id": "83f40e4790ac1906f7588f8b52e5b9e5c0db9368fc7d3b32aa2d9b392edd00ab",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10007",
        "label": "qq / synthetic-chat / 10007",
        "nickname": ""
      },
      {
        "id": "6ed68c6b686c9951261dc5de9738b25019ab809bc0e703c1c626a17f14c6ad81",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10018",
        "label": "qq / synthetic-chat / 10018",
        "nickname": ""
      },
      {
        "id": "6ec240f3ccf36a9e65f0f924da49e2b7f133782a030fc05cee5fd45c70f557d2",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10009",
        "label": "qq / synthetic-chat / 10009",
        "nickname": ""
      },
      {
        "id": "6a31c17069f1faa088d70f67b863369c79c828ac93d8dc45f53e943b0d1faa20",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10019",
        "label": "qq / synthetic-chat / 10019",
        "nickname": ""
      },
      {
        "id": "5887c46fe09940abadf7caa6cf01d5725f4de752431821268b675be39984d3c5",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10013",
        "label": "qq / synthetic-chat / 10013",
        "nickname": ""
      },
      {
        "id": "54c518ff3fbeb5e9479c2941bd9b2f274fc8495e7acd1c60253fb9f315bdac71",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10002",
        "label": "qq / synthetic-chat / 10002",
        "nickname": ""
      },
      {
        "id": "52e7028ab96e6d15771e356ec0cc141e9924f6d9c807f92056fabd22000acc42",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10006",
        "label": "qq / synthetic-chat / 10006",
        "nickname": ""
      },
      {
        "id": "51511c831a5c7e9483c8524dd0d21c9cd5704388bbde5977b68c0b84b2c6e7d6",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10014",
        "label": "qq / synthetic-chat / 10014",
        "nickname": ""
      },
      {
        "id": "3541c3e1eb5a73c2e9c3cff4062576aa8741454589a14ccac2b743235a818bed",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10017",
        "label": "qq / synthetic-chat / 10017",
        "nickname": ""
      },
      {
        "id": "20e34e626946676301e279dd297c66c688b26bf3862adb3ff1457474292c8be5",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10021",
        "label": "qq / synthetic-chat / 10021",
        "nickname": ""
      },
      {
        "id": "1ef1a91376e7269b4f41b29e3d2b8a50f54ce42f81bc7343bb04b473e71a4baf",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10023",
        "label": "qq / synthetic-chat / 10023",
        "nickname": ""
      },
      {
        "id": "1ccd90c62355721865cacd5c9ecdb7d9c6e45962cde9fa9b49c085cdbbec2515",
        "scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10020",
        "label": "qq / synthetic-chat / 10020",
        "nickname": ""
      }
    ],
    "counts": {
      "global": 24,
      "private": 23,
      "group": 1
    }
  },
  "relationships": {
    "api_version": 1,
    "selection": {
      "persona_id": "fixture-persona",
      "view_scope": "global",
      "context_id": "",
      "platform": ""
    },
    "center": {
      "id": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
      "persona_id": "fixture-persona"
    },
    "nodes": [
      {
        "id": "e4e8210c93560d74ba4764249ff98e919057ac0c7f6433abeeb2f5812fe0eaf7",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10021",
        "label": "10021",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "20e34e626946676301e279dd297c66c688b26bf3862adb3ff1457474292c8be5",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "d82928066adf44e994afc87f23c44aac26505a2127b70ddc0f9fef2b48c084f8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10019",
        "label": "10019",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "6a31c17069f1faa088d70f67b863369c79c828ac93d8dc45f53e943b0d1faa20",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "d5a0f7879fcd72d70c0e1468624c11f0c5b2d4b2de7f19816e7a09e5ce7636bf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10007",
        "label": "10007",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "83f40e4790ac1906f7588f8b52e5b9e5c0db9368fc7d3b32aa2d9b392edd00ab",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "c867fc2832983b115f4466680aa31ae1d6c9f4361f64f285c0ab0734fe072d9d",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10001",
        "label": "小雨（合成QQ名字）",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "af4c64efe2bd84af88a5b125e64520e83d16c8bb664e2c9544f66edd5c0eca8c",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "c00054d0505e5bcd7f5d1f655b60e5ab3e59dab0be8a0cd0f690cbafd6fd1dbc",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10005",
        "label": "10005",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "de24a467cea45b055f7f8def9fc56b4070e20ef6e76c9e97078bb1c6293ce863",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "bec7993aacc968bbe925eee176827eeedbed2876f091d566e8cc406d6af09185",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10020",
        "label": "10020",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "1ccd90c62355721865cacd5c9ecdb7d9c6e45962cde9fa9b49c085cdbbec2515",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "b8fddea1e66bd4401e8ff37025e1ce607c2d7d6db8a8bbc68b6d0bcbc6158ff8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10017",
        "label": "10017",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "3541c3e1eb5a73c2e9c3cff4062576aa8741454589a14ccac2b743235a818bed",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "b69fb57d322b06bac925a50b981d3efecc5a868dae60958329193aed4baafe82",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10008",
        "label": "10008",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "fa26f35ec2546c181ee72799f01b5aae504e5c4033b7b202d9abecf62d5f11ab",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "adb022534ea72423c94d283a6d29240db1b4c6e0643dd02015d375b7f409d71f",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10010",
        "label": "10010",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "b2843aaa258a1b53a0f8db7536d25dfa3b1e750fcc890b11c5c655c446a38226",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "a231321ba9499da2d50011ab63fee305af89f7e69b41954567e7c9bc91d92fcb",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10014",
        "label": "10014",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "51511c831a5c7e9483c8524dd0d21c9cd5704388bbde5977b68c0b84b2c6e7d6",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "9fd41a29af14350c6be368260de8e77cf57d3089bb7c63ee4a0d2dac9a463cfb",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10003",
        "label": "10003",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "dfb32f3bfc4be410769366615ff06d2c19e98932e1931081a830bb8ab15e1e79",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "9d8e435e4a5b0b14d1ea055e0664a4dc0e45c69910c249721ba76528dd8dbbab",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10023",
        "label": "10023",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "1ef1a91376e7269b4f41b29e3d2b8a50f54ce42f81bc7343bb04b473e71a4baf",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "903ea42ec60700f6a58d4c8ceb7b18036c47b7cb8082ab4ac6346c3ee0f84b57",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10009",
        "label": "10009",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "6ec240f3ccf36a9e65f0f924da49e2b7f133782a030fc05cee5fd45c70f557d2",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "8b66532908389711e30d79b3917511c025d649e0226170c95b6ebc9329086a90",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10002",
        "label": "10002",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "54c518ff3fbeb5e9479c2941bd9b2f274fc8495e7acd1c60253fb9f315bdac71",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "606fad4bc097427cc13515300c5bfe7e8f28273ee2e6b689723cfe96155f90ed",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10011",
        "label": "10011",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "8bea336f974443c4c11057900f7ed8652adc31754428a84ee4b83b85b2fe44e1",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "599993818a971672d92766010112f13a45ebe0324a5a8a0f8a9dabc9411f2532",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10022",
        "label": "10022",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "5483bfd2e703f07d69c023c70e9f3f084a9ea4332c18e4d985b74b576521ccb2",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10006",
        "label": "10006",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "52e7028ab96e6d15771e356ec0cc141e9924f6d9c807f92056fabd22000acc42",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "4813dfbe51ca3b2705f0d65b997dc2b4bc5082a069b9dfd4f433eeae2f4c0469",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10012",
        "label": "10012",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "ac17a10a834bbd6546d9df4799a3fbf4180e0f0eb2330a229a24c5d17b6f87cd",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "45769e01aa2b5ed4b35af7fd17f1a2cae7377e8f3e593a43a9a60659a9b89a9d",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10018",
        "label": "10018",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "6ed68c6b686c9951261dc5de9738b25019ab809bc0e703c1c626a17f14c6ad81",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "3315db5a2de4e83356d84a8441a56b9f37d61842ec2b478bfa664ef772bcdfaf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10013",
        "label": "10013",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "5887c46fe09940abadf7caa6cf01d5725f4de752431821268b675be39984d3c5",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "28e2b592ea4239630563d20fbca7273893a9587280d48d68bd0d494068257679",
        "persona_id": "fixture-persona",
        "platform": "bilibili",
        "account_id": "10001",
        "label": "10001",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "c639f0787f3e721670ce91c66ea83ae1f3643d241cf98a647895d77ed430d573",
            "platform": "bilibili",
            "view_scope": "group",
            "scene_id": "synthetic-group"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "1afebc4e70572f630907d8324723db71ce06c82d70524f2297cce5250b197952",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10016",
        "label": "10016",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "aa3c7b08efef0610f928e202a72bc946347131b4dd10858badb9498c48f82f74",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "0799dec7c092fc60a037a69973bf862a443aed80c6ce1f0b5f6837e45506ee70",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10004",
        "label": "10004",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "b6523e02ceff69b99ebe35a09d40dfcf4c6eaf0456ff317bfdffa7c4250efbd0",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "026d65db6260001564b8163edc0bedc05677d499333bd717d7ac6004f1521a3c",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10015",
        "label": "10015",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "99e913771ab562575d758281889a84d5a651e9ed85199a933b1d36905ba60a43",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      }
    ],
    "edges": [
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "e4e8210c93560d74ba4764249ff98e919057ac0c7f6433abeeb2f5812fe0eaf7",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "d82928066adf44e994afc87f23c44aac26505a2127b70ddc0f9fef2b48c084f8",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "d5a0f7879fcd72d70c0e1468624c11f0c5b2d4b2de7f19816e7a09e5ce7636bf",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "c867fc2832983b115f4466680aa31ae1d6c9f4361f64f285c0ab0734fe072d9d",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "c00054d0505e5bcd7f5d1f655b60e5ab3e59dab0be8a0cd0f690cbafd6fd1dbc",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "bec7993aacc968bbe925eee176827eeedbed2876f091d566e8cc406d6af09185",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "b8fddea1e66bd4401e8ff37025e1ce607c2d7d6db8a8bbc68b6d0bcbc6158ff8",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "b69fb57d322b06bac925a50b981d3efecc5a868dae60958329193aed4baafe82",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "adb022534ea72423c94d283a6d29240db1b4c6e0643dd02015d375b7f409d71f",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "a231321ba9499da2d50011ab63fee305af89f7e69b41954567e7c9bc91d92fcb",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "9fd41a29af14350c6be368260de8e77cf57d3089bb7c63ee4a0d2dac9a463cfb",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "9d8e435e4a5b0b14d1ea055e0664a4dc0e45c69910c249721ba76528dd8dbbab",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "903ea42ec60700f6a58d4c8ceb7b18036c47b7cb8082ab4ac6346c3ee0f84b57",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "8b66532908389711e30d79b3917511c025d649e0226170c95b6ebc9329086a90",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "606fad4bc097427cc13515300c5bfe7e8f28273ee2e6b689723cfe96155f90ed",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "599993818a971672d92766010112f13a45ebe0324a5a8a0f8a9dabc9411f2532",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "5483bfd2e703f07d69c023c70e9f3f084a9ea4332c18e4d985b74b576521ccb2",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "4813dfbe51ca3b2705f0d65b997dc2b4bc5082a069b9dfd4f433eeae2f4c0469",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "45769e01aa2b5ed4b35af7fd17f1a2cae7377e8f3e593a43a9a60659a9b89a9d",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "3315db5a2de4e83356d84a8441a56b9f37d61842ec2b478bfa664ef772bcdfaf",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "28e2b592ea4239630563d20fbca7273893a9587280d48d68bd0d494068257679",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "1afebc4e70572f630907d8324723db71ce06c82d70524f2297cce5250b197952",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "0799dec7c092fc60a037a69973bf862a443aed80c6ce1f0b5f6837e45506ee70",
        "score": 20.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "026d65db6260001564b8163edc0bedc05677d499333bd717d7ac6004f1521a3c",
        "score": 20.0
      }
    ],
    "items": [
      {
        "id": "e4e8210c93560d74ba4764249ff98e919057ac0c7f6433abeeb2f5812fe0eaf7",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10021",
        "label": "10021",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "20e34e626946676301e279dd297c66c688b26bf3862adb3ff1457474292c8be5",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "d82928066adf44e994afc87f23c44aac26505a2127b70ddc0f9fef2b48c084f8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10019",
        "label": "10019",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "6a31c17069f1faa088d70f67b863369c79c828ac93d8dc45f53e943b0d1faa20",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "d5a0f7879fcd72d70c0e1468624c11f0c5b2d4b2de7f19816e7a09e5ce7636bf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10007",
        "label": "10007",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "83f40e4790ac1906f7588f8b52e5b9e5c0db9368fc7d3b32aa2d9b392edd00ab",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "c867fc2832983b115f4466680aa31ae1d6c9f4361f64f285c0ab0734fe072d9d",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10001",
        "label": "小雨（合成QQ名字）",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "af4c64efe2bd84af88a5b125e64520e83d16c8bb664e2c9544f66edd5c0eca8c",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "c00054d0505e5bcd7f5d1f655b60e5ab3e59dab0be8a0cd0f690cbafd6fd1dbc",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10005",
        "label": "10005",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "de24a467cea45b055f7f8def9fc56b4070e20ef6e76c9e97078bb1c6293ce863",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "bec7993aacc968bbe925eee176827eeedbed2876f091d566e8cc406d6af09185",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10020",
        "label": "10020",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "1ccd90c62355721865cacd5c9ecdb7d9c6e45962cde9fa9b49c085cdbbec2515",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "b8fddea1e66bd4401e8ff37025e1ce607c2d7d6db8a8bbc68b6d0bcbc6158ff8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10017",
        "label": "10017",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "3541c3e1eb5a73c2e9c3cff4062576aa8741454589a14ccac2b743235a818bed",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "b69fb57d322b06bac925a50b981d3efecc5a868dae60958329193aed4baafe82",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10008",
        "label": "10008",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "fa26f35ec2546c181ee72799f01b5aae504e5c4033b7b202d9abecf62d5f11ab",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "adb022534ea72423c94d283a6d29240db1b4c6e0643dd02015d375b7f409d71f",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10010",
        "label": "10010",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "b2843aaa258a1b53a0f8db7536d25dfa3b1e750fcc890b11c5c655c446a38226",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      },
      {
        "id": "a231321ba9499da2d50011ab63fee305af89f7e69b41954567e7c9bc91d92fcb",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10014",
        "label": "10014",
        "raw": 200.0,
        "score": 20.0,
        "normalized": 0.2,
        "stage": "stage_1",
        "stage_key": "stage_1",
        "stage_index": 1,
        "stage_name": "陌生",
        "stage_type": "陌生",
        "trust": null,
        "familiarity": null,
        "boundary": null,
        "frozen": false,
        "source_completeness": "partial",
        "sources": [
          {
            "context_id": "51511c831a5c7e9483c8524dd0d21c9cd5704388bbde5977b68c0b84b2c6e7d6",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat"
          }
        ],
        "version": 0,
        "updated_at": 0.0,
        "note": ""
      }
    ],
    "total": 24,
    "displayed": 24,
    "page": 1,
    "page_size": 10,
    "graph_scope": "matched",
    "focus_ids": [],
    "graph_total": 24,
    "graph_truncated": false,
    "peer_edges": [
      {
        "id": "00733abfc39a938702b7b5cc4ebf416d537541ac939c2203a9fa0e9288549550",
        "source": "8b66532908389711e30d79b3917511c025d649e0226170c95b6ebc9329086a90",
        "target": "c867fc2832983b115f4466680aa31ae1d6c9f4361f64f285c0ab0734fe072d9d",
        "relation": "朋友",
        "inferred": true,
        "evidence": [
          {
            "source_id": "synthetic-relationship-source",
            "kind": "聊天记录",
            "at": 1800000000.0,
            "context_id": "af4c64efe2bd84af88a5b125e64520e83d16c8bb664e2c9544f66edd5c0eca8c",
            "platform": "qq",
            "view_scope": "private",
            "scene_id": "synthetic-chat",
            "basis": "本人陈述",
            "excerpt": "我和@10002是朋友"
          }
        ]
      }
    ]
  },
  "energy": {
    "api_version": 1,
    "selection": {
      "persona_id": "fixture-persona",
      "view_scope": "global",
      "context_id": "",
      "platform": ""
    },
    "window_start": 1799913601.0,
    "window_end": 1800000001.0,
    "timezone": "Asia/Shanghai",
    "collected": true,
    "reason": "",
    "points": [
      {
        "at": 1800000001.0,
        "energy": 100.0,
        "min": 100.0,
        "max": 100.0,
        "first": 100.0,
        "owner_key": "f46deaba14cb340e679bac3c43c83885d1a535adc90ed641c9330f05d24d8507"
      }
    ],
    "items": [
      {
        "seq": 1,
        "event_id": "27c2b934ebe23bfcc858658d84f256eb8524cdfdeef1a5c2ec6751fce1f9665d",
        "occurred_at": 1800000001.0,
        "owner_key": "f46deaba14cb340e679bac3c43c83885d1a535adc90ed641c9330f05d24d8507",
        "source_scope_key": "c6f0b1435481c305a05da3e29ed5eec7084236a631641dcb2de81913a58683d6",
        "source_id": "",
        "category": "config",
        "before_units": 1000,
        "after_units": 1000,
        "delta_units": 0,
        "before_state": "awake",
        "after_state": "awake",
        "reason_code": "state_mode",
        "before": 100.0,
        "after": 100.0,
        "delta": 0.0,
        "id": "27c2b934ebe23bfcc858658d84f256eb8524cdfdeef1a5c2ec6751fce1f9665d",
        "at": 1800000001.0,
        "kind": "config",
        "before_energy": 100.0,
        "after_energy": 100.0,
        "reason": "state_mode"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10,
    "series_total": 1,
    "points_truncated": false
  }
};
export const nativeDTOEvidence = {
  "captured_at": "2026-11-12T14:01:31.871346+00:00",
  "field_count": 95,
  "scope": "real Console DTO / synthetic host / temporary database",
  "sources_sha256": {
    "config.py": "eac5dcb07b7c593194c2a27003e313cc17ea34afdbd50c17e3e5c5dee946d52a",
    "contracts.py": "5a7dc9148951b8eae2814c44734c2e24091cb80f894a5abcd76780d13ffc9535",
    "runtime/console.py": "93c97bd9c3ac12450c6faf0c54faaf262a6fc063f265602492787701f5e4be81",
    "runtime/config_help.py": "e2a56b87c9d2c3788555cedb2cb99fb830c66d60aaa4cd828359e424d8bd3800",
    "storage/schema.py": "4f539b52a668d1cfc40b8e7df3a549d6de6c0399458153be0bc3762a4d93bb17",
    "storage/sqlite.py": "0a98b16c9065dbe8bb491982cd896e106867f6def083d9023330e28c333a2199",
    "storage/state_scope.py": "5810f7f4209e23b3395ecdb65a384f4d4c4fb4f4d98bd01faecf7b7ac0a14a1f",
    "storage/console_data.py": "8abde8a6dc52e94c7d03f28041981672588798b5f65e4736577b6d51fba0ad01",
    "domain/relationship_inference.py": "73f329394e7094180b7824a0d329826bc7cda3a524c4f5f64a839284b5ec01e9",
    "domain/proactivity.py": "e300cdb9e4130f1312060a9a6865ecaa8bfd9ec6fc7fc51c1c7701e36dcde326",
    "storage/proactivity.py": "003859c71234f93c8a004363de459ccc0471e0b81e10023c4e6530d91ec13e54"
  }
};
