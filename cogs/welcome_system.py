import discord
from discord.ext import commands
from discord import app_commands

class WelcomeSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 🔽 REPLACE THIS WITH YOUR ACTUAL ENTRY CHANNEL ID
        self.WELCOME_CHANNEL_ID = 1519705626022777014 

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
        # Wait until the bot cache is fully ready
        await self.bot.wait_until_ready()
        
        channel = self.bot.get_channel(self.WELCOME_CHANNEL_ID)
        if not channel:
            print(f"[Welcome Error] Could not find channel with ID {self.WELCOME_CHANNEL_ID}")
            return
        
        try:
            content, embed = self.generate_welcome_payload(member)
            await channel.send(content=content, embed=embed)
            print(f"[Welcome System] Automatically welcomed {member.name} successfully.")
        except Exception as e:
            print(f"[Welcome System Error] Failed to auto-send message: {e}")

    # 🔥 Hides the command completely from regular users in the Discord UI menu
    @app_commands.command(name="setwelcome", description="Manually send the welcome embed for a specific user.")
    @app_commands.describe(user="The member you want to welcome")
    @app_commands.default_permissions(administrator=True) 
    @app_commands.guild_only() # Prevents users from trying to run it in bot DMs
    async def setwelcome(self, interaction: discord.Interaction, user: discord.Member):
        """Admin-only slash command to manually trigger the message."""
        await interaction.response.defer(ephemeral=True)
        
        channel = self.bot.get_channel(self.WELCOME_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("❌ Welcome channel not found. Check the configuration ID.", ephemeral=True)
            return

        try:
            # Send the payload to the welcome channel
            content, embed = self.generate_welcome_payload(user)
            await channel.send(content=content, embed=embed)
            
            # Give the admin a private confirmation response
            await interaction.followup.send(f"✅ Welcome message sent successfully for {user.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to send welcome payload: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeSystem(bot))
    print("[Module Loader] welcome_system cog loaded successfully.")
