# surprise 基线修复：回归材料

日期：2026-11-12。开发者：[AKIhunter](https://github.com/AKIhunter)。
使用说明与流程图见 [插件帮助手册](plugin-manual.md)、
[情绪计算及标签流程](emotion-five-dimension.md#页面标签与兴奋口径)。

## 问题与修复

旧公式将正常唤醒水平也计入 surprise。阴天六情绪各加 0.1 后，平静状态
容易被页面映射为「兴奋」。新公式仅计算唤醒超出基线的部分：默认基线 0.3，
已细化的完整状态使用 `baseline_arousal`。

四维原始状态、天气加成、0.25 标签阈值和另外五种派生情绪公式不变。
受影响的消费者为当前标签、六情绪曲线、日记和梦境基调。
存量历史采样未保存动态基准，历史重算使用默认 0.3。

## 场景矩阵（离线实测）

所有模型、天气和发送链路使用合成替身；不访问真实模型或平台。

| 输入 | 原公式的阴天标签（离线复算） | 新控制台标签（离线实测） |
| --- | --- | --- |
| 默认平静：p=0、a=0.3 | 兴奋：surprise=0.18+0.1 | 平静：surprise=0+0.1 |
| 采集样本：p=0.0361、a=0.3483、基线=0.3145 | 兴奋：surprise≈0.3046 | 平静：surprise≈0.1199 |
| 动态基准抬高：a=0.6、基线=0.6 | 兴奋：surprise=0.36+0.1 | 平静：surprise=0+0.1 |
| 实际高唤醒：p=0、a=0.9、基线=0.3 | 兴奋 | 兴奋：surprise=0.36+0.1 |

采集样本新公式下最大项为 affection≈0.2103，低于 0.25。
以上小数为公式离线推算；标签断言由真实 `Console._attach_emotion_curve` 路径执行。
回归同时检查两个展示位置采用相同六情绪结果，并且标签投影不写回输入状态。

## 测试结果（本地实测）

| 检查 | 修复前记录 | 修复后 |
| --- | --- | --- |
| 定向 emotion / dream_paper / console_simulation | 前轮 92 通过（已含 surprise 单测） | 本轮 96 通过 |
| 后端可移植全量 | 1761 通过 / 28 失败 | 1766 通过 / 28 失败 |
| 失败集合差分 | 保存原 28 项清单 | 新增 0、消失 0 |
| UI 构建 | 通过 | 通过 |
| UI 单元 | 11 通过 / 1 失败 | 11 通过 / 1 失败 |

定向前轮数字已包含 surprise 单测，本轮新增四组控制台标签回归；
全量修复前数字沿用本次改动前保存的测试记录。
UI 失败仍为 `tests/ui/model.test.mjs:73` 对 energy collected 的旧断言
（实际 true、预期 false），与本次 surprise 无关。
28 项后端既有失败没有被本次修复消除，也没有被算作通过。

新增回归位于 `tests/experience/test_dream_paper.py`：

- `test_surprise_counts_only_arousal_above_baseline`：平静为零、随增量增加、
  动态基准生效、阴天加成不误越过阈值。
- `test_cloudy_console_label_uses_arousal_increase`：四组参数检验完整页面标签路径。

UI 合成夹具 `tests/ui/native-dto.mjs` 从真实 Console 重新导出，
将旧 surprise 数值同步为新公式，并更新采集时间。

## 复现命令

从插件根目录使用已安装开发依赖的虚拟环境执行：

```bash
.venv-ci/bin/python -m pytest -q tests/experience/test_dream_paper.py tests/domain/test_emotion.py tests/behavior/test_console_simulation.py
.venv-ci/bin/python -m pytest -q
npm --prefix tests/ui run build
npm --prefix tests/ui test
git diff --check
```

完整 pytest 和 UI 单元当前会因上述既有失败返回非零；
回归判断应比较逐项失败集合，不能只比较失败总数。
部署结果单独记录在工作区交付报告，包含逐文件 SHA-256、备份、
服务巡检和运行态接口读回；本文件不包含环境地址、私聊数据或凭据。
