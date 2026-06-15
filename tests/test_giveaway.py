"""Tests for GiveawayPlugin pure functions and store logic."""
from __future__ import annotations

import pytest

from easycord.plugins.giveaway import _parse_duration, _pick_winners, _build_embed


# ---------------------------------------------------------------------------
# _parse_duration
# ---------------------------------------------------------------------------

class TestParseDuration:
    def test_seconds(self) -> None:
        assert _parse_duration("30s") == 30

    def test_minutes(self) -> None:
        assert _parse_duration("30m") == 1800

    def test_hours(self) -> None:
        assert _parse_duration("2h") == 7200

    def test_days(self) -> None:
        assert _parse_duration("1d") == 86400

    def test_case_insensitive(self) -> None:
        assert _parse_duration("1H") == 3600
        assert _parse_duration("2D") == 172800

    def test_whitespace_stripped(self) -> None:
        assert _parse_duration("  30m  ") == 1800

    def test_zero_value(self) -> None:
        assert _parse_duration("0s") == 0

    def test_large_value(self) -> None:
        assert _parse_duration("100d") == 8640000

    def test_invalid_unit(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("30x")

    def test_no_unit(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("30")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("")

    def test_text(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("bad")

    def test_decimal_not_supported(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("1.5h")


# ---------------------------------------------------------------------------
# _pick_winners
# ---------------------------------------------------------------------------

class TestPickWinners:
    def test_empty_entries_returns_empty(self) -> None:
        assert _pick_winners([], 3) == []

    def test_count_zero_returns_empty(self) -> None:
        assert _pick_winners([1, 2, 3], 0) == []

    def test_fewer_entries_than_count(self) -> None:
        result = _pick_winners([1], 5)
        assert result == [1]

    def test_exact_count(self) -> None:
        entries = [1, 2, 3]
        result = _pick_winners(entries, 3)
        assert sorted(result) == [1, 2, 3]

    def test_subset_selected(self) -> None:
        entries = list(range(100))
        result = _pick_winners(entries, 3)
        assert len(result) == 3
        assert len(set(result)) == 3  # no duplicates
        assert all(w in entries for w in result)

    def test_single_winner(self) -> None:
        result = _pick_winners([42], 1)
        assert result == [42]

    def test_returns_list(self) -> None:
        result = _pick_winners([1, 2], 1)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _build_embed
# ---------------------------------------------------------------------------

class TestBuildEmbed:
    def test_active_embed_title(self) -> None:
        embed = _build_embed("Nitro", 1718445600, 1, 0)
        assert embed.title is not None
        assert "GIVEAWAY" in embed.title

    def test_active_embed_has_footer(self) -> None:
        embed = _build_embed("Nitro", 1718445600, 1, 0)
        assert embed.footer.text is not None
        assert len(embed.footer.text) > 0

    def test_ended_embed_has_no_footer(self) -> None:
        embed = _build_embed("Nitro", 1718445600, 1, 5, ended=True)
        assert embed.footer.text is None

    def test_prize_in_description(self) -> None:
        embed = _build_embed("Steam Key", 1718445600, 1, 0)
        assert embed.description is not None
        assert "Steam Key" in embed.description

    def test_entry_count_in_description(self) -> None:
        embed = _build_embed("Prize", 1718445600, 2, 42)
        assert embed.description is not None
        assert "42" in embed.description

    def test_winner_count_in_description(self) -> None:
        embed = _build_embed("Prize", 1718445600, 3, 0)
        assert embed.description is not None
        assert "3" in embed.description

    def test_ended_embed_color_differs(self) -> None:
        import discord
        active = _build_embed("X", 0, 1, 0)
        ended = _build_embed("X", 0, 1, 0, ended=True)
        assert active.color != ended.color
        assert ended.color == discord.Color.greyple()
