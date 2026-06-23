# Type Checking with Pyright

EasyCord ships a `pyrightconfig.json` at the repo root pre-configured for plugin authors. It uses `typeCheckingMode: "standard"` — not `"strict"` — because discord.py relies on heavy dynamic dispatch that generates noise at strict level without being actionable.

## Installation

```bash
pip install pyright
```

## Running

```bash
pyright          # from the repo root — picks up pyrightconfig.json automatically
pyright easycord/plugins/my_plugin.py   # single-file pass during development
```

## What the config checks (and why)

| Rule | Level | Reason |
|------|-------|--------|
| `reportMissingImports` | error | Catches missing packages before runtime |
| `reportUndefinedVariable` | error | Typos in variable names |
| `reportReturnType` | error | Functions that forget to return a value |
| `reportAttributeAccessIssue` | warning | Attributes that don't exist on a type |
| `reportMissingTypeArgument` | warning | Generic types used without parameters |
| `reportUnknownMemberType` | off | discord.py internals are largely untyped |
| `reportUnknownVariableType` | off | Same: heavy use of `Any` in discord.py |
| `reportUnknownArgumentType` | off | Same |

## Common plugin type patterns

### Typing `ctx`

Import `Context` from `easycord` and annotate command parameters directly:

```python
from easycord import Context, Plugin, slash

class MyPlugin(Plugin):
    @slash(description="Say hello")
    async def hello(self, ctx: Context) -> None:
        await ctx.respond("Hello!")
```

`ctx.user` and `ctx.member` are the correct attributes. `ctx.author` does not exist and will produce a type error. `ctx.is_admin` is a property — do not call it as a method.

### Typing event handlers

discord.py event payloads use concrete types from the `discord` namespace:

```python
import discord
from easycord import Plugin, on

class GuildPlugin(Plugin):
    @on("member_join")
    async def handle_join(self, member: discord.Member) -> None:
        ...

    @on("message")
    async def handle_message(self, message: discord.Message) -> None:
        ...
```

### TYPE_CHECKING imports for cyclic deps

EasyCord uses the same pattern internally. Copy it for your own cyclic imports:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from easycord import Bot  # imported only by the type checker, not at runtime

class MyPlugin(Plugin):
    def setup(self, bot: Bot) -> None:
        ...
```

### Awaiting `ToolLimiter`

`ToolLimiter.check_limit`, `reset_user`, and `reset_tool` are all async. Forgetting `await` is a common mistake that pyright will catch at the call site:

```python
# correct
allowed = await self._bot.tool_limiter.check_limit(user_id, "search")

# wrong — pyright flags this as returning a coroutine, not a bool
allowed = self._bot.tool_limiter.check_limit(user_id, "search")
```

## Silencing discord.py stub gaps

When a discord.py attribute genuinely exists at runtime but pyright can't see it through the stubs, use a narrow inline suppression with the specific code:

```python
channel = interaction.channel
channel.send(...)  # type: ignore[union-attr]
```

Prefer `type: ignore[specific-code]` over a bare `type: ignore` so suppressions don't silently swallow unrelated future errors.

For channel sends specifically, EasyCord provides `SENDABLE_CHANNEL_TYPES` to narrow the type properly instead of suppressing:

```python
from easycord.helpers.tools import SENDABLE_CHANNEL_TYPES

if isinstance(channel, SENDABLE_CHANNEL_TYPES):
    await channel.send(content)
```

## Editor integration

Both VS Code (Pylance) and Neovim (via `pyright` LSP) pick up `pyrightconfig.json` automatically. No additional configuration is needed.
