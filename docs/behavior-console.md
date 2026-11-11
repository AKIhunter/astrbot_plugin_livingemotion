# 主动行为测试与发送日志

页面只保留测试发送、真实发送和发送日志。

测试发送先选择当前情绪、平静或六种情绪，再按人格、情绪和合法本地素材调用一次主动聊天模型。没有实时会话、没有素材、仅观察、自动行为未开启，都可以测试。没有素材时只分享此刻心情或轻问近况，不编造往事。情绪只影响本次提示，不写回真实情绪。生成结果不调用发送器、不创建发送 intent、不增加真实发送额度或未回应次数。

测试提示中的 `current_emotions` 复用 `weather_emotions()`：基础情绪先随时间衰减，再叠加住所当天的天气加成，使用与页面相同的 0–1 上限和四位小数。选择“当前情绪”时，语气提示也使用这组数值；手动选择情绪时仍按所选情绪生成。未配置住所或天气不可用、日期不匹配时不加成，重复测试不会累加天气影响或写回真实状态。

模拟结果按请求 ID 写入 SQLite 的 runtime_meta，使用 `console.behavior.simulation.v1:` 前缀。同一 ID、人格和情绪再次请求只读回结果，不重复调用模型。不同参数复用 ID 返回冲突。并发只接受一条生成；超时或失败不会自动重试。

`runtime/behavior_simulation.py` 负责生成；`storage/behavior_logs.py` 负责模拟记录与统一分页查询；`page_api/validation.py`、`routes.py` 负责参数校验和宿主管理员鉴权。

真实发送保留原有执行与身份校验。`services/behavior.py` 在进入 sending 阶段时，把将要发送的正文通过 `SQLiteStore.transition_intent(content=...)` 与状态一起持久化，便于失败、中断后按唯一 ID 回查。通用 `query_records()` 仍去除正文，正文只进入鉴权控制台的专用发送日志。

日志只显示发送 ID、目标号码、正文和回应 bool。私聊显示 QQ 号，群聊显示 QQ 群号；模拟行显示“模拟”及所选情绪。真实行的回应表示发送尝试之后，同一会话、同一 generation 又收到有效 human 事件，并不推测其语义是否在回答这句话。

旧记录只用同会话、同 generation 的确切消息回执关联 `bot_action_succeeded` 和 `body_window` 找正文；找不到显示“内容未留存”。清理过的旧正文无法恢复。

默认页面每分钟刷新保持原有计时。发送日志另每 5 秒自动更新；输入查询后 250 ms 自动请求，查询条件、输入焦点和测试情绪选择保留。后台页不读取。模拟完成后立即显示新日志。每页 10 条，发送 ID、号码和正文均可查询。

验证入口：

- `.venv/bin/python -m pytest tests/behavior/test_console_simulation.py tests/behavior/test_simulation_validation.py -q`
- `node tests/ui/behavior-console-browser.test.mjs`

测试使用合成宿主和模型，覆盖无素材、情绪提示、真实情绪不被覆盖、请求回放、失败不重试、历史正文匹配、回应 bool、隔离与分页、桌面/窄屏、自动更新和零真实发送。
