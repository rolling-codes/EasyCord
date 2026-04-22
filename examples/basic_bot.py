"""The smallest practical EasyCord bot."""

from easycord import Bot

from _runtime import run_bot


def build_bot() -> Bot:
    bot = Bot()

    @bot.slash()
    async def ping(ctx):
        await ctx.respond("Pong!")

    @bot.slash()
    async def echo(ctx, message: str, times: int = 1):
        if times < 1 or times > 5:
            await ctx.respond("`times` must be between 1 and 5.", ephemeral=True)
            return
        await ctx.respond("\n".join([message] * times))

    return bot


def main() -> None:
    run_bot(build_bot())


if __name__ == "__main__":
    main()
