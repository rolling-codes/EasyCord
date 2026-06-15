# EasyCord v5.46.0 Release Notes

## 8 New Community Plugins

### BirthdayPlugin

Announce member birthdays automatically at midnight UTC and optionally assign a birthday role for 24 hours.

```python
from easycord import Bot
from easycord.plugins import BirthdayPlugin
from easycord.testing import invoke

bot = Bot(auto_sync=False, db_backend="memory")
bot.add_plugin(BirthdayPlugin())

# Member registers their birthday
ctx = await invoke(bot, "birthday_set", month=6, day=15)

# Admin sets announcement channel
ctx = await invoke(bot, "birthday_channel", channel=my_channel)

# List upcoming birthdays this month
ctx = await invoke(bot, "birthday_list")
```

---

### ReminderPlugin

Set personal reminders using flexible duration strings (`30m`, `2h`, `1d`). Reminders survive bot restarts.

```python
from easycord.plugins import ReminderPlugin

bot.add_plugin(ReminderPlugin())

# Set a reminder for 2 hours from now
ctx = await invoke(bot, "remind", when="2h", message="Pick up the package")

# List pending reminders
ctx = await invoke(bot, "reminders")

# Cancel reminder #3
ctx = await invoke(bot, "reminder_cancel", id=3)
```

---

### VerificationPlugin

Gate new members behind a button click (or an optional challenge question modal) that grants a configured role on success.

```python
from easycord.plugins import VerificationPlugin

bot.add_plugin(VerificationPlugin())

# Configure role + panel channel
ctx = await invoke(bot, "verification_setup", role=member_role, channel=verify_channel)

# (Optional) add a challenge question
ctx = await invoke(bot, "verification_question", text="What is the first rule of this server?")

# Post the verification panel
ctx = await invoke(bot, "verification_panel")
```

---

### ServerStatsPlugin

Create three live-updating voice channels showing member count, online count, and boost count. Updates every 10 minutes to stay within Discord rate limits.

```python
from easycord.plugins import ServerStatsPlugin

bot.add_plugin(ServerStatsPlugin())

# Create stat channels and start the update loop
ctx = await invoke(bot, "stats_setup")

# Remove stat channels and stop updates
ctx = await invoke(bot, "stats_teardown")
```

---

### ScheduledAnnouncementsPlugin

Post recurring messages to any text channel on a configurable interval (`1h`, `6h`, `1d`).

```python
from easycord.plugins import ScheduledAnnouncementsPlugin

bot.add_plugin(ScheduledAnnouncementsPlugin())

# Schedule a daily announcement
ctx = await invoke(bot, "announcement_add", channel=general, interval="24h", message="Daily reminder: stay on topic!")

# List all scheduled announcements
ctx = await invoke(bot, "announcement_list")

# Remove announcement #1
ctx = await invoke(bot, "announcement_remove", id=1)
```

---

### ReputationPlugin

Community rep system with 24-hour per-giver cooldown, a top-10 leaderboard, and admin reset.

```python
from easycord.plugins import ReputationPlugin

bot.add_plugin(ReputationPlugin())

# Give rep to another member
ctx = await invoke(bot, "rep", user=target_member)

# Check your rep score
ctx = await invoke(bot, "rep_check")

# View the leaderboard
ctx = await invoke(bot, "rep_top")

# Admin: reset a member's score
ctx = await invoke(bot, "rep_reset", user=target_member)
```

---

### WordFilterPlugin

Block words/phrases with `delete`, `warn`, or `both` action modes. Optionally exempt a specific role.

```python
from easycord.plugins import WordFilterPlugin

bot.add_plugin(WordFilterPlugin())

# Add a blocked phrase
ctx = await invoke(bot, "filter_add", word="badphrase")

# Set action to delete and warn
ctx = await invoke(bot, "filter_action", action="both")

# Exempt moderators from filtering
ctx = await invoke(bot, "filter_exempt", role=mod_role)

# View blocklist
ctx = await invoke(bot, "filter_list")
```

---

### AutoRolePlugin

Assign one or more roles automatically when a new member joins. Supports an optional delay (useful as a bot-verification window).

```python
from easycord.plugins import AutoRolePlugin

bot.add_plugin(AutoRolePlugin())

# Add a role to auto-assign
ctx = await invoke(bot, "autorole_add", role=member_role)

# Set a 60-second delay before assigning
ctx = await invoke(bot, "autorole_delay", seconds=60)

# View configured roles
ctx = await invoke(bot, "autorole_list")
```

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.46.0/easycord-5.46.0-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.46.0/easycord-5.46.0.tar.gz"
```
