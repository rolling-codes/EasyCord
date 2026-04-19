from easycord import Plugin, component, modal

class FeedbackPlugin(Plugin):

    @component("open_feedback")
    async def open_feedback(self, interaction):
        # Present the modal to the user
        await interaction.ask_form("feedback_form", subject=dict(label="Subject"))

    @modal("feedback_form")
    async def handle_feedback(self, interaction, data):
        # Extract the data directly from the parsed data dict
        subject = data.get("subject")
        await interaction.respond(f"Feedback received: {subject}!")
