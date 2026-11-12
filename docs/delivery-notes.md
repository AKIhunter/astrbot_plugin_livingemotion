# 交付与检查

开发者：[AKIhunter](https://github.com/AKIhunter)。当前仓库公开，
安装入口见[安装说明](installation.md)，日常使用见[插件帮助手册](plugin-manual.md)。

## 当前实现

情绪、关系、作息、精力、补课与额度由插件自身实现。已撤下旧库导入、回退、
外部情感插件发现及冲突退让路径；模式仅来自自身配置。
自己的数据结构升级保留，业务配置和已有状态不因清理代码被清空。
“本地化”的边界和升级步骤见[独立运行说明](local-runtime.md)。

## 检查分层

从插件根目录运行：

```bash
.venv-ci/bin/python -m pytest -q
npm --prefix tests/ui run build
npm --prefix tests/ui test
```

普通 pytest 包含可移植规则、存储、运行时和协作回归。
`performance_f6.py` 保持自动收集；大样本 benchmark 和独立宿主 runner 显式运行。
`tests/console/test_console.py`、`tests/budgets/test_model_payload.py` 是宿主专项，
不把没有宿主的跳过当作通过。真实宿主准备方法见[宿主契约](host-contract.md)。

测试采用隔离数据库、合成消息及模型替身。真实计费模型、真实发送和生产峰值
不由这些结果证明。生产检查只核对代码、进程、日志、数据库和已鉴权的管理接口。
本次结果与既有失败对照见[本地化验收](verification-local-runtime.md)。

## 文档与发布包

以当前源码、配置定义和运行态为准；README、手册与流程图同步更新。
`LICENSE` 和 D3 等实际分发依赖的版权声明保留。
发布包排除 `.git`、虚拟环境、缓存、node_modules、数据库和私人运行数据。
原文档验证器应对实际候选运行，不能把开发环境体积当作发布包体积。

旧接口参考和旧组合验收材料已撤下，可在 Git 历史查看。
保留的 [改版报告](verification-retro-final.md)、[四版宿主报告](verification-retro-host.md)、
[预算](verification-budgets-final.md)及[性能](verification-performance-final.md)均是各自时点的证据；
不代表本次代码已在所有宿主和外部服务重测。

## 线上部署

1. 检查远端是否有额外改动，按每个文件比对 SHA-256。
2. 备份插件、原配置与 SQLite 一致快照，记录清单、SHA-256 和逐文件回滚方法。
3. 只更新此次清单中的文件，删除项也须先归档，不覆盖整个目录。
4. 重启 AstrBot，核对服务、监听端口、新 ERROR、数据库及管理 API 读回。
5. 检查失败则逐文件回滚并巡检；不拿旧整库覆盖新记录。

发布到插件市场、GitHub Release、收费模型测试和真实平台投递是单独的操作，
不能用一次普通代码部署代替它们的验收。
