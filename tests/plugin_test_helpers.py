"""Shared Discord mock helpers for plugin offline tests.

These helpers avoid duplicating fake-Discord construction across
test_economy.py, test_moderation.py, test_polls.py, test_welcome.py
and any future plugin test modules.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord


def make_ctx(
    *,
    guild_id: int | None = 100,
    user_id: int = 1,
    is_admin: bool = False,
    user_mention: str | None = None,
    guild_name: str | None = None,
    channel: MagicMock | None = None,
    sendable_channel: bool = True,
) -> MagicMock:
    """Return a minimal Context mock suitable for plugin slash-command tests.

    Args:
        guild_id: Guild ID; pass ``None`` for DM context (ctx.guild = None).
        user_id: Invoking user's ID.
        is_admin: Sets ``ctx.is_admin`` and ``ctx.member.guild_permissions.administrator``.
        user_mention: Override the default ``<@{user_id}>`` mention string.
        guild_name: Override the default ``Guild-{guild_id}`` name.
        channel: Pre-built channel mock; defaults to a ``TextChannel`` if sendable_channel
            is True, otherwise a ``CategoryChannel``.
        sendable_channel: When True (default) and *channel* is None, attaches a
            ``discord.TextChannel`` mock with an async ``.send``.
    """
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    ctx.t = MagicMock(
        side_effect=lambda key, *, default=None, **kw: (
            (default or key).format(**kw) if kw else (default or key)
        )
    )

    mention = user_mention or f"<@{user_id}>"
    user = MagicMock()
    user.id = user_id
    user.mention = mention
    user.__str__ = MagicMock(return_value=f"User#{user_id}")
    ctx.user = user

    perms = MagicMock(spec=discord.Permissions)
    perms.administrator = is_admin
    perms.kick_members = is_admin
    perms.ban_members = is_admin
    perms.manage_roles = is_admin
    perms.moderate_members = is_admin
    perms.manage_guild = is_admin

    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.mention = mention
    member.guild_permissions = perms
    member.roles = []
    ctx.member = member
    ctx.is_admin = is_admin

    if guild_id is not None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = guild_name or f"Guild-{guild_id}"
        guild.get_channel = MagicMock(return_value=None)
        guild.get_role = MagicMock(return_value=None)
        guild.get_member = MagicMock(return_value=None)
        guild.roles = []
        ctx.guild = guild
        ctx.guild_id = guild_id
    else:
        ctx.guild = None
        ctx.guild_id = None

    if channel is not None:
        ctx.channel = channel
    elif sendable_channel:
        ch = MagicMock(spec=discord.TextChannel)
        ch.id = 55
        ch.mention = "<#55>"
        ch.send = AsyncMock()
        ctx.channel = ch
    else:
        ctx.channel = MagicMock(spec=discord.CategoryChannel)

    fake_msg = MagicMock()
    fake_msg.id = 900000000000000001
    fake_msg.edit = AsyncMock()
    ctx.interaction = MagicMock()
    ctx.interaction.original_response = AsyncMock(return_value=fake_msg)

    return ctx


def make_member(
    *,
    guild_id: int = 100,
    guild_name: str = "TestGuild",
    member_count: int = 10,
    user_id: int = 42,
    mention: str | None = None,
    channel: MagicMock | None = None,
) -> MagicMock:
    """Return a ``discord.Member`` mock for event-handler tests (e.g. on_member_join)."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = guild_name
    guild.member_count = member_count
    guild.get_channel = MagicMock(return_value=channel)
    guild.get_role = MagicMock(return_value=None)

    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.guild = guild
    member.mention = mention or f"<@{user_id}>"
    member.display_avatar = MagicMock()
    member.display_avatar.url = "https://cdn.example/avatar.png"
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    member.roles = []
    return member


def make_target_user(user_id: int = 999) -> MagicMock:
    """Return a ``discord.User`` mock for moderation target tests."""
    target = MagicMock(spec=discord.User)
    target.id = user_id
    target.name = f"target-{user_id}"
    target.discriminator = "0000"
    target.mention = f"<@{user_id}>"
    return target


def make_target_member(user_id: int = 999) -> MagicMock:
    """Return a ``discord.Member`` mock for moderation target tests."""
    target = MagicMock(spec=discord.Member)
    target.id = user_id
    target.name = f"target-{user_id}"
    target.discriminator = "0000"
    target.mention = f"<@{user_id}>"
    target.kick = AsyncMock()
    target.ban = AsyncMock()
    target.timeout = AsyncMock()
    target.add_roles = AsyncMock()
    target.remove_roles = AsyncMock()
    target.roles = []
    target.guild_permissions = MagicMock(spec=discord.Permissions)
    target.guild_permissions.administrator = False
    return target


def make_text_channel(channel_id: int = 999) -> MagicMock:
    """Return a ``discord.TextChannel`` mock with an async ``.send``."""
    ch = MagicMock(spec=discord.TextChannel)
    ch.id = channel_id
    ch.mention = f"<#{channel_id}>"
    ch.send = AsyncMock()
    return ch


def make_discord_user(user_id: int = 42) -> MagicMock:
    """Return a plain ``discord.User`` mock (not a guild member)."""
    u = MagicMock(spec=discord.User)
    u.id = user_id
    u.mention = f"<@{user_id}>"
    return u
