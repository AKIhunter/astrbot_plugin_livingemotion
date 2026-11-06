# C15/C16 身份授权与关系投影修复

状态：**本专项完成并冻结交付**，2026-11-05 21:45:49 UTC。
必要窄回归 `102 passed / 26 deselected`；V05 原独立三参数只读复跑 `3 passed`。
**联合 V04/Application 与 H01/C39 未验收**，由核心接线、随后独立者验收。
不等待全部宿主修复，本专项释放名额；以下产品文件不再修改。

## SHA-256 冻结

| 文件 | SHA-256 |
| --- | --- |
| `adapters/identity.py` | `14e3bd04653f17d055c1800b23bf8bd003c42312c1beb67152ced193443a80d6` |
| `domain/relationship.py` | `fca375101f7ed93bf49b6c9a89c56d4138fc07821b148bb0dfe2fbd79caad8b5` |
| `runtime/relationship_projection.py` | `e7702f98fb6c973fa34153e2f549d8e55fec15139759ffe7de90ac3002150dc5` |
| `tests/identity/test_projection_access.py` | `77e7ba4f8880c6b0bb981689b86916f017917a37b3ba1d49d66d597ffaa905a2` |
| `tests/identity/test_projection_read.py` | `fae87d8ed8406345bff9a9f669aa26198a9d5a4361af9a9f6d7e9e0e3e11d1cb` |

哈希为本专项产品/测试边界，不替代全插件冻结版本。
文档只记录上述哈希，不自引用文档哈希。

## 身份与权限

专项：`identity-and-secrets`，高置信度。目标是修复来源读取授权和可撤销投影。
身份提供者的账号成员关系不是跨实例、跨 Bot、跨人格、跨场景授权。

| 读取路径 | 允许范围 | 撤销与失效 |
| --- | --- | --- |
| 无提供者/缺修订号 | 原账号、原场景、相同受众 | 不跨账号聚合 |
| 当前提供者的绑定私聊 | 同实例/Bot/人格；受众只允许当前绑定账号等价替换 | 读取前后复核快照，变化拒绝整个结果 |
| 群聊/公开评论 | 同场景、同受众 | 不继承私聊或其他群/评论线程来源 |
| 未知持久来源 | 拒绝作为聚合贡献 | 不根据裸账号或目标请求补造来源 |

本次不涉及密钥、管理员引导、紧急提权或身份服务迁移；不增加绑定权威表。
账本原地保留；读投影不写入任何账号的持久汇总，也不产生新证据。

## 接入交接

本会话未暴露代理消息工具，没有声称发过直接消息。
父已确认将本文固定协议转交核心及 F6；核心负责接线：

- 核心 `arun_6aeca78908a3b52e23bb04e7` 独占
  `runtime/application.py`、`adapters/astrbot.py`、`main.py`。
- 性能 `arun_6aecf4ef08a3b52e23bb0f31` 接管
  `storage/sqlite.py`、`runtime/projector.py`、`api.py`。
- 本专项仅改身份授权、领域投影、新增专项测试和本文件；
  已提供 `runtime/relationship_projection.py` 的独立服务。
- API 已出现对 `application.current_relationship(scope, record=record)` 的调用。
  核心请统一 API、行为快照、普通表达使用该方法，失败返回 `None`/不可用，
  不使用旧聚合结果；最终使用前继续执行原有上下文/人格/身份复核。
- 当前公开 store 有 `list_contexts(limit=512)` 和 `relationship_ledger(context)`。
  候选必须来自完整持久 Context，不从 events 或账号补造；未知来源不聚合。
  需要新增批量查询时由存储所有者提供，专项服务不会访问 SQL 或私有连接。

### F7/C39 固定公开协议

核心请定义 `Application.current_relationship(context, *, record=None)`。
API 所有者已经按该签名调用，目前未定义的方法也是 H01/C39 的失败原因。
核心负责先取得 `source = await bridge.current(context)`；不存在就返回 `None`。
随后只调用以下服务，身份快照和真实事件必须来自同一个已验证的 source：

```python
from .relationship_projection import read_relationship_projection

return await read_relationship_projection(
    self.store, self.bridge.identity, source.identity,
    event=source.event(), record=record,
)
```

服务签名：
`read_relationship_projection(store, identities, identity, *, event=None, record=None)
-> Relationship | None`。`None` 表示本次读取失败，不能回退旧聚合；
API 现有逻辑会转为 `unavailable/context_changed`。
未绑定/提供者不可用的**新本地快照**只读取本账号；
失效的旧绑定快照必须返回 `None`，不静默改成本地身份。

服务负责：

1. 读取前及最终返回前验证 identity fingerprint（含提供者实例、成员与 revision）。
2. 使用原始持久 Context 和原账本；不依赖保留期内 events，不补造来源。
3. 将账本中的维度按领域规则重投影；冻结标记仍属当前账号。
4. 来源账本与本账号快照不相符时只保留本地基线并标记不完整，不参与聚合。
5. 对读到的 scope/generation 做校验；数据清除后拒绝本次结果。
6. 不落库、不缓存、不访问模型或发送接口。

当前依赖的公开 store 方法为 `get_state`、`get_generation`、
`list_contexts(limit=512)`、`relationship_ledger(context)`。无需新增 schema。
`list_contexts` 达到 512 条时服务保守返回 `None`，不会悄悄汇总截断结果；
如需扩大支持，由性能专项提供按完整来源过滤/分页或原子批读接口再协调接入。
未知/不完整持久 Context 不能用传入目标的字段补齐。

最终使用仍由核心执行原有生命周期、人格、身份和清除代际复核。
特别是行为和普通表达在服务返回后继续 await 的情况，不能把本次 grant 当长期凭据。
请父将本协议转交核心及性能所有者。本专项不直接编辑其文件。

## 验证记录

首轮命令（插件根 cwd）：

```bash
env PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/.venv-ci/lib/python3.12/site-packages" \
$WORKSPACE/.livingemotion-host-t1/venv/bin/python \
-m pytest tests/identity tests/verification/test_cross_module.py \
-k 'not test_application and (identity or retained_source_ledger)' -q -p no:cacheprovider
```

实际 `91 passed, 26 deselected in 0.48s`，exit 0。
包括原 V05 三参数以及原 retained-ledger 领域组合反例。
这是最小授权修复结果，不是 V04/Application/H01 接线通过证据。
未修改 `tests/verification`，未运行全量、生产、真实用户或模型。

### 最终专项结果

- 新增服务测试首次为 `95 passed / 1 failed in 0.41s`。
  唯一失败是测试误用已关闭 SQLiteStore 实例重新 open；改为新实例重开同一临时库。
  没有修改产品存储行为或降低断言。
- 使用上面的同一窄选择命令最终为 `102 passed, 26 deselected in 0.55s`，exit 0。
- 额外用同一环境前缀运行
  `-m pytest tests/verification/test_cross_module.py::test_identity_grant_does_not_turn_private_account_binding_into_scene_access -q -p no:cacheprovider`，
  实际 `3 passed in 0.11s`，exit 0；未改独立反例。
- 新服务真实 SQLite/Projector 测试确认：31 天后 events=0，重开库仍保留账本；
  绑定服务读 1.0、解绑读 0.5；原账本和账号持久版本均未改变。
- 覆盖读取中 revision 变化、提供者丢失、来源 clear 的整结果拒绝；
  本地基线不相加、未知登记来源不猜测、冻结标记保留、候选截断拒绝。
- 授权矩阵覆盖实例、Bot、人格、私聊/群聊/公开评论、同号其他场景、
  额外受众、缺失受众、未知修订号类型；合法当前绑定私聊仍可聚合。

### 剩余接点

1. 核心完成 `current_relationship` 并统一 API、行为、普通表达读取。
   本专项没有编辑 API、Application、AstrBotBridge、SQLite 或 Projector。
2. 独立者在最终核心源码上运行原
   `test_application_bound_relationship_read_reprojects_retained_ledger`
   和 H01/C39 宿主检查；这里的服务 PASS 不能代替联合 V04。
3. 当前候选登记达到 512 条会保守不可用，账本读未做性能保证；
   批量/分页公开查询需求交存储所有者，不把本专项测试当 C51 性能证据。

所有输入合成，所有数据库位于测试临时目录。未访问生产、真实用户、模型，
未修改其他插件或父规格，未执行任何 Git 操作。
