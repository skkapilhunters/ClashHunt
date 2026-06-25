import discord
from discord.ext import commands
from discord import app_commands

class WelcomeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 🔽 REPLACE THIS WITH YOUR ACTUAL ENTRY CHANNEL ID
        self.WELCOME_CHANNEL_ID = 123456789012345678 

    def generate_welcome_payload(self, member: discord.Member):
        """Helper function to keep the embed and content structure identical for both events."""
        content_message = f"<@{member.id}> **Read the information below**"
        
        embed_description = (
            f"Welcome {member.mention} to HUNTERS : 💎FWA💎!\n\n"
            "**If you want to check our minimum requirements, type `;reqs`**\n\n"
            "If you wish to join one of our clans please follow the steps below.\n"
            "• **Step 1**: Post your PLAYER tag.\n"
            "• **Step 2**: Post a picture of `My Profile` tab.\n"
            "• **Step 3**: Post a picture of your FWA base.\n"
            "*If you dont have a FWA base you can do `;th#` (Replace # with your townhall level)*\n"
            "• **Step 4**: Submit an application by typing `;apply`\n"
            "• **Step 5**: Wait and you will be assisted further.\n\n"
            "**Once approved, you will be moved to <#738407927425007647> where leaders of our <#738405775193407498> will post spots.**"
        )

        embed = discord.Embed(
            description=embed_description,
            color=46079 # Your original JSON decimal color
        )
        return content_message, embed

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Triggers automatically when someone joins the server."""
        channel = self.bot.get_channel(self.WELCOME_CHANNEL_ID)
        if not channel:
            return
        
        content, embed = self.generate_welcome_payload(member)
        await channel.send(content=content, embed=embed)

    @app_commands.command(name="setwelcome", description="Manually send the welcome embed for a specific user.")
    @app_commands.describe(user="The member you want to welcome")
    @app_commands.checks.has_permissions(administrator=True) # Restricts to Admins only
    async def setwelcome(self, interaction: discord.Interaction, user: discord.Member):
        """Admin-only slash command to manually trigger the message."""
        channel = self.bot.get_channel(self.WELCOME_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Welcome channel not found. Check the configuration ID.", ephemeral=True)
            return

        # Send the payload to the welcome channel
        content, embed = self.generate_welcome_payload(user)
        await channel.send(content=content, embed=embed)
        
        # Give the admin a private confirmation response so the chat doesn't get cluttered
        await interaction.response.send_message(f"✅ Welcome message sent successfully for {user.mention}!", ephemeral=True)

    @setwelcome.error
    async def setwelcome_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles error if a non-admin tries to run the command."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You do not have permission to use this command. Only Administrators can use it.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WelcomeSystem(bot))
