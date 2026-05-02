# Changelog

## [4.5.0] — 2026-05-02

Stable release: v4.5.0-beta.3 promoted without feature changes after validation.

### Validated
- Full test suite passing for the stable release line
- Release consistency checks covering version pins, release notes, and package artifact hygiene
- Clean wheel and source distribution packaging

### Changed
- Package metadata and install documentation now target `v4.5.0`
- Release workflow validates and uploads built package artifacts

---

## [4.5.0-beta.3] — 2026-05-02

Release Candidate: All v4.5.0 hardening validated, 703 tests passing, production-ready.

### Validated
- All 3 correctness bug fixes (STRICT diagnostics, metrics isolation, locale validation)
- Complete test coverage (703/703 passing, zero regressions)
- Performance thresholds (5/5 benchmarks under limits)
- Release engineering (version consistency, clean packaging, comprehensive documentation)
- Operational guarantees (deterministic, bounded, safe, scalable)

---

## [4.5.0-beta.2] — 2026-05-02

Hardening phase: Correctness fixes, metrics semantics, performance enforcement.

### Fixed
- **STRICT diagnostics deduplication** — Now raises on EVERY call, not just first
- **get_metrics() snapshot mutation** — Returns fully isolated deep copy
- **Locale validation BCP-47** — Now accepts script subtags (zh-Hant-HK, sr-Latn-RS)

### Changed
- **Metrics semantics** — cache_misses only counts TRUE misses, not fallback/auto-translate
- **Release consistency** — check_release_consistency.py parameterized for pre-release versions
- **GitHub Actions** — perf-regression.yml with cache-based baselines and real comparison
- **CLAUDE.md** — Added Architecture Invariants, Forbidden Shortcuts, Performance Constraints

### Added
- **Benchmark JSON** — benchmark_i18n.py writes detailed JSON results
- **Regression tests** — 8 new tests validating all bug fixes and semantics

---

## [4.5.0-beta.1] — 2026-05-02

Localization platform foundation: Fallback chains, diagnostics, metrics, completeness validation.

### Added
- Locale auto-detection with intelligent fallback chains (user → guild → system → default)
- Regional fallback support (pt-BR → pt → en-US)
- Three diagnostic modes: SILENT (zero overhead), WARN (deduplicated), STRICT (raise)
- Translation completeness validation with metrics
- Debug-only locale resolution tracing
- Optional metrics tracking (cache hits, fallback frequency, locale distribution)
- Deterministic locale normalization (idempotent, cacheable)
- Bounded fallback chains (non-recursive, ~12 max candidates)

### Test Results
- 193 localization tests passing
- All diagnostic modes validated
- Performance verified under stress

---

## [4.1.0] — 2026-04-28

Localization auto-translate, Composer localization wiring, and release-line alignment.

### Added
- Optional `auto_translator` callback in `LocalizationManager` for missing-locale translation + caching.
- New Composer localization methods: `localization`, `default_locale`, `translations`, `auto_translator`.

### Changed
- `Bot(...)` can now auto-create localization when `auto_translator` is provided.
- Project/version metadata aligned to 4.1.0.
- README license section clarified for this release line (MIT only).

---

## [1.0.0] — 2026-04-24

**Stable release.**

### Added
- Localization system with `ctx.t()` for multi-language support
- `LocalizationManager` for registering and resolving translations
- Locale fallback chains: user locale → guild locale → default locale → English

### Merged
- PR #6: Complete localization implementation

### Stability
- 452 tests passing
- No breaking changes from pre-1.0 versions

---

## [2.8] — 2026-04-18

Fluent UI builders, plugin hot-reload, and command aliases.

### New: UI Builders

Four fluent builders in `easycord.builders` — all exported from `easycord` directly:

- **`EmbedBuilder`** — chain `.title()`, `.description()`, `.field()`, `.footer()`, `.color()`, call `.build()` for a `discord.Embed`
- **`ButtonRowBuilder`** — chain `.button()` calls, `.build()` returns a `discord.ui.View`; handlers wired via `@bot.component`
- **`SelectMenuBuilder`** — chain `.option()` calls, `.build(custom_id)` returns a `discord.ui.View`
- **`ModalBuilder`** — chain `.field()` calls, `await .send(ctx)` delegates to `ctx.ask_form()`

### New: `bot.reload_plugin(name)`

Reload a loaded plugin in-place — calls `on_unload()` then `on_load()` without re-instantiating:

```python
await bot.reload_plugin("TagsPlugin")
```

### New: `@slash(aliases=[...])`

Register extra command names that trigger the same handler:

```python
@bot.slash(description="Show help", aliases=["help2", "commands"])
async def help(ctx): ...
```

Works on both `@bot.slash` and the `@slash` decorator for Plugin methods. Plugin `remove_plugin` also cleans up alias registrations from the command tree.

---

## [2.7] — 2026-04-17

New plugin, a modal shortcut, a global error handler, and expanded embed support.

### New: `TagsPlugin`

Per-guild text snippet store. Drop it in like any other plugin:

```python
from easycord.plugins import TagsPlugin
bot.add_plugin(TagsPlugin())
```

Four slash commands: `/tag get`, `/tag set`, `/tag delete` (admin or creator), `/tag list`.
Persists to `tags_<guild_id>.json` in the configured `data_dir`.

### New: `ctx.prompt()`

Single-field modal shortcut — replaces the verbose `ask_form` call for the common "ask one question" case:

```python
text = await ctx.prompt("What's your reason?", max_length=200)
```

Returns the entered string, or `None` on timeout/dismiss.

### New: `@bot.on_error` decorator

Register a global error handler for unhandled command exceptions without wiring `catch_errors()` middleware:

```python
@bot.on_error
async def handle_error(ctx, error):
    await ctx.respond(f"Something went wrong: {error}", ephemeral=True)
```

### `send_embed` extras

Four new optional keyword arguments on `ctx.send_embed()`:

| Param | Effect |
| --- | --- |
| `thumbnail="url"` | Small thumbnail in top-right corner |
| `image="url"` | Large image below description |
| `author="name"` or `author={name, icon_url, url}` | Author line above title |
| `timestamp=True` | Current UTC timestamp; or pass a `datetime` |

All four are backwards-compatible — existing calls are unaffected.

### Component router, guild management, and context helpers

- `@bot.component(custom_id)` — persistent button/select-menu routing with prefix matching
- `_GuildMixin` — `fetch_guild`, `fetch_channel`, `leave_guild`, `create_channel`, `delete_channel`, `send_webhook`, `create_emoji`, `delete_emoji`, `fetch_guild_emojis`
- `ctx.fetch_member`, `ctx.bot_permissions`, `ctx.typing()`, `ctx.fetch_pinned_messages()`
- `boost_only()` and `has_permission()` middleware factories
- `set_status`: `activity_type="streaming"` now creates a `discord.Streaming` activity

---

## [2.6] — 2026-04-16

Internal refactor and framework improvements. No breaking changes to the public API.

### Bot internals split

`bot.py` (668 lines) has been split into three focused mixin modules that mirror how `Context` already works:

| File | Contents |
| --- | --- |
| `easycord/_bot_commands.py` | Slash command registration, context menus, subcommand groups |
| `easycord/_bot_events.py` | Event dispatch, middleware, presence, user lookup |
| `easycord/_bot_plugins.py` | Plugin lifecycle, background tasks, shared method scanner |

`bot.py` is now an 83-line shell that wires the mixins together.

### Deduplication: `add_group` / `add_plugin`

A shared `_scan_methods(plugin, *, parent=None)` helper replaced two nearly-identical `inspect.getmembers` loops. `_register_slash` now accepts an optional `parent: app_commands.Group` parameter, so `add_group` reuses it instead of copying the registration logic. The autocomplete lambda is now defined once.

### Composer: complete middleware coverage

`Composer` now exposes fluent methods for all built-in middleware — previously `dm_only`, `allowed_roles`, `admin_only`, and `channel_only` were missing. `add_group` is also now available on `Composer`.

### `LevelsPlugin` split

`easycord/plugins/levels.py` (406 lines) has been split:

- `easycord/plugins/_levels_data.py` — `LevelsStore` (atomic per-guild JSON storage), `xp_for_level`, `level_from_xp`, `progress_bar`, `rank_for_level`
- `easycord/plugins/levels.py` — `LevelsPlugin` class only (185 lines)

All seven slash commands in `LevelsPlugin` now use `guild_only=True` on the decorator, removing the `_require_guild` helper.

### Test consolidation

Three stale test files removed; their content merged into the correct homes:

| Deleted | Merged into |
| --- | --- |
| `tests/test_middleware_v2.py` | `tests/test_middleware.py` |
| `tests/test_v2.py` | `tests/test_bot.py` + `tests/test_context.py` |
| `tests/test_task.py` | `tests/test_bot.py` + `tests/test_decorators.py` |

A shared `bot` fixture now lives in `tests/conftest.py`, removing duplicate fixture definitions across files.

---

## [2.5] — 2026-04-13

New decorator parameter, two middleware factories, two context shortcuts, and minimized agent documentation.

### New: `ephemeral=True` on `@slash` / `@bot.slash`

All responses from a command are forced ephemeral without touching each `ctx.respond()` call:

```python
@slash(description="Show your token.", ephemeral=True)
async def token(self, ctx):
    await ctx.respond("Your token is …")  # automatically ephemeral
```

### New: `channel_only(*channel_ids)` middleware

```python
from easycord.middleware import channel_only

bot.use(channel_only(COMMANDS_CHANNEL_ID, BOT_CHANNEL_ID))
```

Restricts commands to the specified channels. Passes silently in DMs.

### New: `ctx.guild_id` property

`ctx.guild.id` safe shortcut — returns `None` instead of raising `AttributeError` in DMs.

### New: `ctx.is_admin` property

Boolean shortcut for administrator permission check — `True` only inside a guild when the invoking member has `administrator`. Always `False` in DMs.

```python
if not ctx.is_admin:
    await ctx.respond("Admins only.", ephemeral=True)
    return
```

### Doc minimization

`model.md` and `docs/api.md` rewritten as dense reference tables. Reduced from ~700 → ~200 lines in `model.md` and from ~460 → ~230 lines in `docs/api.md`, cutting agent token cost roughly in half when reading project context.

---

## [2.4] — 2026-04-13

New decorator parameter, middleware factory, context property, and simplified example plugins.

### New: `guild_only=True` on `@slash` / `@bot.slash`

Eliminates the repeated 4-line guild-guard boilerplate from commands that only work inside a server:

```python
# Before
@slash(description="Show server info.")
async def serverinfo(self, ctx):
    if ctx.guild is None:
        await ctx.respond("This command only works in a server.", ephemeral=True)
        return
    ...

# After
@slash(description="Show server info.", guild_only=True)
async def serverinfo(self, ctx):
    ...
```

Works on `@bot.slash`, `@slash` (plugin decorator), and `SlashGroup` subcommands.

### New: `admin_only()` middleware

```python
from easycord.middleware import admin_only

bot.use(admin_only())
```

Blocks commands unless the invoking member has the `administrator` permission. Passes silently in DMs — combine with `guild_only()` if the command must be server-only. Accepts a custom `message` kwarg.

### New: `ctx.member` property

```python
if ctx.member and discord.utils.get(ctx.member.roles, name="Staff"):
    ...
```

Returns the invoking user as `discord.Member` (with `.roles`, `.nick`, `.guild_permissions`) or `None` in DMs. Avoids the `isinstance(ctx.user, discord.Member)` cast that was previously required.

### Simplified `server_commands/`

- `info.py` — `serverinfo`, `roleinfo`, `channelinfo`, `roles` now use `guild_only=True` and `ctx.send_embed()` instead of manual `discord.Embed` calls and inline guild guards.
- `moderation.py` — `announce` now uses `guild_only=True` and `ctx.send_embed()`.

---

## [2.3] — 2026-04-13

`LevelsPlugin` — concurrency and performance bug fixes.

### Bug fixes

| Area | Fix |
| --- | --- |
| Config lock race | `_load_config` / `_save_config` shared the XP lock, so a config read could block (or be blocked by) an unrelated XP write. Config now has its own `_cfg_locks` dict. |
| Config write not atomic under concurrency | Config writes were unguarded; concurrent `/set_rank` calls could interleave. Replaced with `_update_config(guild_id, fn)` which holds `_cfg_locks[guild_id]` across the read-modify-write cycle. |
| `_level_from_xp` O(n) loop | Replaced the `while` loop with an O(1) closed-form solve via `math.isqrt`, removing a potential hot-path bottleneck on high-XP members. |

### Internal improvements (no API change)

- `_require_guild(ctx)` helper deduplicates the guild-only guard across all slash commands.
- `_rank_for_level` simplified to a one-liner using `max()`.
- Comments tightened; redundant inline remarks removed.

---

## [2.1] — 2026-04-13

`LevelsPlugin` — drop-in XP, leveling, and named rank system for any bot.

**Jump to docs:**

- [LevelsPlugin](docs/api.md#levelsplugin)

---

### 2.1 — New plugin: `easycord.plugins.levels.LevelsPlugin`

A fully self-contained per-guild leveling plugin. Members earn XP for sending messages; reaching a new level posts a level-up embed and optionally awards a configured Discord role.

**Slash commands it registers:**

| Command | Permission | What it does |
| --- | --- | --- |
| `/rank` | everyone | Show your level, XP, rank name, and progress bar |
| `/leaderboard` | everyone | Top-10 XP leaderboard for the server |
| `/give_xp member amount` | manage_guild | Award XP to any member |
| `/set_rank level name` | manage_guild | Attach a rank name to a level threshold |
| `/remove_rank level` | manage_guild | Remove a rank name |
| `/set_level_role level role` | manage_guild | Assign a role reward to a level |
| `/ranks` | everyone | List all configured ranks and role rewards |

**Quick start:**

```python
from easycord.plugins.levels import LevelsPlugin

bot.add_plugin(LevelsPlugin())
```

**Advanced:**

```python
bot.add_plugin(LevelsPlugin(
    xp_per_message=15,
    cooldown_seconds=45,
    announce_levelups=True,
    data_dir=".easycord/levels",
))
```

Full docs: [docs/api.md#levelsplugin](docs/api.md#levelsplugin)

---

## [2.0] — 2026-04-12

Context menus, message editing, pinning, crosspost publishing, voice state, ban listing, and two bug fixes.

**Jump to docs:**

- [Context menus](docs/api.md#context-menus)
- [Response editing](docs/api.md#responding)
- [Pinning](docs/api.md#message-management)
- [Voice state](docs/api.md#easycordcontext)
- [Member & ban helpers](docs/api.md#member--ban-helpers)

---

### 2.0 — New `Bot` decorators

| Decorator | What it does |
| --- | --- |
| `@bot.user_command(name)` | Register a right-click User context menu command |
| `@bot.message_command(name)` | Register a right-click Message context menu command |

Both pass middleware through the same stack as slash commands. Handlers receive `(ctx, target)` where `target` is `discord.Member \| discord.User` or `discord.Message` respectively.

Full docs: [docs/api.md#context-menus](docs/api.md#context-menus)

---

### 2.0 — New `Context` helpers

| Method / Property | What it does |
| --- | --- |
| `ctx.voice_channel` | Property — voice/stage channel the invoker is currently in, or `None` |
| `await ctx.edit_response(content, *, embed)` | Edit the bot's original response in-place |
| `await ctx.pin(message, *, reason)` | Pin a message in the current channel |
| `await ctx.unpin(message, *, reason)` | Unpin a message from the current channel |
| `await ctx.crosspost(message)` | Publish a message from an announcement channel to all followers |
| `ctx.get_member(user_id)` | Cache-only guild member lookup — no API call, returns `None` if not found |
| `await ctx.fetch_bans(limit)` | Return a list of `discord.BanEntry` for the guild |

Full signatures: [docs/api.md#easycordcontext](docs/api.md#easycordcontext)

---

### 2.0 — Bug fixes

| Method | Fix |
| --- | --- |
| `ctx.move_member` | Now accepts `discord.StageChannel` as a valid destination (previously rejected all non-`VoiceChannel` channels) |
| `ctx.purge` | Now works in `discord.Thread` channels (previously restricted to `TextChannel` only) |

---

## [1.199] — 2026-04-12

Reactions, targeted message deletion, static parameter choices, and bot-level user/member lookup.

**Jump to docs:**

- [Reactions](docs/api.md#reactions)
- [Message deletion](docs/api.md#message-management)
- [Static choices on slash params](docs/api.md#slash-commands)
- [Bot fetch helpers](docs/api.md#easycordbot)

---

### New `Context` helpers

#### Reactions

| Method | What it does |
| --- | --- |
| `await ctx.react(message, emoji)` | Add a reaction to a message |
| `await ctx.unreact(message, emoji)` | Remove the bot's own reaction |
| `await ctx.clear_reactions(message)` | Remove all reactions (requires `manage_messages`) |

Full signatures: [docs/api.md#reactions](docs/api.md#reactions)

#### Message management

| Method | What it does |
| --- | --- |
| `await ctx.delete_message(message, *, delay)` | Delete a message, optionally after a delay in seconds |

Full signatures: [docs/api.md#message-management](docs/api.md#message-management)

---

### New `@slash` / `@bot.slash` parameter

| Parameter | What it does |
| --- | --- |
| `choices={"param": ["a", "b", "c"]}` | Show a fixed dropdown in Discord for the named parameter |

Works on both `@bot.slash` and the plugin `@slash` decorator. Values may be strings or numbers — Discord renders them as a locked dropdown (no free-text entry).

Full docs: [docs/api.md#slash-commands](docs/api.md#slash-commands)

---

### New `Bot` method

| Method | What it does |
| --- | --- |
| `await bot.fetch_member(guild_id, user_id)` | Fetch a `discord.Member` by guild and user ID (cache-first, API fallback) |

`await bot.fetch_user(user_id)` is already available via the inherited `discord.Client` API.

Full signatures: [docs/api.md#easycordbot](docs/api.md#easycordbot)

---

## [1.198] — 2026-04-12

Server management: nickname editing, voice moves, role CRUD, slowmode, and channel locking.

**Jump to docs:**

- [Member management](docs/api.md#member-management)
- [Role management](docs/api.md#role-management)
- [Channel management](docs/api.md#channel-management)

---

### 1.198 — New `Context` helpers

#### Member management

| Method | What it does |
| --- | --- |
| `await ctx.set_nickname(member, nickname, *, reason)` | Set or clear a member's server nickname (`None` resets to default) |
| `await ctx.move_member(member, channel_id, *, reason)` | Move to a voice channel by ID, or disconnect (`None`) |

Full signatures: [docs/api.md#member-management](docs/api.md#member-management)

#### Role management

| Method | What it does |
| --- | --- |
| `await ctx.create_role(name, *, color, hoist, mentionable, reason)` | Create a new role; returns `discord.Role` |
| `await ctx.delete_role(role_id, *, reason)` | Delete a role by ID |

Full signatures: [docs/api.md#role-management](docs/api.md#role-management)

#### Channel management

| Method | What it does |
| --- | --- |
| `await ctx.slowmode(seconds, *, reason)` | Set slowmode delay (0 = off, max 21600) |
| `await ctx.lock_channel(*, reason)` | Prevent @everyone from sending messages |
| `await ctx.unlock_channel(*, reason)` | Restore @everyone send permission |

Full signatures: [docs/api.md#channel-management](docs/api.md#channel-management)

---

## [1.197] — 2026-04-12

Moderation helpers, role assignment, bulk delete, file sending, threads, message history, select-menu UI, autocomplete, and bot presence.

**Jump to docs:**

- [Autocomplete](docs/api.md#slash-commands)
- [Bot presence](docs/api.md#presence)
- [Select-menu UI (`ctx.choose`)](docs/api.md#interactive-ui)
- [Moderation helpers](docs/api.md#moderation)
- [Role management](docs/api.md#role-management)
- [Message management](docs/api.md#message-management)
- [Threads & history](docs/api.md#threads)

---

### 1.197 — New `Context` helpers

| Method | What it does |
| --- | --- |
| `await ctx.choose(prompt, options, ...)` | Select-menu; returns chosen string or `None` on timeout |
| `await ctx.kick(member, *, reason)` | Kick a member |
| `await ctx.ban(member, *, reason, delete_message_days)` | Ban a member |
| `await ctx.timeout(member, duration, *, reason)` | Temporarily mute (seconds) |
| `await ctx.unban(user, *, reason)` | Unban a user |
| `await ctx.add_role(member, role_id, *, reason)` | Add a role by ID |
| `await ctx.remove_role(member, role_id, *, reason)` | Remove a role by ID |
| `await ctx.purge(limit)` | Bulk-delete recent messages; returns count |
| `await ctx.send_file(path, *, filename, content, ephemeral)` | Send a file attachment |
| `await ctx.fetch_messages(limit)` | Return N most recent messages |
| `await ctx.create_thread(name, *, auto_archive_minutes, reason)` | Create a thread; returns `discord.Thread` |

### 1.197 — New `Bot` method

| Method | What it does |
| --- | --- |
| `await bot.set_status(status, *, activity, activity_type)` | Set presence and activity text |

### 1.197 — New `@slash` parameter

| Parameter | What it does |
| --- | --- |
| `autocomplete={"param": async_fn}` | Live suggestions as the user types |

---

## 1.196 and earlier — Initial release

| Feature | Docs |
| --- | --- |
| `@bot.slash` — slash commands, permission guards, cooldowns | [concepts.md](docs/concepts.md#slash-commands) |
| `@bot.on` — multi-handler event system | [concepts.md](docs/concepts.md#events) |
| `bot.use` — middleware chain | [concepts.md](docs/concepts.md#middleware) |
| `Plugin` / `SlashGroup` — lifecycle hooks and grouping | [concepts.md](docs/concepts.md#plugins) |
| `@task` — repeating background tasks | [api.md](docs/api.md#decorators-for-plugins-easycorddecorators) |
| `Context` — respond, defer, send\_embed, dm, send\_to, ask\_form, confirm, paginate | [api.md](docs/api.md#easycordcontext) |
| `ServerConfigStore` — per-guild atomic JSON config | [api.md](docs/api.md#easycordserverconfigstore) |
| `AuditLog` — structured embed logging | [api.md](docs/api.md) |
| `Composer` — fluent bot builder | [README.md](README.md#composer) |
