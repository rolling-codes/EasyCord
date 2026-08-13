# Command Sync

EasyCord separates command registration (writing to `InteractionRegistry`) from command sync (publishing to Discord via `discord.app_commands.CommandTree`). The sync planner lets you preview what would change before touching Discord.

---

## Preview a sync (no Discord connection)

```python
plan = bot.plan_command_sync(remote_commands=["old_ping", "old_ban"])
```

The plan is a dict with five keys:

| Key | Contents |
|---|---|
| `added` | Command names present locally but not in `remote_commands` |
| `changed` | Command names present in both with a detected definition change |
| `removed` | Command names in `remote_commands` but not registered locally |
| `unchanged` | Command names matching exactly on both sides |
| `warnings` | Diagnostic messages (e.g., duplicate names, scope conflicts) |

`changed` is reserved for a future full-schema comparison and is currently
empty. The offline planner compares command presence by name.

## Preview Discord's current commands

Once the bot has an authenticated Discord application connection, fetch a
read-only, type-aware preview from Discord:

```python
plan = await bot.preview_command_sync()
guild_plan = await bot.preview_command_sync(guild_id=123456789012345678)
```

The preview distinguishes slash, user-context, and message-context commands.
It never calls `sync()`, copies commands, or changes registry state. Discord
authentication, permission, network, and rate-limit exceptions propagate to
the caller so applications can apply their own retry policy.

---

## Dry-run sync

Run the planner as a coroutine without writing to Discord:

```python
plan = await bot.sync_commands(dry_run=True, remote_commands=["old_ping"])
```

Use dry-run in startup diagnostics or test suites to confirm the expected diff before a real sync.

---

## Live sync

```python
await bot.sync_commands()
```

Syncs all locally-registered commands globally via `discord.app_commands.CommandTree`.

### Guild sync (instant, for development)

```python
await bot.sync_commands(guild_id=123456789012345678)
```

Copies global commands into the target guild before syncing. Guild-scoped commands update in seconds; global commands can take up to an hour to propagate.

### Confirm removals explicitly

If the plan includes commands to remove from Discord, EasyCord requires an explicit flag:

```python
await bot.sync_commands(
    remote_commands=["old_ping", "old_ban"],
    confirm_removals=True,
)
```

Omitting `confirm_removals=True` when removals are present raises an error rather than silently deleting commands.

---

## Format the plan as text

```python
from easycord import format_sync_plan

print(format_sync_plan(plan))
```

---

## CLI

```bash
easycord sync-plan bot:bot --remote old_ping --remote old_ban
easycord sync-plan bot:bot --remote old_ping --json
```

`sync-plan` never contacts Discord. Pass `--remote` once per remote command name you want to compare against. Use `--json` for stable output in CI or other tooling.
