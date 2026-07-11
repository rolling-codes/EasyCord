"""Channel type utilities."""
from __future__ import annotations

import logging
from typing import Any

import discord

# Channel types that support .send() in discord.py.
# StageChannel is intentionally excluded — it has no Messageable interface.
SENDABLE_CHANNEL_TYPES = (
    discord.TextChannel,
    discord.Thread,
    discord.VoiceChannel,
)


async def send_safe(
    channel: discord.abc.Messageable,
    *,
    log: logging.Logger,
    what: str,
    **send_kwargs: Any,
) -> discord.Message | None:
    """Send to a configured channel, absorbing permission/API failures.

    Returns the sent message, or ``None`` when the send failed. Failures are
    logged as warnings instead of raising — a decorator-level bot_permissions
    preflight can only validate the invocation channel, so sends to a channel
    taken from config must carry their own guard (B-021). Callers decide
    whether ``None`` needs a user-facing response.
    """
    channel_id = getattr(channel, "id", "?")
    try:
        return await channel.send(**send_kwargs)
    except discord.Forbidden:
        log.warning("Missing permission to send %s in channel %s", what, channel_id)
    except discord.HTTPException as exc:
        log.warning("Failed to send %s in channel %s: %s", what, channel_id, exc)
    return None
