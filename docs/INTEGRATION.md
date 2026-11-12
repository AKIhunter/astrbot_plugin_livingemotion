# 运行集成契约

当前实现由 `runtime/application.py` 装配；公开 API 为 v1。
本页描述当前接点，旧冻结分工及参考材料保存在 Git 历史。

## 生命周期与模式

`main.py` 创建 Application，初始化存储、后台队列和服务后暴露 `plugin.api`，
随后注册页面接口；停止时先停页面，再取消并等待自身任务，最后关闭存储。
初始化失败也清理已创建资源。配置保存后更新运行配置和 revision，
在途任务须复核版本、来源和 Provider。

`effective_mode(context)` 只根据 `closed`、`enabled`、`mode` 返回
`disabled`、`observe_only` 或 `active`。其他插件的开关不参与模式判定。
观察模式仍记录规则状态，但不注入或自主发送。

## 消息与回复

真实消息经 AstrBotBridge 解析原生人格与来源；持久接受后投影状态、归档补课、
异步记忆及可选模型细化。临时状态块以 `livingemotion:state:v1` 唯一注入，
请求重入先清旧块。LivingHello 协作开关通过公开契约控制。

正常回复、补课和晚安共享当前来源、状态代际及配置复核；睡眠、新人消息和撤权
可以取消旧结果。首次提交占用对应唤醒窗口，原生提交不代表平台送达。
补课耗时只写 `livingemotion:wake_prepare_seconds`。
详细票据、补课上界和发送额度见[回复契约](internal-reply-contract.md)。

## 模型与数据

原生 OpenAI 与 router 指定上游使用共同输入、输出、并发和每日预算，
不发送 tools 或图片。Provider、人格、来源或水位改变时取消旧结果。
模式与授权校验保留；旧库导入及其额外生成限制已撤下。
行为历史只使用本插件的配额与意图，未知发送仍保守占用且不自动重发。

SQLite 保存事件、状态、关系、作息、体验、额度和意图。
`schema.py` 的自身版本迁移保留；不扫描或导入其他插件数据库。
来源类型 `legacy_unknown` 的体验在读取、查询、置顶和清理时保持七天硬期限。

## 接口与验收

管理页的配置、状态、记录及动作接口均由 PageAPI 验证当前 Dashboard 管理员。
前端自动刷新读取后端 DTO；仅磁盘文件读回不算配置生效。
消费者通过 `plugin.api` 查询能力与调用，不直接访问 store 或私有配置。

公开方法见 [api.md](api.md)，协作见 [consumers.md](consumers.md)，
本次验证见 [verification-local-runtime.md](verification-local-runtime.md)。
