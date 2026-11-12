# 五维情绪：四维计算、五维展示

日期：2026-11-12。范围：Bot 情绪的计算、展示与强度档位。
本文记录实现口径、配置入口与离线测试材料；不涉及真实模型调用或消息发送。

## 结论

- 运行期仍只算四维：`pleasure` / `arousal` / `stress` / `social_need`，
  本地规则、半衰期衰减、LivingHello 注入全部保持四维。
- 页面展示第五维「底气（control）」：只由异步情绪模型写入，
  **不参与本地规则、不参与衰减基准、不注入回复模型**。
- 新增情绪强度三档：`gentle`（保守 ×1.35）/ `normal`（平常 ×1.6，默认）/ `intense`（激进 ×2.0）。
  只放大单次增量与两道闸门，不改半衰期。
- 页面雷达由四轴改为五轴，并移除六种派生情绪的展示；
  「六维分析」文本块保留，日记、梦境、曲线、天气加成等内部逻辑不受影响。

## 计算逻辑

```mermaid
flowchart TD
    A[真实互动事件<br/>消息 / 回复成功] --> B[事件信号识别<br/>本地规则 + 第一人称自述]
    B --> C[规则增量求和<br/>× 置信度 × 强度增益]
    C --> D{单次上限<br/>0.15 × 增益}
    D -->|超出则裁剪| E[同类刺激窗口<br/>300 秒内累计上限 0.30 × 增益]
    E --> F[四维状态写回<br/>pleasure / arousal / stress / social_need]
    F --> G[半衰期回落到动态基准]
    G --> H[LivingHello 读取四维<br/>拼装回复上下文]

    I[异步情绪模型<br/>按间隔轮询] --> J[四维有界增量 ×0.5 权重]
    J --> F
    I --> K[底气 control 0–1]
    K --> L[EMA 平滑 0.2<br/>约等于最近 5 次样本]
    L --> M[60 分钟半衰期<br/>无新样本回落 0.5]
    M --> N[页面五轴雷达]
    F --> N
    G --> N

    style K fill:#fff3cd,stroke:#c9a227
    style N fill:#e7f4ea,stroke:#4f8a5b
```

模型返回的底气先按半衰期衰减到当前时刻，再以 0.2 的 EMA 写入；
`control_at` 与 `updated_at` 分离，写底气不会打断四维情绪的衰减时钟。
旧状态没有这两个字段时按中性 0.5 / 时间 0 处理，无需迁移。

## 维度与回落速度

| 维度 | 范围 | 中性/基准 | 什么情况下升高 | 什么情况下回落 | 半衰期 |
| --- | --- | --- | --- | --- | --- |
| 愉悦 pleasure | 0–1 | 0.5 | 被夸奖、收到关心与感谢、对方开心、承诺兑现 | 被侮辱、冲突、承诺失信、边界被侵犯 | 30 分钟 |
| 唤醒 arousal | 0–1 | 0.3 | 突发消息、冲突、被表扬、重要提醒 | 被安抚、道歉、稳定陪伴、长时间无刺激 | 20 分钟 |
| 压力 stress | 0–1 | 0.0 | 冲突、越界、承诺失信、对方焦虑 | 道歉、边界被尊重、被照顾、互动顺畅 | 40 分钟 |
| 社交需求 social_need | 0–1 | 0.3 | 对方难过/焦虑（想靠近陪伴）、冲突、被忽视 | 收到关心、感谢、回复成功、持续互动 | 60 分钟 |
| 底气 control（仅展示） | 0–1 | 0.5 | 模型判断 TA 此刻回应有把握 | 模型判断 TA 拿不准；无新样本时自然回落 | 60 分钟 |

`control` 的起点与终点都是 0.5，样本越少越接近中性；
它不会出现在 LivingHello 的注入内容里，也不影响任何回复生成参数。

## 强度三档

单次上限 = `0.15 × 增益`，同类刺激 300 秒累计上限 = `0.30 × 增益`：

| 档位 | 配置值 | 增益 | 单次上限 | 同类累计上限 |
| --- | --- | --- | --- | --- |
| 保守 | `gentle` | 1.35 | 0.2025 | 0.405 |
| 平常（推荐） | `normal` | 1.60 | 0.2400 | 0.480 |
| 激进 | `intense` | 2.00 | 0.3000 | 0.600 |

衰减半衰期与基准完全不变；换档只让「变化更快、更明显」，
不会让情绪长期停在极端值。

## 配置与页面位置

- AstrBot 管理面板 → 插件 → livingEmotion → 配置 → 情绪 → **情绪强度**。
- livingEmotion 页面 → 设置 → 情绪分组 → **情绪强度**（三档下拉）。
- 页面 → TA / 情绪页 → 五轴雷达；点击雷达下方问号展开
  「情绪与五维指标说明」，表内数值按当前档位折算。
- 生效方式：保存后重启 AstrBot（插件配置在启动时加载）。

## 测试材料

环境：macOS arm64，插件虚拟环境 `.venv`，Node 25.6.0；
全部为离线测试，无真实模型调用、无消息发送、无生产数据。

### 后端

```bash
cd 插件/astrbot_plugin_livingemotion
.venv/bin/python -m pytest -q
```

| 阶段 | 结果 | 说明 |
| --- | --- | --- |
| 实施前基线 | 28 failed / 1759 passed | 失败清单落盘 `/tmp/le_baseline_fail.txt` |
| 实施后 | 28 failed / 1761 passed | 新增 2 条底气/档位单测 |
| 失败清单比对 | 无新增 | `comm` 逐项比对，28 项均为既有失败 |

既有失败分布（与本改动无关）：`tests/verification/test_cross_module.py` 12 项、
`tests/budgets/test_runtime_budgets.py` 4 项、`tests/identity/test_projection_read.py` 3 项、
`tests/integration/test_proactive_runtime.py` 3 项、`tests/runtime/test_background.py` 2 项，
其余 4 项分别位于 contracts / integration / storage / performance_f6。

新增覆盖：

- `tests/domain/test_emotion.py::ControlTests::test_control_ema_decay_and_rule_independence`
  —— 规则事件不重置底气、无样本按 60 分钟回落。
- `tests/domain/test_emotion.py::ControlTests::test_intensity_presets_scale_deltas_and_gates_only`
  —— 三档只放大增量与闸门，半衰期不变。

### 前端

```bash
cd tests/ui
npm run build
npm test
```

- 构建：通过（仅打包本地 d3-force 依赖）。
- 单测：11 通过 / 1 失败；失败为既有的
  `energyPoints(nativeDTO.energy).collected === false` 断言，
  `native-dto.mjs` 中该字段实施前后均为 `true`，非本次引入。

### 契约与 DTO

- `tests/console/test_management_dto.py` 已同步 `control: 0.5` 基准与五维 DTO。
- `tests/ui/native-dto.mjs` 由 `npm run fixture:native` 重新生成（94 → 95 字段），
  新增字段为 `control`。

## 兼容性与边界

- 配置新增 `emotion_intensity`，旧配置缺省按 `normal` 处理；不改动旧键。
- 持久化新增 `control` / `control_at`，旧状态缺省 0.5 / 0，读写均向后兼容。
- `six_emotions()` 与日记、梦境、曲线、天气加成保持不变，仅移除页面展示。
- 底气是软件状态，不是心理测量；页面说明已注明不构成心理诊断。
