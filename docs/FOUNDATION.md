# T1/T2 基础阶段交接

日期：2026-11-05。负责范围：入口、共享契约、原生配置、公开门面骨架、
SQLite 状态存储、实例运行时及根测试配置。仅新增本插件文件，没有提交 Git、
创建远端仓库、修改父规格复选框或更改既有消费者文件。

## 已实现

| 内容 | 入口 / 证据 |
| --- | --- |
| 宿主独立类型 | `contracts.py`；具体字段、量纲与方法见 `CONTRACTS.md` |
| 原生生命周期骨架 | `main.py`、`runtime/lifecycle.py`；使用 `Star(context, config)` 及 `StarTools.get_data_dir("astrbot_plugin_livingemotion")` |
| 默认安全配置 | `config.py` 与 `_conf_schema.json` 默认值逐项测试；active、本地规则状态可用，memory=none，模型/日记/梦/自主/导出均关闭 |
| R9 v1 门面 | `plugin.api`；能力、事件、Bot/对方分型状态、关系、可用性、无费用模拟、健康查询；业务未接线时明确降级 |
| 持久宿主实例 | `SQLiteStore.get_instance_id()`，同库重启不变；加入 Context.scope_key，真实 facade 拒绝其他实例 |
| 原子状态 | WAL、FULL 同步、短事务、全部 SQLite 操作走 to_thread；事件/幂等/多投影/来源关系账本一同提交，CAS 冲突不半写 |
| 有界正文 | 默认 7 天、每场景 200、全库 10000、单条 8000 字符；正文不复制到长期事件元数据；查询按发生时间过滤 |
| 清除与恢复 | 清除代际拒绝迟到回写；保留非正文事件幂等和配额，不用清除重置预算；关系账本保留原账号来源 |
| 额度与意图 | 原子额度预留、跨重启/失败不退款、全局/用途/场景限制、情绪 300 秒间隔；意图 CAS、单额度不复用、sending 重启变 unknown |
| 后台任务 | 默认 1 工作者、队列 100、queued 与持久 accepted 分离；声明 Token 上限、超时、任务去重、取消与等待 |
| 维护 | SQLite backup 一致备份、失败迁移事务回滚、事件/体验到期清理；旧实例 API 停用 |

`StateWrite.value` 支持 T3 文档约定的 `_runtime` 与快照同事务持久化；
R9 状态输出已经过滤以下划线开头的内部字段。未直接接入领域纯函数。
模型真实 tokenizer 与 Provider 输出 Token 限制由调用服务落实；
运行时的声明额度验证不能冒充模型端已经执行 Token 限制。

## 实际测试

环境：macOS，Python 3.11.9，插件内独立 `.venv`；
pytest 8.4.2、pytest-asyncio 1.4.1.post1。仅合成数据和临时数据库。

```bash
.venv/bin/python -m pytest \
  tests/contracts/test_foundation.py tests/storage/test_sqlite.py \
  tests/runtime/test_background.py -q -o faulthandler_timeout=15
```

最终本阶段结果：**56 passed in 1.49s**。
覆盖 20 并发 CAS、两个真实 SQLite 连接竞争、原子回滚、重载幂等/配额、
清除期间迟到任务、来源/实例隔离、有界窗口、WAL 备份、失败迁移、
三次生命周期重载、队列满拒绝、取消线程等待、超时/并发预算、
内部 runtime 不公开以及 `admin=true` 不能伪造 Context。

首轮测试在停止队列时暴露取消竞争：`wait_for` 的内层任务恰好完成时，
旧工作者可能继续等待队列。已改为停止接收后退出工作循环，并完成回归。

合并现有 T3/T4 的兼容测试：

```bash
.venv/bin/python -m pytest \
  tests/contracts/test_foundation.py tests/storage/test_sqlite.py \
  tests/runtime/test_background.py tests/domain tests/identity tests/memory \
  -q -o faulthandler_timeout=15
```

结果：**207 passed in 2.97s**。这包括其他代理的测试，不冒称全部由本代理编写。
`python3 -m compileall -q contracts.py config.py api.py main.py storage runtime
tests/contracts tests/storage tests/runtime` 退出码 0。

## 下一阶段接线顺序

1. **T3 投影器**：按 `DOMAIN.md` 还原嵌套 EvidenceRef/Context，拆读 `_runtime`，
   调用 apply_emotion/apply_relationship，将 Bot、观察、关系、runtime 与贡献一次提交。
   接入 `LivingEmotionAPI(project_event=...)`，CAS 冲突重读重算，清除代际不能更新后重试。
   管理关系修正仍需增加带已认证主体/理由/版本的原子状态+账本+审计入口；
   现有通用 write_states 不声称已具备这个管理事务。
2. **T4 宿主与记忆**：`memory.md` 中 context_from_event 已把 host_instance_id 纳入 bot_id，
   还须显式设置新增的 `Context.instance_id` 为生命周期持久 ID（不是固定 local）。
   人格/身份使用同一实例并接入最终复核；gateway.close 纳入生命周期。
   external 后台检索/幂等导出缺能力时继续明确拒绝，不绕私有存储。
3. **管理入口 / C46**：本阶段未注册任何管理 route，也未实现 page_api。
   按 `host-contract.md` 的已验签严格 Dashboard claims 白名单保护每个 handler，
   拒绝 plugin_page_asset、OAuth/未知 claims、伪造/过期 token 和 admin 参数。
   v1 与 legacy 都要做成品 HTTP 回归；不能仅靠 request.username 或宿主 require_scope。
   接入 `ui.md` 的相对 `console/state|records|config|preview|action`；
   原生配置单一来源、版本检查及审计，未实现动作禁用并给原因。
   Bot pleasure 映射 `(x+1)/2`，night energy 映射 `x/100`，观察保持独立。
4. **T5/T6/T7**：接作息/补课、行为和体验服务；先真实路由/当前人格/身份/新消息
   复核，再预留额度并推进意图；唯一发送端保存 unknown，不自动重发。
   `send_message=True` 只表示找到平台，不等于可靠成功投递回执。

## 尚未验收

- 最终 livingEmotion 在真实 AstrBot 中加载/重载、原生人格、配置页面与 HTTP guard，
  真实 bridge 交互、多插件组合、主对话行为。`host-contract.md` 只是独立探针的有限实测。
- 宿主 v4.29.4 探针记录 46 通过、2 项原生 v1 token 安全断言失败；
  独立 guard 13 项通过，不代表成品管理入口已完成。C46 不能勾选。
- 1 万事件 / 20 并发的 p95 指标尚未测量，本阶段并发正确性测试不是性能验收。
- 最低支持宿主版本未确立，metadata 不宣称兼容范围；Python 3.11 单元测试不代表
  满足 AstrBot v4.29.4 的 Python 3.12 运行要求。
- 没有真实模型调用、真实消息发送、生产数据迁移或生产部署。父代理维护任务状态。
