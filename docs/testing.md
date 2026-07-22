# Testing Commands

`easycord.testing` provides everything needed to exercise slash commands and plugin logic without a Discord connection.

---

## PluginTestSuite

The fastest way to write plugin tests. Extend it and get a wired-up bot, plugin factory, and assertion helpers for free.

```python
from easycord.testing import PluginTestSuite

class TestGreetPlugin(PluginTestSuite):
    def setup_method(self):
        super().setup_method()
        self.plugin = self.make_plugin(GreetPlugin)

    async def test_greet_responds_with_hello(self):
        ctx = await self.invoke_command("greet", name="Alice")
        self.assert_last_response(ctx, "Hello, Alice!")

    async def test_greet_ephemeral_by_default(self):
        ctx = await self.invoke_command("greet", name="Alice")
        assert ctx.responses[-1].ephemeral is True
```

### Methods provided by `PluginTestSuite`

| Method | What it does |
|---|---|
| `make_plugin(PluginClass)` | Instantiates a plugin and wires it to `self.bot` |
| `invoke_command(name, **kwargs)` | Calls the named slash command with keyword args |
| `invoke_autocomplete(name, **kwargs)` | Triggers the autocomplete callback |
| `invoke_component(custom_id, **kwargs)` | Fires a component (button / select) handler |
| `invoke_modal(modal_id, **kwargs)` | Submits a modal |
| `invoke_user_command(name, target_user)` | Runs a user context-menu command |
| `invoke_message_command(name, target_message)` | Runs a message context-menu command |
| `assert_last_response(ctx, expected)` | Asserts the last captured response content equals `expected` |

---

## Constructing plugins

Use `object.__new__` if you need to construct a plugin without calling its `__init__` directly. Set `_bot` (not `bot`) directly:

```python
plugin = object.__new__(MyPlugin)
plugin._bot = bot   # _bot is the raw backing attribute; bot is a property
Plugin.__init__(plugin)
```

`PluginTestSuite.make_plugin` does this for you when the plugin has a no-arg constructor.

---

## `invoke` helpers

Standalone helpers for tests that don't use `PluginTestSuite`:

```python
from easycord.testing import invoke, invoke_autocomplete, FakeContextBuilder

async def test_ping():
    bot = Bot(auto_sync=False)

    @bot.slash(description="Ping")
    async def ping(ctx):
        await ctx.respond("Pong!")

    ctx = await invoke(bot, "ping")
    ctx.assert_content("Pong!")
```

All `invoke_*` helpers return a `FakeContext` with `.last_response`, `.responses`, and `.assert_content`.

---

## `FakeContextBuilder`

Build a context with specific user attributes when you need more control:

```python
from easycord.testing import FakeContextBuilder

ctx = (
    FakeContextBuilder()
    .with_user(42, name="alice")
    .in_guild(100)
    .as_admin()
    .with_roles(999, 1234)
    .with_locale("fr")
    .build()
)
```

| Builder method | Effect |
|---|---|
| `.with_user(id, name=..., display_name=...)` | Set user ID, username, and display name |
| `.in_guild(id)` | Place the interaction in a guild |
| `.as_admin()` | Grant administrator permission |
| `.with_permissions(**permissions)` | Set specific Discord permissions by name (e.g. `manage_messages=True`) |
| `.with_roles(*role_ids)` | Add role IDs to the member |
| `.with_locale(locale)` | Set the interaction locale (e.g. `"fr"`, `"ja"`) |
| `.in_dm()` | Make it a DM (no guild) |
| `.build()` | Return the `FakeContext` |

---

## `FakeContext` properties

```python
ctx.last_response        # str | None — content of the most recent response
ctx.responses            # list[_CapturedResponse]
ctx.response_count       # int
ctx.assert_content(text) # raises AssertionError if last_response != text
```

Each entry in `ctx.responses` has:
- `.content` — the text sent
- `.ephemeral` — whether it was sent as ephemeral
- `.embed` — the embed if one was sent

---

## Testing guild-only commands

```python
async def test_birthday_set_requires_guild(bot):
    plugin = make_plugin(BirthdayPlugin)

    ctx = FakeContextBuilder().in_dm().build()
    # guild_only commands return early when guild is None
    await invoke_command(bot, "birthday_set", ctx=ctx, month=1, day=1)
    assert ctx.response_count == 0
```

---

## Full example

```python
from easycord import Plugin, slash
from easycord.testing import PluginTestSuite


class CounterPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self._count = 0

    @slash(description="Increment the counter.")
    async def increment(self, ctx):
        self._count += 1
        await ctx.respond(f"Count: {self._count}", ephemeral=True)


class TestCounterPlugin(PluginTestSuite):
    def setup_method(self):
        super().setup_method()
        self.plugin = self.make_plugin(CounterPlugin)

    async def test_first_increment(self):
        ctx = await self.invoke_command("increment")
        self.assert_last_response(ctx, "Count: 1")

    async def test_second_increment(self):
        await self.invoke_command("increment")
        ctx = await self.invoke_command("increment")
        self.assert_last_response(ctx, "Count: 2")

    async def test_response_is_ephemeral(self):
        ctx = await self.invoke_command("increment")
        assert ctx.responses[-1].ephemeral is True
```
