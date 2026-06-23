# Subcommand Groups

`SlashGroup` lets you nest multiple slash commands under a shared namespace. Users see `/admin kick`, `/admin ban`, `/admin sync` rather than three unrelated top-level commands.

---

## When to use groups

Use `SlashGroup` when commands share a concept and benefit from a common prefix. Avoid groups for commands that happen to belong to the same plugin but serve different purposes — a flat list of top-level commands is easier to discover.

Good fit:
- `/admin kick`, `/admin ban`, `/admin timeout`
- `/shop buy`, `/shop sell`, `/shop balance`
- `/config set`, `/config get`, `/config reset`

Poor fit:
- `/ping` and `/settings` in a single group just because they're in the same plugin

---

## Creating a group

Subclass `SlashGroup` and pass `name` and `description` as class keyword arguments. Each `@slash`-decorated method becomes a subcommand:

```python
from easycord import SlashGroup, slash
import discord

class AdminGroup(SlashGroup, name="admin", description="Server administration"):

    @slash(description="Kick a member from the server")
    async def kick(self, ctx, member: discord.Member, reason: str = ""):
        await ctx.kick(member, reason=reason or None)
        await ctx.respond(f"Kicked {member.display_name}.", ephemeral=True)

    @slash(description="Temporarily mute a member")
    async def timeout(self, ctx, member: discord.Member, seconds: int = 300):
        await ctx.timeout(member, seconds)
        await ctx.respond(f"Timed out {member.display_name} for {seconds}s.", ephemeral=True)
```

Register with `bot.add_group()` (not `bot.add_plugin()`):

```python
bot.add_group(AdminGroup())
```

---

## Class keyword arguments

| Argument | Type | Description |
|---|---|---|
| `name` | `str` | The group name — becomes the first part of `/name subcommand`. Defaults to the class name lowercased |
| `description` | `str` | Shown in the Discord command picker |
| `guild_id` | `int \| None` | Register the group in a single guild only |
| `guild_only` | `bool` | Require a guild context for all subcommands |
| `nsfw` | `bool` | Mark the group as age-restricted |
| `default_permissions` | `discord.Permissions \| None` | Default permission gate for the entire group |
| `allowed_contexts` | | Interaction context types permitted |
| `allowed_installs` | | Installation types permitted |

---

## Permission inheritance

`default_permissions` set on the class applies to every subcommand in the group. Server admins can override this per-command in Discord's Integration settings, but the class-level value is the default:

```python
class ModGroup(
    SlashGroup,
    name="mod",
    description="Moderation tools",
    default_permissions=discord.Permissions(kick_members=True),
):
    ...
```

Individual subcommands can also carry their own `permissions=` middleware or `@require_permissions` — these stack on top of the group-level gate.

---

## Guild-restricted groups

To register a group in a single guild during development:

```python
class DevGroup(SlashGroup, name="dev", description="Dev tools", guild_id=123456789):
    ...
```

For commands that require a guild context at runtime (but are registered globally):

```python
class AdminGroup(SlashGroup, name="admin", description="Admin", guild_only=True):
    ...
```

`guild_only=True` causes commands to respond with an error if invoked outside a server.

---

## Subcommand-level overrides

Each `@slash` method can still carry its own middleware or options independently:

```python
from easycord import slash
from easycord.middleware import require_permissions

class ShopGroup(SlashGroup, name="shop", description="Economy"):

    @slash(description="Buy an item")
    async def buy(self, ctx, item: str, quantity: int = 1):
        ...

    @slash(description="Admin: restock the shop")
    @require_permissions("administrator")
    async def restock(self, ctx):
        ...
```

---

## Accessing bot state

`SlashGroup` extends `Plugin`, so `self.bot` and `self.bot.db` work exactly as in any plugin:

```python
class ShopGroup(SlashGroup, name="shop", description="Economy"):

    @slash(description="Check your balance")
    async def balance(self, ctx):
        bal = await self.bot.db.get(ctx.user.id, "coins", default=0)
        await ctx.respond(f"You have **{bal}** coins.")
```
