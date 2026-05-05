"""Tests for plugin data layers, pure functions, and stores."""
from __future__ import annotations

import pytest

from easycord.plugins.tags import TagsStore
from easycord.plugins._shared import (
    channel_reference,
    format_template,
    read_json_file,
    require_guild,
    role_reference,
    write_json_file,
)
from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins._levels_data import (
    LevelsStore,
    level_from_xp,
    progress_bar,
    rank_for_level,
    xp_for_level,
)
from easycord.plugins.polls import _is_valid_duration, _poll_options


# ---------------------------------------------------------------------------
# TagsStore
# ---------------------------------------------------------------------------

class TestTagsStore:
    @pytest.fixture
    def store(self, tmp_path):
        return TagsStore(str(tmp_path / "tags"))

    def test_set_and_get(self, store) -> None:
        store.set(1, "hello", "Hello, world!", author_id=99)
        entry = store.get(1, "hello")
        assert entry is not None
        assert entry["text"] == "Hello, world!"
        assert entry["author_id"] == 99

    def test_get_missing_returns_none(self, store) -> None:
        assert store.get(1, "nonexistent") is None

    def test_delete(self, store) -> None:
        store.set(1, "tag", "value", author_id=1)
        store.delete(1, "tag")
        assert store.get(1, "tag") is None

    def test_delete_noop_if_missing(self, store) -> None:
        store.delete(1, "nonexistent")  # should not raise

    def test_list_names(self, store) -> None:
        store.set(1, "alpha", "a", author_id=1)
        store.set(1, "beta", "b", author_id=1)
        names = store.list_names(1)
        assert names == ["alpha", "beta"]

    def test_list_names_empty(self, store) -> None:
        assert store.list_names(1) == []

    def test_guilds_are_isolated(self, store) -> None:
        store.set(1, "tag", "guild1", author_id=1)
        assert store.get(2, "tag") is None

    def test_overwrite_existing_tag(self, store) -> None:
        store.set(1, "tag", "v1", author_id=1)
        store.set(1, "tag", "v2", author_id=2)
        entry = store.get(1, "tag")
        assert entry["text"] == "v2"
        assert entry["author_id"] == 2


# ---------------------------------------------------------------------------
# PluginConfigManager
# ---------------------------------------------------------------------------

class TestPluginConfigManager:
    @pytest.fixture
    def manager(self, tmp_path):
        return PluginConfigManager(str(tmp_path / "cfg"))

    @pytest.mark.asyncio
    async def test_get_returns_defaults_when_empty(self, manager) -> None:
        result = await manager.get(1, "settings", {"enabled": True})
        assert result == {"enabled": True}

    @pytest.mark.asyncio
    async def test_get_persists_defaults(self, manager) -> None:
        await manager.get(1, "settings", {"x": 1})
        result = await manager.get(1, "settings", {"x": 999})
        assert result["x"] == 1  # returns stored, not the new defaults

    @pytest.mark.asyncio
    async def test_update(self, manager) -> None:
        await manager.get(1, "settings", {"x": 1})
        result = await manager.update(1, "settings", x=42, y=7)
        assert result["x"] == 42
        assert result["y"] == 7

    @pytest.mark.asyncio
    async def test_set_default_idempotent(self, manager) -> None:
        await manager.set_default(1, "cfg", {"a": 1})
        await manager.set_default(1, "cfg", {"a": 999})  # should not overwrite
        result = await manager.get(1, "cfg")
        assert result["a"] == 1


# ---------------------------------------------------------------------------
# XP / Level math
# ---------------------------------------------------------------------------

class TestXpMath:
    def test_xp_for_level_1(self) -> None:
        assert xp_for_level(1) == 100

    def test_xp_for_level_2(self) -> None:
        assert xp_for_level(2) == 300

    def test_xp_for_level_0(self) -> None:
        assert xp_for_level(0) == 0

    def test_level_from_xp_zero(self) -> None:
        assert level_from_xp(0) == 0

    def test_level_from_xp_at_threshold(self) -> None:
        assert level_from_xp(100) == 1

    def test_level_from_xp_just_below(self) -> None:
        assert level_from_xp(99) == 0

    def test_level_from_xp_level5(self) -> None:
        assert level_from_xp(xp_for_level(5)) == 5

    def test_level_from_xp_roundtrip(self) -> None:
        for level in range(1, 20):
            assert level_from_xp(xp_for_level(level)) == level

    def test_progress_bar_empty(self) -> None:
        bar = progress_bar(xp_for_level(1), 1)
        assert len(bar) == 10
        assert bar == "░" * 10

    def test_progress_bar_full(self) -> None:
        bar = progress_bar(xp_for_level(2) - 1, 1)
        assert "█" in bar

    def test_rank_for_level_no_ranks(self) -> None:
        assert rank_for_level({}, 5) is None

    def test_rank_for_level_returns_highest_eligible(self) -> None:
        config = {"ranks": {"1": "Bronze", "5": "Silver", "10": "Gold"}}
        assert rank_for_level(config, 7) == "Silver"
        assert rank_for_level(config, 10) == "Gold"
        assert rank_for_level(config, 3) == "Bronze"

    def test_rank_for_level_below_all_thresholds(self) -> None:
        config = {"ranks": {"5": "Silver"}}
        assert rank_for_level(config, 3) is None


# ---------------------------------------------------------------------------
# LevelsStore
# ---------------------------------------------------------------------------

class TestLevelsStore:
    @pytest.fixture
    def store(self, tmp_path):
        return LevelsStore(str(tmp_path / "levels"))

    def test_get_entry_defaults(self, store) -> None:
        entry = store.get_entry(1, 1)
        assert entry["xp"] == 0
        assert entry["level"] == 0

    @pytest.mark.asyncio
    async def test_add_xp(self, store) -> None:
        xp, level, leveled_up = await store.add_xp(1, 1, 50)
        assert xp == 50
        assert level == 0
        assert not leveled_up

    @pytest.mark.asyncio
    async def test_add_xp_causes_levelup(self, store) -> None:
        xp, level, leveled_up = await store.add_xp(1, 1, 100)
        assert xp == 100
        assert level == 1
        assert leveled_up

    @pytest.mark.asyncio
    async def test_add_xp_accumulates(self, store) -> None:
        await store.add_xp(1, 1, 50)
        xp, level, _ = await store.add_xp(1, 1, 50)
        assert xp == 100

    @pytest.mark.asyncio
    async def test_read_config_empty(self, store) -> None:
        cfg = store.read_config(1)
        assert isinstance(cfg, dict)

    @pytest.mark.asyncio
    async def test_update_config(self, store) -> None:
        def set_rank(cfg):
            cfg.setdefault("ranks", {})["5"] = "Silver"

        await store.update_config(1, set_rank)
        cfg = store.read_config(1)
        assert cfg["ranks"]["5"] == "Silver"

    @pytest.mark.asyncio
    async def test_read_xp_empty(self, store) -> None:
        data = store.read_xp(1)
        assert data == {}


# ---------------------------------------------------------------------------
# Poll helpers
# ---------------------------------------------------------------------------

class TestPollHelpers:
    def test_poll_options_filters_blank(self) -> None:
        options = _poll_options("Yes", "No", "", "  ", "Maybe")
        assert options == ["Yes", "No", "Maybe"]

    def test_is_valid_duration_true(self) -> None:
        assert _is_valid_duration(5) is True
        assert _is_valid_duration(60) is True

    def test_is_valid_duration_false(self) -> None:
        assert _is_valid_duration(4) is False
        assert _is_valid_duration(0) is False


# ---------------------------------------------------------------------------
# Poll view internals
# ---------------------------------------------------------------------------

class TestPollView:
    def test_tally_empty(self) -> None:
        from easycord.plugins.polls import _PollView
        view = _PollView("Q?", ["A", "B"], 60)
        counts = view._tally()
        assert counts == [0, 0]

    def test_tally_with_votes(self) -> None:
        from easycord.plugins.polls import _PollView
        view = _PollView("Q?", ["A", "B"], 60)
        view.votes = {1: 0, 2: 0, 3: 1}
        counts = view._tally()
        assert counts == [2, 1]

    def test_bar_full(self) -> None:
        from easycord.plugins.polls import _PollView
        view = _PollView("Q?", ["A"], 60)
        assert view._bar(10) == "█" * 10

    def test_bar_empty(self) -> None:
        from easycord.plugins.polls import _PollView
        view = _PollView("Q?", ["A"], 60)
        assert view._bar(0) == "░" * 10

    def test_build_embed(self) -> None:
        from easycord.plugins.polls import _PollView
        view = _PollView("Who wins?", ["Alice", "Bob"], 60)
        embed = view.build_embed()
        assert "Who wins?" in embed.title

    def test_build_embed_closed(self) -> None:
        from easycord.plugins.polls import _PollView
        view = _PollView("Q?", ["A", "B"], 60)
        embed = view.build_embed(closed=True)
        assert "closed" in embed.footer.text.lower()
