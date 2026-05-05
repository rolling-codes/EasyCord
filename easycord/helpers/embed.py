"""Quick embed creation helpers."""
from __future__ import annotations

import discord


class EmbedBuilder:
    """Fluent embed builder with common presets."""

    @staticmethod
    def success(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Green success embed."""
        return discord.Embed(title=title, description=description, color=discord.Color.green(), **kwargs)

    @staticmethod
    def error(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Red error embed."""
        return discord.Embed(title=title, description=description, color=discord.Color.red(), **kwargs)

    @staticmethod
    def info(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Blue info embed."""
        return discord.Embed(title=title, description=description, color=discord.Color.blue(), **kwargs)

    @staticmethod
    def warning(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Orange warning embed."""
        return discord.Embed(title=title, description=description, color=discord.Color.orange(), **kwargs)

    def __init__(self, title: str = "", description: str = "", color: int | discord.Color | None = None):
        """Create embed with title, description, optional color."""
        self.embed = discord.Embed(title=title, description=description, color=color or discord.Color.default())

    def set_color(self, color: int | discord.Color) -> EmbedBuilder:
        """Set embed color."""
        self.embed.color = color
        return self

    def add_field(self, name: str, value: str, inline: bool = True) -> EmbedBuilder:
        """Add field to embed."""
        self.embed.add_field(name=name, value=value, inline=inline)
        return self

    def set_thumbnail(self, url: str | None) -> EmbedBuilder:
        """Set thumbnail URL."""
        if url:
            self.embed.set_thumbnail(url=url)
        return self

    def set_image(self, url: str | None) -> EmbedBuilder:
        """Set image URL."""
        if url:
            self.embed.set_image(url=url)
        return self

    def set_footer(self, text: str, icon_url: str | None = None) -> EmbedBuilder:
        """Set footer text (optional icon)."""
        self.embed.set_footer(text=text, icon_url=icon_url)
        return self

    def set_author(self, name: str, icon_url: str | None = None, url: str | None = None) -> EmbedBuilder:
        """Set author name (optional icon/url)."""
        self.embed.set_author(name=name, icon_url=icon_url, url=url)
        return self

    def set_timestamp(self) -> EmbedBuilder:
        """Set current timestamp."""
        self.embed.timestamp = discord.utils.utcnow()
        return self

    def build(self) -> discord.Embed:
        """Return built embed."""
        return self.embed
