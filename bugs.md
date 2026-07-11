# Bug Log

A running record of bugs found and fixed, with root cause and the lesson, so the
same mistakes are not repeated. Newest first. Severity: CRITICAL / HIGH / MEDIUM / LOW.

| ID | Date | Area | Severity | Status | Summary |
|----|------|------|----------|--------|---------|
| B-001 | 2026-06-30 | CI / test gate | HIGH | Fixed | Coverage gate ignored `async def` tests |
| B-002 | 2026-06-30 | CI / test gate | MEDIUM | Fixed | Plugin→test-file name mismatch counted real tests as 0 |
| B-003 | 2026-06-30 | CI / workflows | MEDIUM | Fixed | Invalid `assignees: ['tee']` broke issue-opening automation |
| B-004 | 2026-06-30 | Tests / typing | LOW | Fixed | `embed.footer.text` (`str \| None`) used with `in` without narrowing |
| B-005 | 2026-06-30 | Tests / typing | LOW | Fixed | `plugin._bot` (Optional) member access flagged by Pyright in tests |
| B-006 | 2026-06-30 | levels plugin | MEDIUM | Fixed | Cooldown map `.clear()` reset every user at once (XP-gate bypass) |
| B-007 | 2026-06-30 | invite_tracker | LOW | Won't fix (noted) | `_invite_cache` not pruned on guild-remove (bounded by guild count) |
| B-008 | 2026-06-30 | openclaw plugin | LOW | Fixed (v5.51.0) | Optional member access: asserts/guards added in the v5.51.0 release commit; pyright clean 2026-07-02 — see the Release v5.51.0 section |
| B-018 | 2026-07-02 | starboard plugin | HIGH | Fixed | `cfg.get("enabled")` without default read a missing key as disabled — starboard dead after `/starboard_channel` alone |
| B-019 | 2026-07-02 | plugins (pattern) | MEDIUM | Superseded by B-020 | No-default `cfg.get("enabled")` sweep closed as benign against internal config-creation paths only; B-020 reopened it for the manual-edit / partial-update threat model |
| B-013 | 2026-07-09 | auto_responder | HIGH | Fixed | TOCTOU race in trigger add/remove; also cfg.get("enabled") without default |
| B-014 | 2026-07-09 | invite_tracker | MEDIUM | Fixed | on_load swallowed discord.Forbidden; now catches discord.HTTPException |
| B-015 | 2026-07-09 | levels plugin | MEDIUM | Fixed | _grant_level_reward caught Forbidden only; HTTPException could escape |
| B-016 | 2026-07-09 | auto_role plugin | MEDIUM | Fixed | add_roles after asyncio.sleep had no exception handler |
| B-020 | 2026-07-10 | plugins (pattern) | MEDIUM | Fixed | Issue #74: no-default `cfg.get("enabled")` in economy, role_persistence, member_logging silently disabled features when the key was missing (manual config edit / partial update) — supersedes B-019's benign verdict |
| B-021 | 2026-07-10 | verification, welcome | MEDIUM | Fixed | Unguarded `channel.send` in `verification_panel` (surfaced by dropping bot_permissions preflight, PR #78 review) and in welcome/goodbye event handlers — Forbidden escaped the command/dispatcher |

---

## B-021 — Unguarded sends in verification_panel and welcome event handlers
- **Where:** `easycord/plugins/verification.py` `verification_panel` (panel send to the
  *configured* channel); `easycord/plugins/welcome.py` `_on_member_join` welcome send and
  `_on_member_remove` goodbye send.
- **Symptom:** if the bot lacks Send Messages in the configured channel,
  `verification_panel` raised `discord.Forbidden` out of the slash command (surfaced by
  Codex review on PR #78 after the bot_permissions preflight was dropped), and the
  welcome/goodbye sends raised into the event dispatcher.
- **Root cause:** the dropped `bot_permissions=["send_messages"]` preflight checked the
  *invocation* channel, so it never actually covered these sends — the target is a
  *configured* channel. Removing it exposed that the sends themselves were unguarded,
  same event-path class as B-014/B-015/B-016.
- **Fix:** new `send_safe()` helper (`easycord/helpers/channel.py`) — sends to a
  configured channel, absorbs Forbidden/HTTPException, logs a warning, returns the
  message or `None`. Adopted by `verification_panel` (ephemeral error + nothing
  persisted on `None`) and the welcome/goodbye sends. The auto-role `add_roles`
  failure now logs a warning instead of a silent `pass`.
- **Tests:** `test_verification.py::test_panel_send_forbidden_responds_ephemeral_error`,
  `test_plugin_commands.py::test_welcome_send_failure_does_not_escape`.
- **Lesson:** decorator-level `bot_permissions` can only validate the invocation channel.
  Any send to a channel taken from config must carry its own Forbidden/HTTPException
  guard, whether the decorator preflight exists or not.

---

## B-020 — no-default `cfg.get("enabled")` reopened for manual config edits (issue #74)
- **Where:** `easycord/plugins/economy.py:219` (`_on_message` reward gate),
  `easycord/plugins/role_persistence.py:53,79` (both member handlers),
  `easycord/plugins/member_logging.py:60` (`_log_to_channel` gate).
- **Symptom:** a config section that exists without the `enabled` key reads as
  disabled — the plugin silently stops working with no log output.
- **Root cause:** same as B-018 — `cfg.get("enabled")` without a default. B-019
  closed these sites as benign because no *internal* code path creates a partial
  section, but that verdict didn't cover an admin editing the config JSON directly
  or an external tool doing a partial update (issue #74's threat model). Any
  existing non-empty section bypasses the `_get_config()` defaults path.
- **Fix:** `cfg.get("enabled", True)` at all four sites, matching each plugin's
  `_DEFAULTS`. `ai_moderator.py:183,237` made *explicit* as
  `cfg.get("enabled", False)` — moderation is opt-in by design, so a missing key
  correctly reads as disabled there (no behavior change). `auto_responder.py:68`
  was already fixed by B-013.
- **Tests:** missing-`enabled`-key regression tests added in
  `test_plugin_logic.py`, `test_role_persistence.py`, `test_plugins_new.py`, and
  `test_ai_moderator.py` (the last pins the intentional opt-in default).
- **Lesson:** B-019's two-condition rule (truthy default + internal partial-write
  path) under-scoped the threat model. The config file is user-editable state:
  every `enabled` read must carry an explicit default regardless of internal
  write paths. B-018's lesson stands unqualified.

---

## B-018 — Starboard silently disabled after configuring only the channel
- **Where:** `easycord/plugins/starboard.py` — `_on_reaction_add`, `_on_reaction_remove`,
  `starboard_config` display.
- **Symptom:** New tests `test_reaction_add_archives_at_threshold` and
  `test_reaction_remove_unarchives_below_threshold` failed: handlers returned before
  archiving. In production: an admin who runs `/starboard_channel #starboard` (or any
  single config command) on a fresh guild gets a starboard that never fires.
- **Root cause:** `PluginConfigManager.get(guild, key, _DEFAULTS)` only applies defaults
  when the section is *absent*. `update()` creates the section with just the updated
  keys and no defaults merged. So a section created by `/starboard_channel` is
  `{"channel_id": …}` with no `"enabled"` key, and `if not cfg.get("enabled")` treated
  the missing key as `False`.
- **Fix:** `cfg.get("enabled", True)` in both reaction handlers and the config display —
  same missing-key fallback pattern the code already used for `emoji` and `threshold`.
- **Lesson:** With this config layer, a section can exist with *any subset* of the
  default keys. Every read must carry its own default (`cfg.get(k, default)`); relying
  on `_DEFAULTS` having been merged is wrong unless the section was created by the
  defaults path. See B-019 for the sweep of sibling plugins with the same pattern.

---

## B-019 — no-default `cfg.get("enabled")` sweep (SUPERSEDED by B-020)
- **Where:** the five plugins flagged after B-018: `auto_responder.py:68`,
  `economy.py:219`, `member_logging.py:60`, `role_persistence.py:53,79`,
  `ai_moderator.py:183,237`.
- **Verification (2026-07-02):** the B-018 bug requires an `update()`-only path that
  creates the config section *without* the `enabled` key before the defaults path runs.
  None of the five have one:
  - **member_logging, economy, role_persistence** — zero `update()` calls / zero config
    slash commands; their sections can only be created by `_get_config()` (defaults path),
    so `enabled` is always present.
  - **auto_responder** — `_update_config` calls exist (lines 100/112/130) but every one
    runs after `_get_config()` already created the section with defaults.
  - **ai_moderator** — default is `enabled: False` (opt-in moderation) and the explicit
    `/mod_enable` command always writes the key; a missing key reading as disabled is
    the CORRECT behavior. The `mod_config` display at line 237 is cosmetic-only.
  - Broader sweep for other no-default truthy-flag gates (e.g. moderation.py
    `enable_warnings`) found none reachable before a `_get_config()` call.
- **Lesson:** the B-018 pattern is only a bug when (a) `_DEFAULTS` has a truthy value for
  the key AND (b) an `update()`-style path can create the section before the defaults
  path runs. Check both conditions before filing sweep items — presence of the
  no-default read alone is not sufficient.
- **Superseded (2026-07-10):** issue #74 pointed out this verification only covered
  internal code paths — a manual config-file edit or partial external update can
  strip `enabled` from an existing section. Reopened and fixed as B-020.

---

## B-001 — Coverage gate ignored async test functions
- **Where:** `scripts/verify_plugin_tests.py:11` (`count_test_functions`)
- **Symptom:** PR #71's `Verify plugin test coverage thresholds` step failed on Python
  3.10/3.11/3.12 and cancelled all downstream test jobs. Plugins with many tests
  reported near-zero (e.g. `ai_moderator` showed 1 of 21).
- **Root cause:** The AST walk matched only `ast.FunctionDef`. An `async def test_…`
  parses as `ast.AsyncFunctionDef`, a *separate* node type, so every async test —
  nearly all plugin tests in this asyncio-mode-auto suite — was invisible.
- **Fix:** Count `(ast.FunctionDef, ast.AsyncFunctionDef)`.
- **Lesson:** When walking Python AST for *functions*, always handle both
  `FunctionDef` and `AsyncFunctionDef`. They do not share a common concrete base you
  can `isinstance`-check with one name. This codebase is async-first — assume tests
  are coroutines.

## B-002 — Plugin→test-file name mismatch
- **Where:** `scripts/verify_plugin_tests.py` (`main`)
- **Symptom:** Even after B-001, `levels` and `reminders` counted 0 tests.
- **Root cause:** The checker assumed `test_<plugin>.py`, but the files are
  `test_levels_plugin.py` and `test_reminder.py` (singular). The lookup silently
  treated a missing file as 0 tests instead of erroring.
- **Fix:** Added an explicit `test_file_aliases` map
  (`levels→levels_plugin`, `reminders→reminder`) consulted via a `test_file_for()`
  helper.
- **Lesson:** A "file not found → 0" branch hides configuration drift. Prefer an
  explicit alias map over silent zero; if a mapped file is missing, that should be
  loud. Also exposed a genuine gap (B-002 follow-up below).

### B-002 follow-up — genuine missing coverage
After B-001/B-002 fixes, three real gaps remained and were filled:
- `tests/test_reminder.py`: +2 tests (→20) — `_parse_duration` seconds + invalid-raises.
- `tests/test_tags.py` (new, 15): store CRUD, per-guild isolation, admin/author delete gating.
- `tests/test_starboard.py` (new, 11): config defaults, mutate-guarded archived-map RMW,
  archive/unarchive, NotFound cleanup, threshold/channel gating.

## B-003 — Invalid GitHub assignee in workflows
- **Where:** `.github/workflows/ci-failure-reporter.yml:75`, `nightly.yml:97`,
  `triage.yml:42`.
- **Symptom:** "CI Failure Reporter" run failed with an invalid-assignee error
  (`tee` is not a GitHub user on this repo; it is only the local `git config user.name`).
- **Root cause:** `assignees: ['tee']` hardcoded a local git identity as if it were a
  GitHub login. The repo is under the `rolling-codes` org; no `tee` collaborator exists.
- **Fix:** Removed the `assignees` field from the two `issues.create` calls and the
  `addAssignees` block in `triage.yml`; softened the triage comment accordingly.
- **Lesson:** GitHub assignees must be valid repo-collaborator *logins*, never a local
  git `user.name`. If auto-assignment is wanted later, set the maintainer's real
  GitHub login (or use `context.actor`), and prefer failing soft over hardcoding.

## B-004 — Optional `embed.footer.text` used with `in`
- **Where:** `tests/test_reminder.py:83` (pre-existing).
- **Symptom:** Pyright `reportOperatorIssue` — `in` unsupported for `str` and `None`.
- **Root cause:** `discord.Embed.footer.text` is `str | None`; the test used
  `"unknown time" in embed.footer.text` without narrowing.
- **Fix:** Assert `embed.footer.text is not None` first.
- **Lesson:** discord.py embed accessors are heavily Optional. Narrow before
  membership/index/attribute use in tests too — not just in `easycord/`.

## B-005 — Optional `_bot` member access in tests
- **Where:** `tests/test_starboard.py` (two unarchive tests).
- **Symptom:** Pyright `reportOptionalMemberAccess` on `plugin._bot.get_guild`.
- **Root cause:** `Plugin._bot` is `Optional`; configuring the mock through the
  attribute tripped the Optional check.
- **Fix:** Build a local `bot = MagicMock()`, configure it, then assign `plugin._bot = bot`.
- **Lesson:** Per CLAUDE.md, set `_bot` directly in tests — and configure the mock on a
  local variable to keep the attribute access off the Optional-typed field.

## B-006 — Levels cooldown map cleared wholesale
- **Where:** `easycord/plugins/levels.py` `_award_xp` (the memory-safety branch).
- **Symptom:** When the in-memory cooldown map exceeded 10k entries it ran
  `self._cooldowns.clear()`, wiping every tracked `(guild, user)` cooldown at once.
- **Root cause:** A "nuclear" reset used as memory bounding. Memory *was* bounded, but
  the side effect is a correctness bug: immediately after the clear, every user in
  every guild can earn XP again on their next message — a server-wide cooldown bypass
  (thundering-herd reset).
- **Fix:** Prune only entries older than the cooldown window (`ts < now - cooldown`),
  drop emptied guild dicts, keep active cooldowns. Threshold named
  `_COOLDOWN_PRUNE_THRESHOLD`. Regression test
  `test_award_xp_prunes_only_expired_cooldowns`.
- **Lesson:** Don't bound memory by discarding live state. Expired entries are free to
  drop (the gate would pass anyway); active ones must survive. "Clear everything at a
  threshold" trades a memory bound for a correctness hole.

## B-007 — invite_tracker cache not pruned on guild removal (noted, not fixed)
- **Where:** `easycord/plugins/invite_tracker.py:42` `_invite_cache: dict[int, dict[str, int]]`.
- **Assessment:** Keyed by `guild_id`, so bounded by the number of guilds the bot is in
  — not attacker-spammable (you cannot inject fake guild IDs). If the bot is kicked, the
  guild's entry lingers until restart. Low impact; left as-is to avoid speculative churn.
- **Lesson:** "Unbounded dict" is only a real DoS risk when the *key* is attacker-
  controlled. Guild-keyed caches are bounded by membership; user-keyed/global caches
  (cf. B-006) are the ones that need eviction.

## B-008 — openclaw Optional member access (FIXED — v5.51.0)
- **Where:** `easycord/plugins/openclaw.py`, Pyright `reportOptionalMemberAccess`
  (severity: warning, not the error baseline — so not CI-blocking, but real gaps):
  - `ctx.guild.id` in `guild_only=True` commands: lines **91, 119, 153, 164, 187**.
    `ctx.guild` is `Optional[Guild]`; at runtime `guild_only=True` guarantees it, but the
    static checker can't see that.
  - `self.orchestrator.strategy` — line **220** (`self.orchestrator` is Optional).
  - `source.can_execute(...)` — line **296** (`source` is Optional).
- **Fix (for the follow-up agent):** Apply the SAME pattern starboard already adopted in
  commit `bdd0c22` — add `assert ctx.guild is not None  # guaranteed by guild_only=True`
  at the top of each guild-only command before using `ctx.guild.id`. For the
  `orchestrator`/`source` cases, narrow with an explicit `if ... is None: return`
  (or assert) before the member access, matching how the value is actually guaranteed.
- **Lesson:** `guild_only=True` is a *runtime* guarantee the type checker doesn't model;
  the project convention is an explicit `assert ctx.guild is not None` per command, not a
  blanket `# type: ignore`. Same Optional-narrowing discipline as B-004/B-005.
- **Status:** Fixed in the v5.51.0 release commit (see "Release v5.51.0" section below,
  which records the same fix). Verified 2026-07-02: `pyright easycord/plugins/openclaw.py`
  → 0 errors, 0 warnings under the repo pyrightconfig (`reportOptionalMemberAccess:
  warning` active). This entry previously contradicted the release section — reconciled.

## Audit pass (2026-06-30) — verified clean / false positives
Four parallel read-only audits ran (mutate contract, destructive-action isolation,
Optional/None narrowing, per-guild memory growth). Recording the negatives so they
aren't re-investigated:
- **mutate() contract:** all 16 `.mutate(` callers pass synchronous local-only closures;
  every unguarded load→modify→save has its own per-guild lock. Clean.
- **Destructive-action isolation:** all `@on(...)` handlers performing delete / role /
  edit calls wrap discord exceptions; none escape the dispatcher. Clean.
- **Optional/None narrowing:** guild-only commands guarded; `get_member/get_channel/
  get_role/get_guild` results checked before use. No `ctx.author`, no `ctx.is_admin()`.
  Clean.
- **openclaw `_active`/`_runners`:** flagged as "no cleanup" but the `finally` block in
  the runner (and the stop path) pops both dicts; keyed by guild_id, one task per guild.
  **False positive** — verify the `finally` before trusting an audit's "no cleanup".

---

## Release v5.51.0 — CRITICAL bug fixes

Fixed in this release (July 2026):

### B-008 — openclaw.py Optional narrowing (FIXED)
Added `assert ctx.guild is not None` guards at lines 91, 119, 153, 164, 187 (guild-only commands).
Added `assert self.orchestrator is not None` before line 225.
Added `if source is None: return` guard at line 284.

### B-009 — scheduled_announcements.py loop resilience (FIXED)
Wrapped `ch.send()` at line 152 in try/except to catch `discord.Forbidden` and `discord.HTTPException`.
Loop continues on send failure instead of dying permanently.

### B-012 — ctx.channel Optional access (FIXED)
Added guards in giveaway.py:300, polls.py:304, reminder.py:209 before accessing `ctx.channel.id`.

### B-011 — tickets.py button guild guard (FIXED)
Added guard at line 95 to return early if `interaction.guild is None`.

### Cherry-pick c60c8b6 — three live bugs (FIXED)
- birthday.py: Fixed `_days_until` year-advance logic (Feb 29 crash)
- tickets.py: Fixed `oldest_first=False` in transcript history
- levels.py: Extracted `_grant_level_reward`, integrated into `/give_xp`

### B-017 — suggestions.py dead field (FIXED)
Removed unused `self.suggestion_counter = {}` from __init__.

### B-010 — tags.py concurrent write safety (FIXED)
Added per-guild `asyncio.Lock` to TagsStore._get_lock().
Made set() and delete() async with lock protection.
Added atomic delete_if_authorized() method to prevent TOCTOU race in authorization check.

## Fixed in v5.52.0

### B-013 — auto_responder.py TOCTOU race (FIXED)
Replaced `_add_trigger` / `_add_regex_trigger` / `_remove_trigger` load→modify→save
with `ServerConfigStore.mutate()`. Also fixed the sibling `cfg.get("enabled")` bug
(same root cause as B-018/B-019): changed to `cfg.get("enabled", True)` in `_on_message`
so a section created by a trigger-add before the defaults path runs doesn't silently
disable the plugin. Regression tests: 22 tests in `tests/test_auto_responder.py`.

### B-014 — invite_tracker.py on_load network I/O swallowed (FIXED)
`_refresh_invite_cache` now catches `discord.HTTPException` (parent of `discord.Forbidden`)
instead of `discord.Forbidden` alone, and logs the failure with `logger.warning`.

### B-015 — levels.py HTTPException not narrowed (FIXED)
`_grant_level_reward` now catches `discord.HTTPException` (covers `discord.Forbidden` as
a subclass) and logs a `logger.warning` instead of letting the exception escape.

### B-016 — auto_role.py exception after sleep (FIXED)
Post-sleep `member.add_roles()` call now caught under `discord.HTTPException` with a
`logger.warning`. Walrus-operator refactor also applied (`role for rid ... if (role := ...) is not None`)
to correctly narrow the type and avoid double lookups.

## Deferred
- LocalizationManager thread-safety (metrics atomicity)
- Hot-reload command dispatch race (architectural)
