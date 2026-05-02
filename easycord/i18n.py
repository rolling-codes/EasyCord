"""Lightweight localization helpers for EasyCord."""
from __future__ import annotations

import locale as stdlib_locale
import logging
from collections.abc import Mapping
from enum import Enum
from typing import Callable
from typing import Any

logger = logging.getLogger("easycord.i18n")
trace_logger = logging.getLogger("easycord.i18n.trace")


class DiagnosticMode(Enum):
    """Localization diagnostic modes."""
    SILENT = "silent"       # No warnings, no tracking
    WARN = "warn"           # Deduplicated warnings to logger
    STRICT = "strict"       # Raise exceptions on missing keys


class TranslationValidationReport:
    """Report from translation completeness validation."""

    def __init__(self, base_locale: str):
        self.base_locale = base_locale
        self.results: dict[str, dict] = {}

    def add_locale(
        self,
        locale: str,
        missing_keys: list[str],
        orphaned_keys: list[str],
        coverage: float,
    ) -> None:
        """Add validation results for a locale."""
        self.results[locale] = {
            "missing_keys": sorted(missing_keys),
            "orphaned_keys": sorted(orphaned_keys),
            "coverage": coverage,
            "total_missing": len(missing_keys),
            "total_orphaned": len(orphaned_keys),
        }

    def is_valid(self) -> bool:
        """Check if all locales are fully translated."""
        return all(
            result["total_missing"] == 0 for result in self.results.values()
        )

    def summary(self) -> dict:
        """Return summary statistics."""
        total_locales = len(self.results)
        fully_translated = sum(
            1 for r in self.results.values() if r["total_missing"] == 0
        )
        return {
            "base_locale": self.base_locale,
            "total_locales": total_locales,
            "fully_translated": fully_translated,
            "coverage_by_locale": {
                locale: result["coverage"] for locale, result in self.results.items()
            },
        }

    def report_text(self) -> str:
        """Return human-readable report."""
        lines = [f"Translation Validation Report (base: {self.base_locale})"]
        lines.append("")

        for locale in sorted(self.results.keys()):
            result = self.results[locale]
            status = "✓" if result["total_missing"] == 0 else "✗"
            lines.append(
                f"{status} {locale}: {result['coverage']:.1%} coverage "
                f"({result['total_missing']} missing)"
            )
            if result["missing_keys"]:
                lines.append(
                    f"  Missing: {', '.join(result['missing_keys'][:3])}"
                    f"{'...' if len(result['missing_keys']) > 3 else ''}"
                )
            if result["orphaned_keys"]:
                lines.append(
                    f"  Orphaned: {', '.join(result['orphaned_keys'][:3])}"
                    f"{'...' if len(result['orphaned_keys']) > 3 else ''}"
                )
        return "\n".join(lines)


class LocalizationDiagnostics:
    """Track missing keys and invalid placeholders with deduplication."""

    def __init__(self, mode: DiagnosticMode = DiagnosticMode.SILENT):
        self.mode = mode
        self._seen_missing: set[tuple[str, str]] = set()
        self._seen_placeholder: set[tuple[str, str]] = set()
        self._missing_count = 0
        self._placeholder_count = 0

    def report_missing_key(
        self,
        key: str,
        locale: str,
        fallback_locale: str | None = None,
    ) -> None:
        """Report a missing translation key."""
        if self.mode == DiagnosticMode.SILENT:
            return

        cache_key = (key, locale)
        if cache_key in self._seen_missing:
            return

        self._seen_missing.add(cache_key)
        self._missing_count += 1

        fallback_msg = f" (fallback: {fallback_locale})" if fallback_locale else ""
        message = f"Missing key '{key}' in locale '{locale}'{fallback_msg}"

        if self.mode == DiagnosticMode.STRICT:
            raise KeyError(message)
        elif self.mode == DiagnosticMode.WARN:
            logger.warning(message)

    def report_invalid_placeholder(
        self,
        key: str,
        template: str,
        placeholder: str,
    ) -> None:
        """Report a template with missing/invalid placeholders."""
        if self.mode == DiagnosticMode.SILENT:
            return

        cache_key = (key, placeholder)
        if cache_key in self._seen_placeholder:
            return

        self._seen_placeholder.add(cache_key)
        self._placeholder_count += 1

        message = f"Invalid placeholder in '{key}': template has '{placeholder}' but value not provided"

        if self.mode == DiagnosticMode.STRICT:
            raise KeyError(message)
        elif self.mode == DiagnosticMode.WARN:
            logger.warning(message)

    def missing_keys_summary(self) -> dict[str, int]:
        """Return summary of missing keys."""
        return {
            "total_missing": self._missing_count,
            "total_placeholders": self._placeholder_count,
            "unique_missing": len(self._seen_missing),
            "unique_placeholders": len(self._seen_placeholder),
        }

    def reset(self) -> None:
        """Reset all diagnostics."""
        self._seen_missing.clear()
        self._seen_placeholder.clear()
        self._missing_count = 0
        self._placeholder_count = 0


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
    """Detect the system's locale preference.

    Returns normalized locale string (e.g., 'en-US') or None if detection fails.
    """
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
        auto_translator: Callable[[str, str, str], str | None] | None = None,
        auto_detect_system_locale: bool = False,
        warn_invalid_locale: bool = True,
        diagnostic_mode: DiagnosticMode = DiagnosticMode.SILENT,
        track_metrics: bool = False,
    ) -> None:
        self.default_locale = _normalize_locale(default_locale) or "en-US"
        self._catalogs: dict[str, dict[str, str]] = {}
        self._auto_translator = auto_translator
        self._auto_detect_system_locale = auto_detect_system_locale
        self._warn_invalid_locale = warn_invalid_locale
        self._system_locale: str | None = None
        self.diagnostics = LocalizationDiagnostics(mode=diagnostic_mode)
        self.track_metrics = track_metrics
        self._metrics: dict[str, int] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "fallback_uses": 0,
            "missing_keys": 0,
            "locale_frequency": {},
        } if track_metrics else {}
        if auto_detect_system_locale:
            self._system_locale = detect_os_locale()
            if self._system_locale:
                logger.debug(f"Detected system locale: {self._system_locale}")
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

    def get_metrics(self) -> dict[str, int | dict]:
        """Get resolution metrics (only if track_metrics=True).

        Returns dict with:
        - cache_hits: successful lookups in preferred locale
        - cache_misses: lookups that fell back
        - fallback_uses: times default locale was used
        - missing_keys: keys not found in any locale
        - locale_frequency: usage count per locale
        """
        if not self.track_metrics:
            return {}
        return dict(self._metrics)

    def reset_metrics(self) -> None:
        """Reset all metrics to zero (for per-session tracking)."""
        if self.track_metrics:
            self._metrics["cache_hits"] = 0
            self._metrics["cache_misses"] = 0
            self._metrics["fallback_uses"] = 0
            self._metrics["missing_keys"] = 0
            self._metrics["locale_frequency"] = {}

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

    def auto_detect_locale(
        self,
        user_locale: Any = None,
        guild_locale: Any = None,
    ) -> str | None:
        """Detect the best locale using auto-detection chain.

        Detection priority:
        1. Explicit user locale
        2. Explicit guild locale
        3. System locale (if auto_detect_system_locale=True)
        4. Default locale

        Returns the best matching locale or None if no suitable match found.
        Validates that returned locale is registered in catalogs.
        """
        candidates = [
            _normalize_locale(user_locale),
            _normalize_locale(guild_locale),
            self._system_locale,
            self.default_locale,
        ]

        for candidate in candidates:
            if not candidate:
                continue
            if not self._is_valid_locale(candidate):
                if self._warn_invalid_locale:
                    logger.warning(f"Invalid or unsupported locale: {candidate}")
                continue
            chain = self.resolve_chain(candidate)
            for loc in chain:
                if loc in self._catalogs:
                    return loc

        return self.default_locale if self.default_locale in self._catalogs else None

    def _is_valid_locale(self, locale: str) -> bool:
        """Check if locale format is valid (basic validation)."""
        if not locale or not isinstance(locale, str):
            return False
        parts = locale.split("-")
        if not parts[0] or len(parts[0]) < 2:
            return False
        if len(parts) > 1 and len(parts[1]) != 2:
            return False
        return True

    def _trace_resolution(
        self,
        key: str,
        raw_locale: Any,
        normalized_locale: str | None,
        guild_locale: Any,
        resolved_locale: str | None,
        fallback_chain: list[str],
        found_in: str | None,
        cache_hit: bool,
    ) -> None:
        """Trace locale resolution path (debug-only telemetry)."""
        if not trace_logger.isEnabledFor(logging.DEBUG):
            return

        trace_logger.debug(
            f"[{key}] "
            f"raw_locale={raw_locale!r} "
            f"normalized={normalized_locale!r} "
            f"guild={guild_locale!r} "
            f"resolved={resolved_locale!r} "
            f"chain={fallback_chain!r} "
            f"found_in={found_in!r} "
            f"cache_hit={cache_hit}"
        )

    def validate_completeness(
        self, base_locale: str | None = None
    ) -> TranslationValidationReport:
        """Validate translation completeness against a base locale.

        Parameters
        ----------
        base_locale : str, optional
            Locale to use as the source of truth for required keys.
            Defaults to the manager's default_locale.

        Returns
        -------
        TranslationValidationReport
            Report with missing keys, orphaned keys, and coverage stats.
        """
        base = base_locale or self.default_locale
        if base not in self._catalogs:
            raise ValueError(f"Base locale '{base}' not registered")

        base_keys = set(self._catalogs[base].keys())
        report = TranslationValidationReport(base)

        for locale in sorted(self._catalogs.keys()):
            if locale == base:
                report.add_locale(locale, [], [], 1.0)
                continue

            locale_keys = set(self._catalogs[locale].keys())
            missing_keys = sorted(base_keys - locale_keys)
            orphaned_keys = sorted(locale_keys - base_keys)
            coverage = (len(locale_keys & base_keys) / len(base_keys)) if base_keys else 1.0

            report.add_locale(locale, missing_keys, orphaned_keys, coverage)

        return report

    def get(
        self,
        key: str,
        *,
        locale: Any = None,
        guild_locale: Any = None,
        default: str | None = None,
    ) -> str:
        """Look up a translated string and fall back safely if missing."""
        requested_locale = _normalize_locale(locale)
        guild_normalized = _normalize_locale(guild_locale)
        preferred_chain: list[str] = []
        for candidate in (requested_locale, guild_normalized):
            if not candidate:
                continue
            parts = candidate.split("-")
            for index in range(len(parts), 0, -1):
                value = "-".join(parts[:index])
                if value not in preferred_chain:
                    preferred_chain.append(value)

        # Check preferred chain (user locale + guild locale)
        for candidate in preferred_chain:
            catalog = self._catalogs.get(candidate)
            if catalog and key in catalog:
                if self.track_metrics:
                    self._metrics["cache_hits"] += 1
                    self._metrics["locale_frequency"][candidate] = (
                        self._metrics["locale_frequency"].get(candidate, 0) + 1
                    )
                self._trace_resolution(
                    key, locale, requested_locale, guild_locale, candidate,
                    preferred_chain, candidate, True
                )
                return catalog[key]

        auto_translated = self._auto_translate_missing(
            key,
            locale=locale,
            guild_locale=guild_locale,
            default=default,
        )
        if auto_translated is not None:
            if self.track_metrics and requested_locale:
                self._metrics["cache_hits"] += 1
            self._trace_resolution(
                key, locale, requested_locale, guild_locale, None,
                preferred_chain, "auto_translator", True
            )
            return auto_translated

        # Fall back to default locale chain
        if self.track_metrics:
            self._metrics["cache_misses"] += 1
        default_chain = self.resolve_chain(self.default_locale)
        for candidate in default_chain:
            catalog = self._catalogs.get(candidate)
            if catalog and key in catalog:
                if self.track_metrics:
                    self._metrics["fallback_uses"] += 1
                    self._metrics["locale_frequency"][candidate] = (
                        self._metrics["locale_frequency"].get(candidate, 0) + 1
                    )
                if requested_locale:
                    self.diagnostics.report_missing_key(
                        key, requested_locale, fallback_locale=candidate
                    )
                self._trace_resolution(
                    key, locale, requested_locale, guild_locale, candidate,
                    default_chain, candidate, False
                )
                return catalog[key]

        # Not found anywhere
        if self.track_metrics:
            self._metrics["missing_keys"] += 1
        if requested_locale:
            self.diagnostics.report_missing_key(key, requested_locale)
        self._trace_resolution(
            key, locale, requested_locale, guild_locale, None,
            default_chain, None, False
        )
        return default if default is not None else key

    def _find_source_for_key(
        self,
        key: str,
        *,
        default: str | None,
    ) -> tuple[str, str] | None:
        for candidate in self.resolve_chain(self.default_locale):
            catalog = self._catalogs.get(candidate)
            if catalog and key in catalog:
                return candidate, catalog[key]

        if default is not None:
            return self.default_locale, default

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
