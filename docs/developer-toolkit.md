# Developer Toolkit

EasyCord includes a small, dependency-free toolkit for local bot development.

## Create a bot

```bash
easycord new my-bot --template community
cd my-bot
pip install -e ".[dev]"
pytest
```

If you are new, start here instead of copying examples by hand. The scaffold
creates a runnable bot, tests, `.env.example`, `pyproject.toml`, and safe local
defaults. Generated runnable bot code uses `Bot(auto_sync=False)`, which keeps
command sync disabled and uses EasyCord's default local storage unless you
configure another database backend.

The default `plugin` scaffold matches v5.3 behavior and includes `bot.py`, one
plugin under `plugins/`, `.env.example`, `pyproject.toml`, and a starter pytest
file using `easycord.testing.invoke()`.

Choose a template when you want a smaller or more specialized starting point:

```bash
easycord new --list-templates
easycord new tiny-bot --template minimal
easycord new plugin-bot --template plugin
easycord new server-bot --template community
easycord new assistant-bot --template ai
easycord new storage-bot --template database
```

- `minimal`: one `bot.py` with a slash command and a command test.
- `plugin`: a plugin-oriented project; this is the default.
- `community`: a composition-first bot with bundled community plugins and tests.
- `ai`: a plugin scaffold with a friendly AI-provider placeholder command.
- `database`: a plugin scaffold showing SQLite app setup and in-memory tests.

## Check your setup

Run `doctor` before launching a bot or debugging a new environment:

```bash
easycord doctor
easycord doctor bot:bot
easycord doctor bot:bot --json
easycord audit-tools bot:bot
easycord audit-tools bot:bot --json
easycord audit-tools bot:bot --fail-on-warnings
```

The command checks Python version support, the installed `discord.py` package,
whether `DISCORD_TOKEN` is configured, and optionally imports a bot target. When
a target is supplied, it also reports how many EasyCord interactions are
registered and warns if local imports would auto-sync commands.

JSON output is stable for automation. Doctor checks include `code`, `name`,
`ok`, `detail`, `severity`, and `fix` fields:

```bash
easycord doctor bot:bot --json
```

The same output formatter is available in Python:

```python
from easycord import format_doctor_report

print(format_doctor_report(report))
```

## Audit AI tools

EasyCord can inspect registered AI tools without executing them or contacting an
AI provider:

```bash
easycord audit-tools bot:bot
easycord audit-tools bot:bot --json
```

The audit checks tool safety classification, enabled/disabled state,
descriptions, parameter schemas, permission gates, timeouts, and rate limits.
It is intentionally advisory: warnings do not change runtime behavior. Use
`--fail-on-warnings` in CI when you want safety warnings to fail the local check.

The same audit and formatter are available in Python:

```python
from easycord import audit_tool_registry, format_tool_audit

report = audit_tool_registry(bot.tool_registry)
print(format_tool_audit(report))
```

Example tool safety patterns:

```python
from easycord import Plugin, ToolSafety, ai_tool


class SafetyExamples(Plugin):
    @ai_tool(description="Read the server member count")
    async def member_count(self, ctx):
        return str(len(ctx.guild.members))

    @ai_tool(
        description="Timeout a member after moderator approval",
        safety=ToolSafety.CONTROLLED,
        permissions=["moderate_members"],
    )
    async def timeout_member(self, ctx, user_id: int):
        return f"Would timeout {user_id}"

    @ai_tool(
        description="No description provided.",
        safety=ToolSafety.CONTROLLED,
        require_guild=False,
    )
    async def risky_tool(self, ctx, value: str):
        return value
```

`risky_tool` will produce warnings because it has a placeholder description,
accepts user-provided arguments without a parameter schema, and has no admin,
permission, role, or user gate.

## Inspect interactions

Point the CLI at a bot object using `module:object` syntax:

```bash
easycord inspect bot:bot
easycord inspect bot:bot --json
```

This imports the bot and prints `bot.inspect_interactions()` in a readable
format. Use `--json` when another tool needs the grouped registry shape. The
same formatter is available in Python:

```python
from easycord import format_interaction_inventory

print(format_interaction_inventory(bot.inspect_interactions()))
```

## Preview command sync

```bash
easycord sync-plan bot:bot --remote old_ping
easycord sync-plan bot:bot --remote old_ping --json
```

`sync-plan` never contacts Discord. It compares local registered command names
with remote names you pass manually and prints the same plan shape returned by
`bot.plan_command_sync(...)`. Use `--json` for stable `added`, `changed`,
`removed`, `unchanged`, and `warnings` lists.

## Run a command offline

Invoke a registered slash command and see its response without connecting to
Discord — no token, no network:

```bash
easycord try bot:bot ping
easycord try bot:bot greet --set name=World --set times=3
easycord try bot:bot config --dm --no-admin      # invoke in a DM, as a non-admin
easycord try bot:bot ping --json
```

`try` imports the bot, runs the command through the same offline harness as
`easycord.testing.invoke`, and prints every captured response (with an
`(ephemeral)` marker and embed title/description when present). `--set key=value`
is repeatable; values are coerced to `int`, `float`, `bool`, then `str`. Context
defaults to an admin invocation in guild `100` — override with `--user`,
`--guild`, `--dm`, and `--no-admin`.

It exits non-zero when the command name is unknown (listing available commands)
or when the command raises, so it doubles as a quick smoke check in scripts. The
target module is imported, so guard `bot.run(...)` behind `if __name__ ==
"__main__":` or the import will block.

## Generate a test

```bash
easycord test-template greetings
easycord test-template greetings --output tests/test_greetings.py
```

The template uses `Bot(auto_sync=False, db_backend="memory")`, adds the plugin,
and invokes a command without connecting to Discord.

## Author plugin packages

Use the plugin authoring helpers when you want a reusable plugin module or a
distributable package instead of a full bot project. The Python API is the
primary interface:

```python
from pathlib import Path

from easycord import create_package_plugin

result = create_package_plugin(
    name="greetings",
    target=Path("easycord-greetings"),
    author="EasyCord Developer",
)
print(result.manifest_path)
```

Generated plugins include a required manifest. Runnable bot scaffolds default
to local storage; generated tests use `Bot(auto_sync=False,
db_backend="memory")` so test runs stay offline and disposable. Validate
projects before publishing or loading them dynamically:

```python
from easycord import check_plugin_project, discover_plugins, load_entrypoint_plugins

report = check_plugin_project("easycord-greetings")
plugins = discover_plugins()
installed = load_entrypoint_plugins(group="easycord.plugins")
```

The CLI wrappers are intentionally thin:

```bash
easycord plugin create greetings
easycord plugin check easycord-greetings
easycord plugin discover --json
```

Package plugins should publish entry points under `easycord.plugins`. See
[`plugin-authoring.md`](plugin-authoring.md) for the manifest fields and full
helper list.

## Offline interaction tests

Use the testing helpers for command, autocomplete, context menu, component, and
modal flows:

```python
from easycord.testing import invoke, invoke_autocomplete
from easycord.testing import FakeContextBuilder
from easycord.testing import invoke_component, invoke_message_command
from easycord.testing import invoke_modal, invoke_user_command

ctx = await invoke(bot, "hello")
choices = await invoke_autocomplete(bot, "search", "query", "ea")
profile = await invoke_user_command(bot, "Profile", target_id=42)
quote = await invoke_message_command(bot, "Quote", content="Ship it")
clicked = await invoke_component(bot, "ticket:close:42")
submitted = await invoke_modal(bot, "feedback", message="Great bot")
```

Use `FakeContextBuilder` when a direct handler test needs a richer offline
context:

```python
ctx = (
    FakeContextBuilder()
    .with_user(42, display_name="Ada")
    .in_guild(100, name="Test Guild")
    .as_admin()
    .with_permissions(manage_messages=True)
    .with_roles(123456789)
    .with_locale("en-US", guild_locale="en-GB")
    .build()
)

await my_handler(ctx)
ctx.assert_contains("done")
```

## Full local workflow

```bash
easycord new support-bot --template database
cd support-bot
pip install -e ".[dev]"
pytest
easycord doctor bot:bot
easycord audit-tools bot:bot
easycord inspect bot:bot --json
easycord try bot:bot ping
easycord sync-plan bot:bot --remote old_command --json
```
