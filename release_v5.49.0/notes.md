# EasyCord v5.49.0 Release Notes

Minor feature release — `/translate` slash command, Google Translate wired into the localization core, and automatic localized command names.

---

## Added

### TranslatePlugin — `/translate` slash command

```python
from easycord.plugins import TranslatePlugin
bot.add_plugin(TranslatePlugin())
```

Members type `/translate`, enter the text to translate, and a `"source to target"` language pair:

```
/translate text: Bonjour tout le monde  languages: French to English
→  Hello everyone

/translate text: Hello  languages: auto to Japanese
→  こんにちは

/translate text: Guten Morgen  languages:
→  (translated into the user's Discord locale automatically)
```

Requires `deep-translator`:
```bash
pip install "easycord[translate]"
```

---

### Google Translate → LocalizationManager

```python
from easycord import LocalizationManager
from easycord.helpers.google_translate import make_google_auto_translator

localization = LocalizationManager(
    auto_translator=make_google_auto_translator(),
    translations={"en-US": {"greeting": "Hello!", "farewell": "Goodbye!"}},
)
# French user: ctx.t("greeting") → "Bonjour!" (auto-translated, cached)
# Japanese user: ctx.t("farewell") → "さようなら" (auto-translated, cached)
```

---

### Localized command names

After installing the translator and syncing, Discord shows each user commands in their own language:

```python
await bot.use_google_translate()   # installs GoogleTranslateTranslator on tree
await bot.sync_commands()          # Discord fetches localized names for all locales
```

French users see `/traduire`, German users see `/übersetzen`, Japanese users see `/翻訳する` — all routing to the same `/translate` handler. The interaction payload always carries the canonical English name, so no bot-side routing changes are needed.

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.49.0/easycord-5.49.0-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.49.0/easycord-5.49.0.tar.gz"
```
