# Server Setup Templates

`ServerSetupPlugin` bootstraps a server's structure from a preset template: categories, text and voice channels, roles, role-level permissions, and per-channel permission overwrites (like staff-only areas).

```python
from easycord.plugins import ServerSetupPlugin

bot.add_plugin(ServerSetupPlugin())
```

## The `/setup-server` command

```bash
/setup-server template:<gaming | community | study | creator>
```

The command is admin-gated (invoker needs **Manage Server**; the bot needs **Manage Channels** and **Manage Roles**) and always runs in three steps:

1. **Preview** — an ephemeral embed shows exactly which roles and channels would be created, and which already exist and will be skipped.
2. **Confirm** — Apply/Cancel buttons. Nothing is created until you press **Apply**. The prompt times out after 60 seconds (timing out creates nothing).
3. **Apply** — items are created in order (roles → categories → channels) with an audit-log reason, then a summary reports what was created, skipped, or failed.

## Additive only — the safety guarantee

Applying a template never modifies or deletes anything that already exists:

- A role or channel whose (Discord-normalized) name already exists is **skipped**, not touched. `General Chat` and `general-chat` count as the same text channel.
- Re-running the same template — or a second template on top — only fills in the gaps. Re-running is always safe.
- If everything in the template already exists, the command says so and stops before the confirm step.

## Templates

| Key | Label | Roles | Highlights |
|---|---|---|---|
| `gaming` | Gaming / Esports | Admin, Moderator, Team Captain, Member | Game Rooms voice category (Lobby, Team Alpha/Bravo), looking-for-group, staff-only area |
| `community` | Community / Social | Admin, Moderator, VIP, Member | Introductions, events, voice lounges, staff area with mod-log |
| `study` | Study / Education | Admin, Tutor, Student | Subject channels, homework-help, quiet voice rooms, tutor lounge |
| `creator` | Creator / Content | Admin, Moderator, Subscriber, Member | Read-only new-uploads, showcase/fan-art, subscriber-only lounge, watch party voice |

Every template includes a read-only announcements channel (send denied for `@everyone`) and a staff category hidden from `@everyone`.

## Permissions behavior

- **Role permissions are clamped**: Discord rejects granting a permission the bot itself lacks, so requested role permissions are intersected with the bot's guild permissions. Clamped roles are named in the summary.
- **Role ordering is left to you**: new roles are created at the bottom of the role hierarchy. Drag them where you want them afterward — the plugin never reorders roles.
- **Overwrites resolve by role name**: staff-only channels reference template roles (or pre-existing roles with the same name). If a referenced role could not be created, its overwrite is dropped and reported, never raised.
- Per-item failures (for example a `Forbidden` from Discord midway) are recorded in the summary and do not abort the rest of the run.

## Tracking

After a successful apply, the plugin records the template key, timestamp, invoker, and created role/channel IDs in its per-guild store (default `.easycord/server_setup/<guild_id>.json`). The preview footer mentions any previous run.
