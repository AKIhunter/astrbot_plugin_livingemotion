# livingEmotion

![livingEmotion wordmark and state lines](.github/img/Banner.png)

[![Version](https://img.shields.io/badge/version-0.9.0-3a8060)](CHANGELOG.md)

[简体中文](README.md) · **English**

Give AstrBot personas persistent mood, relationships and daily routines, with expression that follows
their current state and delayed promises that execute when due. Local mood rules need no model calls.
The console refreshes automatically while preserving drafts; proactive chat, journals, dreams and memory
can be enabled independently.

Install on AstrBot 4.29.1–4.29.4 with Python 3.12 or later. Open `livingemotion → Settings`,
select your persona mode and save. Local mood rules work without model calls.
Configure an IANA timezone before enabling sleep. Disabling sleep keeps the persona awake at 100% energy.

Supported message adapters: QQ OneBot (`aiocqhttp`), QQ official (`qq_official`), Telegram and Discord.
QQ OneBot provides native message-ID receipts; other adapters use host delivery without equivalent confirmation.
The proactive account/group-number lists apply to QQ. Telegram and Discord delivery has not been tested
on real platforms. WebChat is currently rejected. See [platform compatibility](docs/compatibility.md).

TA displays nine emotion components. Optional wronged, hurt and shyness collection is off by default;
enable it in Settings → Emotions and select a person on TA. Collection requires Active mode.
Settings → Quick start → Object emotion dimension chooses conversation (default: each group and private chat stays separate) or person (one QQ shares the feeling across chats).
Enable model refinement for contextual interpretation. A joint analysis is reused; during its
cooldown a separate object analysis can use the shared daily budget. Replies wait at most one second; a slower analysis finishes in the background and applies to the next reply.
Control influences negative emotion intensity and speaking style. TA selection and relationship
filters are independent; the relationship list updates at local midnight while the graph stays live.
Behavior simulation offers 12 choices, keeps its records separate and does not send messages.
State refresh continues while editing and preserves drafts and optimistic versions.

Delayed promises execute when due. Image tasks can bind and settle the original promise through LivingHello 2.9.0.
Known image failures may receive bounded wording repairs; unknown generation or delivery waits for verification.
Successful wording substitutions are scoped by the actual image provider, model and protocol.
`sent` records acceptance by the sending interface, not user read confirmation.

| Documentation | Contents |
| --- | --- |
| [User guide](docs/user-guide.md) | Controls, daily operations and simulation boundaries |
| [Configuration reference](docs/config-reference.md) | Every field, default, location, effect and example |
| [Technical guide](docs/technical-guide.md) | Decision flows, persistence, integration and upgrades |
| [Control integration](docs/control-integration.md) | Mood projection, speaking style and history migration |
| [Image prompt contract](docs/image-prompt-retry.md) | Bounded repairs and mapping reuse |
| [Scheduled greeting coordination](docs/native-proactive-yield.md) | Same-conversation 15-minute windows |
| [Model input precision](docs/prompt-precision.md) | Three decimal places and literal Chinese in reply state blocks |
| [Troubleshooting](docs/troubleshooting.md) | Configuration conflicts, generation and delivery |
| [Documentation index](docs/README.md) | Current reference and development documents |
| [Changelog](CHANGELOG.md) | Historical changes |

Model generation can incur provider charges. Normal use needs neither Node nor an external CDN.
Developer: [AKIhunter](https://github.com/AKIhunter). Feedback QQ group: 991350637.

0.9.0 adds Object emotion dimension (Settings → Quick start): conversation keeps each group and private chat separate, while person lets one QQ share wronged, hurt and shyness across chats. The TA conversation picker merges one QQ into a single entry. Replies wait one second; a slower analysis is written back in the background instead of discarded. No configuration or database migration; the default stays conversation.

0.8.0 adds a diagnostic ZIP download at the top of the console for the last 72 hours, covering events, emotion, proactive behavior and promise status. Independent records are capped at 32 MiB with 1 MiB files and automatic expiry cleanup every minute. No configuration or database migration is required, and export makes no model calls. LivingHello 2.10.0 provides its own export; each plugin works independently. See the [diagnostic guide](docs/diagnostics.md).
SQLite upgrades automatically to v9 without filling missing historical control values.
No new configuration keys; three-decimal model inputs and scheduled greeting coordination remain.
