# 来源与第三方说明

记录日期：2026-11-05。本项目显示名 livingEmotion，作者标识 AKIhunter。
本轮仅本地准备文档与 CI，没有公开发布或授权上架。

## 自有内容

新插件按行为需求独立重实现，源码、提示词、页面和测试夹具均新写。
不从从绫复制函数体、提示词、页面、logo、图片、数据库或私人记录。
[MIT 许可](LICENSE)仅授予权属明确的本项目原创内容，不代表本仓依赖或行为参考也采用 MIT。
新增第三方内容前须核对适用版本、许可、署名和分发义务，并更新本文件。

## 行为参考

- 项目：[LUOSHUI319/astrbot_plugin_congling](https://github.com/LUOSHUI319/astrbot_plugin_congling)。
- 已记录参考 HEAD：`5015e1804a30cb1784efa41feefcd91508c163f3`；参考工作区有未提交改动，
  HEAD 不能替代完整来源身份。选用文件哈希及采集时间见 [source-baseline.md](docs/source-baseline.md)。
- 基线核查记录 GitHub license 为 null，远端/本地根目录未发现 LICENSE。
  结论仅为**未发现明确许可**，不推断作者没有其他授权，也不据此获得复制或再许可权。
- livingEmotion 是行为参考意义上的**非官方独立实现/衍生项目**，
  不表示共享上游源码，不声称获得上游背书、维护关系、商标或分发授权。
- 核心差异：对方观察不再等于 Bot 心情；关系与作息不依赖原记忆表；
  记忆可替换，主动发送单一归属，私人体验保留类型、来源和授权边界。

## 宿主、可选插件与工具

| 名称 | 用途 | 本仓分发边界 |
| --- | --- | --- |
| AstrBot | 原生生命周期、人格、Provider、页面 bridge、消息路由 | 外部宿主，不随新插件复制；宿主和其 bridge 按自身许可使用 |
| LivingMemory | 可选公开身份/事件记忆接口 | 不复制引擎、SQL、提示词或数据，不授予其代码 MIT |
| BiliBot / LivingHello | 独立仓库的消费者协作 | 配套改动由各自所有者审核；不将其他仓库源码或 dirty 内容纳入新仓 |
| Python、SQLite | 运行时及本地事务存储 | 使用安装环境提供的组件，按各自许可 |
| pytest、pytest-asyncio、pytest-timeout | 开发测试 | 从包源安装，不提交虚拟环境；各包许可证保留于安装分发包 |
| PyJWT、PyYAML | 管理鉴权测试依赖、文档/配置验证 | 开发依赖不覆盖其许可证；生产鉴权使用宿主环境的 PyJWT |
| Playwright / playwright-core 1.64.1 | 合成浏览器测试 | npm 元数据为 Apache-2.0；不提交 node_modules 或浏览器二进制 |
| Chromium / 本机 Chrome | 浏览器执行环境 | 独立安装，遵循自身及所含组件条款，不纳入本插件 MIT |
| GitHub Actions | 未来仓库的检查配置 | 使用外部 action；本轮未触发工作流或授予发布权限 |

这不是宿主和所有传递依赖的完整法律清单或 SBOM。锁文件只记录实际测试包身份，
不是对第三方再许可。若以后分发依赖、浏览器、SDK 或其他素材，须先补齐相应许可证和 notices。

## 素材与测试数据

### 前端关系布局依赖（2026-11-06）

`pages/livingemotion/vendor/d3-force.mjs` 是通过固定 `esbuild@0.25.10`
构建的自托管 ESM，只在关系页载入。锁文件位于 `tests/ui/package-lock.json`。
运行期不依赖 npm、CDN 或远程脚本。包及传递依赖采用 ISC：
`d3-force@3.0.0`、`d3-dispatch@3.0.2`、`d3-quadtree@3.0.2`、`d3-timer@3.0.2`。
esbuild 为 MIT 开发构建工具，不打包进页面。

以下版权及许可适用于上述分发的 D3 代码，不由本项目 MIT 替代：

```text
Copyright 2010-2021 Mike Bostock (d3-force)
Copyright 2010-2026 Mike Bostock (d3-dispatch, d3-quadtree, d3-timer)

Permission to use, copy, modify, and/or distribute this software for any purpose
with or without fee is hereby granted, provided that the above copyright notice
and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF
THIS SOFTWARE.
```

本轮不制作 logo/Banner，不借用官方或上游标志。页面为自有 livingEmotion 字标；
视觉方向参考不构成对他人商标/素材的使用授权。
测试账号、聊天文本、日记、梦、令牌反例和数据库均为合成/隔离生成，不来自生产。
`tests/ui/evidence/` 只保留已审阅的合成证据；宿主报告保留源码哈希和脱敏检查结果，
不携带 token、密码、数据库、真实聊天或生产日志。
