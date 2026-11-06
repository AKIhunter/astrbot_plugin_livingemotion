# 本地交付交接

## 0.2.0 当前交付

本轮九区生活控制台、五档睡眠、平台关系力图、完整补课、记忆、
天气日记、梦境及集中设置已实现。用户已批准更新原PRIVATE仓库，
中文新提交与普通push在最终验收、显式暂存及审阅之后执行。
未连接或部署生产、未发真实消息、未调用收费模型、未发布市场。

当前本地证据：完整可移植1451/1451，UI单元9/9、浏览器24/24；
旧入口/分场景/人格共享满载提交p95分别47.454167/44.336042/42.299291ms。
每种模式10000预热、10000提交/40000状态写入及10000读取，WAL/FULL和容量保持。
完整新版结果与失败历史见 [改版验收](verification-retro-final.md)，
四版本真实Dashboard及iframe见 [宿主验收](verification-retro-host.md)。
最终同一清单四版各424宿主检查通过，每版36真实视图，
浏览器检查分别159/163/163/165；所有源和加载副本前后不变，停止后产品任务0。
旧0.1数字不能作为新版证据，远端SHA和CI以实际仓库检查为准。

## 0.1 历史交付状态

读者：T12交付者与维护者；用途：冻结候选的文档核对与仓库收尾，不是生产上线许可。
文档专项冻结于 **2026-11-06 00:13:22 UTC**；F14 获追加授权补齐原创文档资产，
并将当前仓库措辞改为长期说明。本轮仅修改下列7个文件，不修改产品、验证报告、
父spec、测试、CI、配置值或版本；旧阶段记录与失败数字保留。

**0.1.0冻结候选已完成本地分层验收；本地结果不代表远端CI或生产部署。**
目标为 `AKIhunter/astrbot_plugin_livingemotion` **PRIVATE**，访问方式见[安装说明](installation.md)。
实际提交、访问权限与CI结果以仓库记录为准，远端交付证据由父协调者另行记录；
本文不预填建仓成功、SHA或CI通过。本轮不执行Git写操作、生产部署、真实模型调用或平台发送；
BiliBot/LivingHello本地消费者改动不纳入新仓库提交，现有部署不改。

### 最终证据索引

| 层 | 已完成结果 | 当前权威与限制 |
| --- | --- | --- |
| 宿主 | single222/four230/conflict245，共697 PASS、0 FAIL | [最终宿主](verification-host-final.md)；697含1条browser退出检查 |
| 原生浏览器 | 44 PASS、28组布局、0 pageerror | 布局已计入44；F13确认能力明确unsupported，不计作可靠发送 |
| 组件 | full1273/1273、migration84/84、V06 4/4 PASS | [最终组件](verification-final.md)；38项矩阵29 PASS、9限制、0 FAIL，集合不相加 |
| 性能 | 原完整C51-03 10000/10000、p95=48.801416ms | [最终性能](verification-performance-final.md)；<=50ms余量2.40%，非生产充足保证 |
| 窗口 | 冻结window-03 11/11 PASS | 静默scope物理 `[2,2,2]`；最终组件补齐迁移TTL |
| 预算/取消 | C50 31/31、F8 53/53 PASS，Provider16实际执行、0 skip | [最终预算](verification-budgets-final.md)；真实Provider/SDK+合成transport，无生产调用 |

产品所有者冻结时间（2026-11-05 UTC）：core 22:18:24，
storage/api/projector 22:35:47，domain/emotion 22:41:45。
最终宿主三轮输入及隔离副本前后hash一致截至 **23:55:49 UTC**，进程已退出并释放写权。
组件51产品文件跨轮稳定；full全清单曾新增未收集的宿主辅助 `final_provenance.py`，
故不声称全清单完全不变。后续交付文档变更不冒充产品冻结前的相同候选。
本轮只运行下述既有文档静态检查，不重跑full/宿主/浏览器/perf，不安装依赖。

### 固定支持边界

- 独立默认 `enabled=true, mode=active`；自主/群主动/日记/梦/外部写入分别单开。
- LM后台授权检索、幂等导出unsupported，开关不赋予能力、不穿透私库。
- 原生after-sent/bool不是发送确认；settling最多120秒取消回awake/drowsy，不自动重发。
- 原生iframe禁存储时主题仅本次有效，刷新随系统；业务配置持久化是另一件事。
- OpenAI/Qwen仅纯文本路径，UTF-8字节+256为预算上界，不是精确token或生产账单usage。
- 历史C51失败221.628/139.081/56.895041ms及历史宿主失败保留，不再当当前FAIL。

### 交付文件与候选

精确修改范围：
`logo.png`、`.github/img/Banner.png`、`README.md`、`docs/delivery-notes.md`，
以及追加授权的 `metadata.yaml` 注释、`docs/installation.md`、`CHANGELOG.md` 临时交付措辞。
`.gitignore` 原样保留，严格保留 `/tests/host/final_evidence/`；原JSON/log/XML不删除。
证据例外严格保持原3个脱敏JSON及8张合成PNG，完整路径见下方[证据交付边界](#证据交付边界)；
不放行新截图、原始报告或任意同名替换。

候选按插件根 `.gitignore` 选取实际源码、文档及既有白名单资产，
排除依赖、缓存、数据库、运行输出及仓库外消费者；不是本地整个目录体积。
F14前候选176文件、3,976,048字节；补齐两图后候选178文件，低于16,000,000字节；
精确字节数、清单摘要及文档冻结时间以最终交回消息为准，避免本文自引用哈希。
最终来源/隐私候选核对交T12；本轮静态路径/例外扫描不替代完整交付审阅。

### F14 文档资产检查

两图采用既有页面的深绿/黄绿配色，原创模块化LE与livingEmotion字标，
只借鉴极简留白和细线，不复制官方图案、上游Logo或外部图片，不新增无关插画。
生成源与实际候选副本仅放临时目录，不进入交付清单。
下列检查已在真实候选副本执行，精确字节与F14冻结时间随最终交回消息记录。

| 已执行检查 | 结果 |
| --- | --- |
| 既有CI `Documentation links, metadata and configuration contract` 同体本地执行 | PASS：10文档、72个本地链接目标、51项Config/schema默认值；metadata/main版本0.1.0、宿主限定==4.29.4 |
| `validate_astrbot_docs.py <candidate-copy>` | exit0：结构、metadata、语义版本、CHANGELOG、图片尺寸、候选3.82MiB均通过；原验证器未修改 |
| 原创资产 | logo 256x256、Banner 1200x360；PNG实际解码通过，64px图标/600px横幅缩放目视清晰 |
| 候选规则与字节计量 | 依.gitignore排除环境/原始产物；证据仍仅3个已批准JSON+8张合成PNG，另增两张原创品牌资产，不扩展证据例外 |

历史冻结结果（00:13:22 UTC）：静态10文档/71链接/51默认值通过；
原验证器exit1，缺logo/Banner且原目录75.00MiB超限；当时尚未init、建仓或推送，远端CI未运行。
技能验证器不完整识别 `.venv-ci/.ci-work` 及gitignore边界，75.00MiB包含环境和原始产物，
不是实际候选体积。F14按父新增授权补齐必要品牌资产，在排除依赖、缓存、数据库、
原始日志/证据的真实候选副本上运行原验证器，不改校验规则、不删除原始产物。
未执行远端CI、GitHub Markdown渲染、实际clone或发布归档；
没有新增测试、重跑full/宿主/perf、安装依赖或删除任何原始JSON/log/XML。

### 仓库交付边界

以下由T12独立执行与留证，实际进度以仓库和父交接记录为准；
本轮不改父spec或代勾清单。

- 按明确候选逐文件审阅来源/隐私与严格3 JSON+8 PNG例外，不使用force add绕过。
- 核验已批准PRIVATE目标的可见性和访问权限，保留实际可访问证据。
- 独立审阅后按明确文件暂存、提交、推送并记录真实SHA；消费者本地改动不混入。
- 记录实际远端Actions链接/结果，验证GitHub Markdown渲染和私有clone可用性。
- 实际交付候选有变化时重算字节数及清单摘要；不把本地环境计作发布包。

以上仓库动作本轮均未执行；没有tag/release、商店上架、生产部署/模型/发送任务。
F14仅补齐自有文档品牌资产，不扩展产品或商店发布范围。
最终38项矩阵由独立组件报告维护，本页只链接摘要，不修改验证者结论或父清单。

<details>
<summary>历史短收尾与前轮冻结记录（非当前状态，失败数字和哈希保留）</summary>

以下“本轮”“当前”“待验”均指前轮时间点，已由本文顶部取代，不作为T12待办。

## 历史短收尾

2026-11-05：只同步已落盘证据与当前支持边界，不等 core/storage freeze，不重跑最终测试。
本轮修改 README、architecture、api、compatibility、installation、本文，
另获授权仅将 identity-fix/cancellation-fix 的个人工作区前缀替换为 `$WORKSPACE`。
其余文件不改；下方原 14 文件成果、哈希及失败均为前轮记录，不是本轮重新冻结。

- 预算权威：[verification-budgets-final.md](verification-budgets-final.md)。
  C50 31/31、F8 53/53，Provider 16 项实际执行、0 skip；旧 C22 窗口 11/11 不放行新 SQLite。
- 宿主入口：[verification-host.md](verification-host.md)。H01/H02/H03 非冻结窄复验 57/57，
  C30 降级/超时 51/51；after-sent/bool 均无可靠确认，120 秒取消 settling 回 awake/drowsy，
  不自动重发，无待回复计划/手动睡眠可用。typed port 成功不代表生产投递；
  unsupported 展示与最终矩阵待验。
- 最终组件入口：[verification-final.md](verification-final.md)。
  C51 完整 139.081ms 仍 FAIL，第二轮 F6/独立性能复验待交回；
  `verification-performance-final.md` 未出现前保留[旧性能入口](verification-performance.md)。
- 本轮仅执行既有 CI 文档链接/metadata/schema 默认值检查与候选 Markdown 路径扫描，
  不新增测试、不安装依赖、不操作 Git/生产、不删除原产物或扩展证据 allowlist。
  结果和本轮文件 SHA-256 随交回消息给父；原始数字、失败和历史哈希不改写。

## 当前结果

**T11 文档/CI 已收敛并交回，2026-11-05；不是产品整体通过或上线许可。**
本轮按用户确认的独占分工及 F3 已结束交接接管下列文档/配置。
只写新插件文档、metadata、CI 和开发配置，不改产品、测试、父规格或旧插件，
没有 Git 初始化、建仓、提交、推送、生产模型调用或真实消息发送。
计划仓库 `https://github.com/AKIhunter/astrbot_plugin_livingemotion` 必须 **PRIVATE**，
实际建仓/远端 CI 尚未完成。

本轮文件清单（共 14 个修改文件）：

- `README.md`、`CHANGELOG.md`、`metadata.yaml`
- `docs/architecture.md`、`docs/api.md`、`docs/compatibility.md`、`docs/installation.md`
- `docs/delivery-notes.md`、`docs/memory.md`、`docs/migration.md`
- `.gitignore`、`.github/workflows/ci.yml`、`pyproject.toml`、`requirements-dev.txt`

`LICENSE`、`THIRD_PARTY_NOTICES.md` 核对后保留，不重写许可或既有证据。
没有生成 logo/Banner，商店上架不在范围。
前轮 `INTEGRATION`、`verification-*`、`identity-fix`、`performance-fix`、`cancellation-fix`
以及产品和测试文件均只读；本轮仅新增顶部注明的两份文档路径脱敏授权。

### 冻结清单与命令结果

本轮只验证文档/配置/依赖和测试收集，不重跑全套、浏览器、真实宿主或性能基准。
本文自身不写自引用哈希，最终哈希由交回消息给出。

| 命令/检查 | 本轮结果 |
| --- | --- |
| `.venv-ci/bin/python -m pytest --collect-only -q -p no:cacheprovider` | 首次661项；核心并行新增后668项。F6固定18项，三个宿主层0项，portable budgets/verification均在；不是测试全部通过 |
| `pytest tests/contracts/test_foundation.py::test_safe_config_and_schema_defaults_match -q -p no:cacheprovider` | 1 passed / 0.01s，配置专项，不替代全套 |
| CI `Documentation links, metadata and configuration contract` 同体本地执行 | 10文档、49个本地链接目标、51默认值、metadata/入口0.1.0一致，通过 |
| 工作流 YAML/内嵌 Python | 触发器、contents:read、语法通过；远端工作流未运行 |
| `.venv-ci/bin/python -m pip check` | No broken requirements found |
| `tools/migrate_legacy.py --help` 及四子命令 `--help` | 5条退出0；无数据库操作 |
| `git diff --no-index --check /dev/null <file>` | 16个边界文件无空白诊断；不是暂存/提交检查 |
| Git check-ignore `--no-index` | 原始JSON/XML/log忽略；三个脱敏JSON及8张原合成截图白名单保留；F6测试不忽略 |
| 脱敏检查 | 自有文档/metadata无个人路径；三个JSON解析/字段检查无个人路径、JWT或凭据值字段；禁改文档余项另列 |
| astrbot-doc validator | metadata/版本/README结构/CHANGELOG通过；exit1仅余缺logo/Banner及原目录71.87MiB（含本地环境），不是选择性交付包大小 |

没有生成发布归档，也未验证 GitHub Markdown 渲染或远端链接可安装。
原目录体积校验不识别全部 `.venv-ci/.ci-work/gitignore` 边界，T12仍须核对实际allowlist包大小。
本轮检查中一处自检把CI内的“个人路径检测正则”误判为个人路径；
已将文档路径自检限定到文档/metadata，与CI实际扫描范围一致，复检通过；
README首轮缺固定标题也已修复。没有因此改测试或隐藏产品失败。

下面为文档/配置冻结 SHA-256（LICENSE/notices 核对未修改）：

```text
71ff19ce6f6c3a383ac3c8dd0ae57287f9d8cfad2c29cca7df00dece43818f33  README.md
3d41f65ff58b6cd96221d6a3a659e7c21d1bb66cc5357556321f6cf574534ba0  .gitignore
59d69ca79047a52efdd62dfbf092db1c4c0fc823eadfc3de0a499d3b2cc22cae  .github/workflows/ci.yml
b5551b7e6ee5e5d068a4f5c82c5c7afa0801fc2057862b55e28a7e10e79c6962  pyproject.toml
6ed47f6816aef098fec3fd91b75016ba3f64f7ed6f173b22a55f61c1a7401c53  requirements-dev.txt
812b651cfb57a58ecded2b3c0e31fc334fbd748d0a100a09ba44409c8fc71878  metadata.yaml
8b5f28006ba045e4d905892fdb5939a70d1436645f964c7e8af86db0d56f99cc  docs/architecture.md
280e6fdabde1c56c789e79031bb319a82266329d8145b6fec220e8b306d447c3  docs/api.md
07bfb36bca885c105a806b30d40bbb2617d3ea8db09b51aab68794918f7b4f7f  docs/compatibility.md
c7c7695190c76b224ed65ccdf75bbfa7c40d79d5832d4b1c3718985c1bcc41c0  docs/installation.md
2f1f1c49723ff5cd43e1db5e30783449c5c88a5b869045142bef792966fdd977  docs/memory.md
f9e50680397adde91dc9b7c2e3c8db4330a628ba55e4e79e101299ec9bf6a2cf  docs/migration.md
3f3fe2498fb6904543be4fadec28faa8ec07d6f715c134366b60d2603dc80d0c  CHANGELOG.md
a481292960f2bb7c1d8c1a4e518897c9e4a4be6e82bc70b79f84cdf868cd8736  LICENSE
85479137a48a8365580d343f0925c24f57807e3dadee53e413284228920cc855  THIRD_PARTY_NOTICES.md
```

### 余下待验

- [ ] H01公开关系、H02读取故障下原生聊天继续、H03四插件管理员睡眠豁免已有
  非冻结独立窄复验，最终冻结矩阵仍待验，不能用旧single160项通过关闭。
- [ ] F3 运行时 History/最终 guard、F7 来源授权/绑定投影与 F9 新存储等最终联合复验。
  F8/C50 独立结果已交回，见顶部预算权威入口，不再等待旧复验者。
- [ ] C30 确认能力 unsupported 展示及最终宿主验收；不要求或宣称不可靠原生成功回执。
- [ ] C51完整独立复验 **p95=139.081ms，仍FAIL**，父已安排第二轮F6。
  短诊断约40ms不算最终PASS，历史221.628ms失败保留；本代理不干扰正在进行的benchmark。
- [ ] 最终普通全套、固定宿主矩阵、迁移回退及 CI Linux/Chromium 由父协调，文档代理不重跑。
- [ ] T12 暂存前仍须核对候选文档路径与证据 allowlist；本轮仅脱敏
  identity-fix/cancellation-fix，其他文档由所有者处理，扫描余项随交回消息列出。
- [ ] PRIVATE 建仓、明确暂存审阅、提交/推送、远端 Actions 和生产部署均未执行。

已存在的证据层级：固定 AstrBot v4.29.4 HEAD
`61335414433db721b3f7ecc93f90deafe0a59d78`；旧 single 成品 HTTP 160 项通过，
原生 iframe 38 项通过/28 组布局，四真实插件普通 pipeline 一次模型/一次回复/一次状态补充。
原生 sandbox 禁 localStorage，页面“仅本次页面有效”、刷新回系统；
非 sandbox 持久化为 12 项合成浏览器场景证据。以上均非本轮重新执行。
原生 ProviderOpenAIOfficial/Qwen 纯文本使用 UTF-8 字节+256 上界，
不精确计量 usage、不需要 tiktoken，其他 Provider 未验证并拒绝。
LM 后台授权检索/幂等导出 unsupported；宿主发送 bool 不能伪造成功。

</details>

## 检查分层

| 层 | 自动收集/入口 | 环境与边界 |
| --- | --- | --- |
| 普通 CI | `python -m pytest -q` | 仅 requirements-dev；含可移植 budgets、verification 及 F6 18 项，不导入真实宿主 |
| F6 回归 | `tests/storage/performance_f6.py` | pyproject `python_files` 显式纳入，不重命名，原命令不变；不自动运行 performance_probe.py/benchmark |
| 原生 Provider | `tests/budgets/test_model_payload.py`、`tests/integration/run_provider_payload.py` | 固定宿主环境，真实 Provider/SDK + 合成 transport，无生产调用 |
| 管理 ASGI | `tests/console/run_host_asgi.py` | 真实宿主 auth/routes + 合成 Application，不代表完整插件 |
| 成品宿主 | `tests/host/final_run.py` | 固定宿主/原生 Dashboard；显式独立验收 |
| 原生漏洞探针 | `tests/host/run_isolated_host.py` | 历史 46 pass/2 fail，不能改断言或掩盖退出码 |
| 合成前端 | `npm --prefix tests/ui test`、`run test:browser` | CI Node22 + Playwright Chromium，fixture 不是生产页面后台 |
| 性能 | `tests/performance/bench_local_state.py` | 大样本独立执行，不在本轮重跑 |

默认排除项明确写在 pyproject 和 CI：`tests/host`、
`tests/console/test_console.py`、`tests/budgets/test_model_payload.py`。
这是宿主层分离，不是 skip 或“所有测试通过”；每个层次须独立报告。
普通可移植预算/窗口/迁移与跨模块测试仍自动运行，不忽略整个 budgets/verification 目录。
F6 方案已通知父与 final_components：**只改收集配置，不改文件名或断言**。
budget新验收者独占tests/budgets，父已收到最终ignore约定：
显式Provider层覆盖`-o addopts="-ra --strict-markers"`，不继承默认ignore。
其参数化 runner 与哈希采集已完成，详见[最终预算证据](verification-budgets-final.md)；
本轮未改 runner/断言。

从插件根目录运行普通层：

```bash
python3.12 -m venv .venv-ci
.venv-ci/bin/python -m pip install -r requirements-dev.txt
.venv-ci/bin/python -m pip check
.venv-ci/bin/python -m pytest -q
```

以下是**独立宿主层命令，本轮未执行**。先将 `ASTRBOT_HOST_SOURCE` 指向该固定 HEAD 的干净
AstrBot checkout，`HOST_PYTHON` 指向已按宿主依赖准备的隔离解释器，
`T11_DEPS` 指向既有 pytest 依赖目录，`SANDBOX_PARENT` 指向专用隔离输出目录。
不要使用生产运行目录或覆盖旧证据。Provider runner 显式接收宿主来源，
覆盖默认排除项及 `PYTEST_ADDOPTS`；缺宿主/SDK、skip、漏执行或源码漂移不能通过：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T11_DEPS" "$HOST_PYTHON" \
  tests/budgets/run_evidence.py --lane provider --host-source "$ASTRBOT_HOST_SOURCE" \
  --output tests/budgets/evidence/provider-next-label.json
"$HOST_PYTHON" tests/integration/run_provider_payload.py --host-source "$ASTRBOT_HOST_SOURCE"
"$HOST_PYTHON" tests/console/run_host_asgi.py --host-source "$ASTRBOT_HOST_SOURCE" \
  --sandbox-parent "$SANDBOX_PARENT" --output "$SANDBOX_PARENT/console-new.json"
"$HOST_PYTHON" tests/host/final_run.py --host-source "$ASTRBOT_HOST_SOURCE" \
  --sandbox-parent "$SANDBOX_PARENT" --dashboard-dist "$DASHBOARD_DIST"
```

`all/f8/transport/window/portable/runner` 的范围与复跑命令以预算权威页为准，
不要沿用下方历史发现中的私有宿主路径或旧运行方式。

### 历史分层发现

以下保留前轮发现；第 1、2 项已由预算独立者参数化 runner/fixture 并验证解决，
不是当前待办，见[最终预算证据](verification-budgets-final.md)。

1. `tests/budgets/conftest.py:10` 注入工作区特定 `.livingemotion-host-t1/AstrBot`，
   `budget_support.py:109` 的 Wire 导入真实 Provider、httpx/openai；
   `test_model_payload.py` 不能作为仅 requirements-dev 的可移植测试。
   本轮只将该文件分到显式宿主层；请作者参数化宿主来源，避免私有 checkout 优先于显式 PYTHONPATH。
2. `tests/budgets/run_evidence.py` 的宿主哈希仍读同一工作区固定路径，且运行 pytest 时不明确
   覆盖默认分层选项；请作者让实际导入宿主、报告哈希和显式宿主收集相符。
   本轮不改 runner、不覆盖 budgets 证据。
3. `tests/console/test_console.py:13` 有环境缺失 `SkipTest`；
   普通 CI 已显式排除此真实宿主文件，以 runner 单独执行，不把这个 skip 作为通过。
4. `tests/verification/*.py` 未发现强制私有宿主或硬编码用户绝对路径依赖；
   `run_checks.py full` 今后代表默认可移植层，不包含上述宿主层。
   既有报告中的绝对 cwd 是历史证据，不为“可移植”而改写它。

这些是静态分层发现，不是本轮产品修复。没有给 requirements-dev 增加宿主或 tokenizer。

### 证据交付边界

原始运行产物不删除，`.gitignore` 默认忽略 tests 下 evidence 目录内容、
JUnit XML、日志以及 host/console 非白名单 JSON。verification JSON 含原运行命令、
绝对 cwd 等信息，**仅本地保留，不进入仓库**；budgets/performance 原始报告也留本地。
文档提到这些文件名是本地可复跑证据索引，不承诺 clone 后存在；上述层级表给出复跑入口，
本页及 compatibility 保留精简结论与旧失败数字。不得用 force add 绕过审阅。

本轮结构/内容检查后仅沿用三个脱敏 JSON：
`tests/host/evidence-v4.29.4.json`（原生探针仍有两失败）、
`tests/console/evidence-v4.29.4.json`（合成 Application 的30项ASGI）、
`tests/ui/evidence/browser-results.json`（12项合成浏览器）。
它们只含版本/哈希/合成来源/数量或断言，不含个人工作区、凭据或真实正文。
本轮核对的 SHA-256：

```text
52fdb9af8f56cb9402fbe0cd43d60df3676a314d9815799b7ea07e42add63c79  tests/host/evidence-v4.29.4.json
a6ab9b86366c5b283e6305009c9b422e113906f16a5f6d536513644ad693c953  tests/console/evidence-v4.29.4.json
e476e68a011efd8c9fd4307777d2983b695e75e68e460f6cb0a6caef5e15c2ef  tests/ui/evidence/browser-results.json
```

UI 八张合成截图沿用原已审阅白名单，不放行任意新截图。
allowlist 只针对已审阅内容；报告变化后必须重新审阅，不因同名自动成为可交付证据。

CI 不上传原始 Python XML/日志，只保留明确的合成 UI 报告/截图，
并检查 tracked 证据白名单与 Markdown/脱敏 JSON 中的个人路径。
这不是全面 secret scanner，也不能替代 T12 的明确暂存清单和人工内容核对。
禁改文档仍有路径的项已单独交父，不声称全仓已完成脱敏。

## 文档生命周期

以下 `Last verified` 为 **2026-11-05 冻结源码/最终报告核对**，不是本轮重跑或生产验收。

| Doc | Diataxis quadrant | Responsibility path | Source of truth | Last verified | Verification cadence | Staleness signal |
| --- | --- | --- | --- | --- | --- | --- |
| README | tutorial | 文档维护者→父协调者 | 安装/API/兼容权威页 | 2026-11-05 | 每次交付、最长30天 | 入口或支持边界变更未同步 |
| installation（运维） | how-to | 安装维护者→核心 | main/Config/Application/models | 2026-11-05 | 每次安装交付、最长30天 | 配置/路径/Provider 改动 |
| architecture（架构） | explanation | 模块维护者→核心 | domain/runtime/storage | 2026-11-05 | 每次架构变更、最长90天 | 所有权/算法/恢复语义变化 |
| api | reference | API/页面维护者→核心 | api/contracts/page_api/console | 2026-11-05 | 每次契约变更、最长30天 | 签名/量纲/鉴权/动作变化 |
| compatibility | reference | 独立验收者→父协调者 | 哈希对应的 verification 报告 | 2026-11-05 | 每次宿主升级/交付 | 受测源码或宿主哈希变化 |
| memory | reference | 适配器维护者→核心 | adapters/memory + runtime/materials | 2026-11-05 | 接口变更、最长30天 | 来源授权或后端能力变化 |
| migration（运维） | how-to | 迁移维护者→核心 | CLI/legacy_import/legacy | 2026-11-05 | 每次迁移前及交付 | schema/期限/约束变化 |
| delivery-notes | reference | 文档代理→父协调者 | 本轮命令、文件哈希、原始证据 | 2026-11-05 | 每次交回 | 文件继续变化或新增结果 |
| CHANGELOG/许可/notices | reference | 维护者→仓库交付者 | 版本/来源基线/权属范围 | 2026-11-05 | 每次交付或引入依赖 | 版本/来源/分发范围变化 |

**不重复权威说明**：每个主题只有上表的一处当前权威位置；README 只导航，
阶段交接/原始测试报告只证明当时结果。旧内容保留在下面的历史区，不再当当前操作指南。
超过表中周期或任一 staleness signal 出现即标记待核对，由对应维护者更新，
不得复制一份互相矛盾的“当前状态”。任务→文档→源码/证据的路径可追溯。

运维 freshness：安装/Provider 参数看 installation；迁移/恢复顺序看 migration；
预算和 p95 定义看 architecture 与独立 performance 报告。阈值、故障或恢复流程变化即复核，
不能把模型字节预算当精确 usage 指标。
每个文档 PR 的 CI 自动检查相对链接目标、metadata/入口版本、Config/schema 默认值和空白；
检查失败阻断普通 lane。外部网页、Markdown 渲染和真实宿主另验。
查找路径已经串联：README→安装→按需启用→API/记忆→迁移→兼容/交接。

---

## 历史交接归档（原文保留，非当前状态）

以下为早期文档代理原记录。诸如“无 CLI”“不修改 metadata”“成品页面待接线”
均是当时状态，已被上方当前说明取代；失败数字与跳过不改写。
仅将个人机器前缀替换为 `$WORKSPACE`，复跑时它表示包含隔离宿主的工作区根目录；
不是插件 clone 根，也不要求相同用户名。旧运行产物仅本地留存。

日期：2026-11-05。阶段：本轮文档与 CI 准备已完成，成品集成仍在进行。
负责人：本轮文档/CI 代理；最终证据与接线由父代理核对。

## 范围

本轮独占 README、LICENSE、THIRD_PARTY_NOTICES、CHANGELOG、
docs/architecture、api、compatibility、installation、本文、.gitignore、
.github/workflows/ci.yml，以及必要的测试依赖/配置。
不修改 metadata、config、main、runtime、pages、其他代理测试实现或父规格。
使用 astrbot-doc 整理本地安装/使用/来源文案，不制作商店素材，不公开发布。
目标仓库为 `AKIhunter/astrbot_plugin_livingemotion`，可见性必须为 **PRIVATE**。
本轮不建仓、不初始化 Git、不 commit/push、不调用远端工作流、不生产部署。

## 立即交给父代理的缺口

以下来自读过的代码和交接，不是要求本代理越界修复：

1. 首次读代码时 `main.py` 仅创建 Lifecycle；第二阶段已改为 Application、
   注册页面、接消息/LLM hook（priority=11000）及 le_wake 命令。
   本轮已据落盘入口更新文档，但未重跑最终宿主，不把接线存在当端到端已通过。
2. 首次检查时 config 尚无人格/时区/行为白名单等字段；本轮首跑期间集成代理已新增
   13 个字段，但 `_conf_schema.json` 尚未同步，触发默认值契约失败。
   第二阶段交接随后声明原生配置和更多行为/体验参数已补齐；本轮不等待/追跑核心，
   保留首跑证据，最终默认值一致性由下一轮验证确认。
   README/安装文档已按新增字段说明前提，具体输入格式和页面映射仍待所有者收敛；
   `Config.from_mapping` 忽略未知键，不能把旧 schema 的保存当作实际启用。
3. 首次读取 capabilities 的执行/生成标志固定 false；第二阶段已改为判断
   Application 接入，preview 委托行为服务、mode 读取有效模式。
   Application 存在仍不等于模型已配置或允许发送，调用者必须检查用途能力和最终闸门。
4. LivingMemory 尚无合格后台来源授权与幂等体验导出门面。
   `memory_export=true` 不能使缺失能力生效；不得回退私有 SQL 或伪造事件。
5. AstrBot v4.29.4 `send_message` 的 bool 不是投递回执。
   当前 sender 的 False→rejected，其他返回值→unknown；
   unknown 不自动重发、不退款、不生成成功行为、不推进成功回执收尾。
6. 宿主探针两项 v1 资源令牌越权断言失败；guard 探针通过不等于成品 HTTP
   和 iframe 已通过。成品 legacy/v1 五个入口均须独立验证。
7. 体验读/置顶/多来源保存等接口已在不同交接中演进，最终以服务与存储实际接线为准；
   不沿用阶段文档的“缺接口”或“已完成”句子作为最终验收。
8. 尚无本轮核实的迁移 CLI；安装文档只给安全边界，不编造导入命令。
9. 新插件和工作区根目前都没有 `.git`，不能声称 git diff 或暂存检查已通过。

## Metadata 建议文案（仅交接，不修改文件）

当前 metadata 为 0.1.0，入口注册版本也是 0.1.0。建议所有者在接线后同步文案：

```yaml
short_desc: 基于原生人格的 Bot 感受、关系与作息，长期记忆可选。
desc: >-
  独立实现 Bot 感受、对方观察、关系、长夜与私人日记梦境。
  模型生成、主动发送和外部导出默认关闭；提供白昼/黑夜管理页。
  当前处于集成验证阶段，宿主证据限 AstrBot v4.29.4 固定 HEAD 探针。
help: >-
  在 AstrBot 原生配置和 livingemotion 插件页管理。
  先检查能力与健康，再按安装文档启用所需开关；le_wake 已注册，真实宿主效果待验。
```

保留 display_name=livingEmotion；不要添加未经证实的最低 astrbot_version。
repo 字段待父代理实际核对目标 PRIVATE 仓库后填写，无仓库时不声称可远端安装。
没有 logo/Banner 是本轮非商店范围，不借用上游图片或伪造素材。

## 质量门禁

专项：`testing-and-quality-gates`，置信度高。产物是开发阶段的本地可复跑检查，
防止来源隔离、幂等、默认副作用、界面状态和依赖安装回归，不是上线许可。

| 阶段/层次 | 风险与检查 | 失败处理 |
| --- | --- | --- |
| 合并前，小型纯逻辑 | pytest 中领域/契约/适配器；UI Node 单测 | 保留断言，归对应模块修复后复跑 |
| 合并前，中型本地组件 | pytest 中临时 SQLite、队列、行为/体验合成桩 | 查并发、代际、额度和 unknown；不忽略失败文件 |
| 合并前，中型浏览器 | 回环 fixture、两主题、390/1280、拒绝/空态、无外联 | 查生成的合成证据；资源安装失败与产品断言失败分开 |
| 交付前，真实宿主 | 显式隔离探针、成品加载/重载/HTTP/iframe、多插件 | 已知宿主失败保留，阻止宣称完整兼容；不纳入普通 pytest |
| 交付前，专项 | 1 万事件/20 并发 p95、迁移、真实模型参数/上限 | 未执行即待验，不以单元测试数替代 |
| 生产 | 不在本轮范围 | 没有发布、发送或部署授权 |

CI 用 Ubuntu 24.04、Python 3.12/3.13、Node 22；矩阵表示测试运行环境，
不是宿主兼容范围。全部 `tests` 自动收集，只有 `tests/host` 独立排除，
防止将已知宿主漏洞探针变成普通测试或依赖本机私有 checkout。
新增纯合成测试应留在普通目录，真实宿主测试放 host 并给显式命令。
不自动安装 AstrBot 或其他插件；如果新测试确实需要宿主模块，须明确依赖/测试层，
不能通过 importorskip 静默让核心功能通过。本轮发现新增
`tests/console/test_console.py` 用明确 SkipTest 要求隔离宿主环境，
因此普通 pytest 显示 1 skipped；下方单列其显式命令，不算管理端已通过。

保留单元/组件为主、少量浏览器场景的现有结构，不按覆盖率刷数量。
关键风险目标是上述每类都有断言或显式待验记录；行覆盖率尚未测量、不设虚假门槛。
阻塞 job 硬超时各 10 分钟，pytest 单例 60 秒；
目标完整 lane p95 <10 分钟，须有真实 Actions 历史才测量。
包下载缓存按平台/解释器/依赖文件失效，不缓存测试结果、数据库或 node_modules；
每轮重新安装并重跑测试，Chromium 按 Playwright 锁定版本安装。
反复重跑结果不一致率目标为 0，>1% 时维护者须在 48 小时内修复或记录有到期日的隔离，
不得直接增加 ignore/continue-on-error 或重跑到绿。
此配置没有安全扫描或完整供应链锁定承诺；依赖升级需本地复验。

## 验证记录

### 本轮完成

- [x] 写入 README、LICENSE、THIRD_PARTY_NOTICES、CHANGELOG。
- [x] 写入架构/计算逻辑、API、兼容性、本地安装使用/迁移回退边界及本交接。
- [x] 写入 .gitignore、CI 工作流，修改 pyproject.toml 和 requirements-dev.txt，
  生成 tests/ui/package-lock.json；没有改测试断言或 UI/业务实现。
- [x] 从公共 PyPI/npm 验证并安装真实测试依赖，运行本地检查，保留失败和跳过。
- [x] 记录权限、来源、外部后台/导出缺口、发送 unknown 与成品待验边界。

本轮明确修改/新增 **14 个交付文件**。metadata 文案只在本文建议，没有实际修改。
未初始化 Git、未建远端、未 commit/push、未触发工作流或发布；
没有修改父规格、旧仓库或生产运行环境。

### 本轮实跑结果

| 检查 | 结果与范围 |
| --- | --- |
| Python 3.12.16 独立 .venv-ci，普通 pytest 全收集 | **442 passed, 1 failed, 1 skipped in 7.51s**；失败/跳过如下，不宣称全绿 |
| npm 锁文件生成与 npm ci | 成功；Playwright/playwright-core 1.64.1，公开 registry 地址和 integrity，无私有源凭证 |
| UI 单测 | 系统 Node 25.6.0 首跑 7/7；Node **22.23.4** 复跑同一套 **7/7**，不重复计数 |
| 合成浏览器 | macOS arm64、Node 22.23.4、Playwright 1.64.1、本机 Chrome **156.0.8078.80**；**12/12**，28 组布局、44 组对比度，页面异常 0、非回环请求 0 |
| pip check | 无依赖冲突 |
| Linux x86_64 wheel 解析 | Python 3.12 与 3.13 的 `--dry-run --only-binary` 均成功；不是 Linux 执行证据 |
| YAML | metadata 和工作流成功解析；检查了触发器、contents:read、Python 矩阵 |
| 文档链接/空白 | 14 文件逐项检查，37 个相对链接目标存在；无 whitespace 诊断；不是仓库暂存/提交审阅 |
| 选择性源码体积 | 当时 123 文件、3,192,328 字节，约 **3.04 MiB**；排除环境/缓存/运行输出，非实际发布归档 |

首跑失败为
`tests/contracts/test_foundation.py::test_safe_config_and_schema_defaults_match`：
Config 在并行实现中新增 persona_mode/persona_id/timezone/provider_id/fallback_provider_id/
autonomy_scopes/muted_scopes/night_schedule_enabled/sleep_at/wake_at/diary_at/
diary_backfill_yesterday/scheduler_seconds，而 schema 尚未同步。
这是当时工作区状态的证据，未越权修复、未移除测试、未等待其他代理完成后刷结果。
父代理应在配置收敛后重跑全套。

跳过项为 `tests/console/test_console.py`，需要
`LIVINGEMOTION_CONSOLE_TEST_ROOT` 和真实宿主模块，由专用 runner 设置。
本轮未运行此宿主 ASGI 专项，也不把跳过视为通过。

Python 已安装直接依赖：pytest 8.4.2、pytest-asyncio 1.4.1.post1、
pytest-timeout 2.4.0、PyJWT 2.10.1、PyYAML 6.0.3。
当时传递依赖：iniconfig 2.3.1、packaging 26.3、pluggy 1.7.0、
Pygments 2.21.0、typing_extensions 4.16.0。
直接依赖精确固定；requirements-dev 不是带哈希的完整传递依赖锁。

### 精确复跑命令

以下命令从**插件根目录**执行。普通安装文档使用 python3.12；
本机本轮创建 venv 使用已存在的隔离解释器，不更改该宿主环境：

```bash
"$WORKSPACE/.livingemotion-host-t1/venv/bin/python" -m venv .venv-ci
.venv-ci/bin/python -m pip install --index-url https://pypi.org/simple -r requirements-dev.txt
.venv-ci/bin/python -m pip check
.venv-ci/bin/python -m pytest -q --junitxml=.ci-results/pytest.xml
npm ci --prefix tests/ui --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org
npm exec --yes --package=node@22 -- node --test tests/ui/model.test.mjs
```

本轮浏览器使用副本，避免覆盖 UI 代理的已存证据：

```bash
mkdir -p .ci-work/browser/pages .ci-work/browser/tests
cp -R pages/livingemotion .ci-work/browser/pages/
rsync -a --exclude=node_modules --exclude=evidence tests/ui/ .ci-work/browser/tests/ui/
PLAYWRIGHT_MODULE="$PWD/tests/ui/node_modules/playwright" \
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
npm exec --yes --package=node@22 -- node .ci-work/browser/tests/ui/browser.test.mjs
```

新报告/截图仅在 `.ci-work/browser/tests/ui/evidence/`；Python XML 在
`.ci-results/pytest.xml`。`.venv-ci` 和这些运行目录全部被忽略，不随仓库交付。
CI 使用 Playwright 自带 Chromium，而不是本机 Chrome，命令为：

```bash
tests/ui/node_modules/.bin/playwright install --with-deps chromium
npm --prefix tests/ui test
npm --prefix tests/ui run test:browser
```

CI 浏览器运行前清掉已提交的旧合成证据，只上传本轮白名单结果；
未执行浏览器步骤时不上传旧证据。没有上传整个工作区/运行目录。
依赖解析命令（只解析下载兼容包，不运行 Linux）：

```bash
.venv-ci/bin/python -m pip install --dry-run --ignore-installed --only-binary=:all: \
  --platform manylinux2014_x86_64 --python-version 3.12 \
  --index-url https://pypi.org/simple -r requirements-dev.txt
.venv-ci/bin/python -m pip install --dry-run --ignore-installed --only-binary=:all: \
  --platform manylinux2014_x86_64 --python-version 3.13 \
  --index-url https://pypi.org/simple -r requirements-dev.txt
```

真实宿主命令从**工作区根目录**执行，本轮仅记录，没有执行：

```bash
.livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/host/run_isolated_host.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs

.livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/console/run_host_asgi.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs \
  --output .livingemotion-host-t1/console-delivery-evidence.json
```

第一条是探针，不是成品，已有证据预期 exit 2（两项原生鉴权失败），
不得 `|| true` 或删除断言。第二条是真实宿主 auth/route/request + 合成 Application，
也不是完整插件/浏览器联调。新输出留隔离目录，不覆盖其他代理证据。
不得运行 `capture_baseline.py` 覆盖原来源基线。

### 文档技能校验及范围例外

从工作区根实际运行：

```bash
python3 .trae/skills/astrbot-doc/scripts/validate_astrbot_docs.py \
  插件/astrbot_plugin_livingemotion
```

exit 1：版本/README 结构/CHANGELOG 通过；缺 repo、logo 和 Banner，
建议字段缺 astrbot_version/social_link/tags；原始目录体积报 67.76 MiB。
该商店校验器只排除名为 `.venv` 的目录，不识别本轮 `.venv-ci`、`.ci-work`
和全部 gitignore 规则，所以该体积不是交付包大小；另做选择性体积检查如上。
本轮不改 metadata，不创建图片或仓库来迎合商店门槛；不宣称商店校验通过。
没有执行真实 GitHub Markdown 渲染，只做相对链接存在性检查。
根目录没有 Git，不能执行普通 `git diff --check`；改用每个交付文件的
`git diff --no-index --check /dev/null <file>`，退出 1 代表文件差异，按诊断输出判断空白问题。
没有 git init 或暂存。

### 父代理后续待办

- [ ] 配置/schema/页面同步后更新默认值表、范围输入格式并重跑全部 pytest。
- [ ] 核心/迁移/消费者完成后按实际行为更新 README、API、架构与安装步骤；
  本轮不等待这些任务，前面的缺口是时间点记录。
- [ ] 完整成品隔离安装、三次重载/卸载、模型参数/预算、真实 HTTP/iframe、
  四插件和冲突组合、迁移回退、性能基准另行验收。
- [ ] 运行 Linux Python 3.12/3.13 与 CI Chromium，补充真实 Actions 链接和结果；
  目前只有依赖解析与 macOS Node 22/Chrome 结果。
- [ ] 建仓前按明确文件检查许可/隐私和暂存清单，目标 PRIVATE；
  本轮没有提交、建仓、发布或生产部署，不勾选父规格交付完成。

本轮结束后不保留宿主/浏览器/预览服务器进程；只保留被忽略的依赖环境和合成测试产物。

## 第二阶段同步备注

父代理要求本轮尽快结束、不等待核心/迁移/消费者/宿主最终证据。
已读取 INTEGRATION 第二阶段并核对 main/API 接点，未把该专项新增测试计入本轮结果。
其模型桥文案尚在评估；按父代理最新要求，**不把 GPT-only/tiktoken 写成默认前提，
不添加 tiktoken 强制依赖**。模型支持能力与可选依赖待最终核定。
README/安装/架构已加此边界；requirements-dev 仍仅包含本轮验证过的测试依赖。
