"""Pre-composed decorator stacks for common command patterns.

Instead of:

    @slash(description="...", permissions=["kick_members"], cooldown=30.0)
    @require_permissions("kick_members")
    @cooldown(rate=1, per=30.0)
    async def kick(self, ctx, member: discord.Member):
        ...

You can write:

    @slash_admin_command(description="...", cooldown=30.0)
    async def kick(self, ctx, member: discord.Member):
        ...

Or even simpler:

    @slash_management_command(description="...")
    async def kick(self, ctx, member: discord.Member):
        ...
"""
from __future__ import annotations

from typing import Callable, TypeVar

from .decorators import (
    slash as _slash,
    cooldown as _cooldown,
    require_permissions as _require_permissions,
    describe as _describe,
)

F = TypeVar("F", bound=Callable)


def slash_admin_command(
    *,
    description: str = "No description provided.",
    cooldown: float | None = None,
    bot_permissions: list[str] | None = None,
    ephemeral: bool | None = None,
) -> Callable[[F], F]:
    """Pre-composed stack for admin-only commands.
    
    Equivalent to @slash + require_admin=True.
    
    Parameters
    ----------
    description: str
        Command description.
    cooldown: float
        Optional per-user cooldown in seconds.
    bot_permissions: list[str]
        Bot permissions required (e.g., ["ban_members"]).
    ephemeral: bool | None
        Whether the response is ephemeral (default True).
    
    Example::
    
        @slash_admin_command(description="Nuke the server", cooldown=3600.0)
        async def nuke(self, ctx):
            await ctx.respond("Nuked!", ephemeral=True)
    """
    def decorator(func: F) -> F:
        func = _slash(
            description=description,
            require_admin=True,
            cooldown=cooldown,
            bot_permissions=bot_permissions,
            ephemeral=True if ephemeral is None else ephemeral,
        )(func)
        return func
    return decorator


def slash_management_command(
    *,
    description: str = "No description provided.",
    permissions: list[str] | None = None,
    cooldown: float | None = None,
    bot_permissions: list[str] | None = None,
    ephemeral: bool = True,
) -> Callable[[F], F]:
    """Pre-composed stack for moderator/staff commands.
    
    Default permissions: manage_guild. Supply *permissions* to override.
    
    Parameters
    ----------
    description: str
        Command description.
    permissions: list[str]
        User permissions required (defaults to ["manage_guild"]).
    cooldown: float
        Optional per-user cooldown in seconds.
    bot_permissions: list[str]
        Bot permissions required.
    ephemeral: bool
        Whether the response is ephemeral (default True).
    
    Example::
    
        @slash_management_command(description="Set welcome message")
        async def set_welcome(self, ctx, message: str):
            await ctx.respond(f"Welcome message set", ephemeral=True)
    """
    perms = permissions or ["manage_guild"]
    
    def decorator(func: F) -> F:
        func = _slash(
            description=description,
            permissions=perms,
            cooldown=cooldown,
            bot_permissions=bot_permissions,
            ephemeral=ephemeral,
        )(func)
        return func
    return decorator


def slash_mod_command(
    *,
    description: str = "No description provided.",
    cooldown: float | None = None,
    bot_permissions: list[str] | None = None,
) -> Callable[[F], F]:
    """Pre-composed stack for moderation commands.
    
    Default permissions: kick_members, ban_members, timeout_members.
    
    Parameters
    ----------
    description: str
        Command description.
    cooldown: float
        Optional per-user cooldown in seconds.
    bot_permissions: list[str]
        Bot permissions required (in addition to moderation defaults).
    
    Example::
    
        @slash_mod_command(description="Ban a member", cooldown=30.0)
        async def ban(self, ctx, member: discord.Member, reason: str = ""):
            await member.ban(reason=reason)
            await ctx.respond(f"Banned {member.mention}", ephemeral=True)
    """
    mod_perms = ["kick_members", "ban_members", "timeout_members"]
    all_bot_perms = (bot_permissions or []) + ["ban_members", "kick_members"]
    
    def decorator(func: F) -> F:
        func = _slash(
            description=description,
            permissions=mod_perms,
            cooldown=cooldown,
            bot_permissions=all_bot_perms,
            ephemeral=True,
        )(func)
        return func
    return decorator


def slash_user_command(
    *,
    description: str = "No description provided.",
    cooldown: float | None = None,
    guild_only: bool = True,
) -> Callable[[F], F]:
    """Pre-composed stack for public user commands.
    
    No permission restrictions; global or server-specific.
    
    Parameters
    ----------
    description: str
        Command description.
    cooldown: float
        Optional per-user cooldown in seconds.
    guild_only: bool
        Whether the command is server-only (default True).
    
    Example::
    
        @slash_user_command(description="Show your profile", cooldown=5.0)
        async def profile(self, ctx):
            await ctx.respond(f"Your profile: ...", ephemeral=True)
    """
    def decorator(func: F) -> F:
        func = _slash(
            description=description,
            cooldown=cooldown,
            guild_only=guild_only,
            ephemeral=True,
        )(func)
        return func
    return decorator


def slash_with_confirm(
    *,
    description: str = "No description provided.",
    permissions: list[str] | None = None,
    cooldown: float | None = None,
    bot_permissions: list[str] | None = None,
) -> Callable[[F], F]:
    """Pre-composed stack for dangerous commands that need confirmation.
    
    This is a marker — the actual confirmation UI should be implemented
    in the command body using ctx.confirm().
    
    Parameters
    ----------
    description: str
        Command description.
    permissions: list[str]
        User permissions required.
    cooldown: float
        Optional per-user cooldown in seconds.
    bot_permissions: list[str]
        Bot permissions required.
    
    Example::
    
        @slash_with_confirm(
            description="Delete all data",
            permissions=["manage_guild"],
            cooldown=3600.0,
        )
        async def nuke(self, ctx):
            if not await ctx.confirm("Are you sure? This cannot be undone."):
                await ctx.respond("Cancelled.", ephemeral=True)
                return
            # Perform dangerous operation
            await ctx.respond("Nuked!", ephemeral=True)
    """
    def decorator(func: F) -> F:
        func = _slash(
            description=description,
            permissions=permissions,
            cooldown=cooldown,
            bot_permissions=bot_permissions,
            ephemeral=True,
        )(func)
        return func
    return decorator
