# 兼容性与证据矩阵

## 改版说明

新版范围、状态/睡眠、记忆、页面与管理契约见 [生活控制台](life-console.md)。
本轮全量、四版宿主与浏览器验收已完成，结果对应同一冻结源码；
下文所有0.1固定宿主数字仅作历史记录，不能作为新版通过证据。
支持范围以随候选提交的 `metadata.yaml` 为准，不泛化到未测宿主或生产环境。

## 0.2.0 接口与运行边界

metadata限定 `>=4.29.1,<=4.29.4`，入口版本0.2.0，进程内API仍为v1，
存储schema升级至3。旧配置缺失新字段时保留分场景/v1作息，不擅自合并或阻断回复。
新页面支持九区与十个Console接口，所有接口均执行当前Dashboard管理员复核；
资源令牌、query令牌、cookie-only和未知来源不能授权私人读写。

原生回复在最终输出阶段记为“已提交”，不作为平台送达证明。
生成错误占用唤醒回复轮，不扣回复精力、不启动窗口；流式和live采用明确限制。
全局查看范围不成为发送目标，私人正文与记忆仍按真实来源授权。

LivingMemory使用当前可发现的事件授权能力；本地向量使用原生embedding提供者，
模型、来源或配置改变后重新复核。授权服务不可用时关闭式拒绝，不回退私人材料。
天气不可用显示“未获取”，不让日记模型伪造日期、城市或天气。
原生sandbox不能持久保存主题时仅本次有效，减少动效直接切换。

完整新版结果见 [改版验收](verification-retro-final.md)、
[四版宿主](verification-retro-host.md)；生产投递、收费模型、未测宿主及真实峰值均未验证。
四版各424宿主检查通过，浏览器分别159/163/163/165检查通过，每版36真实视图。
产品源SHA256为 `802dc2f3f075091396e22fce2c1798a5e8cf97c671f6af64ca248121eeea3bb5`。
宿主、加载副本、Dashboard和验收脚本前后不变；完整失败历史保留。

<details>
<summary>0.1固定宿主历史记录（以下“当前”均指旧验收时点）</summary>

## 0.1 历史固定宿主矩阵

读者：安装者、维护者和验收者。2026-11-05 核对现存报告与源码，不是重新执行报告中的测试。
维护者在宿主/Provider/页面/消费者变动及每次交付时更新；证据必须对应源码哈希。
本页是支持边界的权威入口，原始验证报告保留失败，不互相替代或相加计数。

## 当前边界

metadata 限定 `astrbot_version: "==4.29.4"`。唯一实测宿主为
**v4.29.4 / `61335414433db721b3f7ecc93f90deafe0a59d78`**，Python 3.12.16。
这是保守版本闸门，不宣称最低支持版本、广泛4.x或任意同版本改版兼容。
产品冻结后的本地分层验收已完成，不等于全部外部能力、生产部署或T12仓库交付完成。

| 表面 | 最终证据 | 限制 |
| --- | --- | --- |
| 单插件加载与 HTTP | `final-single-3txvcu3v` 222/222，含H01公开关系、三次重载、停止任务0及无写回 | 仅固定宿主/合成会话，不是生产运行 |
| 原生页面 | `final-conflict-fqecldcf` browser 44/44，含28组布局，0 pageerror | 28已计入44；不与宿主断言相加 |
| 双主题 | 原生sandbox提示仅本次有效、刷新随系统；历史非sandbox合成12场景通过 | 原生localStorage不可用；非sandbox持久化不是原生证据 |
| 四插件与冲突组合 | `final-four-az7ogq76` 230/230；conflict 245/245，H01/H02/H03均通过 | 普通文本模型桩1/回复桩1/状态块1；未验真实图像、TTS或平台投递 |
| 原生人格 | 最终pipeline人格一次；生成后切换取消、发送桩0 | 真实跨平台OneID绑定/解绑未执行，不由合成身份测试代替 |
| Provider | `ProviderOpenAIOfficial`、Qwen 纯文本参数，经真实 Provider/SDK + 合成 transport 检验 | 不是生产调用/精确 usage 证据；其他 Provider 未验证并拒绝 |
| 发送 | False→rejected，其余 bool/None 等→unknown；无真实外发 | True 不等于投递成功，不生成成功行为证据 |
| C30 入睡确认 | 三场景各41条原检查通过；F13 HTTP 12/12、iframe4/4明示unsupported；120秒取消回awake/drowsy、不重发 | after-sent失败也执行，bool仅找到平台；typed成功仅组件端口，不是生产投递 |
| 记忆 | 三模式端口有合成测试；外部真实事件门面有限接入 | LM 后台授权检索及幂等导出 unsupported，不修改 LM |
| 组件与迁移 | full1273/1273、migration84/84、V06 4/4；38项矩阵29 PASS/9限制/0 FAIL | 集合重叠；无生产迁移/回退；full全清单新增宿主辅助文件，51产品文件稳定 |
| C50/F8 预算与取消 | 独立 C50 31/31、F8 53/53；Provider 16 项实际执行、0 skip | 用例重叠不相加；非生产调用，取消不证明远端未处理/未计费 |
| C22/F9 正文窗口 | 冻结window-03 11/11，静默scope物理 `[2,2,2]`；最终组件迁移TTL通过 | 与预算报告旧快照11/11区分；默认满窗口见原完整C51 |
| C51 性能 | 原完整C51-03 10000/10000成功，p95=48.801416ms，<=50ms PASS | 余量1.198584ms（2.40%），不是生产容量充足保证 |
| CI | Ubuntu 24.04、Python 3.12/3.13、Node 22 配置 | 未运行远端 Actions；矩阵不是宿主兼容承诺 |

当前权威报告：[最终宿主](verification-host-final.md)、
[最终组件38项矩阵](verification-final.md)、
[C50/F8预算](verification-budgets-final.md)、[最终性能与window](verification-performance-final.md)。
三场景共697条宿主断言PASS，包含1条browser退出状态检查；浏览器44项另列，不叠加宣传。
宿主输入及隔离副本三轮前后hash一致至2026-11-05 23:55:49 UTC，进程已退出。
组件51产品文件跨轮一致；full期间新增未收集的 `tests/host/final_provenance.py`，
不宣称全清单完全不变，细节保留在组件报告。
本轮仅同步这些已完成结果，未重跑测试；文档静态检查与T12余项见[交接](delivery-notes.md)。
无生产部署、真实模型调用或平台发送。
报告中的 verification/budgets/performance 原始 JSON/XML/日志仅本地保留，
不是随仓交付链接；本页为精简结论，复跑入口见交接。
T12仍需对明确候选做隐私/来源审阅；其他所有者报告只读，原始数字和失败不改。

### 历史结果

旧single HTTP160 PASS、原生iframe38 PASS/28布局，以及另一轮宿主160 PASS/1 FAIL，
H01/H02/H03失败与非冻结窄复验57/57均保留在[历史宿主报告](verification-host.md)，不作当前结果。
历史C51 p95=221.628ms、139.081ms、56.895041ms均未达50ms门槛；
短诊断约40ms不是最终PASS，见[历史性能报告](verification-performance.md)及最终性能页历史区。

## 管理登录

当前五个私有 handler 均使用额外 Dashboard Bearer guard。
仅接受已验签、当前管理员一致、claims 白名单 `{username, exp, auth_source}`，
auth_source 仅缺省/password/desktop。允许 desktop claims 不等于桌面登录端到端已测。
未知/OAuth claims、资源 token、query token、cookie-only、API key、`admin=true`
不是当前管理授权方式。宿主签发结构变动需重验，不放宽签名、期限或用途检查。

原生宿主探针 **46 通过/2 失败** 是历史真实结果：v1 扩展接受页面资产 token 读写。
插件guard在最终三场景五handler的legacy/v1检查中通过，但没有改宿主，
也不能把原始宿主漏洞探针失败重写为通过。
见 [host-contract.md](host-contract.md) 和
[原始报告](../tests/host/evidence-v4.29.4.json)。

## 明确降级

- 原生 iframe sandbox 禁 localStorage：仅本次主题有效，刷新跟系统。
- LM 后台授权检索：`external_background_authorization_unsupported`。
- LM 幂等体验导出：`external_idempotent_export_unsupported`，开关不能赋予能力。
- 未验证 Provider：拒绝绑定；输入使用 UTF-8 字节+256 上界，不需要 tiktoken，不是精确 usage。
- unknown 发送：不自动重发、不退款、不生成成功行为、不满足成功回执收尾。
- 原生回复确认不可用：不得用 after-sent 或 bool 补造 receipt；120 秒取消收尾，
  无待回复计划/手动睡眠可用，unsupported已在最终HTTP/iframe实显验证。
- 未确认迁移范围/时区/梦夜周期：拒绝相关用途，不以当前配置或伪造计数补证。

未来升级必须重跑受影响层次；独立宿主 runner 不属于普通可移植 pytest。
具体命令和 F6 自动收集约定见[检查分层](delivery-notes.md#检查分层)。

</details>
