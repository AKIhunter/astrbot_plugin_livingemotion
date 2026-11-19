# API v1

适用0.6.0；按api.py、page_api/routes.py、validation.py和Console核对。
本页同时列出公开进程内门面和全部21项注册管理路由。
注册不等于应用已接通：emotion-image-save当前缺少应用入口，返回503。

## 进程内门面

可信插件每次从宿主发现当前激活实例并使用plugin.api，不缓存重载前对象，
不跨插件读私有配置或SQL。响应含api_version=1/status/reason_code，
先核对status再读data；外层ok不保证内层业务成功。

| async方法 | 输入 | 结果与作用 |
| --- | --- | --- |
| get_capabilities | 可选context | schema_version、operations、实例、实际领域/执行/模型能力 |
| resolve_producer_context | 受信source字典 | 完整Context；不接受自定实例或路由 |
| ingest_event | Event或字典 | accepted/duplicate/rejected、event_key、generation、versions |
| get_bot_state | Context | 当前bot状态、version、generation |
| get_current_emotion | context或关键字event | 当前情绪、labels、affect、影响回复许可 |
| get_observation | Context，含账号 | 对方观察；缺失/到期为null |
| get_relationship | Context，含账号 | score/normalized及版本 |
| get_availability | Context | available/block_chat及reason_codes |
| preview_behavior | Context | eligible/reason_codes，model_calls=0/sends=0 |
| get_health | 无 | 存储、队列和结构化健康原因 |
| get_action_policy | context、关键字event | image-policy.v1，新需求生图许可；已有义务单独判定 |
| get_image_prompt_retry_policy | 同上 | 新版有限改词是否可以接手 |
| handoff_image_failure | 同上 | image-followup.v1，同一真实失败的交接 |
| resume_image_followup | 同上及promise_id/prompt | 具体新画面恢复原waiting事项；纯重试、未知结果不授权 |
| bind_image_promise | context、event | image-result.v1；读取受控binding，收费前原子领取 |
| settle_image_promise | context、event | 同契约；sent/failed/unknown原事项回执结算 |

Context隔离宿主实例、Bot、适配器、平台、场景、会话、账号、人格及修订。
producer resolver支持private/public_comment；private场景ID等于账号，
公开评论使用真实稳定线程ID且无route。一般Context可有group，
不代表producer入口支持group。resolver成功不等于事件提交或发送授权。
Event必填event_id/producer/event_type/context/actor_role/occurred_at/source_id；
human actor_id匹配来源。时间为有限非负UTC秒，bool不可冒充数字。
authorization和代际须最终复核；历史、梦与摘要不伪造成新互动。

## 生图绑定与回执

LH 2.9.0在同一受信事件extra写入受控结构，再调用公开门面：

```json
{"promise_id":"原事项ID","request_id":"原请求ID","prompt":"窗边的猫","use_reference":false}
```

binding存于_livinghello_image_binding；原事项scheduled、图片类型、来源和代次一致，
且没有宿主所有权才返回data.status=bound。失败不调用上游。
receipt存于_livinghello_image_result，在上面字段追加status=sent/failed/unknown，
可含kind、revised、original_prompt、attempted_prompt、auto_prompt_retry、adjustment_asked。
sent只表示发送调用受理；同请求重复回执幂等，成功不能降级。
明确失败且新版许可有效才回到原ID retry_ready，未知图片副作用暂停。
状态和trace同事务落库，缓存TTL使用当前配置。详见[承诺](promise.md)。

## 管理HTTP与认证

页面通过宿主bridge-sdk访问console相对端点；外部当前v1路径：

```text
/api/v1/plugins/extensions/astrbot_plugin_livingemotion/console/<端点>
```

所有读写使用Dashboard管理员Bearer令牌。资源token、cookie-only、API Key、
客户端actor_id/admin不能替代身份；handler注入实际actor并在请求前后复核。
GET只接受单值白名单参数；POST不接受query，要求application/json，
拒绝重复JSON键、NaN/Infinity、NUL、未知字段和类型混用。
一般请求32KiB，config 512KiB，emotion-image-save 732KiB。

成功为`{"status":"ok","data":{"api_version":1}}`，业务需继续核对data.status。
失败为status=error/code/message/data=null；响应no-store。
400 validation_error须修输入；401/403须核对身份/许可；
409 version_conflict须重读，generation_in_progress等任务完成；
503 unavailable须先读回状态，写操作不盲重试。

## 全部21项管理路由

S为ScopeSelection：persona_id/view_scope=global/private/group/context_id/platform。
context_id是后端发布的账号级account_key，不能替换QQ号或scope_key。
global汇总真实来源，不创建全局发送路由。state/configuration可无参数或旧context_id，
新范围参数需人格；records需kind及旧会话或新范围。
列表page默认1（1–1000000）、page_size固定10，query最多200字。

| 方法 / 端点 | 输入 | 主要结果或效果 |
| --- | --- | --- |
| GET state | 可选S | revision、config、actions、状态/健康、selection、action_target |
| GET configuration | 同state | 轻量config对象；保存前优先读它 |
| GET scopes | 可选S | 人格、平台、会话选择及counts |
| GET records | S、kind=emotion/behavior/diary/dream、分页/query | items/total；行为含完整promises与总数，私人体验含正文/来源 |
| POST config | patch、expected_revision；可选context_id/reason/receipt=state或config | 原生保存、运行态替换与回执 |
| POST preview | context_id | 行为资格预览，0模型/0发送 |
| POST action | context_id/action/expected_revision/confirmed=true；可选reason及置顶字段 | 下述动作；最终复核业务守卫 |
| GET relationships | S、分页/query、limit、graph_scope=matched/all | 分页关系及nodes/edges/displayed |
| POST relationship | persona_id/platform/account_id或context_id、expected_version、score/frozen/note、reason | CAS编辑好感；需编辑许可 |
| GET energy | S、分页、event_type | 精力事件与曲线 |
| GET settings-options | 无 | 人格、chat/embedding模型选项，不含密钥 |
| GET persona-description | persona_id | 原生人格说明，最多16000字符 |
| GET style-summary | persona_id | 当前摘要、是否custom/available |
| POST style-summary-save | persona_id/text；可选reason | 最多2000字符，空串恢复默认 |
| POST memory-sync | 可选context_id | 当前提供者实际同步能力与结果 |
| POST behavior-simulate | 可选context_id/persona_id/emotion/request_id | 生成模拟日志，sends=0；模型可收费 |
| GET emotion-images | 无 | 情绪图片配置、各mood可用项 |
| GET emotion-image | mood/index | 图片读取结果，不产生消息 |
| POST emotion-image-save | mood及data_url/index/remove | 当前应用入口缺失，503 |
| POST experience-generate | request_id/persona_id/kind=diary或dream | 接受或复用后台私人任务 |
| GET experience-task | request_id | 同人格任务状态，查询不再次派发模型 |

action白名单是night.sleep/night.wake/diary.generate/dream.generate/behavior.send/experience.pin。
睡眠动作仍需allow_sleep及当前可用动作；唤醒不加精力。
behavior.send跳过时机/冷却等软条件，保留硬闸门；它会真实发送。
experience.pin需entry_id、pinned与相反的expected_pinned；无模型、无发送。
当前没有promise.cancel、clear_context、全库删除或local_lite录入HTTP端点。

## 配置保存与任务幂等

config.revision是配置版本，state.revision是动作版本，不混用。
patch非空，仅接公开Config字段，合并当前值后做跨字段校验；
原生保存失败不确认成功，冲突保留草稿。数字参数见[配置参考](config-reference.md)，
天气过渡0–7200秒、缓存1–168小时步进0.1。可请求receipt=config快速读回。

```json
{"expected_revision":"读取的config.revision","patch":{"allow_sleep":false},"receipt":"config"}
```

experience request_id为16–64位ASCII字母/数字/下划线/连字符或UUID；
同ID同人格/类型复用，身份/类型不同冲突，同日正在运行时返回已有ID。
轮询返回ID，成功正文从records读取。手动生成无需自动开关，梦仍需dream_enabled。
输入32768 UTF-8字节、输出请求8192 Token、90秒，模型费用与生成结果单独验收。
情绪0–1、原生pleasure -1–1、关系0–1000、energy_percent 0–100；
旧night.energy为0–1，不能重复归一化。来源/清晰度/置顶规则见[体验](experience.md)。
