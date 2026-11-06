# T11 新独立宿主阶段证据

日期：2026-11-05。标签：`final-independent-v2`。
本验收者未参与产品实现，只改独占 final 测试及脱敏验收文档。
本文件是冻结前窄复验，不是最终三场景验收，不是生产投递验证。
父修订的 C30/F13 将无可靠原生回执场景列为明确不可用且有界取消收尾。

## 实际命令与结果

均从 `$WORKSPACE` 运行；固定隔离 AstrBot v4.29.4，
HEAD `61335414433db721b3f7ecc93f90deafe0a59d78`，不调用 Git、不重建环境。

```bash
.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_c30_contract.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs

.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist \
  --scenario four --focus h01-h03-c30

.livingemotion-host-t1/venv/bin/python3.12 \
  插件/astrbot_plugin_livingemotion/tests/host/final_run.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --dashboard-dist .livingemotion-host-t1/final-dashboard/dist \
  --scenario single --focus c30
```

| 运行 | 结果 | 层次 |
| --- | --- | --- |
| `final-c30-contract-k1twarqq` | 49 PASS / 0 FAIL，exit 0 | 真实宿主类、合成 listener 和平台口，无产品实例 |
| `final-h01-h03-c30-four-u75159c6` | 57 PASS / 0 FAIL，exit 0，15.296s | 真实四插件实例、原生 pipeline、合成 Provider/发送口 |
| `final-c30-single-yl7oro9e` | 51 PASS / 0 FAIL，exit 0，13.553s | 真实产品、原生 RespondStage/aiocqhttp 事件、合成平台口 |

四插件真实实例：

| 注册名 | 真实类 |
| --- | --- |
| `astrbot_plugin_livingemotion` | `data.plugins.astrbot_plugin_livingemotion.main.LivingEmotionPlugin` |
| `astrbot_plugin_at_guard` | `data.plugins.astrbot_plugin_at_guard.main.Main` |
| `astrbot_plugin_livingmemory` | `data.plugins.LivingMemory.main.LivingMemoryPlugin` |
| `astrbot_plugin_bilibili_ai_bot` | `data.plugins.BiliBot.main.BiliBiliBot` |

单插件场景只加载 LivingEmotion 与宿主内建 `builtin_commands/astrbot`；
不是把 fixture registry 当作成品实例。

## H 问题与 C30

- H01 原公开 `get_relationship` 断言通过，`api_version=1/status=ok/reason_code=snapshot`。
- H02 保留原 `get_state` 抛 `OSError` 反例，真实九阶段 pipeline 中合成模型口 1 次、
  回复口 1 次、状态块 0 份；正常路径仍为 1 次模型口、1 次回复口、1 份状态块。
- H03 保留原生管理员配置及断言：`is_admin=true`、`control_request=admin`、
  `stopped=false`，模型口和发送口各 1 次；普通睡眠阻断及原生叫醒仍通过。
- C30 固定宿主 RespondStage 捕获发送异常后仍触发 after-sent；
  原生 aiocqhttp 发送方法丢弃平台消息 ID。`None/False/成功/部分成功` 均可能
  `has_send=true`，因此 hook/标记/布尔返回/response_sent trace 都不是完整成功凭据。
- 成品联合验证中 `None/False/发送异常/平台返回消息ID被丢弃` 四例，
  真实 after-sent 各调用一次，产品全部保持 settling。
- 每例 `transition_deadline - updated_at == 120`；只推进 Store 受控时钟至 deadline+1，
  返回清醒/困倦并清空等待 ID，不真实等待两分钟。再推进相同窗口不重入 settling，
  合成平台回复尝试保持 1 次、主动发送口尝试 0 次。
- 无 pending 的直接计划睡眠、手动睡眠仍入睡。两者不是伪造回复成功。
- 原 typed receipt 的错消息、其他范围、unknown、failed 和新增 cancelled 均不入睡；
  匹配 succeeded 可以入睡，但仅为直接 Application 端口组件证据。
  超时后的迟到成功不能再次入睡。
- 此时新插件 after-sent 注册仍为空。原生成功回执能力应明确 unavailable；
  F13 展示接线尚未验证，不能将修订 C30 整项标为 PASS。

## 源码与隔离

每轮 `source_before` 是运行时独立拷贝的逐文件 SHA-256，
运行后 `C03.source_unchanged` 通过。测试脚本哈希在同一报告。
以下摘要算法为选取 `astrbot_plugin_livingemotion/` 前缀后的 JSON 对象，
`jq -cS` 输出含末尾换行，再取 SHA-256。

| 运行 | 产品源码摘要 |
| --- | --- |
| H 窄复验 | `b5ad39e54c1f335983a9b3d3ba2301536a564cc55919c4df27b787e99cbf285a` |
| C30 成品窄复验 | `d5821dbe441406c7a103ada7f9557d4f660193512fbb5fc8c67be5c7989abfb4` |

两轮之间仅 `storage/sqlite.py`、`runtime/projector.py` 改变；
这是 F6 并行实现的新快照，不是完整冻结 hash。不可把不同 hash 的通过数拼成最终结果。
宿主契约探针报告另记录六个真实宿主文件及自身脚本哈希，不将它当产品 hash。

运行使用新 `ASTRBOT_ROOT`，空模型/外部平台配置；合成身份/消息/随机测试凭据。
契约探针无外联尝试；H 轮 4 次、C30 轮 3 次非回环 DNS 被 audit hook 拦截。
三轮实际放行外部调用、真实模型调用、真实平台投递均为 0。
保护为 Python audit hook 和显式合成发送口，不宣称 OS 沙箱或真实平台投递。
宿主子进程已退出，产品停止后任务 0、数据字节无迟到写回。

## 本轮逐项边界

PASS 仅指本轮列明的风险检查；其余沿用历史记录但不冒充本轮复验。

| C项 | 本轮结论 | 限制或后续 |
| --- | --- | --- |
| C01 | PASS，窄范围 | 无旧插件的真实单实例加载；最终三场景仍待冻源 |
| C03 | PASS | 四实例中三次 reload 单任务、停用无写回 |
| C04 | 部分 PASS | 固定宿主加载/发送契约核实；本轮没有页面测试或真实投递 |
| C05 | PASS，窄范围 | 原生人格一次、Bot 来源与人格分离 |
| C06 | 待最终复验 | 本轮未执行生成人格切换；历史原断言保留 |
| C08 | 部分 PASS | trace/唯一状态块已验；模式/总开关等最终矩阵再跑 |
| C18 | 待最终复验 | 三种记忆模式不在本轮窄范围 |
| C19 | 限制 | 真实外部检索/导出未执行；最终补启用开关后的拒后台检查 |
| C20 | 限制 | LivingMemory 真实例已加载，不等于真实后台来源接口可用 |
| C21 | 限制 | 无真实外部材料/授权凭据正例 |
| C27 | 限制 | 未执行外部幂等导出；不能用 unsupported 替代成功正例 |
| C30 | 部分 PASS | 宿主不可确认、120秒安全取消、不重发已验；待 F13 能力展示 |
| C31 | PASS，H03 范围 | 显式睡眠阻断、真 admin 豁免、原生命令叫醒 |
| C35 | 限制 | 使用合成事件验证的原生 UMO；未投递真实平台，裸账号拒绝留组件专项 |
| C39 | PASS，读取门面范围 | H01 与其余公开读取通过；Bili 上报留最终组合轮 |
| C40 | 待最终复验 | 本轮不执行消费者新旧选择切换 |
| C41 | 待最终复验 | 桥失败与 Bili 本地写者保持原历史证据 |
| C42 | PASS，普通文本限定 | 四真实实例九阶段、唯一状态/回复；图像/TTS 不外发 |
| C43 | 待最终复验 | 本轮不跑从绫 conflict |
| C44 | 待最终复验 | 本轮不启动 HTTP/浏览器 |
| C45 | 待最终复验 | 配置/刷新/CAS/10条交最终 HTTP/浏览器 |
| C46 | 待最终复验 | F1 全矩阵保留原断言，未在本轮重跑 |
| C47 | 待最终复验 | 原28布局证据保留，不计本轮 |
| C48 | 待最终复验 | 页面模拟/无CDN交最终浏览器 |
| C52 | PASS，H02 范围 | 普通聊天无额外模型、读故障省略状态且继续聊天 |
| C53 | 部分 PASS | 导出证据无凭据/个人路径；完整日志关联与私密正文检查未重跑 |
| C58 | 待最终复验 | 原25→25保留；最终 hash 变更后复跑隔离回退 |
| C64 | 待最终复验 | 本轮没有重做视觉验收 |
| C65 | 限制 | 原生 iframe 存储不可用；历史双主题/临时偏好/回退证据保留 |

## 证据与下一步

脱敏文件：`tests/host/final_evidence/<运行ID>/host.json` 与 `manifest.json`。
原始 `report.json/runtime.log` 和配置仅留 `.livingemotion-host-t1/runs/<运行ID>/`，
不修改、不交付原始凭据或个人路径；旧 207/2、38/40 浏览器、28布局等记录不覆盖。

最终入口环境已检查在位：原固定 Python、Dashboard dist、Playwright 和 Chrome，
没有重新安装。收到 core/F6 双 freeze 后，记录同一源码 hash，再顺序执行原
single/four/conflict 三场景，至少一个启用 `--browser`，不带窄复验 `--focus`。
缺失回执能力的展示接线先由核心完成；验收者不改产品，不用 after-sent 造成功。
