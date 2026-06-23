"""Conversation memory management for multi-turn AI interactions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


@dataclass
class ConversationTurn:
    """Single turn in conversation."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Conversation:
    """Conversation history for a user in a guild."""

    user_id: int
    guild_id: int | None
    turns: list[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    max_turns: int = 20  # Keep last N turns
    max_age_minutes: int = 60  # Expire after N minutes
    summary_on_eviction: bool = False
    summary_fn: Callable[[list[ConversationTurn]], str] | None = None

    def add_turn(self, role: str, content: str) -> None:
        """Add a turn to conversation."""
        self.turns.append(ConversationTurn(role=role, content=content))
        self.last_updated = datetime.now(timezone.utc)
        self._cleanup()

    def _cleanup(self) -> None:
        """Remove old turns exceeding limits."""
        # Remove oldest turns if exceeding max
        if self.max_turns > 0 and len(self.turns) > self.max_turns:
            if self.summary_on_eviction and self.summary_fn is not None:
                # We need to evict k turns such that after adding 1 summary turn,
                # the total turns count is <= max_turns.
                # len(turns) - k + 1 <= max_turns  =>  k >= len(turns) - max_turns + 1
                k = len(self.turns) - self.max_turns + 1
                if k > len(self.turns):
                    k = len(self.turns)
                if k > 0:
                    evicted_turns = self.turns[:k]
                    remaining_turns = self.turns[k:]
                    try:
                        summary_content = self.summary_fn(evicted_turns)
                        summary_turn = ConversationTurn(
                            role="system",
                            content="TL;DR: " + summary_content
                        )
                        self.turns = [summary_turn] + remaining_turns
                    except Exception as exc:
                        logger.warning(
                            "Conversation summary failed for user %s: %s",
                            getattr(self, "user_id", "unknown"),
                            exc,
                        )
                        self.turns = self.turns[len(self.turns) - self.max_turns:]
            else:
                while len(self.turns) > self.max_turns:
                    self.turns.pop(0)
        elif self.max_turns <= 0:
            self.turns.clear()

        # Remove turns older than max_age
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=self.max_age_minutes
        )
        self.turns = [t for t in self.turns if t.timestamp > cutoff]

    def is_expired(self) -> bool:
        """Check if conversation is expired."""
        age = datetime.now(timezone.utc) - self.last_updated
        return age > timedelta(minutes=self.max_age_minutes)

    def to_messages(self) -> list[dict]:
        """Convert to message format for providers."""
        return [
            {
                "role": t.role,
                "content": t.content,
            }
            for t in self.turns
        ]

    def estimate_tokens(self, avg_chars_per_token: int = 4) -> int:
        """Rough token estimate for conversation."""
        total_chars = sum(len(t.content) for t in self.turns)
        return max(1, total_chars // avg_chars_per_token)


class ConversationMemory:
    """Manage conversation history per user/guild.

    Conversations are bounded by age, turn count, and total conversation count
    to avoid unbounded growth in long-running bots.
    """

    def __init__(
        self,
        *,
        max_conversations: int = 1000,
        default_max_turns: int = 20,
        default_max_age_minutes: int = 60,
        summary_on_eviction: bool = False,
        summary_fn: Callable[[list[ConversationTurn]], str] | None = None,
    ) -> None:
        if max_conversations < 1:
            raise ValueError("max_conversations must be at least 1")
        self.max_conversations = max_conversations
        self.default_max_turns = default_max_turns
        self.default_max_age_minutes = default_max_age_minutes
        self.summary_on_eviction = summary_on_eviction
        self.summary_fn = summary_fn
        self._conversations: dict[tuple[int, int | None], Conversation] = {}

    def get_or_create(
        self,
        user_id: int,
        guild_id: int | None = None,
        max_turns: int | None = None,
        max_age_minutes: int | None = None,
        summary_on_eviction: bool | None = None,
        summary_fn: Callable[[list[ConversationTurn]], str] | None = None,
    ) -> Conversation:
        """Get or create conversation for user/guild."""
        max_turns = self.default_max_turns if max_turns is None else max_turns
        max_age_minutes = (
            self.default_max_age_minutes
            if max_age_minutes is None
            else max_age_minutes
        )
        summary_on_eviction = (
            self.summary_on_eviction
            if summary_on_eviction is None
            else summary_on_eviction
        )
        summary_fn = (
            self.summary_fn
            if summary_fn is None
            else summary_fn
        )
        key = (user_id, guild_id)
        self.cleanup_expired()

        if key in self._conversations:
            conv = self._conversations[key]
            if not conv.is_expired():
                return conv
            # Conversation expired, remove it
            del self._conversations[key]

        conv = Conversation(
            user_id=user_id,
            guild_id=guild_id,
            max_turns=max_turns,
            max_age_minutes=max_age_minutes,
            summary_on_eviction=summary_on_eviction,
            summary_fn=summary_fn,
        )
        self._conversations[key] = conv
        self._evict_oldest_if_needed()
        return conv

    def add_user_message(
        self,
        user_id: int,
        content: str,
        guild_id: int | None = None,
    ) -> None:
        """Add user message to conversation."""
        conv = self.get_or_create(user_id, guild_id)
        conv.add_turn("user", content)

    def add_assistant_message(
        self,
        user_id: int,
        content: str,
        guild_id: int | None = None,
    ) -> None:
        """Add assistant message to conversation."""
        conv = self.get_or_create(user_id, guild_id)
        conv.add_turn("assistant", content)

    def get_messages(
        self,
        user_id: int,
        guild_id: int | None = None,
    ) -> list[dict]:
        """Get conversation history as messages."""
        conv = self.get_or_create(user_id, guild_id)
        return conv.to_messages()

    def clear(self, user_id: int, guild_id: int | None = None) -> None:
        """Clear conversation history."""
        key = (user_id, guild_id)
        if key in self._conversations:
            del self._conversations[key]

    def cleanup_expired(self) -> int:
        """Remove expired conversations. Return count removed."""
        keys_to_remove = [
            key
            for key, conv in self._conversations.items()
            if conv.is_expired()
        ]
        for key in keys_to_remove:
            del self._conversations[key]
        return len(keys_to_remove)

    def _evict_oldest_if_needed(self) -> int:
        """Evict least-recently-updated conversations beyond the configured cap."""
        overflow = len(self._conversations) - self.max_conversations
        if overflow <= 0:
            return 0

        keys_to_remove = [
            key for key, _ in sorted(
                self._conversations.items(),
                key=lambda item: item[1].last_updated,
            )[:overflow]
        ]
        for key in keys_to_remove:
            self._conversations.pop(key, None)
        return len(keys_to_remove)

    def get_stats(self) -> dict:
        """Get memory stats."""
        return {
            "total_conversations": len(self._conversations),
            "max_conversations": self.max_conversations,
            "total_turns": sum(
                len(c.turns) for c in self._conversations.values()
            ),
            "avg_turns_per_conv": (
                sum(len(c.turns) for c in self._conversations.values())
                / max(1, len(self._conversations))
            ),
        }
