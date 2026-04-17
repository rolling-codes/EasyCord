"""Built-in middleware factories and chain-builder utilities for EasyCord bots."""
from __future__ import annotations

import contextlib
import logging
import time
from collections import defaultdict
from typing import Awaitable, Callable

from .context import Context

MiddlewareFn = Callable[[Context, Callable[[], Awaitable[None]]], Awaitable[None]]


# ── Middleware chain helpers ───────────────────────────────────────────────────

def _wrap(
    mw: MiddlewareFn,
    ctx: Context,
    proceed: Callable[[], Awaitable[None]],
) -> Callable[[], Awaitable[None]]:
    """Return a zero-arg coroutine that calls mw(ctx, proceed)."""
    async def step() -> None:
        await mw(ctx, proceed)
    return step


def build_chain(
    ctx: Context,
    invoke: Callable[[], Awaitable[None]],
    middleware: list[MiddlewareFn],
) -> Callable[[], Awaitable[None]]:
    """Wrap *invoke* in the full middleware stack so the first middleware runs first."""
    chain = invoke
    for mw in reversed(middleware):
        chain = _wrap(mw, ctx, chain)
    return chain


def dm_only() -> MiddlewareFn:
    """Block commands invoked inside a guild (i.e. only allow DMs)."""

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        if ctx.guild is not None:
            await ctx.respond(
                "This command can only be used in a direct message.", ephemeral=True
            )
            return
        await proceed()

    return handler


def allowed_roles(*role_ids: int, message: str = "You don't have the required role to use this command.") -> MiddlewareFn:
    """Block commands unless the invoking member holds at least one of *role_ids*.

    Silently passes when used outside a guild (DMs), so combine with
    ``guild_only()`` if the command must be server-only.

    Example::

        bot.use(allowed_roles(STAFF_ROLE_ID, ADMIN_ROLE_ID))
    """
    role_set = frozenset(role_ids)

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        if ctx.guild is None:
            await proceed()
            return
        member = ctx.guild.get_member(ctx.user.id)
        if member is None or role_set.isdisjoint(r.id for r in member.roles):
            await ctx.respond(message, ephemeral=True)
            return
        await proceed()

    return handler


def channel_only(
    *channel_ids: int,
    message: str = "This command cannot be used in this channel.",
) -> MiddlewareFn:
    """Block commands invoked outside of the specified channel(s).

    Passes silently when used outside a guild (DMs).

    Example::

        bot.use(channel_only(COMMANDS_CHANNEL_ID, BOT_CHANNEL_ID))
    """
    channel_set = frozenset(channel_ids)

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        if ctx.guild is None:
            await proceed()
            return
        if ctx.channel is None or ctx.channel.id not in channel_set:  # type: ignore[union-attr]
            await ctx.respond(message, ephemeral=True)
            return
        await proceed()

    return handler


def admin_only(
    message: str = "This command requires administrator permissions.",
) -> MiddlewareFn:
    """Block commands unless the invoking member has the administrator permission.

    Silently passes when used outside a guild (DMs), so combine with
    ``guild_only()`` if the command must be server-only.

    Example::

        bot.use(admin_only())
    """

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        if ctx.guild is None:
            await proceed()
            return
        member = ctx.guild.get_member(ctx.user.id)
        if member is None or not member.guild_permissions.administrator:
            await ctx.respond(message, ephemeral=True)
            return
        await proceed()

    return handler


def log_middleware(
    level: int = logging.INFO,
    fmt: str = "/{command} invoked by {user} in {guild}",
) -> MiddlewareFn:
    """Log every slash command invocation."""
    logger = logging.getLogger("easycord")

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        logger.log(
            level,
            fmt.format(
                command=ctx.command_name,
                user=ctx.user,
                guild=ctx.guild or "DM",
            ),
        )
        await proceed()

    return handler


def guild_only() -> MiddlewareFn:
    """Block commands invoked outside of a guild (i.e. in DMs)."""

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        if ctx.guild is None:
            await ctx.respond(
                "This command can only be used inside a server.", ephemeral=True
            )
            return
        await proceed()

    return handler


def rate_limit(
    limit: int = 5,
    window: float = 10.0,
) -> MiddlewareFn:
    """Per-user sliding-window rate limiter."""
    if limit < 1:
        raise ValueError("rate_limit: limit must be at least 1")
    if window <= 0:
        raise ValueError("rate_limit: window must be greater than 0")
    _history: dict[int, list[float]] = defaultdict(list)

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        uid = ctx.user.id
        now = time.monotonic()
        cutoff = now - window
        _history[uid] = [t for t in _history[uid] if t > cutoff]

        if len(_history[uid]) >= limit:
            wait = window - (now - _history[uid][0])
            await ctx.respond(
                f"You're being rate limited. Try again in {wait:.1f}s.",
                ephemeral=True,
            )
            return

        _history[uid].append(now)
        await proceed()

    return handler


def boost_only(
    message: str = "This command is for server boosters only.",
) -> MiddlewareFn:
    """Block commands unless the invoking member is currently boosting the server.

    Silently passes in DMs. Combine with ``guild_only()`` if the command must
    be server-only.

    Example::

        bot.use(boost_only())
    """

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        if ctx.guild is None:
            await proceed()
            return
        member = ctx.guild.get_member(ctx.user.id)
        if member is None or member.premium_since is None:
            await ctx.respond(message, ephemeral=True)
            return
        await proceed()

    return handler


def has_permission(
    *permissions: str,
    message: str | None = None,
) -> MiddlewareFn:
    """Block commands unless the invoking member holds all of the given permissions.

    ``permissions`` are ``discord.Permissions`` attribute names
    (e.g. ``"kick_members"``, ``"manage_messages"``).

    Silently passes in DMs. Combine with ``guild_only()`` if the command must
    be server-only.

    Example::

        bot.use(has_permission("kick_members", "ban_members"))
    """

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        if ctx.guild is None:
            await proceed()
            return
        member = ctx.guild.get_member(ctx.user.id)
        if member is None:
            await ctx.respond(
                message or "Could not verify your permissions.", ephemeral=True
            )
            return
        missing = [
            p for p in permissions
            if not getattr(member.guild_permissions, p, False)
        ]
        if missing:
            await ctx.respond(
                message or f"You need the following permission(s): {', '.join(missing)}.",
                ephemeral=True,
            )
            return
        await proceed()

    return handler


def catch_errors(
    message: str = "Something went wrong. Please try again.",
) -> MiddlewareFn:
    """Catch unhandled exceptions, log them, and send an ephemeral error reply."""
    logger = logging.getLogger("easycord")

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        try:
            await proceed()
        except Exception as exc:  # noqa: BLE001 — intentional broad catch for error handler
            logger.exception("Unhandled error in /%s: %s", ctx.command_name, exc)
            with contextlib.suppress(Exception):
                await ctx.respond(message, ephemeral=True)

    return handler
