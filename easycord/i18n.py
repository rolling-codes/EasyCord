"""Lightweight localization helpers for EasyCord."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Callable
from typing import Any


def _normalize_locale(locale: Any) -> str | None:
    if locale is None:
        return None
    if hasattr(locale, "value"):
        locale = locale.value
    text = str(locale).strip()
    if not text:
        return None
    return text.replace("_", "-")


class LocalizationManager:
    """Store and resolve string templates by locale.

    The manager keeps a dictionary of catalogs keyed by locale string. A lookup
    checks the interaction locale and guild locale first. If a key is still
    missing and ``auto_translator`` is configured, the manager can synthesize a
    translation and cache it for subsequent lookups. If no translation is
    available, it falls back to the configured default locale (including
    language-only fallback, for example ``pt-BR`` → ``pt``).
    """

    def __init__(
        self,
        *,
        default_locale: str = "en-US",
        translations: Mapping[str, Mapping[str, str]] | None = None,
        auto_translator: Callable[[str, str, str], str | None] | None = None,
    ) -> None:
        self.default_locale = _normalize_locale(default_locale) or "en-US"
        self._catalogs: dict[str, dict[str, str]] = {}
        self._auto_translator = auto_translator
        for locale, values in (translations or {}).items():
            self.register(locale, values)

    def register(self, locale: Any, translations: Mapping[str, str]) -> None:
        """Register or merge a locale catalog."""
        normalized = _normalize_locale(locale)
        if normalized is None:
            raise ValueError("locale must be a non-empty string")
        self._catalogs.setdefault(normalized, {}).update(
            {str(key): str(value) for key, value in translations.items()}
        )

    def locales(self) -> list[str]:
        """Return the known locale tags."""
        return sorted(self._catalogs)

    def resolve_chain(
        self,
        locale: Any = None,
        *,
        guild_locale: Any = None,
    ) -> list[str]:
        """Return the fallback chain for a locale lookup."""
        chain: list[str] = []
        for candidate in (
            _normalize_locale(locale),
            _normalize_locale(guild_locale),
            self.default_locale,
        ):
            if not candidate:
                continue
            parts = candidate.split("-")
            for index in range(len(parts), 0, -1):
                value = "-".join(parts[:index])
                if value not in chain:
                    chain.append(value)
        return chain

    def get(
        self,
        key: str,
        *,
        locale: Any = None,
        guild_locale: Any = None,
        default: str | None = None,
    ) -> str:
        """Look up a translated string and fall back safely if missing."""
        preferred_chain: list[str] = []
        for candidate in (_normalize_locale(locale), _normalize_locale(guild_locale)):
            if not candidate:
                continue
            parts = candidate.split("-")
            for index in range(len(parts), 0, -1):
                value = "-".join(parts[:index])
                if value not in preferred_chain:
                    preferred_chain.append(value)

        for candidate in preferred_chain:
            catalog = self._catalogs.get(candidate)
            if catalog and key in catalog:
                return catalog[key]

        auto_translated = self._auto_translate_missing(
            key,
            locale=locale,
            guild_locale=guild_locale,
            default=default,
        )
        if auto_translated is not None:
            return auto_translated

        for candidate in self.resolve_chain(self.default_locale):
            catalog = self._catalogs.get(candidate)
            if catalog and key in catalog:
                return catalog[key]
        return default if default is not None else key

    def _find_source_for_key(
        self,
        key: str,
        *,
        default: str | None,
    ) -> tuple[str, str] | None:
        """Resolve source locale/text used for auto-translation.

        Preference order:
        1) caller-supplied ``default`` text
        2) key from the default locale chain
        3) first key found in any registered locale (stable sorted order)
        """
        if default is not None:
            return self.default_locale, default

        for candidate in self.resolve_chain(self.default_locale):
            catalog = self._catalogs.get(candidate)
            if catalog and key in catalog:
                return candidate, catalog[key]

        for candidate in sorted(self._catalogs):
            catalog = self._catalogs[candidate]
            if key in catalog:
                return candidate, catalog[key]
        return None

    def _auto_translate_missing(
        self,
        key: str,
        *,
        locale: Any = None,
        guild_locale: Any = None,
        default: str | None = None,
    ) -> str | None:
        """Translate and cache a missing key for the requested target locale."""
        if self._auto_translator is None:
            return None

        target_locale = _normalize_locale(locale) or _normalize_locale(guild_locale)
        if target_locale is None:
            return None

        source = self._find_source_for_key(key, default=default)
        if source is None:
            return None
        source_locale, source_text = source
        if source_locale == target_locale:
            return None

        translated = self._auto_translator(source_text, source_locale, target_locale)
        if not translated:
            return None
        self.register(target_locale, {key: translated})
        return translated

    def format(
        self,
        key: str,
        *,
        locale: Any = None,
        guild_locale: Any = None,
        default: str | None = None,
        **kwargs,
    ) -> str:
        """Look up a translated string and format it with keyword arguments."""
        template = self.get(
            key,
            locale=locale,
            guild_locale=guild_locale,
            default=default,
        )
        return template.format(**kwargs)
