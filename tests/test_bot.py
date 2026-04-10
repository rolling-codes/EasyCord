import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord import Bot, Plugin
from easycord.decorators import slash, on as ec_on


@pytest.fixture
def bot():
    """Bot instance with discord.Client internals mocked out."""
    mock_tree = MagicMock()
    mock_tree.add_command = MagicMock()
    mock_tree.remove_command = MagicMock()
    mock_tree.sync = AsyncMock()

    with patch("discord.Client.__init__", return_value=None), \
         patch("easycord.bot.app_commands.CommandTree", return_value=mock_tree):
        b = Bot(intents=MagicMock(), auto_sync=False)
        b.is_ready = MagicMock(return_value=False)
        return b


# ── use ───────────────────────────────────────────────────────────────────────

def test_use_appends_middleware(bot):
    async def mw(ctx, proceed):
        await proceed()

    bot.use(mw)
    assert mw in bot._middleware


def test_use_returns_middleware(bot):
    async def mw(ctx, proceed):
        await proceed()

    result = bot.use(mw)
    assert result is mw


def test_multiple_middleware_preserved_in_order(bot):
    async def mw1(ctx, _proceed): pass
    async def mw2(ctx, _proceed): pass

    bot.use(mw1)
    bot.use(mw2)
    assert bot._middleware == [mw1, mw2]


# ── on ────────────────────────────────────────────────────────────────────────

def test_on_registers_handler(bot):
    async def handler(msg):
        pass

    bot.on("message")(handler)
    assert handler in bot._event_handlers["message"]


def test_on_multiple_handlers_same_event(bot):
    async def h1(msg): pass
    async def h2(msg): pass

    bot.on("message")(h1)
    bot.on("message")(h2)
    assert h1 in bot._event_handlers["message"]
    assert h2 in bot._event_handlers["message"]


def test_on_returns_original_function(bot):
    async def handler(msg): pass
    result = bot.on("message")(handler)
    assert result is handler


# ── slash ─────────────────────────────────────────────────────────────────────

def test_slash_registers_command(bot):
    @bot.slash(description="Ping the bot")
    async def ping(ctx):
        pass

    bot.tree.add_command.assert_called_once()
    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "ping"
    assert cmd.description == "Ping the bot"


def test_slash_custom_name(bot):
    @bot.slash(name="pong", description="Pong")
    async def handler(ctx):
        pass

    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "pong"


def test_slash_guild_scoped(bot):
    @bot.slash(guild_id=12345)
    async def cmd(ctx):
        pass

    _, kwargs = bot.tree.add_command.call_args
    assert kwargs.get("guild") is not None
    assert kwargs["guild"].id == 12345


# ── add_plugin ────────────────────────────────────────────────────────────────

def test_add_plugin_registers_slash_commands(bot):
    class MyPlugin(Plugin):
        @slash(description="Hello")
        async def hello(self, ctx):
            pass

    plugin = MyPlugin()
    bot.add_plugin(plugin)

    assert plugin in bot._plugins
    assert plugin._bot is bot
    bot.tree.add_command.assert_called_once()


def test_add_plugin_registers_event_handlers(bot):
    class MyPlugin(Plugin):
        @ec_on("member_join")
        async def greet(self, member):
            pass

    plugin = MyPlugin()
    bot.add_plugin(plugin)

    assert plugin.greet in bot._event_handlers.get("member_join", [])


def test_add_multiple_plugins(bot):
    class PluginA(Plugin):
        @slash(description="A")
        async def cmd_a(self, ctx): pass

    class PluginB(Plugin):
        @slash(description="B")
        async def cmd_b(self, ctx): pass

    bot.add_plugin(PluginA())
    bot.add_plugin(PluginB())

    assert bot.tree.add_command.call_count == 2
    assert len(bot._plugins) == 2


# ── remove_plugin ─────────────────────────────────────────────────────────────

async def test_remove_plugin_removes_command(bot):
    class MyPlugin(Plugin):
        @slash(description="cmd")
        async def my_cmd(self, ctx):
            pass

    plugin = MyPlugin()
    bot.add_plugin(plugin)
    await bot.remove_plugin(plugin)

    assert plugin not in bot._plugins
    bot.tree.remove_command.assert_called_once_with("my_cmd", guild=None)


async def test_remove_plugin_removes_event_handler(bot):
    class MyPlugin(Plugin):
        @ec_on("member_join")
        async def greet(self, member):
            pass

    plugin = MyPlugin()
    bot.add_plugin(plugin)
    await bot.remove_plugin(plugin)

    assert plugin.greet not in bot._event_handlers.get("member_join", [])


async def test_remove_plugin_not_loaded_raises(bot):
    with pytest.raises(ValueError, match="has not been added"):
        await bot.remove_plugin(Plugin())


async def test_remove_plugin_calls_on_unload(bot):
    plugin = Plugin()
    plugin.on_unload = AsyncMock()
    plugin._bot = bot
    bot._plugins.append(plugin)

    await bot.remove_plugin(plugin)
    plugin.on_unload.assert_called_once()


# ── dispatch ──────────────────────────────────────────────────────────────────

def test_dispatch_calls_registered_handlers(bot):
    handler = MagicMock()
    bot._event_handlers["custom"] = [handler]

    with patch.object(discord.Client, "dispatch"), \
         patch("asyncio.create_task") as mock_task:
        bot.dispatch("custom", "payload")

    mock_task.assert_called_once()
    handler.assert_called_once_with("payload")


def test_dispatch_skips_unregistered_events(bot):
    with patch.object(discord.Client, "dispatch"), \
         patch("asyncio.create_task") as mock_task:
        bot.dispatch("no_listeners")

    mock_task.assert_not_called()


def test_dispatch_calls_multiple_handlers(bot):
    h1 = MagicMock()
    h2 = MagicMock()
    bot._event_handlers["evt"] = [h1, h2]

    with patch.object(discord.Client, "dispatch"), \
         patch("asyncio.create_task") as mock_task:
        bot.dispatch("evt")

    assert mock_task.call_count == 2
