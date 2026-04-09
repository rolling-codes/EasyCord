<<<<<<< HEAD
# EasyCord 🎮

A developer-friendly Python framework for building Discord bots, built on top of [discord.py 2.x](https://discordpy.readthedocs.io/).

EasyCord keeps the full power of discord.py within reach while removing the boilerplate — decorators handle slash commands and events, a middleware chain wraps every command, and plugins let you organise code into clean, reusable modules.

---

## Installation

```bash
pip install "discord.py>=2.0"
```

Clone or copy the `easycord/` folder into your project (PyPI package coming soon).

Additional documentation lives in `docs/`:

- `docs/index.md`
- `docs/getting-started.md`
- `docs/concepts.md`
- `docs/api.md`
- `docs/examples.md`
- `docs/fork-and-expand.md`

---

## Quick Start

```python
from easycord import EasyCord
from easycord.middleware import logging_middleware

bot = EasyCord()
bot.use(logging_middleware())

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong! 🏓")

bot.run("YOUR_TOKEN")
```

Set your token via environment variable instead of hardcoding it:

```bash
DISCORD_TOKEN=your_token_here python my_bot.py
```

---

## Slash Commands

Register slash commands with `@bot.slash`.  Parameters become Discord options automatically — just use type annotations.

```python
@bot.slash(description="Say hello to someone")
async def hello(ctx, name: str, loud: bool = False):
    msg = f"Hello, {name}!"
    await ctx.respond(msg.upper() if loud else msg)
```

### Guild-only commands (instant, great for testing)

```python
@bot.slash(description="Admin test", guild_id=123456789012345678)
async def test(ctx):
    await ctx.respond("This only shows up in one server.")
```

### Context helpers

```python
async def my_command(ctx):
    ctx.user          # discord.User / Member
    ctx.guild         # discord.Guild or None (DM)
    ctx.channel       # channel object
    ctx.command_name  # "my_command"

    await ctx.respond("plain text")
    await ctx.respond("hidden", ephemeral=True)
    await ctx.respond_embed("Title", "Description", color=discord.Color.red())
    await ctx.defer()  # for slow operations — respond within 15 minutes
```

---

## Event Handling

```python
@bot.on("message")
async def handle_message(message):
    if "hello bot" in message.content.lower():
        await message.reply("Hey there!")

@bot.on("member_join")
async def welcome(member):
    await member.send(f"Welcome to {member.guild.name}!")
```

Multiple handlers for the same event are all called.

---

## Middleware

Middleware wraps every slash-command invocation.  Register with `@bot.use` or `bot.use(fn)`.

```python
@bot.use
async def my_middleware(ctx, next):
    print(f"Before /{ctx.command_name}")
    await next()          # call the next middleware / command
    print("After")
```

Middleware is executed in the order it was registered.

### Built-in middleware

```python
from easycord.middleware import (
    logging_middleware,       # log every invocation
    error_handler_middleware, # catch unhandled exceptions
    rate_limit_middleware,    # per-user rate limiting
    guild_only_middleware,    # block DM usage
)

bot.use(logging_middleware())
bot.use(error_handler_middleware(message="Something broke 💥"))
bot.use(rate_limit_middleware(max_calls=5, window_seconds=10))
bot.use(guild_only_middleware())
```

---

## Plugins

Group related commands and handlers into self-contained classes.

```python
from easycord import Plugin, slash, on

class FunPlugin(Plugin):
    """Random fun commands."""

    async def on_load(self):
        # Called once when the plugin is registered
        print("FunPlugin ready!")

    @slash(description="Roll a dice")
    async def roll(self, ctx, sides: int = 6):
        import random
        await ctx.respond(f"🎲 {random.randint(1, sides)}")

    @on("member_join")
    async def welcome(self, member):
        await member.send("Welcome!")

bot.load_plugin(FunPlugin())
```

### Unloading plugins at runtime

```python
plugin = FunPlugin()
bot.load_plugin(plugin)
# later...
await bot.unload_plugin(plugin)  # calls plugin.on_unload()
```

---

## Project Layout

```
my_bot/
├── easycord/               ← framework source
│   ├── __init__.py
│   ├── bot.py
│   ├── context.py
│   ├── decorators.py
│   ├── middleware.py
│   └── plugin.py
├── server_commands/
│   ├── fun.py
│   ├── moderation.py
│   └── info.py
├── main.py
└── requirements.txt
```

```python
# main.py
import os
from easycord import EasyCord
from easycord.middleware import logging_middleware, error_handler_middleware
from server_commands.fun import FunPlugin
from server_commands.moderation import ModerationPlugin

bot = EasyCord()
bot.use(logging_middleware())
bot.use(error_handler_middleware())

bot.load_plugin(FunPlugin())
bot.load_plugin(ModerationPlugin())

bot.run(os.environ["DISCORD_TOKEN"])
```

---

## API Reference

### `EasyCord`

| Method | Description |
|---|---|
| `bot.slash(name, *, description, guild_id)` | Decorator — register a slash command |
| `bot.on(event)` | Decorator — register an event handler |
| `bot.use(middleware)` | Register a middleware function |
| `bot.load_plugin(plugin)` | Load a `Plugin` instance |
| `await bot.unload_plugin(plugin)` | Unload a plugin at runtime |
| `bot.run(token)` | Start the bot |

### `Context`

| Attribute / Method | Description |
|---|---|
| `ctx.user` | The invoking user |
| `ctx.guild` | Guild or `None` (DM) |
| `ctx.channel` | Channel |
| `ctx.command_name` | Slash command name |
| `await ctx.respond(...)` | Send a reply |
| `await ctx.defer(...)` | Acknowledge (15-min window) |
| `await ctx.respond_embed(title, description, ...)` | Send an embed |

### `Plugin`

| Method | Description |
|---|---|
| `async on_load()` | Called when plugin is loaded |
| `async on_unload()` | Called when plugin is unloaded |
| `self.bot` | Back-reference to `EasyCord` |

---

## Creating a Bot Application

1. Go to [discord.com/developers](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, enable the intents your bot needs (e.g. "Server Members Intent" for `member_join`).
3. Under **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes, then invite the bot to your server.
4. Copy the token and run:

```bash
DISCORD_TOKEN=your_token python my_bot.py
```

> **Global slash commands** can take up to 1 hour to appear in Discord.  
> Use `guild_id=YOUR_SERVER_ID` while developing for instant updates.
=======
🚀 EasyCord
A high-level framework for discord.py that actually gets out of your way.

I built EasyCord because I was tired of fighting with boilerplate. It’s a wrapper designed to make bot development faster and a lot less frustrating by automating the repetitive API setup that usually eats up your afternoon.

💡 The Backstory
This project wasn't just a coding exercise—it was a solution to a real problem. I founded and managed the Senior IT Program Discord server for my school.

When you're running a live server for a class full of IT students, you need a bot that can scale now. I found myself spending way too much time on "plumbing"—syncing slash commands, manually handling events, and writing the same permission checks over and over.

The Fix: I decided to stop being just a user and started being an architect. I collaborated with AI tools to design a system that handles the heavy lifting automatically. EasyCord allowed me to move from a "hey, we need this feature" idea to a live, working tool for my school's community without the usual Discord API headaches.

🛠 What it actually does
1. Fast Slash Commands
No more manual syncing. EasyCord uses signature rewriting to look at your function arguments and build the Discord UI for you automatically.

Python
@bot.slash(description="Give someone temporary lab access")
async def grant_access(ctx, user: discord.Member, hours: int = 4):
    # EasyCord handles the 'user' and 'hours' types for you.
    await ctx.respond(f"Access granted to {user.display_name} for {hours}h.")
2. Clean Middleware
Stop repeating yourself. Use the middleware chain to wrap every command in a logic layer—perfect for global logging or blocking commands during maintenance.

Python
@bot.use
async def simple_logger(ctx, next):
    print(f"User {ctx.user} ran /{ctx.command_name}")
    await next() 
3. Stress-Free Config
Skip the complex database setup. The built-in ServerConfigStore lets you save server-specific settings (like role IDs or welcome channels) to simple JSON files.

📖 The Docs
I put together a full docs/ folder to make sure the transition from "cloning the repo" to "running a bot" is as seamless as possible:

getting-started.md: The quick-start guide for your first 5 minutes.

concepts.md: A look under the hood at how the middleware and plugins work.

api.md: The full technical reference for when you need to dig deep.

examples.md: Real-world patterns you can copy and paste.

fork-and-expand.md: A guide on making this project your own.

🤖 Expanding with AI (Even if you don't code)
One of the coolest things about EasyCord is that it’s AI-native. I wanted my entire IT class to be able to contribute, even the people who weren't Python experts.

Inside the repo, there is a file called model.md. It’s a "Single-Source Context Map" designed specifically for AI agents.

If you have an idea but zero coding knowledge, you can still expand this bot:

Feed the AI: Copy the text from README.md, model.md, and the docs/ folder.

The Prompt: "Hey, using the EasyCord framework, write me a new Plugin that adds a [Your Feature Idea] feature."

The framework is so modular that the AI can write a perfect Plugin file. You just drop it into the server_commands/ folder, and the bot is updated. It makes the project a living tool that anyone can help build.

📂 Layout
easycord/: The core engine logic.

docs/: The full roadmap (Getting Started, API, Examples).

server_commands/: The actual plugins I used for the Senior IT server.

model.md: The "Cheat Sheet" for expanding the bot with AI.

.easycord/: Where the bot stores your server-specific settings.
>>>>>>> f8fb69da48c9f0ca96dc173a77f2947e0067fe4e
