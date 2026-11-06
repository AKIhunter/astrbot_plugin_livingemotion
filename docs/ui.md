# livingEmotion 管理页面

## 接线协议（前端 v1，待主集成者冻结）

页面为 `pages/livingemotion/index.html`，无运行期依赖、外部字体、图片或 CDN。所有业务数据只来自宿主 bridge。此文档是 T9 给主集成者的接线交接；前端及合成测试已实现，尚不代表真实宿主验证通过。

bridge 脚本明确使用 `/api/plugin/page/bridge-sdk.js`，宿主将其替换为带范围令牌的地址。DOMContentLoaded 后读取 `window.AstrBotPluginView`，兼容别名 `AstrBotPluginPage`，调用 `apiGet(path, params)` / `apiPost(path, body)`。不等待可能阻塞的 `ready()`，不自行读取 token，不使用 fetch 或自行实现 postMessage。具体宿主兼容结论见 `host-contract.md`。

**给 foundation / 父集成者的紧急对齐项：**

- 已核对固定宿主 `PluginViewPage.vue:122`：父页面把 `console/state` 转为 `/api/v1/plugins/extensions/{pluginName}/console/state`。不要让前端绕过 bridge，也不要认为选 legacy SDK 路径就避开 v1 API 的令牌风险。
- `host-contract.md` 已确认 v4.29.4 的 asset token 可被 v1 误认为管理身份；所有管理 handler 必须额外拒绝 `plugin_page_asset`，不能把前端按钮禁用当成鉴权。
- `PluginViewPage.vue:382-401,513` 及 SDK `:176` 会丢弃 HTTP 错误 code，只保留 message。后端拒绝时请将 message 设为 **`[livingemotion:forbidden] 可读说明`**，其他前缀为 `unauthorized/version_conflict/validation_error/unavailable`。前端已解析此白名单；实际 HTTP 仍需返回正确 401/403/409，不能为保留错误码改成成功授权。成功响应原样/单层 data 均支持。
- 原生认证中间件可能返回没有前缀的文本错误。前端将无法分型的 bridge 错误按失去可信连接处理，隐藏私人快照并锁定可能结果不明的写操作，不凭未分型错误宣称仍有管理权限。已分型 `unavailable` 读取失败可保留明确标注的旧快照，但停用写操作。
- SDK `applyContext` 会写通用 `data-theme`。页面主题使用独立 `data-le-theme`，保证宿主主题消息不会覆盖系统初始偏好或用户手动选择，不注册任何业务主题回调。
- `contracts.py` 当前 `BotAffect.pleasure` 为 `[-1,1]`，UI 归一值须显式 `(value+1)/2`；`NightState.energy` 为 `[0,100]`，须 `/100`；其余 Bot 维度为 `[0,1]`。不能凭字段名或数值大小自动猜量纲。关系原值取 score，归一值取 normalized/score÷1000，原量纲标 `0–1000`。
- `HumanObservation.labels/subject_id/occurred_at` 映射到 observation 的 label/subject/observed_at，**不能**补到 bot_state。`NightState.phase/sleep_stage/sleep_started_at` 分别映射到 state/stage/sleep_at。reason_codes 转为可读 reason/reasons；完整原因码保留于来源详情或记录。

统一响应：

```json
{"status":"ok","data":{"api_version":1}}
```

也接受直接数据对象及 `{ok:true,data:...}`。错误推荐 `{status:"error",code:"forbidden",message:"[livingemotion:forbidden] 说明"}`，码值按上文白名单；不可假设 bridge 保留 code。401/403 清空私人视图、草稿并停用写操作；409 保留草稿但禁止覆盖提交，需重新读取最新配置后再确认。页面不自动重试写请求或不明动作。

| 方法 / 路径 | 请求 | 响应 data |
| --- | --- | --- |
| GET `console/state` | `{context_id?:string}`；上下文 ID 仅由上一次已授权响应取得 | 下文 State |
| GET `console/records` | `{context_id,kind,page,page_size:10,query}`；kind 为 `emotion/behavior/diary/dream`，page 从 1 起 | `{api_version:1,items:[],page:1,page_size:10,total:0}`；过滤后 total，由服务端分页及授权 |
| POST `console/config` | `{context_id,expected_revision,patch:{字段键:值},reason}` | 完整 State；服务端白名单校验及审计，只更改同一份原生配置，不建立页面专属配置 |
| POST `console/preview` | `{context_id}` | `{api_version:1,eligible:boolean,reasons:[],candidates:[],model_calls:0,sends:0}`；此路径必须无模型计费、无消息发送 |
| POST `console/action` | `{context_id,action,expected_revision,reason,confirmed:true}` | `{api_version:1,status,reason,request_id?}`；只允许 State.actions 明确宣告的动作，必须重新鉴权及版本复核 |

读取/写入前端超时均为 15 秒；耗时动作应返回 accepted/请求 ID，再由行为记录反映实际执行结果，不让 HTTP 一直等模型。写操作超时标为结果不明且不自动重试；该页锁定对应重复提交入口。前端的确认、版本和按钮状态都不能替代服务端最终复核。

`State` 字段（缺失只显示未提供，绝不补造状态）：

```text
api_version: 1
context_id: string
contexts: [{id, label}]
updated_at: ISO时间或Unix秒
mode: "active" | "observe_only" | "disabled"
revision: string | number                   # 手动动作版本
capabilities: ["config.write", "behavior.preview", ...]
config:
  revision: string | number
  source: string                           # 原生配置来源的可读名称
  values: {字段键:实际值}
  fields: [{key,label,section,type,help?,options?,min?,max?,step?,readonly?}]
  # section: persona/emotion/behavior/night/experience/memory
  # type: boolean/enum/integer/number/string；options:[{value,label}]
  # 服务端决定可编辑字段，不从 UI 默认值派生配置。
persona: {name,id,source,revision,description}
bot_state:
  label, reason, updated_at, expires_at, source, version
  dimensions: {pleasure,arousal,stress,social_need} # [0,1]，须由adapter转换领域量纲
observation:
  subject, label, confidence, reason, observed_at, expires_at, source
  # confidence [0,1]；明确属于对方，不能用作 bot_state fallback
relationship:
  stage, raw, normalized, scale, source_completeness, identity_revision, reason
  # normalized [0,1]，raw/scale保留原量纲，不伪造未知维度
availability: {available, state, reasons:[]}
health: [{name,status,reason}]               # status: ok/degraded/unavailable
behavior: {enabled,remaining,cooldown_until,backoff,reason,candidates:[]}
night: {state,stage,energy,sleep_at,wake_at,reason,catch_up:{completed,total,reason}}
  # energy [0,1]；精力仅来自night
experience: {diary_enabled,dream_enabled,reason}
memory: {mode,provider,can_read,can_write,capabilities:[],reason}
actions: [{id,enabled,reason?}]
  # 前端仅识别 night.sleep/night.wake/diary.generate/dream.generate/
  # behavior.send；后三项可能计费，behavior.send可能真实发消息。
```

记录字段：

```text
公共: id, created_at, status, reason, source, request_id, latency_ms, context
emotion: before:{四维}, after:{四维}, expires_at, label
behavior: candidate, vetoes:[], result, intent_id
diary/dream: title, body, visibility, clarity, pinned,
            sources:[{kind,label,source_id,excerpt}]
# sources.kind: bot_action/human_action/dream/unknown
# dream始终标记为想象；缺省visibility显示"私人"，不提供分享/导出捷径。
```

未声明写能力或动作时禁用并解释；未提供列表接口时显示错误而非声称“没有记录”。主集成者可在 `api.mjs` / `model.mjs` 对接冻结后的名称与 R9 量纲，渲染层不读取私有对象、SQL 或配置文件。

## 页面实现

| 文件 | 责任 |
| --- | --- |
| `pages/livingemotion/index.html` | 七区语义骨架、跳转链接、文字主题按钮、范围选择、操作确认 dialog |
| `theme.js` | 样式表之前同步确定主题；系统初始偏好、手动持久化、页签同步和存储失败处理 |
| `style.css` | 白昼/黑夜语义色、细线编号与自有字标；390/1280 响应式；焦点与减少动效 |
| `model.mjs` | v1 UI DTO 校验、有限数值、字段白名单与分页校验，不跨类型补状态 |
| `api.mjs` | 唯一宿主 bridge 接口、错误恢复、超时与零自动写重试 |
| `app.mjs` | 七区渲染、四类记录、前后值和本地 SVG 曲线、配置草稿、模拟与真实动作 |

总览把 Bot 感受、四维与对方观察分别呈现；精力只来自长夜。情绪、行为、日记和梦境的服务端列表固定每页 10 条，来源与耗时默认 details 折叠，长列表候选和素材来源也按 10 条分页。梦境明确标为想象；私人全文默认折叠，没有直接向聊天分享的入口。

配置仅使用服务端返回的 fields/values，不保存第二套业务配置或默认值。页面刷新按钮保留草稿，切换分区和主题保留草稿；409 需明确重新读取最新配置并复核，不能盲目覆盖。非法输入跨分区仍阻止保存。浏览器整页刷新丢弃未保存草稿并提示离开；已经保存的配置从服务端重新读取。分区、筛选和页码记在 sessionStorage，主题记在 localStorage；私人正文、完整快照与配置草稿不进入浏览器存储。

所有接口文本经 `textContent` / 输入控件 `value` 展示，不解析为 HTML、Markdown 或可执行 URL。图形路径只由已校验有限数值生成。未配置模型、无真实路由或未声明动作时禁用相关按钮，不能使用测试数据降级。没有 bridge 时只显示宿主连接错误。

## 实测证据

日期：2026-11-05。macOS Darwin 24.6.0 / arm64，Node v25.6.0，Playwright 1.64.1，Chrome 156.0.8078.80。页面自身六个文件约 69 KB（未压缩，不含宿主 SDK），没有构建步骤或生产 npm 依赖；机器证据记录本次实际测试文件的 SHA-256。

- 单元测试：`node --test tests/ui/model.test.mjs`，**7/7 通过**。
- 合成浏览器：`tests/ui/browser.test.mjs`，**12/12 场景通过**；页面异常 0，非回环请求 0。
- 尺寸矩阵：390 × 844 与 1280 × 900，双主题 × 七区共 **28 组**，没有整页横向溢出或无文字按钮，主要按钮高度至少 44px。
- 可访问性：跳转链接、导航方向键 + Enter、原生 details、dialog Escape/焦点返回、分页焦点保留已实际操作；不以颜色独立表达状态。
- 首帧：同步 theme 脚本在 CSS 前；浏览器检查 DOMContentLoaded 时正确跟随系统。手动刷新保留、跨页签同步、系统变化、两种 storage 抛异常、宿主覆盖通用 `data-theme` 均已测试。
- 安全与交互：注入字符串未生成 img/script；401/403 与 message-only 拒绝清空私人视图；纯模拟仅访问 preview；unknown 动作没有再次发起；配置只发 patch/版本/原因；缺失数据和失败响应不显示合成兜底。
- 对比度：浏览器计算样式按 WCAG 相对亮度公式测量，共 **44 组**，覆盖默认七区、展开配置/保存区、私人正文/来源、dialog、加载、空记录、拒绝及错误反馈。

| 主题 | 正文最小值 | 控件边界最小值 | 焦点最小值 |
| --- | --- | --- | --- |
| 白昼 | 5.84:1 | 3.40:1 | 4.91:1 |
| 黑夜 | 6.88:1 | 3.76:1 | 6.34:1 |

机器证据：[`tests/ui/evidence/browser-results.json`](../tests/ui/evidence/browser-results.json)。截图均含合成范围标识，不包含真实账号或私人内容：

- [1280 白昼总览](../tests/ui/evidence/1280-light-overview.png)
- [1280 黑夜总览](../tests/ui/evidence/1280-dark-overview.png)
- [390 白昼总览](../tests/ui/evidence/390-light-overview.png)
- [390 黑夜总览](../tests/ui/evidence/390-dark-overview.png)
- [390 情绪与前后值](../tests/ui/evidence/390-dark-emotion.png)
- [390 私人阅读与来源](../tests/ui/evidence/390-dark-private-reading.png)

## 复跑

在插件根目录执行，无需安装插件到生产宿主：

```bash
node --test tests/ui/model.test.mjs
npm install --prefix tests/ui
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  node tests/ui/browser.test.mjs
```

没有本地 Chrome 时可用 `tests/ui/node_modules/.bin/playwright install chromium` 安装测试浏览器，然后不设置 CHROME_PATH。本次复用了已有 Playwright：

```bash
PLAYWRIGHT_MODULE=/tmp/at-guard-ui-tools/node_modules/playwright \
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
node tests/ui/browser.test.mjs
```

测试程序只监听临时回环端口，结束后关闭浏览器和服务。可选手动预览：

```bash
node tests/ui/server.mjs
```

打开终端返回的 `.../tests/ui/fixture.html`。测试服务只允许页面资源白名单；SDK 路径返回空测试脚本，fixture-bridge 只在测试 HTML 注入；不是生产认证服务，也不声称复刻真实父窗口。部署文件不得引用 tests。

## 尚未验收

以下仍需主集成者完成；不勾选 T9 整体完成，不以本测试替代：

1. 按上文 State/Records/Config/Preview/Action 冻结并接好真实 `page_api`；确认量纲、原因码与原生人格字段映射。
2. 对真实宿主的 legacy/v1 管理 GET/POST 验证额外令牌类型保护，拒绝 asset token、未登录、无权限与 `admin=true` 伪造参数。`host-contract.md` 的两项失败尚不能据此视为修复。
3. 在真实 Dashboard 外壳中确认带令牌的 SDK、iframe 父窗口握手、按钮数据返回、刷新与原生配置双向一致；当前通过的是无真实宿主的浏览器 fixture。
4. 后端审计、配置原子版本检查、各业务服务真实状态以及手动生成/发送的最终闸门。UI 只能按能力显示或禁用，不替代其实现。

本专项只写了页面、`tests/ui/` 与本文档。未修改入口/API/存储、其他代理文件或规格复选框，未 git commit、未部署、未调用生产模型或发送真实消息。
