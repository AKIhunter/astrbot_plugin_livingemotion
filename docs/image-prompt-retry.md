# 图片承诺的提示词调整

新流程适用 LivingEmotion 0.12.0 与 LivingHello 2.11.0。

LE 管承诺、到期、取消、等待和结案。LH 从承诺意图起草图片描述，负责映射、调整、生成和投递回执。
LE 通过 `livinghello.promise-image.v2` 传递原需求、会话上下文和重试预算，并保存 LH 返回的执行进度。
提示词模型和额度在 LH → AI生图配置。旧生图配置首次需要起稿或改词时，LE 只提供一次旧模型 ID 和
每日上限供 LH 迁移，不代调用。迁移优先级为收尾模型、LE 通用模型（两者均空才取 AstrBot 会话模型）、旧备用模型。
后续 LE 更改设置不会影响 LH 的迁移结果。LE 的收尾模型仍负责自己的晚安和承诺文案。
原 SQLite 任务与配置保留，执行进度继续存放在原动作结果字段。

| 配套情况 | 新建或尚未生成的图片承诺 |
|---|---|
| 双方支持新契约 | 由 LH 执行，LE 跟踪原事项 |
| 新 LE 搭配旧 LH | 已可发现旧接口时保留并推迟任务，不烧重试预算 |
| 旧 LE 搭配新 LH | 原入口仍可调用，沿用旧流程 |

已生成并存盘的旧图片仍按原投递契约处理。
LH 的调整次数（0–10，默认 2）与 LE 剩余重试预算（0–10，默认 5）取较小值。
明确限流会推迟原事项，已保存的描述继续复用；内容拒绝后，LH 不发送已经拒绝过的措辞，包括映射后变回原句的候选。
需要改变画面、没有可用调整或次数用尽时，等待用户明确修改或取消。
即时图片的文字和图片顺序不变；已有承诺 ID 的回执仍结算原事项。

| 状态 | 恢复规则 |
|---|---|
| retry_ready | 用已落盘的进度继续，已准备的候选可复用 |
| 起稿或改词中止 | 保留原承诺，提示用户补充画面；已派发的文本请求不自动重发 |
| generating / unknown（生图） | 暂停并保留原请求 |
| generated | 发送已有图片；明确拒收时仍用原图 |
| sending / unknown（投递） | 有 LH 确认回执就补记完成，无回执就继续等待核对 |
| held / waiting | 等待用户明确调整或取消 |
| sent / cancelled | 不再执行 |

平台确认发送后，LE 在一个事务内更新承诺和交付事实。
如果这一步中断，恢复只读核对 LH 的原请求回执，不会再次发图。
用户明确修改后沿用同一 `promise_id`，重置该画面的候选和调整次数；仅说“再试一次”不重置。
等待/未知默认24小时后结束，可在LE设置1–168小时；页面与聊天可取消后续处理。

## 离线复测

完整矩阵需包含 `images/guard_promise_image.py` 的 LH 源码。默认 pytest 不收集此矩阵；
CI 固定的旧 LH 用于验证兼容门面，完整矩阵在双方新源码配套时单独运行。
先准备 LE 常规测试环境，再从 LE 根目录执行：

```bash
LIVINGHELLO_SOURCE="/path/to/astrbot_plugin_livinghello" \
  python -m pytest -q -o addopts="-ra --strict-markers" \
  tests/integration/test_image_prompt_mapping.py
```

用固定 AstrBot 源码还可验证真实 `CronMessageEvent` 和两端 SQLite，包括平台已确认但 LE 尚未记账的恢复：

```bash
ASTRBOT_NATIVE_SOURCE="../AstrBot/astrbot" \
  python -B tests/host/promise_actions_native.py --livinghello ../astrbot_plugin_LivingHello
```

模型、生图和平台发送均使用测试替身。
