import os
from datetime import datetime, timezone
import discord
from discord import app_commands  # 👈 Added for Slash Commands
from discord.ext import commands, tasks
from pymongo import MongoClient

# 🛠️ MongoDB Configuration

COC_API_TOKEN = os.getenv("COC_API_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_player_timers = os.getenv("MONGO_player_timers")


# Target channel ID where the background loop automatically posts completed upgrades
ANNOUNCEMENT_CHANNEL_ID = 1519257143721590864  # 👈 REPLACE WITH YOUR ACTUAL CHANNEL ID

class UpgradeTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize MongoDB Client
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.collection = self.db[MONGO_player_timers]
        
        # Start the background checking loop
        self.check_upgrades_loop.start()

    def cog_unload(self):
        self.check_upgrades_loop.cancel()

    # -------------------------------------------------------------
    # 🎛️ SLASH COMMAND: /check_upgrades
    # -------------------------------------------------------------
    @app_commands.command(name="check_upgrades", description="Check and post all current player upgrades from the database right now.")
    async def check_upgrades_command(self, interaction: discord.Interaction):
        """Slash command that loops through and posts every active timer currently in MongoDB."""
        # Defer the response because sending multiple embeds might take more than 3 seconds
        await interaction.response.defer(ephemeral=True)
        
        try:
            cursor = list(self.collection.find({}))
            
            if not cursor:
                await interaction.followup.send("❌ There are no active upgrades currently tracking in the database.", ephemeral=True)
                return

            # Loop through every single tracking document and send it to the channel where command was used
            for entry in cursor:
                await self.send_upgrade_embed(interaction.channel, entry, is_forced_check=True)
                
            await interaction.followup.send(f"✅ Successfully posted all {len(cursor)} active upgrade timers to this channel!", ephemeral=True)
            
        except Exception as e:
            print(f"[Slash Command Error] Failed to complete check: {e}")
            await interaction.followup.send("❌ An error occurred while trying to fetch data from MongoDB.", ephemeral=True)

    # -------------------------------------------------------------
    # ⏰ BACKGROUND AUTOMATION LOOP
    # -------------------------------------------------------------
    @tasks.loop(minutes=1.0)
    async def check_upgrades_loop(self):
        """Background task running every minute checking only for COMPLETED upgrades."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
        if not channel:
            print(f"[Upgrade Tracker Warning] Channel ID {ANNOUNCEMENT_CHANNEL_ID} not found.")
            return

        now = datetime.now(timezone.utc)

        try:
            cursor = self.collection.find({})
            for entry in cursor:
                finish_time_str = entry.get("estimated_finish_time", "")
                if not finish_time_str:
                    continue

                try:
                    clean_time_str = finish_time_str.split("+")[0]
                    finish_dt = datetime.strptime(clean_time_str, "%Y-%m-%d %H:%M:%S.%f")
                    finish_dt = finish_dt.replace(tzinfo=timezone.utc)

                    # Auto-alert only if time has actually passed
                    if now >= finish_dt:
                        await self.send_upgrade_embed(channel, entry, is_forced_check=False)
                        self.collection.delete_one({"_id": entry["_id"]})
                        print(f"[Success] Auto-announcement sent and cleared for {entry.get('player_name')}")

                except Exception as e:
                    print(f"[Upgrade Tracker Error] Error processing entry {entry.get('id')}: {e}")
        except Exception as e:
            print(f"[Upgrade Tracker DB Error] Failed to scan collection: {e}")

    # -------------------------------------------------------------
    # 🎨 EMBED CONSTRUCTOR & SENDER
    # -------------------------------------------------------------
    async def send_upgrade_embed(self, channel, db_entry, is_forced_check=False):
        """Constructs and sends the exact Discord embed layout."""
        finish_time_str = db_entry.get("estimated_finish_time", "")
        processed_day = "Unknown"
        formatted_finish = "N/A"
        time_remaining_text = "**0 Seconds (Finished!)**"
        
        if finish_time_str:
            clean_time_str = finish_time_str.split("+")[0]
            finish_dt = datetime.strptime(clean_time_str, "%Y-%m-%d %H:%M:%S.%f")
            finish_dt = finish_dt.replace(tzinfo=timezone.utc)
            
            processed_day = finish_dt.strftime("%A") 
            formatted_finish = finish_dt.strftime("%Y-%m-%d %H:%M")

            # Dynamic countdown calculations if using the /check_upgrades manual command
            if is_forced_check:
                now = datetime.now(timezone.utc)
                if finish_dt > now:
                    diff = finish_dt - now
                    # Beautiful breakdown format: e.g., 2d 5h 12m or just seconds if tiny
                    if diff.days > 0:
                        time_remaining_text = f"**{diff.days}d {diff.seconds // 3600}h {(diff.seconds % 3600) // 60}m remaining**"
                    elif diff.seconds // 3600 > 0:
                        time_remaining_text = f"**{diff.seconds // 3600}h {(diff.seconds % 3600) // 60}m remaining**"
                    else:
                        time_remaining_text = f"**{(diff.seconds % 3600) // 60}m {diff.seconds % 60}s remaining**"

        target_lvl = db_entry.get("upgrading_to_level", "1")
        try:
            current_lvl = str(int(target_lvl) - 1)
        except ValueError:
            current_lvl = "N/A"

        # Image Fallbacks
        thumbnail_url = db_entry.get("imageurl") or "https://www.clash.ninja/images/entities/10_13.png"
        post_url = db_entry.get("posturl") or "https://clashofclans.fandom.com/wiki/Army_Camp/Home_Village"
        footer_icon = db_entry.get("typeimageurl") or "https://www.clash.ninja/images/season-perk-builder.png"

        player_name = db_entry.get("player_name", "Unknown")
        player_tag = db_entry.get("player_tag", "")
        clean_tag = player_tag.replace("#", "")

        description = (
            f"**{db_entry.get('item_name', 'Unknown Item')}**\n"
            f"**[{player_name}](https://link.clashofclans.com/en?action=OpenClanProfile&tag={clean_tag})** (`{player_tag}`)"
        )

        embed = discord.Embed(
            title=f"@{player_name.lower().replace(' ', '')}",
            description=description,
            color=3368601 
        )

        embed.set_thumbnail(url=thumbnail_url)
        embed.set_footer(text="✧ A-S-R ✧", icon_url=footer_icon)

        # Fields setup matching your UI layout perfectly
        embed.add_field(name="📌 Category", value=f"**{db_entry.get('type', 'Building')}**", inline=True)
        embed.add_field(name="**Current Level **", value=f"**{current_lvl}**", inline=True)
        embed.add_field(name="⬆ Target Level", value=f"**{target_lvl}**", inline=True)
        
        embed.add_field(name="⏳ Time Remaining", value=time_remaining_text, inline=True)
        embed.add_field(name="Processed Day", value=f"**{processed_day}**", inline=True)
        
        embed.add_field(name="Finish At", value=f"**{formatted_finish}**", inline=False)
        embed.add_field(name="Links", value=f"**Open Stats**: **[ Click Here ]({post_url})**", inline=False)

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UpgradeTracker(bot))