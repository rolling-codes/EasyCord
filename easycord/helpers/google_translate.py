"""Google Translate integration helpers for i18n and command-name localization."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from functools import partial

import discord
from discord import app_commands

logger = logging.getLogger(__name__)

# BCP47 codes that need special handling for Google Translate
_PASSTHROUGH = {"zh-CN", "zh-TW"}


def _to_google_lang(bcp47: str) -> str:
    """Convert a BCP 47 locale code to the language code Google Translate expects.

    Most codes just need the region stripped: "en-US" → "en", "pt-BR" → "pt".
    Chinese variants are passed through unchanged so Google distinguishes them.
    """
    if bcp47 in _PASSTHROUGH:
        return bcp47
    return bcp47.split("-")[0].split("_")[0]


def _sync_translate(text: str, source_lang: str, target_lang: str) -> str | None:
    """Run GoogleTranslator synchronously. Returns None on any failure."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        logger.warning(
            "deep-translator is not installed; Google Translate unavailable. "
            "Install with: pip install 'easycord[translate]'"
        )
        return None
    try:
        return GoogleTranslator(source=source_lang, target=target_lang).translate(text)
    except Exception:
        logger.debug("Google Translate failed for %r → %r", source_lang, target_lang, exc_info=True)
        return None


def make_google_auto_translator() -> Callable[[str, str, str], str | None]:
    """Return a callable suitable for ``LocalizationManager(auto_translator=...)``.

    The callback translates a string from one locale to another using Google
    Translate whenever the LocalizationManager cannot find a key in a
    requested locale's catalog.

    Usage::

        from easycord import LocalizationManager
        from easycord.helpers.google_translate import make_google_auto_translator

        localization = LocalizationManager(
            auto_translator=make_google_auto_translator(),
            translations={"en-US": {"greeting": "Hello!"}},
        )
        # A French user calling ctx.t("greeting") gets "Bonjour!" automatically.
    """

    def _auto_translator(source_text: str, source_locale: str, target_locale: str) -> str | None:
        src = _to_google_lang(source_locale)
        tgt = _to_google_lang(target_locale)
        if src == tgt:
            return None
        return _sync_translate(source_text, src, tgt)

    return _auto_translator


class GoogleTranslateTranslator(app_commands.Translator):
    """discord.py ``Translator`` that localizes command names via Google Translate.

    Install it on the command tree before syncing::

        from easycord.helpers.google_translate import GoogleTranslateTranslator

        await bot.tree.set_translator(GoogleTranslateTranslator())
        await bot.sync_commands()

    After syncing, Discord shows localized command names in each user's language
    (e.g. French users see ``/traduire``) while the interaction payload always
    carries the canonical name, so no routing changes are required.

    Only command names are translated — descriptions are left as-is to avoid
    the 100-character limit being hit by verbose translated phrases.
    """

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContext,
    ) -> str | None:
        if context.location is not app_commands.TranslationContextLocation.command_name:
            return None

        source_text = str(string)
        target_lang = _to_google_lang(locale.value)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, partial(_sync_translate, source_text, "auto", target_lang)
        )
        if result is None:
            return None

        # Discord command names must be lowercase with no leading/trailing whitespace
        translated = result.strip().lower()
        # Return None if translation is identical to the original (no-op)
        return translated if translated != source_text.lower() else None
