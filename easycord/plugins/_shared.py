"""Shared helpers for the bundled plugins."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import discord

if TYPE_CHECKING:
    from easycord.server_config import ServerConfig


def require_guild(ctx: object) -> discord.Guild | None:
    """Return the invoking guild, or ``None`` when the command ran in DMs."""
    return getattr(ctx, "guild", None)


async def respond_error(ctx: object, message: str) -> None:
    """Send *message* as an ephemeral error reply.

    Collapses the ubiquitous ``await ctx.respond(msg, ephemeral=True)`` pattern
    used for validation failures and permission denials across the plugins.
    """
    await ctx.respond(message, ephemeral=True)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Typed config accessors
#
# Discord snowflake IDs are frequently persisted as JSON strings, so reads
# normalize back to ``int``. These are pure over a ``ServerConfig`` (no store,
# no lock, no I/O), so they slot inside an existing ``mutate``/lock span
# without changing locking semantics.
# ---------------------------------------------------------------------------

def get_id(cfg: "ServerConfig", key: str) -> int | None:
    """Return the snowflake stored under *key* as an ``int``, or ``None``."""
    value = cfg.get_other(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_id(cfg: "ServerConfig", key: str, value: int | None) -> None:
    """Store a snowflake under *key*. ``None`` removes the key entirely."""
    if value is None:
        cfg.remove_other(key)
        return
    cfg.set_other(key, int(value))


def get_ids(cfg: "ServerConfig", key: str) -> list[int]:
    """Return the list of snowflakes under *key* as ``int``s (missing -> [])."""
    raw = cfg.get_other(key)
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def set_ids(cfg: "ServerConfig", key: str, values: Iterable[int]) -> None:
    """Store an iterable of snowflakes under *key* as a list of ``int``s."""
    cfg.set_other(key, [int(v) for v in values])


def format_template(template: str, **values: str) -> str:
    """Render a simple placeholder template."""
    return template.format(**values)


def read_json_file(path: Path) -> dict:
    """Read a JSON file if it exists, otherwise return an empty mapping."""
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json_file(path: Path, data: dict) -> None:
    """Write JSON atomically using a temporary file and rename."""
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, path)


def channel_reference(guild: discord.Guild, channel_id: int) -> str:
    """Return a user-facing channel mention with a deleted-channel fallback."""
    channel = guild.get_channel(channel_id)
    return channel.mention if channel else f"<#{channel_id}> *(deleted?)*"


def role_reference(guild: discord.Guild, role_id: int) -> str:
    """Return a user-facing role mention with a deleted-role fallback."""
    role = guild.get_role(role_id)
    return role.mention if role else f"<@&{role_id}> *(deleted?)*"


# ---------------------------------------------------------------------------
# Guild lock manager for concurrent per-guild mutations
# ---------------------------------------------------------------------------

MAX_TRACKED_GUILDS = 5000


class GuildLockManager:
    """Per-guild lock manager with idle-eviction to prevent unbounded memory growth.

    Each guild gets one lock that serializes all read-modify-write operations.
    The lock is created on first access, refreshed on every access (updating
    last-used timestamp), and automatically evicted after 7 days of idleness
    or when the total count exceeds MAX_TRACKED_GUILDS.

    Safe under concurrent access: never evicts a currently-held lock, preventing
    the race where a new caller receives a fresh lock while an existing holder
    still considers itself the sole writer.

    Usage::

        mgr = GuildLockManager()
        async with mgr.lock(guild_id):
            # perform read-modify-write atomically
            pass
    """

    def __init__(self) -> None:
        self._registry: dict[int, asyncio.Lock] = {}
        self._created: dict[int, datetime] = {}

    def lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create the lock for a guild, refresh its timestamp, return it."""
        if guild_id not in self._registry:
            self._registry[guild_id] = asyncio.Lock()
            self._cleanup()
        self._created[guild_id] = datetime.now(timezone.utc)
        return self._registry[guild_id]

    def _cleanup(self) -> None:
        """Evict idle locks to prevent unbounded memory growth.

        A lock is removed only if it has been idle >7 days AND is not held.
        If still over MAX_TRACKED_GUILDS, evict oldest 25% of idle locks.
        """
        now = datetime.now(timezone.utc)
        max_age = timedelta(days=7)

        # Remove locks idle >7 days, but never remove an acquired lock.
        idle_old = [
            gid
            for gid, ts in self._created.items()
            if now - ts > max_age and not self._registry[gid].locked()
        ]
        for gid in idle_old:
            del self._registry[gid]
            del self._created[gid]

        # If still over limit, evict oldest 25% of idle locks.
        if len(self._registry) > MAX_TRACKED_GUILDS:
            candidates = sorted(
                ((gid, ts) for gid, ts in self._created.items() if not self._registry[gid].locked()),
                key=lambda x: x[1],
            )
            remove_count = max(1, len(candidates) // 4)
            for gid, _ in candidates[:remove_count]:
                del self._registry[gid]
                del self._created[gid]
