import discord
from discord.ext import commands
import uuid
import asyncio
# Import the shared token system from your page module
from page import ACTIVE_TOKENS

# Change this to your actual Render app URL (e.g., https://clashhunt-bot.onrender.com)
RENDER_SITE_URL = "https://clashhunt.onrender.com"

class PushCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="push", prefix="?")
    @commands.has_permissions(manage_messages=True)
    async def generate_push_link(self, ctx):
        """Generates a secure, temporary web page URL to paste massive data blocks."""
        
        # Generate a high-entropy random token link
        secret_token = str(uuid.uuid4())
        
        # Register token with context details
        ACTIVE_TOKENS[secret_token] = {
            "bot": self.bot,
            "channel_id": ctx.channel.id,
            "author_id": ctx.author.id
        }
        
        one_time_url = f"{RENDER_SITE_URL}/{secret_token}"
        
        # Build an interactive embed response
        embed = discord.Embed(
            title="🔗 Secure Data Portal Generated",
            description="Since your raw data is too massive for Discord, use the link below to paste it directly into our web portal.",
            color=discord.Color.blue()
        )
        embed.add_field(name="🌐 Submission Link", value=f"[Click Here to Open Submission Portal]({one_time_url})", inline=False)
        embed.set_footer(text="⚠️ Notice: This link is single-use and expires automatically in 10 minutes.")
        
        # Send it as an ephemeral/direct notice if possible, or right in the channel
        await ctx.send(embed=embed, delete_after=600) # Auto-removes message from chat logs in 10 minutes

        # Optional auto-expiry cleaner task if they don't use it
        async def expire_token():
            await asyncio.sleep(600) # 10 minutes
            if secret_token in ACTIVE_TOKENS:
                ACTIVE_TOKENS.pop(secret_token, None)
                
        self.bot.loop.create_task(expire_token())

async def setup(bot):
    await bot.add_cog(PushCommandCog(bot))
