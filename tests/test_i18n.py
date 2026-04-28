from easycord.i18n import LocalizationManager


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
