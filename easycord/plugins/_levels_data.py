"""XP math and per-guild storage for LevelsPlugin."""
from __future__ import annotations

import asyncio
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Callable


# ── XP / level formulae ───────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """Total XP required to reach *level* from zero.

    Uses a triangular progression: each level costs ``level * 100`` XP more
    than the previous one.

    - Level 1:  100 XP total
    - Level 2:  300 XP total
    - Level 5:  1 500 XP total
    - Level 10: 5 500 XP total
    """
    return level * (level + 1) // 2 * 100


def level_from_xp(xp: int) -> int:
    """Return the level achieved for a given total XP amount (O(1))."""
    n = (math.isqrt(1 + 8 * xp // 100) - 1) // 2
    while xp_for_level(n + 1) <= xp:
        n += 1
    return n


def progress_bar(xp: int, level: int, width: int = 10) -> str:
    """Return a Unicode progress bar string for the current level."""
    current_floor = xp_for_level(level)
    next_ceil = xp_for_level(level + 1)
    span = next_ceil - current_floor
    filled = int((xp - current_floor) / span * width) if span else width
    return "█" * filled + "░" * (width - filled)


def rank_for_level(config: dict, level: int) -> str | None:
    """Return the highest rank name whose threshold is at or below *level*."""
    eligible = [
        (int(k), v)
        for k, v in config.get("ranks", {}).items()
        if int(k) <= level
    ]
    return max(eligible, key=lambda t: t[0])[1] if eligible else None


# ── Storage ───────────────────────────────────────────────────────────────────

class LevelsStore:
    """Handles atomic per-guild XP and config JSON storage."""

    def __init__(self, data_dir: str) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._xp_locks: dict[int, asyncio.Lock] = {}
        self._cfg_locks: dict[int, asyncio.Lock] = {}

    # ── Lock helpers ──────────────────────────────────────────

    def _get_xp_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create XP lock for guild (lazy-init inside async context)."""
        if guild_id not in self._xp_locks:
            self._xp_locks[guild_id] = asyncio.Lock()
        return self._xp_locks[guild_id]

    def _get_cfg_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create config lock for guild (lazy-init inside async context)."""
        if guild_id not in self._cfg_locks:
            self._cfg_locks[guild_id] = asyncio.Lock()
        return self._cfg_locks[guild_id]

    # ── Paths ─────────────────────────────────────────────────

    def _xp_path(self, guild_id: int) -> Path:
        return self._data_dir / f"{guild_id}_xp.json"

    def _cfg_path(self, guild_id: int) -> Path:
        return self._data_dir / f"{guild_id}_config.json"

    # ── XP ────────────────────────────────────────────────────

    def read_xp(self, guild_id: int) -> dict[str, dict]:
        path = self._xp_path(guild_id)
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write_xp(self, guild_id: int, data: dict[str, dict]) -> None:
        path = self._xp_path(guild_id)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    async def add_xp(
        self, guild_id: int, user_id: int, amount: int
    ) -> tuple[int, int, bool]:
        """Add *amount* XP and return ``(total_xp, level, leveled_up)``."""
        async with self._get_xp_lock(guild_id):
            data = self.read_xp(guild_id)
            uid = str(user_id)
            entry = data.get(uid, {"xp": 0, "level": 0})
            old_level = entry["level"]
            entry["xp"] += amount
            entry["level"] = level_from_xp(entry["xp"])
            data[uid] = entry
            self._write_xp(guild_id, data)
        return entry["xp"], entry["level"], entry["level"] > old_level

    def get_entry(self, guild_id: int, user_id: int) -> dict:
        """Return a read-only snapshot for a user (no lock needed)."""
        return self.read_xp(guild_id).get(str(user_id), {"xp": 0, "level": 0})

    # ── Config ────────────────────────────────────────────────

    def read_config(self, guild_id: int) -> dict:
        path = self._cfg_path(guild_id)
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    async def update_config(self, guild_id: int, fn: Callable[[dict], object]) -> object:
        """Read config, call ``fn(config)`` under a lock, write back atomically."""
        async with self._get_cfg_lock(guild_id):
            config = self.read_config(guild_id)
            result = fn(config)
            path = self._cfg_path(guild_id)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            os.replace(tmp, path)
        return result
