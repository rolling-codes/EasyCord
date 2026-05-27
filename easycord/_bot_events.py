"""Event dispatch, middleware registration, and bot utility helpers."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Literal

import discord

from .middleware import MiddlewareFn

logger = logging.getLogger("easycord")


class _EventsMixin:
    """Mixin: event dispatch, middleware, presence, and lookup helpers."""

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

    def dispatch(self, event: str, /, *args, **kwargs) -> None:
        super().dispatch(event, *args, **kwargs)
        for handler in list(self._event_handlers.get(event, [])):
            task = asyncio.create_task(handler(*args, **kwargs))
            background_tasks = getattr(self, "_background_tasks", None)
            if background_tasks is not None:
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            task.add_done_callback(self._log_task_exception)

    def _log_task_exception(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            logger.exception("Unhandled error in event handler task", exc_info=exc)

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

    def on_error(self, func: Callable) -> Callable:
        """Register a global error handler called when any slash command raises an unhandled exception.

        Can be used as a decorator or called directly::

            @bot.on_error
            async def handle_error(ctx, error):
                await ctx.respond(f"Something went wrong: {error}", ephemeral=True)

        Only one handler can be registered. A second call overwrites the first.
        """
        if not callable(func):
            raise TypeError(
                f"error handler must be callable, got {type(func).__name__!r}"
            )
        self._error_handler = func
        return func

    async def _dispatch_framework_error(
        self,
        exc: Exception,
        ctx=None,
        plugin_name: str | None = None,
        plugin_instance=None,
    ) -> None:
        """Route an exception through plugin and global error handlers."""
        if plugin_instance is None and plugin_name is not None:
            for p in getattr(self, "_plugins", []):
                if getattr(p, "_instance_id", type(p).__name__) == plugin_name:
                    plugin_instance = p
                    break

        if plugin_instance is not None:
            from .plugin import Plugin as _Plugin
            if isinstance(plugin_instance, _Plugin):
                plugin_on_error = type(plugin_instance).on_error
                base_on_error = _Plugin.on_error
                if plugin_on_error is not base_on_error:
                    try:
                        await plugin_instance.on_error(ctx, exc)
                    except Exception as handler_exc:
                        logger.exception("Error in plugin on_error handler", exc_info=handler_exc)
                    return

        error_handler = getattr(self, "_error_handler", None)
        if error_handler is not None:
            try:
                await error_handler(ctx, exc)
            except Exception as handler_exc:
                logger.exception("Error in global on_error handler", exc_info=handler_exc)
            return

        logger.exception("Unhandled exception in framework interaction or task", exc_info=exc)

    # ── User & member lookup ──────────────────────────────────

    async def fetch_member(self, guild_id: int, user_id: int) -> discord.Member:
        """Fetch a guild member by guild ID and user ID.

        Tries the cache first; falls back to an API call.
        Raises ``discord.NotFound`` if the user is not in the guild.
        """
        guild = self.get_guild(guild_id) or await super().fetch_guild(guild_id)
        return await guild.fetch_member(user_id)

    async def fetch_user(self, user_id: int) -> discord.User:
        """Fetch a Discord user by ID (not guild-specific).

        Checks the internal cache first; falls back to an API call.
        Raises ``discord.NotFound`` if no user with that ID exists.
        """
        return self.get_user(user_id) or await super().fetch_user(user_id)

    # ── Presence ──────────────────────────────────────────────

    async def set_status(
        self,
        status: Literal["online", "idle", "dnd", "invisible"] = "online",
        *,
        activity: str | None = None,
        activity_type: Literal["playing", "watching", "listening", "streaming"] = "playing",
    ) -> None:
        """Set the bot's presence status and optional activity text."""
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
                discord_activity = discord.Activity(
                    type=discord.ActivityType.watching, name=activity
                )
            elif activity_type == "listening":
                discord_activity = discord.Activity(
                    type=discord.ActivityType.listening, name=activity
                )
            elif activity_type == "streaming":
                discord_activity = discord.Streaming(name=activity, url="")
            else:
                discord_activity = discord.Game(activity)
        await self.change_presence(status=discord_status, activity=discord_activity)

    # ── Component routing ─────────────────────────────────────

    def _register_component_handler(
        self,
        custom_id: str,
        func: Callable,
        source_plugin: str | None = None,
        *,
        ttl: float | None = None,
    ) -> None:
        """Internal helper to register a component handler with collision detection."""
        self.registry.register_component(custom_id, func, source_plugin, ttl=ttl) # type: ignore[attr-defined]

    def _register_modal_handler(self, custom_id: str, func: Callable, source_plugin: str | None = None) -> None:
        """Internal helper to register a modal handler with collision detection."""
        self.registry.register_modal(custom_id, func, source_plugin) # type: ignore[attr-defined]

    def component(self, id_or_func=None, *, ttl: float | None = None) -> Callable:
        """Decorator that registers a persistent component (button / select-menu) handler."""
        if callable(id_or_func):
            self._register_component_handler(id_or_func.__name__, id_or_func, ttl=ttl)
            return id_or_func

        custom_id: str = id_or_func  # type: ignore[assignment]

        def decorator(func: Callable) -> Callable:
            self._register_component_handler(custom_id, func, ttl=ttl)
            return func

        return decorator

    def modal(self, id_or_func=None) -> Callable:
        """Decorator that registers a persistent modal submission handler."""
        if callable(id_or_func):
            self._register_modal_handler(id_or_func.__name__, id_or_func)
            return id_or_func

        custom_id: str = id_or_func  # type: ignore[assignment]

        def decorator(func: Callable) -> Callable:
            self._register_modal_handler(custom_id, func)
            return func

        return decorator

    async def _dispatch_component(self, interaction: discord.Interaction) -> None:
        """Route a component interaction to its registered handler."""
        from .context import Context
        from .middleware import build_chain

        custom_id: str = (interaction.data or {}).get("custom_id", "")  # type: ignore[union-attr]

        entry, parsed = self.registry.resolve_component(custom_id)  # type: ignore[attr-defined]
        handler = entry["func"] if entry else None
        suffix: str | None = None

        if handler is None:
            for registered_id, candidate_entry in self.registry.components.items():  # type: ignore[attr-defined]
                if registered_id.endswith("_") and custom_id.startswith(registered_id):
                    handler = candidate_entry["func"]
                    suffix = custom_id[len(registered_id):]
                    entry = candidate_entry
                    break

        if handler is None:
            return

        ctx = Context(interaction)

        async def invoke() -> None:
            try:
                if parsed:
                    await handler(ctx, **parsed)
                elif suffix is not None:
                    await handler(ctx, suffix)
                else:
                    await handler(ctx)
            except Exception as exc:
                plugin_name = entry.get("source") if entry else None
                await self._dispatch_framework_error(exc, ctx=ctx, plugin_name=plugin_name)

        await build_chain(ctx, invoke, self._middleware)()  # type: ignore[attr-defined]

    async def _dispatch_modal(self, interaction: discord.Interaction) -> None:
        """Route a modal submission to its registered handler."""
        from .context import Context
        from .middleware import build_chain

        custom_id: str = (interaction.data or {}).get("custom_id", "")  # type: ignore[union-attr]

        entry = self.registry.modals.get(custom_id)  # type: ignore[attr-defined]
        handler = entry["func"] if entry else None
        
        if handler is None:
            return

        ctx = Context(interaction)
        
        # Parse components from the interaction data
        data = {}
        for row in (interaction.data or {}).get("components", []): # type: ignore[union-attr]
            for comp in row.get("components", []):
                data[comp["custom_id"]] = comp["value"]

        async def invoke() -> None:
            try:
                await handler(ctx, data)
            except Exception as exc:
                plugin_name = entry.get("source") if entry else None
                await self._dispatch_framework_error(exc, ctx=ctx, plugin_name=plugin_name)

        await build_chain(ctx, invoke, self._middleware)()  # type: ignore[attr-defined]

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Intercept component interactions and dispatch to registered handlers."""
        if interaction.type == discord.InteractionType.component:
            await self._dispatch_component(interaction)
        elif interaction.type == discord.InteractionType.modal_submit:
            await self._dispatch_modal(interaction)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Auto-create a database row when the bot joins a new guild."""
        db = getattr(self, "db", None)
        if db is None or not getattr(db, "auto_sync_guilds", True):
            return
        await db.ensure_guild(guild.id)
