"""Diagnostic helpers for EasyCord localization."""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("easycord.i18n")


class DiagnosticMode(Enum):
    """Localization diagnostic modes."""

    SILENT = "silent"
    WARN = "warn"
    STRICT = "strict"


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

        fallback_msg = f" (fallback: {fallback_locale})" if fallback_locale else ""
        message = f"Missing key '{key}' in locale '{locale}'{fallback_msg}"

        if self.mode == DiagnosticMode.STRICT:
            self._missing_count += 1
            raise KeyError(message)
        if self.mode == DiagnosticMode.WARN:
            cache_key = (key, locale)
            if cache_key in self._seen_missing:
                return
            self._seen_missing.add(cache_key)
            self._missing_count += 1
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

        message = (
            f"Invalid placeholder in '{key}': template has '{placeholder}' "
            "but value not provided"
        )

        if self.mode == DiagnosticMode.STRICT:
            self._placeholder_count += 1
            raise KeyError(message)
        if self.mode == DiagnosticMode.WARN:
            cache_key = (key, placeholder)
            if cache_key in self._seen_placeholder:
                return
            self._seen_placeholder.add(cache_key)
            self._placeholder_count += 1
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
