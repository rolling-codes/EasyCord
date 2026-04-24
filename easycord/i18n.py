"""Lightweight localization helpers for EasyCord."""
from __future__ import annotations

from collections.abc import Mapping
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
    checks the interaction locale first, then the guild locale, then the
    configured default locale, and finally a simple language-only fallback
    (for example ``pt-BR`` → ``pt``).
    """

    def __init__(
        self,
        *,
        default_locale: str = "en-US",
        translations: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        self.default_locale = _normalize_locale(default_locale) or "en-US"
        self._catalogs: dict[str, dict[str, str]] = {}
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
        for candidate in self.resolve_chain(locale, guild_locale=guild_locale):
            catalog = self._catalogs.get(candidate)
            if catalog and key in catalog:
                return catalog[key]
        return default if default is not None else key

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
