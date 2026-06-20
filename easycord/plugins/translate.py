"""Translation plugin — slash command using deep-translator for language conversion."""
from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

# Discord locale codes → language names accepted by deep-translator
_LOCALE_TO_LANGUAGE: dict[str, str] = {
    "en-US": "english",
    "en-GB": "english",
    "zh-CN": "chinese (simplified)",
    "zh-TW": "chinese (traditional)",
    "cs": "czech",
    "da": "danish",
    "nl": "dutch",
    "fi": "finnish",
    "fr": "french",
    "de": "german",
    "el": "greek",
    "hi": "hindi",
    "hu": "hungarian",
    "id": "indonesian",
    "it": "italian",
    "ja": "japanese",
    "ko": "korean",
    "lt": "lithuanian",
    "no": "norwegian",
    "pl": "polish",
    "pt-BR": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "es-ES": "spanish",
    "sv-SE": "swedish",
    "th": "thai",
    "tr": "turkish",
    "uk": "ukrainian",
    "vi": "vietnamese",
    "bg": "bulgarian",
    "hr": "croatian",
    "sk": "slovak",
}


def _locale_to_language(locale: discord.Locale | str | None) -> str:
    """Convert a Discord locale to a deep-translator language name."""
    if locale is None:
        return "english"
    value = locale.value if isinstance(locale, discord.Locale) else str(locale)
    return _LOCALE_TO_LANGUAGE.get(value, value)


def _parse_languages(languages: str, ctx_locale: discord.Locale | str | None) -> tuple[str, str]:
    """Parse 'source to target' → (source, target).

    Returns lowercase strings suitable for passing directly to GoogleTranslator.
    If blank, source is 'auto' and target is derived from the user's Discord locale.
    """
    cleaned = languages.strip()
    if not cleaned:
        return "auto", _locale_to_language(ctx_locale)

    # Pad with spaces so " to " is found even when source or target is empty.
    # e.g. "French to " → " french to " → split works; target="" → ctx locale.
    sep = " to "
    padded = f" {cleaned.lower()} "
    idx = padded.find(sep)
    if idx == -1:
        return "auto", cleaned.lower()

    source = padded[:idx].strip()
    target = padded[idx + len(sep):].strip()
    return (source or "auto"), (target or _locale_to_language(ctx_locale))


def _do_translate(text: str, source: str, target: str) -> str:
    """Synchronous translation call — run this in an executor."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise RuntimeError(
            "deep-translator is not installed. "
            "Add it with: pip install 'easycord[translate]'"
        ) from exc

    return GoogleTranslator(source=source, target=target).translate(text)


class TranslatePlugin(Plugin):
    """Slash command that translates text between languages using deep-translator.

    Members type ``/translate``, enter the text they want translated, and a
    ``languages`` pair like ``"French to English"`` or ``"auto to Spanish"``.
    If ``languages`` is left blank the bot translates into the invoking user's
    Discord locale.

    Requires the ``deep-translator`` package::

        pip install "easycord[translate]"

    Then add the plugin::

        from easycord.plugins import TranslatePlugin
        bot.add_plugin(TranslatePlugin())
    """

    @slash(
        description=(
            "Translate text between languages. "
            'Use "source to target" in the languages field, e.g. "French to English". '
            "Leave languages blank to translate into your Discord language."
        ),
    )
    async def translate(
        self,
        ctx: "Context",
        text: str,
        languages: str = "",
    ) -> None:
        source, target = _parse_languages(languages, ctx.locale)

        loop = asyncio.get_running_loop()
        try:
            translated = await loop.run_in_executor(
                None, partial(_do_translate, text, source, target)
            )
        except RuntimeError as exc:
            logger.error("TranslatePlugin: %s", exc)
            await ctx.respond(
                ctx.t(
                    "translate.not_installed",
                    default="Translation is not available on this bot.",
                ),
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("TranslatePlugin: translation request failed")
            await ctx.respond(
                ctx.t(
                    "translate.error",
                    default="Translation failed. Please try again later.",
                ),
                ephemeral=True,
            )
            return

        source_label = "auto-detected" if source == "auto" else source.title()
        embed = discord.Embed(
            description=translated,
            color=discord.Color.blurple(),
        )
        embed.set_author(name=f"{source_label} → {target.title()}")
        embed.set_footer(text=f'Original: {text[:80]}{"…" if len(text) > 80 else ""}')
        await ctx.respond(embed=embed)
