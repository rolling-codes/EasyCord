# EasyCord Documentation

Pick a goal below to jump straight to what you need, or browse the [complete index](#complete-index) at the bottom.

---

## Start here

**New to EasyCord?** Read [Getting Started](getting-started.md) first. It covers installation, your first command, plugins, storage, and localization in one place.

---

## I want to…

### Build my first bot
→ [Getting Started](getting-started.md) — install, first command, project layout, `BotConfig`

### Add slash commands, context menus, components, or modals
→ [Interactions](interactions.md) — slash commands, autocomplete, buttons, select menus, modals, context menus

### Organize commands under a shared name (like `/admin kick`, `/admin ban`)
→ [Subcommand Groups](subcommand-groups.md) — `SlashGroup`, permission inheritance, guild restrictions

### Preview and apply my command registrations to Discord
→ [Command Sync](command-sync.md) — dry-run sync, diff output, guild-scoped sync, removal confirmation

### Add buttons and select menus with typed URL-style routing
→ [Dynamic Component Routing](components-dynamic-routing.md) — `:int`, `:str`, `:snowflake` routes, TTL-expiring components

### Run background tasks on a schedule
→ [Task Scheduling](task-scheduling.md) — `@task`, intervals, error restart, plugin lifecycle

### Add ready-made features without writing commands
→ [Built-in Plugins](builtin-plugins.md) — all 28 bundled plugins: levels, moderation, economy, reminders, polls, starboard, and more

### Add AI to my bot
→ [Conversation Memory](conversation-memory.md) — `ctx.ai()`, multi-turn history, provider selection, eviction  
→ [Built-in Plugins → AI plugins](builtin-plugins.md#ai-plugins) — `OpenClaudePlugin`, `OpenClawPlugin`, `AIModeratorPlugin`

### Show confirmation buttons, paginated messages, dropdowns, or forms
→ [Interactive UI](context-interactive-ui.md) — `ctx.confirm()`, `ctx.paginate()`, `ctx.choose()`, `ctx.prompt()`, `ctx.ask_form()`

### Control access: guild-only commands, cooldowns, permissions, rate limits
→ [Middleware Patterns](middleware-patterns.md) — `guild_only`, `rate_limit`, `require_permissions`, `cooldown`, custom middleware

### Handle errors gracefully
→ [Error Handling](error-handling.md) — per-command, plugin-scoped, and global error handler waterfall

### React to bot and plugin lifecycle events
→ [Lifecycle Hooks](hooks.md) — `before_command`, `after_command`, `on_plugin_load`, `on_plugin_unload`

### Let plugins talk to each other without tight coupling
→ [Event Bus](event-bus.md) — async pub/sub, exception isolation, subscribe/publish patterns

### See everything `ctx` can do
→ [Context Reference](context-reference.md) — complete API: responding, DMs, channels, moderation, member lookups, AI shortcuts

### Test my commands without a Discord connection
→ [Testing Commands](testing.md) — `PluginTestSuite`, `FakeContextBuilder`, `invoke_*` helpers, offline test patterns

### Develop faster: reload code without restarting the bot
→ [Hot-Reload Development](hot-reload-development.md) — `bot.run(reload=True)`, `on_reload()` hook, safe failure modes

### Use the CLI for scaffolding, inspection, and diagnostics
→ [Developer Toolkit](developer-toolkit.md) — `easycord new`, `easycord doctor`, `easycord inspect`, `easycord sync-plan`, `easycord audit-tools`

### Build a plugin package others can install
→ [Plugin Authoring](plugin-authoring.md) — manifest, entry-point discovery, `create_package_plugin`, `check_plugin_project`

### Mark APIs as deprecated or track when things were added
→ [Deprecation Helpers](deprecation.md) — `@deprecated`, `@version_introduced`, suppressing warnings in tests

### Get type checking working with Pyright
→ [Type Checking](type-checking.md) — `pyrightconfig.json`, typing `ctx`, `_MixinBase` pattern, common plugin patterns

---

## Complete index

| Guide | What it covers |
|---|---|
| [Getting Started](getting-started.md) | Install, first command, plugins, storage, localization |
| [Interactions](interactions.md) | Slash commands, autocomplete, buttons, modals, context menus |
| [Subcommand Groups](subcommand-groups.md) | `SlashGroup` — namespaced subcommands with permission gates |
| [Command Sync](command-sync.md) | Preview, diff, and apply Discord command registration |
| [Dynamic Component Routing](components-dynamic-routing.md) | Typed URL-style routes for buttons and select menus |
| [Task Scheduling](task-scheduling.md) | `@task` — background tasks, intervals, error restart |
| [Built-in Plugins](builtin-plugins.md) | All 28 bundled plugins — commands, setup, storage requirements |
| [Conversation Memory](conversation-memory.md) | Multi-turn AI context, eviction, `ctx.ai()` vs `Orchestrator` |
| [Interactive UI](context-interactive-ui.md) | `ctx.confirm()`, `ctx.paginate()`, `ctx.ask_form()`, `ctx.choose()`, `ctx.prompt()` |
| [Middleware Patterns](middleware-patterns.md) | Built-in guards, rate limiting, logging, custom middleware |
| [Error Handling](error-handling.md) | Per-command, plugin-scoped, and global error waterfall |
| [Lifecycle Hooks](hooks.md) | `before_command`, `after_command`, `on_plugin_load`, `on_plugin_unload` |
| [Event Bus](event-bus.md) | Async pub/sub between plugins |
| [Context Reference](context-reference.md) | Full `Context` API — responses, DMs, moderation, channels, members |
| [Testing Commands](testing.md) | `PluginTestSuite`, `FakeContextBuilder`, offline `invoke_*` helpers |
| [Hot-Reload Development](hot-reload-development.md) | Live code reload, `on_reload()` lifecycle, poll interval |
| [Developer Toolkit](developer-toolkit.md) | CLI scaffolding, inspection, diagnostics |
| [Plugin Authoring](plugin-authoring.md) | Build and distribute reusable plugin packages |
| [Deprecation Helpers](deprecation.md) | `@deprecated`, `@version_introduced` decorators |
| [Type Checking](type-checking.md) | Pyright config and plugin typing patterns |
