# 管理后端 T9 / F1

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
expected_revision 原样传递，不在页面先查再写，不在冲突后重试。
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
