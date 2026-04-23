# EasyCord Model Context

## What this folder is for
- Project home for EasyCord.
- Current folder status: the EasyCord framework is now present and actively being updated.

## Version 3.1.3 Notes
The PDF titled `EasyCord_v3.1.3_Brainstorm.pdf` describes the v3.1.3 "Foundation Update" focus areas:
- Advanced database suite
- Localization and fallback handling
- Developer-experience utilities
- Performance and logging improvements

### Key ideas captured from the PDF
- `bot.db` should provide a unified database interface so command code does not care about the backend.
- New guilds should be synced automatically on join.
- JSON-style fields should be supported with serialization helpers where needed.
- Localization should use Discord user locale and fall back cleanly to English or a configured default.
- `bot.i18n.get()` should support interpolation like `Hello {user}!`.
- DX helpers should include reusable UI templates, an easy paginator, and confirmation dialogs.
- Status rotation should support dynamic data.
- Logging and analytics should stay non-intrusive and should surface errors through webhooks or private channels.
- Cooldowns should be simple to apply and should localize retry messages.

## Current Implementation State

- `bot.db` is implemented with auto-configured SQLite and in-memory backends.
- `Bot.load_builtin_plugins()` can load the bundled plugin pack.
- `Composer()` can forward builtin-plugin, database backend, database path, and guild auto-sync settings.
- `EmbedCard` and themed embed wrappers exist for embeds that carry buttons or select menus.
- Existing tests were updated and the full suite passed at save time.
- Open roadmap items from the PDF that are still not fully implemented: localization/i18n, dynamic status rotation, and richer analytics/webhook logging.

## Token-Saving Practices
Use these habits to keep future work concise and cheap:
- Read only the minimum set of files needed for the task.
- Prefer existing abstractions over inventing new ones.
- Summarize long docs instead of quoting them.
- Avoid repeating known context unless it changes.
- Make small, targeted edits instead of broad refactors.
- Reuse file paths and symbols already in the repo.
- Ask at most one short clarifying question only when blocked.
- When responding, lead with the result first and keep the explanation short.
- Prefer bullet points over long paragraphs.
- Do not reload this file unless the task touches project direction or architecture.

## Working Assumptions
- Treat the PDF roadmap as guidance, not a finished spec.
- Confirm details in source files before implementing any behavior.
- Keep future changes aligned with the existing architecture once code appears.
