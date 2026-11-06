# Getting Started with EasyCord

Create a bot, test its first command offline, then connect it to your test server.
You need Python 3.10 or newer. EasyCord uses `discord.py>=2.7.1,<3` for the Discord connection.

## 1. Install and create a project

Create a virtual environment and activate it:

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
```

Install EasyCord from this checkout, then generate the smallest starter:

```bash
python -m pip install -e .
easycord new my-bot --template minimal
cd my-bot
python -m pip install -e ".[dev]"
```

Run the install command from the EasyCord repository root. These instructions
use the updated scaffolds in this checkout; the published v5.61.1 wheel contains
the earlier starter workflow. For that released version, use the
[v5.61.1 wheel](https://github.com/rolling-codes/EasyCord/releases/download/v5.61.1/easycord-5.61.1-py3-none-any.whl).

The starter includes `bot.py`, a README with setup steps, and a command test.
Use `--template community` when you want bundled features, or
`easycord new --list-templates` to see the other choices. The CLI's existing
default remains `plugin` for compatibility.

## 2. Get your first response offline

```bash
python -m pytest
easycord try bot:bot ping
```

The response should contain `Pong!`. No token, Discord account, or network
connection is needed for these commands after installation.

`bot:bot` means “the object named `bot` in `bot.py`.” It uses memory storage
and has command sync disabled. Each generated test creates and closes its own
memory-backed bot, so tests do not write a SQLite database.
Community plugins also have JSON storage: offline checks use `.easycord/offline`,
live launch uses `.easycord/live`, and tests run in temporary directories.
Changing the database backend alone does not change a plugin's JSON storage.

## 3. Connect to Discord

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Open **Bot** and create/reset its token. Keep the token private.
3. Under **OAuth2 → URL Generator**, select `bot` and `applications.commands`.
   Choose any permissions needed by the features you add, open the generated
   URL, and invite the bot to a server you manage.
4. In Discord, enable **User Settings → Advanced → Developer Mode**, then
   right-click that server and choose **Copy Server ID**.
5. Export both values in your launch shell.

macOS/Linux:

```bash
export DISCORD_TOKEN="your-bot-token"
export DISCORD_GUILD_ID="your-test-server-id"
```

Windows PowerShell:

```powershell
$env:DISCORD_TOKEN="your-bot-token"
$env:DISCORD_GUILD_ID="your-test-server-id"
```

`.env.example` documents the variables. EasyCord does **not** load `.env` files
automatically; copying that file alone will not configure the bot.

```bash
easycord doctor bot:bot
python bot.py
```

The generated launch function validates the configuration, enables command sync
for your test server, and uses persistent SQLite storage at `data/bot.db` by
default. After login and sync succeed, run `/ping` in that server.
Set `EASYCORD_AUTO_SYNC=false` when you explicitly want to disable publication.
The launch log reports whether sync is enabled.
The generated `main()` delegates to `run_bot(create_bot)`, so your project does
not need its own copy of configuration parsing and launch handling.

The offline bot remains available for tests and CLI tools. Use `python bot.py`
to launch the live instance with command sync enabled.

If the command is missing, check the launch logs, the server ID, and the invite
scopes. An offline response verifies the handler, not Discord publication.
See [Troubleshooting](troubleshooting.md) and [Command Sync](command-sync.md).

## 4. Add your own command

Inside the generated `create_bot` function, before `return bot`, add:

```python
@bot.slash(description="Say hello")
async def hello(ctx):
    await ctx.respond(f"Hello, {ctx.user.display_name}!")
```

Both offline and live instances use this factory, so they receive the same
commands. Try the new command with `easycord try bot:bot hello`, then restart
the live bot to publish it to your test server.

## 5. Add a ready-made feature

Import a built-in plugin at the top of `bot.py`:

```python
from easycord.plugins import TagsPlugin
```

Inside `create_bot`, before `return bot`, attach it:

```python
bot.add_plugin(TagsPlugin(data_dir=f"{data_dir}/tags"))
```

Passing `data_dir` keeps offline checks and tests on their own files instead of
live guild data. If you already attached `TagsPlugin()` without it, copy any existing
tag files into the new folder first, without overwriting files already there.

Use [Built-in Plugins](builtin-plugins.md) to choose features. Member and message
event plugins may require matching Discord intents in both the Developer Portal
and the bot's `discord.Intents` settings. Add a custom `Plugin` class when you
need related commands, shared state, or lifecycle hooks.

## Continue when you need more

- [Testing](testing.md): add checks using `easycord.testing.invoke`.
- [Building Commands](building-commands.md): arguments, buttons, forms, and groups.
- [Organizing Code](organizing-code.md): split features into custom plugins.
- [Database Guide](database-guide.md): persistent per-server data.
- [Request Lifecycle](request-lifecycle.md): permissions, middleware, and errors.
- [Developer Toolkit](developer-toolkit.md): inspect commands and diagnose setup.
- [AI Features](conversation-memory.md): optional providers and conversation memory.
- [All guides](README.md): configuration, localization, composition, and references.
