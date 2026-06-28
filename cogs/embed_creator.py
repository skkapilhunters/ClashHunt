import discord
from discord.ext import commands
import asyncio

class EmbedCreator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="makeembed", prefix="?")
    @commands.has_permissions(manage_messages=True)
    async def make_embed(self, ctx):
        """Interactive setup to create a custom embed using ?makeembed"""
        
        # Helper check function to make sure the bot only listens to the user who ran the command
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            # 1. Get Title
            await ctx.send("📝 **Step 1:** What should the **Title** of the embed be? (Type `none` to skip)")
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            title = None if msg.content.lower() == 'none' else msg.content

            # 2. Get Description
            await ctx.send("💬 **Step 2:** What should the **Description** be? (Type `none` to skip)")
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            description = None if msg.content.lower() == 'none' else msg.content

            # 3. Get Color
            await ctx.send("🎨 **Step 3:** What color should the embed sidebar be? (Enter a Hex code like `#ff0000` for Red, `#00ff00` for Green, or type `default`)")
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            
            color = discord.Color.blue() # fallback default
            if msg.content.lower() != 'default':
                try:
                    # Clean up hex string if they included a '#'
                    hex_color = msg.content.lstrip('#')
                    color = discord.Color(int(hex_color, 16))
                except ValueError:
                    await ctx.send("❌ Invalid hex code! Using default blue color instead.", delete_after=3)

            # 4. Get Thumbnail (Optional)
            await ctx.send("🖼️ **Step 4:** Provide a URL for a **Thumbnail image** (small image top right), or type `none` to skip:")
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            thumbnail = None if msg.content.lower() == 'none' else msg.content

            # 5. Build and Preview the Embed
            embed = discord.Embed(title=title, description=description, color=color)
            
            if thumbnail and (thumbnail.startswith("http://") or thumbnail.startswith("https://")):
                embed.set_thumbnail(url=thumbnail)
                
            embed.set_footer(text=f"Created by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)

            # Ask for final confirmation
            await ctx.send("👀 Here is a preview of your embed. Type `yes` to send it to this channel, or `no` to cancel.", embed=embed)
            
            confirmation = await self.bot.wait_for('message', timeout=60.0, check=check)
            if confirmation.content.lower() == 'yes':
                # Send the final embed and delete the setup conversation trail if desired
                await ctx.send(embed=embed)
                await ctx.send("✅ Embed posted successfully!", delete_after=3)
            else:
                await ctx.send("❌ Embed creation canceled.", delete_after=5)

        except asyncio.TimeoutError:
            return await ctx.send("⏰ You took too long to respond! Embed setup canceled.", delete_after=5)

    @make_embed.error
    async def embed_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need `Manage Messages` permissions to create embeds.", delete_after=5)

async def setup(bot):
    await bot.add_cog(EmbedCreator(bot))
