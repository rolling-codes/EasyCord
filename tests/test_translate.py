"""Tests for TranslatePlugin."""
from __future__ import annotations

from unittest.mock import patch

import discord
import pytest

from easycord.plugins.translate import TranslatePlugin, _parse_languages, _locale_to_language
from easycord.testing import FakeContextBuilder, invoke
from easycord import Bot, Plugin


# ── Unit tests: helpers ───────────────────────────────────────────────────────


def test_locale_to_language_known():
    assert _locale_to_language(discord.Locale.french) == "french"


def test_locale_to_language_string():
    assert _locale_to_language("de") == "german"


def test_locale_to_language_none_defaults_english():
    assert _locale_to_language(None) == "english"


def test_locale_to_language_unknown_returns_code():
    assert _locale_to_language("xx-XX") == "xx-XX"


def test_parse_languages_blank_uses_locale():
    source, target = _parse_languages("", discord.Locale.french)
    assert source == "auto"
    assert target == "french"


def test_parse_languages_blank_no_locale_defaults_english():
    source, target = _parse_languages("", None)
    assert source == "auto"
    assert target == "english"


def test_parse_languages_pair():
    source, target = _parse_languages("French to English", None)
    assert source == "french"
    assert target == "english"


def test_parse_languages_auto_to_target():
    source, target = _parse_languages("auto to Spanish", None)
    assert source == "auto"
    assert target == "spanish"


def test_parse_languages_single_language_becomes_target():
    source, target = _parse_languages("Japanese", None)
    assert source == "auto"
    assert target == "japanese"


def test_parse_languages_case_insensitive_separator():
    source, target = _parse_languages("German TO English", None)
    assert source == "german"
    assert target == "english"


def test_parse_languages_empty_source_defaults_auto():
    source, target = _parse_languages(" to English", discord.Locale.french)
    assert source == "auto"
    assert target == "english"


def test_parse_languages_empty_target_uses_locale():
    source, target = _parse_languages("French to ", discord.Locale.spain_spanish)
    assert source == "french"
    assert target == "spanish"


# ── Integration tests ─────────────────────────────────────────────────────────


def _make_bot_with_plugin():
    bot = Bot(command_prefix="!", intents=discord.Intents.default())
    plugin = TranslatePlugin.__new__(TranslatePlugin)
    Plugin.__init__(plugin)
    bot.add_plugin(plugin)
    return bot


@pytest.mark.asyncio
async def test_translate_returns_embed_with_translation():
    bot = _make_bot_with_plugin()
    with patch("easycord.plugins.translate._do_translate", return_value="Hello") as mock_t:
        ctx = await invoke(bot, "translate", text="Bonjour", languages="French to English")

    mock_t.assert_called_once_with("Bonjour", "french", "english")
    embed = ctx.responses[-1].embed
    assert embed is not None
    assert embed.description is not None and "Hello" in embed.description
    assert embed.author.name is not None
    assert "French" in embed.author.name and "English" in embed.author.name


@pytest.mark.asyncio
async def test_translate_blank_languages_uses_discord_locale():
    bot = Bot(command_prefix="!", intents=discord.Intents.default())
    plugin = TranslatePlugin.__new__(TranslatePlugin)
    plugin._bot = bot
    Plugin.__init__(plugin)

    with patch("easycord.plugins.translate._do_translate", return_value="Hola") as mock_t:
        ctx = FakeContextBuilder().with_user(1).build()
        ctx.interaction.locale = discord.Locale.spain_spanish
        await plugin.translate(ctx, text="Hello", languages="")

    _args = mock_t.call_args[0]
    assert _args[2] == "spanish"


@pytest.mark.asyncio
async def test_translate_deep_translator_not_installed_responds_error():
    bot = _make_bot_with_plugin()
    with patch(
        "easycord.plugins.translate._do_translate",
        side_effect=RuntimeError("deep-translator is not installed"),
    ):
        ctx = await invoke(bot, "translate", text="Bonjour", languages="French to English")

    assert ctx.last_response is not None
    assert "not available" in ctx.last_response.lower()


@pytest.mark.asyncio
async def test_translate_network_error_responds_error():
    bot = _make_bot_with_plugin()
    with patch(
        "easycord.plugins.translate._do_translate",
        side_effect=Exception("network error"),
    ):
        ctx = await invoke(bot, "translate", text="Bonjour", languages="French to English")

    assert ctx.last_response is not None
    assert "failed" in ctx.last_response.lower() or "later" in ctx.last_response.lower()
