"""Button-based polling plugin for bots."""
from __future__ import annotations

import discord

from easycord import Plugin, slash


def _poll_options(*options: str) -> list[str]:
    return [option for option in options if option.strip()]


def _is_valid_duration(duration: int) -> bool:
    return duration >= 5


class _PollView(discord.ui.View):
    """A live poll with one vote per user. Closes after *duration* seconds."""

    def __init__(self, question: str, options: list[str], duration: int) -> None:
        super().__init__(timeout=float(duration))
        self.question = question
        self.options = options
        self.votes: dict[int, int] = {}  # user_id → option index

        self._register_buttons()

    def _register_buttons(self) -> None:
        for option_index, option in enumerate(self.options):
            self.add_item(self._make_button(option, option_index))

    def _make_button(self, label: str, option_index: int) -> discord.ui.Button:
        button = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"poll_opt_{option_index}",
        )
        button.callback = self._make_callback(option_index)
        return button

    def _make_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction) -> None:
            self.votes[interaction.user.id] = option_index
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        return callback

    def _tally(self) -> list[int]:
        counts = [0] * len(self.options)
        for idx in self.votes.values():
            counts[idx] += 1
        return counts

    def _bar(self, filled: int) -> str:
        return "█" * filled + "░" * (10 - filled)

    def _format_option_line(self, option: str, count: int, total: int) -> str:
        pct = count / total
        bar = self._bar(round(pct * 10))
        votes_str = f"{count} vote{'s' if count != 1 else ''} ({pct:.0%})"
        return f"**{option}**\n`{bar}` {votes_str}"

    def build_embed(self, *, closed: bool = False) -> discord.Embed:
        counts = self._tally()
        total = sum(counts) or 1
        lines = [
            self._format_option_line(option, count, total)
            for option, count in zip(self.options, counts)
        ]

        color = discord.Color.greyple() if closed else discord.Color.blurple()
        footer = "📊 Poll closed" if closed else f"⏱️ Closes in {self.timeout:.0f}s"
        embed = discord.Embed(
            title=f"📊 {self.question}",
            description="\n\n".join(lines),
            color=color,
        )
        embed.set_footer(text=footer)
        return embed

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore[union-attr]
        self.stop()


class PollsPlugin(Plugin):
    """Create live button-based polls that close automatically after a timeout.

    Members can vote on up to five options; each member gets exactly one vote
    (changing vote is supported). When the poll closes, the embed updates to
    show a bar-chart breakdown of results.

    Quick start::

        from easycord.plugins.polls import PollsPlugin
        bot.add_plugin(PollsPlugin())

    Slash commands registered
    -------------------------
    ``/poll`` — Create a poll. Provide a question, 2–5 options, and an optional
                duration in seconds (default 60).
    """

    @slash(description="Create a button-based poll. 2–5 options, optional duration in seconds.")
    async def poll(
        self,
        ctx,
        question: str,
        option1: str,
        option2: str,
        option3: str = "",
        option4: str = "",
        option5: str = "",
        duration: int = 60,
    ) -> None:
        options = _poll_options(option1, option2, option3, option4, option5)
        if len(options) < 2:
            await ctx.respond(ctx.t("polls.min_options", default="A poll needs at least 2 options."), ephemeral=True)
            return
        if not _is_valid_duration(duration):
            await ctx.respond(ctx.t("polls.min_duration", default="Duration must be at least 5 seconds."), ephemeral=True)
            return

        view = _PollView(question, options, duration)
        await ctx.respond(embed=view.build_embed(), view=view)

        # Block until the view times out, then update with final results.
        await view.wait()
        try:
            await ctx.edit_response(embed=view.build_embed(closed=True), view=view)
        except discord.HTTPException:
            pass  # message may have been deleted
