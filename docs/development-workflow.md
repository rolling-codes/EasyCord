# Development Workflow

How EasyCord itself gets updated: refining existing behavior, adding features, and shipping releases. This is the "how we ship" guide for maintainers and contributors — coding standards and test conventions live in [CONTRIBUTING.md](../CONTRIBUTING.md); building bots *with* the framework starts at the [docs index](README.md).

## Setup

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e ".[dev]"
easycord doctor
```

## The local gate

Every change — fix, feature, or release — passes the same four commands before it goes up in a PR. CI runs exactly these (plus CodeQL and the coverage upload), so a clean local run means a green PR:

```bash
pytest tests/                                      # full suite must pass
ruff check easycord tests --select E9,F63,F7,F82   # critical lint (blocking in CI)
python scripts/check_release_metadata.py           # version consistency across files
python scripts/verify_plugin_tests.py              # >=20 tests per plugin
```

CI gates on top of these: the test matrix runs on Python 3.10/3.11/3.12 (`.github/workflows/tests.yml`), coverage must stay at or above 80% (`codecov.yml`), and CodeQL must report no new findings.

## Refine or fix existing behavior

The verify-first loop:

1. Branch from `main`: `fix/<description>`.
2. **Verify first.** Reproduce the defect with a failing test before touching the implementation. Audit notes and bug reports go stale — the test is the proof the bug still exists as described.
3. **Fix atomically.** Failing test (red) → minimal fix (green) → refactor. One concern per commit, conventional format: `fix:`, `test:`, `refactor:`.
4. **Log it.** Add a row and a root-cause section to [`bugs.md`](../bugs.md) with the next `B-NNN` ID: where, symptom, root cause, fix, tests, lesson. The lesson line is the point — it's what stops the same class of bug from recurring.
5. Run the local gate, push, open a PR to `main` labeled `bug` or `fix`.

Fixing without a regression test is not done: the regression test *is* the fix's receipt.

## Add a new feature

First decide which surface the feature belongs to:

| Surface | When | Where |
|---|---|---|
| **Bundled plugin** | Self-contained user-facing behavior (commands + events + per-guild state) | `easycord/plugins/<name>.py` |
| **Core capability** | Framework-level machinery every plugin can use | `easycord/*.py` (mixins, decorators, middleware) |
| **External plugin** | Distributable separately from the framework | Scaffolded package with `easycord plugin create` |

### Bundled plugin

Copy the anatomy of `easycord/plugins/reputation.py` — it is the reference implementation:

- Pure helper functions at module top (independently testable, no mocking).
- A `Plugin` subclass with `@slash(description=..., permissions=[...], guild_only=True)` commands, `@on("event")` handlers, and `@task(...)` background loops.
- Per-guild state via `ServerConfigStore` — never on `self`. Atomic read-modify-write goes through `store.mutate(guild_id, fn)` or an explicit per-guild `asyncio.Lock` held across load → modify → save. A bare `load()` then `save()` sequence is a TOCTOU race (see B-013 in `bugs.md`).
- Register in `easycord/builtin_plugins.py` only if it should ship enabled with the framework.

### Core capability

Pick the existing pattern that fits — don't invent a new extension mechanism:

- **Bot method** → the matching `_bot_*.py` mixin. **Context method** → the matching `_context_*.py` mixin.
- **Decorator** → `easycord/decorators.py`; attach marker attributes the scanner in `_plugin_scanner.py` reads.
- **Request-phase behavior** → a middleware factory in `easycord/middleware.py` returning a `MiddlewareFn`.
- **Cross-plugin signaling** → `EventBus` / `HookRegistry`.

Public API is exported only through `easycord/__init__.py`. Anything in `easycord/_*.py` is internal and must not be imported by user code or docs examples.

### External plugin

```bash
easycord plugin create my_feature --mode in-project   # plugins/ dir in a bot project
easycord plugin create my_feature --mode package      # standalone pip package
easycord plugin check                                 # validate the manifest
```

The scaffold generates the plugin module, a test file, and an `easycord-plugin.json` manifest; package-mode plugins load via `load_entrypoint_plugins()`. See [Plugin Authoring](plugin-authoring.md).

### Every feature, regardless of surface

- **Tests:** use `invoke()` / `FakeContextBuilder` / `PluginTestSuite` from `easycord.testing` (see [Testing Commands](testing.md)). Plugins need ≥20 tests to pass CI. No wall-clock assertions — mock clocks and synchronize with `asyncio.Event`.
- **Docs:** one page under `docs/`, following the shape of [task-scheduling coverage in Organizing Code](organizing-code.md): quick start → parameters → lifecycle → error handling → testing. Add it to the [docs index](README.md).
- **Changelog:** entry under `### Added` in `CHANGELOG.md` with the touched file paths.
- **PR label** drives the next version (see below): `feature` / `plugin` / `enhancement`.

## Release a new version

Releases are label-driven and mostly automated. The order matters:

1. **Preconditions:** all intended PRs merged, `main` CI green.
2. **Bump.** `python scripts/bump_version.py 5.X.Y --dry-run` to review, then run it for real. It updates `pyproject.toml`, `easycord/__init__.py`, `README.md`, and `docs/getting-started.md`, then self-validates via `check_release_metadata.py`.
3. **Notes.** Add the CHANGELOG heading `## EasyCord v5.X.Y - YYYY-MM-DD` with `### Added` / `### Fixed` / `### Tests` sections, and include the expected wheel and sdist asset names. Release notes live in the GitHub Release draft; do not commit `release_v*/` folders to `main`.
4. **PR + draft.** Push the release branch and open a PR. Release Drafter maintains a draft GitHub Release from merged PR labels:

   | PR label | Version bump |
   |---|---|
   | `breaking-change` | major |
   | `feature`, `plugin`, `enhancement` | minor |
   | `bug`, `fix`, `security`, `dependencies`, `test`, `documentation` | patch |

5. **Merge, then publish.** Merging alone ships nothing — **publishing** the drafted GitHub Release triggers `publish-pypi.yml`, which builds the wheel + sdist and uploads to PyPI.
6. **Verify:** the version appears on [PyPI](https://pypi.org/project/easycord/) and the release assets are attached to the GitHub Release.

## Invariants worth pinning

The full list is in [CONTRIBUTING.md](../CONTRIBUTING.md#key-invariants-easy-to-get-wrong); the ones that most often bite during framework work:

- `ServerConfigStore`: a single `load()` or `save()` is atomic; a load→modify→save *sequence* is not. Use `.mutate()`.
- Cooldown sentinel is `float("-inf")`, not `0.0` — first invocation must always pass.
- Event handlers (`@on("message")` etc.) must never let Discord exceptions escape into the dispatcher; route destructive actions through one governed method.
- `on_reload()` fires on the **new** instance after a hot-reload swap.
- All user-facing strings go through `ctx.t(...)`.
