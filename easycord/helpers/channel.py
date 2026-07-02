"""Channel type utilities."""
from __future__ import annotations

import discord

# Channel types that support .send() in discord.py.
# StageChannel is intentionally excluded — it has no Messageable interface.
SENDABLE_CHANNEL_TYPES = (
    discord.TextChannel,
    discord.Thread,
    discord.VoiceChannel,
)
