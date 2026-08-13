# Built-in Plugins

EasyCord ships 30 ready-to-use plugins. Four load automatically when you pass `load_builtin_plugins=True` to `Bot`; the other 26 are opt-in.

---

## Default plugins

These four load when `Bot(load_builtin_plugins=True)` is set:

```python
from easycord import Bot

bot = Bot(load_builtin_plugins=True)
```

| Plugin | Commands |
|---|---|
| `WelcomePlugin` | Sends a configurable welcome message when a member joins |
| `TagsPlugin` | `/tag set`, `/tag get`, `/tag delete`, `/tag list` — per-guild text snippets |
| `PollsPlugin` | `/poll` — create emoji polls with configurable options |
| `LevelsPlugin` | Tracks XP per message; `/rank`, `/leaderboard`, configurable role rewards |

---

## Optional plugins

Import and register individually. None of these load automatically.

```python
from easycord.plugins import ModerationPlugin, ReminderPlugin

bot.add_plugin(ModerationPlugin())
bot.add_plugin(ReminderPlugin())
```

---

### Community & engagement

**`StarboardPlugin`** — Pins highly-reacted messages to a designated starboard channel.
```python
from easycord.plugins import StarboardPlugin
bot.add_plugin(StarboardPlugin())
```

**`SuggestionsPlugin`** — `/suggest` — members submit suggestions that land in a review channel with upvote/downvote reactions.
```python
from easycord.plugins import SuggestionsPlugin
bot.add_plugin(SuggestionsPlugin())
```

**`ReputationPlugin`** — `/rep`, `/rep_check`, `/rep_top` — lets members award reputation points to each other.
```python
from easycord.plugins import ReputationPlugin
bot.add_plugin(ReputationPlugin())
```

**`GiveawayPlugin`** — `/giveaway`, `/giveaway_end`, `/giveaway_reroll` — timed prize drawings.
```python
from easycord.plugins import GiveawayPlugin
bot.add_plugin(GiveawayPlugin())
```

---

### Moderation & safety

**`ModerationPlugin`** — `/kick`, `/ban`, `/unban`, `/timeout`, `/warn` — standard moderation toolkit. Requires `kick_members` and `ban_members` permissions.
```python
from easycord.plugins import ModerationPlugin
bot.add_plugin(ModerationPlugin())
```

**`WordFilterPlugin`** — Auto-deletes messages containing configured forbidden words. Configure via `/filter_add`, `/filter_remove`, `/filter_list`.
```python
from easycord.plugins import WordFilterPlugin
bot.add_plugin(WordFilterPlugin())
```

**`AIModeratorPlugin`** — Uses an orchestrator to evaluate messages and flag or remove those that violate configured rules. Without an orchestrator, AI analysis is disabled.
```python
from easycord import Bot, FallbackStrategy, Orchestrator
from easycord.plugins import AIModeratorPlugin, OpenAIProvider

bot = Bot()
orchestrator = Orchestrator(
    strategy=FallbackStrategy([OpenAIProvider()]),
    tools=bot.tool_registry,
)
bot.add_plugin(AIModeratorPlugin(orchestrator=orchestrator))
```

**`VerificationPlugin`** — Gate new members behind a verification step before they can access the server.
```python
from easycord.plugins import VerificationPlugin
bot.add_plugin(VerificationPlugin())
```

**`SecurityLabPlugin`** — Security testing utilities; intended for bot development and audit workflows.
```python
from easycord.plugins import SecurityLabPlugin
bot.add_plugin(SecurityLabPlugin())
```

---

### Automation & roles

**`AutoRolePlugin`** — Assign roles automatically when members join. Configure target role IDs via `/autorole_add`, `/autorole_remove`, and `/autorole_list`.
```python
from easycord.plugins import AutoRolePlugin
bot.add_plugin(AutoRolePlugin())
```

**`AutoResponderPlugin`** — Trigger custom replies when a message matches a keyword or pattern.
```python
from easycord.plugins import AutoResponderPlugin
bot.add_plugin(AutoResponderPlugin())
```

**`ReactionRolesPlugin`** — Assign roles when members react to a specific message with a specific emoji.
```python
from easycord.plugins import ReactionRolesPlugin
bot.add_plugin(ReactionRolesPlugin())
```

**`RolePersistencePlugin`** — Restores a member's roles if they leave and rejoin the server.
```python
from easycord.plugins import RolePersistencePlugin
bot.add_plugin(RolePersistencePlugin())
```

**`ServerSetupPlugin`** — `/setup-server` — preview and apply a server preset (channels, roles, permissions) from four templates: gaming, community, study, creator. Additive only; see [Server Setup Templates](server-setup.md).

```python
from easycord.plugins import ServerSetupPlugin
bot.add_plugin(ServerSetupPlugin())
```

---

### Utilities & information

**`ReminderPlugin`** — `/remind me in 2h do thing` — sets per-user reminders delivered via DM.
```python
from easycord.plugins import ReminderPlugin
bot.add_plugin(ReminderPlugin())
```

**`BirthdayPlugin`** — Members register birthdays; the bot posts a message and optionally assigns a birthday role.
```python
from easycord.plugins import BirthdayPlugin
bot.add_plugin(BirthdayPlugin())
```

**`ServerStatsPlugin`** — Displays member count, online count, and bot uptime via `/stats`.
```python
from easycord.plugins import ServerStatsPlugin
bot.add_plugin(ServerStatsPlugin())
```

**`MemberLoggingPlugin`** — Logs join/leave events to a configurable channel.
```python
from easycord.plugins import MemberLoggingPlugin
bot.add_plugin(MemberLoggingPlugin())
```

**`InviteTrackerPlugin`** — Tracks which invite link a new member used when joining.
```python
from easycord.plugins import InviteTrackerPlugin
bot.add_plugin(InviteTrackerPlugin())
```

**`ScheduledAnnouncementsPlugin`** — Post recurring or one-off messages to a channel on a schedule.
```python
from easycord.plugins import ScheduledAnnouncementsPlugin
bot.add_plugin(ScheduledAnnouncementsPlugin())
```

**`TicketsPlugin`** — `/ticket_open` — creates a private support thread per user with staff access control.
```python
from easycord.plugins import TicketsPlugin
bot.add_plugin(TicketsPlugin())
```

**`EconomyPlugin`** — `/balance`, `/daily`, `/transfer` — virtual currency system with per-guild balances.
```python
from easycord.plugins import EconomyPlugin
bot.add_plugin(EconomyPlugin())
```

**`TranslatePlugin`** — `/translate` — translates text between languages using deep-translator.
```python
from easycord.plugins import TranslatePlugin
bot.add_plugin(TranslatePlugin())
```

---

### AI plugins

**`AIPlugin`** — `/ask` — conversational AI powered by the provider you pass to the plugin. `OpenClaudePlugin` is a backwards-compatible subclass of `AIPlugin` and can be used interchangeably.

```python
from easycord.plugins import AIPlugin, OpenAIProvider
bot.add_plugin(AIPlugin(provider=OpenAIProvider()))
```

**`OpenClawPlugin`** — Extended Claude/Anthropic integration with tool-calling support.
```python
from easycord.plugins import OpenClawPlugin
bot.add_plugin(OpenClawPlugin())
```

---

## Storage requirements

Most plugins that persist data (LevelsPlugin, EconomyPlugin, BirthdayPlugin, etc.) use `Bot.db`. The default is local SQLite at `.easycord/library.db`; use `db_backend="memory"` for disposable tests. For production, configure an explicit SQLite path:

```python
from easycord import Bot, SQLiteDatabase

bot = Bot(
    database=SQLiteDatabase("data/bot.db"),
    load_builtin_plugins=True,
)
```

Plugins that need persistent data use the configured database, or the default local SQLite database when none is configured.

---

## Complete example: defaults + opt-ins

Here's a bot that loads the four default plugins and adds several opt-in plugins:

```python
from easycord import Bot, SQLiteDatabase
from easycord.plugins import (
    ModerationPlugin,
    EconomyPlugin,
    ReminderPlugin,
    StarboardPlugin,
)

bot = Bot(
    load_builtin_plugins=True,  # loads: welcome, tags, polls, levels
    database=SQLiteDatabase("bot.db"),  # for persistence
)

# Add opt-in plugins
bot.add_plugins(
    ModerationPlugin(),   # /kick, /ban, /timeout, /warn
    EconomyPlugin(),      # /balance, /daily, /transfer
    ReminderPlugin(),     # /remind me in 2h do X
    StarboardPlugin(),    # React with ⭐ to pin
)

bot.run("YOUR_DISCORD_TOKEN")
```

See [examples/with-builtin-plugins.py](../examples/with-builtin-plugins.py) for a complete working bot.

---

## Loading multiple plugins at once

```python
from easycord.plugins import (
    ModerationPlugin,
    ReminderPlugin,
    ServerStatsPlugin,
    StarboardPlugin,
)

for plugin in [ModerationPlugin, ReminderPlugin, ServerStatsPlugin, StarboardPlugin]:
    bot.add_plugin(plugin())
```
