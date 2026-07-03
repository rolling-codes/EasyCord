"""Callback builders for Discord application commands."""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, cast

import discord

logger = logging.getLogger("easycord")

# Entries idle longer than this (seconds) are eligible for background pruning.
_COOLDOWN_TTL = 3600.0
# How often the background sweep runs (seconds).
_COOLDOWN_SWEEP_INTERVAL = 600.0


async def _cooldown_sweep_loop(
    cooldown_last_used: dict[int, list[float]],
    cooldown_window: float,
) -> None:
    """Background task: remove stale bucket entries every sweep interval.

    An entry is stale when every timestamp it contains is older than the
    command's cooldown window *and* the entry has been idle for at least
    ``_COOLDOWN_TTL`` seconds.  Using ``max(cooldown_window, _COOLDOWN_TTL)``
    as the expiry threshold ensures short-window commands still get their
    entries pruned after a reasonable quiet period.
    """
    max_age = max(cooldown_window, _COOLDOWN_TTL)
    while True:
        await asyncio.sleep(_COOLDOWN_SWEEP_INTERVAL)
        now = time.monotonic()
        stale = [
            key
            for key, timestamps in list(cooldown_last_used.items())
            if all(now - ts >= max_age for ts in timestamps)
        ]
        if stale:
            for key in stale:
                cooldown_last_used.pop(key, None)
            logger.debug(
                "cooldown sweep: pruned %d stale bucket(s)", len(stale)
            )


def build_slash_callback(
    bot: Any,
    func: Callable,
    *,
    context_factory: Callable[[discord.Interaction], Any],
    chain_builder: Callable,
    guild_only: bool = False,
    require_admin: bool = False,
    ephemeral: bool = False,
    permissions: list[str] | None = None,
    bot_permissions: list[str] | None = None,
    cooldown: float | None = None,
    cooldown_rate: int = 1,
    cooldown_bucket: str = "user",
    premium_required: bool = False,
    command_name: str | None = None,
) -> Callable:
    """Build a discord.py-compatible slash callback."""
    sig = inspect.signature(func)
    user_params = list(sig.parameters.values())[1:]
    cooldown_last_used: dict[Any, list[float]] = {}
    if cooldown is not None:
        if cooldown_rate < 1:
            raise ValueError("cooldown_rate must be at least 1")
        if hasattr(bot, "_cooldown_registries"):
            bot._cooldown_registries.append((cooldown_last_used, cooldown))
    if cooldown_bucket not in {"user", "guild", "global"}:
        raise ValueError("cooldown_bucket must be 'user', 'guild', or 'global'")

    if cooldown is not None:
        # Schedule a background pruning task that removes stale bucket entries
        # every _COOLDOWN_SWEEP_INTERVAL seconds.  Without this, bucket keys
        # for users who issued a command once and went idle accumulate without
        # bound — the TTL sweep ensures memory is reclaimed periodically.
        # Per-invocation code below only ever touches the single key for the
        # current user/guild, so no O(n) full-dict scan happens on hot paths.
        background_tasks: set = getattr(bot, "_background_tasks", set())
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            sweep_task = loop.create_task(
                _cooldown_sweep_loop(cooldown_last_used, cooldown)
            )
            background_tasks.add(sweep_task)
            sweep_task.add_done_callback(background_tasks.discard)

    effective_permissions = list(permissions or [])
    if require_admin and "administrator" not in effective_permissions:
        effective_permissions.append("administrator")

    async def callback(interaction: discord.Interaction, **kwargs) -> None:
        ctx = context_factory(interaction)
        if ephemeral:
            ctx._force_ephemeral = True

        if ctx.guild is not None:
            _registry = getattr(bot, "registry", None)
            _check = getattr(bot, "is_plugin_enabled", None)
            if _registry is not None and _check is not None:
                _cmd = command_name or func.__name__
                # Registry keys are scoped: "global:<name>" for global commands,
                # "guild:<id>:<name>" for guild-restricted ones.
                _entry = (
                    _registry.slash_commands.get(f"global:{_cmd}")
                    or _registry.slash_commands.get(f"guild:{ctx.guild.id}:{_cmd}")
                )
                if _entry and _entry.source:
                    # entry.source stores _instance_id; resolve to plugin.name
                    _plugin_name: str = _entry.source
                    for _p in getattr(bot, "_plugins", []):
                        if getattr(_p, "_instance_id", None) == _entry.source:
                            _plugin_name = _p.name
                            break
                    if not _check(_plugin_name, ctx.guild.id):
                        await ctx.respond(
                            ctx.t(
                                "errors.plugin_disabled",
                                default="This feature is disabled in this server.",
                            ),
                            ephemeral=True,
                        )
                        return

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
                    p
                    for p in effective_permissions
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
            if bot_permissions:
                # Validate the *bot's* own permissions before running, so a
                # command that calls a privileged API (member.kick(), etc.) fails
                # fast with a clear message instead of executing and raising
                # Forbidden partway through. Distinct from the user check above.
                if not ctx.guild:
                    await ctx.respond(
                        ctx.t(
                            "errors.guild_only",
                            default="This command can only be used inside a server.",
                        ),
                        ephemeral=True,
                    )
                    return
                bot_perms = ctx.bot_permissions
                missing_bot = [
                    p for p in bot_permissions if not getattr(bot_perms, p, False)
                ]
                if missing_bot:
                    await ctx.respond(
                        ctx.t(
                            "errors.bot_permissions_missing",
                            default="I'm missing the following permission(s): {permissions}.",
                            permissions=", ".join(missing_bot),
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
                # O(1) key lookup; filter only this user's timestamps (bounded
                # by cooldown_rate — typically 1–5 entries, never the full dict).
                used_at = [
                    ts
                    for ts in cooldown_last_used.get(bucket_key, [])
                    if now - ts < cooldown
                ]
                if not used_at:
                    cooldown_last_used.pop(bucket_key, None)
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
                cooldown_last_used[bucket_key] = used_at
            try:
                await func(ctx, **kwargs)
            except Exception as exc:
                per_cmd = (
                    getattr(bot, "_command_error_handlers", {}).get(command_name)
                    if command_name
                    else None
                )
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
                if bot._error_handler is not None:
                    await bot._error_handler(ctx, exc)
                else:
                    raise

        # When dev hot-reload is active, serialize against plugin swaps so a
        # command never executes against a half-removed registry. In production
        # the flag is falsy and this stays a lock-free fast path.
        reload_lock = getattr(bot, "_reload_lock", None)
        if reload_lock is not None and getattr(bot, "_hot_reload_active", False):
            async with reload_lock:
                await chain_builder(ctx, invoke, bot._middleware)()
        else:
            await chain_builder(ctx, invoke, bot._middleware)()

    interaction_param = inspect.Parameter(
        "interaction",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=discord.Interaction,
    )
    cast(Any, callback).__signature__ = sig.replace(
        parameters=[interaction_param] + user_params
    )
    return callback


def build_context_menu_callback(
    bot: Any,
    func: Callable,
    *,
    context_factory: Callable[[discord.Interaction], Any],
    chain_builder: Callable,
) -> Callable:
    """Build the callback wrapper used by app command context menus."""

    async def callback(interaction: discord.Interaction, target) -> None:
        ctx = context_factory(interaction)

        async def invoke() -> None:
            await func(ctx, target)

        await chain_builder(ctx, invoke, bot._middleware)()

    return callback
