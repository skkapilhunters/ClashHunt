import discord
from discord import app_commands
from discord.ext import commands
# Import your existing function from local_logger.py
from local_logger import save_to_history

# Define the Interactive Pop-Up Window (Modal)
class PushDataModal(discord.ui.Modal, title="Push Player Timers Data"):
    # The large multi-line text input field where you paste the JSON string
    json_input = discord.ui.TextInput(
        label="Paste Raw Data String",
        style=discord.TextStyle.long,
        placeholder="Paste the raw JSON data containing tags and timers here...",
        required=True,
        max_length=4000 # Discord text input limit
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Acknowledge the interaction immediately to prevent timeouts
        await interaction.response.defer(ephemeral=True)
        
        raw_string = self.json_input.value
        
        try:
            # Send the text to your working local_logger logic
            save_to_history(raw_string)
            await interaction.followup.send("✅ Data processed! Local files updated and synchronized with MongoDB.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to process data: {e}", ephemeral=True)

# Define the Cog containing the Slash Command
class PushCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Listen for when the bot is ready to sync slash commands to Discord globally
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            # Syncs slash commands globally so you can see them across servers
            await self.bot.tree.sync()
            print("[System] Slash commands synced successfully.")
        except Exception as e:
            print(f"[System Error] Failed to sync slash commands: {e}")

    # The actual slash command definition
    @app_commands.command(name="push", description="Open a text box window to submit raw player data directly to MongoDB.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def push_data(self, interaction: discord.Interaction):
        # Open the modal directly on the user's screen
        await interaction.response.send_modal(PushDataModal())

async def setup(bot):
    await bot.add_cog(PushCommandCog(bot))
