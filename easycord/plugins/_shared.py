"""Shared helpers for the bundled plugins."""
from __future__ import annotations

import json
import os
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
