import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone

class ChannelCleaner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 1st Command: Clean on a DAYS basis
    @commands.command(name="cleandays", prefix="?")
    @commands.has_permissions(manage_messages=True)
    async def clean_days(self, ctx, days: int):
        """Deletes messages older than a certain number of days. Usage: ?cleandays 7"""
        if days <= 0:
            await ctx.send("Please provide a number of days greater than 0.", delete_after=5)
            return

        # Calculate the cutoff date (timezone-aware to prevent issues)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        await ctx.send(f"Scanning and cleaning messages older than {days} days...", delete_after=5)
        
        # Check function to filter messages older than the cutoff
        def is_older(msg):
            return msg.created_at < cutoff_date

        try:
            # Note: bulk delete won't work on messages older than 14 days due to Discord's API limits
            deleted = await ctx.channel.purge(before=cutoff_date, limit=None)
            await ctx.send(f"✨ Successfully cleaned **{len(deleted)}** messages older than {days} days!", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {e}", delete_after=5)

    # 2nd Command: Clean on a MESSAGE COUNT basis
    @commands.command(name="cleanmsg", prefix="?")
    @commands.has_permissions(manage_messages=True)
    async def clean_messages(self, ctx, amount: int):
        """Deletes a specific number of messages. Usage: ?cleanmsg 50"""
        if amount <= 0:
            await ctx.send("Please provide a message count greater than 0.", delete_after=5)
            return

        # Plus 1 to include the command message itself
        actual_amount = amount + 1 
        
        try:
            deleted = await ctx.channel.purge(limit=actual_amount)
            # Subtract 1 from final message so the user sees the exact amount they requested
            await ctx.send(f"✨ Successfully deleted **{len(deleted) - 1}** messages!", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {e}", delete_after=5)

    # Error handling for missing permissions or arguments
    @clean_days.error
    @clean_messages.error
    async def clear_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission (`Manage Messages`) to use this command.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Please specify a number. (e.g., `?cleanmsg 10` or `?cleandays 3`)", delete_after=5)

async def setup(bot):
    await bot.add_cog(ChannelCleaner(bot))
