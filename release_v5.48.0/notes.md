# EasyCord v5.48.0 Release Notes

Feature release — PollsPlugin persistence, internal module splits, and several bug fixes.

---

## Added

### PollsPlugin persistence

Polls now survive bot restarts. Vote state and the remaining timer are stored per-guild
in `ServerConfigStore`; `on_ready` re-registers views and resumes countdowns automatically.

```python
from easycord.plugins.polls import PollsPlugin

bot.add_plugin(PollsPlugin())
# /poll created while the bot is running is now fully restart-safe —
# voters can still click buttons and the close timer fires at the correct time
# even if the bot went offline between creation and expiry.
```

### Internal module splits

Six focused sub-modules extracted from the monolithic `_bot_commands.py` and `i18n.py`
to make the codebase easier to navigate:

| Module | Purpose |
|---|---|
| `_command_callbacks.py` | `build_slash_callback` / `build_context_menu_callback` |
| `_command_registration.py` | `register_slash`, `register_context_menu`, choice/autocomplete injection |
| `_plugin_scanner.py` | auto-wires `@slash`/`@on` decorated plugin methods |
| `_i18n_locale.py` | locale normalisation, OS-locale detection, BCP 47 validation, fallback chains |
| `_i18n_diagnostics.py` | `DiagnosticMode` enum and `LocalizationDiagnostics` |
| `_i18n_validation.py` | `TranslationValidationReport` for per-locale completeness auditing |

No public API changes — the splits are internal only.

---

## Fixed

- **Prompt injection** (`ai_moderator.py`): user-controlled `message.content` and
  `message.author.name` are now XML-delimited in the LLM prompt, preventing crafted
  messages from shifting model instructions.

- **12 Pyright type errors** (`ai_moderator.py`): unguarded `ctx.guild` access narrowed
  with `assert ctx.guild is not None` in guild-only handlers and
  `if ctx.guild is None: return False` in `_execute_action`.

- **Poll restore isolation** (`polls.py`): a single malformed poll entry no longer aborts
  restoration of all polls in a guild — each entry is wrapped in its own `try/except`.

- **Cooldown dict growth** (`_command_callbacks.py`): expired bucket keys are pruned after
  filtering, preventing unbounded accumulation for inactive users.

- **Pylance type errors** (`helpers/tools.py`): replaced `all()` truthiness guard with
  `isinstance` checks so Pylance narrows `name`/`description` to `str` and `safety` to
  `ToolSafety`.

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.48.0/easycord-5.48.0-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.48.0/easycord-5.48.0.tar.gz"
```
