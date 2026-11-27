# LivingEmotion 当前文档

适用0.11.1，2026-11-27核对。历史变更统一见[CHANGELOG](../CHANGELOG.md)；
旧测试报告仅证明当时范围，不替代当前代码或生产状态。

| 用途 | 权威入口 | 依据 |
| --- | --- | --- |
| 操作、开关、模拟与发送 | [使用手册](user-guide.md) | 实际页面、许可与动作 |
| 所有配置项默认、位置、范围与例子 | [配置参考](config-reference.md) | schema、Config、同源帮助与Console DTO |
| 模块、状态与功能判断流程 | [技术说明](technical-guide.md) | application、domain、storage、api |
| 九项情绪谱、对象采集与草稿刷新 | [情绪谱](ta-emotion-spectrum.md) | collector、DTO、规则边界与页面 |
| 掌控感、聊天表达与历史兼容 | [掌控感](control-integration.md) | 置信度、六项投影、表达策略和SQLite v9 |
| 保存冲突、不生成与不发送 | [排障](troubleshooting.md) | 校验、理由码与当前接口 |
| 导出近3天诊断包 | [诊断日志](diagnostics.md) | 受控采集、只读来源、管理员下载与清理 |
| 安装与宿主支持 | [安装](installation.md)、[兼容](compatibility.md) | metadata、宿主契约 |
| 可信插件与管理接口 | [API](api.md) | 实际注册端点与门面 |
| 承诺、去重、到期与取消 | [承诺](promise.md) | PromiseService、PromiseStore、宿主仲裁 |
| 图片映射与有限调整 | [映射](image-prompt-retry.md) | LH公开能力、LE修复模型与持久状态 |
| 精力、睡眠与票据 | [睡眠规则](sleep-energy-rules.md) | domain/night、runtime/night、storage/night |
| 模型、素材和体验 | [日记梦境](experience.md)、[记忆](memory.md) | 实际生成与来源许可 |
| 开发测试与显式宿主分层 | [交付分层](delivery-notes.md)、[独立运行](local-runtime.md) | pytest、宿主、浏览器与双插件入口 |
| 承诺重试、等待期限与取消 | [重试与收尾](promise-retry.md) | 配置预算、旧任务迁移和未知结果保护 |
| 早安避重与其他时段随机主动 | [定时问候让行](native-proactive-yield.md) | 宿主目标、UTC时间与±15分钟窗口 |
| 模型情绪输入精度与中文状态块 | [输入精度](prompt-precision.md) | 指定字段输出副本、原值阈值与消息体回归 |

每项文档由对应功能修改者维护；配置字段每次提交自动校验，其他操作与原理每次行为变更更新，
90天复核。超过周期或源码改变未更新时标记stale。README只作为当前产品入口。
