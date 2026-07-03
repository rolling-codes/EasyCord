"""Bot shell wiring together the mixin modules."""
from __future__ import annotations

import asyncio
import math
import os
import time
import logging
from typing import Callable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .plugins._ai_providers import AIProviderProtocol

import discord
from discord import app_commands

from .builtin_plugins import build_builtin_plugins
from .context import Context
from .database import DatabaseConfig, EasyCordDatabase, MemoryDatabase, SQLiteDatabase
from .i18n import LocalizationManager
from .conversation_memory import ConversationMemory
from .middleware import MiddlewareFn
from .plugin import Plugin
from ._bot_commands import _CommandsMixin
from ._bot_events import _EventsMixin
from ._bot_guild import _GuildMixin
from ._bot_plugins import _PluginsMixin
from .registry import InteractionRegistry
from .event_bus import EventBus
from .tools import ToolRegistry
from .builtin_tools import register_builtin_tools

logger = logging.getLogger("easycord")


class Bot(_EventsMixin, _GuildMixin, _PluginsMixin, _CommandsMixin, discord.Client):
    """
    The main bot — a discord.Client with slash commands,
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
    sync_guild_id:
        Optional development guild ID. When set, auto-sync copies global
        commands into that guild and syncs the guild command set instead of
        publishing commands globally.
    """

    def __init__(
        self,
        *,
        intents: discord.Intents | None = None,
        auto_sync: bool = True,
        sync_guild_id: int | None = None,
        load_builtin_plugins: bool = False,
        database: EasyCordDatabase | None = None,
        db_backend: str | None = None,
        db_path: str | None = None,
        db_auto_sync_guilds: bool | None = None,
        guild_sync_timeout: float | None = 30.0,
        localization: LocalizationManager | None = None,
        default_locale: str = "en-US",
        translations: dict | None = None,
        auto_translator: Callable[[str, str, str], str | None] | None = None,
        ai_provider: AIProviderProtocol | None = None,
        enable_conversation_memory: bool = False,
        enable_health_command: bool = False,
        cooldown_cleanup_interval: float = 600.0,
        **kwargs,
    ) -> None:
        super().__init__(intents=intents or discord.Intents.default(), **kwargs)
        self.tree = app_commands.CommandTree(self)
        self._auto_sync = auto_sync
        self._sync_guild_id = sync_guild_id
        self._guild_sync_timeout = guild_sync_timeout
        self._middleware: list[MiddlewareFn] = []
        self._event_handlers: dict[str, list[Callable]] = {}
        self._plugins: list[Plugin] = []
        self._task_handles: dict[int, list[asyncio.Task]] = {}
        self._task_statuses: dict[str, dict[str, Any]] = {}
        self._background_tasks: set[asyncio.Task] = set()
        self._webhooks: dict[int, discord.Webhook] = {}
        self.cooldown_cleanup_interval = cooldown_cleanup_interval
        self._cooldown_registries: list[tuple[dict[Any, list[float]], float]] = []
        self.registry = InteractionRegistry()
        self.ai_provider = ai_provider
        self.conversation_memory = (
            ConversationMemory() if enable_conversation_memory else None
        )
        self.ai_tools: dict[str, dict] = {}
        self.event_bus = EventBus()
        self.tool_registry = ToolRegistry()
        try:
            register_builtin_tools(self.tool_registry)
        except Exception as e:
            logger.debug(f"Failed to register builtin AI tools: {e}")
        self._error_handler = None
        self._command_error_handlers: dict[str, object] = {}
        self.db = database or self._create_database(
            db_backend=db_backend,
            db_path=db_path,
            db_auto_sync_guilds=db_auto_sync_guilds,
        )
        self.localization: LocalizationManager | None = localization or (
            LocalizationManager(
                default_locale=default_locale,
                translations=translations,
                auto_translator=auto_translator,
            )
            if translations or auto_translator
            else None
        )
        if load_builtin_plugins:
            self.load_builtin_plugins()
        if enable_health_command:
            self._register_health_command()
        self._start_time = time.time()

    # ── Interaction inspection and command sync planning ──────

    def inspect_interactions(self) -> dict[str, list[dict[str, Any]]]:
        """Return registered interactions grouped by EasyCord interaction type."""
        return self.registry.grouped()

    def plan_command_sync(
        self,
        *,
        guild_id: int | None = None,
        remote_commands: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Build a command sync diff without contacting Discord by default.

        Pass ``remote_commands`` in tests or after your own fetch to compare the
        current EasyCord inventory with Discord's current command names.
        """
        local_entries = self.registry.iter_syncable(guild_id=guild_id)
        local_names = [entry.name for entry in local_entries if entry.enabled]
        remote_names = list(remote_commands or [])

        warnings: list[str] = []
        duplicates = sorted({name for name in local_names if local_names.count(name) > 1})
        for name in duplicates:
            warnings.append(f"Duplicate local command name: {name}")

        local_set = set(local_names)
        remote_set = set(remote_names)
        return {
            "added": sorted(local_set - remote_set),
            "changed": [],
            "removed": sorted(remote_set - local_set),
            "unchanged": sorted(local_set & remote_set),
            "warnings": warnings,
        }

    async def sync_commands(
        self,
        *,
        guild_id: int | None = None,
        dry_run: bool = False,
        remote_commands: list[str] | None = None,
        confirm_removals: bool = False,
    ) -> dict[str, list[str]]:
        """Plan or execute command sync through ``discord.py``'s CommandTree.

        If the plan detects removals, pass ``confirm_removals=True`` before a
        non-dry-run sync. This keeps EasyCord from applying a destructive sync
        without an explicit caller decision.
        """
        plan = self.plan_command_sync(
            guild_id=guild_id,
            remote_commands=remote_commands,
        )
        if dry_run:
            return plan
        if plan["removed"] and not confirm_removals:
            raise RuntimeError(
                "Command sync would remove remote commands. Re-run with "
                "confirm_removals=True after reviewing plan_command_sync()."
            )
        guild = discord.Object(id=guild_id) if guild_id is not None else None
        if guild is not None:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        for entry in self.registry.iter_syncable(guild_id=guild_id):
            entry.sync_state = "synced"
        return plan

    async def use_google_translate(self) -> None:
        """Wire Google Translate into the command tree for localized command names.

        After calling this, the next ``sync_commands()`` will translate every
        command name into all Discord-supported locales using Google Translate.
        Users then see commands in their own language (e.g. French users see
        ``/traduire`` instead of ``/translate``); the interaction payload always
        carries the canonical name so no routing changes are required.

        Requires the ``deep-translator`` package::

            pip install "easycord[translate]"
        """
        from easycord.helpers.google_translate import GoogleTranslateTranslator

        await self.tree.set_translator(GoogleTranslateTranslator())

    def enable_interaction_inspector(self, *, owner_ids: set[int] | None = None) -> None:
        """Register the optional ``/easycord interactions`` developer command."""
        group = app_commands.Group(
            name="easycord",
            description="EasyCord developer diagnostics",
        )

        @group.command(name="interactions", description="Show registered EasyCord interactions")
        async def interactions(interaction: discord.Interaction) -> None:
            if owner_ids is not None and interaction.user.id not in owner_ids:
                await interaction.response.send_message("Not authorized.", ephemeral=True)
                return
            grouped = self.inspect_interactions()
            lines = [
                f"{kind}: {len(entries)}"
                for kind, entries in grouped.items()
            ]
            await interaction.response.send_message("\n".join(lines), ephemeral=True)

        self.tree.add_command(group)
    
    def _register_health_command(self) -> None:
        """Register the global ``/health`` command."""

        async def health(ctx: Context) -> None:
            from . import __version__
            import asyncio
            import threading

            # Calculate uptime
            uptime = time.time() - self._start_time
            hours, rem = divmod(int(uptime), 3600)
            minutes, seconds = divmod(rem, 60)

            # Measure event loop latency
            loop = asyncio.get_running_loop()
            start = loop.time()
            await asyncio.sleep(0)
            loop_latency = (loop.time() - start) * 1000

            embed = discord.Embed(
                title="Bot Health & Telemetry",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            latency = self.latency
            api_latency = (
                f"{round(latency * 1000)}ms"
                if math.isfinite(latency)
                else "unavailable"
            )
            embed.add_field(name="API Latency", value=api_latency)
            embed.add_field(name="Loop Latency", value=f"{loop_latency:.2f}ms")
            embed.add_field(name="Uptime", value=f"{hours}h {minutes}m {seconds}s")
            embed.add_field(name="Guilds", value=str(len(self.guilds)))
            embed.add_field(name="Threads", value=str(threading.active_count()))

            # Memory usage (requires psutil)
            try:
                import psutil
                process = psutil.Process()
                mem = process.memory_info().rss / (1024 * 1024)
                embed.add_field(name="Memory", value=f"{mem:.1f} MB")
            except ImportError:
                pass  # psutil is an optional dependency; skip the memory field if missing

            registry = self.registry.grouped()
            counts = [f"{k.title()}: {len(v)}" for k, v in registry.items()]
            embed.add_field(name="Registry", value="\n".join(counts))
            from .database import MemoryDatabase, SQLiteDatabase
            try:
                db_latency = await self.db.ping()
                db_lines = [type(self.db).__name__, f"Latency: {db_latency:.1f}ms"]
                if isinstance(self.db, SQLiteDatabase) and self.db.path:
                    db_lines.append(f"Path: {self.db.path}")
                if isinstance(self.db, MemoryDatabase):
                    db_lines.append(f"Records: {self.db.record_count}")
                db_value = "\n".join(db_lines)
            except Exception as exc:
                db_value = f"{type(self.db).__name__}\nError: {exc}"
            embed.add_field(name="Database", value=db_value)
            embed.add_field(name="Version", value=f"v{__version__}")

            if self._plugins:
                plugin_list = []
                for p in self._plugins:
                    ver = getattr(p, "version", "1.0.0")
                    plugin_list.append(f"{p.name} (v{ver})")
                embed.add_field(
                    name="Plugins", value="\n".join(plugin_list), inline=False
                )

            await ctx.respond(embed=embed, ephemeral=True)

        self._register_slash(
            health,
            name="health",
            description="Show bot health and status",
            guild_id=None,
            ephemeral=True,
        )

    def _create_database(
        self,
        *,
        db_backend: str | None,
        db_path: str | None,
        db_auto_sync_guilds: bool | None,
    ) -> EasyCordDatabase:
        config = DatabaseConfig.from_env()
        backend = db_backend or config.backend
        path = db_path or os.getenv("EASYCORD_DB_PATH") or config.path
        auto_sync = config.auto_sync_guilds if db_auto_sync_guilds is None else db_auto_sync_guilds

        if backend == "memory":
            return MemoryDatabase(auto_sync_guilds=auto_sync)
        if backend == "sqlite":
            return SQLiteDatabase(path=path, auto_sync_guilds=auto_sync)
        raise ValueError(
            f"Unknown database backend {backend!r}. Must be 'sqlite' or 'memory'."
        )

    def load_builtin_plugins(self) -> None:
        """Load the framework's bundled first-party plugins."""
        loaded_types = {type(plugin) for plugin in self._plugins}
        for plugin in build_builtin_plugins():
            if type(plugin) in loaded_types:
                continue
            self.add_plugin(plugin)
            loaded_types.add(type(plugin))

    async def _sync_guilds_with_timeout(self) -> None:
        """Run ``db.sync_guilds`` bounded by ``_guild_sync_timeout``.

        When a positive timeout is configured the sync is wrapped in
        ``asyncio.wait_for``; on expiry a warning is logged and startup
        continues uninterrupted.  Pass ``guild_sync_timeout=None`` (or
        ``<=0``) to opt out and restore the original unbounded behaviour.

        Note: cancellation is suppressed to avoid interrupting DB operations
        mid-lock, which could cause corruption. The task continues in the
        background but we stop waiting for it.
        """
        guild_ids = [guild.id for guild in getattr(self, "guilds", [])]
        timeout = self._guild_sync_timeout
        if timeout is not None and timeout > 0:
            task = asyncio.create_task(self.db.sync_guilds(guild_ids))
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Guild sync timed out after %.1fs for %d guild(s); "
                    "startup will continue without a complete sync. "
                    "Sync continues in background.",
                    timeout,
                    len(guild_ids),
                )
        else:
            await self.db.sync_guilds(guild_ids)

    async def setup_hook(self) -> None:
        await self.db.ensure_schema()
        if self.db.auto_sync_guilds:
            await self._sync_guilds_with_timeout()
        if self._auto_sync:
            if self._sync_guild_id is not None:
                guild = discord.Object(id=self._sync_guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()
        for plugin in self._plugins:
            await plugin.on_load()
            self._start_plugin_tasks(plugin)
        if getattr(self, "_dev_reload", False):
            task = asyncio.create_task(self._hot_reload_loop())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            task.add_done_callback(self._log_task_exception)

        cleanup_task = asyncio.create_task(self._cooldown_cleanup_loop())
        self._background_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self._background_tasks.discard)
        cleanup_task.add_done_callback(self._log_task_exception)

    def _prune_cooldown_registries(self, now: float) -> None:
        """Prune expired timestamps from all cooldown registries."""
        for cooldown_dict, window in self._cooldown_registries:
            try:
                for key in list(cooldown_dict.keys()):
                    entry = cooldown_dict.get(key)
                    if entry is None:
                        continue
                    valid = [ts for ts in entry if now - ts < window]
                    if valid:
                        cooldown_dict[key] = valid
                    else:
                        cooldown_dict.pop(key, None)
            except Exception:
                logger.exception("Error pruning cooldown registry; skipping")

    async def _cooldown_cleanup_loop(self) -> None:
        """Periodically prune expired cooldown entries to prevent memory leaks."""
        while True:
            await asyncio.sleep(self.cooldown_cleanup_interval)
            self._prune_cooldown_registries(time.monotonic())

    async def on_ready(self) -> None:
        if self.db.auto_sync_guilds:
            await self._sync_guilds_with_timeout()
        for plugin in self._plugins:
            try:
                await plugin.on_ready()
            except Exception:
                logger.exception("Error calling on_ready for %s", plugin.__class__.__name__)

        for plugin in self._plugins:
            try:
                self._validate_plugin_permissions(plugin)
            except Exception:
                logger.debug("Permission validation failed for %s", plugin.__class__.__name__, exc_info=True)

        # Startup diagnostics summary
        from . import __version__
        diag = [
            f"EasyCord v{__version__}",
            f"Guilds: {len(self.guilds)}",
            f"Plugins: {len(self._plugins)}",
            f"Commands: {len(self.registry.slash_commands)}",
            f"Components: {len(self.registry.components)}",
            f"DB: {type(self.db).__name__.replace('Database', '')}",
            f"Sync Mode: {'Guild' if self._sync_guild_id else 'Global'}",
        ]
        print("\n" + "─" * 30)
        for line in diag:
            print(f" {line}")
        print("─" * 30 + "\n")
        
        user = self.user
        if user is not None:
            logger.info("Logged in as %s (ID: %s)", user, user.id)
        else:
            logger.info("EasyCord on_ready completed without a cached bot user")

    async def close(self) -> None:  # type: ignore[override]
        """Close the bot and release framework-owned resources.

        Cancels plugin background loops and one-shot framework tasks before
        closing Discord and database resources. This prevents lingering task
        references from keeping plugin/bot state alive after shutdown.
        """
        pending: list[asyncio.Task] = []
        for handles in self._task_handles.values():
            pending.extend(handles)
        pending.extend(getattr(self, "_background_tasks", set()))

        for task in pending:
            if not task.done():
                task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        self._task_handles.clear()
        getattr(self, "_background_tasks", set()).clear()

        try:
            await self.db.close()
        finally:
            await super().close()

    def run(self, token: str, *, reload: bool = False, **kwargs) -> None:  # type: ignore[override]
        """Configure basic logging and start the bot.

        Parameters
        ----------
        reload:
            When ``True``, watch plugin files for changes and hot-reload any that
            are modified without restarting the bot. Intended for development only.

            Limitations: plugins with ``__init__`` arguments cannot be re-instantiated
            automatically, and changes to shared helper modules are not detected.
            ``sync_commands()`` is not called after a reload — do it manually if
            command signatures change.

        Example::

            # Production
            bot.run(os.environ["DISCORD_TOKEN"])

            # Development — hot-reload plugins on file change
            bot.run(os.environ["DISCORD_TOKEN"], reload=True)
        """
        self._dev_reload = reload
        if reload and self._auto_sync:
            logger.warning(
                "bot.run(reload=True) is intended for development only. "
                "Running with auto_sync=True suggests a production environment. "
                "Guard with: if os.environ.get('EASYCORD_ENV') == 'development': bot.run(token, reload=True)"
            )
        logging.basicConfig(level=logging.INFO)
        super().run(token, **kwargs)


# Imported here to avoid a circular import at module level while still allowing
# the type annotation in add_group to resolve at runtime.
