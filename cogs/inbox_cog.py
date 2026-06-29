# cogs/inbox_cog.py
import os
import asyncio
import discord
from discord.ext import commands
from supabase import create_client, Client

class InboxCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Initialize Supabase Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("⚠️ [Inbox Cog] Missing Supabase environment variables!")
            self.supabase: Client = None
        else:
            self.supabase: Client = create_client(supabase_url, supabase_key)

    def create_mail_embed(self, record, current_index, total_count):
        """Helper function to build a consistent mail embed."""
        sender = record.get("sender") or "Unknown Sender"
        recipient = record.get("recipient") or "Unknown Recipient"
        subject = record.get("subject") or "(No Subject)"
        
        body = record.get("body_text") or record.get("raw_body") or "No content."
        if len(body) > 1000:
            body = body[:997] + "..."

        embed = discord.Embed(
            title=f"✉️ {subject}",
            description=body,
            color=discord.Color.blue()
        )
        embed.add_field(name="From", value=sender, inline=True)
        embed.add_field(name="To", value=recipient, inline=True)
        
        attachments = record.get("attachments", [])
        if attachments and len(attachments) > 0:
            embed.add_field(name="📎 Attachments", value=f"{len(attachments)} file(s) attached", inline=False)

        # Track what number email we are viewing in the footer
        created_at = record.get("created_at", "Unknown time")
        embed.set_footer(text=f"Email {current_index + 1} of {total_count} • Received: {created_at}")
        return embed

    @commands.command(name="latest_mail", aliases=["inbox"])
    async def get_latest_mail(self, ctx):
        """Fetches the absolute newest entry from the Supabase inbox table."""
        if not self.supabase:
            return await ctx.send("❌ Supabase client is not configured properly.")

        async with ctx.typing():
            try:
                response = self.supabase.table("inbox").select("*").order("created_at", desc=True).limit(1).execute()
                if not response.data:
                    return await ctx.send("📭 The inbox database is currently empty.")
                
                embed = self.create_mail_embed(response.data[0], 0, 1)
                await ctx.send(embed=embed)
            except Exception as e:
                print(f"❌ Error: {e}")
                await ctx.send("⚠️ An error occurred while fetching data.")

    @commands.command(name="old_mails", aliases=["history", "mails"])
    async def get_old_mails(self, ctx):
        """Fetches historical emails and allows browsing via reaction buttons."""
        if not self.supabase:
            return await ctx.send("❌ Supabase client is not configured properly.")

        async with ctx.typing():
            try:
                # Fetch up to the last 20 emails ordered newest to oldest
                response = self.supabase.table("inbox").select("*").order("created_at", desc=True).limit(20).execute()
                records = response.data

                if not records:
                    return await ctx.send("📭 No historical emails found in the database.")
                
                # If there's only 1 email, just send it directly without pagination mechanics
                if len(records) == 1:
                    embed = self.create_mail_embed(records[0], 0, 1)
                    await ctx.send(embed=embed)
                    return

            except Exception as e:
                print(f"❌ Error: {e}")
                return await ctx.send("⚠️ An error occurred while fetching history.")

        # Pagination logic setup
        current_page = 0
        total_pages = len(records)
        
        # Send the first (newest) email in the list
        embed = self.create_mail_embed(records[current_page], current_page, total_pages)
        message = await ctx.send(embed=embed)

        # Add control reactions to the message
        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        # Check function to verify that only the caller can flip pages
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"] and reaction.message.id == message.id

        # Loop to handle button interactions for up to 2 minutes
        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=120.0, check=check)

                if str(reaction.emoji) == "▶️":
                    # Go backward in time (higher index = older email)
                    if current_page < total_pages - 1:
                        current_page += 1
                        new_embed = self.create_mail_embed(records[current_page], current_page, total_pages)
                        await message.edit(embed=new_embed)
                
                elif str(reaction.emoji) == "◀️":
                    # Go forward in time (lower index = newer email)
                    if current_page > 0:
                        current_page -= 1
                        new_embed = self.create_mail_embed(records[current_page], current_page, total_pages)
                        await message.edit(embed=new_embed)

                # Remove the user's reaction so they can click it again easily
                await message.remove_reaction(reaction.emoji, user)

            except asyncio.TimeoutError:
                # Clear the reactions once the 2-minute timer expires to clean up the UI
                try:
                    await message.clear_reactions()
                except discord.Forbidden:
                    pass  # Missing permissions to clear reactions
                break

async def setup(bot):
    await bot.add_cog(InboxCog(bot))
