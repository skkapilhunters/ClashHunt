import os
import re
import asyncio
import discord
from discord.ext import commands
from supabase import create_client, Client

class MailLinkButton(discord.ui.View):
    """Adds a dynamic link button below the embed targeting your dashboard."""
    def __init__(self, record_id):
        super().__init__()
        # Replace this URL with your actual website base path
        dashboard_url = f"https://mail.admin.com/view?id={record_id}"
        self.add_item(discord.ui.Button(
            label="View Complete Mail", 
            url=dashboard_url, 
            style=discord.ButtonStyle.link,
            emoji="🔗"
        ))

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
        """Builds an optimized, premium layout matching the user template with conditional OTP fields."""
        sender_name = record.get("sender_name") or "Sender's Name"
        sender_mail = record.get("sender_mail") or record.get("sender") or "info@mail.admin.com"
        recipient = record.get("recipient") or record.get("to") or "beta@mail.admin.com"
        subject = record.get("subject") or "(No Subject)"
        
        body = record.get("body_text") or record.get("raw_body") or "No content."
        
        # 1. Scanning and isolating an OTP code dynamically
        # Looks for standard 4-8 digit numeric codes inside the text
        otp_match = re.search(r'\b\d{4,8}\b', body) or re.search(r'\b\d{4,8}\b', subject)
        otp_code = otp_match.group(0) if otp_match else None

        # Truncate content body to safeguard Discord payload character limits
        if len(body) > 1000:
            body = body[:997] + "..."

        # 2. Replicating the user's signature visual styles
        embed = discord.Embed(
            title=f"✨ **Todays Mail** : {record.get('created_at', '2026-06-29')[:10]} ✨",
            color=10052095 # Matching user palette color decimal
        )
        
        # Static asset setup using your custom template icons
        icon_url = "https://media.discordapp.net/attachments/1519257143721590864/1519324369963188346/download.png"
        embed.set_thumbnail(url=icon_url)

        # Structure field lines perfectly
        embed.add_field(name="From", value=sender_name, inline=True)
        embed.add_field(name="Sender Mail", value=sender_mail, inline=True)
        embed.add_field(name="To", value=recipient, inline=False)
        
        # Conditional Logic: Only append OTP area if an explicit target is matched
        if otp_code:
            embed.add_field(name="OTP (Tap to Copy)", value=f"`{otp_code}`", inline=False)

        embed.add_field(name="Content", value=body, inline=False)
        
        # Parsing attachment links cleanly
        attachments = record.get("attachments", [])
        if attachments and len(attachments) > 0:
            attach_str = ""
            for i, att in enumerate(attachments[:2]): # Cap preview text strings to 2
                emoji = "<:sub_entry_one:1519326682891288666>" if i == 0 else "<:sub_entry_two:1519326714679918632>"
                url = att.get("url", "https://mail.admin.com")
                name = att.get("name", f"Attachment {i+1}")
                attach_str += f"{emoji} **{name}** : **[Click Here ]({url})**\n"
            embed.add_field(name="Attachments :", value=attach_str, inline=False)

        # Track history details inside the footer template
        embed.set_footer(
            text=f"✧ Mail12599 ✧ Email {current_index + 1} of {total_count}",
            icon_url=icon_url
        )
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
                
                record = response.data[0]
                embed = self.create_mail_embed(record, 0, 1)
                
                # Attach modern Action Row components directly via discord.py
                view = MailLinkButton(record_id=record.get("id", "0"))
                
                await ctx.send(content=f"**Subject : {record.get('subject', 'Test with data')}**", embed=embed, view=view)
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
                response = self.supabase.table("inbox").select("*").order("created_at", desc=True).limit(20).execute()
                records = response.data

                if not records:
                    return await ctx.send("📭 No historical emails found in the database.")
                
                if len(records) == 1:
                    embed = self.create_mail_embed(records[0], 0, 1)
                    view = MailLinkButton(record_id=records[0].get("id", "0"))
                    await ctx.send(content=f"**Subject : {records[0].get('subject')}**", embed=embed, view=view)
                    return

            except Exception as e:
                print(f"❌ Error: {e}")
                return await ctx.send("⚠️ An error occurred while fetching history.")

        current_page = 0
        total_pages = len(records)
        
        embed = self.create_mail_embed(records[current_page], current_page, total_pages)
        view = MailLinkButton(record_id=records[current_page].get("id", "0"))
        message = await ctx.send(content=f"**Subject : {records[current_page].get('subject')}**", embed=embed, view=view)

        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"] and reaction.message.id == message.id

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=120.0, check=check)

                if str(reaction.emoji) == "▶️" and current_page < total_pages - 1:
                    current_page += 1
                elif str(reaction.emoji) == "◀️" and current_page > 0:
                    current_page -= 1
                else:
                    await message.remove_reaction(reaction.emoji, user)
                    continue

                new_embed = self.create_mail_embed(records[current_page], current_page, total_pages)
                new_view = MailLinkButton(record_id=records[current_page].get("id", "0"))
                await message.edit(content=f"**Subject : {records[current_page].get('subject')}**", embed=new_embed, view=new_view)
                await message.remove_reaction(reaction.emoji, user)

            except asyncio.TimeoutError:
                try:
                    await message.clear_reactions()
                except discord.Forbidden:
                    pass
                break

async def setup(bot):
    await bot.add_cog(InboxCog(bot))
