"""SlashGroup — subcommand namespace for grouping related slash commands."""
from __future__ import annotations

from .plugin import Plugin


class SlashGroup(Plugin):
    """Base class for slash subcommand groups.

    Subclass ``SlashGroup``, pass ``name`` and ``description`` as class
    keyword arguments, decorate methods with ``@slash``, then register
    with ``bot.add_group()``.

    Example::

        from easycord import SlashGroup, slash

        class ModGroup(SlashGroup, name="mod", description="Moderation commands"):

            @slash(description="Kick a member", permissions=["kick_members"])
            async def kick(self, ctx, member: discord.Member):
                await member.kick()
                await ctx.respond(f"Kicked {member.display_name}.")

            @slash(description="Ban a member", permissions=["ban_members"])
            async def ban(self, ctx, member: discord.Member, reason: str = ""):
                await member.ban(reason=reason)
                await ctx.respond(f"Banned {member.display_name}.")

        bot.add_group(ModGroup())
    """

    _group_name: str = ""
    _group_description: str = "No description provided."
    _group_guild: int | None = None
    _group_guild_only: bool = False
    _group_allowed_contexts = None
    _group_allowed_installs = None
    _group_nsfw: bool = False
    _group_default_permissions = None

    def __init_subclass__(
        cls,
        name: str = "",
        description: str = "No description provided.",
        guild_id: int | None = None,
        guild_only: bool = False,
        allowed_contexts=None,
        allowed_installs=None,
        nsfw: bool = False,
        default_permissions=None,
        **kwargs,
    ) -> None:
        super().__init_subclass__(**kwargs)
        cls._group_name = name or cls.__name__.lower()
        cls._group_description = description
        cls._group_guild = guild_id
        cls._group_guild_only = guild_only
        cls._group_allowed_contexts = allowed_contexts
        cls._group_allowed_installs = allowed_installs
        cls._group_nsfw = nsfw
        cls._group_default_permissions = default_permissions
