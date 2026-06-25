import os
import collections
from datetime import datetime, timezone, timedelta, time
import discord
from discord import app_commands
from discord.ext import commands, tasks
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class DailySummary(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Load environment values
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGO_DB_NAME", "clash_tracker")
        self.coll_name = os.getenv("MONGO_COLLECTION_NAME", "player_timers")
        self.channel_id = int(os.getenv("DAILY_ANNOUNCEMENT_CHANNEL_ID", "0"))

        # Mongo Connection
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.coll_name]

        # Start automatic daily tracking loop
        self.daily_report_loop.start()

    def cog_unload(self):
        self.daily_report_loop.cancel()

    def convert_to_ist(self, utc_dt_str):
        """Converts a database UTC string into an IST datetime object."""
        if not utc_dt_str:
            return None
        try:
            clean_time_str = utc_dt_str.split("+")[0]
            dt_utc = datetime.strptime(clean_time_str, "%Y-%m-%d %H:%M:%S.%f")
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            # Add 5 hours and 30 minutes for Indian Standard Time (IST)
            return dt_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
        except Exception:
            return None

    # -------------------------------------------------------------
    # 🕒 AUTOMATED SCHEDULER
    # -------------------------------------------------------------
    @tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
    async def daily_report_loop(self):
        """Fires every day to drop the automated daily update schedule."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            embed = self.build_day_embed(target_offset=0)
            if embed:
                await channel.send(content="@role", embed=embed)

    # -------------------------------------------------------------
    # 🎛️ SLASH COMMANDS: /check [day / tomorrow / week / month]
    # -------------------------------------------------------------
    @app_commands.command(name="check", description="View scheduled upgrade summaries for Day, Tomorrow, Week, or Month.")
    @app_commands.choices(scope=[
        app_commands.Choice(name="day", value="day"),
        app_commands.Choice(name="tomorrow", value="tomorrow"),
        app_commands.Choice(name="week", value="week"),
        app_commands.Choice(name="month", value="month"),
    ])
    async def check_command(self, interaction: discord.Interaction, scope: str):
        """Deduplicates, parses, and displays calendars inside your visual layouts."""
        await interaction.response.defer()

        if scope == "day":
            embed = self.build_day_embed(target_offset=0)
        elif scope == "tomorrow":
            embed = self.build_day_embed(target_offset=1)
        elif scope == "week":
            embed = self.build_week_embed()
        elif scope == "month":
            embed = self.build_month_embed()

        if not embed:
            await interaction.followup.send(f"✨ No active upgrades found matching the `{scope}` scope criteria.", ephemeral=True)
            return

        await interaction.followup.send(embed=embed)

    # -------------------------------------------------------------
    # 📅 DAY / TOMORROW EMBED GENERATOR
    # -------------------------------------------------------------
    def build_day_embed(self, target_offset=0):
        cursor = list(self.collection.find({}))
        if not cursor:
            return None

        # Calculate matching target date in IST
        now_ist = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
        target_date_ist = now_ist + timedelta(days=target_offset)
        target_day_str = target_date_ist.strftime("%Y-%m-%d")

        # Filter & Deduplicate
        unique_upgrades = {}
        for entry in cursor:
            ist_dt = self.convert_to_ist(entry.get("estimated_finish_time"))
            if ist_dt and ist_dt.strftime("%Y-%m-%d") == target_day_str:
                unique_upgrades[entry.get("id")] = entry

        if not unique_upgrades:
            return None

        title_label = "Today's Update List" if target_offset == 0 else "Tomorrow's Update List"
        embed = discord.Embed(
            title=f"✨ **{title_label}** : {target_day_str} ✨",
            description="This is List of Updates Checkout and if want full week or month then use this commands \n\n`/check day`   `/check week` `/check month`",
            color=10052095
        )
        self.apply_embed_branding(embed)

        # Group by Player
        players_map = collections.defaultdict(list)
        for item in unique_upgrades.values():
            players_map[item.get("player_tag", "UNKNOWN")].append(item)

        for p_tag, items in players_map.items():
            items.sort(key=lambda x: x.get("estimated_finish_time", ""))
            first = items[0]
            field_name = f"{first.get('player_name', 'Player')} [TH18] `{p_tag}` **[4/5]**"
            
            value_lines = []
            for idx, item in enumerate(items):
                ist_dt = self.convert_to_ist(item.get("estimated_finish_time"))
                f_time = ist_dt.strftime("%H:%M") if ist_dt else "20:33"
                emoji = "<:sub_entry_one:1519326682891288666>" if idx < len(items) - 1 else "<:sub_entry_two:1519326714679918632>"
                value_lines.append(f"{emoji}{item.get('item_name')} • {f_time}")

            embed.add_field(name=field_name, value="\n".join(value_lines), inline=False)

        return embed
# -------------------------------------------------------------
    # 🗓️ ROLLING WEEK EMBED GENERATOR (Next 7 Days from Today)
    # -------------------------------------------------------------
    def build_week_embed(self):
        cursor = list(self.collection.find({}))
        if not cursor:
            return None

        # Current time in IST
        now_ist = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
        start_date = now_ist.date()
        end_date = start_date + timedelta(days=7) # Exactly 7 days from right now

        # Group by Date Day -> Player Tag -> Upgrades List
        day_groups = collections.defaultdict(lambda: collections.defaultdict(list))
        
        for entry in cursor:
            ist_dt = self.convert_to_ist(entry.get("estimated_finish_time"))
            if ist_dt and start_date <= ist_dt.date() <= end_date:
                # Format day label nicely (e.g., "Thursday (2026-06-25)")
                day_str = ist_dt.strftime("%A (%Y-%m-%d)")
                p_tag = entry.get("player_tag", "UNKNOWN")
                day_groups[day_str][p_tag].append(entry)

        if not day_groups:
            return None

        embed = discord.Embed(
            title=f"✨ **Next 7 Days Update List** ✨",
            description="This is List of Updates Checkout and if want full week or month then use this commands \n\n`/check day`   `/check week` `/check month`",
            color=10052095
        )
        self.apply_embed_branding(embed)

        # Sort the day keys chronologically so closest days show up first
        for day_label in sorted(day_groups.keys(), key=lambda x: x.split("(")[1].replace(")", "")):
            players_data = day_groups[day_label]
            total_accounts = len(players_data)
            total_buildings = sum(len(items) for items in players_data.values())

            # Header row for that specific day
            embed.add_field(
                name=f":sparkles: **{day_label}**",
                value=f"**Total account's `{total_accounts}`  Total Building `{total_buildings}`**",
                inline=False
            )

            # Individual accounts list for that day
            for p_tag, items in players_data.items():
                items.sort(key=lambda x: x.get("estimated_finish_time", ""))
                first = items[0]
                field_name = f"{first.get('player_name', 'Player')} [TH18] `{p_tag}`"
                
                value_lines = []
                for idx, item in enumerate(items):
                    ist_dt = self.convert_to_ist(item.get("estimated_finish_time"))
                    f_time = ist_dt.strftime("%H:%M") if ist_dt else "20:33"
                    emoji = "<:sub_entry_one:1519326682891288666>" if idx < len(items) - 1 else "<:sub_entry_two:1519326714679918632>"
                    value_lines.append(f"{emoji}{item.get('item_name')} • {f_time}")

                embed.add_field(name=field_name, value="\n".join(value_lines), inline=False)

        return embed

    # -------------------------------------------------------------
    # 📅 ROLLING MONTH EMBED GENERATOR (Next 30 Days from Today)
    # -------------------------------------------------------------
    def build_month_embed(self):
        cursor = list(self.collection.find({}))
        if not cursor:
            return None

        # Current time in IST
        now_ist = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
        start_date = now_ist.date()
        end_date = start_date + timedelta(days=30) # Exactly 30 days from right now

        # Group by 7-day windows (Week 1, Week 2, etc.) relative to today
        week_groups = collections.defaultdict(lambda: collections.defaultdict(list))

        for entry in cursor:
            ist_dt = self.convert_to_ist(entry.get("estimated_finish_time"))
            if ist_dt and start_date <= ist_dt.date() <= end_date:
                # Calculate which rolling week bucket it falls into
                days_diff = (ist_dt.date() - start_date).days
                week_num = (days_diff // 7) + 1
                
                # Make sure we don't accidentally exceed Week 4/5 boundary labels
                if week_num > 4: 
                    week_num = 4
                    
                week_label = f"Week {week_num} (Next {week_num * 7} Days)"
                p_tag = entry.get("player_tag", "UNKNOWN")
                week_groups[week_label][p_tag].append(entry)

        if not week_groups:
            return None

        embed = discord.Embed(
            title=f"✨ **Next 30 Days Update List** ✨",
            description="This is List of Updates Checkout and if want full week or month then use this commands \n\n`/check day`   `/check week` `/check month`",
            color=10052095
        )
        self.apply_embed_branding(embed)

        # Build layout by sorted Week order index keys
        for week_label in sorted(week_groups.keys()):
            players_data = week_groups[week_label]
            total_accounts = len(players_data)
            total_buildings = sum(len(items) for items in players_data.values())

            # Dynamic Summary Row Subheading Header
            embed.add_field(
                name=f":sparkles: **{week_label}**",
                value=f"**Total account's `{total_accounts}`  Total Building `{total_buildings}`**",
                inline=False
            )

            # Player block summaries inside this week segment
            for p_tag, items in players_data.items():
                items.sort(key=lambda x: x.get("estimated_finish_time", ""))
                first = items[0]
                field_name = f"{first.get('player_name', 'Player')} [TH18] `{p_tag}`"
                
                value_lines = []
                for idx, item in enumerate(items):
                    ist_dt = self.convert_to_ist(item.get("estimated_finish_time"))
                    f_time = ist_dt.strftime("%H:%M") if ist_dt else "20:33"
                    emoji = "<:sub_entry_one:1519326682891288666>" if idx < len(items) - 1 else "<:sub_entry_two:1519326714679918632>"
                    value_lines.append(f"{emoji}{item.get('item_name')} • {f_time}")

                embed.add_field(name=field_name, value="\n".join(value_lines), inline=False)

        return embed
    
    def apply_embed_branding(self, embed):
        """Applies global footer timestamps and custom images seamlessly."""
        img_url = "https://media.discordapp.net/attachments/1519257143721590864/1519324369963188346/download.png"
        embed.set_thumbnail(url=img_url)
        embed.set_footer(text="✧ A-S-R ✧", icon_url=img_url)
        embed.timestamp = datetime.now(timezone.utc)

async def setup(bot):
    await bot.add_cog(DailySummary(bot))