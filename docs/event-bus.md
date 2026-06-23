# Event Bus

`EventBus` lets plugins communicate with each other without direct imports or tight coupling. One plugin publishes a named event; any other plugin that subscribed to that name receives it.

`bot.event_bus` is created automatically — no setup needed.

---

## Quick example

```python
# levels_plugin.py
class LevelsPlugin(Plugin):
    async def _on_message(self, message):
        new_level = self._maybe_level_up(message.author.id)
        if new_level:
            await self.bot.event_bus.publish(
                "user_leveled_up",
                user_id=message.author.id,
                guild_id=message.guild.id,
                level=new_level,
            )

# rewards_plugin.py
class RewardsPlugin(Plugin):
    async def on_load(self) -> None:
        self.bot.event_bus.subscribe("user_leveled_up", self._grant_reward)

    async def _grant_reward(self, user_id: int, guild_id: int, level: int) -> None:
        if level % 10 == 0:
            await self._assign_milestone_role(guild_id, user_id, level)

    async def on_unload(self) -> None:
        self.bot.event_bus.unsubscribe("user_leveled_up", self._grant_reward)
```

---

## API

### `subscribe(event, callback)`

Register a callback for an event. Both sync and async callbacks are accepted.

```python
# Sync callback
bot.event_bus.subscribe("user_joined", lambda user_id, guild_id: ...)

# Async callback
async def on_join(user_id: int, guild_id: int) -> None:
    ...

bot.event_bus.subscribe("user_joined", on_join)
```

Raises `ValueError` if `event` is an empty string.  
Raises `TypeError` if `callback` is not callable.

### `unsubscribe(event, callback)`

Remove a previously registered callback. Safe to call even if the callback was never registered or the event has no subscribers.

```python
bot.event_bus.unsubscribe("user_joined", on_join)
```

Always call `unsubscribe` in `on_unload` to avoid stale references:

```python
async def on_unload(self) -> None:
    self.bot.event_bus.unsubscribe("user_joined", self._handler)
```

### `await publish(event, **kwargs)`

Fire an event. All subscribed callbacks are called with the provided keyword arguments.

- Sync callbacks are called directly in order of registration.
- Async callbacks are gathered concurrently via `asyncio.gather`.
- An exception in one callback does not prevent other callbacks from running — each failure is logged at ERROR and the bus continues.

```python
await bot.event_bus.publish("order_placed", order_id=42, user_id=ctx.user.id)
```

Publishing to an event with no subscribers is a no-op.

---

## Exception isolation

A crash in one subscriber will not crash the publisher or other subscribers:

```python
async def buggy_handler(user_id: int) -> None:
    raise RuntimeError("oops")

async def fine_handler(user_id: int) -> None:
    print(f"User {user_id} joined")

bot.event_bus.subscribe("user_joined", buggy_handler)
bot.event_bus.subscribe("user_joined", fine_handler)

await bot.event_bus.publish("user_joined", user_id=42)
# ERROR logged for buggy_handler, fine_handler still runs
```

---

## Event naming

Use snake_case strings that read as past-tense verbs describing what happened:

```
user_leveled_up
order_placed
plugin_config_changed
moderation_action_taken
```

Prefixing with the emitting plugin's name avoids collisions in larger bots:

```
levels.user_leveled_up
shop.order_placed
```

---

## Testing

```python
from easycord.event_bus import EventBus

async def test_reward_granted_on_level_up():
    bus = EventBus()
    granted: list[int] = []

    async def reward_handler(user_id: int, **_: object) -> None:
        granted.append(user_id)

    bus.subscribe("user_leveled_up", reward_handler)
    await bus.publish("user_leveled_up", user_id=7, guild_id=100, level=10)

    assert granted == [7]
```
