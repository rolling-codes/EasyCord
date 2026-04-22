"""Shared runtime helpers for example scripts."""

from __future__ import annotations

import os

from easycord import Bot


def read_token() -> str:
    """Return the Discord token from the environment."""
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Set the DISCORD_TOKEN environment variable.")
    return token


def run_bot(bot: Bot) -> None:
    """Run a bot using the `DISCORD_TOKEN` environment variable."""
    bot.run(read_token())
