"""Focused tests for Composer-to-Bot option parity."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import discord
import pytest

from easycord.composer import Composer


def test_build_preserves_bot_option_defaults() -> None:
    with patch("easycord.composer.Bot") as bot_class:
        Composer().build()

    bot_class.assert_called_once_with(
        intents=None,
        auto_sync=True,
        sync_guild_id=None,
        load_builtin_plugins=False,
        database=None,
        db_backend=None,
        db_path=None,
        db_auto_sync_guilds=None,
        guild_sync_timeout=30.0,
        localization=None,
        default_locale="en-US",
        translations=None,
        auto_translator=None,
        ai_provider=None,
        enable_conversation_memory=False,
        enable_health_command=False,
        cooldown_cleanup_interval=600.0,
    )


def test_new_bot_and_client_options_are_forwarded() -> None:
    provider = MagicMock()
    activity = discord.Game(name="EasyCord")
    mentions = discord.AllowedMentions.none()

    with patch("easycord.composer.Bot") as bot_class:
        result = (
            Composer()
            .sync_guild_id(123)
            .guild_sync_timeout(None)
            .ai_provider(provider)
            .conversation_memory()
            .health_command()
            .cooldown_cleanup_interval(45.0)
            .client_options(activity=activity, allowed_mentions=mentions)
            .build()
        )

    assert result is bot_class.return_value
    kwargs = bot_class.call_args.kwargs
    assert kwargs["sync_guild_id"] == 123
    assert kwargs["guild_sync_timeout"] is None
    assert kwargs["ai_provider"] is provider
    assert kwargs["enable_conversation_memory"] is True
    assert kwargs["enable_health_command"] is True
    assert kwargs["cooldown_cleanup_interval"] == 45.0
    assert kwargs["activity"] is activity
    assert kwargs["allowed_mentions"] is mentions


def test_boolean_options_can_be_disabled_explicitly() -> None:
    with patch("easycord.composer.Bot") as bot_class:
        (
            Composer()
            .conversation_memory(True)
            .conversation_memory(False)
            .health_command(True)
            .health_command(False)
            .build()
        )

    kwargs = bot_class.call_args.kwargs
    assert kwargs["enable_conversation_memory"] is False
    assert kwargs["enable_health_command"] is False


def test_repeated_client_options_merge_with_later_values_winning() -> None:
    first_activity = discord.Game(name="First")
    second_activity = discord.Game(name="Second")

    with patch("easycord.composer.Bot") as bot_class:
        (
            Composer()
            .client_options(activity=first_activity, max_messages=100)
            .client_options(activity=second_activity)
            .build()
        )

    kwargs = bot_class.call_args.kwargs
    assert kwargs["activity"] is second_activity
    assert kwargs["max_messages"] == 100


@pytest.mark.parametrize(
    ("option", "method"),
    [
        ("intents", "intents"),
        ("auto_sync", "auto_sync"),
        ("sync_guild_id", "sync_guild_id"),
        ("load_builtin_plugins", "builtin_plugins"),
        ("database", "database"),
        ("db_backend", "db_backend"),
        ("db_path", "db_path"),
        ("db_auto_sync_guilds", "db_auto_sync_guilds"),
        ("guild_sync_timeout", "guild_sync_timeout"),
        ("localization", "localization"),
        ("default_locale", "default_locale"),
        ("translations", "translations"),
        ("auto_translator", "auto_translator"),
        ("ai_provider", "ai_provider"),
        ("enable_conversation_memory", "conversation_memory"),
        ("enable_health_command", "health_command"),
        ("cooldown_cleanup_interval", "cooldown_cleanup_interval"),
    ],
)
def test_client_options_reject_easycord_owned_options(
    option: str,
    method: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"{option!r}.*Composer\.{method}",
    ):
        Composer().client_options(**{option: object()})
