"""Lightweight localization helpers for EasyCord."""
from __future__ import annotations

from datetime import datetime
import logging
from collections.abc import Mapping
from typing import Callable
from typing import Any

from ._i18n_diagnostics import DiagnosticMode, LocalizationDiagnostics
from ._i18n_locale import (
    _normalize_locale,
    build_locale_chain,
    build_preferred_locale_chain,
    detect_os_locale,
    is_valid_locale,
)
from ._i18n_validation import TranslationValidationReport

logger = logging.getLogger("easycord.i18n")
trace_logger = logging.getLogger("easycord.i18n.trace")


class LocalizationManager:
    """Store and resolve string templates by locale.

    The manager keeps a dictionary of catalogs keyed by locale string. A lookup
    checks the interaction locale first, then the guild locale, then the
    configured default locale, and finally a simple language-only fallback
    (for example ``pt-BR`` → ``pt``).

    Thread Safety:
    This class is NOT thread-safe. It assumes single-threaded access within
    a request/event scope. Metrics and diagnostics state use non-atomic counters.
    For concurrent access (e.g., sharded deployments, async locale providers),
    external synchronization is required.
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
        max_auto_translated_locales: int = 50,
        max_tracked_locales: int = 100,
        plural_rule_evaluator: Callable[[str, float | int], str] | None = None,
    ) -> None:
        self.default_locale = _normalize_locale(default_locale) or "en-US"
        self._catalogs: dict[str, dict[str, str]] = {}
        self._auto_translator = auto_translator
        self._auto_detect_system_locale = auto_detect_system_locale
        self._warn_invalid_locale = warn_invalid_locale
        self._system_locale: str | None = None
        self.diagnostics = LocalizationDiagnostics(mode=diagnostic_mode)
        self.track_metrics = track_metrics
        self._max_auto_translated = max_auto_translated_locales
        self._max_tracked_locales = max_tracked_locales
        self._auto_translated_count = 0
        self._plural_rule_evaluator = plural_rule_evaluator or default_plural_rule
        self._metrics: dict[str, Any] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "fallback_resolution": 0,
            "missing_keys": 0,
            "auto_translated": 0,
            "locale_frequency": {},
        } if track_metrics else {}
        self._chain_cache: dict[tuple[str | None, str | None, bool], list[str]] = {}
        self._reporting = False
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

        Returns IMMUTABLE deep snapshot to prevent caller mutation of internal state.

        Returns dict with:
        - cache_hits: successful lookups in preferred locale (user/guild locale)
        - cache_misses: lookups that required fallback resolution
        - fallback_resolution: times default locale chain was successfully used
        - auto_translated: keys successfully auto-translated
        - missing_keys: keys not found in any locale or via auto-translation
        - locale_frequency: usage count per locale (capped at max_tracked_locales)

        Semantics:
        - cache_hit: key found in requested/guild locale, no fallback needed
        - cache_miss: key not in requested locale, fallback occurred
        - fallback_resolution: fallback to default locale succeeded
        - auto_translated: auto-translator provided translation
        - missing_key: key not found anywhere, returned as-is

        Note: locale_frequency is pruned when exceeding max_tracked_locales
        to prevent unbounded memory growth.
        """
        if not self.track_metrics:
            return {}
        # Return deep copy to prevent caller from mutating internal state
        return {
            "cache_hits": self._metrics["cache_hits"],
            "cache_misses": self._metrics["cache_misses"],
            "fallback_resolution": self._metrics["fallback_resolution"],
            "auto_translated": self._metrics["auto_translated"],
            "missing_keys": self._metrics["missing_keys"],
            "locale_frequency": dict(self._metrics["locale_frequency"]),
        }

    def reset_metrics(self) -> None:
        """Reset all metrics to zero (for per-session tracking)."""
        if self.track_metrics:
            self._metrics["cache_hits"] = 0
            self._metrics["cache_misses"] = 0
            self._metrics["fallback_resolution"] = 0
            self._metrics["auto_translated"] = 0
            self._metrics["missing_keys"] = 0
            self._metrics["locale_frequency"] = {}
        self._auto_translated_count = 0

    def resolve_chain(
        self,
        locale: Any = None,
        *,
        guild_locale: Any = None,
    ) -> list[str]:
        """Return the fallback chain for a locale lookup (with memoization)."""
        cache_key, chain = build_locale_chain(
            self.default_locale,
            locale=locale,
            guild_locale=guild_locale,
        )
        if cache_key in self._chain_cache:
            return self._chain_cache[cache_key]

        if len(self._chain_cache) < 1000:
            self._chain_cache[cache_key] = chain
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
        """Check if locale format is valid (BCP 47 support).

        Valid formats:
        - en (language)
        - en-US (language-region)
        - zh-Hant (language-script)
        - zh-Hant-HK (language-script-region)
        - pt-BR (language-region)

        Requirements:
        - language part: 2-3 characters
        - script part (optional): 4 characters (Hant, Latn, etc.)
        - region part (optional): 2 characters (US, BR, HK, etc.)
        """
        return is_valid_locale(locale)

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

    def _lookup_in_catalog(
        self,
        cat: dict[str, str],
        candidate_locale: str,
        key: str,
        count: float | int | None,
    ) -> str | None:
        if count is not None:
            category = self._plural_rule_evaluator(candidate_locale, count)
            suffix_key = f"{key}_{category}"
            if suffix_key in cat:
                return cat[suffix_key]
        if key in cat:
            return cat[key]
        return None

    def get(
        self,
        key: str,
        *,
        locale: Any = None,
        guild_locale: Any = None,
        default: str | None = None,
        count: float | int | None = None,
    ) -> str:
        """Look up a translated string and fall back safely if missing."""
        requested_locale = _normalize_locale(locale)
        guild_normalized = _normalize_locale(guild_locale)

        preferred_chain = build_preferred_locale_chain(
            requested_locale,
            guild_normalized,
        )

        # Check preferred chain (user locale + guild locale)
        for candidate in preferred_chain:
            catalog = self._catalogs.get(candidate)
            if catalog:
                val = self._lookup_in_catalog(catalog, candidate, key, count)
                if val is not None:
                    if self.track_metrics:
                        self._metrics["cache_hits"] += 1
                        self._update_locale_frequency(candidate)
                    self._trace_resolution(
                        key, locale, requested_locale, guild_locale, candidate,
                        preferred_chain, candidate, True
                    )
                    return val

        # Try auto-translation if enabled and key not found in preferred chain
        if self.track_metrics:
            self._metrics["cache_misses"] += 1

        auto_translated = self._auto_translate_missing(
            key,
            locale=locale,
            guild_locale=guild_locale,
            default=default,
            count=count,
        )
        if auto_translated is not None:
            if self.track_metrics:
                self._metrics["auto_translated"] += 1
                if requested_locale:
                    self._update_locale_frequency(requested_locale)
            self._trace_resolution(
                key, locale, requested_locale, guild_locale, requested_locale,
                preferred_chain, "auto_translator", False
            )
            return auto_translated

        # Fall back to default locale chain
        default_chain = self.resolve_chain(self.default_locale)
        for candidate in default_chain:
            catalog = self._catalogs.get(candidate)
            if catalog:
                val = self._lookup_in_catalog(catalog, candidate, key, count)
                if val is not None:
                    if self.track_metrics:
                        self._metrics["fallback_resolution"] += 1
                        self._update_locale_frequency(candidate)
                    if requested_locale:
                        self.diagnostics.report_missing_key(
                            key, requested_locale, fallback_locale=candidate
                        )
                    self._trace_resolution(
                        key, locale, requested_locale, guild_locale, candidate,
                        default_chain, candidate, False
                    )
                    return val

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

    def _update_locale_frequency(self, locale: str) -> None:
        """Update locale frequency metrics with bounds checking."""
        freq = self._metrics["locale_frequency"]
        freq[locale] = freq.get(locale, 0) + 1

        # Prune if exceeds max tracked locales
        if len(freq) > self._max_tracked_locales:
            # Remove least-frequently-used locale
            min_locale = min(freq, key=freq.get)
            del freq[min_locale]

    def _find_source_for_key(
        self,
        key: str,
        *,
        default: str | None,
        count: float | int | None = None,
    ) -> tuple[str, str, str] | None:
        for candidate in self.resolve_chain(self.default_locale):
            catalog = self._catalogs.get(candidate)
            if catalog:
                if count is not None:
                    category = self._plural_rule_evaluator(candidate, count)
                    suffix_key = f"{key}_{category}"
                    if suffix_key in catalog:
                        return candidate, suffix_key, catalog[suffix_key]
                if key in catalog:
                    return candidate, key, catalog[key]

        if default is not None:
            return self.default_locale, key, default

        for candidate in sorted(self._catalogs):
            catalog = self._catalogs[candidate]
            if count is not None:
                category = self._plural_rule_evaluator(candidate, count)
                suffix_key = f"{key}_{category}"
                if suffix_key in catalog:
                    return candidate, suffix_key, catalog[suffix_key]
            if key in catalog:
                return candidate, key, catalog[key]
        return None

    def _auto_translate_missing(
        self,
        key: str,
        *,
        locale: Any = None,
        guild_locale: Any = None,
        default: str | None = None,
        count: float | int | None = None,
    ) -> str | None:
        if self._auto_translator is None:
            return None

        target_locale = _normalize_locale(locale) or _normalize_locale(guild_locale)
        if target_locale is None:
            return None

        source = self._find_source_for_key(key, default=default, count=count)
        if source is None:
            return None
        source_locale, resolved_key, source_text = source
        if source_locale == target_locale:
            return None

        translated = self._auto_translator(source_text, source_locale, target_locale)
        if not translated:
            return None

        if count is not None:
            target_category = self._plural_rule_evaluator(target_locale, count)
            register_key = f"{key}_{target_category}"
        else:
            register_key = resolved_key

        # Only register if within bounds to prevent unbounded catalog growth
        if self._auto_translated_count < self._max_auto_translated:
            self.register(target_locale, {register_key: translated})
            self._auto_translated_count += 1
        return translated

    def t(
        self,
        key: str,
        *,
        locale: Any = None,
        guild_locale: Any = None,
        default: str | None = None,
        **kwargs,
    ) -> str:
        """Alias for format()."""
        return self.format(
            key,
            locale=locale,
            guild_locale=guild_locale,
            default=default,
            **kwargs,
        )

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
        count = kwargs.get("count")
        template = self.get(
            key,
            locale=locale,
            guild_locale=guild_locale,
            default=default,
            count=count,
        )
        try:
            return template.format(**kwargs)
        except KeyError as exc:
            if self._reporting:
                # If we're already reporting, don't recurse
                raise
            self._reporting = True
            try:
                missing = str(exc).strip("'")
                self.diagnostics.report_invalid_placeholder(key, template, missing)
            finally:
                self._reporting = False
            raise


def default_plural_rule(locale: str, count: float | int) -> str:
    """Default CLDR plural rule evaluator for common languages."""
    lang = (locale or "").split("-")[0].split("_")[0].lower()
    try:
        if isinstance(count, str):
            if "." in count:
                count = float(count)
            else:
                count = int(count)
        n = abs(count)
    except Exception:
        n = count

    is_int = isinstance(n, int) or (isinstance(n, float) and n.is_integer())
    val = int(n) if is_int else n

    if lang in ("ja", "zh", "ko", "vi", "th", "ms", "id"):
        return "other"
    elif lang == "fr":
        if val == 0 or val == 1:
            return "one"
        return "other"
    elif lang == "pt":
        loc_lower = locale.lower()
        if "pt-br" in loc_lower or "pt_br" in loc_lower:
            if val == 0 or val == 1:
                return "one"
        else:
            if val == 1:
                return "one"
        return "other"
    elif lang in ("ru", "uk", "be"):
        if not is_int:
            return "other"
        if val % 10 == 1 and val % 100 != 11:
            return "one"
        elif val % 10 in (2, 3, 4) and val % 100 not in (12, 13, 14):
            return "few"
        elif val % 10 == 0 or val % 10 in (5, 6, 7, 8, 9) or val % 100 in (11, 12, 13, 14):
            return "many"
        return "other"
    elif lang == "pl":
        if not is_int:
            return "other"
        if val == 1:
            return "one"
        elif val % 10 in (2, 3, 4) and val % 100 not in (12, 13, 14):
            return "few"
        elif val % 10 in (0, 1, 5, 6, 7, 8, 9) or val % 100 in (11, 12, 13, 14):
            return "many"
        return "other"
    elif lang == "ar":
        if not is_int:
            return "other"
        if val == 0:
            return "zero"
        elif val == 1:
            return "one"
        elif val == 2:
            return "two"
        elif 3 <= val % 100 <= 10:
            return "few"
        elif 11 <= val % 100 <= 99:
            return "many"
        return "other"
    else:
        if val == 1:
            return "one"
        return "other"


NUM_FORMATS = {
    "en": (",", "."),
    "de": (".", ","),
    "fr": ("\xa0", ","),  # non-breaking space
    "es": (".", ","),
    "it": (".", ","),
    "pt": (".", ","),
    "ru": ("\xa0", ","),
    "pl": ("\xa0", ","),
    "uk": ("\xa0", ","),
    "nl": (".", ","),
    "da": (".", ","),
    "sv": ("\xa0", ","),
    "nb": ("\xa0", ","),
    "nn": ("\xa0", ","),
    "fi": ("\xa0", ","),
    "tr": (".", ","),
    "el": (".", ","),
    "ar": (",", "."),
    "ja": (",", "."),
    "zh": (",", "."),
    "ko": (",", "."),
}


def format_number(value: float | int, locale: str | None = None) -> str:
    """Format a number according to locale-specific conventions."""
    if locale:
        locale = locale.strip()
    lang = (locale or "").split("-")[0].split("_")[0].lower()
    if not lang:
        lang = "en"

    thousand_sep, decimal_sep = NUM_FORMATS.get(lang, (",", "."))

    if isinstance(value, int):
        s = str(abs(value))
        parts = []
        while s:
            parts.append(s[-3:])
            s = s[:-3]
        formatted_int = thousand_sep.join(reversed(parts))
        return f"-{formatted_int}" if value < 0 else formatted_int
    else:
        val_str = str(value)
        if "e" in val_str or "E" in val_str:
            val_str = f"{value:.10f}".rstrip('0').rstrip('.')

        if "." in val_str:
            int_part, frac_part = val_str.split(".", 1)
        else:
            int_part, frac_part = val_str, ""

        is_negative = int_part.startswith("-")
        int_part = int_part.lstrip("-")

        parts = []
        while int_part:
            parts.append(int_part[-3:])
            int_part = int_part[:-3]
        formatted_int = thousand_sep.join(reversed(parts)) or "0"

        if is_negative:
            formatted_int = f"-{formatted_int}"

        if frac_part:
            return f"{formatted_int}{decimal_sep}{frac_part}"
        return formatted_int


DATE_FORMATS = {
    "en": "%m/%d/%Y",
    "en-us": "%m/%d/%Y",
    "en-gb": "%d/%m/%Y",
    "de": "%d.%m.%Y",
    "fr": "%d/%m/%Y",
    "es": "%d/%m/%Y",
    "it": "%d/%m/%Y",
    "pt": "%d/%m/%Y",
    "ru": "%d.%m.%Y",
    "pl": "%d.%m.%Y",
    "uk": "%d.%m.%Y",
    "nl": "%d-%m-%Y",
    "ja": "%Y/%m/%d",
    "zh": "%Y/%m/%d",
    "ko": "%Y-%m-%d",
}


def format_date(dt: datetime, locale: str | None = None, format_pattern: str | None = None) -> str:
    """Format a datetime according to locale-specific conventions."""
    if locale:
        locale = locale.strip()
    lang = (locale or "").split("-")[0].split("_")[0].lower()
    if not lang:
        lang = "en"

    if not format_pattern:
        full_loc = (locale or "").lower().replace("_", "-")
        format_pattern = DATE_FORMATS.get(full_loc) or DATE_FORMATS.get(lang) or "%Y-%m-%d"

    months_long = {
        "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
        "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
        "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
        "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
        "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
        "pl": ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"],
    }

    months_short = {
        "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "de": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
        "es": ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sept.", "oct.", "nov.", "dic."],
        "ru": ["янв.", "февр.", "мар.", "апр.", "мая", "июн.", "июл.", "авг.", "сент.", "окт.", "нояб.", "дек."],
        "pt": ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."],
        "pl": ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"],
    }

    days_long = {
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "ru": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
        "pt": ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"],
        "pl": ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"],
    }

    days_short = {
        "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "de": ["Mon", "Die", "Mit", "Don", "Fre", "Sam", "Son"],
        "fr": ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."],
        "es": ["lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom."],
        "ru": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
        "pt": ["seg.", "ter.", "qua.", "qui.", "sex.", "sáb.", "dom."],
        "pl": ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "ned."],
    }

    weekday_idx = dt.weekday()
    month_idx = dt.month - 1

    l_month = months_long.get(lang, months_long["en"])[month_idx]
    s_month = months_short.get(lang, months_short["en"])[month_idx]
    l_day = days_long.get(lang, days_long["en"])[weekday_idx]
    s_day = days_short.get(lang, days_short["en"])[weekday_idx]

    temp_pattern = format_pattern
    replacements = []

    if "%B" in temp_pattern:
        temp_pattern = temp_pattern.replace("%B", "___LONG_MONTH___")
        replacements.append(("___LONG_MONTH___", l_month))
    if "%b" in temp_pattern:
        temp_pattern = temp_pattern.replace("%b", "___SHORT_MONTH___")
        replacements.append(("___SHORT_MONTH___", s_month))
    if "%A" in temp_pattern:
        temp_pattern = temp_pattern.replace("%A", "___LONG_DAY___")
        replacements.append(("___LONG_DAY___", l_day))
    if "%a" in temp_pattern:
        temp_pattern = temp_pattern.replace("%a", "___SHORT_DAY___")
        replacements.append(("___SHORT_DAY___", s_day))

    res = dt.strftime(temp_pattern)
    for token, value in replacements:
        res = res.replace(token, value)

    return res
