# AstrBot 隔离宿主契约

状态：T1 独立有限宿主核实已完成并交接，**发现宿主 v1 页面令牌提权风险，不能判定完整页面认证验收通过**。
面向父代理及 `emotion_foundation`；没有可用的代理消息工具，使用此共享文件交接。

## 紧急接入警告

真实 `v4.29.4` 宿主中，页面入口签发的 scoped asset token 作为 Bearer 访问
`/api/v1/plugins/extensions/livingemotion_host_probe/status` 返回 **200**，POST
`/api/v1/plugins/extensions/livingemotion_host_probe/check` 也返回 **200**，两项安全断言失败。
静态依据：`astrbot/dashboard/api/auth.py:168` 的 `require_scope()` 验签后仅确认 `username`，
没有像 legacy middleware 一样拒绝 `token_type=plugin_page_asset`。
`require_dashboard_user()` 同样未检查令牌类型。

影响：只校验“经过宿主认证”的插件管理 handler 不足以证明管理权限；
`register_web_api` 自动同时暴露 legacy 和 v1 扩展入口，前端只用 legacy URL 不能消除 v1 风险。
父代理应在新插件管理 handler 内补独立的宿主已验证身份/令牌类型保护，或能力降级关闭私有页面，
并对页面 asset token → 读/写 API 两条路径做拒绝回归。不要修改本次只读宿主，也不要把该风险隐藏成测试桩问题。
无 token / 无效 token 的 API GET/POST 已实际返回 401；问题是资产访问权被 v1 误当管理权。

## 最小 Handler Guard

可直接参考独立编写且已实测的 `tests/host/fixture_plugin/guard.py` 和 `main.py:guarded`。
这是验证样例，未修改 livingEmotion 成品 handler；其集成由 foundation 负责。

真实宿主公开上下文：

- `from astrbot.api.web import request, error_response`；读取 `request.headers`、`request.username`。
- `context.get_config()` 不传 UMO 返回宿主默认配置（`star/context.py:648`），**不是插件配置**。
  其中 `dashboard.jwt_secret` 是 Dashboard 验签密钥；由 `dashboard/server.py:543` 初始化并持久化。
  在每次请求时读取，不能在插件 initialize 阶段要求其已经生成，更不能把它输出到响应/日志/新仓。
- 验签使用宿主已有 PyJWT：`jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "username"], "verify_signature": True, "verify_exp": True})`。
  不使用 `verify_signature=False`，不按 JWT 自报 alg 选择算法，不把 `request.username` 单独作为授权证明。
- 当前固定版本 Dashboard JWT 没有 `aud` / `iss`；不要关闭 audience 验证以接收未知 token，也不能虚构 issuer。
  额外要求 exp 是有限数值、username 等于宿主认证上下文且等于当前配置管理员。
- **只接受 Authorization Bearer**，没有 header 就拒绝，不回退 query token / API key / cookie。
  此最小样例不宣称 cookie-only 登录可用；若 foundation 增加 cookie-only 写入，需另做 CSRF/同源保护。

验签后按固定宿主实际签发结构分类，而不是凭客户端声明：

| 类别 | 实际依据 | Guard 策略 |
| --- | --- | --- |
| Dashboard 密码登录 JWT | `AuthService.generate_jwt():447` 签发 `{username, exp}` | 接受已验签且当前管理员匹配的最小结构 |
| Desktop Dashboard JWT | 同方法，额外 `auth_source=desktop` | 结构允许；桌面原生登录流程未执行 |
| plugin_page_asset | `PluginPageService.issue_plugin_page_asset_token():678`，同一密钥签发，但有 `token_type=plugin_page_asset` 等范围字段 | 无条件拒绝作为管理身份；页面/bridge 静态资产仍由宿主正常提供 |
| OAuth / 其他能力令牌 | 本标签源码只发现上述两处 `jwt.encode`，没有确认 Dashboard OAuth 签发/验证契约 | 默认拒绝任何 `token_type`，拒绝 `auth_source=oauth` 及 `scope/sub/aud/iss/client_id` 等非 Dashboard 字段；不将 OAuth token 自动升级为管理员 |

固定允许 claims 集合是 `{username, exp, auth_source}`；auth_source 只允许缺省/password/desktop。
这是严格的版本能力白名单，未来宿主新增合法 claims 也会先拒绝，须重新核实再扩展。
若外部签发者拥有同一宿主 HMAC 密钥并伪造完全相同的 Dashboard claims，则无法从 token 中区分；
不能声称 guard 能弥补宿主密钥泄漏或未定义的共享密钥 OAuth 设计。

Handler 的最小调用方式（完整验签逻辑在上述 guard.py）：

```python
async def guarded(self):
    if self.closed or not verified_dashboard_user(self.context):
        return error_response("Dashboard authentication required", status_code=401)
    return {"status": "ok", "data": {"guarded": True}}
```

已通过真实 HTTP 的 13 项 guard 断言：合法 Dashboard Bearer legacy/v1 GET/POST 共 4 项；
原生签发 asset token legacy/v1 GET/POST 拒绝共 4 项；同隔离密钥签名的合成 OAuth 类型、
OAuth 非类型 scope/sub、OAuth auth_source、伪造签名、过期 token 拒绝共 5 项。
其中 OAuth 是**合成 token 反例**，不是执行了真实 OAuth 登录。

## 环境与边界

- 固定宿主：AstrBot `v4.29.4`，HEAD `61335414433db721b3f7ecc93f90deafe0a59d78`。
- 获取：`gh repo clone AstrBotDevs/AstrBot .livingemotion-host-t1/AstrBot -- --depth 1 --branch v4.29.4`。
- 工作区根：`$WORKSPACE`。
- Python：`.livingemotion-host-t1/venv/bin/python`，CPython `3.12.16`。
- checkout：`.livingemotion-host-t1/AstrBot`；全部运行目录只放 `.livingemotion-host-t1/`。
- 本地另有 `/private/tmp/bot-t2-dialogue-20261104-TfDVPs/astrbot`，源码自报 `4.29.1`，没有完整 Git/依赖清单，不当作已运行的宿主。
- Python 3.11 测试环境不满足本标签 `requires-python >=3.12`。
- 本标签没有 `uv.lock`，依赖按 `pyproject.toml` 解析；后续记录实际安装清单，不能宣称 lockfile 重现。
- 禁止生产凭证、真实聊天/数据库、模型调用、平台连接和真实发送。支持范围须由本插件自行验证。

## 可立即接入的接口

| 项目 | 固定源码依据（checkout 内相对路径） | 接入结论 |
| --- | --- | --- |
| 生命周期 | `astrbot/core/star/base.py`、`star_manager.py:1422,1933` | `Star(context, config)`；异步 `initialize()` / `terminate()`；插件自行取消并等待自有任务。不要同时定义 `__del__` 和 `terminate`，宿主存在优先走 `__del__` 的分支 |
| 数据目录 | `astrbot/core/star/star_tools.py:244`、`utils/astrbot_path.py` | `StarTools.get_data_dir("astrbot_plugin_livingemotion")` 返回绝对 `Path` 并建目录；数据根来自导入前设置的 `ASTRBOT_ROOT`，结果为 `<root>/data/plugin_data/<name>`；不要在源码目录落库 |
| Bot 来源账号 | `astrbot/core/platform/astr_message_event.py:87` | `event.message_obj.self_id` / `get_self_id()` 是 Bot 账号；不是 provider、persona 或 sender ID |
| 适配器与平台实例 | 同上 | `event.platform_meta.name` 是适配器类型（如 aiocqhttp），`.id` 是配置的平台实例 ID；二者都保存，勿把 name 当唯一账号 |
| 会话路由 | `astrbot/core/platform/message_session.py`、`star/context.py` | `event.unified_msg_origin` 来自 `MessageSession(platform_name=platform_meta.id, message_type, session_id)`；保留真实 UMO 原值，不用裸群号猜路由 |
| 发送 | `astrbot/core/star/context.py:665` 的 `send_message` | `await context.send_message(umo, chain)` 按平台实例 ID 路由；返回布尔值表示找到匹配平台，不是外部平台消息 ID/可靠投递回执；超时仍须 unknown，不盲目重试。文档注明 QQ 官方平台不支持该方法；本专项未调用任何 adapter 发送 |
| 当前人格 | `astrbot/core/persona_mgr.py:123` | `await context.persona_manager.resolve_selected_persona(umo=..., conversation_persona_id=..., platform_name=...)` 返回 `(persona_id, persona_v3_or_none, forced_id, webchat_special_default)` |
| 人格优先级 | 同上 | 会话 `session_service_config.persona_id` > 当前 conversation 的 persona_id > 当前 UMO 配置 `agent_runner.config.persona.persona_id`（local runner）；`[%None]` 为显式无人格；不能只取 default_persona |
| 原生人格正文 | 同上 | 普通请求沿用宿主已组装的人格，只加状态；后台应取当前 conversation 后走同一解析器；`webchat_special_default=True` 时不要擅自当空人格或换成固定角色 |
| Provider | `astrbot/core/star/context.py:184,370,529` | `await context.get_current_chat_provider_id(umo)`；`await context.llm_generate(chat_provider_id=..., prompt=..., system_prompt=..., contexts=..., **kwargs)`，返回 `LLMResponse`；也可异步选 provider 后 `text_chat`，不要当同步方法 |
| Web API | `astrbot/core/star/context.py:774` 的 `register_web_api` | `context.register_web_api("/livingemotion/...", async_handler, ["GET"], desc)`；同 route + 同 methods 替换，不要每次重载叠加不同方法列表。未找到公开 unregister 入口，关闭时 handler 必须检查生命周期并拒绝操作 |
| Web handler | `astrbot/api/web.py`、`dashboard/api/plugins.py:235` | 优先 `from astrbot.api.web import request`，异步 `await request.json()`；宿主给 handler 传 URL 路径参数，不假设注入 FastAPI Request 形参；保留旧 Quart 的兼容性不能当新插件主要依赖 |
| 私有 API 鉴权 | `astrbot/dashboard/server.py:326`、`dashboard/api/plugins.py` | 实测无 token 的 legacy/v1 GET、POST 都拒绝；但 v1 接受页面 asset token，见上方阻断项。不要在未认证静态页直接暴露私有数据 |
| 插件页面 | `astrbot/dashboard/services/plugin_page_service.py` | `pages/<view>/index.html` 自动发现；正文通过宿主页面路由提供，资产令牌仅限页面/bridge，不等于管理权限 |
| Bridge | `astrbot/dashboard/plugin_page_bridge.js`、`services/plugin_page_service.py:581` | 脚本路径必须用 `/api/plugin/page/bridge-sdk.js`，宿主自动附资产令牌；v1 同名接口不能当作等价的 query-token 入口。`window.AstrBotPluginView`，兼容别名 `AstrBotPluginPage`；`apiGet(endpoint, params)` / `apiPost(endpoint, body)` 通过父页面代理，不把管理 JWT 放入插件源码 |

## 环境一致性约束

| 维度 | 隔离本地 | CI / 预发布 / 生产 | 漂移预算及处理 |
| --- | --- | --- | --- |
| 依赖 | 固定源码 HEAD，记录 Python 与实际依赖 | 未验证 | HEAD 或能力签名变化即重跑，不扩展兼容声明 |
| 配置 | 合成全新配置，空 provider / 外部平台 | 未比较 | 只允许合成值差异；缺字段须能力降级 |
| 数据 | 空库及人工构造输入 | 禁止复制生产值 | 生产聊天、账号、密钥进入测试为零容忍 |
| 时钟 | 记录实际时间；无时间场景结论 | 未验证 | 本专项不证明作息/性能指标 |
| 网络 | 依赖安装可访问包源；运行期禁止外联 | 未验证 | 运行期任何非回环连接应失败 |
| 凭证 | 仅隔离运行随机生成 | 禁止读取生产凭证 | 不输出认证 token/密码到新仓 |

检查方式：每次测试记录宿主 HEAD、源码哈希、Python 和包版本；读取状态与页面路径的测试必须经过真实宿主认证代码。
合成 handler、合成事件和假 Provider 即使使用真实宿主类，也必须单独标识，不能描述成真实平台/收费模型验证。

## 已执行证据

最终运行：`2026-11-05`，临时根 `.livingemotion-host-t1/runs/run-lk1wj_1v`。
机器可读脱敏证据：`tests/host/evidence-v4.29.4.json`，包含 14 个宿主选用文件 SHA-256 和实际依赖版本。
**48 项检查：46 通过、2 项未加 guard 的宿主鉴权安全断言失败，退出码 2。** 这不是全绿验收。

| 验证项 | 层次 | 结果 |
| --- | --- | --- |
| 核心初始化、插件管理器加载、独立数据目录 | 真实宿主代码 + 独立探针插件 | 通过 |
| 三次 reload，旧任务退出、只剩一个任务、路由未重复 | 真实宿主生命周期 + 自写 fixture | 通过，不代表 livingEmotion 最终生命周期已验收 |
| Bot self_id / 适配器 name / 平台实例 id / UMO | 真实 AstrMessageEvent 类 + 全合成输入 | 通过；没有真实平台入站消息 |
| 配置人格、conversation 参数、强制会话人格、显式 none | 真实 PersonaManager / SQLite / SharedPreferences + 合成配置 | 通过；没有经过生产聊天 pipeline；WebChat 特殊人格分支仅源码核对 |
| 缺失 Provider | 真实 Context.llm_generate，未配置任何 Provider | 正确抛 ProviderNotFoundError；未执行模型生成、假模型成功响应或付费请求 |
| HTTP 服务 | 完整真实核心与 AstrBotDashboard ASGI app，Uvicorn 回环端口 | 启动于临时端口 55307，已关闭；不是生产 Hypercorn 启动器等价验证 |
| 无登录 / 无效登录 GET、无登录 POST | 真实 HTTP + 原生鉴权 | 401 |
| 登录、legacy/v1 handler、原生 request.json | 真实登录 + 自写无敏感 fixture | 200；密码随机生成且不写入证据 |
| 页面入口、带范围令牌的 HTML、bridge JS | 真实页面发现与 HTTP 静态内容路径 | 200；无 token 的页面入口及 bridge 401 |
| 页面 asset token → legacy 管理 GET | 真实 HTTP | 401 |
| 页面 asset token → v1 管理 GET / POST | 真实 HTTP | **200 / 200，阻断完整安全验收** |
| 增加最小 guard 后的合法 Dashboard / 非管理令牌 | 真实 HTTP + 独立 guard fixture | 13 项通过；见上方 guard 说明，不表示成品 handler 已修复 |
| 正常停止与自有任务取消 | 真实 core.stop / fixture.terminate | 通过，子进程已退出，无遗留宿主服务 |
| 原生 Dashboard 外壳、iframe 握手、页面按钮、390/1280 | 未执行 | 不宣称浏览器 bridge 交互、UI 或完整 livingEmotion 页面通过 |
| livingEmotion 最终插件加载 / 可选插件共存 | 未执行 | 本专项只加载自写探针和宿主 builtins，不接入并行构建中的新插件 |

运行中宿主会尝试获取 T2I endpoints 和模型元数据，3 次非回环 DNS 解析被 audit hook 拒绝；
一次运行期子进程启动也被拒绝。无 Provider / 外部平台配置，真实模型调用数 0、真实消息发送数 0。
该保护是测试进程 Python audit hook，不是操作系统级沙箱；不能作为运行恶意插件的安全边界。
未修改旧插件或宿主源码；宿主 checkout 最终 `git status --short` 为空。无 git commit、push 或远端建仓。

## 运行与交接

从工作区根复跑，脚本自动创建新的隔离根、清空继承环境、复制自己写的 fixture，并在 150 秒内结束：

```bash
.livingemotion-host-t1/venv/bin/python \
  插件/astrbot_plugin_livingemotion/tests/host/run_isolated_host.py \
  --host-source .livingemotion-host-t1/AstrBot \
  --sandbox-parent .livingemotion-host-t1/runs
```

当前固定宿主预期退出码 **2**：运行完成但两项范围令牌拒绝断言失败；0 才是所有断言通过，1 是中途失败。
详细日志及新生成的隔离数据库只留临时根；不要将整个目录加入仓库。

依赖安装使用临时 `bootstrap-venv` 内的 uv，从宿主 pyproject 解析（并非 locked）：

```bash
env UV_PYTHON_INSTALL_DIR="$PWD/.livingemotion-host-t1/python" \
  UV_CACHE_DIR="$PWD/.livingemotion-host-t1/uv-cache" \
  .livingemotion-host-t1/bootstrap-venv/bin/uv pip install \
  --python .livingemotion-host-t1/venv/bin/python \
  -r .livingemotion-host-t1/AstrBot/pyproject.toml
```

给 foundation：使用本文件的路径/人格/Provider 接点；不要把 send_message=True 视为可靠投递；
管理端必须补页面令牌类型保护，再由新插件集成测试核实。
给 UI：`/api/plugin/page/bridge-sdk.js` + `AstrBotPluginPage.apiGet/apiPost`；
HTTP 页面/资源已核实，父窗口代理握手与交互尚需 UI 专项验证。
历史基线保存在 Git 历史；新验收应记录当前源码哈希，不覆盖旧证据。
本独立任务已结束，不占用后台进程；后续 T5 可接续。最低支持版本仍未知，当前只能声明对该 HEAD 的以上有限实测结果。
