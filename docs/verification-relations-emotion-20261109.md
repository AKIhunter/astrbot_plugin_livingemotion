# LivingEmotion 关系、发送、滑块与情绪验证

日期：2026-11-09。范围：当前独立插件工作树；保留已有周末修改。

最初完成本地修改与隔离验证；随后用户明确授权部署并复验日记生成与情绪显示。
现已完成生产部署、单插件重载与一次真实当日日记生成；未提交或推送，
未真实发送消息、未回放历史情绪。原有隔离证据与新增生产证据分开记录。

## 后端

执行：

```bash
.venv/bin/python -m pytest tests/console tests/behavior \
  tests/domain/test_emotion.py tests/integration/test_application.py \
  tests/experience/test_manual_daily.py tests/memory/test_p4_models.py -q --tb=short
```

结果：241 passed。环境有一个已有 pytest 警告：
`Unknown config option: timeout`，未将它解释为测试失败。

覆盖关系精确匹配、平台隔离、一跳邻居与截断、备注 CAS/审计、编辑开关、
授权记忆迟到后重查；原生发送编号、布尔/空回执、错误 envelope、非法来源、
超时/取消与最多一次提交；情绪异步细化、真实事件 GC、有效零调整、
新状态交错、清空/取消、受控失败诊断与无费用模型预检查。

宿主接口依据为 AstrBot v4.29.4，
固定源码提交 `61335414433db721b3f7ecc93f90deafe0a59d78`。
其中 ProviderManager 的原生查询是异步方法；同步 accessor 支持仅是兼容，
本轮证据没有证明它是生产故障原因。

## 前端

在 `tests/ui`：

```bash
npm test
UI_EVIDENCE_DIR=/tmp/livingemotion-daily-20261109/relations-ui npm run test:browser
node daily-browser.test.mjs
```

纯模型检查：12 项通过，包含 20/80/200 人的固定种子、三轴受力、
空间边界/间距与有正负深度的透视检查。

日记专项：7 组通过；1280/390px、深浅主题连续切换 20 次，
阅读区 x/y/宽/高相对初始变化小于 1px；滑块与选中菜单对齐，
正文展开、滚动位置和设置草稿保留；放弃草稿会恢复控件。
生成完成前后阅读区位置变化也小于 1px，刷新后仍能生成，重载只核对既有请求。
取消/未知/未找到请求均不自动发起第二次生成。浏览器异常与外联均为 0。

整页浏览器：30/30 通过，退出码 0；浏览器异常/外联均为 0，
UI 源文件和原生 DTO 来源哈希检查均通过。200 节点交互准备为 115ms，
该值仅代表本次隔离环境。原生 DTO 已从当前 Console 与临时合成数据库重新导出。
最终结果与截图保存在：
`/tmp/livingemotion-daily-20261109/relations-ui/browser-results.json`。
日记机器结果：
`/tmp/livingemotion-daily-20261109/daily-ui-report.json`。
没有独立预览 URL 时，预览用例实际打开本地合成入口，不记空执行为通过。

截图：[手机三维关系图](file:///tmp/livingemotion-daily-20261109/relations-ui/390-dark-relationships.png)、
[桌面日记滑块](file:///tmp/livingemotion-daily-20261109/daily-1280-light.png)。

较早整页脚本有旧筛选栏、确认弹窗、设置展开方式等过期断言。
已按当前操作契约同步；也修复了常驻面板的重复 ID、置顶禁用状态和
只改备注时图中节点资料未刷新的问题。
生成完成专项另外复现了状态提示出现导致 96px 位移；
已修复隐藏规则的优先级，并由后续专项通过检查验证。旧失败轮次不称为通过。

## 验证边界

测试使用临时存储、合成原生类型/Provider/传输替身和 localhost bridge。
模拟模型返回值不能证明线上 Provider 可用，合成协议回执不能证明真实 QQ 已送达。
新增生产验收已验证实际源版本、原运行模式与真实日记模型可用性；
真实 QQ 发送凭据及自然新聊天后的模型情绪细化仍未验证。

仓库全量 `git diff --check` 存在先前工作树的 CRLF/尾空白报告，
主要涉及 `_conf_schema.json`，另有旧模型文案尾空白；本轮未为此重写用户已有文件。

## 已授权的生产部署与复验

2026-11-09，部署 21 个变更文件，86 个生产源哈希与冻结包完全一致。
包 SHA256：`7a9bc9d672138e2439b22d237519239c96697ea2d314381291bdfe6a4c47dc05`。
完整源码、原生配置与 SQLite 一致性快照均已备份校验，schema 5 保持，
单插件重载成功，active 模式、服务进程与各配置保持。

真实原生控制台 sandbox iframe 验证 14 项通过、页面异常 0。
日记仅提交 1 次 POST，queued → running → succeeded，耗时 17.56 秒；
当日 2026-11-09（Asia/Shanghai）原有 1 条、完成后仍为 1 条，修订版本 2，
置顶值保持，正文可展开阅读，单次模型 dispatch 已由数据库核对。
菜单切换和生成完成时阅读区位移均为 0px；生成前后刷新按钮可用。
正文和私有素材未写入报告。

情绪显示“平静”与真实 API `calm` 一致，新诊断区域显示 `uncollected`，
解释等待新互动。没有制造新聊天或回放历史，因此未证明线上模型细化完成；
不将显示正常解释为生产模型分析已恢复。梦境本轮未再次生成，真实 QQ 发送未执行。

日记完成后再次核对生产源哈希、资源、状态、服务、配置与 SQLite，全部通过。
详细报告：
[线上部署与复验](file:///Users/bytedance/Desktop/bot_manager/LivingEmotion-线上部署与日记情绪复验-20261109.md)。
生产备份位于 `/var/lib/astrbot/backups/livingemotion-relations-20261109-7a9bc9d6/`；
原始无正文证据位于 `/tmp/livingemotion-daily-20261109/production-current/`。
