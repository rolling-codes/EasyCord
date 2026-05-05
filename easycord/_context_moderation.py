"""Moderation and role-management helpers for Context."""
from __future__ import annotations

import datetime

import discord


class ModerationMixin:
    """Mixin that adds moderation and role-management methods to Context.

    Requires ``self.guild``, ``self.user``, and ``self.respond()`` from BaseContext.
    """

    # ── Moderation ────────────────────────────────────────────

    async def kick(self, member: discord.Member, *, reason: str | None = None) -> None:
        """Kick a member from the server."""
        await member.kick(reason=reason)

    async def ban(
        self,
        member: discord.Member,
        *,
        reason: str | None = None,
        delete_message_days: int = 0,
    ) -> None:
        """Ban a member from the server.

        Parameters
        ----------
        delete_message_days:
            Number of days of the member's messages to delete (0–7).
        """
        await member.ban(reason=reason, delete_message_days=delete_message_days)

    async def timeout(
        self,
        member: discord.Member,
        duration: float,
        *,
        reason: str | None = None,
    ) -> None:
        """Temporarily mute a member. ``duration`` is in seconds."""
        until = discord.utils.utcnow() + datetime.timedelta(seconds=duration)
        await member.timeout(until, reason=reason)

    async def unban(self, user: discord.User, *, reason: str | None = None) -> None:
        """Unban a user from the server by their User object."""
        if self.guild is None:  # type: ignore[attr-defined]
            raise RuntimeError("unban requires a guild context")
        await self.guild.unban(user, reason=reason)  # type: ignore[attr-defined]

    async def set_nickname(
        self,
        member: discord.Member,
        nickname: str | None,
        *,
        reason: str | None = None,
    ) -> None:
        """Set or clear a member's server nickname. Pass ``None`` to reset to default."""
        await member.edit(nick=nickname, reason=reason)

    async def move_member(
        self,
        member: discord.Member,
        channel_id: int | None,
        *,
        reason: str | None = None,
    ) -> None:
        """Move a member to a voice channel by ID, or disconnect them (pass ``None``).

        Accepts both ``VoiceChannel`` and ``StageChannel`` targets.
        """
        if channel_id is None:
            await member.edit(voice_channel=None, reason=reason)
        else:
            channel = self.interaction.client.get_channel(channel_id)  # type: ignore[attr-defined]
            if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                raise ValueError(f"Channel {channel_id} is not a voice or stage channel, or was not found")
            await member.edit(voice_channel=channel, reason=reason)

    async def fetch_bans(self, limit: int | None = None) -> list[discord.BanEntry]:
        """Return a list of ban entries for the current guild.

        Parameters
        ----------
        limit:
            Maximum number of entries to fetch. ``None`` fetches all bans.
        """
        if self.guild is None:  # type: ignore[attr-defined]
            raise RuntimeError("fetch_bans requires a guild context")
        return [entry async for entry in self.guild.bans(limit=limit)]  # type: ignore[attr-defined]

    async def purge(self, limit: int = 10) -> int:
        """Bulk-delete recent messages in the current channel or thread. Returns count deleted."""
        if not isinstance(self.channel, (discord.TextChannel, discord.Thread)):  # type: ignore[attr-defined]
            raise RuntimeError("purge can only be used in a text channel or thread")
        deleted = await self.channel.purge(limit=limit)  # type: ignore[attr-defined]
        return len(deleted)

    # ── Role management ───────────────────────────────────────

    def _resolve_role(self, role_id: int) -> discord.Role:
        """Return a Role from this guild by ID, raising clear errors if not found."""
        if self.guild is None:  # type: ignore[attr-defined]
            raise RuntimeError("This method requires a guild context")
        role = self.guild.get_role(role_id)  # type: ignore[attr-defined]
        if role is None:
            raise ValueError(f"Role {role_id} not found in this server")
        return role

    async def add_role(
        self,
        member: discord.Member,
        role_id: int,
        *,
        reason: str | None = None,
    ) -> None:
        """Add a role to a member by role ID."""
        await member.add_roles(self._resolve_role(role_id), reason=reason)

    async def remove_role(
        self,
        member: discord.Member,
        role_id: int,
        *,
        reason: str | None = None,
    ) -> None:
        """Remove a role from a member by role ID."""
        await member.remove_roles(self._resolve_role(role_id), reason=reason)

    async def create_role(
        self,
        name: str,
        *,
        color: discord.Color = discord.Color.default(),
        hoist: bool = False,
        mentionable: bool = False,
        reason: str | None = None,
    ) -> discord.Role:
        """Create a new role in the server and return it."""
        if self.guild is None:  # type: ignore[attr-defined]
            raise RuntimeError("create_role requires a guild context")
        return await self.guild.create_role(  # type: ignore[attr-defined]
            name=name, color=color, hoist=hoist, mentionable=mentionable, reason=reason
        )

    async def delete_role(self, role_id: int, *, reason: str | None = None) -> None:
        """Delete a role from the server by role ID."""
        await self._resolve_role(role_id).delete(reason=reason)
