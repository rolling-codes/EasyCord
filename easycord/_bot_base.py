"""Type-checking-only base describing the composed :class:`Bot` surface.

The ``_bot_*`` modules each define a mixin that is combined into the concrete
:class:`~easycord.bot.Bot` (alongside :class:`discord.Client`).  Checked in
isolation a mixin cannot see the state created in ``Bot.__init__`` nor the
helpers contributed by its sibling mixins, which produces a cascade of spurious
``reportAttributeAccessIssue`` errors.

Every mixin inherits this class **only under ``TYPE_CHECKING``** (via the
``_MixinBase`` alias each module defines); at runtime the base is plain
``object``, so the composed ``Bot`` MRO and behaviour are unchanged.  This class
is never instantiated — it exists solely to give static checkers the shape of
the host object that the mixins are bolted onto.

The ``discord.Client`` surface the mixins reach for is declared here as plain
callables rather than by inheriting :class:`discord.Client`.  Inheriting Client
would make the mixins' *intentional* method overrides (``on_error`` as a
decorator, the guild/channel ``fetch_*`` wrappers) report as incompatible
overrides and would surface unrelated discord.py optional-typing friction.  The
mixins' own ``fetch_*`` wrappers keep their precise return types on the composed
``Bot``.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    import discord
    from discord import app_commands

    from .conversation_memory import ConversationMemory
    from .database import EasyCordDatabase
    from .event_bus import EventBus
    from .hooks import HookRegistry
    from .i18n import LocalizationManager
    from .middleware import MiddlewareFn
    from .plugin import Plugin
    from .registry import InteractionRegistry
    from .tools import ToolRegistry


class _BotBase:
    """Declares ``Bot``'s composed attribute surface for isolated mixin checks."""

    # ── State created in ``Bot.__init__`` ─────────────────────
    tree: app_commands.CommandTree[Any]
    registry: InteractionRegistry
    tool_registry: ToolRegistry
    event_bus: EventBus
    hooks: HookRegistry
    db: EasyCordDatabase
    localization: LocalizationManager | None
    conversation_memory: ConversationMemory | None
    ai_provider: Any
    ai_tools: dict[str, dict[str, Any]]
    _middleware: list[MiddlewareFn]
    _event_handlers: dict[str, list[Callable[..., Any]]]
    _command_error_handlers: dict[str, object]
    _error_handler: Callable[..., Any] | None
    _plugins: list[Plugin]
    _task_handles: dict[int, list[asyncio.Task[Any]]]
    _task_statuses: dict[str, dict[str, Any]]
    _background_tasks: set[asyncio.Task[Any]]
    _webhooks: dict[int, discord.Webhook]
    _auto_sync: bool
    _sync_guild_id: int | None
    _start_time: float

    # ── discord.Client surface the mixins reach for ───────────
    dispatch: Callable[..., Any]
    get_guild: Callable[..., Any]
    get_user: Callable[..., Any]
    get_channel: Callable[..., Any]
    fetch_guild: Callable[..., Any]
    fetch_user: Callable[..., Any]
    fetch_channel: Callable[..., Any]
    change_presence: Callable[..., Any]
    is_ready: Callable[..., Any]

    # ── Helpers contributed by sibling mixins ─────────────────
    _register_slash: Callable[..., Any]
    _register_context_menu: Callable[..., Any]
    _register_component_handler: Callable[..., Any]
    _register_modal_handler: Callable[..., Any]
    add_group: Callable[..., Any]
    _dispatch_framework_error: Callable[..., Any]
    _log_task_exception: Callable[..., Any]
    _scan_methods: Callable[..., Any]
    _start_plugin_tasks: Callable[..., Any]
    reload_plugin: Callable[..., Any]
