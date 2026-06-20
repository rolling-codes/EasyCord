"""Callback builders for Discord application commands."""
from __future__ import annotations

import inspect
import time
from typing import Any, Callable, cast

import discord


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
    cooldown: float | None = None,
    cooldown_rate: int = 1,
    cooldown_bucket: str = "user",
    premium_required: bool = False,
    command_name: str | None = None,
) -> Callable:
    """Build a discord.py-compatible slash callback."""
    sig = inspect.signature(func)
    user_params = list(sig.parameters.values())[1:]
    cooldown_last_used: dict[int, list[float]] = {}
    if cooldown is not None and cooldown_rate < 1:
        raise ValueError("cooldown_rate must be at least 1")
    if cooldown_bucket not in {"user", "guild", "global"}:
        raise ValueError("cooldown_bucket must be 'user', 'guild', or 'global'")

    effective_permissions = list(permissions or [])
    if require_admin and "administrator" not in effective_permissions:
        effective_permissions.append("administrator")

    async def callback(interaction: discord.Interaction, **kwargs) -> None:
        ctx = context_factory(interaction)
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
