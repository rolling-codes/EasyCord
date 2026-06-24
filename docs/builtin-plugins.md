# Built-in Plugins

EasyCord ships 28 ready-to-use plugins. Four load automatically when you pass `load_builtin_plugins=True` to `Bot`; the other 24 are opt-in.

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
| `TagsPlugin` | `/tag create`, `/tag get`, `/tag delete`, `/tag list` — per-guild text snippets |
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

**`PollsPlugin`** (also default) — `/poll` with multi-option voting.

**`ReputationPlugin`** — `/rep give`, `/rep check` — lets members award reputation points to each other.
```python
from easycord.plugins import ReputationPlugin
bot.add_plugin(ReputationPlugin())
```

**`GiveawayPlugin`** — `/giveaway start`, `/giveaway end`, `/giveaway reroll` — timed prize drawings.
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

**`WordFilterPlugin`** — Auto-deletes messages containing configured forbidden words. Configure via `/filter add`, `/filter remove`, `/filter list`.
```python
from easycord.plugins import WordFilterPlugin
bot.add_plugin(WordFilterPlugin())
```

**`AIModeratorPlugin`** — Uses an AI provider to evaluate messages and flag or remove those that violate configured rules. Requires `Bot(ai_provider=…)`.
```python
from easycord.plugins import AIModeratorPlugin
bot.add_plugin(AIModeratorPlugin())
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

**`AutoRolePlugin`** — Assign roles automatically when members join. Configure target role IDs via `/autorole set`.
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

**`TicketsPlugin`** — `/ticket open` — creates a private support thread per user with staff access control.
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

**`OpenClaudePlugin`** (also exported as `AIPlugin`) — `/chat` — conversational AI powered by your configured provider. Requires `Bot(ai_provider=…)`.
```python
from easycord.plugins import OpenClaudePlugin
bot.add_plugin(OpenClaudePlugin())
```

**`OpenClawPlugin`** — Extended Claude/Anthropic integration with tool-calling support.
```python
from easycord.plugins import OpenClawPlugin
bot.add_plugin(OpenClawPlugin())
```

---

## Storage requirements

Most plugins that persist data (LevelsPlugin, EconomyPlugin, BirthdayPlugin, etc.) use `Bot.db`. The default is an in-memory store. For production, configure SQLite:

```python
from easycord import Bot, SQLiteDatabase

bot = Bot(
    db=SQLiteDatabase("data/bot.db"),
    load_builtin_plugins=True,
)
```

Plugins that need persistent data will silently fall back to in-memory storage if no database is configured — data will not survive bot restarts.

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
