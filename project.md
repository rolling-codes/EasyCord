# Project Log — EasyCord

Living record of **critical decisions** and **bug fixes**, plus a **per-PR triage log**.
Purpose: keep findings consistent across PRs. Automated reviewers (augmentcode,
coderabbit, sourcery) and human passes have been inconsistent PR-to-PR — some PRs
caught far more than others, and stale branches generate findings that no longer
apply. This file is the durable memory so the same bug isn't re-litigated and a
real one isn't dropped.

> Scope: this is a decision/triage journal. The one-time deep audit lives in
> [`EasyCord_Improvement_Plan/`](EasyCord_Improvement_Plan/). Architecture/conventions
> live in [`CLAUDE.md`](CLAUDE.md), [`AGENTS.md`](AGENTS.md), and [`context/`](context/).

**Snapshot:** v5.50.2 · Python 3.10+ / discord.py 2.7.1–<3 · active branch
`fix/ai-moderator-governance-and-doc-drift` (merged once as #63 → v5.50.1, continued to v5.50.2).

---

## Triage methodology (read before acting on any review)

External review findings are **suggestions to verify, not orders**. The dominant
failure mode here is acting on a finding whose code has moved or never existed on
the target branch.

1. **Verify against *current* code, not the PR's line numbers.** Stale/behind
   branches make line references meaningless. Open the real file on the active branch.
2. **Classify every finding into one bucket:**
   - **already-fixed** — current code already handles it (common on stale PRs).
   - **moot** — the flagged code only exists on the stale branch / feature not present here.
   - **valid** — reproduces on current code → fix it.
   - **pushed-back** — technically real but pre-existing and out of scope, or wrong for this stack. Record *why*.
3. **Fix valid items one at a time, test each.** Match existing codebase patterns.
4. **Record the disposition here** so the next PR's reviewer pass doesn't re-raise it.

---

## Critical decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-28 | **AI-moderation actions are hardcoded-safe, never model-driven.** `ModerationAction = Literal["delete","warn"]`; `_on_message` passes literal `"delete"`/`"warn"` to the single governed `_execute_action`, never the model's returned `action`. | An LLM verdict must not be able to escalate to timeouts/mutes. Destructive actions stay inside one path that owns rate limiting + Discord error handling and never raises into the event dispatcher (the broad `except` there is intentional, `# noqa: BLE001`). |
| 2026-06-28 | **Config mutators must be permission-gated via `permissions=[...]` on `@slash`.** | `permissions=` is enforced server-side at runtime in `_command_callbacks.py` (resolves member, checks `guild_permissions.<perm>`), not just a Discord UI hint. `manage_guild` is the project convention for admin config commands (auto_role, levels, starboard, birthday all use it). |
| 2026-06-28 | **Admin checks use the `ctx.is_admin` property, not manual `guild.get_member()` lookups.** | `get_member()` returns `None` for uncached members → falsely denies legitimate admins. `ctx.is_admin` is the documented, correct path. |
| 2026-06-28 | **Full plugin i18n is aspirational, not a merge blocker.** Several bundled plugins (moderation ~48, suggestions ~11, economy ~6, starboard ~4) still hardcode response strings. | The `ctx.t(...)` convention is real, but localizing the whole suite is a separate initiative. Don't let "localize these strings" findings on unrelated plugins block scoped PRs — track them as debt instead. |
| 2026-06-28 | **Stale release branches get closed, not "fixed."** PR #70 (`release/v5.43.3`) closed as superseded rather than rebased. | Its substantive findings were already fixed/moot on `main` (v5.50.2). Re-fixing a branch 14 commits behind wastes effort and risks reintroducing reverted code. |
| 2026-06-28 | **All config read-modify-write goes through `ServerConfigStore.mutate(guild_id, fn)`.** The per-guild `asyncio.Lock` only made a single `load`/`save` atomic; `mutate` holds it across the whole load→modify→save. `fn` must be sync and do no network I/O (the lock is held while it runs). | Generalizes the per-guild-lock pattern economy/auto_role/birthday/giveaway/polls already used (their bespoke `_guild_lock` dicts are now redundant but left as-is). Eliminates last-write-wins data loss across the config layer. Never hold the lock across Discord I/O — do `channel.send`/`add_roles` outside `mutate`. |
| 2026-06-28 | **role_persistence records roles by identity, gates assignability at restore, and only clears the record on success or when stale.** | A role above the bot at leave-time must still be remembered and restored once the bot's position improves; a failed restore must be retryable, and an entry whose roles were all deleted must not leak forever. |
| 2026-07-02 | **Plugin test-count floor is a flat ≥20 for every plugin** — `verify_plugin_tests.py` no longer distinguishes complex (≥20) from simple (≥8). Suggestions/tags/starboard were brought up from 13/15/11 to 21/21/25 tests to keep the gate green. | The complex/simple split let the smallest plugins stay thin; a single floor keeps coverage expectations uniform. Docs updated in CLAUDE.md and CONTRIBUTING.md. |

---

## Bug fixes

| Date | Severity | Area | Fix | Source |
|------|----------|------|-----|--------|
| 2026-06-28 | High (security) | `plugins/ai_moderator.py` | Added `permissions=["manage_guild"]` to all five config mutators (`mod_enable`, `mod_threshold`, `mod_action_level`, `mod_add_rule`, `mod_remove_rule`) — previously any member could enable moderation or flip it to `auto_delete`. Added parametrized regression test in `tests/test_ai_moderator.py`. | PR #70 review (coderabbit) |
| 2026-06-28 | Low (correctness) | `plugins/tags.py` | `tags.delete` now uses `ctx.is_admin` instead of `ctx.guild.get_member(ctx.user.id)` + `administrator` (uncached member → false denial). | PR #70 review (coderabbit) |
| 2026-06-28 | Med (data integrity) | `server_config.py`, `_config_manager.py` | Added atomic `ServerConfigStore.mutate()`; routed `PluginConfigManager.update`/`get`(create)/`set_default` through it. Fixed the overstated "per-guild locks"/"atomically" docstrings. | Code-read audit (user) |
| 2026-06-28 | Med (data integrity) | `plugins/suggestions.py` | `_get_next_id`, suggestion storage, and approve/reject now run under `mutate` — fixes duplicate IDs and dropped suggestion entries from racing `/suggest`. | Code-read audit (user) |
| 2026-06-28 | Med (data integrity) | `plugins/starboard.py`, `plugins/reaction_roles.py`, `plugins/moderation.py` | Routed archived-message writes, reaction-role mapping writes + delete-event cleanups, and `/warn` warning appends through `mutate`. reaction_roles `raw_message_delete` keeps a read-first guard so it doesn't write on every deletion. | Code-read audit (user) |
| 2026-06-28 | Med (data integrity + logic) | `plugins/role_persistence.py` | Routed save/restore through `mutate`; plus 3 logic fixes — save by identity (not bot hierarchy), gate assignability at restore, and only delete the saved record on successful restore or when all saved roles are gone (failed restore now retryable). | Code-read audit (user) |
| 2026-07-02 | High (feature dead on arrival) | `plugins/starboard.py` | B-018: `cfg.get("enabled")` without default treated a missing key as disabled — any guild whose config section was created by a single config command (e.g. `/starboard_channel`) had a starboard that never fired. Fixed with `cfg.get("enabled", True)` in both reaction handlers + config display. B-019 (open): same pattern in auto_responder, economy, member_logging, role_persistence, ai_moderator needs a sweep. | New ≥20-test gate work (test-first exposure) |

New tests: `tests/test_server_config.py::TestAtomicMutate`, `tests/test_suggestions.py`, `tests/test_role_persistence.py`. Full suite: 1248 passed.

---

## PR triage log

| PR | Branch | Disposition | Notes |
|----|--------|-------------|-------|
| #70 | `release/v5.43.3` | **Closed (superseded)** | 14 commits behind `main` (v5.50.2), conflicting. ~40 bot findings triaged: most **already-fixed** (orchestrator fallback/`attempt`, `steps` accounting, tool-schema gating via signature inspection, `tools.execute()` auth, `auto_delete` governance, `/unmute` role creation, CHANGELOG conflict marker); many **moot** (welcome `fetch_ban`, `/saved_roles`, suggestions key-migration, economy `/buy` shop, invite_tracker state, reaction_roles responses — code only on the stale branch); 2 **valid** → fixed (see Bug fixes). i18n comments **pushed-back** (pre-existing debt). |
| #63 | `fix/ai-moderator-governance-and-doc-drift` | Merged → v5.50.1 | AIModeratorPlugin governance + doc drift. Active branch continued past this to v5.50.2. |

---

## Known issues / tech debt

- ~~**`scripts/verify_plugin_tests.py` undercounts tests.**~~ *Fixed* — B-001 (walks
  `ast.AsyncFunctionDef`) and B-002 (plugin→test-file aliases). 2026-07-02: threshold
  is now a flat ≥20 for all plugins (was complex ≥20 / simple ≥8).
- **Local pytest hangs at exit on this dev machine** (Python 3.14 + pytest 9.1.1):
  every run — including untouched files like `test_middleware.py` — completes all
  tests to `[100%]`, then hangs before printing the summary. Results are still
  readable from `-v` output. CI (3.10/3.12) is unaffected. Suspect pytest-asyncio/
  interpreter finalization; diagnose when a local upgrade window opens.
- **Plugin i18n gaps** — moderation/suggestions/economy/starboard hardcode response
  strings (see decision above). Migrate to `ctx.t(...)` as a dedicated pass.
- **CI action-pin drift** — invariants in CLAUDE.md/AGENTS.md state `actions/checkout@v4`
  is pinned (and "v6 does not exist"), but dependabot PR #65 bumped checkout 4→7.
  Confirm `tests.yml` (currently `@v4`) and other workflows agree, and reconcile the
  documented invariant with what's actually pinned.

---

## Maintaining this file

- Add a **PR triage** row whenever a PR's review is processed — record the disposition, not just "fixed."
- Promote any durable choice (security gate, architectural rule, scope call) to **Critical decisions**.
- Log every applied fix in **Bug fixes** with severity + source PR.
- Move resolved tech-debt items out of **Known issues** (note the PR that closed them).
- Keep entries dated (absolute dates) and terse — this is an index, not prose.
