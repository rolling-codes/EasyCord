# EasyCord Documentation

Pick a goal below to jump straight to what you need. **No wasted clicks.**

**[See the restructure plan →](RESTRUCTURE_PLAN.md)** — We're consolidating 25 guides to 12 core guides for clarity.

---

## Start here (5 minutes)

**New to EasyCord?** Start with the [Day 1 guide in the README](../README.md#your-first-bot-day-1).  
Then pick one goal below based on what you want to build next.

---

## Pick Your Path

### Building Commands & Features
| Goal | Read |
|------|------|
| Add slash commands with parameters | [Building Commands](building-commands.md) |
| Add buttons, dropdowns, forms | [Building Commands](building-commands.md) |
| Organize commands under one name (`/admin kick`) | [Building Commands](building-commands.md) |
| Dynamic routing for buttons (URL-style) | [Building Commands](building-commands.md) |
| Show pagination, confirmations, dropdowns | [Interactive UI](context-interactive-ui.md) |

### Organizing & Controlling Code
| Goal | Read |
|------|------|
| Structure my bot into reusable plugins | [Plugin Authoring](plugin-authoring.md) |
| Control who can use a command (permissions, cooldowns) | [Request Lifecycle](request-lifecycle.md) |
| Let plugins communicate safely | [Event Bus](event-bus.md) |
| Handle errors gracefully | [Request Lifecycle](request-lifecycle.md) |
| React to lifecycle events (load/unload) | [Request Lifecycle](request-lifecycle.md) |

### Data & Storage
| Goal | Read |
|------|------|
| Store user/guild data per guild | [Built-in Plugins](builtin-plugins.md) |
| Choose between SQLite and memory database | [Built-in Plugins](builtin-plugins.md) |
| Understand storage concurrency safety | [Built-in Plugins](builtin-plugins.md) |

### AI Features (Optional)
| Goal | Read |
|------|------|
| Add AI chat to my bot | [Conversation Memory](conversation-memory.md) |
| Use built-in AI plugins (moderator, agent) | [Built-in Plugins → AI](builtin-plugins.md#ai-plugins) |
| Change LLM provider (Claude, OpenAI, etc.) | [Conversation Memory](conversation-memory.md) |

### Testing & Deployment
| Goal | Read |
|------|------|
| Test commands without running Discord | [Testing Commands](testing.md) |
| Verify my command registrations before deploying | [Command Sync](command-sync.md) |
| Debug issues in production | [Troubleshooting](troubleshooting.md) |

### Developer Experience
| Goal | Read |
|------|------|
| Reload code without restarting | [Hot-Reload Development](hot-reload-development.md) |
| Use the CLI (new project, doctor, inspect) | [Developer Toolkit](developer-toolkit.md) |
| Get type checking to work with Pyright | [Type Checking](type-checking.md) |
| Publish my plugin to PyPI | [Plugin Authoring](plugin-authoring.md) |
| Mark APIs as deprecated | [Deprecation Helpers](deprecation.md)

---

## All Guides

| Core Guides | What to read |
|---|---|
| [Getting Started](getting-started.md) | Installation, your first command, plugins |
| [Building Commands](building-commands.md) | Slash commands, groups, buttons, modals, context menus, dynamic routing |
| [Interactive UI](context-interactive-ui.md) | Built-in UI helpers (confirm, paginate, forms) |
| [Command Sync](command-sync.md) | Registering commands to Discord |
| [Request Lifecycle](request-lifecycle.md) | Middleware, error handlers, hooks, command flow |
| [Middleware Patterns](middleware-patterns.md) | Guards, rate limiting, logging, custom middleware |
| [Error Handling](error-handling.md) | Error handler waterfall |
| [Lifecycle Hooks](hooks.md) | Lifecycle events (before/after command, plugin load/unload) |
| [Event Bus](event-bus.md) | Plugin-to-plugin communication |
| [Built-in Plugins](builtin-plugins.md) | 28 bundled plugins (levels, economy, moderation, AI, etc.) |
| [Conversation Memory](conversation-memory.md) | AI context, multi-turn memory |
| [Testing Commands](testing.md) | Offline testing without Discord |
| [Plugin Authoring](plugin-authoring.md) | Build reusable plugins |
| [Hot-Reload Development](hot-reload-development.md) | Reload code without restart |
| [Developer Toolkit](developer-toolkit.md) | CLI tools (new, doctor, inspect) |
| [Type Checking](type-checking.md) | Pyright configuration |
| [Deprecation Helpers](deprecation.md) | Marking APIs as deprecated |
| [Troubleshooting](troubleshooting.md) | Common issues and fixes |
| [Context Reference](context-reference.md) | Full `Context` API |
| [Database Guide](database-guide.md) | Storage, concurrency, backends |
| [Plugin Ecosystem Health](plugin-ecosystem-health.md) | Profiling and scaling |
