"""Smart one-shot embed templates."""
from __future__ import annotations

import discord


class EasyEmbed:
    """Factory for status-style embeds.

    Examples
    --------
    >>> embed = EasyEmbed.success("Operation complete!")
    >>> isinstance(embed, discord.Embed)
    True
    """

    @staticmethod
    def success(message: str) -> discord.Embed:
        """Return a green success embed with a checkmark prefix."""
        return discord.Embed(
            description=f"✅ {message}",
            color=discord.Color(0x2ECC71),
        )

    @staticmethod
    def error(message: str) -> discord.Embed:
        """Return a red error embed with an X prefix."""
        return discord.Embed(
            description=f"❌ {message}",
            color=discord.Color(0xE74C3C),
        )

    @staticmethod
    def info(message: str) -> discord.Embed:
        """Return a blue info embed."""
        return discord.Embed(
            description=f"ℹ️ {message}",
            color=discord.Color(0x3498DB),
        )

    @staticmethod
    def warning(message: str) -> discord.Embed:
        """Return an amber warning embed."""
        return discord.Embed(
            description=f"⚠️ {message}",
            color=discord.Color(0xF39C12),
        )
