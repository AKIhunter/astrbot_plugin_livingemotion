# LivingHello 群聊回复复核

`runtime/application.py` 的 `_native_freshness_valid` 在同一群事件同时提供 `_livinghello_policy_send_check` 和 `_at_guard_send_check` 时委托 LivingHello 判断是否可发送。新群消息本身不撤销已生成的合法回复；撤回、消息有效期和策略变更仍由回调复核，显式阻断或回调异常返回不可发送。

私聊、群 ID 不匹配、缺少任一回调或未接管事件仍使用严格人类消息水位。配置 revision、上下文 generation、active 模式和记忆证据授权独立检查，记忆复核后再次检查上下文与发送资格，避免等待期间条件改变。

`tests/integration/test_livinghello_freshness.py` 使用合成群/私聊上下文验证上述边界，不执行模型请求或真实发送。本改动不改变主动行为开关及生产模式。
