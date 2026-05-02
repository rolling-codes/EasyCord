"""
Locale resolution tracing tests.

Verifies debug-only telemetry for locale resolution paths.
Essential for Phase 2 Discord integration debugging.
"""
import logging
import pytest

from easycord.i18n import LocalizationManager, DiagnosticMode


class TestLocaleResolutionTracing:
    """Test locale resolution tracing (debug telemetry)."""

    @pytest.fixture
    def i18n_with_tracing(self):
        """Manager with multiple locales for tracing tests."""
        return LocalizationManager(
            default_locale="en-US",
            translations={
                "en-US": {"hello": "Hello", "greeting": "Welcome"},
                "pt-BR": {"hello": "Olá"},
                "pt": {"hello": "Olá"},
                "es-ES": {"greeting": "Bienvenido"},
            },
        )

    def test_trace_cache_hit(self, i18n_with_tracing, caplog):
        """Trace shows cache hit when key found in preferred locale."""
        with caplog.at_level(logging.DEBUG, logger="easycord.i18n.trace"):
            result = i18n_with_tracing.get("hello", locale="pt-BR")

        assert result == "Olá"
        trace_records = [r for r in caplog.records if r.name == "easycord.i18n.trace"]
        assert len(trace_records) > 0
        assert "pt-BR" in trace_records[0].message or "pt" in trace_records[0].message

    def test_trace_fallback_path(self, i18n_with_tracing, caplog):
        """Trace shows fallback when key missing in preferred locale."""
        with caplog.at_level(logging.DEBUG, logger="easycord.i18n.trace"):
            result = i18n_with_tracing.get("greeting", locale="pt-BR")

        assert result == "Welcome"  # Falls back to en-US
        trace_records = [r for r in caplog.records if r.name == "easycord.i18n.trace"]
        assert len(trace_records) > 0
        # Trace should indicate fallback
        assert "cache_hit=False" in trace_records[0].message

    def test_trace_missing_key(self, i18n_with_tracing, caplog):
        """Trace shows missing key resolution path."""
        with caplog.at_level(logging.DEBUG, logger="easycord.i18n.trace"):
            result = i18n_with_tracing.get("unknown", locale="es-ES")

        assert result == "unknown"  # Returns key itself
        trace_records = [r for r in caplog.records if r.name == "easycord.i18n.trace"]
        assert len(trace_records) > 0
        assert "found_in=None" in trace_records[0].message

    def test_trace_includes_raw_and_normalized(self, i18n_with_tracing, caplog):
        """Trace includes both raw and normalized locale."""
        with caplog.at_level(logging.DEBUG, logger="easycord.i18n.trace"):
            i18n_with_tracing.get("hello", locale="pt_BR")  # Underscore (raw)

        trace_records = [r for r in caplog.records if r.name == "easycord.i18n.trace"]
        assert len(trace_records) > 0
        message = trace_records[0].message
        # Should show both raw and normalized
        assert "pt_BR" in message  # raw_locale
        assert "normalized" in message

    def test_trace_with_guild_locale(self, i18n_with_tracing, caplog):
        """Trace includes guild locale in resolution path."""
        with caplog.at_level(logging.DEBUG, logger="easycord.i18n.trace"):
            result = i18n_with_tracing.get("hello", locale="es-ES", guild_locale="pt-BR")

        assert result == "Olá"  # Guild locale wins
        trace_records = [r for r in caplog.records if r.name == "easycord.i18n.trace"]
        assert len(trace_records) > 0
        assert "guild=" in trace_records[0].message

    def test_trace_disabled_by_default(self, i18n_with_tracing, caplog):
        """Trace is disabled by default (no log records emitted)."""
        # Don't set logging level - should be disabled
        caplog.clear()
        i18n_with_tracing.get("hello", locale="pt-BR")

        trace_records = [r for r in caplog.records if r.name == "easycord.i18n.trace"]
        # Should be empty because logger is disabled by default
        assert len(trace_records) == 0

    def test_trace_fallback_chain_included(self, i18n_with_tracing, caplog):
        """Trace includes the fallback chain examined."""
        with caplog.at_level(logging.DEBUG, logger="easycord.i18n.trace"):
            i18n_with_tracing.get("greeting", locale="pt-BR")

        trace_records = [r for r in caplog.records if r.name == "easycord.i18n.trace"]
        assert len(trace_records) > 0
        message = trace_records[0].message
        assert "chain=" in message  # Fallback chain included


class TestLocaleResolutionMetrics:
    """Test locale resolution metrics tracking."""

    @pytest.fixture
    def i18n_with_metrics(self):
        """Manager with metrics enabled."""
        return LocalizationManager(
            default_locale="en-US",
            track_metrics=True,
            translations={
                "en-US": {"hello": "Hello", "greeting": "Welcome"},
                "pt-BR": {"hello": "Olá"},
                "es-ES": {"greeting": "Bienvenido"},
            },
        )

    def test_metrics_disabled_by_default(self):
        """Metrics tracking is disabled by default."""
        i18n = LocalizationManager(
            default_locale="en-US",
            translations={"en-US": {"hello": "Hello"}},
        )
        assert i18n.get_metrics() == {}

    def test_metrics_cache_hit(self, i18n_with_metrics):
        """Metrics tracks cache hits."""
        i18n_with_metrics.get("hello", locale="pt-BR")
        metrics = i18n_with_metrics.get_metrics()

        assert metrics["cache_hits"] == 1
        assert metrics["cache_misses"] == 0
        assert "pt-BR" in metrics["locale_frequency"]
        assert metrics["locale_frequency"]["pt-BR"] == 1

    def test_metrics_cache_miss_and_fallback(self, i18n_with_metrics):
        """Metrics tracks cache misses and fallback usage."""
        i18n_with_metrics.get("greeting", locale="pt-BR")  # Not in pt-BR
        metrics = i18n_with_metrics.get_metrics()

        assert metrics["cache_misses"] == 1
        assert metrics["fallback_uses"] == 1
        assert metrics["locale_frequency"]["en-US"] == 1

    def test_metrics_missing_key(self, i18n_with_metrics):
        """Metrics tracks missing keys."""
        i18n_with_metrics.get("unknown", locale="es-ES")
        metrics = i18n_with_metrics.get_metrics()

        assert metrics["missing_keys"] == 1

    def test_metrics_accumulate(self, i18n_with_metrics):
        """Metrics accumulate across multiple lookups."""
        i18n_with_metrics.get("hello", locale="pt-BR")  # Cache hit
        i18n_with_metrics.get("hello", locale="pt-BR")  # Cache hit again
        i18n_with_metrics.get("greeting", locale="pt-BR")  # Cache miss + fallback
        i18n_with_metrics.get("unknown", locale="es-ES")  # Cache miss + missing key

        metrics = i18n_with_metrics.get_metrics()
        assert metrics["cache_hits"] == 2
        assert metrics["cache_misses"] == 2  # Two misses (greeting, unknown)
        assert metrics["fallback_uses"] == 1  # Only greeting had fallback (unknown not found)
        assert metrics["missing_keys"] == 1  # Only unknown missing

    def test_metrics_locale_frequency(self, i18n_with_metrics):
        """Metrics tracks locale usage frequency."""
        i18n_with_metrics.get("hello", locale="pt-BR")
        i18n_with_metrics.get("hello", locale="pt-BR")
        i18n_with_metrics.get("hello", locale="en-US")

        metrics = i18n_with_metrics.get_metrics()
        assert metrics["locale_frequency"]["pt-BR"] == 2
        assert metrics["locale_frequency"]["en-US"] == 1

    def test_metrics_reset(self, i18n_with_metrics):
        """Metrics can be reset."""
        i18n_with_metrics.get("hello", locale="pt-BR")
        assert i18n_with_metrics.get_metrics()["cache_hits"] == 1

        i18n_with_metrics.reset_metrics()
        metrics = i18n_with_metrics.get_metrics()
        assert metrics["cache_hits"] == 0
        assert metrics["locale_frequency"] == {}
