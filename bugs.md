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
| B-008 | 2026-06-30 | openclaw plugin | LOW | Open (for follow-up agent) | Optional member access: `ctx.guild.id` in guild_only cmds + `self.orchestrator`/`source` unnarrowed |

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

## B-008 — openclaw Optional member access (OPEN — for follow-up agent)
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
- **Status:** Not fixed in this pass (out of the CI/audit scope); recorded here so the
  next agent picks it up. Verify the exact line numbers against current `openclaw.py`
  before editing — they drift.

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
