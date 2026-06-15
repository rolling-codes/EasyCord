# EasyCord v5.47.0 Release Notes

## SecurityLabPlugin — Educational Security Demonstrations

A new opt-in plugin demonstrating real attack vectors against Discord bots and their defenses. Each command shows an attack in action, explains why it works, and provides code-based fixes.

### Available Labs (Admin-Only Commands)

**`/lab_stored_injection`** — Demonstrates stored mention injection attacks where `@everyone` and `@here` embedded in user-supplied text fire when replayed.

```python
from easycord import Bot
from easycord.plugins import SecurityLabPlugin

bot = Bot()
bot.add_plugin(SecurityLabPlugin())

# Admin runs the demo
ctx = await invoke(bot, "lab_stored_injection", payload="@everyone attack")
# Embed shows: "Result: @everyone mention FIRED"
# Fix: escape_mentions(text) to prevent pings
```

**`/lab_input_overflow`** — Shows that most EasyCord plugins accept unbounded user input (6000+ chars) with no truncation.

**`/lab_redos`** — Tests regex patterns for catastrophic backtracking. Pattern like `(a+)+$` hangs on non-matching input.

```python
# Admin tests a dangerous pattern
ctx = await invoke(bot, "lab_redos", pattern="(a+)+$")
# Embed shows: "🔴 HUNG (regex timeout)"
# Fix: safe_regex(pattern, text, timeout_ms=100)
```

**`/lab_prompt_injection`** — Echoes text as if an LLM response, showing how "Ignore previous instructions" payloads slip through raw forwarding to AI.

**`/lab_phantom_permission`** — Demonstrates silent lockout: typos in permission names (e.g., `kick_member` vs `kick_members`) block commands silently.

**`/lab_flood_check`** — Shows that without `SecurityManager`, all 20 rapid-fire calls succeed (no rate limit by default).

**`/lab_report`** — Summary of all 6 vectors with severity ratings.

### New Security Utilities (`easycord.security`)

- `escape_mentions(text)` — Replace `@everyone` / `@here` with spaced variants
- `truncate(text, max_len)` — Hard-cap text with ellipsis
- `safe_regex(pattern, text, timeout_ms)` — Regex match with timeout protection against ReDoS
- `strip_injection_prefixes(text)` — Remove common prompt-injection openers

### Bug Fixes

- `TagsPlugin.__init__` now calls `super().__init__()`
- `WordFilterPlugin` bare `except` clauses now have explanatory comments

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.47.0/easycord-5.47.0-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.47.0/easycord-5.47.0.tar.gz"
```
