"""Rate limiting for tool execution — prevent abuse of expensive operations."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from easycord.context import Context


@dataclass
class RateLimit:
    """Rate limit config for a tool."""

    max_calls: int  # Max calls allowed
    window_minutes: int = 60  # Time window


@dataclass
class RateLimitEntry:
    """Track calls for a user/tool pair."""

    timestamps: list[datetime] = field(default_factory=list)


class ToolLimiter:
    """Check and enforce per-user tool rate limits."""

    def __init__(self):
        # {(user_id, tool_name): RateLimitEntry}
        self._usage: dict[tuple[int, str], RateLimitEntry] = {}
        self._lock = asyncio.Lock()

    async def check_limit(
        self,
        user_id: int,
        tool_name: str,
        limit: RateLimit,
    ) -> tuple[bool, str | None]:
        """Check if user can call tool. Return (allowed, reason)."""
        async with self._lock:
            key = (user_id, tool_name)
            entry = self._usage.get(key, RateLimitEntry())
            self._usage[key] = entry

            # Remove old timestamps outside window
            cutoff = datetime.now(timezone.utc) - timedelta(
                minutes=limit.window_minutes
            )
            entry.timestamps = [ts for ts in entry.timestamps if ts > cutoff]

            # Check limit
            if len(entry.timestamps) >= limit.max_calls:
                oldest = entry.timestamps[0]
                reset_time = oldest + timedelta(minutes=limit.window_minutes)
                return (
                    False,
                    f"Rate limit exceeded. Reset at {reset_time.isoformat()}",
                )

            # Record this call
            entry.timestamps.append(datetime.now(timezone.utc))
            return True, None

    async def reset_user(self, user_id: int) -> None:
        """Clear all rate limit entries for a user."""
        async with self._lock:
            keys_to_remove = [
                key for key in self._usage.keys() if key[0] == user_id
            ]
            for key in keys_to_remove:
                del self._usage[key]

    async def reset_tool(self, tool_name: str) -> None:
        """Clear all rate limit entries for a tool."""
        async with self._lock:
            keys_to_remove = [
                key for key in self._usage.keys() if key[1] == tool_name
            ]
            for key in keys_to_remove:
                del self._usage[key]

    def get_stats(self) -> dict:
        """Get rate limit statistics."""
        return {
            "tracked_limits": len(self._usage),
            "total_calls": sum(
                len(entry.timestamps) for entry in self._usage.values()
            ),
        }
