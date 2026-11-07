"""Shared development startup for factory-built bots."""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING

from .config import BotConfig

if TYPE_CHECKING:
    from .bot import Bot


def _lock_data_dir(data_dir: str):
    """Hold an OS lock on ``data_dir`` for this process's lifetime.

    Two live bots sharing one ``data_dir`` both sync their full command tree to
    the same test guild (last write wins) and both read-modify-write the same
    plugin JSON (last save clobbers the other). An exclusive file lock lets only
    one live instance use a directory at a time; the OS releases it on exit, so a
    crash leaves no stale lock. Does not coordinate across machines — point each
    deployment at its own ``data_dir``/test guild for that.
    """
    os.makedirs(data_dir, exist_ok=True)
    handle = open(os.path.join(data_dir, ".live.lock"), "w")
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise SystemExit(
            f"Another live bot is already using {data_dir!r}. Stop it first, or "
            "launch with a different data_dir and test server."
        ) from None
    return handle


def run_bot(factory: Callable[..., Bot], *, data_dir: str = ".easycord/live") -> None:
    """Run a factory with environment configuration and an explicit test guild.

    The factory receives normal Bot constructor options plus ``data_dir`` for
    plugin storage. Imports and offline factory calls do not read credentials.
    Login and publication failures propagate rather than reporting success.
    """
    try:
        config = BotConfig.from_env()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if config.guild_id is None:
        raise SystemExit(
            "Set DISCORD_GUILD_ID to your test server ID before launching. "
            "See README.md for setup steps."
        )
    if not 0 < config.guild_id < 2**64:
        raise SystemExit("DISCORD_GUILD_ID must be a positive Discord server ID below 2**64.")
    _lock = _lock_data_dir(data_dir)  # held until the process exits
    try:
        bot = config.build_bot(bot_factory=factory, data_dir=data_dir)
    except (OSError, sqlite3.Error):
        raise SystemExit(
            "Could not open bot storage. Check EASYCORD_DB_PATH and plugin data "
            "directory permissions."
        ) from None
    if config.auto_sync:
        print(f"Starting bot; commands will sync to test server {config.guild_id}.")
    else:
        print("Starting bot with command sync disabled (EASYCORD_AUTO_SYNC=false).")
    bot.run(config.token)
