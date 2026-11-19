# livingEmotion 🎯

![Original LivingEmotion banner](.github/img/Banner.png)

[![AstrBot](https://img.shields.io/badge/AstrBot-4.29.1–4.29.4-3a8060)](https://docs.astrbot.app/)
[![Version](https://img.shields.io/badge/version-0.4.3-3a8060)](CHANGELOG.md)

[简体中文](README.md) · **English**

LivingEmotion adds persistent mood, relationships, schedules and energy to your existing
AstrBot persona, with an automatically refreshed console. Proactive chat, diaries,
imaginary dreams, memory and deferred promises have separate permissions.
The displayed state is computed software behavior, not evidence of human feelings.
Maintainer: [AKIhunter](https://github.com/AKIhunter).

## Quick start

1. Follow the [installation guide](docs/installation.md). Supported: AstrBot 4.29.1–4.29.4, Python≥3.12.
2. Open the `livingemotion` plugin page → Settings → Quick start, select the persona mode and save.
3. Keep normal emotion intensity. Local rules need no model; optional generation can remain disabled.
4. For sleep, set an IANA timezone and schedule, then enable `allow_sleep`.
   Disabling it makes the character awake with energy fixed at 100%.
5. Interact in a real conversation and check the automatically refreshed state. An empty new store is normal.

## Documentation

The detailed guides are in Chinese and separated by purpose.

| Purpose | Guide |
| --- | --- |
| All 32 feature switches and everyday operations | [User guide](docs/user-guide.md) |
| All 101 other parameters, defaults and units | [Configuration reference](docs/config-reference.md) |
| Architecture, persistence, contracts and migration | [Technical guide](docs/technical-guide.md) |
| Deterministic examples and behavior boundaries | [Principles and examples](docs/principles-examples.md) |
| Saving, generation, sleep and delivery failures | [Troubleshooting](docs/troubleshooting.md) |
| Topics and historical evidence | [Documentation index](docs/README.md) |

## Defaults and limits

Enabled/active by default. Emotion models, random proactive chat, automatic diaries,
dreams and long-term memory reads/writes are disabled by default; promises and sleep are enabled.
Upgrades preserve explicit saved values. Sleep schedules need a valid timezone.
Group proactive chat also needs its extra permission; an empty group list covers known real QQ groups.
Private text remains isolated by its actual source.

Model generation may incur provider fees. Unknown generation or delivery is not blindly retried.
`sent` means the host accepted the delivery, not that the platform confirmed receipt.
Basic operation needs no other plugin, Node or external CDN.
Shared prompt editing uses the LivingHello 2.7.11 contract.
Trusted integrations use [API v1](docs/api.md). `le_wake` is an administrator command.

## 0.4.3

One sleep permission now controls schedules and manual sleep. When disabled, all stored
night states become awake/100%; time and replies do not drain energy, and re-enabling does not
charge the disabled interval. Editing schedule parameters no longer grants sleep permission.
Explicit `allow_sleep` wins; legacy schedule permission is migrated only when it is missing.
An old `allow_sleep=true / night_schedule_enabled=false` combination now allows automatic schedules.

The common preset explanation sits below personality editing, with a compact header,
inline controls and a version label. Documentation is split into five guides.
See the [changelog](CHANGELOG.md).

Portable offline regression: 2229 Python tests, 16 UI unit tests and four synthetic browser layouts passed.
These results do not certify live model quality, billing or final platform delivery.
