# 源码基线快照

采集时间（UTC）：`2026-11-05T15:40:19.600350+00:00`。

本文件由 `tests/host/capture_baseline.py` 生成，只记录源码身份。
不包含上游函数体、提示词、素材、聊天、数据库、密钥或运行配置。
HEAD 不是 dirty 工作区的完整身份；以各选用文件 SHA-256 为准。
dirty 全量状态只保存数量及原始 NUL 清单的摘要，不泄露未选用文件名。
这是采集时点的基线，其他代理后续配套修改不属于此快照。
status_stable 只说明采集前后路径状态相同，不保证跨仓库原子快照。
从绫许可未确认，仅作接口/行为参考，不据此授权复制或重新许可。

## 插件/astrbot_plugin_congling

- HEAD：`5015e1804a30cb1784efa41feefcd91508c163f3`
- dirty：`True`；status_stable：`True`
- dirty 状态计数：`{" M": 34, "??": 33}`
- dirty 清单 SHA-256：`af94a8c08ed59d3be53d87bf386e7cf6e19698860110c79ba29a46a1b3eec031`

| 选用文件 | 状态 | SHA-256 |
| --- | --- | --- |
| `metadata.yaml` | `clean` | `79dbdd355b377cb6359d36d19594a6f3f17471c283f67b7df7ad477fb7b280a3` |
| `main.py` | `M ` | `c2356b7d5964e7363cf2da12d9d5d87441455eb8d3527e3d8f43b6a249537466` |
| `core/paths.py` | `clean` | `890e0dafdc1b59a34c0d618656e21010aeaa717f33e6a9ee74e77f9c7571a332` |
| `core/store.py` | `clean` | `6f2427b78b153bba47ae13065e85286ded39e76740ec6b9c2eeabebec63de362` |
| `humanize/persona.py` | `M ` | `826ba741d7200c70d601b2125bd2a0c065c21bb45035d9797fc775c919f24c69` |
| `humanize/proactive.py` | `M ` | `f969ad38790c373bb71959039c86ca0651c4f35595d61b10bfc2f04c922b1864` |
| `memory/emotion.py` | `M ` | `d8fdbfd965e1732916c3a725cc84010611dcd4ef21ef90edcbd0f7b4cea93ae5` |
| `memory/affinity.py` | `clean` | `f2dfe5b9b4fab80c33f6950da2af012702d15a0bc190f0a92c75781e6b177e56` |
| `memory/diary.py` | `clean` | `36bfc01d11e6589c8ca4a0a2e7bfd11bb98c12286b7575530067e120ed7e4f07` |
| `night/state.py` | `clean` | `7e6d4d6e58fe6fa39bd5ce8bc29fe7053a77d44ee66708dd5fa97e474230e275` |
| `night/energy.py` | `clean` | `5ada450b1df1e86d4a360aaa23924764da2f7df57de6c8141db6521f15e88260` |
| `night/stages.py` | `clean` | `ca927ea3f3f245435ce8e0293b9185b87c8c097ba9f5c915a968853eb7dc9aec` |
| `night/wake_flow.py` | `M ` | `859345b3414d3f633d60f70bd110953e613c617a029b1def81b2de514a8553d3` |
| `night/dream.py` | `clean` | `d3b331f32c6b130e62e4e29c9586ebe84634367f3dea735c132b85ff165a3e43` |
| `page_api/__init__.py` | `M ` | `25b2bb9ceb7245e2f57ddc68bc6a767863cd93e9232a1c8507fc902ec48af727` |
| `pages/fromling/index.html` | `M ` | `b47b18b5f53d6bde5682bedb026af84b600a4787cba3830986f0a43bdfa2910f` |

## 插件/BiliBot

- HEAD：`a0acfa9bd6b306a720bf6ccf133fd630ffd958f4`
- dirty：`False`；status_stable：`True`
- dirty 状态计数：`{}`
- dirty 清单 SHA-256：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

| 选用文件 | 状态 | SHA-256 |
| --- | --- | --- |
| `metadata.yaml` | `clean` | `af65b70403f884b6d1c4f27adf6f5180b13cfd2dbdaf8e9ba69509d42942d786` |
| `main.py` | `clean` | `166587acd3549354ffb5cd4fb11fea0fc7be8f84ae6a8aa7528b6ac06af2050f` |
| `core/emotion_bridge.py` | `clean` | `cb64e307d1221d98096d202eaf05dda4d4c551ff58206dfec8e94ce8a4b9da1c` |

## 插件/astrbot_plugin_at_guard

- HEAD：`e74d174ed6ccf6e8521a07151e25e80ec1e56d95`
- dirty：`False`；status_stable：`True`
- dirty 状态计数：`{}`
- dirty 清单 SHA-256：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

| 选用文件 | 状态 | SHA-256 |
| --- | --- | --- |
| `metadata.yaml` | `clean` | `cf86377330a160aded1de7a77ed130216c9462938c3064ac03ec615e24d0c75d` |
| `main.py` | `clean` | `21ac8b610544eecffcbb6a32ae31af535343d7e37e0cbae5beeda291439cc1f2` |
| `guard_expression.py` | `clean` | `8a8ed83107415ff0a7082e4e953f399ac26fbf9426310d92bb58bb2be5ee32b5` |
| `guard_webui.py` | `clean` | `125f83b5a0e6f8c2e8f9eb21d978f304768830f7523e0fffd77c346061c658dd` |
| `guard_native_settings.py` | `clean` | `6a6cbe2febd349d0729453761c9aafdbd558f0c5514d77a967d770cdea747767` |
| `tests/test_congling_expression_handoff.py` | `clean` | `f98a150aeef6385c10ce39db9b615ba695b9c0ae03d73c58c24452f8f96f4c9d` |

## 插件/LivingMemory

- HEAD：`b118190d34b6e52e2f2ab6bf460e02cb77822be4`
- dirty：`True`；status_stable：`True`
- dirty 状态计数：`{" M": 52, "??": 31}`
- dirty 清单 SHA-256：`dec3ae5b7e67f291ef0c8dd6a00635ae9319a250553a243c6a822e0cc2d99f99`

| 选用文件 | 状态 | SHA-256 |
| --- | --- | --- |
| `metadata.yaml` | `clean` | `647a772f6f20367dcc443e1b7b5260518f415486546ef4689939b6460d662f36` |
| `main.py` | `M ` | `867ba53234e44925d5cb01e2b1e3faafbc8b92bc5643c116a64d857856301152` |
| `core/astrbot_compat.py` | `clean` | `315880a591b1cbb9d05a5d3d83111ce77843e78df92d00a239c93cd023bf38a4` |
| `core/identity.py` | `M ` | `2256832959a5d272c80a75fd29f799151af38c1f6118fd3a9452777ea34841e1` |
| `docs/oneid-core.md` | `??` | `649c0b79441152160fc07fde0b61baeffd30eab501681198828fbaace3fdada2` |
