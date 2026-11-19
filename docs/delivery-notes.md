# 开发与检查分层

适用0.6.0。完整克隆保留tests与开发依赖；使用Python 3.12/3.13验证便携路径。
先从插件根目录安装requirements-dev.txt，然后运行：

```bash
python scripts/check_docs.py
python -m pytest -q
npm --prefix tests/ui ci --ignore-scripts --no-audit --no-fund
npm --prefix tests/ui run build
npm --prefix tests/ui test
npm --prefix tests/ui run test:browser
node tests/ui/sleep-master-browser.test.mjs
node tests/ui/promise-cancel-browser.test.mjs
```

## 检查分层

默认pytest覆盖规则、存储、运行时、便携预算和F6回归。
tests/host、tests/console/test_console.py、tests/budgets/test_model_payload.py为显式宿主层；
依赖固定AstrBot快照，不能把缺依赖跳过当作通过。
显式双插件映射使用LIVINGHELLO_SOURCE，命令见[提示词调整](image-prompt-retry.md#离线复测)。
LH另有tests/image_result_handoff.py，覆盖真实双方门面与SQLite，
替换上游和发送接口，源码需分别来自当前公开版本。
该入口编译真实宿主工具类，额外安装固定参数校验依赖：

```bash
python -m pip install pydantic==2.14.3 jsonschema==4.26.0
ASTRBOT_NATIVE_SOURCE=../AstrBot/astrbot python -B ../astrbot_plugin_LivingHello/scripts/run_image_handoff_tests.py
```

AstrBot、LH、LE源码放同一父目录，LE目录名为astrbot_plugin_livingemotion。
ASTRBOT_NATIVE_SOURCE仅指向源码快照，不启动宿主或连接平台。

UI测试读取真实Console DTO与实际页面，配置保存由合成桥处理。
浏览器外联全部阻断；自动刷新、草稿保存、列表展开与多分辨率独立核对。
UI_EVIDENCE_DIR可指向仓库外证据目录；PLAYWRIGHT_MODULE可复用已安装依赖。
临时服务在finally关闭。浏览器通过不替代宿主HTTP认证和真实平台投递。

## 文档与提交

README只作当前入口；配置参考从schema、Console和同源帮助生成。
修改帮助后运行`python scripts/check_docs.py --write`，并重新导出真实UI DTO：
`python tests/ui/export-native-dto.py`。不能手改证据里的源码hash。
CI检查全部Markdown链接、元数据、schema默认值、便携测试、双插件矩阵和UI。
历史文档统一见[CHANGELOG](../CHANGELOG.md)，旧原件可由固定Git提交追溯。

测试证据放仓库外，不提交私人路径、数据库、原始消息、密钥或临时模型连接。
正常提交精准选择文件；推送前fetch检查分叉，rebase冲突立即abort。
逐文件部署、计费API和真实发送分别授权与验收，不由GitHub提交自动发生。
