# 安装与升级

适用0.11.2，Python与依赖由宿主管理。metadata声明支持AstrBot 4.29.1–4.29.4；
范围外版本须独立验收，见[兼容边界](compatibility.md)。

1. 在AstrBot插件市场搜索LivingEmotion，或导入[仓库](https://github.com/AKIhunter/astrbot_plugin_livingemotion)。
2. 确认加载成功，在插件详情打开livingemotion页面。
3. 在“设置”选择人格、模型、时区及需要的独立开关；保存后核对实际值。
4. 主动发送需active模式、授权目标、可用模型和最终守卫；先阅读[使用手册](user-guide.md)。
5. 双插件生图原事项、回执与学习使用LH 2.9.0；单独安装仍可用自身功能。

升级前备份源码、配置和一致SQLite快照；按文件核对差异，保留额外现场改动。
不清空旧数据或覆盖整个目录。新增默认值只补缺省项；显式保存值优先。
allow_sleep成为唯一睡眠许可，旧night_schedule_enabled退役；
关闭总开关转清醒100%，重开不补扣关闭时间。其他迁移见[独立运行](local-runtime.md)。
0.7.0没有新增配置键，原开关值保留。SQLite自动升至v9，为历史样本增加可空
control/control_at，旧历史不回填；日关系列表复用runtime_meta，不新增表。
关闭模型细化仍走本地对象规则；开启后语义分析可能在四维冷却期间占用每日总额度。
完整变化和回落规则见[掌控感](control-integration.md)与[情绪谱](ta-emotion-spectrum.md)。

模型、索引、场景许可和插件能力分别检查。页面可打开不代表管理认证或外部模型可用。
日志只看受控原因、ID与状态；不要把凭据放进公开报告。
开发命令见[检查分层](delivery-notes.md)，全部字段见[配置参考](config-reference.md)。
