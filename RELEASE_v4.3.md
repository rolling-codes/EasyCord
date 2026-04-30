# v4.3.0 - AI, Admin Helpers, Plugins, and Package References

**Release Date:** 2026-04-29

## Summary

v4.3.0 refreshes the EasyCord package line around the framework features now available in `easycord/`: unified AI calls, context helpers, UI builders, plugin improvements, localization fixes, and updated package download references.

## Added

- Unified AI helper: `ctx.ai()` centralizes AI calls across plugins, supports shared or one-off providers, supports model overrides for providers that expose a model setting, and works with localized AI response flows.
- Conversation memory integration: `Bot(enable_conversation_memory=True)` enables in-memory conversation storage, and `ctx.ai()` records user prompts and assistant responses when memory is active.
- Conversation history API: `ctx.conversation_history(limit)` returns recent `ConversationTurn` objects for the current user, or an empty list when conversation memory is unavailable.
- Structured conversation classes: `ConversationTurn`, `Conversation`, and `ConversationMemory` provide in-memory history storage for context-aware AI workflows.
- Orchestrator fallback support: `FallbackStrategy` tries providers in sequence when a provider fails or produces no final text.
- Composer and bot setup helpers: `Composer` exposes fluent setup methods for intents, localization, plugins, groups, built-in plugins, secure defaults, and convenience framework presets.
- Invitation and scheduled event helpers: `Context` includes `create_invite()`, `get_invites()`, `revoke_invite()`, `create_event()`, `get_events()`, and `delete_event()`.
- Invite tracking: `InviteTrackerPlugin` tracks invite usage, stores counts, and exposes invite stats and leaderboard commands.
- Moderation utilities: `Context` includes `kick()`, `ban()`, `timeout()`, `unban()`, `add_role()`, `remove_role()`, `purge()`, `send_file()`, thread helpers, and voice-channel helpers.
- UI builders: `EmbedBuilder`, `ButtonRowBuilder`, `SelectMenuBuilder`, and `ModalBuilder` provide chainable APIs for embeds and components.
- Tags and Levels plugins: `TagsPlugin` supports create/edit/delete/list tag workflows with JSON persistence, and `LevelsPlugin` provides XP, levels, named ranks, and role rewards.
- Package UX helpers: `Paginator`, `EasyEmbed.warning()`, `SecurityManager`, `FrameworkManager`, `Composer.secure_defaults()`, and `Composer.convenience_framework()` reduce boilerplate for common bot builds.

## Fixed/Improved

- Localization fallback order now tries the requested locale, configured default locale, language fallback, and then the generic default catalog.
- Fixed the `Bot.__init__` conversation-memory setup path by adding an explicit keyword argument without breaking existing keyword-only constructor behavior.
- Levels XP awarding now respects `cooldown_seconds` during message-based awards so rapid message spam cannot generate unlimited XP.
- Invite tracking now detects increased Discord invite use counts when members join.
- Type hints were refined for translation mappings and public helper APIs.
- Middleware now includes `boost_only()` and `has_permission()` helpers, plus improved logging and rate-limit cleanup behavior.
- Plugin reload and error handling are available through `Bot.reload_plugin()` and `Bot.on_error()`.
- Context-menu support is available through `user_command` and `message_command` decorators.
- Recreates stale cached webhooks once and retries the send instead of failing permanently.
- Validates emoji image paths and rejects files larger than Discord's 256 KiB custom emoji limit before upload.
- Makes SQLite payload decoding tolerate corrupt, invalid, or non-dict JSON by returning an empty mapping.
- Prunes empty middleware rate-limit buckets so long-running bots do not keep dead user entries.
- Runs OpenClaude limiter cleanup before prompt-length rejection so rejected oversized prompts still allow stale bucket cleanup.
- Preserves the `LevelsPlugin` bot-message guard fix already present on `main`.
- Release metadata, package install commands, and download references now point at the `v4.3` tag/release.

## Release Notes

- Added automatic release-label handling and PR governance cleanup for future release planning.
- `v4.3.0` publishes clearer notes for the actual `easycord/` package features and fixes.
- Added focused tests for `Bot(enable_conversation_memory=True)`, `ctx.ai()` memory logging, and `ctx.conversation_history()`.
- Added a focused invite-tracker test for member joins that increase an invite use count.

## Testing

- `python -m compileall easycord`
- `python -m build` was attempted, but the local Windows sandbox blocked build-backend temp directory writes.
