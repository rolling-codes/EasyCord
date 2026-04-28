# Examples and patterns

These snippets are designed to be copied into a first bot project.

## Smallest starter bot

```python
from easycord import Bot

bot = Bot()

@bot.slash(description="Ping the bot.")
async def ping(ctx):
    await ctx.respond("Pong!")
```

## Command validation with ephemeral errors

```python
@bot.slash(description="Echo your message back to you.")
async def echo(ctx, message: str, times: int = 1):
    if times < 1 or times > 5:
        await ctx.respond("`times` must be between 1 and 5.", ephemeral=True)
        return
    await ctx.respond("\n".join([message] * times))
```

## Plugin structure

```python
from easycord import Bot, Plugin, slash, on

bot = Bot()

class MyPlugin(Plugin):
    @slash(description="Roll a dice")
    async def roll(self, ctx, sides: int = 6):
        import random
        await ctx.respond(str(random.randint(1, sides)))

    @on("member_join")
    async def welcome(self, member):
        await member.send("Welcome!")

bot.add_plugin(MyPlugin())
```

For the bundled example plugins, `server_commands/__init__.py` keeps the default plugin list in one place and exposes `load_default_plugins(bot)` so bot startup stays simple.

## AI assistant plugin (multi-provider)

The `AIPlugin` supports Anthropic Claude, OpenAI GPT, Google Gemini, Ollama (local), and other LLM providers. Each provider is independently optional — install only the SDK you need.

### With Anthropic Claude

```python
from easycord import Bot
from easycord.plugins import OpenClaudePlugin

bot = Bot()
bot.add_plugin(OpenClaudePlugin(api_key="sk-ant-..."))
# or use ANTHROPIC_API_KEY env var: bot.add_plugin(OpenClaudePlugin())

bot.run("YOUR_DISCORD_TOKEN")
```

Members use `/ask "your question"` to query Claude. The command is rate limited per user by default, shows a localized `openclaude.thinking` message while waiting, and edits that message with the final response.

### With OpenAI (ChatGPT/GPT-4)

```python
from easycord import Bot
from easycord.plugins import AIPlugin, OpenAIProvider

bot = Bot()
provider = OpenAIProvider(api_key="sk-...")  # or OPENAI_API_KEY env var
bot.add_plugin(AIPlugin(provider=provider))

bot.run("YOUR_DISCORD_TOKEN")
```

### With `ctx.ai(...)`

```python
from easycord import Bot
from easycord.plugins import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")
bot = Bot(ai_provider=provider)

@bot.slash(description="Ask AI")
async def ask(ctx, prompt: str):
    response = await ctx.ai(prompt, model="gpt-4o")
    await ctx.respond(response[:2000])
```

### With Google Gemini

```python
from easycord import Bot
from easycord.plugins import AIPlugin, GeminiProvider

bot = Bot()
provider = GeminiProvider(api_key="AIzaSy...")  # or GOOGLE_API_KEY env var
bot.add_plugin(AIPlugin(provider=provider))

bot.run("YOUR_DISCORD_TOKEN")
```

### With local Ollama

```python
from easycord import Bot
from easycord.plugins import AIPlugin, OllamaProvider

bot = Bot()
provider = OllamaProvider(model="llama2")  # local Ollama required
bot.add_plugin(AIPlugin(provider=provider))

bot.run("YOUR_DISCORD_TOKEN")
```

### Custom provider

Create a subclass of `AIProvider`:

```python
from easycord.plugins._ai_providers import AIProvider

class MyProvider(AIProvider):
    def _init_client(self):
        # Lazy-initialize your SDK
        pass

    def query(self, prompt: str) -> str:
        # Call your API, return response text
        pass
```

## Grouped commands

```python
from easycord import Composer, SlashGroup, slash

class ModerationGroup(SlashGroup, name="mod", description="Moderation commands"):
    @slash(description="Kick a member")
    async def kick(self, ctx, member):
        await member.kick()
        await ctx.respond(f"Kicked {member.display_name}.")

bot = Composer().add_groups(ModerationGroup()).build()
```

## Using `respond()` vs follow-ups

`Context.respond()` automatically switches to a follow-up message if you’ve already responded once. That means you can write:

```python
await ctx.respond("First response")
await ctx.respond("Second response")  # follow-up automatically
```

## Development: guild-only commands

```python
@bot.slash(description="Instant during development", guild_id=123456789012345678)
async def dev(ctx):
    await ctx.respond("Instant in one guild.")
```

