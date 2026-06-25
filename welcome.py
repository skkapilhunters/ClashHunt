import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Replace this with the actual ID of your entry/welcome text channel
        self.WELCOME_CHANNEL_ID = 1519705626022777014 

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Fetch the entry chat channel
        channel = self.bot.get_channel(self.WELCOME_CHANNEL_ID)
        if not channel:
            return

        # Dynamically injecting the new user's information into your JSON structure
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

        # Building the embed based on your JSON data
        embed = discord.Embed(
            description=embed_description,
            color=46079 # Decimal color value from your JSON
        )

        # Sending the raw content and the embed together
        await channel.send(content=content_message, embed=embed)

# This setup function allows your auto-cog loader to detect and load the file
async def setup(bot):
    await bot.add_cog(Welcome(bot))