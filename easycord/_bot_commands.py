"""Slash command, context menu, and subcommand group registration."""
from __future__ import annotations

import asyncio
import inspect
import time
from typing import Callable, Union

import discord
from discord import app_commands
import logging

from .context import Context
from .middleware import build_chain

logger = logging.getLogger("easycord")


class _CommandsMixin:
    """Mixin: slash commands, context menus, and subcommand groups."""

    # ── Slash commands ────────────────────────────────────────

    def slash(
        self,
        name: str | None = None,
        *,
        description: str = "No description provided.",
        guild_id: int | None = None,
        guild_only: bool = False,
        ephemeral: bool = False,
        permissions: list[str] | None = None,
        cooldown: float | None = None,
        autocomplete: dict[str, Callable] | None = None,
        choices: dict[str, list] | None = None,
        aliases: list[str] | None = None,
        nsfw: bool = False,
        allowed_contexts: discord.AppCommandContext | None = None,
        allowed_installs: discord.AppInstallationType | None = None,
    ) -> Callable:
        """Decorator that registers a top-level slash command.

        Parameters
        ----------
        permissions:
            List of ``discord.Permissions`` attribute names the invoking member
            must have (e.g. ``["kick_members", "ban_members"]``). Responds with
            an ephemeral error and skips the command if any are missing.
        cooldown:
            Per-user cooldown in seconds. The command is blocked ephemerally
            until the window expires.
        autocomplete:
            Dict mapping parameter names to async callbacks that return
            suggestions. Each callback receives the current typed string and
            returns a ``list[str]``::

                async def fruit_choices(current: str) -> list[str]:
                    fruits = ["apple", "banana", "cherry"]
                    return [f for f in fruits if current.lower() in f]

                @bot.slash(description="Pick a fruit", autocomplete={"fruit": fruit_choices})
                async def pick(ctx, fruit: str):
                    await ctx.respond(f"You picked {fruit}!")
        """

        def decorator(func: Callable) -> Callable:
            primary = name or func.__name__
            self._register_slash(
                func,
                name=primary,
                description=description,
                guild_id=guild_id,
                guild_only=guild_only,
                ephemeral=ephemeral,
                permissions=permissions,
                cooldown=cooldown,
                autocomplete=autocomplete,
                choices=choices,
                nsfw=nsfw,
                allowed_contexts=allowed_contexts,
                allowed_installs=allowed_installs,
            )
            for alias in (aliases or []):
                self._register_slash(
                    func,
                    name=alias,
                    description=description,
                    guild_id=guild_id,
                    guild_only=guild_only,
                    ephemeral=ephemeral,
                    permissions=permissions,
                    cooldown=cooldown,
                    autocomplete=autocomplete,
                    choices=choices,
                    nsfw=nsfw,
                    allowed_contexts=allowed_contexts,
                    allowed_installs=allowed_installs,
                )
            return func

        return decorator

    def _build_slash_callback(
        self,
        func: Callable,
        *,
        guild_only: bool = False,
        ephemeral: bool = False,
        permissions: list[str] | None = None,
        cooldown: float | None = None,
    ) -> Callable:
        """Build a discord.py-compatible callback with guild, permission, and cooldown guards."""
        sig = inspect.signature(func)
        user_params = list(sig.parameters.values())[1:]
        _cooldown_last_used: dict[int, float] = {}

        async def callback(interaction: discord.Interaction, **kwargs) -> None:
            ctx = Context(interaction)
            if ephemeral:
                ctx._force_ephemeral = True

            async def invoke() -> None:
                if guild_only and not ctx.guild:
                    await ctx.respond(
                        "This command can only be used inside a server.",
                        ephemeral=True,
                    )
                    return
                if permissions:
                    if not ctx.guild:
                        await ctx.respond(
                            "This command can only be used inside a server.",
                            ephemeral=True,
                        )
                        return
                    member = ctx.guild.get_member(ctx.user.id)
                    if not member:
                        await ctx.respond(
                            "Could not verify your permissions.", ephemeral=True
                        )
                        return
                    missing = [
                        p for p in permissions
                        if not getattr(member.guild_permissions, p, False)
                    ]
                    if missing:
                        await ctx.respond(
                            f"You need the following permission(s): "
                            f"{', '.join(missing)}.",
                            ephemeral=True,
                        )
                        return
                if cooldown is not None:
                    uid = ctx.user.id
                    now = time.monotonic()
                    remaining = cooldown - (now - _cooldown_last_used.get(uid, 0.0))
                    if remaining > 0:
                        await ctx.respond(
                            f"This command is on cooldown. "
                            f"Try again in {remaining:.1f}s.",
                            ephemeral=True,
                        )
                        return
                    _cooldown_last_used[uid] = now
                try:
                    await func(ctx, **kwargs)
                except Exception as exc:
                    if self._error_handler is not None:
                        await self._error_handler(ctx, exc)
                    else:
                        raise

            await build_chain(ctx, invoke, self._middleware)()

        interaction_param = inspect.Parameter(
            "interaction",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=discord.Interaction,
        )
        callback.__signature__ = sig.replace(
            parameters=[interaction_param] + user_params
        )
        return callback

    def _register_slash(
        self,
        func: Callable,
        *,
        name: str,
        description: str,
        guild_id: int | None,
        guild_only: bool = False,
        ephemeral: bool = False,
        permissions: list[str] | None = None,
        cooldown: float | None = None,
        autocomplete: dict[str, Callable] | None = None,
        choices: dict[str, list] | None = None,
        nsfw: bool = False,
        allowed_contexts: discord.AppCommandContext | None = None,
        allowed_installs: discord.AppInstallationType | None = None,
        parent: app_commands.Group | None = None,
    ) -> None:
        """Register a callable as a slash command.

        When *parent* is an ``app_commands.Group`` the command is added to
        the group instead of the command tree (used by add_group).
        """
        guild = discord.Object(id=guild_id) if guild_id else None
        callback = self._build_slash_callback(
            func,
            guild_only=guild_only,
            ephemeral=ephemeral,
            permissions=permissions,
            cooldown=cooldown,
        )
        if choices:
            self._inject_choices(callback, choices)
        cmd = app_commands.Command(
            name=name,
            description=description,
            callback=callback,
            nsfw=nsfw,
            allowed_contexts=allowed_contexts,
            allowed_installs=allowed_installs,
        )
        for param_name, handler in (autocomplete or {}).items():
            async def _ac(
                _: discord.Interaction,
                current: str,
                _h: Callable = handler,
            ) -> list[app_commands.Choice]:
                results = await _h(current)
                return [app_commands.Choice(name=r, value=r) for r in results]
            cmd.autocomplete(param_name)(_ac)
        if parent is not None:
            parent.add_command(cmd)
        else:
            self.tree.add_command(cmd, guild=guild)

    # ── Subcommand groups ──────────────────────────────────────

    def add_group(self, group: "SlashGroup") -> None:  # type: ignore[name-defined]
        """Register a SlashGroup as a discord subcommand namespace.

        Example::

            class ModGroup(SlashGroup, name="mod", description="Moderation commands"):

                @slash(description="Kick a member", permissions=["kick_members"])
                async def kick(self, ctx, member: discord.Member):
                    await member.kick()
                    await ctx.respond(f"Kicked {member.display_name}.")

            bot.add_group(ModGroup())
        """
        if group in self._plugins:
            raise ValueError(
                f"{type(group).__name__} is already added to this bot."
            )
        group._bot = self
        self._plugins.append(group)

        discord_group = app_commands.Group(
            name=group._group_name,
            description=group._group_description,
            guild_only=group._group_guild_only,
            allowed_contexts=group._group_allowed_contexts,
            allowed_installs=group._group_allowed_installs,
            nsfw=group._group_nsfw,
            default_permissions=group._group_default_permissions,
        )
        self._scan_methods(group, parent=discord_group)

        guild = discord.Object(id=group._group_guild) if group._group_guild else None
        self.tree.add_command(discord_group, guild=guild)

        if self.is_ready():
            asyncio.create_task(group.on_load())
            self._start_plugin_tasks(group)

    def add_groups(self, *groups: "SlashGroup") -> None:  # type: ignore[name-defined]
        """Register several SlashGroup namespaces in one call."""
        for group in groups:
            self.add_group(group)

    # ── Context menus ─────────────────────────────────────────

    def user_command(
        self,
        name: str | None = None,
        *,
        guild_id: int | None = None,
        nsfw: bool = False,
        allowed_contexts: discord.AppCommandContext | None = None,
        allowed_installs: discord.AppInstallationType | None = None,
    ) -> Callable:
        """Decorator that registers a right-click User context menu command.

        The handler receives ``(ctx, member)`` where ``member`` is the
        right-clicked user as a ``discord.Member | discord.User``.
        """
        def decorator(func: Callable) -> Callable:
            self._register_context_menu(
                func,
                name=name or func.__name__,
                menu_type=discord.AppCommandType.user,
                guild_id=guild_id,
                nsfw=nsfw,
                allowed_contexts=allowed_contexts,
                allowed_installs=allowed_installs,
            )
            return func
        return decorator

    def message_command(
        self,
        name: str | None = None,
        *,
        guild_id: int | None = None,
        nsfw: bool = False,
        allowed_contexts: discord.AppCommandContext | None = None,
        allowed_installs: discord.AppInstallationType | None = None,
    ) -> Callable:
        """Decorator that registers a right-click Message context menu command.

        The handler receives ``(ctx, message)`` where ``message`` is the
        right-clicked ``discord.Message``.
        """
        def decorator(func: Callable) -> Callable:
            self._register_context_menu(
                func,
                name=name or func.__name__,
                menu_type=discord.AppCommandType.message,
                guild_id=guild_id,
                nsfw=nsfw,
                allowed_contexts=allowed_contexts,
                allowed_installs=allowed_installs,
            )
            return func
        return decorator

    def _register_context_menu(
        self,
        func: Callable,
        *,
        name: str,
        menu_type: discord.AppCommandType,
        guild_id: int | None,
        nsfw: bool = False,
        allowed_contexts: discord.AppCommandContext | None = None,
        allowed_installs: discord.AppInstallationType | None = None,
    ) -> None:
        """Build and register an app_commands.ContextMenu from a user-provided handler."""
        guild = discord.Object(id=guild_id) if guild_id else None
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        target_name = params[1].name if len(params) > 1 else "target"

        if menu_type == discord.AppCommandType.user:
            target_annotation: type = Union[discord.Member, discord.User]  # type: ignore[assignment]
        else:
            target_annotation = discord.Message

        interaction_param = inspect.Parameter(
            "interaction",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=discord.Interaction,
        )
        target_param = inspect.Parameter(
            target_name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=target_annotation,
        )

        async def callback(interaction: discord.Interaction, target) -> None:
            ctx = Context(interaction)
            async def invoke() -> None:
                await func(ctx, target)
            await build_chain(ctx, invoke, self._middleware)()

        callback.__signature__ = inspect.Signature(
            parameters=[interaction_param, target_param]
        )
        menu = app_commands.ContextMenu(
            name=name,
            callback=callback,
            type=menu_type,
            nsfw=nsfw,
            allowed_contexts=allowed_contexts,
            allowed_installs=allowed_installs,
        )
        self.tree.add_command(menu, guild=guild)
        logger.debug("Registered context menu %r (type=%s)", name, menu_type.name)

    @staticmethod
    def _inject_choices(callback: Callable, choices: dict[str, list]) -> None:
        """Stamp discord.py's internal choices attribute onto a command callback."""
        if not hasattr(callback, "__discord_app_commands_param_choices__"):
            callback.__discord_app_commands_param_choices__ = {}
        for param_name, values in choices.items():
            callback.__discord_app_commands_param_choices__[param_name] = [
                app_commands.Choice(name=str(v), value=v) for v in values
            ]
