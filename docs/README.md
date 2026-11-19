# 文档入口

当前版本0.4.3；维护者AKIhunter，2026-11-19按当前源码与离线验收核对。
每种用途只保留一个权威总入口，**不重复维护同一份完整说明**。
专题用于展开细节；标记历史的报告仅说明当时结果，不能覆盖当前操作、配置和算法。

## 从需求找到文档

| 文档 | 类型 | 读者 / 用途 | 事实来源 | 核对与更新 |
| --- | --- | --- | --- | --- |
| [使用手册](user-guide.md) | tutorial / how-to | 用户；首次使用、32个开关、日常操作 | schema、页面、运行守卫 | 2026-11-19；每次功能/许可/页面变化及发布 |
| [配置参考](config-reference.md) | reference | 管理员；101个非开关参数、默认值、单位 | config、schema、帮助与校验 | 2026-11-19；每次字段/默认/校验变化及发布 |
| [技术说明](technical-guide.md) | reference / architectural | 开发者；模块、状态、契约、迁移 | runtime、domain、storage、API | 2026-11-19；每次契约/存储/路由变化及发布 |
| [原理示例](principles-examples.md) | explanation | 用户/开发者；确定性算例与边界 | 领域公式、离线回归 | 2026-11-19；每次规则变化及发布 |
| [排障](troubleshooting.md) | how-to / operational | 管理员；保存、状态、任务与恢复 | 回执、原因码、业务守卫 | 2026-11-19；每次故障修复及发布 |
| [安装](installation.md) | tutorial | 安装者；入口与升级检查 | metadata、宿主发现规则 | 当前安装部分随入口/兼容变化及发布核对 |
| [API](api.md)及internal契约 | reference | 可信插件/页面开发者 | 当前源码签名和DTO | 每次接口变化核对；早期枚举按历史标记阅读 |
| [交付分层](delivery-notes.md) / verification报告 | reference / historical | 维护者；复测入口与历史证据 | 各报告对应的测试结果 | 历史数字冻结，不当作当前/生产验收 |

责任路径统一为AKIhunter/对应代码改动维护者。每次发布复核当前五份总入口与相关专题；
距最后核对超过90天，或依赖源码变化未同步时标为待核对。历史报告保留来源与适用版本，
不提升为当前操作规范。CI校验文档链接、版本、配置覆盖和默认值，文档与代码一同提交。

## 当前专题

- 情绪：[四维与底气](emotion-five-dimension.md)、[开心窗口](joy-window.md)。
- 关系：[好感V2](relationship-scoring-v2.md)、[生图婉拒](relationship-image-refusal.md)。
- 睡眠：[状态、精力、补觉与在途回复](sleep-energy-rules.md)。
- 任务：[承诺](promise.md)、[宿主未来事件](future-tasks.md)、
  [承诺记忆](promise-memory.md)、[延迟动作](promise-actions-20261116.md)、
  [图片调整](promise-adjustment-20261118.md)。
- 主动：[选题、节奏与守卫](proactive-life.md)。
- 协作：[API](api.md)、[LivingHello协作](cooperation-contract-20261116.md)、
  [状态](internal-state-contract.md)、[管理](internal-console-contract.md)、
  [记忆](internal-memory-contract.md)、[回复](internal-reply-contract.md)。
- 兼容：[宿主矩阵](compatibility.md)、[本地运行/升级](local-runtime.md)、
  [CI](../.github/workflows/ci.yml)、[CHANGELOG](../CHANGELOG.md)。

## 旧入口与历史材料

[plugin-manual.md](plugin-manual.md)保留为新五份文档的导航；
architecture、life-console等旧总览也保留链接兼容，但当前总入口优先。
FOUNDATION/DOMAIN/INTEGRATION/CONTRACTS、早期night/behavior/console/ui阶段文档、
verification系列、带日期的修复报告和ui-progress是阶段说明或历史证据。
它们的旧默认值、测试数字、早期端点数量或未接能力描述不能替代当前源码与五份文档。
其中当前专题链接仍可用于细节，但出现冲突时以当前源码和新总入口为准，并修正对应专题。
