# 承诺内容拒绝后的主动反问

内容规则拒绝图片时，机器人主动在原会话问怎样调整，任务继续保持等待。追问使用固定文案，不增加模型请求。

> 这张没能弄好，有些内容我暂时做不了。你想换个人物、场景或风格再试试，还是这次就算了？

用户改过画面后再次被拒：

> 按你刚才改的想法又试了一下，还是没能弄好，有些内容我暂时做不了。我先停在这里。你想再调整一下，还是这次就算了？

拍照、自拍、画图共用这套反馈，不把拍照承诺一律说成“画”。补齐 `拍照`、`拍给你看` 的图片承诺识别，仍保留“提醒拍照”属于提醒而非代拍的原规则。

用户可见回应不用任务、接口、待办、服务或内部编号；LH 的其他失败说明也改成日常说法。文案与内部失败类别分开，换说法不改变限流和结果未知的处理规则。

## 执行逻辑

1. **即时失败**：LH 将明确问句与失败说明一起发送，确认成功后将 `adjustment_asked=true` 通过原交接接口交给 LE。LE 持久记录已问，不再重复；LH 也不追加第二条“记下/等待”说明。
2. **到期失败**：LE 将内容拒绝、画面、原任务恢复入口与 `waiting/held` 一起落盘，随后主动追问。崩溃或重启不会重新执行已被拒绝的画面。
3. **存量等待任务**：扫描 `content_rejected` 的等待记录，缺少追问记录时补问一次。其他失败类别不走调整追问。
4. **通知结果**：发送前原子占位；确认发出记 `sent`。明确 `rejected` 时五分钟后重试，最多三次发送尝试；不明结果记 `unknown`，中断留下的 `sending` 也不自动补发。暂时没有有效会话或被守卫拦下时，不消耗发送次数，并让出扫描位置。
5. **恢复任务**：受信用户新消息必须包含具体调整，且新画面与被拒画面不同。纯“嗯、好的、再试一次、继续”不能恢复；编号加重试口令也不能绕过。多条等待任务需要明确 ID、当前列表编号或完整原画面，否则返回歧义，交由正常回复询问。
6. **新阻塞轮次**：用户调整时递增内部 `adjustment_round`，失败后保留轮次，明确说明按新想法又试过，并让用户选择继续改或取消。旧轮次的迟到发送回执不能把新轮次标成已通知。
7. **真实取消**：选择算了、不拍了、不画了、不用了或不要了时，可将内容拒绝的 `waiting` 图片取消，停止后续通知和执行。多张图片未明确选择时先确认；取消用语不能被当作画面调整。运行中与未知结果的原有取消保护保持不变。

发送继续走既有 `send_promise_notice` 与发送守卫。新增可选 `authorize` 回调在发送前核对该任务仍在等待，避免用户已调整后还收到旧追问。限流沿用既有延期；结果未知、发送未知与接口问题仍需核对。图生图的原有恢复限制保持不变。

## 代码位置

| 文件 | 改动 |
|---|---|
| [storage/promise_store.py](../storage/promise_store.py) | 通知字段迁移；确认和取消口令过滤；调整轮次；通知回执；等待图片取消 |
| [runtime/promise_actions.py](../runtime/promise_actions.py) | 拍照/拍给你看识别；保留调整轮次与原承诺恢复入口 |
| [runtime/promise_service.py](../runtime/promise_service.py) | 等待扫描、生活化追问与发送结果处理 |
| [runtime/application.py](../runtime/application.py) | 可选发送授权、正常回复中的调整与取消 |
| [api.py](../api.py) | 保留 LH 已问回执、核实用户调整与图片选择 |
| [tests/integration/test_promise_adjustment.py](../tests/integration/test_promise_adjustment.py) | LE 60 项离线场景 |
| LH `images/guard_image_settings.py`、`guard_image_failure.py` | 生活化问句、已问回执、受控失败与重复说明移除 |
| LH `tests/test_promise_adjustment_notice.py`、`tests/promise_adjustment_handoff.py` | 7 项独立场景 + 1 项显式双插件门面验收 |

通知状态分别保存在 `adjustment_notice_state`、`adjustment_notice_attempt`、`adjustment_notice_retry_at`。它们是任务运行字段，不新增配置项，不改变任务对外的 `waiting` 状态，也不将通知计作图片交付成功。

## 升级与使用

完整即时失败交接需 **LivingEmotion 0.4.1 + LivingHello 2.7.8**，
并在 LH 中开启 LivingEmotion 接入、生图功能；LE 的承诺开关仍须开启。
两边升级并按宿主提示加载后，保留原配置、关系数据与生图额度。

旧库首次访问承诺表时自动增加三个通知字段，缺省为空、0、0。
已有 `content_rejected` 等待图片会在有效来源及发送守卫允许时补问一次；
其他等待原因不补问。升级前备份插件数据目录，保留数据库和相关代码以供整套回滚。
这三个字段是运行数据，没有新开关，无需手工编辑 SQLite。

例如“改成窗边穿外套的自拍”可作为新画面；“嗯，好的，再试一次”不能恢复。
选择“算了，不拍了”会取消内容拒绝的等待图片。多张等待时先明确是哪一张。
承诺描述、内部编号与运行类别不会直接拼进用户可见失败说明。

## 发布验证

以下均为 2026-11-18 发布代码的离线实测；模型和发送全部打桩，
LH 原有协议测试仅连接本地 HTTP 替身。

| 范围 | 结果 |
|---|---|
| LE 新矩阵 | 60/60 通过 |
| LH 新矩阵：7 项独立 + 1 项双插件实际门面 | 8/8 通过 |
| LE 原有相关回归 | Git 基线与发布代码均 91 通过、11 失败，失败名称一致 |
| LH 原有生图回归 | Git 基线 56/56；发布版同步更新 3 处旧发送预期后 56/56 |
| 真实模型、付费图片服务、真实聊天测试发送 | 0 次 |

LE 基线失败涉及旧提示文案断言与夹具的 `delivery` 参数兼容；
未在本版本扩范围修改，不能据此声称全量 CI 通过。
双插件实际门面用例固定隔离关系许可，确保确实触发内容拒绝；
冷启动等待预算为 5 秒，运行时关系核验的 0.5 秒预算不变，此用例不验收线上时延或平台已读。

在 LE 仓库根目录执行：

```bash
python -m pytest -q tests/integration/test_promise_adjustment.py
python -m pytest -q tests/integration/test_application.py tests/integration/test_promise_actions.py tests/integration/test_promise_contract.py
```

LH 的显式双插件命令与宿主快照要求见
[LivingHello 失败交接说明](https://github.com/AKIhunter/astrbot_plugin_livinghello/blob/main/docs/image-failure-followup.md)。
两仓库应作为同级目录，LE 目录名为 `astrbot_plugin_livingemotion`。
