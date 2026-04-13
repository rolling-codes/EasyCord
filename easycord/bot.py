from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Callable, Literal, Union

import discord
from discord import app_commands

from .context import Context
from .middleware import MiddlewareFn, build_chain
from .plugin import Plugin

logger = logging.getLogger("easycord")


class Bot(discord.Client):
    """
    The main EasyCord bot — a discord.Client with slash commands,
    middleware, event listeners, and plugins built in.

    Quick start::

        import os
        from easycord import Bot
        from easycord.middleware import log_middleware, catch_errors

        bot = Bot()
        bot.use(log_middleware())
        bot.use(catch_errors())

        @bot.slash(description="Ping the bot")
        async def ping(ctx):
            await ctx.respond("Pong!")

        bot.run(os.environ["DISCORD_TOKEN"])

    Parameters
    ----------
    intents:
        Discord gateway intents. Defaults to ``discord.Intents.default()``.
    auto_sync:
        Automatically sync slash commands with Discord on startup (default ``True``).
        Set to ``False`` during development to avoid hitting Discord's sync rate limit.
    """

    def __init__(
        self,
        *,
        intents: discord.Intents | None = None,
        auto_sync: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(intents=intents or discord.Intents.default(), **kwargs)
        self.tree = app_commands.CommandTree(self)
        self._auto_sync = auto_sync
        self._middleware: list[MiddlewareFn] = []
        self._event_handlers: dict[str, list[Callable]] = {}
        self._plugins: list[Plugin] = []
        self._task_handles: dict[int, list[asyncio.Task]] = {}

    # ── Lifecycle ─────────────────────────────────────────────

    async def setup_hook(self) -> None:
        if self._auto_sync:
            await self.tree.sync()
        for plugin in self._plugins:
            await plugin.on_load()
            self._start_plugin_tasks(plugin)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)  # type: ignore[union-attr]

    def dispatch(self, event: str, /, *args, **kwargs) -> None:
        super().dispatch(event, *args, **kwargs)
        # Snapshot the list so handlers that modify _event_handlers mid-loop
        # don't cause a RuntimeError or silently skip handlers.
        for handler in list(self._event_handlers.get(event, [])):
            task = asyncio.create_task(handler(*args, **kwargs))
            task.add_done_callback(self._log_task_exception)

    def _log_task_exception(self, task: asyncio.Task) -> None:
        if not task.cancelled() and (exc := task.exception()):
            logger.exception("Unhandled error in event handler task", exc_info=exc)

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

        Example::

            @bot.slash(description="Kick a member", permissions=["kick_members"])
            async def kick(ctx, member: discord.Member):
                await member.kick()
                await ctx.respond(f"Kicked {member.display_name}.")

            @bot.slash(description="Roll dice", cooldown=5)
            async def roll(ctx):
                import random
                await ctx.respond(str(random.randint(1, 6)))
        """

        def decorator(func: Callable) -> Callable:
            self._register_slash(
                func,
                name=name or func.__name__,
                description=description,
                guild_id=guild_id,
                guild_only=guild_only,
                ephemeral=ephemeral,
                permissions=permissions,
                cooldown=cooldown,
                autocomplete=autocomplete,
                choices=choices,
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
        """Build a discord.py-compatible callback with guild, permission and cooldown guards."""
        sig = inspect.signature(func)
        user_params = list(sig.parameters.values())[1:]  # skip ctx (or self for bound methods)

        _cooldown_last_used: dict[int, float] = {}

        async def callback(interaction: discord.Interaction, **kwargs) -> None:
            ctx = Context(interaction)
            if ephemeral:
                ctx._force_ephemeral = True

            async def invoke() -> None:
                # ── Guild guard ───────────────────────────────────
                if guild_only and not ctx.guild:
                    await ctx.respond(
                        "This command can only be used inside a server.",
                        ephemeral=True,
                    )
                    return

                # ── Permission check ──────────────────────────────
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

                # ── Per-command cooldown ──────────────────────────
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

                await func(ctx, **kwargs)

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
    ) -> None:
        """Register a callable as a slash command in discord.py's app-command tree."""
        guild = discord.Object(id=guild_id) if guild_id else None
        callback = self._build_slash_callback(func, guild_only=guild_only, ephemeral=ephemeral, permissions=permissions, cooldown=cooldown)
        if choices:
            self._inject_choices(callback, choices)
        cmd = app_commands.Command(name=name, description=description, callback=callback)
        for param_name, handler in (autocomplete or {}).items():
            async def _ac(_: discord.Interaction, current: str, _h: Callable = handler) -> list[app_commands.Choice]:
                results = await _h(current)
                return [app_commands.Choice(name=r, value=r) for r in results]
            cmd.autocomplete(param_name)(_ac)
        self.tree.add_command(cmd, guild=guild)

    # ── Events ────────────────────────────────────────────────

    def on(self, event: str) -> Callable:  # type: ignore[override]
        """Decorator that registers an event listener.

        Use the event name without the ``on_`` prefix::

            @bot.on("member_join")
            async def welcome(member):
                await member.send("Welcome!")
        """
        if not isinstance(event, str) or not event:
            raise ValueError("event name must be a non-empty string")

        def decorator(func: Callable) -> Callable:
            if not callable(func):
                raise TypeError(
                    f"event handler must be callable, got {type(func).__name__!r}"
                )
            self._event_handlers.setdefault(event, []).append(func)
            return func

        return decorator

    # ── Middleware ────────────────────────────────────────────

    def use(self, middleware: MiddlewareFn) -> MiddlewareFn:
        """Register a middleware function that runs before every slash command.

        Can be used as a decorator or called directly::

            @bot.use
            async def my_middleware(ctx, proceed):
                print("before")
                await proceed()
                print("after")
        """
        if not callable(middleware):
            raise TypeError(
                f"middleware must be callable, got {type(middleware).__name__!r}"
            )
        self._middleware.append(middleware)
        return middleware

    # ── Plugins ───────────────────────────────────────────────

    def add_plugin(self, plugin: Plugin) -> None:
        """Add a plugin, registering all of its slash commands and event handlers.

        Raises ``TypeError`` if ``plugin`` is not a :class:`Plugin` instance.
        Raises ``ValueError`` if the same plugin instance has already been added.
        """
        if not isinstance(plugin, Plugin):
            raise TypeError(
                f"expected a Plugin instance, got {type(plugin).__name__!r}"
            )
        if plugin in self._plugins:
            raise ValueError(
                f"{type(plugin).__name__} is already added to this bot. "
                "Create a new instance if you need a second copy."
            )
        plugin._bot = self
        self._plugins.append(plugin)

        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_slash", False):
                self._register_slash(
                    method,
                    name=method._slash_name,
                    description=method._slash_desc,
                    guild_id=method._slash_guild,
                    guild_only=getattr(method, "_slash_guild_only", False),
                    ephemeral=getattr(method, "_slash_ephemeral", False),
                    permissions=getattr(method, "_slash_permissions", None),
                    cooldown=getattr(method, "_slash_cooldown", None),
                    autocomplete=getattr(method, "_slash_autocomplete", None),
                    choices=getattr(method, "_slash_choices", None),
                )
            if getattr(method, "_is_event", False):
                self._event_handlers.setdefault(method._event_name, []).append(method)

        if self.is_ready():
            asyncio.create_task(plugin.on_load())
            self._start_plugin_tasks(plugin)

    async def remove_plugin(self, plugin: Plugin) -> None:
        """Remove a plugin, deregistering its commands and event handlers.

        Raises ``ValueError`` if the plugin was never added.
        """
        if plugin not in self._plugins:
            raise ValueError(
                f"{type(plugin).__name__} has not been added to this bot. "
                "Call bot.add_plugin() before trying to remove it."
            )

        self._plugins.remove(plugin)

        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_slash", False):
                guild = discord.Object(id=method._slash_guild) if method._slash_guild else None
                try:
                    self.tree.remove_command(method._slash_name, guild=guild)
                except Exception:  # noqa: BLE001
                    logger.debug("Could not remove command %r during unload", method._slash_name)

            if getattr(method, "_is_event", False):
                try:
                    self._event_handlers[method._event_name].remove(method)
                except (KeyError, ValueError):
                    pass

        # Cancel background tasks
        for handle in self._task_handles.pop(id(plugin), []):
            handle.cancel()
            try:
                await handle
            except asyncio.CancelledError:
                pass

        await plugin.on_unload()

    def _start_plugin_tasks(self, plugin: Plugin) -> None:
        """Start all @task-decorated methods for a plugin."""
        handles = []
        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_task", False):
                handle = asyncio.create_task(
                    self._run_task(method, method._task_interval)
                )
                handles.append(handle)
        if handles:
            self._task_handles[id(plugin)] = handles

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
    async def _run_task(method: Callable, interval: float) -> None:
        """Run a plugin task method in a loop, sleeping between calls."""
        while True:
            try:
                await method()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in task %r", getattr(method, "__name__", method))
            await asyncio.sleep(interval)

    # ── Subcommand groups ──────────────────────────────────────

    def add_group(self, group: SlashGroup) -> None:  # type: ignore[name-defined]
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
        )

        for _, method in inspect.getmembers(group, predicate=inspect.ismethod):
            if getattr(method, "_is_slash", False):
                callback = self._build_slash_callback(
                    method,
                    guild_only=getattr(method, "_slash_guild_only", False),
                    ephemeral=getattr(method, "_slash_ephemeral", False),
                    permissions=getattr(method, "_slash_permissions", None),
                    cooldown=getattr(method, "_slash_cooldown", None),
                )
                _choices = getattr(method, "_slash_choices", None)
                if _choices:
                    self._inject_choices(callback, _choices)
                cmd = app_commands.Command(
                    name=method._slash_name,
                    description=method._slash_desc,
                    callback=callback,
                )
                for param_name, handler in getattr(method, "_slash_autocomplete", {}).items():
                    async def _ac(_: discord.Interaction, current: str, _h: Callable = handler) -> list[app_commands.Choice]:
                        results = await _h(current)
                        return [app_commands.Choice(name=r, value=r) for r in results]
                    cmd.autocomplete(param_name)(_ac)
                discord_group.add_command(cmd)
            if getattr(method, "_is_event", False):
                self._event_handlers.setdefault(method._event_name, []).append(method)

        guild = discord.Object(id=group._group_guild) if group._group_guild else None
        self.tree.add_command(discord_group, guild=guild)

        if self.is_ready():
            asyncio.create_task(group.on_load())
            self._start_plugin_tasks(group)

    # ── Context menus ─────────────────────────────────────────

    def user_command(
        self,
        name: str | None = None,
        *,
        guild_id: int | None = None,
    ) -> Callable:
        """Decorator that registers a right-click User context menu command.

        The handler receives ``(ctx, member)`` where ``member`` is the
        right-clicked user as a ``discord.Member | discord.User``.

        Example::

            @bot.user_command(name="User Info")
            async def user_info(ctx, member):
                await ctx.respond(f"{member.display_name} joined {member.guild.name}.")
        """
        def decorator(func: Callable) -> Callable:
            self._register_context_menu(
                func,
                name=name or func.__name__,
                menu_type=discord.AppCommandType.user,
                guild_id=guild_id,
            )
            return func
        return decorator

    def message_command(
        self,
        name: str | None = None,
        *,
        guild_id: int | None = None,
    ) -> Callable:
        """Decorator that registers a right-click Message context menu command.

        The handler receives ``(ctx, message)`` where ``message`` is the
        right-clicked ``discord.Message``.

        Example::

            @bot.message_command(name="Quote")
            async def quote(ctx, message):
                await ctx.respond(f"> {message.content[:100]}")
        """
        def decorator(func: Callable) -> Callable:
            self._register_context_menu(
                func,
                name=name or func.__name__,
                menu_type=discord.AppCommandType.message,
                guild_id=guild_id,
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
    ) -> None:
        """Build and register an app_commands.ContextMenu from a user-provided handler."""
        guild = discord.Object(id=guild_id) if guild_id else None
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        target_name = params[1].name if len(params) > 1 else "target"

        # Annotation tells discord.py what type to inject as the second argument.
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

        callback.__signature__ = inspect.Signature(parameters=[interaction_param, target_param])

        menu = app_commands.ContextMenu(name=name, callback=callback)
        self.tree.add_command(menu, guild=guild)

    # ── User & member lookup ──────────────────────────────────

    async def fetch_member(self, guild_id: int, user_id: int) -> discord.Member:
        """Fetch a guild member by guild ID and user ID.

        Tries the cache first; falls back to an API call if the guild is not
        cached. Raises ``discord.NotFound`` if the user is not in the guild.

        Example::

            member = await bot.fetch_member(ctx.guild.id, stored_user_id)
            await ctx.kick(member, reason="Delayed action")
        """
        guild = self.get_guild(guild_id) or await super().fetch_guild(guild_id)
        return await guild.fetch_member(user_id)

    async def fetch_user(self, user_id: int) -> discord.User:
        """Fetch a Discord user by ID (not guild-specific).

        Checks the internal cache first; falls back to an API call.
        Raises ``discord.NotFound`` if no user with that ID exists.

        Example::

            user = await bot.fetch_user(stored_user_id)
            await user.send("Hello from the bot!")
        """
        return self.get_user(user_id) or await super().fetch_user(user_id)

    # ── Presence ──────────────────────────────────────────────

    async def set_status(
        self,
        status: Literal["online", "idle", "dnd", "invisible"] = "online",
        *,
        activity: str | None = None,
        activity_type: Literal["playing", "watching", "listening"] = "playing",
    ) -> None:
        """Set the bot's presence status and optional activity text.

        Parameters
        ----------
        status:
            One of ``"online"``, ``"idle"``, ``"dnd"``, or ``"invisible"``.
        activity:
            Display text shown next to the status. ``None`` clears it.
        activity_type:
            One of ``"playing"``, ``"watching"``, or ``"listening"``.

        Example::

            await bot.set_status("idle", activity="Taking a break", activity_type="watching")
        """
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        discord_status = status_map.get(status, discord.Status.online)

        discord_activity: discord.BaseActivity | None = None
        if activity is not None:
            if activity_type == "playing":
                discord_activity = discord.Game(activity)
            elif activity_type == "watching":
                discord_activity = discord.Activity(type=discord.ActivityType.watching, name=activity)
            elif activity_type == "listening":
                discord_activity = discord.Activity(type=discord.ActivityType.listening, name=activity)
            else:
                discord_activity = discord.Game(activity)

        await self.change_presence(status=discord_status, activity=discord_activity)

    # ── Run ───────────────────────────────────────────────────

    def run(self, token: str, **kwargs) -> None:  # type: ignore[override]
        """Configure basic logging and start the bot."""
        logging.basicConfig(level=logging.INFO)
        super().run(token, **kwargs)


# Imported here to avoid a circular import at module level while still allowing
# the type annotation in add_group to resolve at runtime.
from .group import SlashGroup  # noqa: E402
