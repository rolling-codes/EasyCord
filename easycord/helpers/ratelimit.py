"""Rate limit helper shortcuts."""
from __future__ import annotations

from easycord.tool_limits import RateLimit, ToolLimiter


class RateLimitHelpers:
    """Shortcuts for rate limit management."""

    @staticmethod
    def create_limit(name: str, max_calls: int, window_minutes: int) -> RateLimit:
        """Create a rate limit config."""
        return RateLimit(max_calls=max_calls, window_minutes=window_minutes)

    @staticmethod
    async def check(limiter: ToolLimiter, user_id: int, tool_name: str, limit: RateLimit) -> bool:
        """Check if user can execute tool."""
        allowed, _ = await limiter.check_limit(user_id, tool_name, limit)
        return allowed

    @staticmethod
    async def reset_user(limiter: ToolLimiter, user_id: int) -> None:
        """Clear all rate limits for user."""
        await limiter.reset_user(user_id)

    @staticmethod
    async def reset_tool(limiter: ToolLimiter, tool_name: str) -> None:
        """Clear all rate limits for tool."""
        await limiter.reset_tool(tool_name)

    @staticmethod
    def get_stats(limiter: ToolLimiter) -> dict:
        """Get rate limit statistics."""
        return limiter.get_stats()
