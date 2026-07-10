"""Tests for AutoResponderPlugin: CRUD, per-guild isolation, concurrency, and message dispatch."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from easycord.plugins.auto_responder import AutoResponderPlugin


def _make_plugin(tmp_path) -> AutoResponderPlugin:
    return AutoResponderPlugin(store_path=str(tmp_path / "auto-responder"))


def _make_message(*, guild_id: int = 1, content: str = "hello world", is_bot: bool = False) -> MagicMock:
    msg = MagicMock()
    msg.guild = MagicMock()
    msg.guild.id = guild_id
    msg.author = MagicMock()
    msg.author.bot = is_bot
    msg.content = content
    msg.reply = AsyncMock()
    return msg


# ── _add_trigger / _remove_trigger ───────────────────────────


async def test_add_trigger_stored(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "hello back")
    cfg = await plugin._get_config(1)
    assert cfg["triggers"]["hi"] == "hello back"


async def test_add_regex_trigger_stored(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_regex_trigger(1, r"\bhello\b", "hi there")
    cfg = await plugin._get_config(1)
    assert cfg["regex_triggers"][r"\bhello\b"] == "hi there"


async def test_remove_trigger_returns_true_when_found(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "bye", "see ya")
    found = await plugin._remove_trigger(1, "bye")
    assert found is True
    cfg = await plugin._get_config(1)
    assert "bye" not in cfg["triggers"]


async def test_remove_trigger_returns_false_when_missing(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    found = await plugin._remove_trigger(1, "ghost")
    assert found is False


async def test_remove_regex_trigger(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_regex_trigger(1, r"\bfoo\b", "bar")
    found = await plugin._remove_trigger(1, r"\bfoo\b")
    assert found is True
    cfg = await plugin._get_config(1)
    assert r"\bfoo\b" not in cfg["regex_triggers"]


async def test_add_trigger_invalid_regex_raises(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    with pytest.raises(ValueError, match="Invalid regex"):
        await plugin._add_regex_trigger(1, "[unclosed", "oops")


async def test_triggers_are_per_guild(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "guild-one")
    await plugin._add_trigger(2, "hi", "guild-two")
    cfg1 = await plugin._get_config(1)
    cfg2 = await plugin._get_config(2)
    assert cfg1["triggers"]["hi"] == "guild-one"
    assert cfg2["triggers"]["hi"] == "guild-two"


async def test_add_multiple_triggers_preserved(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "a", "resp-a")
    await plugin._add_trigger(1, "b", "resp-b")
    cfg = await plugin._get_config(1)
    assert cfg["triggers"] == {"a": "resp-a", "b": "resp-b"}


# ── B-013 regression: concurrent writes must not lose entries ─


async def test_concurrent_add_triggers_all_persist(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await asyncio.gather(*[plugin._add_trigger(1, f"kw{i}", f"resp{i}") for i in range(20)])
    cfg = await plugin._get_config(1)
    assert len(cfg["triggers"]) == 20, "concurrent adds lost some entries (B-013 regression)"


async def test_concurrent_remove_triggers_no_corruption(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    for i in range(10):
        await plugin._add_trigger(1, f"kw{i}", f"v{i}")
    # Remove even-indexed triggers concurrently; odd ones must survive.
    await asyncio.gather(*[plugin._remove_trigger(1, f"kw{i}") for i in range(0, 10, 2)])
    cfg = await plugin._get_config(1)
    assert set(cfg["triggers"].keys()) == {f"kw{i}" for i in range(1, 10, 2)}


# ── _on_message dispatch ──────────────────────────────────────


async def test_on_message_replies_for_literal_match(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "hello there!")
    msg = _make_message(content="say hi now")
    await plugin._on_message(msg)
    msg.reply.assert_called_once_with("hello there!", mention_author=False)


async def test_on_message_replies_for_regex_match(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_regex_trigger(1, r"\bworld\b", "hello world!")
    msg = _make_message(content="goodbye world")
    await plugin._on_message(msg)
    msg.reply.assert_called_once_with("hello world!", mention_author=False)


async def test_on_message_no_response_for_no_match(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "hello")
    msg = _make_message(content="completely unrelated")
    await plugin._on_message(msg)
    msg.reply.assert_not_called()


async def test_on_message_ignores_bot(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "hello")
    msg = _make_message(content="hi", is_bot=True)
    await plugin._on_message(msg)
    msg.reply.assert_not_called()


async def test_on_message_ignores_no_guild(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "hello")
    msg = _make_message(content="hi")
    msg.guild = None
    await plugin._on_message(msg)
    msg.reply.assert_not_called()


async def test_on_message_ignores_empty_content(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "hello")
    msg = _make_message(content="")
    await plugin._on_message(msg)
    msg.reply.assert_not_called()


async def test_on_message_case_insensitive_match(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "HI", "hello")
    msg = _make_message(content="hi there")
    await plugin._on_message(msg)
    msg.reply.assert_called_once()


async def test_on_message_only_replies_once_for_multiple_matches(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "foo", "first")
    await plugin._add_trigger(1, "bar", "second")
    msg = _make_message(content="foo bar")
    await plugin._on_message(msg)
    assert msg.reply.call_count == 1


async def test_on_message_disabled_plugin_no_response(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._add_trigger(1, "hi", "hello")
    # Force disabled
    await plugin._update_config(1, enabled=False)
    msg = _make_message(content="hi")
    await plugin._on_message(msg)
    msg.reply.assert_not_called()


async def test_on_message_bad_stored_regex_skipped(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    # Write an invalid pattern directly (bypassing validation)
    await plugin._update_config(1, regex_triggers={"[bad": "oops"})
    msg = _make_message(content="anything")
    # Must not raise — bad stored patterns are logged and skipped.
    await plugin._on_message(msg)
    msg.reply.assert_not_called()


# ── Config lifecycle ──────────────────────────────────────────


async def test_get_config_returns_defaults_for_fresh_guild(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    cfg = await plugin._get_config(99)
    assert cfg["enabled"] is True
    assert cfg["triggers"] == {}
    assert cfg["regex_triggers"] == {}


async def test_on_load_logs_info(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    with patch("easycord.plugins.auto_responder.logger") as mock_logger:
        await plugin.on_load()
    mock_logger.info.assert_called_once()
