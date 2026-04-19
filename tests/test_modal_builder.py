"""Tests for easycord.builders.modal — ModalBuilder."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from easycord.builders.modal import ModalBuilder


async def test_send_requires_title():
    ctx = MagicMock()
    with pytest.raises(ValueError, match="requires a title"):
        await ModalBuilder().send(ctx)


async def test_send_delegates_to_ask_form():
    ctx = MagicMock()
    ctx.ask_form = AsyncMock(return_value={"reason": "test"})
    result = await ModalBuilder().title("Feedback").field("reason", "Why?").send(ctx)
    ctx.ask_form.assert_called_once_with(
        "Feedback", reason={"label": "Why?", "required": True}
    )
    assert result == {"reason": "test"}


async def test_send_returns_none_on_timeout():
    ctx = MagicMock()
    ctx.ask_form = AsyncMock(return_value=None)
    result = await ModalBuilder().title("Form").field("x", "X").send(ctx)
    assert result is None


async def test_field_with_placeholder():
    ctx = MagicMock()
    ctx.ask_form = AsyncMock(return_value={"x": "val"})
    await ModalBuilder().title("T").field("x", "Label", placeholder="hint").send(ctx)
    assert ctx.ask_form.call_args.kwargs["x"]["placeholder"] == "hint"


async def test_field_not_required():
    ctx = MagicMock()
    ctx.ask_form = AsyncMock(return_value={"x": ""})
    await ModalBuilder().title("T").field("x", "Label", required=False).send(ctx)
    assert ctx.ask_form.call_args.kwargs["x"]["required"] is False


async def test_multiple_fields_all_passed():
    ctx = MagicMock()
    ctx.ask_form = AsyncMock(return_value={"a": "1", "b": "2"})
    await ModalBuilder().title("T").field("a", "A").field("b", "B").send(ctx)
    assert "a" in ctx.ask_form.call_args.kwargs
    assert "b" in ctx.ask_form.call_args.kwargs


def test_chaining_returns_self():
    b = ModalBuilder()
    assert b.title("T") is b
    assert b.field("k", "L") is b
