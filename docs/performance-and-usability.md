# Performance and usability guide

This guide focuses on practical ways to make EasyCord bots feel faster for end users and easier to maintain for developers.

## 1) Keep interaction latency low

Discord interactions should be acknowledged quickly. If a command may take more than ~1–2 seconds, defer first and then send follow-up output.

```python
@bot.slash(description="Generate a long report")
async def report(ctx):
    await ctx.defer(ephemeral=True)
    data = await build_report()
    await ctx.respond(f"Done: {data.summary}")
```

### Why this helps

- Users see immediate feedback.
- You avoid interaction timeout failures.
- Heavy work can run without blocking response acknowledgement.

## 2) Prefer guild-scoped commands during development

Use `guild_id` while iterating so command updates appear instantly.

```python
@bot.slash(description="Dev command", guild_id=123456789012345678)
async def dev_ping(ctx):
    await ctx.respond("Updated instantly in this guild.")
```

Switch to global commands when releasing.

## 3) Move cross-cutting logic into middleware

If you repeatedly write checks (permissions, logging, rate limiting), implement them once as middleware.

```python
from easycord.middleware import log_middleware, catch_errors, rate_limit

bot.use(log_middleware())
bot.use(catch_errors())
bot.use(rate_limit(limit=10, window=30))
```

### Why this helps

- Less repeated code per command.
- Consistent behavior across your bot.
- Lower maintenance overhead as your command count grows.

## 4) Use plugins for feature boundaries

Group related commands/events into plugins (e.g., moderation, onboarding, fun).

Benefits:

- Better discoverability for contributors.
- Easier testing and lifecycle management.
- Cleaner command namespacing for UI interactions.

## 5) Keep handlers thin

A good pattern:

- Handler: parse input + call service function.
- Service layer: business logic.
- Framework surface (`ctx`): response and platform operations.

This makes command behavior easier to test and reason about.

## 6) Use cooldowns and rate limits intentionally

- Command-level cooldowns (`cooldown=...`) protect expensive commands.
- Global middleware `rate_limit(...)` controls burst abuse across commands.

Combine both when commands involve external APIs or intensive work.

## 7) Add observability early

At minimum:

- Log command name and user ID.
- Log failures with stack traces.
- Measure median and p95 command duration.

This quickly shows where users experience slowness.

## 8) Build for intuitive UX

Use these defaults:

- Clear command descriptions (`@bot.slash(description="...")`).
- Type annotations for parameter validation.
- Helpful ephemeral errors for permission and validation failures.
- Static `choices` when input options are fixed.

Small UX improvements reduce support requests and mistaken command usage.

## Suggested rollout checklist

1. Enable `catch_errors()` and logging middleware.
2. Add cooldowns to expensive commands.
3. Convert repeated command boilerplate into middleware.
4. Split large command files into plugins by domain.
5. Track latency for top 5 most-used commands.
