# livingEmotion 生活控制台 UI

P6/P7 前端冻结时间：2026-11-06 20:40:28 +08:00。
冻结的是页面实现与本轮浏览器验证，不代表 P2 状态迁移、四版宿主或生产验收完成。
需求和生活规则见主协调者的 [life-console.md](life-console.md)；API 以
[internal-console-contract.md](internal-console-contract.md) 的 P5 DT1 为准，
状态端口以 [internal-state-contract.md](internal-state-contract.md) 为准。

## 页面与接线

入口：`pages/livingemotion/index.html`。九区为 TA、人格、情绪、关系、主动行为、
长夜、日记与梦境、记忆接入、设置。日记与梦境有独立二级页签。
没有 Node/npm/CDN 运行依赖，不下载外部图片、字体或官方标志。
关系布局使用已经构建的本地 D3 ESM，仅进入关系页才加载。

业务请求只走 AstrBot 的 `/api/plugin/page/bridge-sdk.js`，读取
`window.AstrBotPluginView`，兼容 `AstrBotPluginPage`。
页面不自行获取 Token、不直接 fetch 后端，也不实现第二套 postMessage 协议。
主题使用独立的 `data-le-theme`，不受 SDK 的通用 `data-theme` 覆盖。

| UI 请求 | 最终使用的 DTO |
| --- | --- |
| `GET console/scopes` | 初次发现人格、平台及已授权真实会话 |
| `GET console/state` | `persona_id/view_scope/context_id/platform`；消费 `selection`、`state_mode`、真实 baseline 和五档状态 |
| `GET console/records` | 同一 ScopeSelection；`kind=emotion/behavior/diary/dream`，每页 10 条，服务端筛选 |
| `GET console/relationships` | 同一 ScopeSelection、平台/账号搜索、每页 10 条、`limit=200`；图与表使用同一返回数据 |
| `POST console/relationship` | 人格、平台、账号、可选真实会话、`score/frozen/expected_version/reason`；不传 `view_scope` 或客户端 actor |
| `GET console/energy` | 同一 ScopeSelection、`event_type/page/page_size=10`；真实 24h 时窗、points 与逐事件 items |
| `GET console/settings-options` | 原生人格、聊天 Provider、embedding Provider、任务组 |
| `POST console/config` | 仅 `context_id/expected_revision/patch/reason`；一份 patch、一次 POST |
| `POST console/preview` | 真实 `context_id`；必须回执 `model_calls=0/sends=0` |
| `POST console/action` | 已声明动作、真实会话、版本、原因和显式确认；全局不提供动作 |

wire 参数只允许上述四个 ScopeSelection 字段，不把旧内部 `scene_id` 或
不可信 `actor_id/admin` 混入请求。页面选择只影响管理查看，不创建全局 Context。
私聊/群聊的聚合项明确显示“全部已授权会话”；选定单个会话后才传其真实 ID。
场景独立模式下，全局数值注明 `representative_context_id`，不冒称共享状态或平均值。

## 图表与交互

- TA 使用大字号情绪和同坐标 SVG 雷达；baseline 来自后端，不硬编码前端情绪规则。
  缺少维度/基准时明确未采集，不补值。高于基准有箭头、加粗和较大点；
  压力使用温和警示色，升高不等于改善。对方观察只在情绪页分开展示。
- 情绪记录只请求 `kind=emotion`，不查询或显示日记正文。前后值及原因保留来源详情。
- 关系以人格为中心，平台/账号稳定 ID 不合并同号账号。最多 200 人物节点，
  显示绘制人数/总人数，未绘制账号仍可搜索。支持拖动、缩放、复位、暂停、
  节点 Enter/Space、表格键盘选择和好感 0.1 编辑、冻结自动变化。
  熟悉/信任/边界没有证据时显示未建立，不编造数值或人物间边。
- 好感写入需要原因和非负整数版本。409 保留草稿，必须读取最新关系人工复核，
  不自动重试。未知写入锁定该人格/平台/账号，在本页跨分区也不会解除。
- 长夜显示清醒、小憩、恍惚、困、沉睡五档；当前精力只消费 night 的归一值，
  固定上限 100。日志按 `owner_key` 分开连线，保留每桶 min/max 竖线，
  不能把不同会话的精力连成同一块电池。
  时间轴、图注、事件表统一使用 DTO 的 IANA 时区，事件过滤和表格均为服务端分页。
  真实端口无事件显示未采集；503 显示读取失败，不伪装成空历史。
- 日记与梦境有二级键盘导航、私人正文和素材来源折叠；梦始终标为想象。
  日记展示程序页头的日期/住所/天气，失败显示天气未获取。
  正文内的置顶操作使用 `experience.pin`，携带记录 ID、相反的预期置顶状态、
  配置版本和原因；需确认后写入。未授权或过期的记录不提供按钮，冲突刷新复核，
  结果不明锁定单条记录，不自动重试；取消置顶不改变原创建日期或保留期限。
- 集中设置以原生 `config.fields/values/groups/readonly` 为单一来源，
  支持 `boolean/enum/integer/float/number/string`、中文标签、数字步进和单位。
  快速开始只引用字段，不复制表单。预算/阈值放高级折叠，普通分区不堆设置。
  作息预览计算配置的跨午夜顺序与中点，不在前端重抽赖床或推测当前周期实际时间。

主题键仍为 `livingemotion.theme.v1`。点击位置圆扩散 480ms，优先 View Transition；
无此能力时使用不承载业务 DOM、不拦截交互的纯色圆形覆盖层。
连续点击合并到最终主题；减少动态效果立即切换。系统首帧、禁存储、
页签同步和宿主通用主题覆盖均有浏览器验证。

## 保存与错误

草稿只在内存中；切换分区/主题和“刷新状态”保留草稿。浏览器整页刷新提示离开，
丢弃未保存草稿；已保存内容重新从宿主读取。
`sessionStorage` 只保存查看选择、分区、筛选及页码；不存私人正文、快照或配置草稿。
测试 fixture 为模拟保存持久性另有 synthetic key，仅测试页面使用。

Config POST 的旧 State 回执不用于替换当前 ScopeSelection；成功后再 GET 当前真实查看范围。
保存成功但随后读取失败时明确提示“已保存，状态未刷新”，不会重新 POST。
409 必须读取最新配置复核后再提交；无效输入跨分区也阻止保存。
所有写入均无自动重试；超时/未分型 bridge 错误按结果不明处理。
401/403 或无法确认认证的 bridge 错误清空私人视图、草稿和范围。
按钮禁用、客户端版本和确认不替代后端鉴权、CAS 或最终授权复核。

所有文本使用 `textContent/value`，不解析为 HTML、Markdown 或可执行 URL。
图形仅使用已校验有限数值。未配置能力时禁用真实动作，不用 fixture 兜底。

## 文件责任

| 文件 | 责任 |
| --- | --- |
| `index.html/style.css` | 九区、响应式、奶白/奶咖/温润暗主题、自有设备纹理、键盘焦点 |
| `theme.js` | 独立主题属性、持久化、圆扩散、降级及减少动效 |
| `app.mjs` | 九区真实渲染、ScopeSelection、四类记录、草稿/保存/错误/手动动作 |
| `model.mjs/api.mjs/dom.mjs` | DTO 校验、量纲、唯一 bridge、超时和安全 DOM |
| `settings.mjs` | 原生任务组去重、Provider 选择、float/单位/只读字段、作息预览 |
| `charts/radar.mjs` | 当前/真实基准 SVG 雷达 |
| `charts/relationships.mjs` | 二维力图、账号分页、键盘/拖动与关系 CAS |
| `charts/energy.mjs` | 真实时窗、多 owner 分线、桶极值及逐事件表 |
| `vendor/d3-force.mjs` | 固定版本的自托管构建结果 |
| `tests/ui/build.mjs` | esbuild 0.25.10 构建 d3-force 3.0.0，依赖锁定 |
| `tests/ui/server.mjs` | 页面及所有新模块的显式白名单映射 |
| `tests/ui/export-native-dto.py` | 用真实 Console、合成宿主和临时 SQLite 生成 DTO，记录后端来源哈希 |
| `tests/ui/native-dto.mjs` | 导出的 81 个原生字段及真实 DTO 形状，仅测试使用 |

第三方 D3 代码及传递依赖的 ISC 许可见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
CI workflow 和截图 allowlist 由主协调者更新，本专项没有修改 workflow。

## 本轮证据

机器证据：[browser-results.json](../tests/ui/evidence/browser-results.json)。
报告记录页面 12 个文件、fixture/锁文件哈希、DTO 生成时间和后端来源哈希。
UI 运行前后 `source_sha256` 一致，`ui_source_stable=true`。

- 单元测试 9/9；构建通过。
- 最终浏览器 24/24；页面异常 0、外联 0。
- 390x844 / 1280x900，双主题 x 九区，共 36 组布局，无整页横向溢出。
- 52 组对比度，包含常用/展开配置、私人正文、dialog、加载、空态和错误态。
- 关系 200 节点在 1 秒内可交互，布局在 2 秒内停止；隐藏停止、卸载清理、
  拖动/缩放/暂停、键盘、搜索、0.1/CAS/409/unknown 均实操。
- 圆扩散实测 480ms，两条实现路径、点击中心、连续点击、reduced 已验证。
- 收尾等待浏览器 `transition.finished` 并释放填充动画；受控延迟反例验证
  完成标记不会早于原生完成，随后普通导航点击正常。
- 新预览 `http://127.0.0.1:59888/tests/ui/fixture.html` 的九区及按需 D3 真正加载通过。
- 主协调者已视觉复核 1280 白昼 TA/关系、390 黑夜 TA、390 白昼设置。
  本执行者补看移动关系、黑夜设置与长夜等截图，没有发现明显布局问题。

| 主题 | 正文最小值 | 控件边界最小值 | 焦点最小值 |
| --- | --- | --- | --- |
| 白昼 | 5.15:1 | 3.26:1 | 5.61:1 |
| 黑夜 | 5.77:1 | 3.68:1 | 5.61:1 |

截图总计 20 张：保留原 allowlist 的 8 个文件名，内容为新版；新增关系/长夜/设置
共 12 张。`settings` 截图为首屏，其余为完整实际页面，未拼接重复视口。

| 宽度/主题 | 新截图 |
| --- | --- |
| 1280 白昼 | `1280-light-relationships.png` / `1280-light-night.png` / `1280-light-settings.png` |
| 1280 黑夜 | `1280-dark-relationships.png` / `1280-dark-night.png` / `1280-dark-settings.png` |
| 390 白昼 | `390-light-relationships.png` / `390-light-night.png` / `390-light-settings.png` |
| 390 黑夜 | `390-dark-relationships.png` / `390-dark-night.png` / `390-dark-settings.png` |

以上全部是合成 fixture 浏览器结果，不证明后端 save_config、状态切换、真实消息发送、
宿主鉴权或生产领域行为通过。真实 Console 导出只证明消费形状，不替代后端测试。

## 复跑与最终冻结

```bash
npm ci --prefix tests/ui
npm run build --prefix tests/ui
npm run fixture:native --prefix tests/ui
npm test --prefix tests/ui
UI_PREVIEW_URL=http://127.0.0.1:59888/tests/ui/fixture.html \
  npm run test:browser --prefix tests/ui
```

`fixture:native` 默认使用插件 `.venv`；其他环境可直接用对应 Python 执行
`tests/ui/export-native-dto.py`。测试独立临时回环端口会在结束时关闭。
未设置 `UI_PREVIEW_URL` 时只能验证临时测试服务，不证明现有预览映射。
若没有本地 Chromium，先按环境安装 Playwright 测试浏览器；不在生产宿主安装。

首轮20:39:57导出期间 `storage/state_scope.py` 来源变化，原 `dto_source_stable=false`
属于历史结果。本轮性能修复后重新导出81字段及只读energy_max，
单元9/9、浏览器24/24，`dto_source_stable=true`、`ui_source_stable=true`。
置顶操作成功后禁用旧快照按钮，刷新可取消置顶；冲突保持单次请求，不自动重试。
首次新增置顶用例失败因控件位于 `#records` 而刷新逻辑只查 `#content`；
修复了容器选择并完整复验，失败报告仍保留本地。

## 未完成边界

1. 初轮 P5 DT1 没有日记/梦境置顶写入入口；后续已补齐认证 action、
   服务端全记录 CAS、actor 审计与页面操作，最终浏览器复验结果另记。
2. P2 legacy/schema 兼容与完整状态行为仍由状态 agent/主协调者验证。
3. 真实 Dashboard/iframe、四版宿主和配置双向持久化、后端审计/最终闸门
   仍使用主协调者独立证据；本专项没有生产部署、收费调用或真实发送。

本专项没有修改后端、README/life-console 或其他仓库，没有 git commit/push。
