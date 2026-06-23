from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from easycord.conversation_memory import ConversationMemory
from easycord.database import MemoryDatabase
from easycord.i18n import DiagnosticMode, LocalizationManager


def test_conversation_memory_evicts_oldest_over_cap() -> None:
    memory = ConversationMemory(max_conversations=2)

    memory.add_user_message(1, "one", guild_id=10)
    memory.add_user_message(2, "two", guild_id=10)
    memory.add_user_message(3, "three", guild_id=10)

    stats = memory.get_stats()
    assert stats["total_conversations"] == 2
    assert memory.get_messages(2, guild_id=10) == [{"role": "user", "content": "two"}]
    assert memory.get_messages(3, guild_id=10) == [{"role": "user", "content": "three"}]


def test_conversation_memory_cleanup_expired() -> None:
    memory = ConversationMemory(max_conversations=10, default_max_age_minutes=1)
    conv = memory.get_or_create(1, 10)
    conv.last_updated = datetime.now(timezone.utc) - timedelta(minutes=5)

    removed = memory.cleanup_expired()

    assert removed == 1
    assert memory.get_stats()["total_conversations"] == 0


@pytest.mark.asyncio
async def test_memory_database_deep_copies_nested_values() -> None:
    db = MemoryDatabase()
    payload = {"nested": {"roles": ["admin"]}}

    await db.set(123, "settings", payload)
    payload["nested"]["roles"].append("mutated-before-read")

    stored = await db.get(123, "settings")
    stored["nested"]["roles"].append("mutated-after-read")

    stored_again = await db.get(123, "settings")
    assert stored_again == {"nested": {"roles": ["admin"]}}


def test_i18n_strict_placeholder_diagnostics() -> None:
    manager = LocalizationManager(
        translations={"en-US": {"hello": "Hello {name}"}},
        diagnostic_mode=DiagnosticMode.STRICT,
    )

    with pytest.raises(KeyError):
        manager.format("hello")


def test_conversation_summary_on_eviction() -> None:
    def simple_summary(turns) -> str:
        return " & ".join(t.content for t in turns)

    memory = ConversationMemory(
        default_max_turns=3,
        summary_on_eviction=True,
        summary_fn=simple_summary,
    )
    conv = memory.get_or_create(1, 10)

    conv.add_turn("user", "one")
    conv.add_turn("user", "two")
    conv.add_turn("user", "three")

    assert len(conv.turns) == 3

    conv.add_turn("user", "four")

    # Length must still be 3.
    # The evicted turns: "one" and "two" (k = 4 - 3 + 1 = 2)
    # They should be compressed to "TL;DR: one & two" as a system turn.
    # The remaining turns: "three" and "four".
    assert len(conv.turns) == 3
    assert conv.turns[0].role == "system"
    assert conv.turns[0].content == "TL;DR: one & two"
    assert conv.turns[1].content == "three"
    assert conv.turns[2].content == "four"


def test_conversation_summary_on_eviction_fallback() -> None:
    def bad_summary(turns) -> str:
        raise ValueError("Simulated summary error")

    memory = ConversationMemory(
        default_max_turns=3,
        summary_on_eviction=True,
        summary_fn=bad_summary,
    )
    conv = memory.get_or_create(1, 10)

    conv.add_turn("user", "one")
    conv.add_turn("user", "two")
    conv.add_turn("user", "three")
    conv.add_turn("user", "four")

    # Should fall back to standard eviction, popping the oldest turn ("one")
    # remaining turns should be "two", "three", "four"
    assert len(conv.turns) == 3
    assert conv.turns[0].content == "two"
    assert conv.turns[1].content == "three"
    assert conv.turns[2].content == "four"

