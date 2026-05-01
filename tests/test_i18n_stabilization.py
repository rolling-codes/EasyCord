"""
Stabilization audit for localization infrastructure.

Tests for performance, safety, edge cases, and scalability.
Purpose: Verify Phase 1 foundation is ready for Phase 2 expansion.
"""
import pytest
import time
from unittest.mock import patch

from easycord.i18n import (
    LocalizationManager,
    DiagnosticMode,
    _normalize_locale,
    detect_os_locale,
)


# ─── Performance & Lookup Profiling ───────────────────────────────────────

class TestPerformanceProfiles:
    """Benchmark lookup costs under different conditions."""

    @pytest.fixture
    def i18n_with_catalogs(self):
        """Create manager with realistic catalog size."""
        catalogs = {
            "en-US": {f"key_{i}": f"English {i}" for i in range(1000)},
            "es-ES": {f"key_{i}": f"Español {i}" for i in range(1000)},
            "fr-FR": {f"key_{i}": f"Français {i}" for i in range(1000)},
            "de-DE": {f"key_{i}": f"Deutsch {i}" for i in range(1000)},
            "pt-BR": {f"key_{i}": f"Português {i}" for i in range(900)},  # Partial
        }
        return {
            "silent": LocalizationManager(
                default_locale="en-US",
                translations=catalogs,
                diagnostic_mode=DiagnosticMode.SILENT,
            ),
            "warn": LocalizationManager(
                default_locale="en-US",
                translations=catalogs,
                diagnostic_mode=DiagnosticMode.WARN,
            ),
        }

    def test_lookup_performance_cold_cache(self, i18n_with_catalogs):
        """Measure single lookup cost (cold)."""
        i18n = i18n_with_catalogs["silent"]
        start = time.perf_counter()
        for _ in range(100):
            i18n.get("key_500", locale="es-ES")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1  # 100 lookups should be < 100ms

    def test_lookup_performance_warm_cache(self, i18n_with_catalogs):
        """Measure repeated lookup cost (warm)."""
        i18n = i18n_with_catalogs["silent"]
        i18n.get("key_500", locale="es-ES")  # Warm up
        start = time.perf_counter()
        for _ in range(10000):
            i18n.get("key_500", locale="es-ES")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5  # 10k repeated lookups should be < 500ms

    def test_diagnostics_overhead_silent_vs_warn(self, i18n_with_catalogs):
        """Measure SILENT vs WARN mode overhead."""
        silent_i18n = i18n_with_catalogs["silent"]
        warn_i18n = i18n_with_catalogs["warn"]

        start_silent = time.perf_counter()
        for _ in range(1000):
            silent_i18n.get("key_500", locale="es-ES")
        silent_time = time.perf_counter() - start_silent

        start_warn = time.perf_counter()
        for _ in range(1000):
            warn_i18n.get("key_500", locale="es-ES")
        warn_time = time.perf_counter() - start_warn

        # WARN mode should have minimal overhead (same code path after dedup)
        assert warn_time < silent_time * 1.5  # Allow 50% overhead

    def test_missing_key_repeated_lookups(self, i18n_with_catalogs):
        """Measure repeated missing key lookups (deduplication working)."""
        warn_i18n = i18n_with_catalogs["warn"]
        start = time.perf_counter()
        for _ in range(1000):
            warn_i18n.get("missing_key", locale="es-ES")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2  # Deduplication should prevent repeated warnings


# ─── Fallback Chain Safety ────────────────────────────────────────────────

class TestFallbackChainSafety:
    """Verify fallback resolution doesn't have recursion or cycle risks."""

    def test_deep_fallback_chain(self):
        """Test resolution with deep locale hierarchy."""
        i18n = LocalizationManager(
            default_locale="en-US",
            translations={
                "en-US": {"hello": "Hello"},
                "en": {"hello": "Hello"},
            },
        )
        # Deep regional variant should still resolve safely
        result = i18n.get("hello", locale="en-GB-scotland-variant")
        assert result == "Hello"

    def test_resolve_chain_depth_limit(self):
        """Ensure resolve_chain doesn't produce unbounded output."""
        i18n = LocalizationManager(default_locale="en-US")
        # Pathological case: very long locale string
        chain = i18n.resolve_chain("a-b-c-d-e-f-g-h-i-j")
        # Should produce reasonable number of candidates (progressively shorter variants)
        # For 10-part locale: all subsets from full to single part = 10 + default = max ~15
        assert len(chain) <= 15
        assert len(chain) > 0

    def test_fallback_determinism(self):
        """Verify fallback order is deterministic."""
        i18n = LocalizationManager(
            default_locale="en-US",
            translations={
                "en-US": {"key": "English"},
                "en": {"key": "English"},
            },
        )
        results = [i18n.get("key", locale="en-GB") for _ in range(10)]
        assert all(r == "English" for r in results)
        assert len(set(results)) == 1  # All identical

    def test_no_infinite_fallback_loops(self):
        """Ensure malformed locale configs don't cause loops."""
        i18n = LocalizationManager(
            default_locale="en-US",
            translations={"en-US": {"key": "value"}},
        )
        # These should not hang or raise
        result1 = i18n.get("key", locale="invalid-locale-format")
        result2 = i18n.get("key", locale="")
        result3 = i18n.get("key", locale=None)
        assert result1 == "value"
        assert result2 == "value"
        assert result3 == "value"


# ─── Locale Normalization Hardening ──────────────────────────────────────

class TestLocaleNormalization:
    """Verify normalization is deterministic and handles edge cases."""

    def test_underscore_to_hyphen_conversion(self):
        """Standard conversion."""
        assert _normalize_locale("en_US") == "en-US"
        assert _normalize_locale("pt_BR") == "pt-BR"

    def test_mixed_separators(self):
        """Handle mixed/unusual separators."""
        assert _normalize_locale("en_US") == "en-US"
        assert _normalize_locale("en-US") == "en-US"
        assert _normalize_locale("en US") == "en US"  # Spaces not normalized

    def test_whitespace_handling(self):
        """Whitespace trimming."""
        assert _normalize_locale("  en-US  ") == "en-US"
        assert _normalize_locale("\ten-US\n") == "en-US"
        assert _normalize_locale("   ") is None

    def test_empty_and_none(self):
        """None and empty values."""
        assert _normalize_locale(None) is None
        assert _normalize_locale("") is None
        assert _normalize_locale("   ") is None

    def test_case_preservation(self):
        """Case is preserved (not normalized)."""
        assert _normalize_locale("EN-US") == "EN-US"
        assert _normalize_locale("en-us") == "en-us"
        assert _normalize_locale("En-Us") == "En-Us"

    def test_locale_with_script(self):
        """Handle locales with script codes."""
        assert _normalize_locale("zh_Hans_CN") == "zh-Hans-CN"
        assert _normalize_locale("zh-Hant-HK") == "zh-Hant-HK"

    def test_normalization_idempotent(self):
        """Applying normalization twice produces same result."""
        locales = ["en_US", "pt_BR", "zh_Hans_CN"]
        for loc in locales:
            first = _normalize_locale(loc)
            second = _normalize_locale(first)
            assert first == second


# ─── Validator Scalability ───────────────────────────────────────────────

class TestValidatorScalability:
    """Measure validator performance with large catalogs."""

    @pytest.fixture
    def large_catalog_manager(self):
        """Create manager with many locales and keys."""
        catalogs = {}
        base_keys = {f"key_{i}": f"English {i}" for i in range(1000)}

        catalogs["en-US"] = base_keys
        for locale_num in range(20):
            locale = f"locale-{locale_num}"
            # Each locale has ~90% of keys (10% gaps for testing)
            keys = {k: f"{locale} {v}" for k, v in base_keys.items()
                   if locale_num % 10 != hash(k) % 10}
            catalogs[locale] = keys

        return LocalizationManager(
            default_locale="en-US",
            translations=catalogs,
        )

    def test_validation_performance_scaling(self, large_catalog_manager):
        """Measure validator runtime."""
        start = time.perf_counter()
        report = large_catalog_manager.validate_completeness()
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0  # Should complete in < 1 second
        assert report.is_valid() is False  # Some missing keys
        assert len(report.results) == 21  # 21 locales

    def test_validation_report_generation(self, large_catalog_manager):
        """Measure report text generation."""
        report = large_catalog_manager.validate_completeness()

        start = time.perf_counter()
        text = report.report_text()
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1  # Should be very fast
        assert "Translation Validation Report" in text


# ─── Cache & Invalidation Semantics ──────────────────────────────────────

class TestCacheInvalidation:
    """Verify cache behavior and invalidation safety."""

    def test_system_locale_cached_on_init(self):
        """System locale is cached, not queried repeatedly."""
        call_count = 0

        def mock_getlocale():
            nonlocal call_count
            call_count += 1
            return ("en", "US")

        with patch("easycord.i18n.stdlib_locale.getdefaultlocale", side_effect=mock_getlocale):
            i18n = LocalizationManager(
                auto_detect_system_locale=True,
                translations={"en-US": {}},
            )
            assert call_count == 1

            # Accessing system locale multiple times doesn't call again
            _ = i18n._system_locale
            _ = i18n._system_locale
            assert call_count == 1

    def test_diagnostics_dedup_cache_independent(self):
        """Diagnostics cache is independent per manager instance."""
        i18n1 = LocalizationManager(
            default_locale="en-US",
            diagnostic_mode=DiagnosticMode.WARN,
            translations={"en-US": {}},
        )
        i18n2 = LocalizationManager(
            default_locale="en-US",
            diagnostic_mode=DiagnosticMode.WARN,
            translations={"en-US": {}},
        )

        i18n1.get("missing", locale="es-ES")
        i18n2.get("missing", locale="es-ES")

        assert i18n1.diagnostics._missing_count == 1
        assert i18n2.diagnostics._missing_count == 1

    def test_diagnostics_reset_clears_cache(self):
        """Diagnostics reset properly clears dedup cache."""
        i18n = LocalizationManager(
            default_locale="en-US",
            diagnostic_mode=DiagnosticMode.WARN,
            translations={"en-US": {}},
        )

        i18n.get("missing", locale="es-ES")
        assert i18n.diagnostics._missing_count == 1

        i18n.diagnostics.reset()
        assert i18n.diagnostics._missing_count == 0


# ─── Logging & Diagnostics Production Safety ────────────────────────────

class TestDiagnosticsProductionSafety:
    """Verify diagnostics are safe under production conditions."""

    def test_silent_mode_zero_overhead(self, caplog):
        """SILENT mode produces no logging overhead."""
        import logging
        caplog.set_level(logging.DEBUG)

        i18n = LocalizationManager(
            default_locale="en-US",
            diagnostic_mode=DiagnosticMode.SILENT,
            translations={"en-US": {}},
        )

        for _ in range(100):
            i18n.get("missing", locale="es-ES")

        # No warnings regardless of repeated misses
        assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 0

    def test_warn_mode_deduplication_prevents_spam(self, caplog):
        """WARN mode deduplicates to prevent log spam."""
        import logging
        with caplog.at_level(logging.WARNING, logger="easycord.i18n"):
            i18n = LocalizationManager(
                default_locale="en-US",
                diagnostic_mode=DiagnosticMode.WARN,
                translations={"en-US": {}},
            )

            # Repeated missing key lookups
            for _ in range(100):
                i18n.get("missing", locale="es-ES")

            # Should only log once due to deduplication
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) == 1

    def test_strict_mode_exception_on_first_miss(self):
        """STRICT mode raises immediately on first miss."""
        i18n = LocalizationManager(
            default_locale="en-US",
            diagnostic_mode=DiagnosticMode.STRICT,
            translations={"en-US": {}},
        )

        with pytest.raises(KeyError):
            i18n.get("missing", locale="es-ES")


# ─── Integration & Cross-Cutting Concerns ────────────────────────────────

class TestIntegrationStability:
    """Test interactions between Phase 1 features."""

    def test_auto_detect_with_diagnostics(self):
        """Auto-detection works with diagnostics enabled."""
        with patch("easycord.i18n.stdlib_locale.getdefaultlocale", return_value=("en", "US")):
            i18n = LocalizationManager(
                default_locale="en-US",
                auto_detect_system_locale=True,
                diagnostic_mode=DiagnosticMode.WARN,
                translations={"en-US": {"hello": "Hello"}},
            )

            locale = i18n.auto_detect_locale()
            assert locale == "en-US"

    def test_validator_with_partial_translations(self):
        """Validator handles partial translations correctly."""
        i18n = LocalizationManager(
            default_locale="en-US",
            translations={
                "en-US": {"a": "A", "b": "B", "c": "C"},
                "es-ES": {"a": "A", "b": "B"},  # Missing 'c'
            },
        )

        report = i18n.validate_completeness()
        assert report.results["es-ES"]["coverage"] == 2/3
        assert "c" in report.results["es-ES"]["missing_keys"]

    def test_diagnostics_with_validation(self):
        """Diagnostics and validation don't interfere."""
        i18n = LocalizationManager(
            default_locale="en-US",
            diagnostic_mode=DiagnosticMode.WARN,
            translations={
                "en-US": {"hello": "Hello"},
                "es-ES": {},  # Partial: empty
            },
        )

        i18n.get("missing", locale="es-ES")
        report = i18n.validate_completeness()

        assert i18n.diagnostics._missing_count == 1
        assert not report.is_valid()  # es-ES is missing "hello"
