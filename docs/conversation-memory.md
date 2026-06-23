# Conversation Memory

EasyCord can track multi-turn conversation history per user, per guild. When enabled, `ctx.ai()` automatically reads and writes to this store so the AI has context across multiple command invocations.

---

## `ctx.ai()` — one-shot AI call

The simplest way to call your configured AI provider from a command:

```python
async def ai(prompt: str, *, provider=None, model: str | None = None) -> str
```

```python
from easycord import Bot, Plugin, slash
from easycord.plugins import AnthropicProvider

bot = Bot(
    ai_provider=AnthropicProvider(api_key="sk-…"),
)

class AskPlugin(Plugin):

    @slash(description="Ask the AI anything")
    async def ask(self, ctx, question: str):
        await ctx.defer()
        answer = await ctx.ai(question)
        await ctx.respond(answer)
```

If `Bot(conversation_memory=…)` is set, `ctx.ai()` automatically logs both the prompt and the response into the user's conversation history before returning.

Pass `model=` to override the provider's default model for a single call:

```python
answer = await ctx.ai(question, model="claude-opus-4-8")
```

`ctx.ai()` raises `RuntimeError` if no provider is configured. Check `Bot(ai_provider=…)` is set before calling it.

### `ctx.ai()` vs `Orchestrator.run()`

| | `ctx.ai()` | `Orchestrator.run()` |
|---|---|---|
| Use case | Single-turn Q&A | Tool-calling loops, agents |
| Memory | Auto if configured | Manual |
| Tools | No | Yes (`@ai_tool`) |
| Overhead | Low | Higher |

Use `ctx.ai()` for straightforward "answer this question" commands. Use `Orchestrator` when the AI needs to call tools, search a database, or iterate.

---

## Setting up memory

Pass a `ConversationMemory` instance to `Bot`:

```python
from easycord import Bot
from easycord.conversation_memory import ConversationMemory

bot = Bot(
    ai_provider=provider,
    conversation_memory=ConversationMemory(
        max_conversations=1000,
        default_max_turns=20,
        default_max_age_minutes=60,
    ),
)
```

That's it — `ctx.ai()` picks it up automatically. Users get a fresh conversation once their history expires.

---

## `ConversationMemory` parameters

```python
ConversationMemory(
    max_conversations: int = 1000,
    default_max_turns: int = 20,
    default_max_age_minutes: int = 60,
    summary_on_eviction: bool = False,
    summary_fn: Callable[[list[ConversationTurn]], str] | None = None,
)
```

| Parameter | Description |
|---|---|
| `max_conversations` | Cap on concurrent tracked conversations. Oldest (by `last_updated`) are evicted when exceeded |
| `default_max_turns` | Per-conversation turn limit. Oldest turns drop when exceeded |
| `default_max_age_minutes` | Conversations are considered expired after this many minutes of inactivity |
| `summary_on_eviction` | When `True`, evicted turns are compressed into a summary turn instead of deleted |
| `summary_fn` | Callable that receives evicted `ConversationTurn` objects and returns a summary string |

---

## Eviction and summaries

When a conversation exceeds `default_max_turns`, the oldest turns are dropped. With `summary_on_eviction=True` and a `summary_fn`, they're compressed instead:

```python
def summarize(turns):
    lines = [f"{t.role}: {t.content[:80]}" for t in turns]
    return "Earlier: " + " | ".join(lines)

memory = ConversationMemory(
    default_max_turns=10,
    summary_on_eviction=True,
    summary_fn=summarize,
)
```

The summary is inserted as a `"system"` role turn with a `"TL;DR: "` prefix, so the AI retains context about earlier exchanges without the full token cost.

---

## Reading history manually

`ctx.conversation_history()` returns the user's current turns without modifying them:

```python
async def conversation_history(limit: int | None = None) -> list[ConversationTurn]
```

```python
@slash(description="Show recent conversation")
async def history(self, ctx):
    turns = await ctx.conversation_history(limit=5)
    if not turns:
        await ctx.respond("No conversation history yet.")
        return
    lines = [f"**{t.role}**: {t.content[:100]}" for t in turns]
    await ctx.respond("\n".join(lines), ephemeral=True)
```

Returns an empty list if memory is not configured or the user has no history.

---

## Managing memory directly

The `ConversationMemory` API is available at `bot.conversation_memory`:

```python
# Add turns manually (ctx.ai() does this automatically)
bot.conversation_memory.add_user_message(user_id, "Hello")
bot.conversation_memory.add_assistant_message(user_id, "Hi there!")

# Get messages in provider format
messages = bot.conversation_memory.get_messages(user_id)
# → [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]

# Clear one user's history
bot.conversation_memory.clear(user_id, guild_id=ctx.guild.id)

# Get memory stats
stats = bot.conversation_memory.get_stats()
# → {"total_conversations": 42, "max_conversations": 1000, "total_turns": 318, ...}
```

---

## Periodic cleanup

Expired conversations are pruned automatically whenever `get_or_create()` is called (which `ctx.ai()` triggers). For very high-traffic bots you may want to run cleanup on a schedule:

```python
class MemoryPlugin(Plugin):

    @task(hours=1)
    async def prune_memory(self):
        removed = self.bot.conversation_memory.cleanup_expired()
        if removed:
            import logging
            logging.getLogger(__name__).info("Pruned %d expired conversations", removed)
```

---

## Testing

```python
from easycord.conversation_memory import ConversationMemory

def test_memory_adds_and_retrieves():
    mem = ConversationMemory(default_max_turns=5)
    mem.add_user_message(42, "Hello")
    mem.add_assistant_message(42, "Hi!")

    messages = mem.get_messages(42)
    assert messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]

def test_memory_evicts_oldest_on_overflow():
    mem = ConversationMemory(default_max_turns=2)
    mem.add_user_message(1, "A")
    mem.add_assistant_message(1, "B")
    mem.add_user_message(1, "C")

    msgs = mem.get_messages(1)
    assert len(msgs) == 2
    assert msgs[0]["content"] == "B"
```
