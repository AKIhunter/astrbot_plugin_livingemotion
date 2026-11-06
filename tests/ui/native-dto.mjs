// Generated from real Console; synthetic host, no model or sends.
export const nativeDTO = {
  "config": {
    "revision": "config-1",
    "source": "AstrBot native plugin configuration",
    "values": {
      "enabled": true,
      "mode": "observe_only",
      "memory_mode": "none",
      "memory_read": false,
      "memory_export": false,
      "autonomy_enabled": false,
      "group_autonomy_enabled": false,
      "emotion_model_enabled": false,
      "dream_enabled": false,
      "diary_enabled": false,
      "night_enabled": true,
      "night_block_chat": false,
      "persona_mode": "follow",
      "persona_id": "",
      "timezone": "Asia/Shanghai",
      "provider_id": "",
      "fallback_provider_id": "",
      "autonomy_scopes": "",
      "muted_scopes": "",
      "night_schedule_enabled": false,
      "sleep_at": "01:00",
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
      "diary_retries": 2,
      "dream_per_night": 2,
      "diary_retention_days": 30,
      "dream_retention_days": 7,
      "dream_half_life_seconds": 86400,
      "experience_body_chars": 2000,
      "model_concurrency": 1,
      "queue_size": 100,
      "model_daily_limit": 48,
      "emotion_interval_seconds": 300,
      "model_input_tokens": 4096,
      "model_output_tokens": 1024,
      "model_timeout_seconds": 30,
      "window_days": 7,
      "window_per_scope": 200,
      "window_global": 10000,
      "body_max_chars": 8000,
      "event_days": 30,
      "persona_shared_state": true,
      "night_policy_version": 2,
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
      "memory_write": false
    },
    "fields": [
      {
        "key": "enabled",
        "label": "启用插件",
        "section": "quick_start",
        "value": true,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "mode",
        "label": "运行模式",
        "section": "quick_start",
        "value": "observe_only",
        "type": "enum",
        "advanced": false,
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
        "key": "memory_mode",
        "label": "旧版记忆模式",
        "section": "memory",
        "value": "none",
        "type": "enum",
        "advanced": true,
        "options": [
          {
            "value": "none",
            "label": "不使用"
          },
          {
            "value": "local_lite",
            "label": "旧版本地记录"
          },
          {
            "value": "external",
            "label": "外部记忆"
          }
        ]
      },
      {
        "key": "memory_read",
        "label": "允许读取记忆",
        "section": "memory",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "memory_export",
        "label": "允许导出记忆",
        "section": "memory",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "autonomy_enabled",
        "label": "允许主动找人",
        "section": "behavior",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "group_autonomy_enabled",
        "label": "允许群聊主动行为",
        "section": "behavior",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "emotion_model_enabled",
        "label": "模型辅助情绪分析",
        "section": "emotion",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "dream_enabled",
        "label": "生成梦境",
        "section": "experience",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "diary_enabled",
        "label": "生成日记",
        "section": "experience",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "night_enabled",
        "label": "启用作息记录",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "night_block_chat",
        "label": "旧版睡眠阻断聊天",
        "section": "night",
        "value": false,
        "type": "boolean",
        "advanced": true
      },
      {
        "key": "persona_mode",
        "label": "人格选择方式",
        "section": "persona",
        "value": "follow",
        "type": "enum",
        "advanced": false,
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
        "advanced": false
      },
      {
        "key": "provider_id",
        "label": "默认生成模型",
        "section": "quick_start",
        "value": "",
        "type": "enum",
        "advanced": false,
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
        "key": "autonomy_scopes",
        "label": "主动行为范围",
        "section": "behavior",
        "value": "",
        "type": "string",
        "advanced": false
      },
      {
        "key": "muted_scopes",
        "label": "静默范围",
        "section": "behavior",
        "value": "",
        "type": "string",
        "advanced": false
      },
      {
        "key": "night_schedule_enabled",
        "label": "自动作息",
        "section": "night",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "sleep_at",
        "label": "旧版入睡时间",
        "section": "night",
        "value": "01:00",
        "type": "string",
        "advanced": true
      },
      {
        "key": "wake_at",
        "label": "基础起床时间",
        "section": "night",
        "value": "08:00",
        "type": "string",
        "advanced": false
      },
      {
        "key": "diary_at",
        "label": "日记生成时间",
        "section": "experience",
        "value": "23:00",
        "type": "string",
        "advanced": false
      },
      {
        "key": "diary_backfill_yesterday",
        "label": "补写昨天日记",
        "section": "experience",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "scheduler_seconds",
        "label": "调度间隔",
        "section": "emotion",
        "value": 60,
        "type": "integer",
        "advanced": true,
        "step": 1,
        "unit": "秒"
      },
      {
        "key": "dnd_start",
        "label": "免打扰开始",
        "section": "behavior",
        "value": "01:00",
        "type": "string",
        "advanced": false
      },
      {
        "key": "dnd_end",
        "label": "免打扰结束",
        "section": "behavior",
        "value": "08:00",
        "type": "string",
        "advanced": false
      },
      {
        "key": "active_start",
        "label": "主动时段开始",
        "section": "behavior",
        "value": "00:00",
        "type": "string",
        "advanced": false
      },
      {
        "key": "active_end",
        "label": "主动时段结束",
        "section": "behavior",
        "value": "23:59",
        "type": "string",
        "advanced": false
      },
      {
        "key": "behavior_daily_limit",
        "label": "每日主动行为总额度",
        "section": "behavior",
        "value": 6,
        "type": "integer",
        "advanced": false,
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
        "step": 1,
        "unit": "次"
      },
      {
        "key": "diary_retries",
        "label": "日记重试次数",
        "section": "experience",
        "value": 2,
        "type": "integer",
        "advanced": false,
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
        "step": 1,
        "unit": "次"
      },
      {
        "key": "emotion_interval_seconds",
        "label": "情绪分析间隔",
        "section": "emotion",
        "value": 300,
        "type": "integer",
        "advanced": false,
        "step": 1,
        "unit": "秒"
      },
      {
        "key": "model_input_tokens",
        "label": "模型输入上限",
        "section": "emotion",
        "value": 4096,
        "type": "integer",
        "advanced": true,
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
        "step": 1,
        "unit": "天"
      },
      {
        "key": "persona_shared_state",
        "label": "同一人格共享状态",
        "section": "persona",
        "value": true,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "night_policy_version",
        "label": "睡眠规则版本",
        "section": "night",
        "value": 2,
        "type": "integer",
        "advanced": true,
        "step": 1,
        "unit": "次"
      },
      {
        "key": "allow_sleep",
        "label": "允许TA睡眠",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "nap_enabled",
        "label": "启用午休",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "nap_start",
        "label": "午休开始",
        "section": "night",
        "value": "13:00",
        "type": "string",
        "advanced": false
      },
      {
        "key": "nap_end",
        "label": "午休结束",
        "section": "night",
        "value": "14:30",
        "type": "string",
        "advanced": false
      },
      {
        "key": "fatigue_start",
        "label": "夜间疲劳开始",
        "section": "night",
        "value": "23:30",
        "type": "string",
        "advanced": false
      },
      {
        "key": "fatigue_end",
        "label": "夜间疲劳结束",
        "section": "night",
        "value": "07:00",
        "type": "string",
        "advanced": false
      },
      {
        "key": "deep_sleep_at",
        "label": "沉睡时间",
        "section": "night",
        "value": "02:30",
        "type": "string",
        "advanced": false
      },
      {
        "key": "lie_in_min_minutes",
        "label": "最少赖床时间",
        "section": "night",
        "value": 0,
        "type": "integer",
        "advanced": false,
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
        "step": 0.1,
        "unit": "点/分钟"
      },
      {
        "key": "catchup_enabled",
        "label": "醒后阅读未读",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "catchup_reply_enabled",
        "label": "醒后历史补答",
        "section": "night",
        "value": true,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "closing_enabled",
        "label": "睡前晚安",
        "section": "night",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "closing_random",
        "label": "道别语随机生成",
        "section": "night",
        "value": false,
        "type": "boolean",
        "advanced": false
      },
      {
        "key": "closing_lead_minutes",
        "label": "晚安提前量",
        "section": "night",
        "value": 5,
        "type": "integer",
        "advanced": false,
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
        "advanced": false
      },
      {
        "key": "embedding_provider_id",
        "label": "向量模型",
        "section": "memory",
        "value": "",
        "type": "enum",
        "advanced": false,
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
        "advanced": false
      },
      {
        "key": "memory_write",
        "label": "允许写入记忆",
        "section": "memory",
        "value": false,
        "type": "boolean",
        "advanced": false
      }
    ],
    "groups": [
      {
        "id": "quick_start",
        "label": "快速开始",
        "field_keys": [
          "enabled",
          "mode",
          "persona_id",
          "timezone",
          "provider_id",
          "allow_sleep",
          "home_city",
          "embedding_provider_id",
          "livingmemory_enabled"
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
          "model_input_tokens",
          "model_output_tokens",
          "model_timeout_seconds"
        ]
      },
      {
        "id": "relationship",
        "label": "关系",
        "field_keys": []
      },
      {
        "id": "behavior",
        "label": "主动行为",
        "field_keys": [
          "autonomy_enabled",
          "group_autonomy_enabled",
          "autonomy_scopes",
          "muted_scopes",
          "dnd_start",
          "dnd_end",
          "active_start",
          "active_end",
          "behavior_daily_limit",
          "behavior_scope_daily_limit",
          "behavior_cooldown_seconds",
          "behavior_unanswered_limit"
        ]
      },
      {
        "id": "night",
        "label": "长夜",
        "field_keys": [
          "night_enabled",
          "night_block_chat",
          "night_schedule_enabled",
          "sleep_at",
          "wake_at",
          "night_policy_version",
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
          "closing_provider_id"
        ]
      },
      {
        "id": "experience",
        "label": "日记与梦境",
        "field_keys": [
          "dream_enabled",
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
          "memory_mode",
          "memory_read",
          "memory_export",
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
        "section": "night"
      }
    ]
  },
  "state": {
    "api_version": 1,
    "context_id": "",
    "contexts": [
      {
        "id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10022",
        "label": "qq / synthetic-chat / 10022"
      },
      {
        "id": "fa26f35ec2546c181ee72799f01b5aae504e5c4033b7b202d9abecf62d5f11ab",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10008",
        "label": "qq / synthetic-chat / 10008"
      },
      {
        "id": "dfb32f3bfc4be410769366615ff06d2c19e98932e1931081a830bb8ab15e1e79",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10003",
        "label": "qq / synthetic-chat / 10003"
      },
      {
        "id": "de24a467cea45b055f7f8def9fc56b4070e20ef6e76c9e97078bb1c6293ce863",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10005",
        "label": "qq / synthetic-chat / 10005"
      },
      {
        "id": "c639f0787f3e721670ce91c66ea83ae1f3643d241cf98a647895d77ed430d573",
        "persona_id": "fixture-persona",
        "platform": "bilibili",
        "view_scope": "group",
        "scene_id": "synthetic-group",
        "account_id": "10001",
        "label": "bilibili / synthetic-group / 10001"
      },
      {
        "id": "b6523e02ceff69b99ebe35a09d40dfcf4c6eaf0456ff317bfdffa7c4250efbd0",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10004",
        "label": "qq / synthetic-chat / 10004"
      },
      {
        "id": "b2843aaa258a1b53a0f8db7536d25dfa3b1e750fcc890b11c5c655c446a38226",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10010",
        "label": "qq / synthetic-chat / 10010"
      },
      {
        "id": "af4c64efe2bd84af88a5b125e64520e83d16c8bb664e2c9544f66edd5c0eca8c",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10001",
        "label": "qq / synthetic-chat / 10001"
      },
      {
        "id": "ac17a10a834bbd6546d9df4799a3fbf4180e0f0eb2330a229a24c5d17b6f87cd",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10012",
        "label": "qq / synthetic-chat / 10012"
      },
      {
        "id": "aa3c7b08efef0610f928e202a72bc946347131b4dd10858badb9498c48f82f74",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10016",
        "label": "qq / synthetic-chat / 10016"
      },
      {
        "id": "99e913771ab562575d758281889a84d5a651e9ed85199a933b1d36905ba60a43",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10015",
        "label": "qq / synthetic-chat / 10015"
      },
      {
        "id": "8bea336f974443c4c11057900f7ed8652adc31754428a84ee4b83b85b2fe44e1",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10011",
        "label": "qq / synthetic-chat / 10011"
      },
      {
        "id": "83f40e4790ac1906f7588f8b52e5b9e5c0db9368fc7d3b32aa2d9b392edd00ab",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10007",
        "label": "qq / synthetic-chat / 10007"
      },
      {
        "id": "6ed68c6b686c9951261dc5de9738b25019ab809bc0e703c1c626a17f14c6ad81",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10018",
        "label": "qq / synthetic-chat / 10018"
      },
      {
        "id": "6ec240f3ccf36a9e65f0f924da49e2b7f133782a030fc05cee5fd45c70f557d2",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10009",
        "label": "qq / synthetic-chat / 10009"
      },
      {
        "id": "6a31c17069f1faa088d70f67b863369c79c828ac93d8dc45f53e943b0d1faa20",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10019",
        "label": "qq / synthetic-chat / 10019"
      },
      {
        "id": "5887c46fe09940abadf7caa6cf01d5725f4de752431821268b675be39984d3c5",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10013",
        "label": "qq / synthetic-chat / 10013"
      },
      {
        "id": "54c518ff3fbeb5e9479c2941bd9b2f274fc8495e7acd1c60253fb9f315bdac71",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10002",
        "label": "qq / synthetic-chat / 10002"
      },
      {
        "id": "52e7028ab96e6d15771e356ec0cc141e9924f6d9c807f92056fabd22000acc42",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10006",
        "label": "qq / synthetic-chat / 10006"
      },
      {
        "id": "51511c831a5c7e9483c8524dd0d21c9cd5704388bbde5977b68c0b84b2c6e7d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10014",
        "label": "qq / synthetic-chat / 10014"
      },
      {
        "id": "3541c3e1eb5a73c2e9c3cff4062576aa8741454589a14ccac2b743235a818bed",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10017",
        "label": "qq / synthetic-chat / 10017"
      },
      {
        "id": "20e34e626946676301e279dd297c66c688b26bf3862adb3ff1457474292c8be5",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10021",
        "label": "qq / synthetic-chat / 10021"
      },
      {
        "id": "1ef1a91376e7269b4f41b29e3d2b8a50f54ce42f81bc7343bb04b473e71a4baf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10023",
        "label": "qq / synthetic-chat / 10023"
      },
      {
        "id": "1ccd90c62355721865cacd5c9ecdb7d9c6e45962cde9fa9b49c085cdbbec2515",
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
    "revision": "config-1",
    "config": {
      "revision": "config-1",
      "source": "AstrBot native plugin configuration",
      "values": {
        "enabled": true,
        "mode": "observe_only",
        "memory_mode": "none",
        "memory_read": false,
        "memory_export": false,
        "autonomy_enabled": false,
        "group_autonomy_enabled": false,
        "emotion_model_enabled": false,
        "dream_enabled": false,
        "diary_enabled": false,
        "night_enabled": true,
        "night_block_chat": false,
        "persona_mode": "follow",
        "persona_id": "",
        "timezone": "Asia/Shanghai",
        "provider_id": "",
        "fallback_provider_id": "",
        "autonomy_scopes": "",
        "muted_scopes": "",
        "night_schedule_enabled": false,
        "sleep_at": "01:00",
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
        "diary_retries": 2,
        "dream_per_night": 2,
        "diary_retention_days": 30,
        "dream_retention_days": 7,
        "dream_half_life_seconds": 86400,
        "experience_body_chars": 2000,
        "model_concurrency": 1,
        "queue_size": 100,
        "model_daily_limit": 48,
        "emotion_interval_seconds": 300,
        "model_input_tokens": 4096,
        "model_output_tokens": 1024,
        "model_timeout_seconds": 30,
        "window_days": 7,
        "window_per_scope": 200,
        "window_global": 10000,
        "body_max_chars": 8000,
        "event_days": 30,
        "persona_shared_state": true,
        "night_policy_version": 2,
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
        "memory_write": false
      },
      "fields": [
        {
          "key": "enabled",
          "label": "启用插件",
          "section": "quick_start",
          "value": true,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "mode",
          "label": "运行模式",
          "section": "quick_start",
          "value": "observe_only",
          "type": "enum",
          "advanced": false,
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
          "key": "memory_mode",
          "label": "旧版记忆模式",
          "section": "memory",
          "value": "none",
          "type": "enum",
          "advanced": true,
          "options": [
            {
              "value": "none",
              "label": "不使用"
            },
            {
              "value": "local_lite",
              "label": "旧版本地记录"
            },
            {
              "value": "external",
              "label": "外部记忆"
            }
          ]
        },
        {
          "key": "memory_read",
          "label": "允许读取记忆",
          "section": "memory",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "memory_export",
          "label": "允许导出记忆",
          "section": "memory",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "autonomy_enabled",
          "label": "允许主动找人",
          "section": "behavior",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "group_autonomy_enabled",
          "label": "允许群聊主动行为",
          "section": "behavior",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "emotion_model_enabled",
          "label": "模型辅助情绪分析",
          "section": "emotion",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "dream_enabled",
          "label": "生成梦境",
          "section": "experience",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "diary_enabled",
          "label": "生成日记",
          "section": "experience",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "night_enabled",
          "label": "启用作息记录",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "night_block_chat",
          "label": "旧版睡眠阻断聊天",
          "section": "night",
          "value": false,
          "type": "boolean",
          "advanced": true
        },
        {
          "key": "persona_mode",
          "label": "人格选择方式",
          "section": "persona",
          "value": "follow",
          "type": "enum",
          "advanced": false,
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
          "advanced": false
        },
        {
          "key": "provider_id",
          "label": "默认生成模型",
          "section": "quick_start",
          "value": "",
          "type": "enum",
          "advanced": false,
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
          "key": "autonomy_scopes",
          "label": "主动行为范围",
          "section": "behavior",
          "value": "",
          "type": "string",
          "advanced": false
        },
        {
          "key": "muted_scopes",
          "label": "静默范围",
          "section": "behavior",
          "value": "",
          "type": "string",
          "advanced": false
        },
        {
          "key": "night_schedule_enabled",
          "label": "自动作息",
          "section": "night",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "sleep_at",
          "label": "旧版入睡时间",
          "section": "night",
          "value": "01:00",
          "type": "string",
          "advanced": true
        },
        {
          "key": "wake_at",
          "label": "基础起床时间",
          "section": "night",
          "value": "08:00",
          "type": "string",
          "advanced": false
        },
        {
          "key": "diary_at",
          "label": "日记生成时间",
          "section": "experience",
          "value": "23:00",
          "type": "string",
          "advanced": false
        },
        {
          "key": "diary_backfill_yesterday",
          "label": "补写昨天日记",
          "section": "experience",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "scheduler_seconds",
          "label": "调度间隔",
          "section": "emotion",
          "value": 60,
          "type": "integer",
          "advanced": true,
          "step": 1,
          "unit": "秒"
        },
        {
          "key": "dnd_start",
          "label": "免打扰开始",
          "section": "behavior",
          "value": "01:00",
          "type": "string",
          "advanced": false
        },
        {
          "key": "dnd_end",
          "label": "免打扰结束",
          "section": "behavior",
          "value": "08:00",
          "type": "string",
          "advanced": false
        },
        {
          "key": "active_start",
          "label": "主动时段开始",
          "section": "behavior",
          "value": "00:00",
          "type": "string",
          "advanced": false
        },
        {
          "key": "active_end",
          "label": "主动时段结束",
          "section": "behavior",
          "value": "23:59",
          "type": "string",
          "advanced": false
        },
        {
          "key": "behavior_daily_limit",
          "label": "每日主动行为总额度",
          "section": "behavior",
          "value": 6,
          "type": "integer",
          "advanced": false,
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
          "step": 1,
          "unit": "次"
        },
        {
          "key": "diary_retries",
          "label": "日记重试次数",
          "section": "experience",
          "value": 2,
          "type": "integer",
          "advanced": false,
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
          "step": 1,
          "unit": "次"
        },
        {
          "key": "emotion_interval_seconds",
          "label": "情绪分析间隔",
          "section": "emotion",
          "value": 300,
          "type": "integer",
          "advanced": false,
          "step": 1,
          "unit": "秒"
        },
        {
          "key": "model_input_tokens",
          "label": "模型输入上限",
          "section": "emotion",
          "value": 4096,
          "type": "integer",
          "advanced": true,
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
          "step": 1,
          "unit": "天"
        },
        {
          "key": "persona_shared_state",
          "label": "同一人格共享状态",
          "section": "persona",
          "value": true,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "night_policy_version",
          "label": "睡眠规则版本",
          "section": "night",
          "value": 2,
          "type": "integer",
          "advanced": true,
          "step": 1,
          "unit": "次"
        },
        {
          "key": "allow_sleep",
          "label": "允许TA睡眠",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "nap_enabled",
          "label": "启用午休",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "nap_start",
          "label": "午休开始",
          "section": "night",
          "value": "13:00",
          "type": "string",
          "advanced": false
        },
        {
          "key": "nap_end",
          "label": "午休结束",
          "section": "night",
          "value": "14:30",
          "type": "string",
          "advanced": false
        },
        {
          "key": "fatigue_start",
          "label": "夜间疲劳开始",
          "section": "night",
          "value": "23:30",
          "type": "string",
          "advanced": false
        },
        {
          "key": "fatigue_end",
          "label": "夜间疲劳结束",
          "section": "night",
          "value": "07:00",
          "type": "string",
          "advanced": false
        },
        {
          "key": "deep_sleep_at",
          "label": "沉睡时间",
          "section": "night",
          "value": "02:30",
          "type": "string",
          "advanced": false
        },
        {
          "key": "lie_in_min_minutes",
          "label": "最少赖床时间",
          "section": "night",
          "value": 0,
          "type": "integer",
          "advanced": false,
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
          "step": 0.1,
          "unit": "点/分钟"
        },
        {
          "key": "catchup_enabled",
          "label": "醒后阅读未读",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "catchup_reply_enabled",
          "label": "醒后历史补答",
          "section": "night",
          "value": true,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "closing_enabled",
          "label": "睡前晚安",
          "section": "night",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "closing_random",
          "label": "道别语随机生成",
          "section": "night",
          "value": false,
          "type": "boolean",
          "advanced": false
        },
        {
          "key": "closing_lead_minutes",
          "label": "晚安提前量",
          "section": "night",
          "value": 5,
          "type": "integer",
          "advanced": false,
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
          "advanced": false
        },
        {
          "key": "embedding_provider_id",
          "label": "向量模型",
          "section": "memory",
          "value": "",
          "type": "enum",
          "advanced": false,
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
          "advanced": false
        },
        {
          "key": "memory_write",
          "label": "允许写入记忆",
          "section": "memory",
          "value": false,
          "type": "boolean",
          "advanced": false
        }
      ],
      "groups": [
        {
          "id": "quick_start",
          "label": "快速开始",
          "field_keys": [
            "enabled",
            "mode",
            "persona_id",
            "timezone",
            "provider_id",
            "allow_sleep",
            "home_city",
            "embedding_provider_id",
            "livingmemory_enabled"
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
            "model_input_tokens",
            "model_output_tokens",
            "model_timeout_seconds"
          ]
        },
        {
          "id": "relationship",
          "label": "关系",
          "field_keys": []
        },
        {
          "id": "behavior",
          "label": "主动行为",
          "field_keys": [
            "autonomy_enabled",
            "group_autonomy_enabled",
            "autonomy_scopes",
            "muted_scopes",
            "dnd_start",
            "dnd_end",
            "active_start",
            "active_end",
            "behavior_daily_limit",
            "behavior_scope_daily_limit",
            "behavior_cooldown_seconds",
            "behavior_unanswered_limit"
          ]
        },
        {
          "id": "night",
          "label": "长夜",
          "field_keys": [
            "night_enabled",
            "night_block_chat",
            "night_schedule_enabled",
            "sleep_at",
            "wake_at",
            "night_policy_version",
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
            "closing_provider_id"
          ]
        },
        {
          "id": "experience",
          "label": "日记与梦境",
          "field_keys": [
            "dream_enabled",
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
            "memory_mode",
            "memory_read",
            "memory_export",
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
          "section": "night"
        }
      ]
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
      "behavior.preview",
      "scopes.read",
      "relationships.read",
      "relationship.write",
      "energy.read",
      "settings-options.read"
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
      }
    ],
    "memory": {
      "mode": "none",
      "provider": "none",
      "can_read": false,
      "can_write": false,
      "capabilities": [],
      "reason": "embedding_not_configured"
    },
    "experience": {
      "diary_enabled": false,
      "dream_enabled": false,
      "reason": "Explicitly enabled generation only"
    },
    "actions": [],
    "persona": {
      "id": "fixture-persona",
      "name": "fixture-persona",
      "source": "AstrBot native",
      "revision": "0",
      "description": ""
    },
    "bot_state": {
      "dimensions": {
        "pleasure": 0.5,
        "arousal": 0.3,
        "stress": 0.0,
        "social_need": 0.3
      },
      "baseline": {
        "pleasure": 0.5,
        "arousal": 0.3,
        "stress": 0.0,
        "social_need": 0.3
      },
      "label": "calm",
      "reason": "",
      "updated_at": 1800000001.0,
      "version": 0,
      "source": "livingEmotion"
    },
    "observation": null,
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
      "reason": ""
    },
    "behavior": {
      "enabled": false,
      "reason": "observe_only",
      "candidates": []
    },
    "representative_context_id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2"
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
          "persona_id",
          "timezone",
          "provider_id",
          "allow_sleep",
          "home_city",
          "embedding_provider_id",
          "livingmemory_enabled"
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
          "model_input_tokens",
          "model_output_tokens",
          "model_timeout_seconds"
        ]
      },
      {
        "id": "relationship",
        "label": "关系",
        "field_keys": []
      },
      {
        "id": "behavior",
        "label": "主动行为",
        "field_keys": [
          "autonomy_enabled",
          "group_autonomy_enabled",
          "autonomy_scopes",
          "muted_scopes",
          "dnd_start",
          "dnd_end",
          "active_start",
          "active_end",
          "behavior_daily_limit",
          "behavior_scope_daily_limit",
          "behavior_cooldown_seconds",
          "behavior_unanswered_limit"
        ]
      },
      {
        "id": "night",
        "label": "长夜",
        "field_keys": [
          "night_enabled",
          "night_block_chat",
          "night_schedule_enabled",
          "sleep_at",
          "wake_at",
          "night_policy_version",
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
          "closing_provider_id"
        ]
      },
      {
        "id": "experience",
        "label": "日记与梦境",
        "field_keys": [
          "dream_enabled",
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
          "memory_mode",
          "memory_read",
          "memory_export",
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
    "personas": [
      {
        "id": "fixture-persona",
        "name": "fixture-persona"
      }
    ],
    "platforms": [
      "bilibili",
      "qq"
    ],
    "contexts": [
      {
        "id": "fda756877b9e09334637756f7557078936706da40bd77d6ad73ad00dee0f2cb2",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10022",
        "label": "qq / synthetic-chat / 10022"
      },
      {
        "id": "fa26f35ec2546c181ee72799f01b5aae504e5c4033b7b202d9abecf62d5f11ab",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10008",
        "label": "qq / synthetic-chat / 10008"
      },
      {
        "id": "dfb32f3bfc4be410769366615ff06d2c19e98932e1931081a830bb8ab15e1e79",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10003",
        "label": "qq / synthetic-chat / 10003"
      },
      {
        "id": "de24a467cea45b055f7f8def9fc56b4070e20ef6e76c9e97078bb1c6293ce863",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10005",
        "label": "qq / synthetic-chat / 10005"
      },
      {
        "id": "c639f0787f3e721670ce91c66ea83ae1f3643d241cf98a647895d77ed430d573",
        "persona_id": "fixture-persona",
        "platform": "bilibili",
        "view_scope": "group",
        "scene_id": "synthetic-group",
        "account_id": "10001",
        "label": "bilibili / synthetic-group / 10001"
      },
      {
        "id": "b6523e02ceff69b99ebe35a09d40dfcf4c6eaf0456ff317bfdffa7c4250efbd0",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10004",
        "label": "qq / synthetic-chat / 10004"
      },
      {
        "id": "b2843aaa258a1b53a0f8db7536d25dfa3b1e750fcc890b11c5c655c446a38226",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10010",
        "label": "qq / synthetic-chat / 10010"
      },
      {
        "id": "af4c64efe2bd84af88a5b125e64520e83d16c8bb664e2c9544f66edd5c0eca8c",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10001",
        "label": "qq / synthetic-chat / 10001"
      },
      {
        "id": "ac17a10a834bbd6546d9df4799a3fbf4180e0f0eb2330a229a24c5d17b6f87cd",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10012",
        "label": "qq / synthetic-chat / 10012"
      },
      {
        "id": "aa3c7b08efef0610f928e202a72bc946347131b4dd10858badb9498c48f82f74",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10016",
        "label": "qq / synthetic-chat / 10016"
      },
      {
        "id": "99e913771ab562575d758281889a84d5a651e9ed85199a933b1d36905ba60a43",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10015",
        "label": "qq / synthetic-chat / 10015"
      },
      {
        "id": "8bea336f974443c4c11057900f7ed8652adc31754428a84ee4b83b85b2fe44e1",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10011",
        "label": "qq / synthetic-chat / 10011"
      },
      {
        "id": "83f40e4790ac1906f7588f8b52e5b9e5c0db9368fc7d3b32aa2d9b392edd00ab",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10007",
        "label": "qq / synthetic-chat / 10007"
      },
      {
        "id": "6ed68c6b686c9951261dc5de9738b25019ab809bc0e703c1c626a17f14c6ad81",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10018",
        "label": "qq / synthetic-chat / 10018"
      },
      {
        "id": "6ec240f3ccf36a9e65f0f924da49e2b7f133782a030fc05cee5fd45c70f557d2",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10009",
        "label": "qq / synthetic-chat / 10009"
      },
      {
        "id": "6a31c17069f1faa088d70f67b863369c79c828ac93d8dc45f53e943b0d1faa20",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10019",
        "label": "qq / synthetic-chat / 10019"
      },
      {
        "id": "5887c46fe09940abadf7caa6cf01d5725f4de752431821268b675be39984d3c5",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10013",
        "label": "qq / synthetic-chat / 10013"
      },
      {
        "id": "54c518ff3fbeb5e9479c2941bd9b2f274fc8495e7acd1c60253fb9f315bdac71",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10002",
        "label": "qq / synthetic-chat / 10002"
      },
      {
        "id": "52e7028ab96e6d15771e356ec0cc141e9924f6d9c807f92056fabd22000acc42",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10006",
        "label": "qq / synthetic-chat / 10006"
      },
      {
        "id": "51511c831a5c7e9483c8524dd0d21c9cd5704388bbde5977b68c0b84b2c6e7d6",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10014",
        "label": "qq / synthetic-chat / 10014"
      },
      {
        "id": "3541c3e1eb5a73c2e9c3cff4062576aa8741454589a14ccac2b743235a818bed",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10017",
        "label": "qq / synthetic-chat / 10017"
      },
      {
        "id": "20e34e626946676301e279dd297c66c688b26bf3862adb3ff1457474292c8be5",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10021",
        "label": "qq / synthetic-chat / 10021"
      },
      {
        "id": "1ef1a91376e7269b4f41b29e3d2b8a50f54ce42f81bc7343bb04b473e71a4baf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10023",
        "label": "qq / synthetic-chat / 10023"
      },
      {
        "id": "1ccd90c62355721865cacd5c9ecdb7d9c6e45962cde9fa9b49c085cdbbec2515",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "view_scope": "private",
        "scene_id": "synthetic-chat",
        "account_id": "10020",
        "label": "qq / synthetic-chat / 10020"
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
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "d82928066adf44e994afc87f23c44aac26505a2127b70ddc0f9fef2b48c084f8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10019",
        "label": "10019",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "d5a0f7879fcd72d70c0e1468624c11f0c5b2d4b2de7f19816e7a09e5ce7636bf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10007",
        "label": "10007",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "c867fc2832983b115f4466680aa31ae1d6c9f4361f64f285c0ab0734fe072d9d",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10001",
        "label": "10001",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "c00054d0505e5bcd7f5d1f655b60e5ab3e59dab0be8a0cd0f690cbafd6fd1dbc",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10005",
        "label": "10005",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "bec7993aacc968bbe925eee176827eeedbed2876f091d566e8cc406d6af09185",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10020",
        "label": "10020",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "b8fddea1e66bd4401e8ff37025e1ce607c2d7d6db8a8bbc68b6d0bcbc6158ff8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10017",
        "label": "10017",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "b69fb57d322b06bac925a50b981d3efecc5a868dae60958329193aed4baafe82",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10008",
        "label": "10008",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "adb022534ea72423c94d283a6d29240db1b4c6e0643dd02015d375b7f409d71f",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10010",
        "label": "10010",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "a231321ba9499da2d50011ab63fee305af89f7e69b41954567e7c9bc91d92fcb",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10014",
        "label": "10014",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "9fd41a29af14350c6be368260de8e77cf57d3089bb7c63ee4a0d2dac9a463cfb",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10003",
        "label": "10003",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "9d8e435e4a5b0b14d1ea055e0664a4dc0e45c69910c249721ba76528dd8dbbab",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10023",
        "label": "10023",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "903ea42ec60700f6a58d4c8ceb7b18036c47b7cb8082ab4ac6346c3ee0f84b57",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10009",
        "label": "10009",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "8b66532908389711e30d79b3917511c025d649e0226170c95b6ebc9329086a90",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10002",
        "label": "10002",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "606fad4bc097427cc13515300c5bfe7e8f28273ee2e6b689723cfe96155f90ed",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10011",
        "label": "10011",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "599993818a971672d92766010112f13a45ebe0324a5a8a0f8a9dabc9411f2532",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10022",
        "label": "10022",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "5483bfd2e703f07d69c023c70e9f3f084a9ea4332c18e4d985b74b576521ccb2",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10006",
        "label": "10006",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "4813dfbe51ca3b2705f0d65b997dc2b4bc5082a069b9dfd4f433eeae2f4c0469",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10012",
        "label": "10012",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "45769e01aa2b5ed4b35af7fd17f1a2cae7377e8f3e593a43a9a60659a9b89a9d",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10018",
        "label": "10018",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "3315db5a2de4e83356d84a8441a56b9f37d61842ec2b478bfa664ef772bcdfaf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10013",
        "label": "10013",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "28e2b592ea4239630563d20fbca7273893a9587280d48d68bd0d494068257679",
        "persona_id": "fixture-persona",
        "platform": "bilibili",
        "account_id": "10001",
        "label": "10001",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "1afebc4e70572f630907d8324723db71ce06c82d70524f2297cce5250b197952",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10016",
        "label": "10016",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "0799dec7c092fc60a037a69973bf862a443aed80c6ce1f0b5f6837e45506ee70",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10004",
        "label": "10004",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "026d65db6260001564b8163edc0bedc05677d499333bd717d7ac6004f1521a3c",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10015",
        "label": "10015",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      }
    ],
    "edges": [
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "e4e8210c93560d74ba4764249ff98e919057ac0c7f6433abeeb2f5812fe0eaf7",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "d82928066adf44e994afc87f23c44aac26505a2127b70ddc0f9fef2b48c084f8",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "d5a0f7879fcd72d70c0e1468624c11f0c5b2d4b2de7f19816e7a09e5ce7636bf",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "c867fc2832983b115f4466680aa31ae1d6c9f4361f64f285c0ab0734fe072d9d",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "c00054d0505e5bcd7f5d1f655b60e5ab3e59dab0be8a0cd0f690cbafd6fd1dbc",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "bec7993aacc968bbe925eee176827eeedbed2876f091d566e8cc406d6af09185",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "b8fddea1e66bd4401e8ff37025e1ce607c2d7d6db8a8bbc68b6d0bcbc6158ff8",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "b69fb57d322b06bac925a50b981d3efecc5a868dae60958329193aed4baafe82",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "adb022534ea72423c94d283a6d29240db1b4c6e0643dd02015d375b7f409d71f",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "a231321ba9499da2d50011ab63fee305af89f7e69b41954567e7c9bc91d92fcb",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "9fd41a29af14350c6be368260de8e77cf57d3089bb7c63ee4a0d2dac9a463cfb",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "9d8e435e4a5b0b14d1ea055e0664a4dc0e45c69910c249721ba76528dd8dbbab",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "903ea42ec60700f6a58d4c8ceb7b18036c47b7cb8082ab4ac6346c3ee0f84b57",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "8b66532908389711e30d79b3917511c025d649e0226170c95b6ebc9329086a90",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "606fad4bc097427cc13515300c5bfe7e8f28273ee2e6b689723cfe96155f90ed",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "599993818a971672d92766010112f13a45ebe0324a5a8a0f8a9dabc9411f2532",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "5483bfd2e703f07d69c023c70e9f3f084a9ea4332c18e4d985b74b576521ccb2",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "4813dfbe51ca3b2705f0d65b997dc2b4bc5082a069b9dfd4f433eeae2f4c0469",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "45769e01aa2b5ed4b35af7fd17f1a2cae7377e8f3e593a43a9a60659a9b89a9d",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "3315db5a2de4e83356d84a8441a56b9f37d61842ec2b478bfa664ef772bcdfaf",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "28e2b592ea4239630563d20fbca7273893a9587280d48d68bd0d494068257679",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "1afebc4e70572f630907d8324723db71ce06c82d70524f2297cce5250b197952",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "0799dec7c092fc60a037a69973bf862a443aed80c6ce1f0b5f6837e45506ee70",
        "score": 0.0
      },
      {
        "source": "75cc0781b781ddc3f57b3745d214b53a240f02d4ffb74346b46fc2d0aef2b071",
        "target": "026d65db6260001564b8163edc0bedc05677d499333bd717d7ac6004f1521a3c",
        "score": 0.0
      }
    ],
    "items": [
      {
        "id": "e4e8210c93560d74ba4764249ff98e919057ac0c7f6433abeeb2f5812fe0eaf7",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10021",
        "label": "10021",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "d82928066adf44e994afc87f23c44aac26505a2127b70ddc0f9fef2b48c084f8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10019",
        "label": "10019",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "d5a0f7879fcd72d70c0e1468624c11f0c5b2d4b2de7f19816e7a09e5ce7636bf",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10007",
        "label": "10007",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "c867fc2832983b115f4466680aa31ae1d6c9f4361f64f285c0ab0734fe072d9d",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10001",
        "label": "10001",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "c00054d0505e5bcd7f5d1f655b60e5ab3e59dab0be8a0cd0f690cbafd6fd1dbc",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10005",
        "label": "10005",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "bec7993aacc968bbe925eee176827eeedbed2876f091d566e8cc406d6af09185",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10020",
        "label": "10020",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "b8fddea1e66bd4401e8ff37025e1ce607c2d7d6db8a8bbc68b6d0bcbc6158ff8",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10017",
        "label": "10017",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "b69fb57d322b06bac925a50b981d3efecc5a868dae60958329193aed4baafe82",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10008",
        "label": "10008",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "adb022534ea72423c94d283a6d29240db1b4c6e0643dd02015d375b7f409d71f",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10010",
        "label": "10010",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      },
      {
        "id": "a231321ba9499da2d50011ab63fee305af89f7e69b41954567e7c9bc91d92fcb",
        "persona_id": "fixture-persona",
        "platform": "qq",
        "account_id": "10014",
        "label": "10014",
        "raw": 0.0,
        "score": 0.0,
        "normalized": 0.0,
        "stage": "unestablished",
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
        "updated_at": 0.0
      }
    ],
    "total": 24,
    "displayed": 24,
    "page": 1,
    "page_size": 10
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
    "collected": false,
    "reason": "energy_history_not_collected",
    "points": [],
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 10,
    "series_total": 2,
    "points_truncated": false
  }
};
export const nativeDTOEvidence = {
  "captured_at": "2026-11-06T13:35:55.630426+00:00",
  "field_count": 81,
  "scope": "real Console DTO / synthetic host / temporary database",
  "sources_sha256": {
    "config.py": "4773b316f75c1d1171d2ff6a058d30ac1a684106994874780cc8ee985b1bec43",
    "contracts.py": "dbc6bc256d6eb58b6fff26a58c652b75a4f6ff1854ad63150ce13a19a1f15696",
    "runtime/console.py": "11842467ef7ac194cb4ecd75a2ddd97f383fe40fba1cd06a544ea3ac5cfb0a9e",
    "storage/schema.py": "2b3d106e881595456a5198f73d10f584ebc0e47dc632e0b3c1a3c814b900e93e",
    "storage/sqlite.py": "2febb2a71165853a53886cfef170ebf8956cb6d8e516a102817badfcf868c07d",
    "storage/state_scope.py": "cce5716c1ec8d3264c37c6d577b092f8a32a0c9d634595a8ef0f302fb688a2fe"
  }
};
