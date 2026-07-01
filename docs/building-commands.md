# Building Commands

EasyCord gives you many ways to interact with users: slash commands, context menus, buttons, select menus, and modals. This guide covers them all and when to use each.

---

## Your First Slash Command

A slash command is registered with Discord and shows up in the `/` menu.

```python
from easycord import Plugin, slash

class GreetPlugin(Plugin):
    @slash(description="Greet someone")
    async def greet(self, ctx, user: str):
        await ctx.respond(f"Hello, {user}!")
```

Register it with:

```python
bot.add_plugin(GreetPlugin())
```

Users will see `/greet` in Discord's command menu.

---

## Command Parameters

Parameters automatically become Discord options. EasyCord converts Python types into Discord types:

```python
@slash(description="Rate something")
async def rate(self, ctx, item: str, stars: int = 5, comment: str = ""):
    await ctx.respond(f"**{item}**: {stars}⭐ ({comment})")
```

Supported types:
- `str` — text input
- `int` — number (-2^31 to 2^31)
- `float` — decimal
- `bool` — yes/no toggle
- `discord.User` — user picker
- `discord.Role` — role picker
- `discord.Channel` — channel picker
- `discord.Member` — member picker (guild-only)

Discord limits commands to 25 options. Use options sparingly; if you need many inputs, consider a modal form instead.

---

## Autocomplete

Show dynamic suggestions as users type:

```python
from easycord import autocomplete

class FruitPlugin(Plugin):
    @autocomplete("fruit", command="pick")
    async def fruit_choices(self, ctx, current: str, options: dict):
        fruits = ["apple", "banana", "orange", "grape"]
        return [f for f in fruits if current.lower() in f.lower()]

    @slash(description="Pick your favorite fruit")
    async def pick(self, ctx, fruit: str):
        await ctx.respond(f"You picked **{fruit}**!")
```

The callback receives:
- `current` — what the user has typed so far
- `options` — other parameters already filled in
- Return a list of strings (up to 25) to show as suggestions

Autocomplete is tested offline:

```python
ctx = await invoke_autocomplete(bot, "pick", current="app", options={})
# Returns list of matching fruits
```

---

## Organizing Commands with Groups

When related commands share a prefix, use `SlashGroup`:

```python
from easycord import SlashGroup, slash

class AdminGroup(SlashGroup, name="admin", description="Server administration"):

    @slash(description="Kick a member from the server")
    async def kick(self, ctx, member: discord.Member, reason: str = ""):
        await ctx.kick(member, reason=reason or None)
        await ctx.respond(f"Kicked {member.display_name}.", ephemeral=True)

    @slash(description="Temporarily mute a member")
    async def timeout(self, ctx, member: discord.Member, seconds: int = 300):
        await ctx.timeout(member, seconds)
        await ctx.respond(f"Timed out {member.display_name}.", ephemeral=True)

    @slash(description="Ban a member from the server")
    async def ban(self, ctx, member: discord.Member, reason: str = ""):
        await ctx.ban(member, reason=reason or None)
        await ctx.respond(f"Banned {member.display_name}.", ephemeral=True)
```

Users will see `/admin kick`, `/admin timeout`, and `/admin ban` under a single prefix.

Register groups with:

```python
bot.add_group(AdminGroup())
```

### When to Use Groups

Use groups when commands genuinely belong under a shared concept:
- `/admin kick`, `/admin ban`, `/admin timeout` ✅
- `/shop buy`, `/shop sell`, `/shop balance` ✅
- `/config set`, `/config get`, `/config reset` ✅

Don't use groups just because commands are in the same plugin:
- `/ping` and `/feedback` don't belong in a group, even if they're both in `UtilityPlugin` ❌

### Group Permissions

Set default permissions for the entire group:

```python
class ModGroup(
    SlashGroup,
    name="mod",
    description="Moderation tools",
    default_permissions=discord.Permissions(kick_members=True),
):
    ...
```

Server admins can override these per-command in Discord's Integration settings. Individual subcommands can have their own `@require_permissions` middleware on top of the group-level gate.

### Guild-Restricted Groups

For development groups that should only appear in one server:

```python
class DevGroup(SlashGroup, name="dev", description="Dev tools", guild_id=123456789):
    ...
```

For production groups that users can only invoke in servers (not DMs):

```python
class AdminGroup(SlashGroup, name="admin", description="Admin", guild_only=True):
    ...
```

---

## Buttons and Select Menus

Buttons let users interact with your bot after a command completes. They're sent as part of a message and persist until clicked (or expire).

### Button Components

```python
import discord
from easycord import Plugin, component, slash

class VotePlugin(Plugin):
    @slash(description="Start a vote")
    async def vote(self, ctx, question: str):
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Yes", custom_id="vote_yes"))
        view.add_item(discord.ui.Button(label="No", custom_id="vote_no"))
        await ctx.respond(question, view=view)

    @component("vote_yes")
    async def vote_yes(self, ctx):
        await ctx.respond("You voted yes!", ephemeral=True)

    @component("vote_no")
    async def vote_no(self, ctx):
        await ctx.respond("You voted no!", ephemeral=True)
```

### Select Menus

Select menus let users pick from a dropdown:

```python
from easycord import component

class ShopPlugin(Plugin):
    @slash(description="Browse the shop")
    async def shop(self, ctx):
        view = discord.ui.View()
        select = discord.ui.Select(
            custom_id="shop_select",
            placeholder="Choose an item to buy",
            options=[
                discord.SelectOption(label="Sword", value="sword", description="100 coins"),
                discord.SelectOption(label="Shield", value="shield", description="75 coins"),
                discord.SelectOption(label="Potion", value="potion", description="25 coins"),
            ]
        )
        view.add_item(select)
        await ctx.respond("What would you like to buy?", view=view)

    @component("shop_select")
    async def shop_select(self, ctx, values: list[str]):
        item = values[0]  # User selected this item
        await ctx.respond(f"You bought a **{item}**!", ephemeral=True)
```

---

## Dynamic Component Routing

For complex interactions where the button ID carries data (like a ticket ID), use dynamic routes:

```python
@component("ticket:close:{ticket_id:int}")
async def close_ticket(self, ctx, ticket_id: int):
    await ctx.respond(f"Closing ticket {ticket_id}...", ephemeral=True)
```

When a button is clicked with `custom_id="ticket:close:42"`, the `ticket_id` parameter automatically becomes `42` as an integer.

### Supported Route Types

- `str` — any text
- `int` — integer
- `snowflake` — Discord snowflake (user ID, role ID, etc.)

### Multi-Parameter Routes

Buttons can encode multiple IDs:

```python
@component("poll:vote:{poll_id:int}:{choice_id:int}")
async def vote(self, ctx, poll_id: int, choice_id: int):
    await ctx.respond("Vote recorded!", ephemeral=True)
```

Custom ID would be: `poll:vote:12:3` (poll 12, choice 3).

### Component TTL (Time-To-Live)

Persistent components (no `ttl`) can be re-registered during bot restarts and will work indefinitely:

```python
@component("ticket:close:{ticket_id:int}")  # Persistent
async def close_ticket(self, ctx, ticket_id: int):
    ...
```

Temporary components (with `ttl`) expire after a deadline and are intended for short-lived flows:

```python
@component("wizard:{session_id:snowflake}:next", ttl=300)  # Expires after 300 seconds
async def wizard_next(self, ctx, session_id: int):
    ...
```

Routes without `ttl` work across bot restarts. Routes with `ttl` are cleaned up after their deadline.

---

## Modals (Multi-Field Forms)

Modals let users fill out a form with multiple fields. They're typically triggered by a button click:

```python
from easycord import modal

class FeedbackPlugin(Plugin):
    @slash(description="Send feedback")
    async def feedback(self, ctx):
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Send Feedback", custom_id="feedback_form"))
        await ctx.respond("Click the button to send feedback.", view=view)

    @component("feedback_form")
    async def feedback_button(self, ctx):
        # Modal is built inline and shown immediately
        class FeedbackModal(discord.ui.Modal):
            title = "Send Feedback"
            feedback = discord.ui.TextInput(label="Your feedback", style=discord.TextInputStyle.long)
            rating = discord.ui.TextInput(label="Rating (1-5)", style=discord.TextInputStyle.short)

        modal = FeedbackModal()
        await ctx.show_modal(modal)

    @modal("feedback")  # or handle in a decorator if reusable
    async def handle_feedback(self, ctx, feedback: str, rating: str):
        await ctx.respond(f"Thanks! Rating: {rating}/5", ephemeral=True)
```

---

## Context Menus

Context menus (right-click on a user or message) are simpler than slash commands — they don't have options.

### User Context Menus

```python
from easycord import user_command

class ProfilePlugin(Plugin):
    @user_command(name="View Profile")
    async def view_profile(self, ctx, user: discord.User):
        await ctx.respond(f"Profile for {user.mention}", ephemeral=True)
```

Right-click a user → "Apps" → "View Profile" will trigger this.

### Message Context Menus

```python
from easycord import message_command

class ArchivePlugin(Plugin):
    @message_command(name="Archive Message")
    async def archive_message(self, ctx, message: discord.Message):
        await ctx.respond(f"Archived: {message.content}", ephemeral=True)
```

Right-click a message → "Apps" → "Archive Message" will trigger this.

---

## Command Registration & Sync

After adding commands, you need to sync them to Discord:

```python
await bot.sync_commands()
```

Discord only sees commands that have been synced. EasyCord provides tools to preview changes:

```python
await bot.preview_sync_commands()  # Shows what will change without applying
```

For more control, see [Command Sync & Registration](command-sync.md).

---

## Inspecting Your Commands

See all registered commands:

```python
registry = bot.inspect_interactions()
print(registry.slash)     # All slash commands
print(registry.component) # All components
print(registry.modal)     # All modals
```

Or enable the inspector command:

```python
bot.enable_interaction_inspector(owner_ids={YOUR_ID})
```

Then `/easycord interactions` will show a live count of all interactions.

---

## Next Steps

- Ready to test your commands? → [Testing Commands](testing.md)
- Need to control who can use commands? → [Request Lifecycle](request-lifecycle.md)
- Want to build a larger feature? → [Organizing Code](organizing-code.md)
