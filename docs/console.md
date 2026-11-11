# 管理后端 T9 / F1

本文前半保留 2026-11-05 的 T9 验收历史；当前关系、日记面板、发送凭据与模型诊断契约见文末的「2026-11-09 更新」。

日期：2026-11-05。负责人范围仅 `page_api/`、`tests/console/`、本文。
当前状态：五个成品 handler、严格 Dashboard guard 及真实宿主路由 ASGI 专项已完成。
最终插件 HTTP 和 iframe 验收交独立验收，不等待核心集成结束。

## 给核心集成者：立即可接的冻结接口

与 `INTEGRATION.md` 的 Application v1 一致，不增加第二套业务配置、缓存或存储。

```python
from .page_api import PageAPI

# application 由 main 创建并 initialize；页面不构造业务服务。
self.page_api = PageAPI(self.context, self.application)
self.page_api.register()       # 同步
# terminate / reload：先拒绝旧页面请求，再停止 application。
self.page_api.stop_accepting() # 同步、幂等；旧实例不能重新开启
```

`PageAPI(host_context, application)` 的第二参数满足
`page_api.protocols.ConsoleApplication`（结构化 Protocol）。所有方法 async，
返回 `ui.md` 的 data DTO，不是 HTTP envelope：

```python
console_state(context_id: str = "") -> dict
console_records(context_id: str, kind: str, page: int = 1,
                page_size: int = 10, query: str = "") -> dict
update_config(patch: dict, *, expected_revision: str | int,
              reason: str, actor_id: str, context_id: str = "") -> dict
console_preview(context_id: str) -> dict
console_action(context_id: str, action: str, *,
               expected_revision: str | int, reason: str,
               actor_id: str, confirmed: bool) -> dict
```

已知业务异常遵循 `ApplicationError.code/status_code` 契约：
`validation_error=400`、`unauthorized=401`、`forbidden=403`、
`version_conflict=409`、`unavailable=503`。页面不硬依赖尚在实现的 application 模块；
只映射上述有限码和状态，使用固定公开提示，不回显异常字符串、正文或密钥。
未知异常为 503，写入不自动重试。

## 路由与兼容

| 前端 bridge 相对路径 | 注册给 Context 的路径 | 方法 |
| --- | --- | --- |
| `console/state` | `/astrbot_plugin_livingemotion/console/state` | GET |
| `console/records` | `/astrbot_plugin_livingemotion/console/records` | GET |
| `console/config` | `/astrbot_plugin_livingemotion/console/config` | POST |
| `console/preview` | `/astrbot_plugin_livingemotion/console/preview` | POST |
| `console/action` | `/astrbot_plugin_livingemotion/console/action` | POST |

真实 v4.29.4 `Context.register_web_api` **不自动添加插件名**；
`dashboard/api/plugins.py` 的 matcher 将整个 plugin_path 与注册路径匹配。
因此不能只注册 `/console/state`，也不能用 `/livingemotion` 替代 metadata 中的插件名。
legacy 为 `/api/plug/astrbot_plugin_livingemotion/console/*`；
v1 为 `/api/v1/plugins/extensions/astrbot_plugin_livingemotion/console/*`。
前端父窗口将 `console/*` 组装成后者，原生 SDK 继续使用
`/api/plugin/page/bridge-sdk.js`，无需更改页面。

每个方法固定单元素 methods，同路径注册替换；没有公开 unregister 时旧 handler
通过 `stop_accepting()` 拒绝。无需、也不允许另开匿名 HTTP 服务。
成功为 `{"status":"ok","data":...}`；错误仍用真实 HTTP 状态，
message 带 `[livingemotion:<code>]`，适配 bridge 只保留 message 的行为。
全部响应 `Cache-Control: no-store`，私人读也执行同一 guard。
这是新增 v1 承诺；后续只增可选字段，语义变更须同步 UI 与契约测试。

## 授权边界

每个请求重新读取 `host_context.get_config()["dashboard"]`，只用于获取当前宿主
JWT secret 和管理员 username。这不是插件业务配置，绝不写入或输出。
只接受单个 Authorization Bearer，固定 HS256 验签及 exp 验证；
claims 精确白名单 `{username, exp, auth_source}`，auth_source 仅缺省/password/desktop。
username 同时匹配已认证 `request.username` 和当前管理员配置。
拒绝 asset、OAuth/未知 claims、无 token、伪签、过期和非有限 exp；
不信任 `admin=true`、客户端 actor_id、query token、API key 或 cookie-only 登录。
不关闭 audience 校验、不允许 alg 自选；共享密钥泄漏不在此 guard 的防御能力内。
认证先于请求解析，并在解析后、输出私人响应前再次复核。
读取期间停止实例或管理员/密钥撤销时不再返回私人快照；
写入期间撤销不能追溯撤回已经提交的核心事务，响应不得被解释为可安全重试。

核心负责 context_id 解析及当前范围授权：仅使用 `contexts` 已发布的 opaque ID；
不能接受客户端构造的 Context 或按裸账号猜范围。
state 的空 context_id 选择最近授权范围；没有互动时展示真实配置/健康及空状态。
records/preview/action 必须提供非空 context_id；未知范围必须拒绝，不降级到全库。

## 配置与动作职责

请求字段严格白名单，重复 query/JSON key、未知字段和非有限 JSON 数值拒绝。
body 上限 32 KiB；context_id 最长 512 字符，query 最长 200 字符，
reason 去空白后必填且最长 1000 字符，revision 为非空字符串或非负整数。
records kind 仅 emotion/behavior/diary/dream，page 从 1 起且至多 1000000，
page_size 固定 10，服务端过滤后 total；created_at 降序、ID 决胜。
这是可变化列表，不保证翻页期间快照一致；页面不请求全库后自行分页。

配置 patch 使用公开 `Config` 字段作为白名单/类型验证来源，字符串上限 8192；
**最终校验、与当前值合并、CAS、save_config 和审计全部由 update_config 完成**。
页面不从 partial patch 构造带默认值的 Config，避免误拒绝已配置人格/作息的局部修改。
不能通过页面直接读写 SQL、私有 store/cfg 或生成自己的持久配置。
expected_revision 原样传递，应用层在锁内执行 CAS。页面可在提交前读取最新配置，
核对草稿涉及的字段；这不能替代应用层版本校验，也不能在冲突后自动重试写入。
actor_id 只来自验签后的 Dashboard 身份。

`console_state` / `console_records` 的 DTO 映射由 Application 唯一负责：
Bot pleasure = `(x+1)/2`，night energy = `x/100`；
观察 labels/subject_id/occurred_at 不进入 Bot 状态。
来源、有效期、变化前后、分型原因与梦境想象标记保留，不为缺失信息补造业务数据。

preview 只调用 console_preview，必须 model_calls=0、sends=0。
action 只允许 night.sleep/night.wake/diary.generate/dream.generate/behavior.send，
必须严格 confirmed=true、版本和原因；application 重新核查当前 actions、服务、范围及硬闸门。
前两者为管理作息；生成可能计费；behavior.send 可能真实发送，必须走唯一执行者。
未连接服务返回明确 unavailable/拒绝；不能假成功，也不能把 queued 说成持久 accepted。
写入及动作没有 HTTP 自动重试：旧 revision 冲突，结果 unknown 不重发。
长期动作使用核心持久意图/请求 ID 与额度，不在页面创建任务或第二套幂等账本。

本版不新增关系 HTTP 动作，避免扩大前端已冻结操作集合。
核心公开 `correct_relationship(context_id, *, expected_version, score=None,
frozen=None, reason, actor_id)` 可用于管理修正/冻结，必须状态、来源账本、审计同事务；
页面未来接入仍必须使用相同认证与版本检查，不能直接 SQL。

## 验证进度

- [x] 已读取父规格、ui、host-contract、FOUNDATION、CONTRACTS 和 INTEGRATION。
- [x] 冻结构造/注册、Application Protocol、路由、认证、错误和事务边界。
- [x] 实现成品五个 handler 和严格 Dashboard guard。
- [x] 使用合成数据验证全部入口认证正反例、请求校验、CAS/审计参数委托。
- [x] 真实宿主 request/路由/auth 代码的 ASGI 回归，记录复跑命令和证据。
- [ ] 最终真实插件 HTTP 与 iframe 联验（独立验收负责，不能用本专项替代）。

## 实际验证证据

执行时间：2026-11-05T21:00:36Z。macOS Darwin 24.6.0 / arm64，
Python 3.12.16；PyJWT 2.15.1、FastAPI 0.162.0、Starlette 1.10.0、httpx 0.28.1。
宿主固定 `v4.29.4` / `61335414433db721b3f7ecc93f90deafe0a59d78`。

从工作区根执行：

```bash
.livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/console/run_host_asgi.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs
```

结果：**30 个测试方法通过，262 个子用例通过，失败/错误/跳过均为 0，退出码 0**。
子用例包含嵌套参数组合，不将两项相加宣传为独立测试数量。
机器证据：[evidence-v4.29.4.json](../tests/console/evidence-v4.29.4.json)，
含宿主选用文件及成品/测试 Python 文件 SHA-256、实际依赖版本、逐项结果。

| 层次 | 实际覆盖 | 边界 |
| --- | --- | --- |
| 成品认证正例 | 宿主 `AuthService.generate_jwt` 签发标准 `{username,exp}`，五个接口 legacy/v1 均返回 200；desktop 签发结构及显式 password claims 也放行 | 使用合成管理员；不是生产密码登录/桌面客户端流程 |
| 资源令牌反例 | 宿主 `PluginPageService.issue_plugin_page_asset_token` 签发真实 asset 结构，五接口 legacy/v1 全部拒绝；v1 成品 guard 返回带前缀 403 | 不依赖前端隐藏按钮或只测拒绝 |
| 其他认证反例 | 伪签、过期、缺 exp、HS384、OAuth 类型/scope/sub/auth_source、aud/iss/client_id、未知 claims、不同用户名、admin=true、cookie-only/API key/query token、重复 Authorization、非有限 exp | OAuth 为合成令牌反例，非真实 OAuth 登录 |
| 真实宿主路径 | 原生 Context.register_web_api、legacy auth_middleware、v1 require_scope、扩展 router/matcher、PluginRequest/bind_request_context | FastAPI ASGITransport，无 TCP 监听、无完整 Dashboard/插件生命周期启动 |
| 请求与委托 | 五接口 whitelist；重复 JSON/query、非法类型、32 KiB、固定每页 10、四种记录、指定 context_id、actor_id 来自验签、CAS 冲突 409、原因/版本原样委托且不重试 | Application 是合成 call-recording double；不声称完成核心配置原子性、真实审计持久化或 SQL 范围过滤验收 |
| 状态与动作 | 已归一化 Bot/精力 DTO 不二次转换、观察分型/来源/过期保留；preview 只调无费用端口；五种动作准确委托；未接服务 503、不假 success、不泄漏异常正文 | DTO 为合成数据；真实核心映射、模型预算及唯一发送由核心与独立验收负责 |
| 生命周期 | 同路由替换、不增加重复 route；停止旧 handler 拒绝；读取中停止/撤销不输出私人数据；解析中撤销不进入写方法 | 未启动业务任务，无真实模型和消息发送 |

运行器创建并清理独立临时 ASTRBOT_ROOT，清空继承凭证/代理环境；
运行期 audit hook 拒绝 socket connect/bind/DNS 和子进程。
最终运行上述尝试计数为 **0**。这不是操作系统沙箱，也不作为恶意插件隔离机制。
第一轮测试断言全过但平台信息采集 `platform.platform()` 触发两次被拦截子进程，
运行器因此返回非零；已改成 `os.uname()`，最终复跑为零尝试，未放宽运行门槛。
宿主依赖 jieba 有预存 SyntaxWarning，本次没有修改第三方依赖。

补充复跑：`node --test tests/ui/model.test.mjs` **7/7 通过**；
`.venv/bin/python -m compileall -q page_api tests/console` 退出码 0。
普通无宿主 pytest 收集时本专项明确 skip 并提示上述运行器，不伪装无宿主认证测试。

## 文件交接

| 文件 | 责任 |
| --- | --- |
| `page_api/__init__.py` | `PageAPI` / `ConsoleApplication` 导出 |
| `page_api/protocols.py` | 五个 Application async 方法、宿主 Context 结构端口 |
| `page_api/routes.py` | 正确插件前缀注册、五 handler、停止闸门、响应封装/不缓存 |
| `page_api/guard.py` | 每请求有效验签、Dashboard claims/用途及当前身份严格复核 |
| `page_api/validation.py` | 输入白名单、重复键/大小/类型、分页/动作/版本边界 |
| `page_api/errors.py` | 固定公开错误、bridge message 前缀、异常脱敏 |
| `tests/console/` | 独立运行器、成品与真实宿主 ASGI 专项、脱敏证据 |

父代理可直接按本文开头注册，不需要等待本专项其他实现。
最新读取的 `main.py` 已由核心代理接上 PageAPI；本专项没有修改该文件，
也没有据此宣称最终插件安装/HTTP/iframe 或核心事务已验收。

本专项不修改 core、父规格或旧仓，不 git 提交，不调用真实模型或发送消息。

## 2026-11-09 更新：关系、阅读面板与运行诊断

以下说明当前实现，替代上文历史版本中关于关系接口、生成入口和操作确认的限制。

### 关系查询与基础信息

`GET console/relationships` 新增可选 `graph_scope`。旧调用默认 `matched`；
页面使用 `neighbors`，先在授权范围内建立可信关系，再按账号/昵称匹配目标，
精确账号匹配优先。一跳邻居只扩展图的 `nodes`，不会进入搜索结果 `items`；
列表仍每页 10 人。平台相同且账号相同才认作同一人物，不合并不同平台的同号账号。
当前 Bot 人格固定在中心，图最多绘制 200 人，目标优先于邻居。
`focus_ids` 标识匹配目标，`graph_total` 和 `truncated` 解释图的截断；
`total` 始终是列表匹配人数，因此 `nodes.length` 可以大于 `total`。

人物之间的虚线必须带真实、授权且可核对的依据；读取授权记忆后再次检查
generation 和当前来源。未知来源、已撤销材料或被清空后的迟到结果不会补进图。
布局不新增关系事实，推测关系仍明确标注“推测”。

图中点击人物只展示阶段、关系维度、备注、冻结状态和已有来源。
列表的“编辑”入口可同时修改好感、冻结和备注；真实 QQ 昵称、平台和账号只读。
`POST console/relationship` 的 `note` 最多 1000 字符，不接受控制字符；
省略或 `null` 保留原备注，空字符串清除备注。好感、冻结、备注、版本与审计
在同一存储事务内提交。编辑开关必须显式开启；关闭返回 `edit_disabled/403`，
不会把业务上的关闭误当成退出宿主登录。

保存要求真实版本和非空修改原因。409 保留草稿，需读取最新关系后人工复核；
超时或未知结果保留草稿并禁止重复提交，只允许重新读取核对。
只改备注/冻结/版本时，刷新图中资料但保留三维位置和相机；列表翻页不重建图。

### 三维布局

`charts/force3d.mjs` 使用账号固定种子生成有正负深度的体积分布。
Bot 吸引、人物排斥、可信边弹簧和碰撞同时作用于 x/y/z；有关系的人形成分团，
无关系的人不会为视觉效果而添加连线。模型空间有中心间距和外界边界。
透视、大小、明暗和遮挡顺序随真实深度变化，允许背景旋转、缩放、
Shift 拖动节点、暂停和复位。

动画用 `requestAnimationFrame`，最多 120 帧且约 2 秒停止；隐藏页面、卸载
或切换减少动效时停止循环。减少动效采用一次静态计算。
三维碰撞不承诺每个视角下所有屏幕投影都不重叠。

### 日记与梦境

设置、日记、梦境三个 panel 常驻；菜单背景滑块移动 280ms，
切换后的正文淡入 140ms。减少动效时直接切换。
桌面阅读区高度 `clamp(480px, 68vh, 760px)`，手机为
`clamp(360px, 62dvh, 620px)`，长内容在各自面板内滚动。
各 panel 保留滚动位置、正文展开、分页和设置草稿，键盘支持左右、Home、End。
状态提示区域预留高度，避免生成完成提示挤动外层页面。

两个记录区分别加载并拒绝迟到响应；切换不重复读取已加载记录。
两秒轮询只更新对应任务和成功后的档案，不重建整个页面，不重复生成。
轮询与生成响应都核对当前请求 ID，旧请求不能覆盖新任务。
手动按钮仍立即生成当日内容，成功后替换当天同类内容并保留置顶；
刷新只读取状态，自动生成设置与日额度不限制手动按钮。
置顶控制仍受当前授权、快照状态和未知结果限制。

### 主动发送和情绪为什么可能平静

AstrBot v4.29.4 的 aiocqhttp 事件发送封装不返回原始消息编号；
宿主的 `True/None` 无法证明协议端确认。因此“未知”不能直接解释为没发出去。
当前插件在验证真实原生事件类型、已记录 session、Bot 身份、平台与目标后，
单次调用原生 QQ 客户端；取得有效消息编号（支持负编号）才返回 `confirmed`。
明确拒绝返回 `rejected`；缺编号、异常响应、提交后超时/取消保持 `unknown`，
不自动重试或降级重发。其他平台继续保留原宿主通道，不凭布尔结果宣称成功。
授权成功后再次检查发送截止时间，避免同一轮事件循环里过期后才提交。

新行为记录附带 `purpose`、`transport_status` 和 `receipt_id`；
页面区分主动行为、睡前收尾与醒后补答，展示“协议端已确认”或
“结果不明，可能已经发送”。旧记录显示“未采集”，不追认历史成功。
`behavior_transport` 健康项检查真实原生路由，平台名字匹配不足以标为可用。

情绪处理依赖新互动的实时规则、衰减和可选模型细化；LivingMemory 中
情绪词的数量不决定当前标签。模型关闭、仅观察、真实来源失效、
预算/频率拒绝、模型不可用、格式无效或旧版本结果丢弃，都可能留下平静标签；
有效分析也可以返回零调整。不能仅凭标签确认其中哪一项是生产故障原因。

`runtime/refinement.py` 为有界异步任务持有真实消息来源，在完成/取消后释放，
防止合法任务仅因原生事件被回收而失效；调用前和提交前仍检查身份、
owner/version/generation，不回放旧聊天，不重复记账。
`emotion_model_analysis` 暴露最近分析的阶段、受控原因和时间，
最多保留 128 个授权上下文的最近结果，不保存正文或模型原文。
关闭、排队、执行、无效输出、预算拒绝、取消、零调整完成和旧结果丢弃均可区分；
重启或旧数据没有诊断时显示“未采集”。
`behavior_model` 只预检查模型绑定和预算参数，不调用模型。

本地验证命令与结果见
[本轮验证记录](verification-relations-emotion-20261109.md)。
这些是隔离代码/浏览器证据，不代表已部署或已确认线上实际发送。
