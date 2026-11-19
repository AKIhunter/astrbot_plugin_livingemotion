# 安装与升级

当前0.4.3；支持AstrBot 4.29.1–4.29.4、Python≥3.12，以
[metadata](../metadata.yaml)为准。普通使用不需要Node或独立网页服务器。
安装后按[使用手册](user-guide.md)操作。

## 安装

1. 从[公开仓库](https://github.com/AKIhunter/astrbot_plugin_livingemotion)使用宿主支持的
   插件安装方式，或下载审核过的源码ZIP。普通读取公开仓库不需要token。
2. 手动解压时，找到包含main.py和metadata.yaml的一层，命名为
   `astrbot_plugin_livingemotion`，放入宿主 `data/plugins/`，不要多套一层目录。
3. 保留根入口、schema、requirements、资产和完整pages；不复制虚拟环境、
   node_modules、缓存、数据库或私人配置。
4. 在AstrBot插件管理加载，按宿主提示应用/重载；打开 `livingemotion` 页面。
5. 选择人格、保存，再正常互动。新库“未采集”正常。

运行数据由StarTools定位到 `data/plugin_data/astrbot_plugin_livingemotion/`，
主库livingemotion.sqlite3；数据不应放进源码包。
本地规则独立可用，长期记忆、模型生成与发送需各自的可用依赖和许可。

## 升级与验收

先记录版本、配置和源码哈希，备份源码、原始配置与SQLite一致快照。
逐文件核对源码差异，保留无关线上改动；不整目录覆盖、不用新默认配置替换旧值。
应用后检查实际插件版本、页面、运行配置读回、历史记录、数据库和新增错误。
磁盘改了不代表内存生效；原生配置页保存后按宿主提示应用，插件设置保存则更新运行配置。

0.4.3使用allow_sleep统一控制睡眠与自动作息。显式值优先，
仅缺少allow_sleep的旧配置从旧作息许可迁移一次；旧作息开关不再公开。
关闭立即清醒/100%，重新开启不补扣关闭期间；编辑时间不隐式启用。
旧allow_sleep=true且schedule=false组合现在按总许可运行自动作息。
原有显式耗能、人格、模型、关系与SQLite业务记录继续保留。

旧配置缺少人格共享/规则版本时按兼容识别，不盲用新安装默认；
详细见[配置参考](config-reference.md#兼容字段与迁移)、[技术说明](technical-guide.md#配置与升级)。
回滚只恢复本轮范围文件，不覆盖未知后续配置或新增业务数据。
通用维护见[独立运行](local-runtime.md)，复测分层见[交付说明](delivery-notes.md)，
宿主证据见[兼容矩阵](compatibility.md)。
