from easycord import Plugin, component, modal


class FeedbackPlugin(Plugin):

    @component("open_feedback")
    async def open_feedback(self, interaction):
        await interaction.ask_form("feedback_form", subject=dict(label="Subject"))

    @modal("feedback_form")
    async def handle_feedback(self, interaction, data):
        subject = data.get("subject")
        await interaction.respond(f"Feedback received: {subject}!")
