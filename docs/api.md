# API v1

进程内 v1 门面保持兼容；新版范围筛选、关系覆盖、精力日志和集中设置的管理 DTO
见 [管理接入契约](internal-console-contract.md)。写操作仍要求 Dashboard 管理员 Bearer，
全局筛选不创建真实发送路由。新增状态所有者、票据与回复提交端口见
[状态接入契约](internal-state-contract.md)。
日记与梦境置顶通过既有 `console/action` 的 `experience.pin`，带真实记录
`context_id/entry_id/pinned/expected_pinned`、配置版本、原因及显式确认。
同一认证身份注入、全记录事务比较与审计生效；旧置顶重放409，不调用模型。
下文保留0.1原始接口参考，不以旧五端点计数代替新版路由集合。

读者：受信插件和管理页面的开发者。本文件依据 `contracts.py`、`api.py`、
`runtime/console.py` 和 `page_api`，2026-11-05 核对源码。
维护者在签名、量纲、鉴权或版本变化时同步，每次交付复核。
Application/宿主钩子已完成冻结版三场景验收，H01/H02/H03 与确认能力降级均通过；
运行时仍以返回能力为准，不把本地验收当作外部能力或发送授权。

## 进程内门面

受信插件每次从宿主发现当前激活实例，再使用 `plugin.api`；
重载后不得缓存旧实例，不读 `.store/.cfg/._lifecycle` 或私有 SQL。
这是同进程协作契约，不是恶意插件安全沙箱，也不是可直接暴露给模型的工具。

| async 方法 | 输入 | 主要输出 |
| --- | --- | --- |
| `get_capabilities()` | 无 | api_version、schema_version、operations、instance_id、mode、memory_mode、domain_ready、autonomous_executor、model_generation |
| `resolve_producer_context(source)` | 可信生产者来源字典 | `status=ok` 时 `data` 为完整 Context；不接受生产者自定实例/路由 |
| `ingest_event(event)` | Event 或对应字典 | accepted/duplicate/rejected、reason_code、event_key、generation、versions、domain_applied |
| `get_bot_state(context)` | Context 或字典 | type=bot、data、version、generation、context |
| `get_observation(context)` | 同上，需 account_id | type=observation、data；没有或已过期为 null |
| `get_relationship(context)` | 同上，需 account_id | type=relationship、score 和 normalized |
| `get_availability(context)` | 同上 | 布尔 available/block_chat、reason_codes；不可用不是自主授权 |
| `preview_behavior(context)` | 同上 | eligible、reason_codes、model_calls=0、sends=0 |
| `get_health()` | 无 | 存储、队列/任务和结构化原因；不是完整成品已验收证明 |

普通响应含 `api_version=1/status/reason_code`，data 只在相应操作中提供。
调用者先查版本、能力、status，不能假定每个响应都有 data。
能力不是固定 false：`domain_ready` 取决于 projector，
`autonomous_executor/model_generation` 取决于 Application 是否接入，
不代表 Provider 可用、配置允许或已获授权。页面 `actions[].enabled` 是当前可尝试动作，
最终执行仍须复核。未接服务的独立门面会出现 `domain_not_connected`、`executor_not_connected`；
domain_ready=false 时即使事件已保存，也不能宣称领域状态已应用。
完整共享类型及存储签名见 [CONTRACTS.md](CONTRACTS.md)；
其中阶段描述与场景枚举可能早于 public_comment 增量，以当前源码为准。

## 来源与事件

Context 的完整隔离维度见 [architecture.md](architecture.md)。
时间使用有限非负 UTC Unix 秒；revision 是不可解释的令牌；
bool 不可冒充数字，NaN/Infinity 被拒绝。
Bot pleasure 为 -1..1，其他情绪维度 0..1，关系 0..1000，night energy 0..100。
页面 DTO 才将 pleasure 映射为 `(x+1)/2`、energy 映射为 `/100`，不要双重归一化。

生产者来源必须精确包含：
`producer/bot_account/adapter_id/platform/scene_kind/scene_id/account_id/persona_id/persona_revision`。
当前生产者入口支持 private 和 public_comment；private 的 scene_id 必须等于 account_id，
公开讨论使用真实稳定对象/线程 ID，不用作者裸 ID、正文哈希或秒时间代替。
一般 Context 另支持 group，但不代表当前 producer resolver 接受 group。
公开评论禁止 route，不参与主动/记忆/体验生成的支持承诺。
解析来源成功仅得到 Context；事件是否持久接受须看 `ingest_event`，不能把 resolver 当发送路由注册。

```python
# 只供可信宿主适配器调用；verified_source 来自真实来源和原生人格。
caps = await plugin.api.get_capabilities()
if caps.get("api_version") == 1 and caps.get("status") == "ok":
    resolved = await plugin.api.resolve_producer_context(verified_source)
    if resolved.get("status") == "ok":
        relationship = await plugin.api.get_relationship(resolved["data"])
```

Event 字段：
`event_id/producer/event_type/context/actor_role/occurred_at/source_id` 必填；
可选 `actor_id/body/signals/confidence/evidence/reliable_source/rule_version`。
actor_role=human/bot/unknown；human 的 actor_id 必须匹配来源账号。
只用真实成功行为构造 `bot_action_succeeded`；不能把 bool、超时或模型“已发送”当回执。
按真实平台来源生成稳定事件键；重复不二次生效，不拿新 ID 绕过拒绝。
记忆、日记、梦、摘要与未知历史不能伪造成新的人类互动。

EvidenceRef 保留 provider、source_id、Context、subject_id、holder_id、kind、
occurred_at、expires_at、sensitive、exportable、authorization 和原 source_ids。
authorization 是提供者复核凭据，不是字符串 admin 或永久访问权。
请求/用途去重和最终授权规则见 [memory.md](memory.md)。

## 状态与重试

- `queued` 只表示排队；`accepted` 表示本地事务已提交，不表示生成或发送完成。
- `duplicate` 不追加状态增量；`rejected`/`unavailable` 应展示原因，不切换提供者重复上报。
- `version_conflict` 要重读并重新计算，不盲重放旧 patch；清除代际改变时丢弃旧结果。
- sending 后超时、部分确认、异常、None 或宿主 True 都可能为 `unknown`；
  不自动重发，不生成成功行为，额度不退款。False 只在可信发送端确定未发送时为 rejected。
- availability.available=false 可否决自主；只有 block_chat=true 才代表聊天阻断请求。
  接口故障不能反向当作主动许可，通常也不应阻断原生主聊天。

固定 v4.29.4 的 `OnAfterMessageSentEvent` 在发送失败后也执行，
`Context.send_message` 的 bool 仅表示找到平台；二者均不提供可靠确认能力。
`Application.confirm_reply` 的 typed receipt 端口仅供具备可靠传输证据的适配器，
不属于上表公开门面；成功用例只证明组件端口，不能称为生产投递。
原生确认能力按 unsupported 处理；console health 的 `reply_confirmation=unavailable`
及对应原因已由最终真实 HTTP/iframe 验证，不扩充进程内公开门面。
待回复 `settling` 在既有 120 秒上限后取消回 `awake/drowsy`，不自动重发；
无待回复的计划睡眠与手动睡眠可用。独立降级结果见[最终宿主验收](verification-host-final.md)。

`get_bot_state` 读取时按当前时间派生情绪恢复；不制造新刺激或更新持久版本。
关系公开接口保留 H01 `storage_failed` 历史失败；最终三场景已返回 ok/snapshot，
仍不能假定运行时返回恒为 ok。
调用方发现 `unavailable` 应省略补充或停止自主，不以缓存的成功状态替代当前授权。

## 页面接口

生产页面经宿主 `/api/plugin/page/bridge-sdk.js` 的
`AstrBotPluginView`（兼容 `AstrBotPluginPage`）调用相对端点：

| 方法/相对端点 | 请求 |
| --- | --- |
| GET `console/state` | 可选 context_id；空值取最近合法范围或空状态 |
| GET `console/records` | context_id、kind=emotion/behavior/diary/dream、page>=1、page_size=10、可选 query |
| POST `console/config` | context_id、patch、expected_revision、reason |
| POST `console/preview` | context_id；必须无模型、无发送 |
| POST `console/action` | context_id、action、expected_revision、reason、confirmed=true |

action 白名单为 night.sleep/night.wake/diary.generate/dream.generate/behavior.send；
仍需检查当前 State.actions 及服务最终硬闸门。生成可能计费，send 可能外发。
context_id 只能使用后端发布的不透明值，不接受客户端 Context。
当前 `context_id/contexts[].id` 为账号级 account_key；主动白名单用 scope_key，
两者不可互换。`config.values/fields/revision` 来自同一原生 Config。
无公开 HTTP 关系修正或全库删除动作；不要猜造端点。
核心存在 `correct_relationship/clear_context/pin_experience` 管理方法，
但本页五个 HTTP 入口没有发布这些动作，也没有 local_lite 录入端点。

宿主注册路径为 `/astrbot_plugin_livingemotion/console/*`；
legacy 实际路径 `/api/plug/astrbot_plugin_livingemotion/console/*`，
v1 为 `/api/v1/plugins/extensions/astrbot_plugin_livingemotion/console/*`。
成功 envelope 为 `{"status":"ok","data":...}`；错误使用 400/401/403/409/503，
message 带 `[livingemotion:<code>]`，完整私有响应应 `Cache-Control: no-store`。

每个私有读写请求均须严格 Dashboard Bearer 验签、当前管理员匹配和 claims 用途白名单；
页面资源 token 只能读页面资产，不能读私人状态或写配置。拒绝未知/OAuth claims、
过期/伪签、admin=true 和客户端 actor_id；不把 cookie-only/API key 当作现有支持方式。
actor_id 必须由 handler 从已验证身份提供。页面不代替业务层 CAS/审计/来源复核。
详见 [console.md](console.md)、[host-contract.md](host-contract.md)。
最终 single222/four230/conflict245，共697条宿主断言通过；原生浏览器44项
（含28组布局）、0 pageerror。H01与五handler鉴权均覆盖，限制见[兼容矩阵](compatibility.md)。
本轮仅同步报告，未重跑宿主或调用真实平台。
