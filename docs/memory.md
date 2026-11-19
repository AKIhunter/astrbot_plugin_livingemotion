# 身份、人格与记忆

适用0.6.0。设置入口：“设置 → 人格”和“设置 → 记忆”；
完整字段见[配置参考](config-reference.md)，调用签名以contracts.py与adapters/memory为准。

## 来源隔离

Context区分宿主实例、Bot、适配器、平台、场景、会话、账号、人格及修订。
人格共享只共享情绪/精力等状态，不能放宽私人正文或账号记忆授权。
PersonaAdapter统一解析原生人格；IdentityAdapter提供不可变身份快照，
写入和生成前后复核来源、修订及清除代际。
公域评论没有发送路由，不参与私人体验/主动发送的支持承诺。

## 记忆模式与开关

`memory_enabled`控制当前读取；`auto_memory_ingest_enabled`独立控制自动写入。
开启LivingMemory接入时只调用其公开接口，按已授权会话、请求和用途核对；
关闭接入使用本地向量路径，embedding_provider_id选择原生向量模型。
不把聊天模型当向量模型，不在后台直接读取另一插件配置或私有库。

| 模式 | 能力与边界 |
| --- | --- |
| LivingMemory | 使用当前提供者公开能力；不支持后台检索/幂等导出时明确unsupported |
| local_vector | 本地索引和向量模型；写入、维度/模型指纹与召回分别核对 |
| local_lite | explicit_memory.sqlite3中的显式记录；没有用户录入页面或自动事实抽取承诺 |

开启模式不等于模型或索引已就绪。`local_lite`是兼容端口，
没有公开HTTP写入动作。管理同步见[API](api.md)，能力不足不换事件ID盲重放。

## 材料、授权与保留

EvidenceRef保留原source_ids、Context、主体/持有者、时间、有效期、
敏感/可导出标记与authorization。提供者凭据须最终复核；
“admin”字符串、旧缓存或公开来源不能授予私人读取。
日记、梦、摘要、记忆和未知历史只能作为材料，不能伪造成新互动刺激。
MaterialResolver按请求/用途去重并控制输入大小；索引召回是候选，不保证模型理解。

当前对话自动记忆与私人体验档案分开。私人日记/梦保留在LE，不自动同步其他记忆库；
明确同步操作按提供者实际能力返回状态。清除上下文改变代次，迟到生成不能写回。
模型输入部分限额按UTF-8字节计算，不代表账单Token。

## 升级与核验

升级保留配置、SQLite和索引。切换向量模型前核对维度、指纹及是否需重建；
不能直接复用不兼容索引。故障先看capabilities、reason_code与memory_sync结果。
测试入口见[交付检查](delivery-notes.md)，历史接入证据见[更新日志](../CHANGELOG.md)。
