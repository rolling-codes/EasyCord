from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Awaitable, Callable

import discord
from discord import app_commands

from .context import Context
from .middleware import MiddlewareFn
from .plugin import Plugin

logger = logging.getLogger("easycord")


def _wrap(
    mw: MiddlewareFn,
    ctx: Context,
    proceed: Callable[[], Awaitable[None]],
) -> Callable[[], Awaitable[None]]:
    """Return a zero-arg coroutine that calls mw(ctx, proceed)."""
    async def step() -> None:
        await mw(ctx, proceed)
    return step


def _build_chain(
    ctx: Context,
    invoke: Callable[[], Awaitable[None]],
    middleware: list[MiddlewareFn],
) -> Callable[[], Awaitable[None]]:
    """Wrap invoke in the full middleware stack so the first middleware runs first."""
    chain = invoke
    for mw in reversed(middleware):
        chain = _wrap(mw, ctx, chain)
    return chain


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

    # ── Lifecycle ─────────────────────────────────────────────

    async def setup_hook(self) -> None:
        if self._auto_sync:
            await self.tree.sync()
        for plugin in self._plugins:
            await plugin.on_load()

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)  # type: ignore[union-attr]

    def dispatch(self, event: str, /, *args, **kwargs) -> None:
        super().dispatch(event, *args, **kwargs)
        # Snapshot the list so handlers that modify _event_handlers mid-loop
        # don't cause a RuntimeError or silently skip handlers.
        for handler in list(self._event_handlers.get(event, [])):
            asyncio.create_task(handler(*args, **kwargs))

    # ── Slash commands ────────────────────────────────────────

    def slash(
        self,
        name: str | None = None,
        *,
        description: str = "No description provided.",
        guild_id: int | None = None,
    ) -> Callable:
        """Decorator that registers a top-level slash command.

        Example::

            @bot.slash(description="Say hello")
            async def hello(ctx, name: str):
                await ctx.respond(f"Hello, {name}!")
        """

        def decorator(func: Callable) -> Callable:
            self._register_slash(
                func,
                name=name or func.__name__,
                description=description,
                guild_id=guild_id,
            )
            return func

        return decorator

    def _register_slash(
        self,
        func: Callable,
        *,
        name: str,
        description: str,
        guild_id: int | None,
    ) -> None:
        """Register a callable as a slash command in discord.py's app-command tree.

        Works for both plain functions (@bot.slash) and bound plugin methods
        (@slash inside a Plugin). In both cases the first parameter is ctx;
        discord.py infers the remaining typed parameters as command options.
        """
        guild = discord.Object(id=guild_id) if guild_id else None
        sig = inspect.signature(func)
        user_params = list(sig.parameters.values())[1:]  # skip ctx (or self for bound methods)

        async def callback(interaction: discord.Interaction, **kwargs) -> None:
            ctx = Context(interaction)

            async def invoke() -> None:
                await func(ctx, **kwargs)

            await _build_chain(ctx, invoke, self._middleware)()

        interaction_param = inspect.Parameter(
            "interaction",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=discord.Interaction,
        )
        callback.__signature__ = sig.replace(
            parameters=[interaction_param] + user_params
        )
        self.tree.add_command(
            app_commands.Command(name=name, description=description, callback=callback),
            guild=guild,
        )

    # ── Events ────────────────────────────────────────────────

    def on(self, event: str) -> Callable:  # type: ignore[override]
        """Decorator that registers an event listener.

        Use the event name without the ``on_`` prefix::

            @bot.on("member_join")
            async def welcome(member):
                await member.send("Welcome!")
        """

        def decorator(func: Callable) -> Callable:
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
        self._middleware.append(middleware)
        return middleware

    # ── Plugins ───────────────────────────────────────────────

    def add_plugin(self, plugin: Plugin) -> None:
        """Add a plugin, registering all of its slash commands and event handlers.

        Raises ``ValueError`` if the same plugin instance has already been added.
        """
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
                )
            if getattr(method, "_is_event", False):
                self._event_handlers.setdefault(method._event_name, []).append(method)

        if self.is_ready():
            asyncio.create_task(plugin.on_load())

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

        await plugin.on_unload()

    # ── Run ───────────────────────────────────────────────────

    def run(self, token: str, **kwargs) -> None:  # type: ignore[override]
        """Configure basic logging and start the bot."""
        logging.basicConfig(level=logging.INFO)
        super().run(token, **kwargs)
