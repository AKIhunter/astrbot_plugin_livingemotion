# 真实宿主有限验证

- `capture_baseline.py`：只读取四个指定旧仓库，记录 HEAD、dirty 计数/摘要、白名单源码哈希；输出文件必须不存在，不覆盖基线。
- `run_isolated_host.py`：全新临时数据根、净化环境、回环 HTTP、真实 AstrBot 核心、合成输入；有界运行后自动停止。
- `fixture_plugin/`：独立编写的宿主接口探针，不是 livingEmotion 成品，也不包含上游复制代码。
- `fixture_plugin/guard.py`：固定版本、Bearer-only、实际验签的最小管理 guard，已核实合法 Dashboard 通过及 asset/OAuth 类令牌拒绝。
- `evidence-v4.29.4.json`：脱敏最终结果及源码/依赖身份，不含密码、token、聊天、数据库或生产日志。

接点、已执行/未执行边界、运行命令和安全阻断项见 `../../docs/host-contract.md`。
当前 v4.29.4 的运行退出码为 2，因为页面范围令牌被 v1 读写接口接受；不要调整断言来掩盖失败。
此脚本不是通用版本适配层：换宿主版本时应核对接口，再重跑并保留新的证据。
