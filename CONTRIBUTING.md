# Contributing to EasyCord

Python 3.10+. MIT license. Contributions welcome.

## Development setup

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e ".[dev]"
easycord doctor
```

`pip install -e ".[dev]"` installs pytest, pytest-asyncio, build, twine, and deep-translator alongside the package in editable mode. `easycord doctor` confirms your local setup is wired correctly before you write anything.

## Running tests

```bash
pytest tests/                                  # full suite
pytest tests/test_middleware.py -v             # single file
pytest tests/test_middleware.py::test_name -v  # single test
```

`asyncio_mode = "auto"` is set in `pyproject.toml` — no manual event loop setup needed in test files.

Coverage must not drop below 80%. New code without tests will not be merged.

## Code style

- Python 3.10+ type hints on all public functions and methods
- Immutable patterns — return new objects, never mutate in place
- Functions under 50 lines; files under 800 lines
- No hardcoded strings in plugins — use `ctx.t(...)` and locale files
- No `# type: ignore` without a specific error code (e.g. `# type: ignore[assignment]`)
- No `print()` or bare `except:` blocks in production code

### Key invariants (easy to get wrong)

- `ctx.user` / `ctx.member` — correct. `ctx.author` — does not exist.
- `ctx.is_admin` is a property, not a method. Never call `ctx.is_admin()`.
- `ToolLimiter` methods (`check_limit`, `reset_user`, `reset_tool`) are async — always `await` them.
- `@ai_tool` requires an explicit `ToolSafety` annotation to register.
- Before calling `.send()` on a channel from `ctx` or Discord, narrow the type first:
  ```python
  from easycord.helpers.tools import SENDABLE_CHANNEL_TYPES
  if isinstance(channel, SENDABLE_CHANNEL_TYPES):
      await channel.send(...)
  ```

## Writing tests

Construct plugins with `__new__` and set `_bot` directly — do not assign to the `bot` property:

```python
plugin = MyPlugin.__new__(MyPlugin)
plugin._bot = bot
Plugin.__init__(plugin)
```

For commands, prefer `invoke` over constructing `FakeContext` by hand:

```python
from easycord.testing import invoke

ctx = await invoke(bot, "ping")
ctx.assert_content("Pong!")
```

When you need locale, roles, or DM context, use `FakeContextBuilder`:

```python
from easycord.testing import FakeContextBuilder

ctx = (
    FakeContextBuilder()
    .with_user(42, name="alice")
    .in_guild(100)
    .as_admin()
    .with_roles(999)
    .build()
)
```

## Pull request process

1. Branch from `main`. Naming: `feat/description`, `fix/description`, `docs/description`.
2. Write tests first. Coverage must not drop.
3. Run `pytest tests/` — all tests must pass.
4. Run `python scripts/check_release_metadata.py` — catches version drift across `pyproject.toml`, `__init__.py`, and `CHANGELOG.md`.
5. PR title follows conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, etc.
6. PR body: what changed, why, and a short test plan.
7. One reviewer required before merge.

## Commit messages

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

## Issue labels

| Label | Meaning |
|-------|---------|
| `bug` | Confirmed broken behavior |
| `enhancement` | New feature or improvement |
| `docs` | Documentation only |
| `good first issue` | Well-scoped for new contributors |
| `breaking` | Changes the public API |

## Plugin contributions

If your PR adds a plugin or changes plugin behavior:

- Update `docs/plugin-authoring.md` if the authoring surface changed
- Add an example under `examples/` if the feature is non-obvious
- Per-guild state belongs in the database layer, not on `self`
- Never hardcode response strings — use `ctx.t(...)` with locale keys

New plugins can be scaffolded with `easycord plugin create` and validated with `easycord plugin check`.

## Security

Never commit API keys, tokens, or credentials. All secrets must come from environment variables. If you discover a security issue, open a private GitHub security advisory rather than a public issue.

## Getting help

- [GitHub Issues](https://github.com/rolling-codes/EasyCord/issues) for bugs and feature requests
- `easycord doctor` for local environment diagnostics
- `easycord inspect` and `easycord sync-plan` for command registration debugging
- `context/architecture.md` and `context/conventions.md` for deeper framework internals
