"""Slash command, context menu, and subcommand group registration."""
from __future__ import annotations

import asyncio
import inspect
import os
import time
from typing import TYPE_CHECKING, Callable, Union

import discord
from discord import app_commands
import logging

from .context import Context
from .middleware import build_chain

if TYPE_CHECKING:
    from .group import SlashGroup

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
            until the window expires. Cooldowns are tracked in memory on this
            bot process and are not shared across shards or processes.
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
                require_admin=require_admin,
                ephemeral=ephemeral,
                permissions=permissions if permissions is not None else getattr(func, "_slash_permissions", None),
                cooldown=cooldown if cooldown is not None else getattr(func, "_slash_cooldown", None),
                cooldown_rate=getattr(func, "_slash_cooldown_rate", cooldown_rate),
                cooldown_bucket=getattr(func, "_slash_cooldown_bucket", cooldown_bucket),
                premium_required=getattr(func, "_slash_premium_required", premium_required),
                autocomplete=autocomplete,
                choices=choices,
                nsfw=nsfw,
                allowed_contexts=allowed_contexts or getattr(func, "_slash_allowed_contexts", None),
                allowed_installs=allowed_installs or getattr(func, "_slash_allowed_installs", None),
            )
            for alias in (aliases or []):
                self._register_slash(
                    func,
                    name=alias,
                    description=description,
                    guild_id=guild_id,
                    guild_only=guild_only,
                    require_admin=require_admin,
                    ephemeral=ephemeral,
                    permissions=permissions if permissions is not None else getattr(func, "_slash_permissions", None),
                    cooldown=cooldown if cooldown is not None else getattr(func, "_slash_cooldown", None),
                    cooldown_rate=getattr(func, "_slash_cooldown_rate", cooldown_rate),
                    cooldown_bucket=getattr(func, "_slash_cooldown_bucket", cooldown_bucket),
                    premium_required=getattr(func, "_slash_premium_required", premium_required),
                    autocomplete=autocomplete,
                    choices=choices,
                    nsfw=nsfw,
                    allowed_contexts=allowed_contexts or getattr(func, "_slash_allowed_contexts", None),
                    allowed_installs=allowed_installs or getattr(func, "_slash_allowed_installs", None),
                )
            return func

        return decorator

    async def watch_plugins(self, *plugin_names: str, interval: float = 1.0) -> None:
        """Watch plugin source files and run lifecycle reloads on changes.

        Intended for development only — run inside a task or background thread.
        Calls ``reload_plugin(name)`` whenever the source file's mtime changes.
        This re-runs the existing plugin instance's unload/load hooks; it does
        not reload Python modules or recreate command objects.

        Example::

            @bot.on("ready")
            async def start_watcher():
                import asyncio
                asyncio.create_task(bot.watch_plugins("MyPlugin"))
        """
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
        """Build a discord.py-compatible callback with guild, permission, and cooldown guards."""
        sig = inspect.signature(func)
        user_params = list(sig.parameters.values())[1:]
        _cooldown_last_used: dict[int, list[float]] = {}
        if cooldown is not None and cooldown_rate < 1:
            raise ValueError("cooldown_rate must be at least 1")
        if cooldown_bucket not in {"user", "guild", "global"}:
            raise ValueError(
                "cooldown_bucket must be 'user', 'guild', or 'global'"
            )

        # Merge require_admin into the permissions list at build time so the
        # check is handled by the single unified permissions path below.
        effective_permissions = list(permissions or [])
        if require_admin and "administrator" not in effective_permissions:
            effective_permissions.append("administrator")

        async def callback(interaction: discord.Interaction, **kwargs) -> None:
            ctx = Context(interaction)
            if ephemeral:
                ctx._force_ephemeral = True

            async def invoke() -> None:
                if guild_only and not ctx.guild:
                    await ctx.respond(
                        ctx.t(
                            "errors.guild_only",
                            default="This command can only be used inside a server.",
                        ),
                        ephemeral=True,
                    )
                    return
                if effective_permissions:
                    if not ctx.guild:
                        await ctx.respond(
                            ctx.t(
                                "errors.guild_only",
                                default="This command can only be used inside a server.",
                            ),
                            ephemeral=True,
                        )
                        return
                    member = ctx.guild.get_member(ctx.user.id)
                    if not member:
                        await ctx.respond(
                            ctx.t(
                                "errors.permissions_unverified",
                                default="Could not verify your permissions.",
                            ),
                            ephemeral=True,
                        )
                        return
                    missing = [
                        p for p in effective_permissions
                        if not getattr(member.guild_permissions, p, False)
                    ]
                    if missing:
                        await ctx.respond(
                            ctx.t(
                                "errors.permissions_missing",
                                default="You need the following permission(s): {permissions}.",
                                permissions=", ".join(missing),
                            ),
                            ephemeral=True,
                        )
                        return
                if premium_required and not ctx.entitlements:
                    await ctx.respond(
                        ctx.t(
                            "errors.premium_required",
                            default="This command requires an active premium subscription.",
                        ),
                        ephemeral=True,
                    )
                    return
                if cooldown is not None:
                    if cooldown_bucket == "guild":
                        bucket_key = ctx.guild.id if ctx.guild else ctx.user.id
                    elif cooldown_bucket == "global":
                        bucket_key = 0
                    else:
                        bucket_key = ctx.user.id
                    now = time.monotonic()
                    used_at = [
                        ts
                        for ts in _cooldown_last_used.get(bucket_key, [])
                        if now - ts < cooldown
                    ]
                    if len(used_at) >= cooldown_rate:
                        remaining = cooldown - (now - used_at[0])
                        await ctx.respond(
                            ctx.t(
                                "errors.cooldown",
                                default="This command is on cooldown. Try again in {seconds:.1f}s.",
                                seconds=remaining,
                            ),
                            ephemeral=True,
                        )
                        return
                    used_at.append(now)
                    _cooldown_last_used[bucket_key] = used_at
                try:
                    await func(ctx, **kwargs)
                except Exception as exc:
                    # Priority: per-command → plugin.on_error → global → raise
                    per_cmd = command_name and getattr(
                        self, "_command_error_handlers", {}
                    ).get(command_name)
                    if per_cmd is not None:
                        await per_cmd(ctx, exc)
                        return
                    plugin = getattr(func, "__self__", None)
                    if plugin is not None:
                        from .plugin import Plugin as _Plugin
                        if isinstance(plugin, _Plugin):
                            plugin_on_error = type(plugin).on_error
                            base_on_error = _Plugin.on_error
                            if plugin_on_error is not base_on_error:
                                await plugin.on_error(ctx, exc)
                                return
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
        allowed_contexts: discord.AppCommandContext | None = None,
        allowed_installs: discord.AppInstallationType | None = None,
        parent: app_commands.Group | None = None,
        source_plugin: str | None = None,
    ) -> None:
        """Register a callable as a slash command.

        When *parent* is an ``app_commands.Group`` the command is added to
        the group instead of the command tree (used by add_group).
        """
        guild = discord.Object(id=guild_id) if guild_id else None
        callback = self._build_slash_callback(
            func,
            guild_only=guild_only,
            require_admin=require_admin,
            ephemeral=ephemeral,
            permissions=permissions,
            cooldown=cooldown,
            cooldown_rate=cooldown_rate,
            cooldown_bucket=cooldown_bucket,
            premium_required=premium_required,
            command_name=name,
        )
        autocomplete_handlers: dict[str, Callable] = {
            **(autocomplete or {}),
            **getattr(func, "_slash_autocomplete_handlers", {}),
        }
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
        for param_name, handler in autocomplete_handlers.items():
            sig = inspect.signature(handler)
            params = list(sig.parameters.values())
            param_count = len(params)
            
            if param_count not in (1, 3):
                plugin_info = f" in plugin {source_plugin}" if source_plugin else ""
                raise TypeError(
                    f"Invalid autocomplete signature for option {param_name!r} "
                    f"of command {name!r}{plugin_info}. "
                    f"Expected (current) or (ctx, current, options), got {sig}."
                )
            
            expects_options = param_count == 3

            def _make_autocomplete(_h: Callable, _expects_options: bool) -> Callable:
                async def _ac(
                    interaction: discord.Interaction,
                    current: str,
                ) -> list[app_commands.Choice]:
                    ctx = Context(interaction)
                    options = self._autocomplete_options(interaction)
                    try:
                        if _expects_options:
                            results = await _h(ctx, current, options)
                        else:
                            results = await _h(current)
                        return [app_commands.Choice(name=r, value=r) for r in results]
                    except Exception as exc:
                        plugin_instance = getattr(_h, "__self__", None)
                        if plugin_instance is None and source_plugin:
                            plugin_instance = next((p for p in self._plugins if getattr(p, "_instance_id", type(p).__name__) == source_plugin), None)
                        await self._dispatch_framework_error(exc, ctx=ctx, plugin_instance=plugin_instance)
                        return []

                return _ac

            _ac = _make_autocomplete(handler, expects_options)
            cmd.autocomplete(param_name)(_ac)
            self.registry.register_autocomplete(
                name,
                param_name,
                handler,
                source_plugin=source_plugin,
                guild_id=guild_id,
            )
        if parent is not None:
            parent.add_command(cmd)
        else:
            self.tree.add_command(cmd, guild=guild)
        registry_name = f"{parent.name} {name}" if parent is not None else name
        self.registry.register_slash_command(
            registry_name,
            func,
            source_plugin=source_plugin,
            guild_id=guild_id,
            metadata={
                "description": description,
                "guild_only": guild_only,
                "permissions": permissions,
                "cooldown": cooldown,
                "cooldown_rate": cooldown_rate,
                "cooldown_bucket": cooldown_bucket,
                "premium_required": premium_required,
                "allowed_contexts": allowed_contexts,
                "allowed_installs": allowed_installs,
                "parent": getattr(parent, "name", None),
            },
        )

    # ── Subcommand groups ──────────────────────────────────────

    def add_group(self, group: "SlashGroup") -> None:
        """Register a SlashGroup as a discord subcommand namespace.

        Example::

            class ModGroup(SlashGroup, name="mod", description="Moderation commands"):

                @slash(description="Kick a member", permissions=["kick_members"])
                async def kick(self, ctx, member: discord.Member):
                    await member.kick()
                    await ctx.respond(f"Kicked {member.display_name}.")

            bot.add_group(ModGroup())
        """
        from .group import SlashGroup
        if not isinstance(group, SlashGroup):
            raise TypeError(
                f"expected a SlashGroup instance, got {type(group).__name__!r}"
            )
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

    def add_groups(self, *groups: "SlashGroup") -> None:
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
        source_plugin: str | None = None,
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
        self.registry.register_context_menu(
            name,
            func,
            source_plugin=source_plugin,
            guild_id=guild_id,
            metadata={
                "menu_type": menu_type.name,
                "nsfw": nsfw,
                "allowed_contexts": allowed_contexts,
                "allowed_installs": allowed_installs,
            },
        )
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

    @staticmethod
    def _autocomplete_options(interaction: discord.Interaction) -> dict[str, object]:
        namespace = getattr(interaction, "namespace", None)
        if namespace is not None:
            try:
                return dict(vars(namespace))
            except TypeError:
                pass
        data = getattr(interaction, "data", None) or {}
        options: dict[str, object] = {}
        for item in data.get("options", []):
            if "name" in item and "value" in item:
                options[item["name"]] = item["value"]
        return options
