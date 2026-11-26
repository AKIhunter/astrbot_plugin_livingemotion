<div align="center">

# livingEmotion

![livingEmotion wordmark and state lines](.github/img/Banner.png)

[![AstrBot](https://img.shields.io/badge/AstrBot-4.29.1–4.29.4-3a8060)](https://docs.astrbot.app/)
[![Version](https://img.shields.io/badge/version-0.10.0-3a8060)](CHANGELOG.md)

[简体中文](README.md) · **English**

</div>

Give AstrBot personas persistent mood, relationships and daily routines, with expression that follows their current state and delayed promises that execute when due. Local mood rules need no model calls. The console refreshes automatically while preserving drafts; proactive chat, journals, dreams and memory can be enabled independently. State is software-computed character state.

Developer: [AKIhunter](https://github.com/AKIhunter). Feedback QQ group: 991350637.

## 🎯 What It Does

| What you want | What the plugin does |
| --- | --- |
| Follow mood and relationships | Nine-component emotion spectrum, object-level appraisal collection, control-based expression; daily relationship list and live 3D graph |
| Try a different mood | 12 choices; generated preview, with simulation records kept separate |
| Manage sleep and energy | One sleep master switch; off means awake at once and energy always at 100% |
| Speak up naturally | Random proactive chances, topic avoidance and back-off after no reply; yields for 15 minutes around same-conversation scheduled greetings |
| Keep promises | Delayed promises become tasks and execute when due; the full task list updates automatically |
| Handle image tasks | Claims and settles the original promise with LivingHello; bounded repairs on known failures, unknown outcomes wait for verification |
| Keep experiences | Private journals and imagined dreams; optional local vectors or LivingMemory with independent read/write permission |
| Shape expression | Native persona, style summary with main-model auto-fill, character presets, independent prompt switches and dual-theme pages |
| Diagnose problems | One-click sanitized diagnostic ZIP of the last 72 hours at the top of the console; final-state log lines for object emotion analysis |
| Set up step by step | "Onboarding guide" in Settings: a six-step checklist (persona, relationships, sleep schedule, prompt injection, style summary, models) that jumps to each setting |

> **🚀 First time here?** After installing, open `livingemotion → Settings → Quick start`, choose the persona mode and save. Rule-based mood needs no model. Not sure what to configure first? Open "Onboarding guide" at the top of Settings for a six-step checklist.

## Contents

- [🚀 Getting Started](#-getting-started)
- [🧠 Core Features](#-core-features)
- [⚙️ Settings and Pages](#-settings-and-pages)
- [📚 Documentation](#-documentation)
- [❓ FAQ](#-faq)
- [🧩 Compatibility and Security](#-compatibility-and-security)
- [⌨️ Commands](#-commands)
- [📜 Changelog](#-changelog)

## 🚀 Getting Started

1. Install from this repository on AstrBot 4.29.1–4.29.4 with Python 3.12 or later.
2. Open the plugin page `livingemotion → Settings`, select your persona mode and save.
3. Local mood rules work without model calls; enable generation and proactive features only as needed.
4. Configure an IANA timezone before enabling sleep. Disabling sleep keeps the persona awake at 100% energy.
5. Chat normally, then return to the TA page; state refreshes automatically.

## 🧠 Core Features

- **Mood**: four rule-based dimensions produce six base emotions without a model. Settings → Emotions adds the wronged, hurt and shyness object emotions and optional model refinement. TA shows nine emotion components. Control is written by the model and shapes the intensity of negative emotions and the speaking style.
- **Object emotion dimension**: Settings → Quick start → Object emotion dimension chooses conversation (default: each group and private chat stays separate) or person (one QQ shares the feeling across chats). Relationships, journals and memory stay isolated per conversation. Replies wait at most one second; a slower analysis finishes in the background.
- **Relationships**: objects are listed by real source. The daily list updates at local 00:00, while the live 3D graph and editing always read current values.
- **Sleep and energy**: enable sleep under Settings and configure an IANA timezone. Disabling sleep keeps the persona awake at 100% energy.
- **Proactive chat**: fill in the existing real QQ account list under Settings and enable permission. Each random chance is evaluated before sending, and unanswered attempts back off.
- **Promises**: promises for later become tasks and execute when due, without another message from the user.
- **Journals and dreams**: manual generation is always available; automatic journals and dreams are opt-in. Optional local vectors or LivingMemory, with read and write permission granted separately.

## ⚙️ Settings and Pages

Open `livingemotion → Settings`. Follow the session persona or choose a native persona. Leave the shared model empty to follow the real session model; each purpose can override it. Feature switches are flat and independent and are saved together. The console refreshes automatically while preserving drafts; after a 409 conflict, reload and review your draft before saving again. The native AstrBot config page and the plugin page edit the same configuration. The style summary under the native persona can be written by hand or drafted with "Fill with the main model"; the draft only takes effect after "Save summary", and that model call may incur charges.

Defaults: enabled, active mode. Object emotion collection, the emotion model, random proactive chat, automatic journals, dreams and long-term memory are off by default; promises and sleep permission are on. Existing explicit settings are kept. Sleep needs a valid timezone. Group proactive chat needs both global and group permission, and listed numbers must match existing real conversations.

Model generation can incur provider charges. Unknown generation or delivery is not blindly retried. `sent` records acceptance by the sending interface, not user read confirmation. Normal use needs neither Node nor an external CDN.

## 📚 Documentation

The guides are written in Chinese.

| What you need | Entry |
| --- | --- |
| Install, upgrade and host requirements | [Installation](docs/installation.md) |
| Controls, daily operations, simulation and real sending | [User guide](docs/user-guide.md) |
| Every field, default, location, effect and example | [Configuration reference](docs/config-reference.md) |
| Nine emotions, object emotion dimension and auto-refresh | [Emotion spectrum](docs/ta-emotion-spectrum.md) |
| How control shapes mood, chat and history | [Control integration](docs/control-integration.md) |
| Exporting the sanitized diagnostic ZIP | [Diagnostic guide](docs/diagnostics.md) |
| Save conflicts, nothing generated or sent | [Troubleshooting](docs/troubleshooting.md) |
| All topics and developer interfaces | [Documentation index](docs/README.md) |

## ❓ FAQ

**TA page is empty?**
A fresh install has no history yet. Confirm a valid native persona and an existing real conversation; state appears after normal interaction.

**Save returns 409?**
The configuration version changed. Reload, review your draft and save again; failed items are not saved.

**TA stays awake at 100% energy?**
Sleep is disabled. That is the intended behavior; changing the schedule does not enable it.

**Sleep is on but TA never sleeps on time?**
A valid IANA timezone is required. Cycles are created by the scheduler, not by opening the page.

**Proactive chat is not sent?**
Check active mode, global and group permission, the real source lists, time windows, silence, quiet hours, budgets, unanswered back-off and host yielding.

**Simulation produced text but no message?**
Preview only evaluates conditions without calling a model or sending. Test calls the model and writes a simulation log, which may incur model charges, and sends nothing. Only real sending contacts real targets.

**Dream button is unavailable?**
Manual dreams still need dream generation enabled, an available persona and a model. Manual journals do not need the automatic journal switch.

**Object emotions keep showing not collected?**
Enable wronged, hurt and shyness under Settings → Emotions, set Operating mode to Participate in expression and action, and select a conversation on TA. Each analysis writes one `[LE-对象情绪]` log line that shows the reason.

## 🧩 Compatibility and Security

| Platform | Intake and scope |
| --- | --- |
| QQ OneBot (`aiocqhttp`, e.g. NapCat) | Private and group emotion, relationships and reply injection; proactive chat from the QQ account list, with platform message IDs for verification |
| QQ official bot (`qq_official`) | Basic message intake; background delivery uses the host channel and receipts may be unknown |
| Telegram, Discord | Basic emotion, relationships and reply injection; the QQ account list does not apply, and real platform delivery has not been verified |
| WebChat | Currently rejected by the source code |

- Host: AstrBot 4.29.1–4.29.4 with Python 3.12 or later; other versions need separate acceptance.
- Upgrades: SQLite upgrades automatically to v9 without backfilling old history. New defaults only fill missing items, and explicitly saved values win.
- Companion plugins: image receipts and original-promise settlement need LivingHello 2.9.0; the basic prompt mapping contract supports LH 2.8.0. LivingMemory is optional and reports unsupported when a capability is missing.
- Credentials: model keys are configured in the host's model management page; plugin settings store Provider IDs. Never put credentials in public reports.
- Admin pages require the administrator identity; resource tokens or client identity parameters grant no admin rights.
- Diagnostic bundles drop message bodies, redact credentials and alias accounts consistently.

Platform declarations cover basic message intake. QQ OneBot has isolated-host acceptance; real delivery and full capability on other adapters must be verified separately. See [platform compatibility](docs/compatibility.md).

## ⌨️ Commands

| Command | Permission | Effect |
| --- | --- | --- |
| `le_wake` | Host administrator only | Request waking TA; the prefix follows host settings. See [sleep rules](docs/sleep-energy-rules.md) |

## 📜 Changelog

Current version: `v0.10.0` (2026-11-26)

- ✨ Settings adds an "Onboarding guide" at the top: a six-step checklist (persona, relationships, sleep schedule, prompt injection, style summary, model selection) that jumps to each setting and lists all nine model fields.
- ✨ The style summary can be drafted with "Fill with the main model"; the draft takes effect only after "Save summary".
- 🔧 The TA page "Emotion and metric guide" gains a table of how each of the nine emotions rises, eases and fades; the "Availability and source" and "Dependency health" blocks are removed.
- 🐛 Fixed the style summary box being disabled after auto-refresh, which made drafts impossible to save.
- 🧩 No configuration or database migration.

Full history: [CHANGELOG.md](CHANGELOG.md) (Chinese).
