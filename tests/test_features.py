import discord
import pytest

from easycord import EasyEmbed, Paginator


def test_paginator_from_lines_slices_pages():
    lines = [f"line-{i}" for i in range(1, 26)]
    paginator = Paginator.from_lines(lines, per_page=10, title="Test")

    assert paginator.page_count == 3
    first = paginator.pages[0]
    second = paginator.pages[1]
    third = paginator.pages[2]

    assert first.title == "Test"
    assert "line-1" in (first.description or "")
    assert "line-10" in (first.description or "")
    assert "line-11" in (second.description or "")
    assert "line-20" in (second.description or "")
    assert "line-21" in (third.description or "")
    assert "line-25" in (third.description or "")


def test_paginator_from_embeds_uses_existing_pages():
    embed_a = discord.Embed(title="A")
    embed_b = discord.Embed(title="B")
    paginator = Paginator.from_embeds([embed_a, embed_b])

    assert paginator.page_count == 2
    assert paginator.pages[0].title == "A"
    assert paginator.pages[1].title == "B"


def test_paginator_requires_pages():
    with pytest.raises(ValueError):
        Paginator.from_embeds([])


def test_easy_embed_success_color():
    embed = EasyEmbed.success("ok")
    assert embed.color.value == 0x2ECC71


def test_easy_embed_error_color():
    embed = EasyEmbed.error("bad")
    assert embed.color.value == 0xE74C3C


def test_easy_embed_info_color():
    embed = EasyEmbed.info("info")
    assert embed.color.value == 0x3498DB
