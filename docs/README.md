# LivingEmotion 当前文档

适用0.6.0，2026-11-19核对。历史变更统一见[CHANGELOG](../CHANGELOG.md)；
旧测试报告仅证明当时范围，不替代当前代码或生产状态。

| 用途 | 权威入口 | 依据 |
| --- | --- | --- |
| 操作、开关、模拟与发送 | [使用手册](user-guide.md) | 实际页面、许可与动作 |
| 所有配置项默认、位置、范围与例子 | [配置参考](config-reference.md) | schema、Config、同源帮助与Console DTO |
| 模块、状态与功能判断流程 | [技术说明](technical-guide.md) | application、domain、storage、api |
| 保存冲突、不生成与不发送 | [排障](troubleshooting.md) | 校验、理由码与当前接口 |
| 安装与宿主支持 | [安装](installation.md)、[兼容](compatibility.md) | metadata、宿主契约 |
| 可信插件与管理接口 | [API](api.md) | 实际注册端点与门面 |
| 承诺、去重、到期与取消 | [承诺](promise.md) | PromiseService、PromiseStore、宿主仲裁 |
| 图片映射与有限调整 | [映射](image-prompt-retry.md) | LH公开能力、LE修复模型与持久状态 |
| 精力、睡眠与票据 | [睡眠规则](sleep-energy-rules.md) | domain/night、runtime/night、storage/night |
| 模型、素材和体验 | [日记梦境](experience.md)、[记忆](memory.md) | 实际生成与来源许可 |
| 开发测试与显式宿主分层 | [交付分层](delivery-notes.md)、[独立运行](local-runtime.md) | pytest、宿主、浏览器与双插件入口 |

每项文档由对应功能修改者维护；配置字段每次提交自动校验，其他操作与原理每次行为变更更新，
90天复核。超过周期或源码改变未更新时标记stale。README只作为当前产品入口。
