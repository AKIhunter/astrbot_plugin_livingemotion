# 更新日志

## 0.1.0（冻结候选，未发布）

### 新增

- 独立事件契约、Bot 感受/对方观察分型、来源关系账本、SQLite 原子提交与预算。
- 原生人格/身份适配器及 none、local_lite、external 记忆端口。
- 长夜与精力、有限醒后补课、单一主动执行服务、私人日记与梦境模块。
- 七区白昼/黑夜管理前端、管理路由保护模块及合成测试。
- Application、原生配置/消息钩子、`le_wake` 和五个管理端点。
- 离线迁移 CLI：`preview/import/verify/rollback-plan`，原期限与旧约束保守接管。
- 本地安装、架构、API、兼容性、来源许可文档；Linux Python 3.12/3.13 与 Node 22 CI 配置。

### 边界

- 模型细化、主动/群主动、日记、梦境和外部导出默认关闭。
- 独立安装默认 enabled/active，不改现有部署或消费者配置；上述用途须分别启用。
- AstrBot 原生 after-sent/send_message 布尔值不等于投递成功；unknown 不自动重发。
  无可靠确认时 settling 最多 120 秒后取消回清醒/困倦，页面明确显示 unsupported。
- 外部后台授权及幂等体验导出缺能力时明确降级，不穿透私有存储。
- 原生 ProviderOpenAIOfficial/Qwen 纯文本请求使用 UTF-8 字节+256 预算上界，
  不依赖 tiktoken，不宣称精确 usage；其他 Provider 未验证并拒绝。
- 原生 sandbox 下主题仅本次有效、刷新回系统；非 sandbox 持久化有合成浏览器证据。
- MIT 仅适用于自有新写内容；从绫仅作非官方行为参考，未发现明确上游许可。

### 最终本地验证

- 固定 v4.29.4 最终 single222/four230/conflict245，共697条宿主断言 PASS；
  原生浏览器44 PASS（含28组布局）、0 pageerror，H01/H02/H03/C30均覆盖。
- 普通full 1273/1273、完整migration 84/84、V06 4/4 PASS；
  38项组件矩阵为29 PASS、9项限制、0 FAIL。集合重叠不相加。
- C50 31/31、F8 53/53 PASS，真实Provider/SDK经合成transport的16项实际执行、0 skip。
- 原完整C51 10000/10000成功、p95=48.801416ms，window11/11 PASS；
  <=50ms门槛余量2.40%，不代表生产余量充足。
- 历史C51 221.628ms、139.081ms、56.895041ms均为当时FAIL，保留原报告，不作当前结论。
- metadata 保守限定 ==4.29.4，不宣称最低版本或广泛兼容；未实测真实外部检索/导出和生产投递。
- CI 普通层排除显式宿主专项而非跳过测试；F6 的 performance_f6.py 纳入自动发现，
  performance_probe.py 和大样本 benchmark 仍是显式诊断/验收。
- 目标仓库为 PRIVATE，通过正常认证访问；实际提交与 CI 结果以仓库记录为准。
  本地验收不代表远端 Actions 通过，不包含商店发布或生产部署。
  本地执行的准确结果见 [delivery-notes.md](docs/delivery-notes.md)。
- 仓库交付证据由交付者独立记录，本次不打tag或发release；
  BiliBot/LivingHello本地消费者改动不纳入新仓库提交。
