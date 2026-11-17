# 分阶段生图婉拒概率（0.4.0）

位置：LivingEmotion 控制台 → 设置 → 关系。五个概率分别平铺展示，
整数范围 0–100；0 表示不因关系随机婉拒，100 表示必定婉拒。

| 阶段 | 显示好感 | 配置项 | 默认婉拒概率 |
| --- | --- | --- | ---: |
| 反感 | 小于 11 | `relationship_image_refusal_averse` | 90% |
| 陌生 | 11 至小于 25 | `relationship_image_refusal_unfamiliar` | 60% |
| 友好 | 25 至小于 45 | `relationship_image_refusal_friendly` | 30% |
| 亲近 | 45 至小于 100 | `relationship_image_refusal_close` | 10% |
| 独特 | 管理员设置的 100 | `relationship_image_refusal_unique` | 5% |

这些是代码缺省值；升级保留存量显式配置。关系阶段自定义名称不改变各档数值边界。

## 生效范围

适用于个人生图请求和**新建**图片承诺，同一请求只判定一次。
已有图片待办继续履行；普通问答和文字提醒不使用此随机判定。
情绪影响表达语气，不直接改变这五个概率。

LivingEmotion 通过 `get_action_policy()`（`livingemotion.image-policy.v1`）
返回概率、关系档位与本次允许/婉拒结果，配套 LivingHello 通过公开接口读取。
没有兼容调用方时，
保存概率本身不代表所有生图工具已经受它控制。
图片功能开关、名单、额度与路由等其他守卫仍需分别满足，
将概率设为 0 不会绕过它们。

保存后离开设置再进入，核对读回值；页面自动刷新继续有效。
关闭图片功能应在 LivingHello 的对应功能配置中操作，
本页的概率用于调整关系婉拒行为。

## 配置与验证

`_conf_schema.json`、`Config.from_mapping()`、运行时概率输出、
配置保存校验和 UI 输入边界保持 0–100 整数的同一口径。
契约入口位于 `api.py`，跨插件读取见配套 LivingHello；
本版不会跨插件读取配置文件或 API Key。

延迟义务兼容测试见 `tests/integration/test_promise_actions.py`；
跨插件概率矩阵由配套 LivingHello 的测试入口验证，
不把承诺专项通过当作全部随机判定分支已经验证。
不使用真实付费生图来验证随机边界，也不把离线结果当作平台最终送达证明。
