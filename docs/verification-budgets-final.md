# C50/F8 与 C22/F9 独立最终预算复验

状态：**本专项已完成并释放，不等待第二轮存储冻结。**
最后一次测试结束于 2026-11-05 22:04:27 UTC。
仅修改 `tests/budgets/` 与本文；未改产品、父规格、
`verification-performance.md`，未执行 Git、全量测试或性能 benchmark。
复用已存在的 host Python 3.12 和 pytest 依赖，未安装依赖。

## 结论

| 检查项 | 独立结果 | 生效边界 |
| --- | --- | --- |
| F8 | **PASS** | 冻结 background/models；原两个反例及 53 项窄回归全部通过 |
| C50 | **31/31 PASS** | Runtime 15 + 真实 Provider 16；最后一轮 F8 命令也完整执行这 31 项 |
| F9 | **已测快照 PASS；新存储快照未验** | 三个静默 scope 物理条数 `[2,2,2]`；随后 sqlite/projector 已改变 |
| C22 | **原窗口预算 11/11 PASS；整项不放行** | 容量、TTL、引用检查通过；新存储快照、迁移正文与默认满窗口边界见下文 |

C51 独立性能失败不终止本份授权。上述结果不代表 C51、宿主全套或最终产品发布通过。
父最新指示为：交付当前预算实测，不等待 sqlite 全 hash 冻结；后续 core 全套覆盖 portable
预算。本专项不勾父清单、不追加重型基准。

## 给父任务与 Docs 作者的接入通知

普通 CI 继续包含可移植 runtime/window 预算，不忽略整个 budgets。
宿主专属 `test_model_payload.py` 保持独立显式 runner：

```bash
python tests/budgets/run_evidence.py --lane all \
  --host-source "$ASTRBOT_HOST_SOURCE" \
  --output tests/budgets/evidence/budgets-new-label.json
```

`ASTRBOT_HOST_SOURCE` 必须指向已准备的 AstrBot 源码根目录，也可通过环境变量传入。
runner/fixture 不再推导工作区私有 `.livingemotion-host-t1/AstrBot`。
缺宿主或 SDK 明确失败，不 skip；普通 portable lane 不导入宿主或 SDK。
JSON 仅记录相对源码/测试路径、版本、合成计数，不记录本地绝对路径或请求正文。

| 层 | 原有数量 | 执行范围 |
| --- | ---: | --- |
| `all` | 44 | Runtime 15 + Provider 16 + 窗口 11 + 计量口径 2 |
| `portable` | 28 | Runtime 15 + 窗口 11 + 计量口径 2 |
| `provider` | 16 | 真实 Provider/SDK + HTTPX MockTransport |
| `window` | 11 | 临时 SQLite、实际 API/Projector、物理正文计数 |
| `f8` | 53 | 原 F8 runtime + runtime/provider budgets 窄回归 |
| `transport` | 原 Provider 16 + 补充 1 | Runtime 直接到真实 Provider 的取消补充 |
| `runner` | 新增 13 | 收集/跳过/环境与 F9 精确物理计数门禁自检 |

显式覆盖 `pyproject.toml` 的 `addopts` 和 `PYTEST_ADDOPTS`，禁止 pytest 缓存，
固定加载现有 asyncio/timeout 测试插件。每层记录收集数、选择数、执行数、
每阶段状态和源码前后 SHA256；少收集、skip、未执行 call、源码漂移均不能整层通过。
`-k` 仅为定位运行，永不宣称完整 lane 通过。旧 JSON 不覆盖。

当前无可用 agent 消息接口，以本文通知父任务和 docs 作者消费上述分层契约。
新增 `provider_cancel_probe.py` 不符合普通 CI 测试文件名，仅显式 runner 运行。
原三个测试文件保持原 SHA256，普通 CI 另外收集 portable runner 自检。

`all`、`f8`、`transport` 实际导入的 Provider 文件均与指定宿主根目录匹配，
JSON `provider_loaded_from_selected_host=true`。宿主 hash 不再来自另一条硬编码路径。
`portable` 和 `runner` 实测 `host_modules_loaded=false`；即使给 portable 一个不存在的
宿主路径，也完整执行 28 项。此为 host Python 上的无宿主导入证明，不冒充远端 CI 结果。

## 窄门禁

SEM 主专项：`testing-and-quality-gates`，高置信度。
依据父 `spec.md` R5/R11、`checklist.md` C22/C50、原性能报告命令及取消交接。

| 风险 | 阻断条件 | 失败响应 |
| --- | --- | --- |
| caller 取消未传播 | 原 work / Provider transport 取消数不为 1、记 succeeded | 留证报父，继续不相关预算 |
| 配额绕过 | 并发、队列、Token、用途/全局额度或跨重启断言失败 | 不放行 C50，不修改门槛 |
| 正文未清理 | F9 三个静默 scope 物理计数不为 `[2,2,2]`、TTL/引用失败 | 不放行 F9/C22 |
| 门禁漏测 | 收集数不符、skip、call 未执行、源码漂移 | 分类为基础设施/快照问题，不假绿 |

只用合成输入、禁 socket fixture/审计钩子、自动清理临时 SQLite。
原三个测试文件断言与阈值保持不变；F9 增加证据层精确 `[2,2,2]` 校验。
不使用缓存结果。无 CI 历史 p95，因此不虚构运行时基线；保留原每例 60 秒 timeout，
记录各次总时长。关键反例覆盖目标 3/3，并非全产品覆盖率。
任一次失败均保留；复跑不一致作为 flake 报父，48 小时内处理，不用择优重跑放行。
静态/安全/依赖扫描和发布前全套不属于本授权范围。

## 实际执行与证据

环境确认：CPython 3.12.16、pytest 8.4.2、pytest-asyncio 1.2.0、
pytest-timeout 2.4.0、OpenAI SDK 3.46.0、HTTPX 0.28.1、AstrBot 4.29.4、
SQLite 3.53.1、macOS 15.6.1 arm64。唯一宿主 warning 为 audioop 弃用提示。
未安装或修改依赖，未使用普通 CI venv 冒充此宿主环境。

下表时长为 pytest 终端报告；JSON 另记包含初始化/清理的 elapsed_seconds。
各成功行 collected=selected=executed=call_executed，0 failed、0 skipped；
测试集合相互重叠，不能相加宣传独立覆盖数。

| 证据 | 实际收集/执行 | pytest 时长 | 退出码 |
| --- | ---: | ---: | ---: |
| [完整原预算](../tests/budgets/evidence/budgets-final-20261105-01.json) | 44/44 | 10.13s | 0 |
| [最终 F8 窄回归](../tests/budgets/evidence/f8-final-20261105-01.json) | 53/53 | 8.53s | 0 |
| [真实 transport 补充层](../tests/budgets/evidence/transport-final-20261105-01.json) | 17/17 | 12.28s | 0 |
| [可移植原预算层](../tests/budgets/evidence/portable-gates-20261105-01.json) | 28/28 | 1.70s | 0 |
| [runner 门禁自检](../tests/budgets/evidence/runner-gates-20261105-01.json) | 13/13 | 0.02s | 0 |
| [缺宿主负向](../tests/budgets/evidence/missing-host-negative-20261105-01.json) | 0/0 | 未执行 | 2，host_source_required |
| [空选择负向](../tests/budgets/evidence/empty-selection-negative-20261105-01.json) | 11/0 | 0.01s | 5，no_tests_selected |

最后两个是**预期拒绝的基础设施检查**，不是产品失败，更不算测试通过。
完整预算和 transport 还显式设置了含 Provider ignore 和 `-x` 的 `PYTEST_ADDOPTS`，
runner 覆盖后仍执行全部 16 个 Provider 用例。
完整原预算的分文件计数为 15/16/11/2；F8 为 runtime 原 14 + 取消竞态 8 + budgets 15/16。
原预算自带的两个计量口径单测不运行 benchmark。

初始组件执行也保留：
[44 项](../tests/budgets/evidence/budgets-final-component-20261105-01.json)、
[53 项](../tests/budgets/evidence/f8-final-component-20261105-01.json)，均通过且 hash 稳定。
它们早于最终 runner 的实际宿主导入位置校验，不替代上表最终证据。
另在 runner 修正前显式跑过原窗口文件 11 passed / 0.24s。

## C50 与 F8 实测

| 子项 | 实测结果 |
| --- | --- |
| 原 caller work 反例 | 调用 1、work 取消 1、持久 cancelled、units=1 |
| 原 caller Generation 反例 | 真实 Provider.text_chat/_query → SDK → MockTransport；wire=1、cancel=1、持久 cancelled、units=1 |
| 直接 Runtime 补充 | run_model → OpenAIBinding → 同一真实 Provider/SDK；wire=1、cancel=1、持久 cancelled、units=1 |
| 取消对照与竞态 | 原 stop/排队取消及新增 F8 预留/派发/清理竞态 8 项通过，worker 可处理后续任务 |
| 并发/队列 | 1 active + 100 queued；下一项 queue_full；排空调用 101、peak_active=1 |
| 输入/输出 | 四用途各拒绝 5 个非法预算；4096/1024 边界可执行；真实输入上界恰好 4096，超限不上 wire |
| 全局日限额 | 四用途共 48 次；24 成功 + 24 失败；clear/cleanup/重开后不退款，次日可派发 |
| 情绪间隔 | 跨午夜/重开/clear 后 2s、299s 拒绝，300s 可执行 |
| 日记/梦 | 日记 1 篇/人格日；unknown 显式尝试最多 3 次；梦 2 次/夜，跨午夜重开不恢复额度 |
| 超时/unknown/失败 | Runtime 1s 超时、HTTP 503、ReadTimeout、输出越界均无隐式重试、无 fallback、无退款 |
| 崩溃/空闲 | 派发后退出保留 reservation，重开为 unknown 且下一调用被拒；空闲 worker 无调用、无额度 |
| 请求局部隔离 | n=1、system/user 两消息、无 tools/history；用途输出上限有效，共享配置/client/双 key 列表未变 |

原两个反例分别是 work 桩和真实 Provider，不能把 work 桩称为 SDK 测试。
为补齐直接 Runtime 入口的真实 transport 证据，另加 `provider_cancel_probe.py`，
未改原测试时序、断言或门槛。

## C22 与 F9 实测

| 子项 | 已测快照结果 |
| --- | --- |
| 原 F9 scope 4→2 | 12 次真实 API/Projector 写入，3 个 scope 各 4 条；重开/cleanup 后物理 SQL 分组计数 `[2,2,2]` |
| 小容量持续写入 | per_scope=3/global=5，16 次有效投影后全库 5、各 scope `[3,2]`；重开不反弹 |
| 单条正文 | 7999/8000/8001 输入落为 7999/8000/8000；配置调小后新正文 17 |
| TTL 边界 | 以 occurred_at 算 7 天；cutoff 不入窗口；推进 1s 后物理条数 2→1，重开仍 1 |
| 引用不延寿 | 已置顶日记保留、来源 ID 保留，源正文到期后 cleanup/重开为 0 |
| 调小全库/TTL | global 12→5；7 天改 1 天后，过期正文删除、未过期保留 |
| 硬上限 | 8 天、201/场景、10001 全库、8001 字符配置均拒绝 |

默认满 10000 / 每 scope 200 的实测来自性能作者既有证据，本专项未重跑满窗口基准，
不把小容量例或硬上限配置拒绝称为默认满容量实测。
迁移正文归属其他专项；存量正文在调小 body_max_chars 后是否重截断仍未验。

## 快照与未冻结范围

每次 JSON 均记录全部受检产品、测试、配置与选定宿主的前后 SHA256；
本次所有实际测试进程内均 `source_changed_during_run=false`。
完整预算于 21:59:49 UTC 结束后，存储专项更新了 sqlite/projector。
22:04:27 UTC 结束的最后 F8 命令在新两文件上仍通过 C50 31 项，但**没有窗口 11 项**，
所以不能以它放行新存储 F9/C22。收尾只读核对时与最后 F8 JSON 无新增差异；
瞬时相同不等于存储所有者已冻结。

| 文件 | 完整 44 项预算 SHA256 | 最后 F8 53 项 SHA256 |
| --- | --- | --- |
| storage/sqlite.py | `92d218a4a33d82b586a2a4c1a638eb1bc18dbd72d27d48fcc64a6fedcd33e8f7` | `0f027622d8e8c7bcacb14d3120f6847eb1b5cd0681cc284c22ca16df06ec9890` |
| runtime/projector.py | `64c51c315d508e5b1d29d8636002142a466161e2c11dac9122871a02f86662a8` | `ed91d95e28997e50c720347fc69fdd85598779e3416841080f1a062d38679368` |

两次均相同的关键文件：

| 文件 | SHA256 |
| --- | --- |
| runtime/background.py（F8 冻结） | `e413824c41c4040c465f7b47e2c96a52ad2cb791f3ed413ca570ec5207e7690d` |
| runtime/models.py（冻结） | `562abfda94bac5fc5ef5783c846cdde24b2c40d51d4c4af1174bd8c77508eddd` |
| api.py（仍属存储专项） | `a54e017aba4d6330da2980b8b7bf7fa7c49728f76c1c542d360ff36f8a867b41` |
| storage/schema.py | `09e48310efbaf48f5d21d4d16579ba58f32950edf52d6c13f0421d321a751de0` |
| host/astrbot/core/provider/sources/openai_source.py | `73c4f3675d5cbb1d448a13c8b43a12fe251aafdd60858066d32bae563a2d96f1` |
| tests/budgets/run_evidence.py | `676bcabc5a0c0c328616cb21e2496c086e02f119c6a3ec64f5328a881850de19` |

core 的 main/application 接线、第二轮 sqlite/api/projector 完整冻结及 C51 由父继续协调。
本专项不持有任何产品文件，不阻塞这些所有者。

## 复跑方式

在插件根目录使用已准备环境；下列变量由执行者指定，runner 不内置机器路径：
`HOST_PYTHON` 为既有 Python 3.12，`T11_DEPS` 为原性能记录的既有 pytest 依赖目录，
`ASTRBOT_HOST_SOURCE` 为已验证的 AstrBot 4.29.4 源码根目录。
不运行安装命令。每次使用新输出名，重复名字会明确拒绝覆盖。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T11_DEPS" "$HOST_PYTHON" \
  tests/budgets/run_evidence.py --lane all --host-source "$ASTRBOT_HOST_SOURCE" \
  --output tests/budgets/evidence/budgets-next-label.json
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T11_DEPS" "$HOST_PYTHON" \
  tests/budgets/run_evidence.py --lane f8 --host-source "$ASTRBOT_HOST_SOURCE" \
  --output tests/budgets/evidence/f8-next-label.json
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T11_DEPS" "$HOST_PYTHON" \
  tests/budgets/run_evidence.py --lane transport --host-source "$ASTRBOT_HOST_SOURCE" \
  --output tests/budgets/evidence/transport-next-label.json
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T11_DEPS" "$HOST_PYTHON" \
  tests/budgets/run_evidence.py --lane window \
  --output tests/budgets/evidence/window-next-label.json
```

普通 pytest 显式运行 Provider 时，必须同时指定
`-o 'addopts=-ra --strict-markers' --budget-host-source "$ASTRBOT_HOST_SOURCE"`；
仅在命令行写测试目录不能保证清除旧 ignore。推荐使用上面的完整 runner。

## 历史保留与限制

[budgets-03.json](../tests/budgets/evidence/budgets-03.json) 原 41 passed / 3 failed
保留：work/transport cancel=0 且 succeeded、F9 实际 `[4,4,4]`。
budgets-01/02/03 及原三个测试文件的 SHA256 均核对未变。
本轮 JSON 已检查无个人绝对路径、合成密钥、请求正文、数据库或异常日志。

取消仅证明本地协作式任务传播，不证明远端未处理/未计费；配额仍保守消耗。
Token 输入为字节上界口径，不是真实 tokenizer；只验证原生 OpenAI Provider/Qwen 文本路径。
身份、人格、legacy/night 边界仍为合成桩，不是 Application 全入口、
完整 scheduler、平台发送、真实模型或远端 CI。真实网络/模型/消息请求均为 0。
