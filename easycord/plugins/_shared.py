"""Shared helpers for the bundled plugins."""
from __future__ import annotations

import json
import os
from pathlib import Path

import discord


def require_guild(ctx: object) -> discord.Guild | None:
    """Return the invoking guild, or ``None`` when the command ran in DMs."""
    return getattr(ctx, "guild", None)


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
