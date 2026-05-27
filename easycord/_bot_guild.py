"""Guild, channel, webhook, and emoji management helpers for Bot."""
from __future__ import annotations

from pathlib import Path

import discord


class _GuildMixin:
    """Mixin: guild/channel/webhook/emoji management methods."""

    # ── Guild lookup ──────────────────────────────────────────

    async def fetch_guild(self, guild_id: int) -> discord.Guild:
        """Return a guild by ID, checking the cache first.

        Raises ``discord.NotFound`` if the bot is not in the guild.
        """
        return self.get_guild(guild_id) or await super().fetch_guild(guild_id)  # type: ignore[misc]

    async def fetch_channel(self, channel_id: int) -> discord.abc.GuildChannel:
        """Return a channel by ID, checking the cache first.

        Raises ``discord.NotFound`` / ``discord.Forbidden`` on failure.
        """
        return self.get_channel(channel_id) or await super().fetch_channel(channel_id)  # type: ignore[misc]

    # ── Guild management ──────────────────────────────────────

    async def leave_guild(self, guild_id: int) -> None:
        """Make the bot leave a guild.

        Raises ``RuntimeError`` if the bot is not in the guild.
        """
        guild = self.get_guild(guild_id)
        if guild is None:
            raise RuntimeError(f"Bot is not in guild {guild_id}")
        await guild.leave()

    # ── Channel management ────────────────────────────────────

    async def create_channel(
        self,
        guild_id: int,
        name: str,
        *,
        channel_type: str = "text",
        category_id: int | None = None,
        topic: str | None = None,
        reason: str | None = None,
    ) -> discord.abc.GuildChannel:
        """Create a channel in a guild and return it.

        ``channel_type`` must be one of ``"text"``, ``"voice"``, ``"category"``,
        ``"stage"``, or ``"forum"``.

        Raises ``RuntimeError`` if the bot is not in the guild.
        Raises ``ValueError`` for an unrecognised ``channel_type``.
        """
        guild = self.get_guild(guild_id)
        if guild is None:
            raise RuntimeError(f"Bot is not in guild {guild_id}")

        category: discord.CategoryChannel | None = None
        if category_id is not None:
            cat = self.get_channel(category_id)
            if isinstance(cat, discord.CategoryChannel):
                category = cat

        if channel_type == "text":
            return await guild.create_text_channel(
                name, category=category, topic=topic, reason=reason
            )
        if channel_type == "voice":
            return await guild.create_voice_channel(
                name, category=category, reason=reason
            )
        if channel_type == "category":
            return await guild.create_category(name, reason=reason)
        if channel_type == "stage":
            return await guild.create_stage_channel(
                name, category=category, reason=reason
            )
        if channel_type == "forum":
            return await guild.create_forum(
                name, category=category, reason=reason
            )
        raise ValueError(
            f"Unknown channel_type {channel_type!r}. "
            "Must be 'text', 'voice', 'category', 'stage', or 'forum'."
        )

    async def delete_channel(
        self, channel_id: int, *, reason: str | None = None
    ) -> None:
        """Delete a channel by ID."""
        channel = self.get_channel(channel_id) or await super().fetch_channel(channel_id)  # type: ignore[misc]
        await channel.delete(reason=reason)

    # ── Webhooks ──────────────────────────────────────────────

    async def send_webhook(
        self,
        channel_id: int,
        content: str | None = None,
        *,
        username: str | None = None,
        avatar_url: str | None = None,
        embed: discord.Embed | None = None,
        **kwargs,
    ) -> None:
        """Send a message via a webhook in the given channel.

        On first call for a channel, creates a webhook named ``"Webhook"`` and
        caches it. Subsequent calls reuse the cached webhook.

        Example::

            await bot.send_webhook(CHANNEL_ID, "Hello from a webhook!")
        """
        if channel_id not in self._webhooks:  # type: ignore[attr-defined]
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                raise RuntimeError(
                    f"Channel {channel_id} is not a text channel"
                )
            self._webhooks[channel_id] = await channel.create_webhook(name="Webhook")  # type: ignore[attr-defined]
        webhook = self._webhooks[channel_id]  # type: ignore[attr-defined]
        try:
            await webhook.send(content, username=username, avatar_url=avatar_url, embed=embed, **kwargs)
        except discord.NotFound:
            # Recreate stale cached webhook once and retry.
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                raise RuntimeError(
                    f"Channel {channel_id} is not a text channel"
                ) from None
            self._webhooks[channel_id] = await channel.create_webhook(name="Webhook")  # type: ignore[attr-defined]
            webhook = self._webhooks[channel_id]  # type: ignore[attr-defined]
            await webhook.send(content, username=username, avatar_url=avatar_url, embed=embed, **kwargs)

    # ── Emoji management ──────────────────────────────────────

    async def create_emoji(
        self,
        guild_id: int,
        name: str,
        image_path: str,
        *,
        reason: str | None = None,
    ) -> discord.Emoji:
        """Create a custom emoji in a guild from a local image file.

        Raises ``RuntimeError`` if the bot is not in the guild.
        """
        guild = self.get_guild(guild_id)
        if guild is None:
            raise RuntimeError(f"Bot is not in guild {guild_id}")
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"Emoji image file not found: {image_path}")
        # Discord's custom emoji upload limit is 256 KiB.
        if path.stat().st_size > 256 * 1024:
            raise RuntimeError(
                f"Emoji image exceeds 256 KiB: {image_path}"
            )
        with path.open("rb") as f:
            image_bytes = f.read()
        return await guild.create_custom_emoji(name=name, image=image_bytes, reason=reason)

    async def delete_emoji(
        self,
        guild_id: int,
        emoji_id: int,
        *,
        reason: str | None = None,
    ) -> None:
        """Delete a custom emoji from a guild by emoji ID.

        Raises ``RuntimeError`` if the bot is not in the guild.
        """
        guild = self.get_guild(guild_id)
        if guild is None:
            raise RuntimeError(f"Bot is not in guild {guild_id}")
        emoji = await guild.fetch_emoji(emoji_id)
        await emoji.delete(reason=reason)

    async def fetch_guild_emojis(self, guild_id: int) -> list[discord.Emoji]:
        """Return all custom emojis for a guild.

        Raises ``RuntimeError`` if the bot is not in the guild.
        """
        guild = self.get_guild(guild_id)
        if guild is None:
            raise RuntimeError(f"Bot is not in guild {guild_id}")
        return await guild.fetch_emojis()
