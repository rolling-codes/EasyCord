from easycord.bot import Bot
from easycord.i18n import LocalizationManager


def test_bot_creates_localization_with_auto_translator_only():
    translator = lambda text, _source, target: f"{text}::{target}"
    bot = Bot(auto_translator=translator)
    assert isinstance(bot.localization, LocalizationManager)


def test_bot_keeps_explicit_localization_over_auto_creation():
    manager = LocalizationManager(default_locale="en-US")
    bot = Bot(
        localization=manager,
        translations={"en-US": {"hello": "Hello"}},
        auto_translator=lambda text, _source, target: f"{text}::{target}",
    )
    assert bot.localization is manager
