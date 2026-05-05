"""Tests for utils, helpers, and plugin config manager."""
from __future__ import annotations

import pytest
import discord

from easycord.utils.easy_embed import EasyEmbed
from easycord.utils.paginator import Paginator
from easycord.helpers.embed import EmbedBuilder as HelpersEmbedBuilder
from easycord.helpers.ratelimit import RateLimitHelpers
from easycord.tool_limits import RateLimit, ToolLimiter


# ---------------------------------------------------------------------------
# EasyEmbed
# ---------------------------------------------------------------------------

class TestEasyEmbed:
    def test_success_embed(self) -> None:
        embed = EasyEmbed.success("All good")
        assert "All good" in embed.description
        assert "✅" in embed.description

    def test_error_embed(self) -> None:
        embed = EasyEmbed.error("Bad thing happened")
        assert "Bad thing happened" in embed.description
        assert "❌" in embed.description

    def test_info_embed(self) -> None:
        embed = EasyEmbed.info("FYI")
        assert "FYI" in embed.description

    def test_warning_embed(self) -> None:
        embed = EasyEmbed.warning("Watch out")
        assert "Watch out" in embed.description
        assert "⚠️" in embed.description


# ---------------------------------------------------------------------------
# Paginator
# ---------------------------------------------------------------------------

class TestPaginator:
    def _embed(self, title: str = "Page") -> discord.Embed:
        return discord.Embed(title=title)

    def test_requires_at_least_one_page(self) -> None:
        with pytest.raises(ValueError):
            Paginator([])

    def test_page_count(self) -> None:
        p = Paginator([self._embed(), self._embed()])
        assert p.page_count == 2

    def test_pages_property(self) -> None:
        e1, e2 = self._embed("A"), self._embed("B")
        p = Paginator([e1, e2])
        assert p.pages[0].title == "A"
        assert p.pages[1].title == "B"

    def test_from_lines_single_page(self) -> None:
        p = Paginator.from_lines(["a", "b", "c"])
        assert p.page_count == 1

    def test_from_lines_multiple_pages(self) -> None:
        lines = [str(i) for i in range(25)]
        p = Paginator.from_lines(lines, per_page=10)
        assert p.page_count == 3

    def test_from_lines_empty(self) -> None:
        p = Paginator.from_lines([])
        assert p.page_count == 1

    def test_from_lines_invalid_per_page(self) -> None:
        with pytest.raises(ValueError):
            Paginator.from_lines(["a"], per_page=0)

    def test_from_embeds(self) -> None:
        embeds = [self._embed(f"P{i}") for i in range(3)]
        p = Paginator.from_embeds(embeds)
        assert p.page_count == 3

    def test_move_next_does_not_exceed_last(self) -> None:
        p = Paginator([self._embed()])
        p._move_next()
        assert p._index == 0

    def test_move_prev_does_not_go_below_zero(self) -> None:
        p = Paginator([self._embed(), self._embed()])
        p._move_prev()
        assert p._index == 0

    def test_move_first_and_last(self) -> None:
        p = Paginator([self._embed(), self._embed(), self._embed()])
        p._move_last()
        assert p._index == 2
        p._move_first()
        assert p._index == 0

    def test_current_embed(self) -> None:
        e1 = self._embed("First")
        e2 = self._embed("Second")
        p = Paginator([e1, e2])
        assert p._current_embed().title == "First"
        p._move_next()
        assert p._current_embed().title == "Second"

    @pytest.mark.asyncio
    async def test_send_single_page(self) -> None:
        from unittest.mock import AsyncMock, MagicMock
        p = Paginator([self._embed("Only")])
        ctx = MagicMock()
        ctx.respond = AsyncMock()
        await p.send(ctx)
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_multiple_pages(self) -> None:
        from unittest.mock import AsyncMock, MagicMock
        p = Paginator([self._embed("A"), self._embed("B")])
        ctx = MagicMock()
        ctx.respond = AsyncMock()
        ctx.interaction = MagicMock()
        ctx.interaction.original_response = AsyncMock(return_value=MagicMock())
        ctx.user = MagicMock()
        ctx.user.id = 1
        await p.send(ctx)
        ctx.respond.assert_called_once()


# ---------------------------------------------------------------------------
# Helpers EmbedBuilder
# ---------------------------------------------------------------------------

class TestHelpersEmbedBuilder:
    def test_success_static(self) -> None:
        embed = HelpersEmbedBuilder.success("Done")
        assert embed.title == "Done"
        assert embed.color == discord.Color.green()

    def test_error_static(self) -> None:
        embed = HelpersEmbedBuilder.error("Failed")
        assert embed.title == "Failed"
        assert embed.color == discord.Color.red()

    def test_info_static(self) -> None:
        embed = HelpersEmbedBuilder.info("Note")
        assert embed.color == discord.Color.blue()

    def test_warning_static(self) -> None:
        embed = HelpersEmbedBuilder.warning("Careful")
        assert embed.color == discord.Color.orange()

    def test_instance_add_field(self) -> None:
        b = HelpersEmbedBuilder(title="T")
        b.add_field("Name", "Val")
        embed = b.build()
        assert embed.fields[0].name == "Name"

    def test_set_color(self) -> None:
        b = HelpersEmbedBuilder(title="T")
        b.set_color(discord.Color.red())
        assert b.build().color == discord.Color.red()

    def test_set_thumbnail_with_url(self) -> None:
        b = HelpersEmbedBuilder(title="T")
        b.set_thumbnail("https://example.com/img.png")
        assert b.build().thumbnail.url == "https://example.com/img.png"

    def test_set_thumbnail_none_noop(self) -> None:
        b = HelpersEmbedBuilder(title="T")
        b.set_thumbnail(None)
        # Should not raise

    def test_set_footer(self) -> None:
        b = HelpersEmbedBuilder(title="T")
        b.set_footer("footer text")
        assert b.build().footer.text == "footer text"

    def test_set_author(self) -> None:
        b = HelpersEmbedBuilder(title="T")
        b.set_author("Author Name")
        assert b.build().author.name == "Author Name"

    def test_set_timestamp(self) -> None:
        b = HelpersEmbedBuilder(title="T")
        b.set_timestamp()
        assert b.build().timestamp is not None


# ---------------------------------------------------------------------------
# RateLimitHelpers
# ---------------------------------------------------------------------------

class TestRateLimitHelpers:
    def test_create_limit(self) -> None:
        limit = RateLimitHelpers.create_limit("tool", max_calls=5, window_minutes=10)
        assert limit.max_calls == 5
        assert limit.window_minutes == 10

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        limiter = ToolLimiter()
        stats = RateLimitHelpers.get_stats(limiter)
        assert "tracked_limits" in stats
        assert "total_calls" in stats
    @pytest.mark.asyncio
    async def test_check_and_reset_helpers_await_limiter(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimitHelpers.create_limit("tool", max_calls=1, window_minutes=10)

        assert await RateLimitHelpers.check(limiter, 1, "tool", limit) is True
        assert await RateLimitHelpers.check(limiter, 1, "tool", limit) is False

        await RateLimitHelpers.reset_user(limiter, 1)
        assert await RateLimitHelpers.check(limiter, 1, "tool", limit) is True

        await RateLimitHelpers.reset_tool(limiter, "tool")
        assert await RateLimitHelpers.check(limiter, 1, "tool", limit) is True

