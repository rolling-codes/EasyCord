"""
examples/plugin_bot.py
~~~~~~~~~~~~~~~~~~~~~~
Demonstrates the EasyCord plugin system.

Each ``Plugin`` subclass groups related commands and event handlers
into a self-contained, reloadable unit.

Run:
    DISCORD_TOKEN=<token> python examples/plugin_bot.py
"""

from easycord import Bot
from server_commands import load_default_plugins

from _runtime import run_bot


def build_bot() -> Bot:
    bot = Bot()
    load_default_plugins(bot)
    return bot


def main() -> None:
    run_bot(build_bot())


if __name__ == "__main__":
    main()
