"""Slash command, context menu, and subcommand group registration."""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
from typing import TYPE_CHECKING, Callable

import discord
from discord import app_commands

from ._command_callbacks import build_slash_callback
from ._command_registration import (
    autocomplete_options,
    inject_choices,
    register_context_menu,
    register_slash,
)
from .context import Context
from .middleware import build_chain

if TYPE_CHECKING:
    from ._bot_base import _BotBase
    from .group import SlashGroup

    _MixinBase = _BotBase
else:
    _MixinBase = object

logger = logging.getLogger("easycord")


class _CommandsMixin(_MixinBase):
    """Mixin: slash commands, context menus, and subcommand groups."""

    def slash(
        self,
        name: str | None = None,
        *,
        description: str = "No description provided.",
        guild_id: int | None = None,
        guild_only: bool = False,
        require_admin: bool = False,
        ephemeral: bool = False,
        permissions: list[str] | None = None,
        cooldown: float | None = None,
        cooldown_rate: int = 1,
        cooldown_bucket: str = "user",
        premium_required: bool = False,
        autocomplete: dict[str, Callable] | None = None,
        choices: dict[str, list] | None = None,
        aliases: list[str] | None = None,
        nsfw: bool = False,
        allowed_contexts: app_commands.AppCommandContext | None = None,
        allowed_installs: app_commands.AppInstallationType | None = None,
    ) -> Callable:
        """Decorator that registers a top-level slash command."""

        def decorator(func: Callable) -> Callable:
            for command_name in [name or func.__name__] + list(aliases or []):
                self._register_slash(
                    func,
                    name=command_name,
                    description=description,
                    guild_id=guild_id,
                    guild_only=guild_only,
                    require_admin=require_admin,
                    ephemeral=ephemeral,
                    permissions=permissions
                    if permissions is not None
                    else getattr(func, "_slash_permissions", None),
                    cooldown=cooldown
                    if cooldown is not None
                    else getattr(func, "_slash_cooldown", None),
                    cooldown_rate=getattr(
                        func, "_slash_cooldown_rate", cooldown_rate
                    ),
                    cooldown_bucket=getattr(
                        func, "_slash_cooldown_bucket", cooldown_bucket
                    ),
                    premium_required=getattr(
                        func, "_slash_premium_required", premium_required
                    ),
                    autocomplete=autocomplete,
                    choices=choices,
                    nsfw=nsfw,
                    allowed_contexts=allowed_contexts
                    or getattr(func, "_slash_allowed_contexts", None),
                    allowed_installs=allowed_installs
                    or getattr(func, "_slash_allowed_installs", None),
                )
            return func

        return decorator

    async def watch_plugins(self, *plugin_names: str, interval: float = 1.0) -> None:
        """Watch plugin source files and run lifecycle reloads on changes."""
        mtimes: dict[str, float] = {}
        while True:
            for name in plugin_names:
                plugin = next(
                    (p for p in self._plugins if type(p).__name__ == name), None
                )
                if plugin is None:
                    continue
                try:
                    src = inspect.getfile(type(plugin))
                    mtime = os.path.getmtime(src)
                    if mtimes.get(name, mtime) != mtime:
                        logger.info("Lifecycle-reloading plugin %r (file changed)", name)
                        await self.reload_plugin(name)
                    mtimes[name] = mtime
                except Exception as exc:
                    logger.debug(
                        "Could not watch/reload plugin %r: %s",
                        name,
                        exc,
                        exc_info=exc,
                    )
            await asyncio.sleep(interval)

    def _build_slash_callback(
        self,
        func: Callable,
        *,
        guild_only: bool = False,
        require_admin: bool = False,
        ephemeral: bool = False,
        permissions: list[str] | None = None,
        cooldown: float | None = None,
        cooldown_rate: int = 1,
        cooldown_bucket: str = "user",
        premium_required: bool = False,
        command_name: str | None = None,
    ) -> Callable:
        """Build a discord.py-compatible callback with guard checks."""
        return build_slash_callback(
            self,
            func,
            context_factory=Context,
            chain_builder=lambda ctx, invoke, middleware: build_chain(
                ctx,
                invoke,
                middleware,
            ),
            guild_only=guild_only,
            require_admin=require_admin,
            ephemeral=ephemeral,
            permissions=permissions,
            cooldown=cooldown,
            cooldown_rate=cooldown_rate,
            cooldown_bucket=cooldown_bucket,
            premium_required=premium_required,
            command_name=command_name,
        )

    def _register_slash(
        self,
        func: Callable,
        *,
        name: str,
        description: str,
        guild_id: int | None,
        guild_only: bool = False,
        require_admin: bool = False,
        ephemeral: bool = False,
        permissions: list[str] | None = None,
        cooldown: float | None = None,
        cooldown_rate: int = 1,
        cooldown_bucket: str = "user",
        premium_required: bool = False,
        autocomplete: dict[str, Callable] | None = None,
        choices: dict[str, list] | None = None,
        nsfw: bool = False,
        allowed_contexts: app_commands.AppCommandContext | None = None,
        allowed_installs: app_commands.AppInstallationType | None = None,
        parent: app_commands.Group | None = None,
        source_plugin: str | None = None,
    ) -> None:
        """Register a callable as a slash command."""
        register_slash(
            self,
            func,
            callback_builder=self._build_slash_callback,
            context_factory=Context,
            name=name,
            description=description,
            guild_id=guild_id,
            guild_only=guild_only,
            require_admin=require_admin,
            ephemeral=ephemeral,
            permissions=permissions,
            cooldown=cooldown,
            cooldown_rate=cooldown_rate,
            cooldown_bucket=cooldown_bucket,
            premium_required=premium_required,
            autocomplete=autocomplete,
            choices=choices,
            nsfw=nsfw,
            allowed_contexts=allowed_contexts,
            allowed_installs=allowed_installs,
            parent=parent,
            source_plugin=source_plugin,
        )

    def add_group(self, group: "SlashGroup") -> None:
        """Register a SlashGroup as a discord subcommand namespace."""
        from .group import SlashGroup

        if not isinstance(group, SlashGroup):
            raise TypeError(
                f"expected a SlashGroup instance, got {type(group).__name__!r}"
            )
        if group in self._plugins:
            raise ValueError(f"{type(group).__name__} is already added to this bot.")
        group._bot = self  # type: ignore[assignment]
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

    def add_groups(self, *groups: "SlashGroup") -> None:
        """Register several SlashGroup namespaces in one call."""
        for group in groups:
            self.add_group(group)

    def user_command(
        self,
        name: str | None = None,
        *,
        guild_id: int | None = None,
        nsfw: bool = False,
        allowed_contexts: app_commands.AppCommandContext | None = None,
        allowed_installs: app_commands.AppInstallationType | None = None,
    ) -> Callable:
        """Decorator that registers a right-click User context menu command."""

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
        allowed_contexts: app_commands.AppCommandContext | None = None,
        allowed_installs: app_commands.AppInstallationType | None = None,
    ) -> Callable:
        """Decorator that registers a right-click Message context menu command."""

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
        allowed_contexts: app_commands.AppCommandContext | None = None,
        allowed_installs: app_commands.AppInstallationType | None = None,
        source_plugin: str | None = None,
    ) -> None:
        """Build and register an app_commands.ContextMenu from a handler."""
        register_context_menu(
            self,
            func,
            context_factory=lambda interaction: Context(interaction),
            chain_builder=lambda ctx, invoke, middleware: build_chain(
                ctx,
                invoke,
                middleware,
            ),
            name=name,
            menu_type=menu_type,
            guild_id=guild_id,
            nsfw=nsfw,
            allowed_contexts=allowed_contexts,
            allowed_installs=allowed_installs,
            source_plugin=source_plugin,
        )

    @staticmethod
    def _inject_choices(callback: Callable, choices: dict[str, list]) -> None:
        """Stamp discord.py's internal choices attribute onto a command callback."""
        inject_choices(callback, choices)

    @staticmethod
    def _autocomplete_options(interaction: discord.Interaction) -> dict[str, object]:
        return autocomplete_options(interaction)
