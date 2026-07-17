# EasyCord v5.56.0 Release Notes

## Install

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.56.0/easycord-5.56.0-py3-none-any.whl"
```

Source: `https://github.com/rolling-codes/EasyCord/releases/download/v5.56.0/easycord-5.56.0.tar.gz`

## ServerConfigStore In-Memory Cache

Per-guild config is now cached in memory after the first disk read. Hot-path reads
(e.g., starboard reaction checks, economy balance reads) no longer hit disk on every
event. The cache is kept coherent by `save()`, `mutate()`, and `delete()`.

## LevelsPlugin Expansion

### New slash commands

| Command | Permissions | Description |
|---|---|---|
| `/set_xp_multiplier <multiplier> [duration_minutes]` | manage_guild | Temporary XP boost (default: 60 min) |
| `/toggle_level_dm` | manage_guild | Toggle level-up DMs for the server |
| `/reset_xp <member>` | manage_guild | Zero out a member's XP and level |

### Leaderboard caching

`/leaderboard` caches the result for 5 minutes per guild, eliminating repeated
full XP file scans for busy servers. Invalidated by `/give_xp` and `/reset_xp`.

### XP multipliers

Multipliers persist to the guild config file with an expiry timestamp, so they
survive bot restarts within their duration. Expired multipliers fall back to 1×
automatically.

### Level-up DMs

When enabled via `/toggle_level_dm`, the bot sends a DM to the leveling user on
each level-up. If the DM is blocked (Forbidden), the error is logged and the
channel announcement still sends normally.

## Internal: decorators.py Cleanup

`component()`/`modal()` share `_dual_api_decorator()` and `user_command()`/
`message_command()` share `_context_menu_decorator()`. No public API changes.

## Internal: EconomyPlugin Improvements

- Lock eviction: per-guild balance locks are now evicted after 7 days of idleness
  or when the pool exceeds 5 000 guilds, preventing unbounded memory growth.
- Atomic transfer: `/transfer` uses a single load + single save under one lock,
  making the operation all-or-nothing.
