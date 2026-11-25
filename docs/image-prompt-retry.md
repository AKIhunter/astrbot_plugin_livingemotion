# 图片承诺的提示词调整

适用 LE 0.8.0 / LH 2.10.0。原 SQLite 任务、状态和额度保留；
候选、原文和计数写入原动作结果字段，旧任务没有新字段时按零次调整恢复。

LH 拥有映射表、实际生图连接、额度和成功词语账本。
LE 只通过 `livinghello.image-prompt-mapping.v1` 契约取得长度与模型范围，
使用自己的 `closing` 收尾模型提议局部等义替换，再由 LH 校验。
详细格式见配套 LH 的 `docs/image-prompt-mapping.md`。

明确内容拒绝与超长描述才调整；LH次数0–10、默认2，LE自动重试0–10、默认5。
实际调整次数取LH限制与LE剩余预算的较小值，延迟重试共用LE预算；任一端设0关闭自动改词。
`get_image_prompt_retry_policy` 告诉 LH 当前 LE 是否能接手，旧版或未开启兑现时沿用用户调整询问。
handoff 只给同一义务添加恢复状态，不重复创建承诺。
即时请求有明确promise_id时先领取原事项，再按image-result.v1结算，
确定可调整失败300秒后沿原执行链重试；没有ID的新图不完成其他旧任务。

| 状态 | 恢复规则 |
|---|---|
| retry_ready | 恢复已落盘候选或提出有限局部调整 |
| generating / sending / unknown | 禁止重新生成，先核对未知结果 |
| generated | 只发送已有图片 |
| held / waiting | 等待用户明确调整或取消 |
| sent / cancelled | 不再执行 |

每次改词增加 `prompt_retry_count`；事件 ID 和模型预算键同时包含用户调整轮次与尝试编号。收费前先落 `generating`，同轮重放去重；用户 A→B→A 属于新的合法轮次。
模型提出改变姿势、表情、年龄、场景等建议时，不生图，发送确认说明。
原画面保存在 `original_prompt`，实际尝试文字保存在 `attempted_prompt`。
用户明确修改后沿用同一 promise_id，清除旧候选并重置新画面的调整预算。
额度不足、配置错误不消耗额外生图；超时、丢失回执、投递未知不重新生图。
等待/未知默认24小时后结束，可在LE设置1–168小时；页面与聊天可取消后续处理。
自定义映射表、全局生图风格和学习数据库留在本地，不包含在源码提交中。

本版验证为离线确定性矩阵：真实承诺 SQLite 与 LH 映射器，模型、图片接口和宿主发送全打桩。
不将离线通过表述为实际上游内容检查通过。

## 离线复测

此矩阵需配套 LH 源码，独立默认 pytest 不收集该文件；CI 显式检出固定 LH commit 并运行，
缺依赖直接失败，不用 skip 冒充通过。先准备 LE 常规测试环境，再从 LE 根目录执行：

```bash
LIVINGHELLO_SOURCE="/path/to/astrbot_plugin_livinghello" \
  python -m pytest -q -o addopts="-ra --strict-markers" \
  tests/integration/test_image_prompt_mapping.py
```

环境变量指向 LH 源码根目录，须包含 `images/guard_image_prompt.py`。相邻源码目录也可自动识别。
全部模型、生图和发送接口使用测试替身，与独立可移植回归分别统计。
