import asyncio

import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord import Plugin
from easycord.decorators import slash, on as ec_on, task


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


def test_bot_stores_ai_provider():
    from easycord import Bot

    provider = object()
    bot = Bot(ai_provider=provider)

    assert bot.ai_provider is provider


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


def test_slash_nsfw_flag_is_forwarded(bot):
    contexts = discord.AppCommandContext(guild=True, dm_channel=False, private_channel=True)
    installs = discord.AppInstallationType(guild=True, user=False)

    @bot.slash(
        description="Secret",
        nsfw=True,
        allowed_contexts=contexts,
        allowed_installs=installs,
    )
    async def secret(ctx):
        pass

    cmd = bot.tree.add_command.call_args[0][0]
    assert getattr(cmd, "nsfw", False) is True
    assert getattr(cmd, "allowed_contexts", None) == contexts
    assert getattr(cmd, "allowed_installs", None) == installs


def test_user_command_metadata_is_forwarded(bot):
    contexts = discord.AppCommandContext(guild=False, dm_channel=True, private_channel=False)
    installs = discord.AppInstallationType(guild=False, user=True)

    @bot.user_command(
        name="Inspect",
        nsfw=True,
        allowed_contexts=contexts,
        allowed_installs=installs,
    )
    async def inspect_user(ctx, member):
        pass

    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "Inspect"
    assert getattr(cmd, "nsfw", False) is True
    assert getattr(cmd, "allowed_contexts", None) == contexts
    assert getattr(cmd, "allowed_installs", None) == installs


async def test_slash_guild_only_blocks_dm(bot):
    """guild_only=True on @bot.slash rejects interactions with no guild."""
    handler_called = False

    @bot.slash(description="server only", guild_only=True)
    async def _server_cmd(_ctx):
        nonlocal handler_called
        handler_called = True

    cmd = bot.tree.add_command.call_args[0][0]

    interaction = MagicMock()
    interaction.guild = None
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.command = MagicMock()
    interaction.command.name = "server_cmd"
    interaction.user = MagicMock()

    await cmd.callback(interaction)
    assert not handler_called
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


async def test_slash_ephemeral_forces_ephemeral_response(bot):
    """ephemeral=True on @bot.slash makes ctx._force_ephemeral True."""
    captured_ctx = {}

    @bot.slash(description="hidden", ephemeral=True)
    async def _hidden_cmd(_ctx):
        captured_ctx["ctx"] = _ctx

    cmd = bot.tree.add_command.call_args[0][0]

    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.command = MagicMock()
    interaction.command.name = "hidden"
    interaction.user = MagicMock()

    await cmd.callback(interaction)
    assert captured_ctx["ctx"]._force_ephemeral is True


async def test_slash_guild_only_passes_in_guild(bot):
    """guild_only=True on @bot.slash allows invocation inside a guild."""
    handler_called = False

    @bot.slash(description="server only", guild_only=True)
    async def server_cmd(ctx):
        nonlocal handler_called
        handler_called = True

    cmd = bot.tree.add_command.call_args[0][0]

    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.command = MagicMock()
    interaction.command.name = "server_cmd"
    interaction.user = MagicMock()

    await cmd.callback(interaction)
    assert handler_called


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


def test_add_plugins_registers_multiple(bot):
    class PluginA(Plugin):
        @slash(description="A")
        async def cmd_a(self, ctx): pass

    class PluginB(Plugin):
        @slash(description="B")
        async def cmd_b(self, ctx): pass

    bot.add_plugins(PluginA(), PluginB())

    assert bot.tree.add_command.call_count == 2
    assert len(bot._plugins) == 2


def test_load_builtin_plugins_registers_bundled_plugins(bot):
    from easycord.plugin import Plugin

    class A(Plugin):
        pass

    class B(Plugin):
        pass

    with patch("easycord.bot.build_builtin_plugins", return_value=(A(), B())):
        bot.load_builtin_plugins()

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


# ── permissions ───────────────────────────────────────────────────────────────

def _make_interaction(*, guild=True, has_perm=True):
    """Build a minimal mock interaction for permission/cooldown tests."""
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.command.name = "test"
    interaction.user.id = 42

    if guild:
        member = MagicMock()
        member.guild_permissions.kick_members = has_perm
        interaction.guild = MagicMock()
        interaction.guild.get_member = MagicMock(return_value=member)
    else:
        interaction.guild = None

    return interaction


async def test_permissions_allows_when_member_has_perm(bot):
    invoked = []

    async def on_cmd(*_):
        invoked.append(True)

    bot.slash(description="test", permissions=["kick_members"])(on_cmd)
    callback = bot.tree.add_command.call_args[0][0].callback
    await callback(_make_interaction(has_perm=True))
    assert invoked


async def test_permissions_blocks_when_missing(bot):
    async def on_cmd(*_):
        pass

    bot.slash(description="test", permissions=["kick_members"])(on_cmd)
    interaction = _make_interaction(has_perm=False)
    callback = bot.tree.add_command.call_args[0][0].callback
    await callback(interaction)

    msg = interaction.response.send_message.call_args[0][0]
    assert "kick_members" in msg
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


async def test_permissions_blocks_in_dm(bot):
    async def on_cmd(*_):
        pass

    bot.slash(description="test", permissions=["kick_members"])(on_cmd)
    interaction = _make_interaction(guild=False)
    callback = bot.tree.add_command.call_args[0][0].callback
    await callback(interaction)

    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── per-command rate limit ────────────────────────────────────────────────────

async def test_rate_limit_per_command_allows_first_call(bot):
    invoked = []

    async def on_cmd(*_):
        invoked.append(True)

    bot.slash(description="test", cooldown=10.0)(on_cmd)
    callback = bot.tree.add_command.call_args[0][0].callback
    await callback(_make_interaction())
    assert invoked


async def test_rate_limit_per_command_blocks_second_call(bot):
    async def on_cmd(*_):
        pass

    bot.slash(description="test", cooldown=10.0)(on_cmd)
    callback = bot.tree.add_command.call_args[0][0].callback
    interaction = _make_interaction()
    await callback(interaction)
    await callback(interaction)

    assert interaction.response.send_message.call_count == 1
    msg = interaction.response.send_message.call_args[0][0]
    assert "cooldown" in msg.lower()


async def test_rate_limit_per_command_independent_per_user(bot):
    invoked = []

    async def on_cmd(ctx):
        invoked.append(ctx.user.id)

    bot.slash(description="test", cooldown=10.0)(on_cmd)
    callback = bot.tree.add_command.call_args[0][0].callback

    i1 = _make_interaction()
    i1.user.id = 1
    i2 = _make_interaction()
    i2.user.id = 2

    await callback(i1)
    await callback(i2)

    assert invoked == [1, 2]


# ── user_command ──────────────────────────────────────────────────────────────

def test_user_command_registers_context_menu(bot):
    @bot.user_command(name="User Info")
    async def user_info(ctx, member):
        pass

    bot.tree.add_command.assert_called_once()
    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "User Info"


def test_user_command_defaults_name_to_function_name(bot):
    @bot.user_command()
    async def show_profile(ctx, member):
        pass

    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "show_profile"


def test_user_command_returns_original_function(bot):
    async def handler(ctx, member):
        pass

    result = bot.user_command(name="X")(handler)
    assert result is handler


async def test_user_command_invokes_handler_with_target(bot):
    received = []

    @bot.user_command(name="Info")
    async def handler(ctx, member):
        received.append(member)

    callback = bot.tree.add_command.call_args[0][0].callback
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    member = MagicMock(spec=discord.Member)
    await callback(interaction, member)
    assert received == [member]


def test_user_command_guild_scoped(bot):
    @bot.user_command(name="X", guild_id=99999)
    async def handler(ctx, member):
        pass

    _, kwargs = bot.tree.add_command.call_args
    assert kwargs.get("guild") is not None
    assert kwargs["guild"].id == 99999


# ── message_command ───────────────────────────────────────────────────────────

def test_message_command_registers_context_menu(bot):
    @bot.message_command(name="Quote")
    async def quote(ctx, message):
        pass

    bot.tree.add_command.assert_called_once()
    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "Quote"


def test_message_command_defaults_name_to_function_name(bot):
    @bot.message_command()
    async def save_message(ctx, message):
        pass

    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "save_message"


def test_message_command_returns_original_function(bot):
    async def handler(ctx, message):
        pass

    result = bot.message_command(name="Y")(handler)
    assert result is handler


async def test_message_command_invokes_handler_with_target(bot):
    received = []

    @bot.message_command(name="Archive")
    async def handler(ctx, message):
        received.append(message)

    callback = bot.tree.add_command.call_args[0][0].callback
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    msg = MagicMock(spec=discord.Message)
    await callback(interaction, msg)
    assert received == [msg]


async def test_context_menu_runs_middleware(bot):
    order = []

    async def mw(ctx, proceed):
        order.append("before")
        await proceed()
        order.append("after")

    bot.use(mw)

    @bot.user_command(name="MW Test")
    async def handler(ctx, member):
        order.append("handler")

    callback = bot.tree.add_command.call_args[0][0].callback
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    await callback(interaction, MagicMock(spec=discord.Member))
    assert order == ["before", "handler", "after"]


# ── background tasks ──────────────────────────────────────────────────────────

def test_add_plugin_does_not_start_tasks_before_ready(bot):
    class MyPlugin(Plugin):
        @task(seconds=1)
        async def my_task(self):
            pass

    plugin = MyPlugin()
    bot.add_plugin(plugin)
    assert id(plugin) not in bot._task_handles


async def test_start_plugin_tasks_creates_asyncio_tasks(bot):
    class MyPlugin(Plugin):
        @task(seconds=100)
        async def my_task(self):
            pass

    plugin = MyPlugin()
    plugin._bot = bot
    bot._plugins.append(plugin)
    bot._start_plugin_tasks(plugin)

    assert id(plugin) in bot._task_handles
    assert len(bot._task_handles[id(plugin)]) == 1

    for handle in bot._task_handles[id(plugin)]:
        handle.cancel()
        try:
            await handle
        except asyncio.CancelledError:
            pass


async def test_remove_plugin_cancels_tasks(bot):
    class MyPlugin(Plugin):
        @task(seconds=100)
        async def my_task(self):
            pass

    plugin = MyPlugin()
    plugin._bot = bot
    bot._plugins.append(plugin)
    bot._start_plugin_tasks(plugin)

    assert id(plugin) in bot._task_handles
    await bot.remove_plugin(plugin)
    assert id(plugin) not in bot._task_handles


# ── set_status streaming ──────────────────────────────────────────────────────

async def test_set_status_streaming(bot):
    bot.change_presence = AsyncMock()
    await bot.set_status("online", activity="live now", activity_type="streaming")
    call_kwargs = bot.change_presence.call_args.kwargs
    activity = call_kwargs["activity"]
    assert isinstance(activity, discord.Streaming)
    assert activity.name == "live now"


# ── _GuildMixin ───────────────────────────────────────────────────────────────

async def test_fetch_guild_returns_cached(bot):
    guild = MagicMock(spec=discord.Guild)
    bot.get_guild = MagicMock(return_value=guild)
    result = await bot.fetch_guild(123)
    assert result is guild
    bot.get_guild.assert_called_once_with(123)


async def test_fetch_channel_returns_cached(bot):
    channel = MagicMock(spec=discord.TextChannel)
    bot.get_channel = MagicMock(return_value=channel)
    result = await bot.fetch_channel(456)
    assert result is channel


async def test_fetch_channel_falls_back_to_api(bot):
    channel = MagicMock(spec=discord.TextChannel)
    bot.get_channel = MagicMock(return_value=None)
    with patch.object(discord.Client, "fetch_channel", new=AsyncMock(return_value=channel)):
        result = await bot.fetch_channel(456)
    assert result is channel


async def test_leave_guild_calls_guild_leave(bot):
    guild = MagicMock(spec=discord.Guild)
    guild.leave = AsyncMock()
    bot.get_guild = MagicMock(return_value=guild)
    await bot.leave_guild(123)
    guild.leave.assert_called_once()


async def test_leave_guild_raises_when_not_in_guild(bot):
    bot.get_guild = MagicMock(return_value=None)
    with pytest.raises(RuntimeError, match="not in guild"):
        await bot.leave_guild(999)


async def test_create_channel_text(bot):
    guild = MagicMock(spec=discord.Guild)
    channel = MagicMock(spec=discord.TextChannel)
    guild.create_text_channel = AsyncMock(return_value=channel)
    bot.get_guild = MagicMock(return_value=guild)
    result = await bot.create_channel(123, "general")
    assert result is channel
    guild.create_text_channel.assert_called_once_with(
        "general", category=None, topic=None, reason=None
    )


async def test_create_channel_voice(bot):
    guild = MagicMock(spec=discord.Guild)
    channel = MagicMock(spec=discord.VoiceChannel)
    guild.create_voice_channel = AsyncMock(return_value=channel)
    bot.get_guild = MagicMock(return_value=guild)
    result = await bot.create_channel(123, "voice-chat", channel_type="voice")
    assert result is channel


async def test_create_channel_invalid_type_raises(bot):
    guild = MagicMock(spec=discord.Guild)
    bot.get_guild = MagicMock(return_value=guild)
    with pytest.raises(ValueError, match="Unknown channel_type"):
        await bot.create_channel(123, "x", channel_type="invalid")


async def test_create_channel_raises_when_guild_not_found(bot):
    bot.get_guild = MagicMock(return_value=None)
    with pytest.raises(RuntimeError, match="not in guild"):
        await bot.create_channel(999, "test")


async def test_delete_channel(bot):
    channel = MagicMock()
    channel.delete = AsyncMock()
    bot.get_channel = MagicMock(return_value=channel)
    await bot.delete_channel(456)
    channel.delete.assert_called_once_with(reason=None)


async def test_delete_channel_fetches_when_not_cached(bot):
    channel = MagicMock()
    channel.delete = AsyncMock()
    bot.get_channel = MagicMock(return_value=None)
    with patch.object(discord.Client, "fetch_channel", new=AsyncMock(return_value=channel)):
        await bot.delete_channel(456, reason="cleanup")
    channel.delete.assert_called_once_with(reason="cleanup")


async def test_send_webhook_creates_and_sends(bot):
    channel = MagicMock(spec=discord.TextChannel)
    webhook = MagicMock(spec=discord.Webhook)
    webhook.send = AsyncMock()
    channel.create_webhook = AsyncMock(return_value=webhook)
    bot.get_channel = MagicMock(return_value=channel)
    await bot.send_webhook(111, "hello")
    channel.create_webhook.assert_called_once_with(name="Webhook")
    webhook.send.assert_called_once_with("hello", username=None, avatar_url=None, embed=None)


async def test_send_webhook_reuses_cached_webhook(bot):
    webhook = MagicMock(spec=discord.Webhook)
    webhook.send = AsyncMock()
    bot._webhooks[111] = webhook
    await bot.send_webhook(111, "hello again")
    webhook.send.assert_called_once()


async def test_create_emoji(bot):
    guild = MagicMock(spec=discord.Guild)
    emoji = MagicMock(spec=discord.Emoji)
    guild.create_custom_emoji = AsyncMock(return_value=emoji)
    bot.get_guild = MagicMock(return_value=guild)
    with patch("builtins.open", MagicMock(return_value=MagicMock(
        __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"imgdata"))),
        __exit__=MagicMock(return_value=False),
    ))):
        result = await bot.create_emoji(123, "cool", "cool.png")
    assert result is emoji
    guild.create_custom_emoji.assert_called_once_with(name="cool", image=b"imgdata", reason=None)


async def test_delete_emoji(bot):
    guild = MagicMock(spec=discord.Guild)
    emoji = MagicMock(spec=discord.Emoji)
    emoji.delete = AsyncMock()
    guild.fetch_emoji = AsyncMock(return_value=emoji)
    bot.get_guild = MagicMock(return_value=guild)
    await bot.delete_emoji(123, 999)
    guild.fetch_emoji.assert_called_once_with(999)
    emoji.delete.assert_called_once_with(reason=None)


async def test_fetch_guild_emojis(bot):
    guild = MagicMock(spec=discord.Guild)
    e1 = MagicMock(spec=discord.Emoji)
    e2 = MagicMock(spec=discord.Emoji)
    guild.fetch_emojis = AsyncMock(return_value=[e1, e2])
    bot.get_guild = MagicMock(return_value=guild)
    result = await bot.fetch_guild_emojis(123)
    assert result == [e1, e2]


# ── @bot.on_error ─────────────────────────────────────────────────────────────

async def test_on_error_registers_handler(bot):
    async def handler(ctx, error):
        pass
    bot.on_error(handler)
    assert bot._error_handler is handler


async def test_on_error_as_decorator(bot):
    @bot.on_error
    async def handler(ctx, error):
        pass
    assert bot._error_handler is handler


async def test_on_error_called_on_command_exception(bot):
    errors_seen = []

    @bot.on_error
    async def handler(ctx, error):
        errors_seen.append(error)

    boom = ValueError("boom")

    @bot.slash(description="test")
    async def bad_cmd(ctx):
        raise boom

    cmd_obj = bot.tree.add_command.call_args_list[-1][0][0]
    mock_interaction = MagicMock()
    mock_interaction.response.send_message = AsyncMock()
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()
    mock_interaction.command = MagicMock()
    mock_interaction.command.name = "bad_cmd"
    mock_interaction.guild = None
    mock_interaction.user = MagicMock()
    mock_interaction.channel = MagicMock()
    mock_interaction.client = MagicMock()
    await cmd_obj.callback(mock_interaction)
    assert errors_seen == [boom]


# ── reload_plugin ─────────────────────────────────────────────────────────────

async def test_reload_plugin_calls_on_unload_then_on_load(bot):
    order = []

    class _OrderedPlugin(Plugin):
        async def on_unload(self): order.append("unload")
        async def on_load(self): order.append("load")

    plugin = _OrderedPlugin()
    bot._plugins = [plugin]
    await bot.reload_plugin("_OrderedPlugin")
    assert order == ["unload", "load"]


async def test_reload_plugin_unknown_raises(bot):
    with pytest.raises(ValueError, match="No plugin named"):
        await bot.reload_plugin("DoesNotExist")


async def test_reload_plugin_preserves_instance(bot):
    class _SimplePlugin(Plugin):
        async def on_load(self): pass
        async def on_unload(self): pass

    plugin = _SimplePlugin()
    bot._plugins = [plugin]
    await bot.reload_plugin("_SimplePlugin")
    assert bot._plugins[0] is plugin


# ── aliases ───────────────────────────────────────────────────────────────────

def test_slash_aliases_register_extra_commands(bot):
    @bot.slash(description="help", aliases=["halp", "commands"])
    async def help_cmd(ctx):
        pass
    assert bot.tree.add_command.call_count == 3


def test_slash_no_aliases_registers_one_command(bot):
    bot.tree.add_command.reset_mock()
    @bot.slash(description="ping")
    async def ping(ctx):
        pass
    assert bot.tree.add_command.call_count == 1


def test_slash_alias_names_registered(bot):
    bot.tree.add_command.reset_mock()
    @bot.slash(description="help", aliases=["halp"])
    async def help_cmd(ctx):
        pass
    names = [call[0][0].name for call in bot.tree.add_command.call_args_list]
    assert "help_cmd" in names
    assert "halp" in names
