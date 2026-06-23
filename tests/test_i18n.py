"""Tests for LocalizationManager, diagnostics, and validation."""
from __future__ import annotations

import pytest

from datetime import datetime
from easycord.i18n import (
    DiagnosticMode,
    LocalizationDiagnostics,
    LocalizationManager,
    TranslationValidationReport,
    _normalize_locale,
    format_number,
    format_date,
)


class TestNormalizeLocale:
    def test_none_returns_none(self) -> None:
        assert _normalize_locale(None) is None

    def test_underscore_to_dash(self) -> None:
        assert _normalize_locale("en_US") == "en-US"

    def test_strips_whitespace(self) -> None:
        assert _normalize_locale("  en-US  ") == "en-US"

    def test_empty_string_returns_none(self) -> None:
        assert _normalize_locale("") is None

    def test_object_with_value(self) -> None:
        class FakeLocale:
            value = "pt_BR"
        assert _normalize_locale(FakeLocale()) == "pt-BR"


class TestLocalizationDiagnostics:
    def test_silent_mode_no_raise(self) -> None:
        d = LocalizationDiagnostics(DiagnosticMode.SILENT)
        d.report_missing_key("k", "en-US")  # no raise

    def test_strict_mode_raises_on_missing(self) -> None:
        d = LocalizationDiagnostics(DiagnosticMode.STRICT)
        with pytest.raises(KeyError):
            d.report_missing_key("k", "en-US")

    def test_warn_mode_deduplicates(self) -> None:
        d = LocalizationDiagnostics(DiagnosticMode.WARN)
        d.report_missing_key("k", "en-US")
        d.report_missing_key("k", "en-US")
        assert d.missing_keys_summary()["unique_missing"] == 1
        assert d.missing_keys_summary()["total_missing"] == 1

    def test_strict_mode_raises_on_invalid_placeholder(self) -> None:
        d = LocalizationDiagnostics(DiagnosticMode.STRICT)
        with pytest.raises(KeyError):
            d.report_invalid_placeholder("k", "Hello {name}", "name")

    def test_silent_placeholder_no_raise(self) -> None:
        d = LocalizationDiagnostics(DiagnosticMode.SILENT)
        d.report_invalid_placeholder("k", "Hi {x}", "x")

    def test_warn_placeholder_deduplicates(self) -> None:
        d = LocalizationDiagnostics(DiagnosticMode.WARN)
        d.report_invalid_placeholder("k", "Hi {x}", "x")
        d.report_invalid_placeholder("k", "Hi {x}", "x")
        assert d.missing_keys_summary()["unique_placeholders"] == 1

    def test_reset(self) -> None:
        d = LocalizationDiagnostics(DiagnosticMode.WARN)
        d.report_missing_key("k", "en-US")
        d.reset()
        assert d.missing_keys_summary()["total_missing"] == 0
        assert d.missing_keys_summary()["unique_missing"] == 0


class TestLocalizationManager:
    def test_register_and_format(self) -> None:
        m = LocalizationManager(translations={"en-US": {"hello": "Hello {name}!"}})
        assert m.format("hello", name="Tom") == "Hello Tom!"

    def test_fallback_to_default_locale(self) -> None:
        m = LocalizationManager(
            default_locale="en-US",
            translations={"en-US": {"key": "Value"}},
        )
        assert m.format("key", locale="fr-FR") == "Value"

    def test_missing_key_returns_key_itself(self) -> None:
        m = LocalizationManager()
        assert m.format("missing.key") == "missing.key"

    def test_locales_returns_sorted_list(self) -> None:
        m = LocalizationManager(translations={
            "fr-FR": {"a": "b"},
            "en-US": {"a": "c"},
        })
        assert m.locales() == ["en-US", "fr-FR"]

    def test_register_merges_catalogs(self) -> None:
        m = LocalizationManager(translations={"en-US": {"a": "A"}})
        m.register("en-US", {"b": "B"})
        assert m.format("a") == "A"
        assert m.format("b") == "B"

    def test_register_empty_locale_raises(self) -> None:
        m = LocalizationManager()
        with pytest.raises(ValueError):
            m.register("", {"k": "v"})

    def test_strict_mode_raises_on_missing_key(self) -> None:
        m = LocalizationManager(
            translations={"en-US": {"hello": "Hello {name}"}},
            diagnostic_mode=DiagnosticMode.STRICT,
        )
        with pytest.raises(KeyError):
            m.format("hello")

    def test_strict_mode_raises_on_missing_with_locale(self) -> None:
        m = LocalizationManager(
            translations={"en-US": {}},
            diagnostic_mode=DiagnosticMode.STRICT,
        )
        with pytest.raises(KeyError):
            m.format("nonexistent", locale="fr-FR")

    def test_format_with_locale_kwarg(self) -> None:
        m = LocalizationManager(translations={
            "en-US": {"hi": "Hello"},
            "fr-FR": {"hi": "Bonjour"},
        })
        assert m.format("hi", locale="fr-FR") == "Bonjour"
        assert m.format("hi", locale="en-US") == "Hello"

    def test_metrics_not_tracked_by_default(self) -> None:
        m = LocalizationManager()
        assert m.get_metrics() == {}

    def test_metrics_tracked_when_enabled(self) -> None:
        m = LocalizationManager(
            translations={"en-US": {"k": "v"}},
            track_metrics=True,
        )
        m.format("k")
        metrics = m.get_metrics()
        assert "cache_hits" in metrics


class TestTranslationValidationReport:
    def test_is_valid_when_no_missing(self) -> None:
        r = TranslationValidationReport("en-US")
        r.add_locale("fr-FR", missing_keys=[], orphaned_keys=[], coverage=1.0)
        assert r.is_valid()

    def test_is_invalid_when_missing_keys(self) -> None:
        r = TranslationValidationReport("en-US")
        r.add_locale("fr-FR", missing_keys=["a"], orphaned_keys=[], coverage=0.5)
        assert not r.is_valid()

    def test_summary(self) -> None:
        r = TranslationValidationReport("en-US")
        r.add_locale("fr-FR", missing_keys=[], orphaned_keys=[], coverage=1.0)
        s = r.summary()
        assert s["total_locales"] == 1
        assert s["fully_translated"] == 1

    def test_report_text_contains_locale(self) -> None:
        r = TranslationValidationReport("en-US")
        r.add_locale("fr-FR", missing_keys=["a", "b"], orphaned_keys=[], coverage=0.5)
        text = r.report_text()
        assert "fr-FR" in text
        assert "missing" in text.lower()


class TestLocalizationManagerPlurals:
    def test_english_plurals(self) -> None:
        m = LocalizationManager(
            translations={
                "en-US": {
                    "items_one": "{count} item",
                    "items_other": "{count} items",
                    "simple": "Simple message",
                }
            }
        )
        assert m.format("items", count=1) == "1 item"
        assert m.format("items", count=5) == "5 items"
        # Fallback to base key
        assert m.format("simple", count=5) == "Simple message"

    def test_russian_plurals(self) -> None:
        m = LocalizationManager(
            translations={
                "ru": {
                    "items_one": "{count} товар",
                    "items_few": "{count} товара",
                    "items_many": "{count} товаров",
                    "items_other": "{count} товара (другое)",
                }
            }
        )
        assert m.format("items", locale="ru", count=1) == "1 товар"
        assert m.format("items", locale="ru", count=2) == "2 товара"
        assert m.format("items", locale="ru", count=5) == "5 товаров"
        assert m.format("items", locale="ru", count=11) == "11 товаров"
        assert m.format("items", locale="ru", count=21) == "21 товар"
        assert m.format("items", locale="ru", count=22) == "22 товара"

    def test_french_plurals(self) -> None:
        m = LocalizationManager(
            translations={
                "fr": {
                    "items_one": "{count} article",
                    "items_other": "{count} articles",
                }
            }
        )
        assert m.format("items", locale="fr", count=0) == "0 article"
        assert m.format("items", locale="fr", count=1) == "1 article"
        assert m.format("items", locale="fr", count=2) == "2 articles"

    def test_arabic_plurals(self) -> None:
        m = LocalizationManager(
            translations={
                "ar": {
                    "items_zero": "صفر",
                    "items_one": "واحد",
                    "items_two": "اثنان",
                    "items_few": "{count} قليل",
                    "items_many": "{count} كثير",
                    "items_other": "{count} آخر",
                }
            }
        )
        assert m.format("items", locale="ar", count=0) == "صفر"
        assert m.format("items", locale="ar", count=1) == "واحد"
        assert m.format("items", locale="ar", count=2) == "اثنان"
        assert m.format("items", locale="ar", count=3) == "3 قليل"
        assert m.format("items", locale="ar", count=11) == "11 كثير"
        assert m.format("items", locale="ar", count=100) == "100 آخر"

    def test_custom_plural_rule_evaluator(self) -> None:
        def custom_rule(locale: str, count: float | int) -> str:
            if count == 42:
                return "answer"
            return "other"

        m = LocalizationManager(
            plural_rule_evaluator=custom_rule,
            translations={
                "en-US": {
                    "msg_answer": "The Answer!",
                    "msg_other": "Normal message",
                }
            }
        )
        assert m.format("msg", count=42) == "The Answer!"
        assert m.format("msg", count=10) == "Normal message"


class TestFormatNumber:
    def test_english_formatting(self) -> None:
        assert format_number(1234567.89, "en") == "1,234,567.89"
        assert format_number(1000, "en") == "1,000"

    def test_german_formatting(self) -> None:
        assert format_number(1234567.89, "de") == "1.234.567,89"
        assert format_number(1000, "de") == "1.000"

    def test_french_formatting(self) -> None:
        assert format_number(1234567.89, "fr") == "1\xa0234\xa0567,89"

    def test_negative_numbers(self) -> None:
        assert format_number(-1234567.89, "de") == "-1.234.567,89"
        assert format_number(-5, "en") == "-5"


class TestFormatDate:
    def test_default_date_formats(self) -> None:
        dt = datetime(2026, 6, 22, 12, 34)
        assert format_date(dt, "en-US") == "06/22/2026"
        assert format_date(dt, "de-DE") == "22.06.2026"
        assert format_date(dt, "fr-FR") == "22/06/2026"

    def test_custom_pattern(self) -> None:
        dt = datetime(2026, 6, 22, 12, 34)
        assert format_date(dt, "en", "%Y-%m-%d %H:%M") == "2026-06-22 12:34"

    def test_localized_names(self) -> None:
        dt = datetime(2026, 6, 22)  # Monday, June 22
        # French
        assert format_date(dt, "fr", "%A, %d %B") == "lundi, 22 juin"
        assert format_date(dt, "fr", "%a, %d %b") == "lun., 22 juin"
        # German
        assert format_date(dt, "de", "%A, %d. %B") == "Montag, 22. Juni"
