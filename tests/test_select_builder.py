"""Tests for easycord.builders.select — SelectMenuBuilder."""
import discord
import pytest

from easycord.builders.select import SelectMenuBuilder


def test_build_requires_options():
    with pytest.raises(ValueError, match="at least one option"):
        SelectMenuBuilder().build(custom_id="sel")


def test_build_returns_view():
    view = SelectMenuBuilder().option("A", "a").build(custom_id="sel")
    assert isinstance(view, discord.ui.View)


def test_select_added_to_view():
    view = SelectMenuBuilder().option("A", "a").build(custom_id="sel")
    assert len(view.children) == 1
    assert isinstance(view.children[0], discord.ui.Select)


def test_option_label_and_value():
    view = SelectMenuBuilder().option("Label", "val").build(custom_id="sel")
    assert view.children[0].options[0].label == "Label"
    assert view.children[0].options[0].value == "val"


def test_multiple_options():
    view = SelectMenuBuilder().option("A", "a").option("B", "b").build(custom_id="sel")
    assert len(view.children[0].options) == 2
    assert view.children[0].options[0].label == "A"
    assert view.children[0].options[1].label == "B"


def test_placeholder_set():
    view = SelectMenuBuilder().placeholder("Pick one").option("A", "a").build(custom_id="sel")
    assert view.children[0].placeholder == "Pick one"


def test_no_placeholder_is_none():
    view = SelectMenuBuilder().option("A", "a").build(custom_id="sel")
    assert view.children[0].placeholder is None


def test_custom_id_passed():
    view = SelectMenuBuilder().option("A", "a").build(custom_id="my_select")
    assert view.children[0].custom_id == "my_select"


def test_chaining_returns_self():
    b = SelectMenuBuilder()
    assert b.placeholder("P") is b
    assert b.option("A", "a") is b
