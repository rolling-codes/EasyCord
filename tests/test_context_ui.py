"""Tests for UIMixin — confirm, paginate, choose, ask_form, prompt."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from easycord._context_ui import UIMixin


def _future(value=None):
    """Return a future already resolved with *value*."""
    f = asyncio.get_event_loop().create_future()
    f.set_result(value)
    return f


class _Ctx(UIMixin):
    """Minimal context stand-in that satisfies UIMixin's required attributes."""

    def __init__(self):
        self.interaction = MagicMock()
        self.interaction.response = MagicMock()
        self.interaction.response.send_modal = AsyncMock()
        self._responded = False
        self.respond = AsyncMock()


# ---------------------------------------------------------------------------
# confirm()
# ---------------------------------------------------------------------------

class TestConfirm:
    async def test_yes_returns_true(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(True)
            result = await ctx.confirm("Are you sure?")
        assert result is True

    async def test_no_returns_false(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(False)
            result = await ctx.confirm("Continue?")
        assert result is False

    async def test_timeout_returns_none(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(None)
            result = await ctx.confirm("Sure?")
        assert result is None

    async def test_prompt_text_forwarded_to_respond(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(True)
            await ctx.confirm("Delete everything?")
        args, _ = ctx.respond.call_args
        assert args[0] == "Delete everything?"

    async def test_ephemeral_flag_forwarded(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(True)
            await ctx.confirm("Sure?", ephemeral=True)
        _, kwargs = ctx.respond.call_args
        assert kwargs["ephemeral"] is True

    async def test_view_included_in_respond(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(True)
            await ctx.confirm("Sure?", yes_label="Confirm", no_label="Abort")
        _, kwargs = ctx.respond.call_args
        assert "view" in kwargs


# ---------------------------------------------------------------------------
# paginate()
# ---------------------------------------------------------------------------

class TestPaginate:
    async def test_empty_list_no_respond(self):
        ctx = _Ctx()
        await ctx.paginate([])
        ctx.respond.assert_not_called()

    async def test_single_string_page(self):
        ctx = _Ctx()
        await ctx.paginate(["Hello world"])
        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs["content"] == "Hello world"

    async def test_first_of_multi_string_pages_shown(self):
        ctx = _Ctx()
        await ctx.paginate(["Page 1", "Page 2", "Page 3"])
        _, kwargs = ctx.respond.call_args
        assert kwargs["content"] == "Page 1"

    async def test_single_embed_page(self):
        ctx = _Ctx()
        embed = discord.Embed(title="Test embed")
        await ctx.paginate([embed])
        _, kwargs = ctx.respond.call_args
        assert kwargs["embed"] is embed
        assert kwargs["content"] is None

    async def test_mixed_first_string_page(self):
        ctx = _Ctx()
        embed = discord.Embed(title="Second page")
        await ctx.paginate(["Text page", embed])
        _, kwargs = ctx.respond.call_args
        assert kwargs["content"] == "Text page"

    async def test_ephemeral_flag_forwarded(self):
        ctx = _Ctx()
        await ctx.paginate(["Only page"], ephemeral=True)
        _, kwargs = ctx.respond.call_args
        assert kwargs["ephemeral"] is True


# ---------------------------------------------------------------------------
# choose()
# ---------------------------------------------------------------------------

class TestChoose:
    async def test_string_options_returns_selection(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future("Green")
            result = await ctx.choose("Pick a color", ["Red", "Green", "Blue"])
        assert result == "Green"

    async def test_dict_option_returns_value_field(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future("red")
            result = await ctx.choose(
                "Pick", [{"label": "Red", "value": "red"}]
            )
        assert result == "red"

    async def test_dict_option_with_description(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future("opt1")
            result = await ctx.choose(
                "Pick",
                [{"label": "Option 1", "value": "opt1", "description": "First choice"}],
            )
        assert result == "opt1"

    async def test_timeout_returns_none(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(None)
            result = await ctx.choose("Pick", ["A", "B"])
        assert result is None

    async def test_prompt_forwarded_to_respond(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future("A")
            await ctx.choose("Choose wisely", ["A"])
        args, _ = ctx.respond.call_args
        assert args[0] == "Choose wisely"


# ---------------------------------------------------------------------------
# ask_form()
# ---------------------------------------------------------------------------

class TestAskForm:
    async def test_returns_submitted_values(self):
        ctx = _Ctx()
        expected = {"name": "Alice"}
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(expected)
            with patch("asyncio.wait_for", new=AsyncMock(return_value=expected)):
                result = await ctx.ask_form("Info", name={"label": "Name"})
        assert result == {"name": "Alice"}

    async def test_timeout_returns_none(self):
        ctx = _Ctx()
        async def _raise(*a, **kw):
            raise asyncio.TimeoutError
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(None)
            with patch("asyncio.wait_for", new=_raise):
                result = await ctx.ask_form("Form", name={"label": "Name"})
        assert result is None

    async def test_paragraph_style_field(self):
        ctx = _Ctx()
        expected = {"body": "long text here"}
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(expected)
            with patch("asyncio.wait_for", new=AsyncMock(return_value=expected)):
                result = await ctx.ask_form(
                    "Feedback", body={"label": "Body", "style": "paragraph"}
                )
        assert result == expected

    async def test_multiple_fields(self):
        ctx = _Ctx()
        expected = {"first": "John", "last": "Doe"}
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(expected)
            with patch("asyncio.wait_for", new=AsyncMock(return_value=expected)):
                result = await ctx.ask_form(
                    "Full Name",
                    first={"label": "First Name"},
                    last={"label": "Last Name"},
                )
        assert result == expected


# ---------------------------------------------------------------------------
# prompt()
# ---------------------------------------------------------------------------

class TestPrompt:
    async def test_returns_submitted_text(self):
        ctx = _Ctx()
        form_result = {"value": "my answer"}
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(form_result)
            with patch("asyncio.wait_for", new=AsyncMock(return_value=form_result)):
                result = await ctx.prompt("Enter your reason")
        assert result == "my answer"

    async def test_returns_none_on_timeout(self):
        ctx = _Ctx()
        with patch("asyncio.get_running_loop") as m:
            m.return_value.create_future.return_value = _future(None)
            with patch("asyncio.wait_for", new=AsyncMock(return_value=None)):
                result = await ctx.prompt("Enter text")
        assert result is None
