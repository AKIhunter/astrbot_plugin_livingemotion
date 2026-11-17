# LivingHello / LivingEmotion 双插件协作契约（LE 0.4.0）

保留两个插件。此次收敛延迟图片的授权、投递和回执入口，不重写全部主动行为调度。

| 能力 / 数据 | 所有者 |
| --- | --- |
| 普通消息判定、名单、回复有效期、图片理解、生图开关及额度 | LivingHello |
| 情绪、关系、作息、人格状态、承诺时间及承诺终态 | LivingEmotion |
| 延迟图片提交与图片投递回执 | LivingHello |
| 宿主 future_task 与 promise 标记的归属仲裁 | LivingEmotion |

普通文字主动行为保留 `AstrBotBehaviorSender` 的原生 QQ 回执和分段能力。
LE 承诺是否完成，只依据自身动作检查点及有效的 LH 投递回执；宿主 cron 摘要不是送达证据。

## 接口与兼容

| 接口 / 字段 | 分类 | 承诺 |
| --- | --- | --- |
| `get_function_coupling().cooperation` | 增量字段 | `livinghello.cooperation.v1` 声明职责，已有 integration 开关与 freshness 字段保持原语义 |
| `get_deferred_image_contract().delivery_contract` | 增量字段 | 宣告 `livinghello.deferred-image-delivery.v1` |
| `generate_deferred_image(event, prompt)` 返回资源 | 增量字段 | 新资源增加 delivery_contract；保留 path、session、request_id、revised |
| `deliver_deferred_image(event, artifact, authorize=None)` | 新接口 | 只投递已登记资源；LE 传实时授权回调，cron 使用 LH 自身守卫 |
| `execute_deferred_image(event, prompt)` | 内部出口兼容收敛 | cron 复用新投递接口，工具仍根据 sent 判断是否交付 |
| `complete_deferred_image(request_id, status)` | 保留旧接口 | 兼容旧 LE 的发送结果回调；不能重新打开已发送的图片 |

调用者每次从宿主实时注册表发现当前实例，不跨重载缓存。
LE 的策略读取、群聊主动名单检查与承诺图片发现共用历史名字表：
`astrbot_plugin_at_guard`、`astrbot_plugin_LivingHello`、`astrbot_plugin_livinghello`、`livinghello`。
名单查询与实际投递使用同一会话的 account_id / scene_id，不跨插件读配置文件。

旧 LH 没有图片契约时，图片承诺退避等待，文字能力独立工作。
LH 有上一版图片契约时，LE 继续原直发/回调路径。旧 LE 可忽略新增字段。
已生成的新资源遇到 LH 接口缺失时保留原图等待，不能绕过新接口发送。
停用 LH 后不再发现图片能力；停用 LE 后 LH 的图片与 cron 工具可独立工作。
现有作息规则保留：用户约定时间的承诺交付走 delivery 授权，普通主动聊天仍受作息限制。

## 资源、回执与重试

资源身份是 `(request_id, session, path)`，由 LH 生成后写入图片额度库的独立表。
投递 event 的会话必须匹配，不能更换路径或借用别的请求 ID。
描述输入仍限制 1～4000 字；本接口为同宿主内受信任插件调用，未新增 Web 路由或外部权限。

所有返回回执包含 contract、request_id、status、reason、retryable。
LE 必须核对 contract 和 request_id 后才能接受 sent；异常、畸形回执或未知状态均落 unknown。
错误只输出固定类别，不携带 API Key、异常正文或模型连接信息。

| 回执 / reason | retryable | 调用方处理 |
| --- | --- | --- |
| `sent` / 空、`already_sent` | false | 记录完成；True 表示宿主适配器受理，未获得平台最终回执 |
| `rejected` / `send_not_accepted` | true | 宿主明确 False，按 LE 退避重发原图，不重新生图 |
| `rejected` / `delivery_blocked`、`source_authorization_denied` | true | 未提交，等待授权恢复 |
| `rejected` / `invalid_artifact` | false | 参数/资源身份错误，停止自动尝试并检查调用方 |
| `unknown` / `file_missing`、`claim_failed`、`already_attempted` | false | 禁止自动重发或重新收费 |
| `unknown` / `send_failed`、`send_not_confirmed` | false | 提交可能发生，停止自动重试 |

发送前原子写盘 `sending`，同资源并发只允许一次提交；sent 重放返回原结果。
异常、取消或发送中断后不再自动领取，只有明确拒收能重新领取。
完成状态写盘失败会保留 sending，宁可等待核实，也不重复发图。
资源不自动过期或删除，以便保留未知提交去重依据；未新增轮询或批量接口。

以后 v1 只增加可选字段；修改已有字段或重试语义须新增版本并保留旧版重叠期。
本轮没有删除旧接口，也没有生产使用率数据，不能据此宣布旧版可移除。

## 验证与边界

`test_promise_actions.py` 覆盖新旧接口、重载、回执校验、退避和跨系统归属。
LH 场景覆盖原图拒收重试、同资源并发、重建服务、取消、身份替换及授权等待期间关开关。
真实宿主类入口验证配套生成、投递、落库及回执重放，Provider 和平台发送隔离。

上述入口是隔离联测，不证明真实模型、真实 QQ 或平台最终送达。
本契约代码已纳入 LE 0.4.0；发布回归与部署读回分别记录，不能混为一种能力证明。
LivingMemory 等外部插件源码联测不属于此契约的验证范围。
外部宿主 API 与 LE 本地领取锁之间
仍存在并发新建任务窗口，不声称跨库事务或全局恰好一次。
