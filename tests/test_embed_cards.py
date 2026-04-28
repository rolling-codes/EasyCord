import discord
import pytest
from datetime import timezone

from easycord import EmbedCard, ErrorEmbed, InfoEmbed, SuccessEmbed, WarningEmbed


def test_embed_card_wraps_existing_embed_and_adds_view_items():
    embed = discord.Embed(title="Status")

    card = (
        EmbedCard.from_embed(embed)
        .button("Approve", custom_id="approve", style="success")
        .link("Docs", "https://example.com")
        .select("pick", options=[("One", "1"), ("Two", "2", "Second option")])
    )

    built_embed, view = card.build()
    assert built_embed is embed
    assert view is not None
    assert len(view.children) == 3


def test_embed_card_to_kwargs_omits_view_when_unused():
    card = EmbedCard().title("Hello")
    payload = card.to_kwargs()
    assert "embed" in payload
    assert "view" not in payload


def test_embed_card_theme_presets_apply_colors():
    assert InfoEmbed().build()[0].color == discord.Color.blurple()
    assert SuccessEmbed().build()[0].color == discord.Color.green()
    assert WarningEmbed().build()[0].color == discord.Color.orange()
    assert ErrorEmbed().build()[0].color == discord.Color.red()


def test_embed_card_validates_button_and_select_inputs():
    card = EmbedCard()

    with pytest.raises(ValueError, match="link buttons require a URL"):
        card.button("Docs", style="link")

    with pytest.raises(ValueError, match="only link buttons may include a URL"):
        card.button("Docs", custom_id="docs", url="https://example.com")

    with pytest.raises(ValueError, match="select menus require at least one option"):
        card.select("empty")


def test_embed_card_supports_now_timestamp_helpers():
    embed, _ = EmbedCard().timestamp(True).build()
    assert embed.timestamp is not None
    assert embed.timestamp.tzinfo == timezone.utc

    embed_via_now, _ = EmbedCard().now().build()
    assert embed_via_now.timestamp is not None
    assert embed_via_now.timestamp.tzinfo == timezone.utc

    cleared_embed, _ = EmbedCard().timestamp(False).build()
    assert cleared_embed.timestamp is None
