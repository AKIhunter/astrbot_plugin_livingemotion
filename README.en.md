# livingEmotion 🎯

![livingEmotion banner](.github/img/Banner.png)

[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A54.29.1-3a8060)](https://docs.astrbot.app/)
[![Version](https://img.shields.io/badge/version-0.3.0-3a8060)](CHANGELOG.md)

[简体中文](README.md) · **English**

**🧠 Mood · 🌙 Sleep · 🤝 Relationships · 📓 Diary & Dreams · 💭 Promises · 🎛️ Console**

LivingEmotion gives your AstrBot character a mood that keeps drifting, relationships
that accumulate, a sleep schedule, and a console to watch it all. Everything runs
inside the plugin; it reuses the persona you already configured in AstrBot.

> First run: keep the model-driven features off and start with rule-based mood.
> See [installation](docs/installation.md) for the full setup.

## ✨ What it does

| You want | What LivingEmotion does |
| --- | --- |
| 🧬 Keep your persona | Follows the native persona of the session; no built-in character |
| 🧠 Mood that moves | Pleasure / arousal / stress / social need, clamped, decaying over time; five-axis radar adds a model-written "poise" |
| 👂 Understand the user | "I'm sad" is an observation about them, not an override of the bot's mood |
| 🤝 Explainable relationships | 2D force graph, account search, 0–100 favor with 0.1 steps |
| 🌙 Sleep and energy | Awake / dozing / groggy / sleepy / deep sleep; reply budget, wake countdown, 24h curve |
| 💬 Proactive chatting | Random waits, memory callbacks, relationship-driven topics; off by default |
| 💭 Promises kept | "I'll send it later" becomes a real task that fires on time, even after a restart |
| 📓 Diary and dreams | First-person diary with weather; dreams reviewed separately |
| 🎛️ Own console | Nine sections, scope filtering, two themes, no external CDN |

## 💭 Promises (0.3.0)

The bot appends an invisible marker (`<!--promise:slot:description-->`) to a reply.
The plugin strips it before sending, stores the task, and delivers on schedule.

```mermaid
flowchart TD
    A["💬 Reply carries a promise marker"] --> B{"📌 Parsable slot + description"}
    B -->|"no"| Z["Plain reply, nothing stored"]
    B -->|"yes"| C["🗂️ Persist as scheduled"]
    C --> D["⏰ Scan every 60s"]
    D --> E{"📡 Context resolvable"}
    E -->|"route rebuilt from session table"| F["✍️ Compose the follow-up"]
    E -->|"session gone"| G["🚫 Cancel, stop spinning"]
    F --> H{"🌙 Night / quota / auth"}
    H -->|"deep sleep"| I["😴 Defer to wake-up, no retry cost"]
    H -->|"quota"| J["⏭️ Push to next day"]
    H -->|"ok"| K["📤 Send through the host channel"]
    K -->|"accepted"| L["🧠 Write to memory"]
    L --> M["✅ sent"]
    K -->|"rejected / unknown"| N["🔁 Retry after 300s, max 3"]
```

Three deliberate decisions:

- **Host channel, not the native handle.** Reverse-WS adapters return `ok` plus a
  `message_id` for messages that never arrive. The host `send_message` at least
  tells the truth (`unknown`), and we record that as accepted.
- **Works after a restart.** Stored contexts have no `route`; the bridge rebuilds it
  from `adapter_id` / `scene_kind` / `scene_id` and requires an exact match.
- **The follow-up is written to memory.** Otherwise asking "what did you just say"
  gets a blank stare.

Slots: 马上 (2–5 min), 一会儿 (15–30 min), 待会 (40–70 min), 今晚 (20:00–22:59),
明天 / 过几天. Up to 3 active per session; identical wording merges.

Cancel by saying "never mind" / "cancel" — with a single task it just cancels,
with several it asks which one. Full details in [docs/promise.md](docs/promise.md).

## 🚀 Quick start

1. Install via [docs/installation.md](docs/installation.md). Requires AstrBot 4.29.1–4.29.4, Python 3.12+.
2. Open the plugin page `livingemotion` → **Settings → Quick start**.
3. Pick a persona (follow the session, or pin one).
4. Keep mood intensity at **normal**. Set a timezone if you want the sleep schedule.
5. Save, then look at the **TA** page. Empty state before the first real chat is normal.

## 🗺️ Docs

- [Plugin manual](docs/plugin-manual.md)
- [Promise tasks](docs/promise.md)
- [Five-dimension emotion](docs/emotion-five-dimension.md)
- [Architecture](docs/architecture.md) · [API](docs/api.md)
- [Compatibility](docs/compatibility.md) · [Memory](docs/memory.md)
- [Changelog](CHANGELOG.md)

## 🔐 Memory and privacy

Read and write are separate switches. Without LivingMemory the plugin uses a local
vector store (10,000 records / 30 days by default). With LivingMemory it only uses
public facades and real events; no fallback to private databases.

Promise delivery is the exception: the message has already been sent, this is a
post-hoc archive entry, so the source may be rebuilt from the session table.

## 🧯 Failure boundaries

`queued` means queued. `accepted` means the local transaction committed.
Neither means delivered. `send_message(False)` is recorded as rejected, anything
else as unknown. Unknown is never auto-resent.

## 📦 Changelog

Current version **0.3.0** — promise tasks ship: what it said it would do, it does,
including across restarts; the follow-up lands in memory. See [CHANGELOG.md](CHANGELOG.md).

MIT for original content. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**🎯 Mood first, then the words feel real.**
