"""
hot-reload-dev-bot.py — demonstrates EasyCord's hot-reload development mode.

Demonstrates:
  - Plugin state that survives across commands (in-process counter)
  - on_reload lifecycle hook that fires whenever a plugin file is saved
  - Bot started with reload=True so file changes apply without restarting

Run:
    DISCORD_TOKEN=... python examples/hot-reload-dev-bot.py

Try editing CounterPlugin and saving the file — the bot reloads it without restarting.
"""

import os
from easycord import Bot, Plugin, slash


# ── Plugin: live-editable counter ─────────────────────────────────────────────

class CounterPlugin(Plugin):
    """A simple counter that resets on reload — edit this class and save to see it."""

    def __init__(self):
        super().__init__()
        self.count = 0

    @slash(description="Increment and show counter")
    async def count_up(self, ctx):
        self.count += 1
        await ctx.respond(f"Count is now **{self.count}**.")

    async def on_reload(self):
        print("[CounterPlugin] Reloaded! Counter reset.")


# ── Bot setup ─────────────────────────────────────────────────────────────────

bot = Bot(
    auto_sync=False,  # dev mode — avoid rate limits during reload testing
)

bot.add_plugin(CounterPlugin())


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN environment variable before running.")
    bot.run(token, reload=True)  # Edit CounterPlugin above and save — changes reload automatically
