import pytest
from unittest.mock import patch

from easycord.i18n import LocalizationManager, _normalize_locale, detect_os_locale


def test_register_and_get_translation():
    i18n = LocalizationManager()
    i18n.register("es-ES", {"errors.guild_only": "Solo servidores"})

    assert i18n.get("errors.guild_only", locale="es-ES") == "Solo servidores"


def test_fallback_to_language_and_default_locale():
    i18n = LocalizationManager(default_locale="en-US")
    i18n.register("pt", {"hello": "olá"})

    assert i18n.get("hello", locale="pt-BR") == "olá"


def test_format_interpolates_values():
    i18n = LocalizationManager()
    i18n.register("en-US", {"errors.cooldown": "Wait {seconds:.1f}s"})

    assert i18n.format("errors.cooldown", locale="en-US", seconds=2.5) == "Wait 2.5s"


def test_missing_key_falls_back_to_default_text():
    i18n = LocalizationManager()

    assert i18n.get("missing.key", default="fallback") == "fallback"


def test_auto_translator_translates_and_caches_missing_locale():
    calls: list[tuple[str, str, str]] = []

    def fake_translator(text: str, source_locale: str, target_locale: str) -> str:
        calls.append((text, source_locale, target_locale))
        return f"{text} ({target_locale})"

    i18n = LocalizationManager(
        default_locale="en-US",
        auto_translator=fake_translator,
        translations={"en-US": {"hello": "Hello"}},
    )

    assert i18n.get("hello", locale="fr-FR") == "Hello (fr-FR)"
    assert i18n.get("hello", locale="fr-FR") == "Hello (fr-FR)"
    assert calls == [("Hello", "en-US", "fr-FR")]


def test_auto_translator_uses_default_text_when_key_missing_everywhere():
    i18n = LocalizationManager(
        default_locale="en-US",
        auto_translator=lambda text, _source, target: f"{text}->{target}",
    )

    assert i18n.get("unknown.key", locale="es-ES", default="Welcome") == "Welcome->es-ES"


# Locale auto-detection tests

def test_normalize_locale_converts_underscore_to_hyphen():
    assert _normalize_locale("en_US") == "en-US"
    assert _normalize_locale("pt_BR") == "pt-BR"


def test_normalize_locale_handles_none():
    assert _normalize_locale(None) is None
    assert _normalize_locale("") is None
    assert _normalize_locale("   ") is None


def test_detect_os_locale_returns_none_on_error():
    with patch("easycord.i18n.stdlib_locale.getdefaultlocale", side_effect=ValueError):
        assert detect_os_locale() is None


def test_detect_os_locale_formats_correctly():
    with patch("easycord.i18n.stdlib_locale.getdefaultlocale", return_value=("en", "US")):
        assert detect_os_locale() == "en-US"


def test_detect_os_locale_with_language_only():
    with patch("easycord.i18n.stdlib_locale.getdefaultlocale", return_value=("fr", None)):
        assert detect_os_locale() == "fr"


def test_auto_detect_locale_priority_user_over_guild():
    i18n = LocalizationManager(
        default_locale="en-US",
        translations={"en-US": {}, "es-ES": {}, "fr-FR": {}},
    )
    locale = i18n.auto_detect_locale(user_locale="es-ES", guild_locale="fr-FR")
    assert locale == "es-ES"


def test_auto_detect_locale_priority_guild_over_system():
    with patch("easycord.i18n.stdlib_locale.getdefaultlocale", return_value=("en", "US")):
        i18n = LocalizationManager(
            default_locale="en-US",
            auto_detect_system_locale=True,
            translations={"en-US": {}, "fr-FR": {}},
        )
        locale = i18n.auto_detect_locale(guild_locale="fr-FR")
        assert locale == "fr-FR"


def test_auto_detect_locale_priority_system_over_default():
    with patch("easycord.i18n.stdlib_locale.getdefaultlocale", return_value=("fr", "FR")):
        i18n = LocalizationManager(
            default_locale="en-US",
            auto_detect_system_locale=True,
            translations={"en-US": {}, "fr-FR": {}},
        )
        locale = i18n.auto_detect_locale()
        assert locale == "fr-FR"


def test_auto_detect_locale_falls_back_to_default():
    i18n = LocalizationManager(
        default_locale="en-US",
        translations={"en-US": {}},
    )
    locale = i18n.auto_detect_locale()
    assert locale == "en-US"


def test_auto_detect_locale_regional_fallback_pt_BR_to_pt():
    i18n = LocalizationManager(
        default_locale="en-US",
        translations={"en-US": {}, "pt": {}},
    )
    locale = i18n.auto_detect_locale(user_locale="pt-BR")
    assert locale == "pt"


def test_auto_detect_locale_unregistered_locale_skipped():
    i18n = LocalizationManager(
        default_locale="en-US",
        translations={"en-US": {}, "es-ES": {}},
    )
    locale = i18n.auto_detect_locale(user_locale="fr-FR")
    assert locale == "en-US"


def test_auto_detect_locale_invalid_locale_silent_when_disabled(caplog):
    i18n = LocalizationManager(
        default_locale="en-US",
        warn_invalid_locale=False,
        translations={"en-US": {}},
    )
    with patch("easycord.i18n.logger") as mock_logger:
        locale = i18n.auto_detect_locale(user_locale="invalid")
        assert locale == "en-US"
        mock_logger.warning.assert_not_called()


def test_auto_detect_system_locale_initialized_on_startup():
    with patch("easycord.i18n.stdlib_locale.getdefaultlocale", return_value=("en", "US")):
        i18n = LocalizationManager(
            default_locale="en-US",
            auto_detect_system_locale=True,
            translations={"en-US": {}},
        )
        assert i18n._system_locale == "en-US"


def test_auto_detect_system_locale_none_when_disabled():
    with patch("easycord.i18n.stdlib_locale.getdefaultlocale", return_value=("en", "US")):
        i18n = LocalizationManager(
            default_locale="en-US",
            auto_detect_system_locale=False,
            translations={"en-US": {}},
        )
        assert i18n._system_locale is None
