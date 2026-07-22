"""Comprehensive tests for WelcomePlugin.

Covers slash commands, event handlers, message templating, guild isolation,
and error containment. Does NOT duplicate TestWelcomePluginConfig from
test_plugin_commands.py (config CRUD and Forbidden-send tests live there).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins.welcome import WelcomePlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plugin(tmp_path) -> WelcomePlugin:
    return WelcomePlugin(data_dir=str(tmp_path / "welcome"))


def _make_ctx(
    *,
    guild_id: int = 100,
    user_id: int = 1,
    with_guild: bool = True,
    user_mention: str = "<@1>",
) -> MagicMock:
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.user.mention = user_mention
    ctx.user.__str__ = MagicMock(return_value=f"User#{user_id}")
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default

    if with_guild:
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = f"Guild-{guild_id}"
        guild.get_channel = MagicMock(return_value=None)
        guild.get_role = MagicMock(return_value=None)
        ctx.guild = guild
        ctx.guild_id = guild_id
    else:
        ctx.guild = None
        ctx.guild_id = None

    return ctx


def _make_member(
    *,
    guild_id: int = 100,
    guild_name: str = "TestGuild",
    member_count: int = 10,
    mention: str = "<@42>",
    channel: MagicMock | None = None,
    auto_role_id: int | None = None,
) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = guild_name
    guild.member_count = member_count
    guild.get_channel = MagicMock(return_value=channel)
    guild.get_role = MagicMock(return_value=None)

    member = MagicMock(spec=discord.Member)
    member.guild = guild
    member.mention = mention
    member.display_avatar = MagicMock()
    member.display_avatar.url = "https://cdn.example/avatar.png"
    member.add_roles = AsyncMock()
    return member


def _text_channel() -> MagicMock:
    ch = MagicMock(spec=discord.TextChannel)
    ch.id = 999
    ch.mention = "<#999>"
    ch.send = AsyncMock()
    return ch


# ---------------------------------------------------------------------------
# Slash commands — set_welcome_channel
# ---------------------------------------------------------------------------

class TestSetWelcomeChannel:
    @pytest.mark.asyncio
    async def test_sets_channel_in_config(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=10)
        channel = _text_channel()

        await plugin.set_welcome_channel(ctx, channel)

        cfg = plugin._read_config(10)
        assert cfg["welcome_channel"] == channel.id
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_responds_with_channel_mention(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=10)
        channel = _text_channel()

        await plugin.set_welcome_channel(ctx, channel)

        text = ctx.respond.call_args[0][0]
        assert "<#999>" in text

    @pytest.mark.asyncio
    async def test_dm_context_bails_out(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(with_guild=False)
        channel = _text_channel()

        await plugin.set_welcome_channel(ctx, channel)

        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True
        # Nothing should have been written
        cfg = plugin._read_config(0)
        assert "welcome_channel" not in cfg

    @pytest.mark.asyncio
    async def test_overwrite_existing_channel(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=10)
        ch1 = _text_channel()
        ch1.id = 11
        await plugin.set_welcome_channel(ctx, ch1)

        ch2 = _text_channel()
        ch2.id = 22
        ctx2 = _make_ctx(guild_id=10)
        await plugin.set_welcome_channel(ctx2, ch2)

        cfg = plugin._read_config(10)
        assert cfg["welcome_channel"] == 22


# ---------------------------------------------------------------------------
# Slash commands — set_goodbye_channel
# ---------------------------------------------------------------------------

class TestSetGoodbyeChannel:
    @pytest.mark.asyncio
    async def test_sets_channel_in_config(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=20)
        channel = _text_channel()

        await plugin.set_goodbye_channel(ctx, channel)

        cfg = plugin._read_config(20)
        assert cfg["goodbye_channel"] == channel.id
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_context_bails_out(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(with_guild=False)
        channel = _text_channel()

        await plugin.set_goodbye_channel(ctx, channel)

        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True


# ---------------------------------------------------------------------------
# Slash commands — set_auto_role
# ---------------------------------------------------------------------------

class TestSetAutoRole:
    @pytest.mark.asyncio
    async def test_stores_role_id(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=30)
        role = MagicMock(spec=discord.Role)
        role.id = 777
        role.mention = "<@&777>"

        await plugin.set_auto_role(ctx, role)

        cfg = plugin._read_config(30)
        assert cfg["auto_role"] == 777
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_context_bails_out(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(with_guild=False)
        role = MagicMock(spec=discord.Role)
        role.id = 888

        await plugin.set_auto_role(ctx, role)

        assert ctx.respond.call_args[1].get("ephemeral") is True
        cfg = plugin._read_config(0)
        assert "auto_role" not in cfg


# ---------------------------------------------------------------------------
# Slash commands — set_welcome_message
# ---------------------------------------------------------------------------

class TestSetWelcomeMessage:
    @pytest.mark.asyncio
    async def test_valid_template_stored(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=40, user_mention="<@1>")

        await plugin.set_welcome_message(ctx, "Hey {user}, welcome to {server}!")

        cfg = plugin._read_config(40)
        assert cfg["welcome_message"] == "Hey {user}, welcome to {server}!"
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_in_response(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=40, user_mention="<@1>")
        ctx.guild.name = "Guild-40"

        await plugin.set_welcome_message(ctx, "Hi {user} from {server}")

        text = ctx.respond.call_args[0][0]
        assert "<@1>" in text
        assert "Guild-40" in text

    @pytest.mark.asyncio
    async def test_invalid_placeholder_rejected(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=40)

        await plugin.set_welcome_message(ctx, "Hello {unknown}!")

        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True
        cfg = plugin._read_config(40)
        assert "welcome_message" not in cfg

    @pytest.mark.asyncio
    async def test_dm_context_bails_out(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(with_guild=False)

        await plugin.set_welcome_message(ctx, "Hello {user}!")

        assert ctx.respond.call_args[1].get("ephemeral") is True


# ---------------------------------------------------------------------------
# Slash commands — set_goodbye_message
# ---------------------------------------------------------------------------

class TestSetGoodbyeMessage:
    @pytest.mark.asyncio
    async def test_valid_template_stored(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=50)

        await plugin.set_goodbye_message(ctx, "Bye {user} from {server}!")

        cfg = plugin._read_config(50)
        assert cfg["goodbye_message"] == "Bye {user} from {server}!"

    @pytest.mark.asyncio
    async def test_invalid_placeholder_rejected(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=50)

        await plugin.set_goodbye_message(ctx, "Bye {badkey}!")

        assert ctx.respond.call_args[1].get("ephemeral") is True
        cfg = plugin._read_config(50)
        assert "goodbye_message" not in cfg


# ---------------------------------------------------------------------------
# Slash commands — welcome_config
# ---------------------------------------------------------------------------

class TestWelcomeConfig:
    @pytest.mark.asyncio
    async def test_shows_not_set_when_unconfigured(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(guild_id=60)

        await plugin.welcome_config(ctx)

        ctx.respond.assert_called_once()
        embed = ctx.respond.call_args[1].get("embed")
        assert embed is not None
        field_values = [f.value for f in embed.fields]
        assert any("not set" in v for v in field_values)

    @pytest.mark.asyncio
    async def test_shows_configured_values(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        plugin._write_config(60, {
            "welcome_channel": 111,
            "goodbye_channel": 222,
            "auto_role": 333,
            "welcome_message": "Custom welcome",
        })
        ctx = _make_ctx(guild_id=60)
        # Wire up get_channel/get_role so channel_reference / role_reference work
        ctx.guild.get_channel = MagicMock(return_value=None)
        ctx.guild.get_role = MagicMock(return_value=None)

        await plugin.welcome_config(ctx)

        embed = ctx.respond.call_args[1].get("embed")
        field_values = [f.value for f in embed.fields]
        all_text = " ".join(field_values)
        assert "Custom welcome" in all_text

    @pytest.mark.asyncio
    async def test_dm_context_bails_out(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _make_ctx(with_guild=False)

        await plugin.welcome_config(ctx)

        assert ctx.respond.call_args[1].get("ephemeral") is True


# ---------------------------------------------------------------------------
# Event handler — on_member_join: welcome message
# ---------------------------------------------------------------------------

class TestOnMemberJoinWelcome:
    @pytest.mark.asyncio
    async def test_sends_welcome_when_channel_configured(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = _make_member(guild_id=100, channel=channel)
        member.guild.get_channel = MagicMock(return_value=channel)
        plugin._write_config(100, {"welcome_channel": channel.id})

        await plugin._on_member_join(member)

        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_send_when_no_channel_configured(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = _make_member(guild_id=100, channel=None)
        # No config written — welcome_channel absent

        await plugin._on_member_join(member)

        channel.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_send_when_channel_not_text_channel(self, tmp_path) -> None:
        """A non-TextChannel stored in config must be silently skipped."""
        plugin = _plugin(tmp_path)
        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.id = 888
        member = _make_member(guild_id=100)
        member.guild.get_channel = MagicMock(return_value=voice_channel)
        plugin._write_config(100, {"welcome_channel": 888})

        await plugin._on_member_join(member)
        # VoiceChannel doesn't pass isinstance(..., TextChannel) — no send expected

    @pytest.mark.asyncio
    async def test_default_message_contains_user_and_server(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = _make_member(
            guild_id=100,
            guild_name="AwesomeServer",
            mention="<@99>",
            channel=channel,
        )
        member.guild.get_channel = MagicMock(return_value=channel)
        plugin._write_config(100, {"welcome_channel": channel.id})

        await plugin._on_member_join(member)

        embed = channel.send.call_args[1]["embed"]
        assert "<@99>" in embed.description
        assert "AwesomeServer" in embed.description

    @pytest.mark.asyncio
    async def test_custom_message_template_resolved(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = _make_member(
            guild_id=100,
            guild_name="Realm",
            mention="<@7>",
            channel=channel,
        )
        member.guild.get_channel = MagicMock(return_value=channel)
        plugin._write_config(100, {
            "welcome_channel": channel.id,
            "welcome_message": "Greetings {user}! You joined {server}.",
        })

        await plugin._on_member_join(member)

        embed = channel.send.call_args[1]["embed"]
        assert "Greetings <@7>!" in embed.description
        assert "You joined Realm." in embed.description

    @pytest.mark.asyncio
    async def test_http_exception_does_not_escape(self, tmp_path) -> None:
        """HTTPException (not just Forbidden) must be absorbed by send_safe."""
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        channel.send = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "server error")
        )
        member = _make_member(guild_id=100, channel=channel)
        member.guild.get_channel = MagicMock(return_value=channel)
        plugin._write_config(100, {"welcome_channel": channel.id})

        try:
            await plugin._on_member_join(member)
        except discord.HTTPException:
            pytest.fail("HTTPException escaped _on_member_join")

        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_embed_footer_shows_member_count(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = _make_member(guild_id=100, member_count=42, channel=channel)
        member.guild.get_channel = MagicMock(return_value=channel)
        plugin._write_config(100, {"welcome_channel": channel.id})

        await plugin._on_member_join(member)

        embed = channel.send.call_args[1]["embed"]
        assert "42" in embed.footer.text


# ---------------------------------------------------------------------------
# Event handler — on_member_join: auto-role
# ---------------------------------------------------------------------------

class TestOnMemberJoinAutoRole:
    @pytest.mark.asyncio
    async def test_assigns_auto_role_when_configured(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        role = MagicMock(spec=discord.Role)
        role.id = 555
        member = _make_member(guild_id=100)
        member.guild.get_role = MagicMock(return_value=role)
        plugin._write_config(100, {"auto_role": 555})

        await plugin._on_member_join(member)

        member.add_roles.assert_awaited_once_with(role, reason="WelcomePlugin auto-role")

    @pytest.mark.asyncio
    async def test_no_auto_role_when_not_configured(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        member = _make_member(guild_id=100)
        # No auto_role in config

        await plugin._on_member_join(member)

        member.add_roles.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auto_role_missing_from_guild_skipped(self, tmp_path) -> None:
        """If the stored role ID no longer exists in the guild, no add_roles call."""
        plugin = _plugin(tmp_path)
        member = _make_member(guild_id=100)
        member.guild.get_role = MagicMock(return_value=None)
        plugin._write_config(100, {"auto_role": 999})

        await plugin._on_member_join(member)

        member.add_roles.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auto_role_http_exception_does_not_escape(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        role = MagicMock(spec=discord.Role)
        role.id = 555
        member = _make_member(guild_id=100)
        member.guild.get_role = MagicMock(return_value=role)
        member.add_roles = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "missing perms")
        )
        plugin._write_config(100, {"auto_role": 555})

        try:
            await plugin._on_member_join(member)
        except discord.HTTPException:
            pytest.fail("HTTPException from add_roles escaped _on_member_join")


# ---------------------------------------------------------------------------
# Event handler — on_member_remove (goodbye)
# ---------------------------------------------------------------------------

class TestOnMemberRemove:
    @pytest.mark.asyncio
    async def test_sends_goodbye_when_channel_configured(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = MagicMock(spec=discord.Member)
        member.guild = MagicMock(spec=discord.Guild)
        member.guild.id = 100
        member.guild.name = "TestGuild"
        member.guild.get_channel = MagicMock(return_value=channel)
        member.__str__ = MagicMock(return_value="SomeUser#1234")
        plugin._write_config(100, {"goodbye_channel": channel.id})

        await plugin._on_member_remove(member)

        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_send_when_no_goodbye_channel(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = MagicMock(spec=discord.Member)
        member.guild = MagicMock(spec=discord.Guild)
        member.guild.id = 100
        member.guild.get_channel = MagicMock(return_value=channel)
        # No goodbye_channel in config

        await plugin._on_member_remove(member)

        channel.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_custom_goodbye_template_resolved(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        member = MagicMock(spec=discord.Member)
        member.guild = MagicMock(spec=discord.Guild)
        member.guild.id = 100
        member.guild.name = "Realm"
        member.guild.get_channel = MagicMock(return_value=channel)
        member.__str__ = MagicMock(return_value="Leaver#0001")
        plugin._write_config(100, {
            "goodbye_channel": channel.id,
            "goodbye_message": "Farewell {user} from {server}.",
        })

        await plugin._on_member_remove(member)

        embed = channel.send.call_args[1]["embed"]
        assert "Leaver#0001" in embed.description
        assert "Realm" in embed.description

    @pytest.mark.asyncio
    async def test_http_exception_does_not_escape(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel = _text_channel()
        channel.send = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "server error")
        )
        member = MagicMock(spec=discord.Member)
        member.guild = MagicMock(spec=discord.Guild)
        member.guild.id = 100
        member.guild.name = "G"
        member.guild.get_channel = MagicMock(return_value=channel)
        member.__str__ = MagicMock(return_value="User#0")
        plugin._write_config(100, {"goodbye_channel": channel.id})

        try:
            await plugin._on_member_remove(member)
        except discord.HTTPException:
            pytest.fail("HTTPException escaped _on_member_remove")


# ---------------------------------------------------------------------------
# Guild isolation
# ---------------------------------------------------------------------------

class TestGuildIsolation:
    @pytest.mark.asyncio
    async def test_welcome_channel_isolated_between_guilds(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        channel_a = _text_channel()
        channel_a.id = 111

        plugin._write_config(1, {"welcome_channel": channel_a.id})

        # Guild B has no config — its member join should send nothing
        channel_b = _text_channel()
        channel_b.id = 222
        member_b = _make_member(guild_id=2, channel=channel_b)
        member_b.guild.get_channel = MagicMock(return_value=channel_b)

        await plugin._on_member_join(member_b)

        channel_a.send.assert_not_awaited()
        channel_b.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_set_channel_command_isolated(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ch = _text_channel()

        ctx_a = _make_ctx(guild_id=1)
        await plugin.set_welcome_channel(ctx_a, ch)

        cfg_b = plugin._read_config(2)
        assert "welcome_channel" not in cfg_b

    @pytest.mark.asyncio
    async def test_auto_role_isolated_between_guilds(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        plugin._write_config(1, {"auto_role": 123})

        member2 = _make_member(guild_id=2)
        member2.guild.get_role = MagicMock(return_value=None)

        await plugin._on_member_join(member2)

        member2.add_roles.assert_not_awaited()
