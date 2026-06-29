# cogs/inbox_cog.py
import os
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

    @commands.command(name="latest_mail", aliases=["inbox"])
    async def get_latest_mail(self, ctx):
        """Fetches the latest entry from the Supabase inbox table and shares it as an embed."""
        if not self.supabase:
            await ctx.send("❌ Supabase client is not configured properly.")
            return

        # Defer or trigger typing while fetching from DB
        async with ctx.typing():
            try:
                # Query the latest row sorted by 'created_at' or 'id'
                response = self.supabase.table("inbox").select("*").order("created_at", desc=True).limit(1).execute()
                
                if not response.data:
                    await ctx.send("📭 The inbox database is currently empty.")
                    return
                
                # Extract the latest record data
                record = response.data[0]
                
                sender = record.get("sender") or "Unknown Sender"
                recipient = record.get("recipient") or "Unknown Recipient"
                subject = record.get("subject") or "(No Subject)"
                # Truncate body text if it exceeds Discord's embed limits (max 4096 characters, keeping it safe at 1000)
                body = record.get("body_text") or record.get("raw_body") or "No content."
                if len(body) > 1000:
                    body = body[:997] + "..."

                # Build the beautiful Discord Embed
                embed = discord.Embed(
                    title=f"✉️ {subject}",
                    description=body,
                    color=discord.Color.blue()
                )
                
                # Add organized fields for database metadata
                embed.add_field(name="From", value=sender, inline=True)
                embed.add_field(name="To", value=recipient, inline=True)
                
                # Format attachments info if present
                attachments = record.get("attachments", [])
                if attachments and len(attachments) > 0:
                    embed.add_field(name="📎 Attachments", value=f"{len(attachments)} file(s) attached", inline=False)

                # Add timestamp footer
                if record.get("created_at"):
                    embed.set_footer(text=f"Received at • {record['created_at']}")

                # Send it!
                await ctx.send(embed=embed)

            except Exception as e:
                print(f"❌ Error fetching from Supabase: {e}")
                await ctx.send("⚠️ An error occurred while fetching data from the database.")

async def setup(bot):
    await bot.add_cog(InboxCog(bot))
