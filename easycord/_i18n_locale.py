"""Locale helpers for EasyCord localization."""
from __future__ import annotations

import locale as stdlib_locale
from typing import Any


def _normalize_locale(locale: Any) -> str | None:
    """Normalize locale string to standard format (en-US, not en_US)."""
    if locale is None:
        return None
    if hasattr(locale, "value"):
        locale = locale.value
    text = str(locale).strip()
    if not text:
        return None
    return text.replace("_", "-")


def detect_os_locale() -> str | None:
    """Detect the system's locale preference."""
    try:
        system_locale = stdlib_locale.getdefaultlocale()
        if system_locale and system_locale[0]:
            lang = system_locale[0]
            country = system_locale[1]
            if country:
                return _normalize_locale(f"{lang}_{country}")
            return _normalize_locale(lang)
    except (AttributeError, ValueError):
        pass
    return None


def is_valid_locale(locale: str) -> bool:
    """Check if a locale tag has a supported BCP 47-like shape."""
    if not locale or not isinstance(locale, str):
        return False

    parts = locale.split("-")
    if not parts[0] or len(parts[0]) < 2 or len(parts[0]) > 3:
        return False

    if len(parts) == 1:
        return True

    second = parts[1]
    if not second:
        return False

    if len(second) == 4:
        if len(parts) == 2:
            return True
        if len(parts) == 3:
            third = parts[2]
            return len(third) == 2
        return False

    if len(second) == 2:
        return len(parts) == 2

    return False


def build_locale_chain(
    default_locale: str,
    *,
    locale: Any = None,
    guild_locale: Any = None,
) -> tuple[tuple[str | None, str | None, bool], list[str]]:
    """Return the cache key and fallback chain for a locale lookup."""
    normalized_locale = _normalize_locale(locale)
    normalized_guild = _normalize_locale(guild_locale)

    if normalized_locale is None and normalized_guild is None:
        cache_key = (None, None, True)
        candidates = [default_locale]
    else:
        cache_key = (normalized_locale, normalized_guild, False)
        candidates = [normalized_locale, normalized_guild, default_locale]

    chain: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        parts = candidate.split("-")
        for index in range(len(parts), 0, -1):
            value = "-".join(parts[:index])
            if value not in chain:
                chain.append(value)
    return cache_key, chain


def build_preferred_locale_chain(*locales: Any) -> list[str]:
    """Build a locale chain without adding the default locale."""
    chain: list[str] = []
    for candidate in (_normalize_locale(locale) for locale in locales):
        if not candidate:
            continue
        parts = candidate.split("-")
        for index in range(len(parts), 0, -1):
            value = "-".join(parts[:index])
            if value not in chain:
                chain.append(value)
    return chain
