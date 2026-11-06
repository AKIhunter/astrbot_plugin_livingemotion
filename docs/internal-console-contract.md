# P5 管理 API / DT0

日期：2026-11-06。状态：P5 DT1 已冻结，实测入口与结果见末节。
消费者：已认证 Dashboard 控制台；不是模型工具。
实施文件仅 runtime/console.py、page_api/*、storage/console_data.py 和管理测试。
为真实 policy 对齐，另补 domain/emotion.py 的最小只读 baseline 属性，
decay_affect 与 Console 均读取它，未改变基准数值或规则。
保留 api_version=1 与旧 state/records/config/preview/action 字段。新增字段为添加式。

## 范围

新查询使用扁平 ScopeSelection 参数：persona_id、view_scope（global/private/group）、
context_id（可选真实 account_key）、platform（可选）。旧 context_id 调用继续支持。
global 仅查看，不创建 SceneKind、Context 或发送路由。指定 context_id 必须与人格、
平台、场景匹配；未知或不匹配返回 400，不回退全库。未指定人格的新范围查询返回 400。
GET scopes 可不带参数，用于首次发现人格；其余新接口必须指定 persona_id。
场景筛选不改变状态所有者，真实来源 ID 始终保留。

## 接口与 DTO

所有路径是 console/*，同一 Dashboard Bearer guard；HTTP envelope 保持
`{"status":"ok","data":...}`，Cache-Control=no-store。以下 DTO 均含 api_version=1。

| 接口 | 参数 / 返回 |
| --- | --- |
| GET scopes | 可选 persona_id/view_scope/context_id/platform；personas[{id,name}]、platforms[]、contexts[{id,persona_id,platform,view_scope,scene_id,account_id,label}]、counts{global,private,group} |
| GET state | 旧 context_id 或 ScopeSelection；原字段＋selection、state_mode、bot_state.baseline（0–1四维）、night.display_state（awake/nap/groggy/drowsy/deep_sleep）、night.energy_percent（0–100） |
| GET records | 旧参数或 ScopeSelection，kind=emotion/behavior/diary/dream、page、page_size=10、query≤200；items/total/page/page_size。emotion 只查情绪 trace，不查日记 |
| GET relationships | ScopeSelection、query≤200（账号搜索）、page、page_size=10、limit≤200（默认200）；center{id,persona_id}、nodes[]、edges[]、items[]、total、displayed、page/page_size |
| POST relationship | persona_id、platform、account_id、可选真实 context_id、score（展示0–100，步进0.1）和/或 frozen（bool）、expected_version（非负整数）、reason；返回 node 与 version |
| GET energy | ScopeSelection、page、page_size=10、可选 event_type；window_start/window_end、timezone、collected、reason、points[]、items[]、total/page/page_size；默认24小时，无旧历史则 collected=false，不伪造点 |
| GET settings-options | 无参数；personas[]、chat_providers[]、embedding_providers[]、groups[]；每个选项仅 value/label，不输出密钥或配置对象 |

关系节点字段：id（实例/人格/platform/account_id 的稳定键）、persona_id、platform、
account_id（原样）、label、score（0–100）、raw（0–1000）、normalized（0–1）、
stage、trust/familiarity/boundary（缺失为null）、frozen、source_completeness、
sources[{context_id,platform,view_scope,scene_id}]、version、updated_at。
图 nodes 与表 items 来自同一次查询的同一数据集；edges 仅 center→node，
不创建人物之间的边。total 是筛选后的完整数量，displayed 是 nodes 数量。
版本指账号覆盖版本（无覆盖为0），不冒充单会话 state 版本。

## 设置单一来源

config.values 来自 Config / AstrBot 原生配置，不新增设置数据库。
config.fields 每项 key/label/section/type/value，中文 label；
数字含 step/unit，Provider 字段含 options/provider_kind。groups 的任务分组：
quick_start/persona/emotion/relationship/behavior/night/experience/memory。
快速开始只引用 field_keys，不复制字段或值。常用字段与高级字段用 advanced 区分。
save 仍用 config POST，一份 patch、一次原生 save_config；revision 冲突人工刷新合并。
原生人格/Provider 列表通过宿主公开列举方法读取；不可用时空列表和原因，禁止猜选项。

## 认证、错误与重试

解析前、解析后调用同一 guard，输出前再复核。actor_id 从认证身份注入，
客户端 actor/admin/未知字段、重复 JSON/query key、非有限值、非0.1分值拒绝。
请求体上限32KiB。400=字段/范围错误；401/403=身份/权限拒绝；
409=配置/关系版本变化；503=依赖不可用/停止/未知失败，固定公开提示不泄漏异常。
读取可刷新；写入不自动重试。关系 override CAS 使相同旧版本重放得到409，
不重复写覆盖或审计。既有动作仍走唯一执行者，禁止全局 preview/action。
日记/梦境列表添加 `context_id/pin_available`。`POST action` 的 `experience.pin`
使用记录自身 `context_id`，另带 `entry_id/pinned/expected_pinned`，两个布尔值必须相反；
保留 `expected_revision/reason/confirmed=true` 和同一 Dashboard guard。
未授权 actor 输入拒绝；旧置顶状态重放409。整个旧记录、来源代际、置顶和审计
在原 SQLite 事务比较更新，不延长创建日期/TTL，不调用模型或发送。
全局列表可管理其中的真实来源记录，仍不构造全局 Context 或发送路由。
分页按时间与稳定ID降序；翻页间不承诺快照一致，不作全库客户端分页。

## 协调者挂接

storage.console_data 提供 `apply_relationship_override(store, context, relationship)`：
在 current_relationship 完成来源授权投影后调用，保留真实已知维度，
仅覆盖该实例/人格/平台/账号的 score/frozen，重新计算 stage。
不得用 helper 代替身份校验，relationship=None 时仍为None；最终使用前仍须原授权复核。
覆盖使用现有 runtime_meta，审计用现有 audit，与版本在 store._run 内同一事务。
P5 不修改 schema/sqlite/application/main/models。

状态与能量优先消费状态 agent 的公开 store 方法，通过 getattr 能力探测。
状态当前使用 get_state（状态 agent 已使其感知 owner），可选 get_owned_state 优先。
能量使用 energy_history(context, since, until, category, page, page_size=10, buckets≤1440)，
共享模式同一 owner 去重，场景模式按 owner 返回独立曲线系列；选择不改变真实来源。
points 字段为 at/energy/min/max/first/owner_key；items 保留原 energy_events 字段，
新增 id/at/kind/before_energy/after_energy/reason 别名（单位均0–100，delta同单位）。
UI 必须按 owner_key 分开连线。series_total 是状态所有者数量，points_truncated 标记裁剪。
只消费已落盘的 energy_history；缺少此端口返回503，不伪装“未采集”。
collected=false 只表示真实端口在窗口内查无事件。窗口外与未来事件被真实存储过滤。
已对齐 docs/internal-state-contract.md 的 energy_history / state_owner / get_state 端口；
状态模式的切换和业务生成/提交接点由主协调者整合，P5 不创建另一套执行链。

P1 当前 ScopeSelection 使用 scene_id 字段，P5 wire 继续使用 opaque context_id；
适配时先解析真实 Context，再将实际 scene_id 传给旧类。类新增 context_id 后自动采用。
Config 的旧规则值1/新安装值2由 Config/schema 负责，DTO 不自行更改默认。
Console.update_config 不调用 switch_state_mode，模式切换完全交 Application._replace_config。

## 实施检查

- [x] DT0 消费形状、兼容/错误/重试/来源边界已落盘。
- [x] 新管理入口与严格输入、guard 回归（4.29.4 ASGI 34项）。
- [x] 关系账号覆盖、平台隔离、审计、CAS 与 helper 实测。
- [x] state baseline/phase、集中设置与能量 store 契约实测；没有能力降级假通过。
- [x] 协调者挂接和实际缺口交接。

## 验证与缺口

本轮实跑（2026-11-06，合成宿主/消息、临时数据库，无真实模型/发送）：

```bash
.venv-ci/bin/python -m pytest -q \
  tests/console/test_management_dto.py tests/integration/test_application.py \
  tests/integration/test_projector.py tests/identity \
  tests/night/test_night.py tests/night/test_persistence.py tests/domain
```

最终 **809项通过**，退出码0。包含guard以外的真实临时库查询、关系版本/并发/持久化、
平台同号隔离、情绪不读取日记、五档DTO、浮点/原生选项、能量窗口边界/共享去重、
policy基准与衰减同源，以及原 observation=None 的实际Application回归。
4.29.4 管理 ASGI 34个测试方法通过；机器证据 tests/console/evidence-v4.29.4.json。
compileall 和 git diff --check 通过。Ruff 未运行：当前 venv 未安装该工具。
ASGI 运行器只收集 unittest 文件，portable DTO 测试走上述 pytest，避免混用环境。

```bash
"$ASTRBOT_HOST_PYTHON" \
  tests/console/run_host_asgi.py \
  --host-source "$ASTRBOT_HOST_SOURCE" \
  --sandbox-parent "$ASTRBOT_HOST_RUNS"
```

上述变量指隔离宿主的 Python、固定源码与临时验收父目录，路径已脱敏。

运行器新增 --host-version=4.29.1/4.29.2/4.29.3/4.29.4，前三版要求源码 HEAD
与本地对应精确发布 tag 一致，4.29.4 保持原 SHA pin；不能用4.29.4结果冒称四版通过。
tests/host/final_checks.py 中管理路由计数和HTTP正反例矩阵已改为10入口，
该全宿主验收由主协调者在四份隔离源码上执行，本专项未启动完整宿主或浏览器。

已确认 Application.current_relationship 在授权投影后调用 override helper，
api.py v1关系读取由协调者挂接；P5未修改它们或 relationship_projection.py。
Console 的额外同账号读取兼容重复挂接，helper 不重复添加 reason code。

已完成对齐：

- EmotionPolicy.baseline 属性已补齐，Console与decay读取同一属性，无常量fallback。
  定向反例改变policy基准，验证两者同时变化；领域回归也通过。
- 状态 agent 已对齐 Config/schema 新安装 night_policy_version=2、缺失旧字段解析为1；
  Console展示实际原生值，不自行替换默认或强启新睡眠阻断。
- energy_history 的 since/until 确为最近24小时；反例含窗口外/未来事件，均未进入DTO。
  共享owner只查询一次，delta固定精度与source_scope_key/source_id真实保留。
- 原 test_default_chat_without_model_and_unique_suffix 已实际通过，不改变其观察断言，
  不从global或其他账号补观察；另覆盖owner scene/shared的旧默认入口。

协调者最终整合/验收责任：

- 场景模式全局 state 是最近真实来源的数值视图，representative_context_id 明确该来源；
  没有伪造全局 Context，context_id为空且actions为空，不代表独立全局共享状态。
- 多 owner 精力 points 需UI按 owner_key分别连线；每桶保留min/max，不能把不同电池连成
  单条曲线。关系图表同源与设置控件的最终浏览器联调属于UI/协调者，不在P5修改范围。
- energy_history 分页为可变化集合；深页多 owner归并会多次读取，每次最多10条，
  尚无跨分页快照隔离/完整性能验收，不用本轮功能测试代替容量证明。

旧空参数 console_state() 的观察回归已复核：selection=None，context/account均真实，
owner scene/shared 两种模式均保留该账号HumanObservation；显式global才隐藏对方观察。
曾有并行整合时的短暂失败，最新“难过＋两次on_llm_request”实测与原回归均通过，
没有通过全局兜底或伪造观察来修复。
