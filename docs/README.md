# EasyCord Documentation

Pick a goal below to jump straight to what you need. **No wasted clicks.**

**[See the restructure plan →](RESTRUCTURE_PLAN.md)** — We're consolidating 25 guides to 12 core guides for clarity.

---

## Start here (5 minutes)

**New to EasyCord?** 
1. **Do the [Day 1 walkthrough](../README.md#your-first-bot-day-1)** in the README (creates a bot, writes a command, tests it offline)
2. **Follow the recommended learning path below**

---

## Recommended Learning Path

After Day 1, follow this progression to build real features:

1. **[Building Commands](building-commands.md)** — Add buttons, forms, autocomplete, command groups
2. **[Request Lifecycle](request-lifecycle.md)** — Add permission guards, error handlers, hooks
3. **[Organizing Code](organizing-code.md)** — Split into plugins, add background tasks, decouple with event bus
4. **[Storage & State](database-guide.md)** — Save and load per-guild data safely
5. **[Testing Commands](testing.md)** — Test offline without Discord running

**Optional:** [AI Features](conversation-memory.md) (conversation memory, optional in bot)  
**Reference:** [Built-in Plugins](builtin-plugins.md) (29 ready-made plugins to extend)

---

## Pick Your Path

Or jump straight to a specific goal:

### Building Commands & Features
| Goal | Read |
|------|------|
| Add slash commands with parameters | [Building Commands](building-commands.md) |
| Add buttons, dropdowns, forms | [Building Commands](building-commands.md) |
| Organize commands under one name (`/admin kick`) | [Building Commands](building-commands.md) |
| Dynamic routing for buttons (URL-style) | [Building Commands](building-commands.md) |
| Show pagination, confirmations, dropdowns | [Interactive UI](context-interactive-ui.md) |
| Bootstrap a new server's channels, roles, and permissions | [Server Setup Templates](server-setup.md) |

### Organizing & Controlling Code
| Goal | Read |
|------|------|
| Structure my bot into reusable plugins | [Organizing Code](organizing-code.md) |
| Control who can use a command (permissions, cooldowns) | [Request Lifecycle](request-lifecycle.md) |
| Let plugins communicate safely | [Organizing Code](organizing-code.md) |
| Handle errors gracefully | [Request Lifecycle](request-lifecycle.md) |
| React to lifecycle events (load/unload) | [Request Lifecycle](request-lifecycle.md) |
| Run background tasks on a schedule | [Organizing Code](organizing-code.md) |

### Data & Storage
| Goal | Read |
|------|------|
| Store user/guild data per guild | [Storage & State](database-guide.md) |
| Choose between SQLite and memory database | [Storage & State](database-guide.md) |
| Understand storage concurrency safety | [Storage & State](database-guide.md) |

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
| Contribute to EasyCord itself (fix, feature, release) | [Development Workflow](development-workflow.md) |

---

## All Guides

| Core Guides | What to read |
|---|---|
| [Getting Started](getting-started.md) | Installation, your first command, plugins |
| [Building Commands](building-commands.md) | Slash commands, groups, buttons, modals, context menus, dynamic routing |
| [Interactive UI](context-interactive-ui.md) | Built-in UI helpers (confirm, paginate, forms) |
| [Command Sync](command-sync.md) | Registering commands to Discord |
| [Request Lifecycle](request-lifecycle.md) | Middleware, error handlers, hooks, command flow |
| [Organizing Code](organizing-code.md) | Plugins, task scheduling, event bus, patterns |
| [Built-in Plugins](builtin-plugins.md) | 29 bundled plugins (levels, economy, moderation, AI, etc.) |
| [Server Setup Templates](server-setup.md) | `/setup-server` presets: channels, roles, permissions |
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
| [Development Workflow](development-workflow.md) | Contributing: fix/feature/release workflows |
