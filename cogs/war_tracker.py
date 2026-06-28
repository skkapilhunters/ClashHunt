import asyncio
import discord  # type: ignore
from discord.ext import tasks, commands  # type: ignore
from discord import app_commands  # type: ignore
import aiohttp # type: ignore
import os
from datetime import datetime, timezone
from dotenv import load_dotenv  # type: ignore
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from modules.scraper import scrape_fwa_details

# Import the shared bot instance safely from your standalone file
from bot_instance import bot

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
BASE_GATEWAY = "https://clash-hunt-api.vercel.app/proxy"

# --- AUTOCOMPLETE DROPDOWN FILTER (SERVER SCOPED) ---
async def clan_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Generates dropdown options showing ONLY clans registered in the current server."""
    if not interaction.guild_id:
        return []
        
    cog = interaction.client.get_cog("WarTracker")
    if not cog:
        return []
        
    guild_clans = await cog.db_get_guild_clans(interaction.guild_id)
    choices = []
    
    for tag, details in guild_clans.items():
        display_name = f"{details['clan_name']} ({tag})"
        if current.lower() in display_name.lower():
            choices.append(app_commands.Choice(name=display_name, value=tag))
            
    return choices[:25]


class WarTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mongo_client = None
        self.db = None
        self.clans_collection = None
        
        # Safely trigger database and background task setup loops
        self.init_mongodb()

    # --- DATABASE MANAGEMENT FUNCTIONS ---
    def init_mongodb(self):
        """Initializes the MongoDB connection client."""
        if not MONGO_URI:
            print("[Critical Error] MONGO_URI is missing from your .env file!")
            return False
        
        self.mongo_client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.mongo_client["ClashHunt"]
        self.clans_collection = self.db["tracked_clans"]
        print("[Database] WarTracker successfully connected to MongoDB Cluster.")
        
        # Start the task loop right after successful initialization
        if not self.check_clan_war_loop.is_running():
            self.check_clan_war_loop.start()
        return True

    async def db_add_clan(self, tag, name, channel_id, guild_id):
        # We also initialize last_match_id as None for brand new tracks
        await self.clans_collection.update_one(
            {"clan_tag": tag, "guild_id": guild_id},
            {"$set": {"clan_name": name, "channel_id": channel_id}, "$setOnInsert": {"last_match_id": None}},
            upsert=True
        )

    async def db_update_last_match(self, tag, guild_id, match_id):
        """Updates the stored match ID state permanently in the database."""
        await self.clans_collection.update_one(
            {"clan_tag": tag, "guild_id": guild_id},
            {"$set": {"last_match_id": match_id}}
        )

    async def db_remove_clan(self, tag, guild_id):
        await self.clans_collection.delete_one({"clan_tag": tag, "guild_id": guild_id})

    async def db_get_guild_clans(self, guild_id):
        cursor = self.clans_collection.find({"guild_id": guild_id})
        clans = await cursor.to_list(length=100)
        
        clans_data = {}
        for c in clans:
            clans_data[c["clan_tag"]] = {"clan_name": c["clan_name"], "channel_id": c["channel_id"]}
        return clans_data

    async def db_get_all_global_clans(self):
        cursor = self.clans_collection.find({})
        return await cursor.to_list(length=1000)

    # --- COC DATA PARSERS ---
    def parse_coc_date(self, date_str):
        if not date_str: return None
        try:
            clean_str = date_str.replace(".000Z", "")
            dt = datetime.strptime(clean_str, "%Y%m%dT%H%M%S")
            return dt.replace(tzinfo=timezone.utc)
        except Exception: return None

    def get_th_composition(self, members):
        counts = {}
        for member in members:
            th = member.get('townhallLevel') or member.get('townHallLevel')
            if th: counts[th] = counts.get(th, 0) + 1
        
        sorted_th = sorted(counts.keys(), reverse=True)
        comp_strings = []
        for th in sorted_th:
            if th >= 12: comp_strings.append(f":th{th}: `{counts[th]}`")
            else: comp_strings.append(f"TH{th} `{counts[th]}`")
        return " ".join(comp_strings) if comp_strings else "No data"

    async def generate_war_embed(self, clan_tag):
        clean_tag = f"#{clan_tag.upper().replace('#', '').strip()}"
        
        params = {
            "endpoint": "clans",
            "tag": clean_tag,
            "suffix": "currentwar"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_GATEWAY, params=params) as response:
                if response.status != 200:
                    return None, None, f"Proxy Error (Status: {response.status})"
                war_data = await response.json()

        if war_data.get('state') == 'notInWar':
            return None, "notInWar", None

        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        state = war_data.get('state')
        match_id = f"{opponent.get('tag')}-{state}"

        print(f"[Main Bot] Scraping FWA metrics for {clean_tag}...")
        fwa_metrics = await asyncio.to_thread(scrape_fwa_details, clean_tag)

        end_time = self.parse_coc_date(war_data.get('endTime'))
        time_left_text = "Unknown"
        if end_time:
            now = datetime.now(timezone.utc)
            delta = end_time - now
            total_hours = int(delta.total_seconds() // 3600)
            days = total_hours // 24
            hours = total_hours % 24
            time_left_text = f"{days}d {hours}h" if days > 0 else f"{hours}h"

        our_comp = self.get_th_composition(clan.get('members', []))
        enemy_comp = self.get_th_composition(opponent.get('members', []))
        clean_our_tag = clan.get('tag', '').replace('#', '')
        clean_enemy_tag = opponent.get('tag', '').replace('#', '')

        embed = discord.Embed(description="<@&1500908965196730480>", color=3368601)
        badge_url = clan.get('badgeUrls', {}).get('medium', "https://api-assets.clashofclans.com/badges/200/GZm0ep4Lp9-5woM7I6P2DD61PIzuMuT2Jk3EeZbpKVc.png")
        embed.set_thumbnail(url=badge_url)

        field_title = f"{clan.get('name')} vs {opponent.get('name')}"
        field_value = (
            f"**[{clan.get('name')}](https://link.clashofclans.com/en?action=OpenClanProfile&tag={clean_our_tag})** (`{clan.get('tag')}`) **VS** "
            f"**[{opponent.get('name')}](https://link.clashofclans.com/en?action=OpenClanProfile&tag={clean_enemy_tag})** (`{opponent.get('tag')}`)\n\n"
            f"**Match Type:** {fwa_metrics['match_type']}\n"
            f"**Sync Number:** #{fwa_metrics['sync_num']}\n"
            f"**War ID:** #{fwa_metrics['war_id']}\n"
            f"**Team Size:** {war_data.get('teamSize')} vs {war_data.get('teamSize')}\n"
            f"**Ends in:** {time_left_text}\n\n"
            f"**Points Balance:** {fwa_metrics['point_balance']}\n\n"
            f"**CC Link:** [Link](https://link.clashofclans.com/en?action=OpenClanProfile&tag={clean_our_tag})\n"
            f"**Points Check:** [Check](https://points.fwafarm.com/clan?tag={clean_our_tag})\n\n"
            f"**{clan.get('name')} Composition**\n{our_comp}\n\n"
            f"**{opponent.get('name')} Composition**\n{enemy_comp}"
        )

        embed.add_field(name=field_title, value=field_value, inline=False)
        return embed, match_id, None

    # --- SERVER-AWARE BACKGROUND TASK LOOP (Optimized for 10 Min & DB Persistence) ---
    @tasks.loop(minutes=10)
    async def check_clan_war_loop(self):
        await self.bot.wait_until_ready()
        all_tracked_entries = await self.db_get_all_global_clans()
        if not all_tracked_entries: return

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loop handling {len(all_tracked_entries)} total database tracks...")

        for document in all_tracked_entries:
            tag = document["clan_tag"]
            guild_id = document["guild_id"]
            channel_id = document["channel_id"]
            last_match_id = document.get("last_match_id") # Grab the last match record from database
            
            channel = self.bot.get_channel(channel_id)
            if not channel: continue

            try:
                embed, match_id, error = await self.generate_war_embed(tag)
                
                # Handling errors or when clan is completely out of war
                if error or match_id == "notInWar":
                    if last_match_id != "notInWar":
                        await self.db_update_last_match(tag, guild_id, "notInWar")
                    continue

                # 🔥 DB INTEGRITY CHECK: If match matches the stored persistent database code, SKIP!
                if last_match_id == match_id:
                    continue

                # If it's a completely new match identifier or update, send the alert message
                await channel.send(embed=embed)
                print(f"[Loop Success] Permanent DB match change posted for {tag} on Guild: {guild_id}")
                
                # Instantly save state to database so reboots do not send it again
                await self.db_update_last_match(tag, guild_id, match_id)

            except Exception as e:
                print(f"[Loop Exception] Tracking error on {tag} for guild {guild_id}: {e}")
            
            await asyncio.sleep(2)

    def cog_unload(self):
        """Safely stops task dependencies when cog unloads."""
        self.check_clan_war_loop.cancel()

    # --- APPLICATION COG SLASH COMMANDS ---

    @app_commands.command(name="addclan", description="Register a new clan to be tracked automatically in this server channel.")
    @app_commands.describe(clan_tag="The unique in-game tag of your clan (e.g., #2RLGQ2L9L)")
    async def addclan(self, interaction: discord.Interaction, clan_tag: str):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be executed within a server guild.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        formatted_tag = f"#{clan_tag.upper().replace('#', '').strip()}"
        
        guild_clans = await self.db_get_guild_clans(interaction.guild_id)
        if formatted_tag in guild_clans:
            await interaction.followup.send(f"⚠️ `{formatted_tag}` is already tracked in <#{guild_clans[formatted_tag]['channel_id']}> on this server.")
            return

        params = {
            "endpoint": "clans",
            "tag": formatted_tag,
            "suffix": ""
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_GATEWAY, params=params) as response:
                if response.status != 200:
                    await interaction.followup.send("❌ Registration rejected. Please check the clan tag.")
                    return
                data = await response.json()
                clan_name = data.get("name", "Unknown Clan")

        await self.db_add_clan(formatted_tag, clan_name, interaction.channel_id, interaction.guild_id)
        await interaction.followup.send(f"✅ MongoDB Entry Saved! **{clan_name}** (`{formatted_tag}`) is now tracked for this server.")

    @app_commands.command(name="removeclan", description="Stop auto-tracking a specific clan tag in this server.")
    @app_commands.autocomplete(clan_tag=clan_autocomplete)
    @app_commands.describe(clan_tag="Choose which clan to clear from this server's records.")
    async def removeclan(self, interaction: discord.Interaction, clan_tag: str):
        if not interaction.guild_id: return
        
        guild_clans = await self.db_get_guild_clans(interaction.guild_id)
        formatted_tag = clan_tag.upper().strip()

        if formatted_tag not in guild_clans:
            await interaction.response.send_message("❌ That clan is not tracked on this server layout.", ephemeral=True)
            return

        name = guild_clans[formatted_tag]["clan_name"]
        await self.db_remove_clan(formatted_tag, interaction.guild_id)
        await interaction.response.send_message(f"🗑️ Wiped server logging records for **{name}** (`{formatted_tag}`).", ephemeral=True)

    @app_commands.command(name="listclans", description="Show clans currently tracked inside this server.")
    async def listclans(self, interaction: discord.Interaction):
        if not interaction.guild_id: return
        
        guild_clans = await self.db_get_guild_clans(interaction.guild_id)
        if not guild_clans:
            await interaction.response.send_message("📭 No clans are configured for tracking in this server.", ephemeral=True)
            return

        embed = discord.Embed(title="📋 Server Tracked Clans Overview", color=0x336869)
        for tag, details in guild_clans.items():
            embed.add_field(
                name=f"{details['clan_name']} ({tag})",
                value=f"Logging destination: <#{details['channel_id']}>",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="checkwar", description="Instantly check live status for any server-tracked clan.")
    @app_commands.autocomplete(clan_tag=clan_autocomplete)
    @app_commands.describe(clan_tag="Select a clan from your server's registered dashboard list.")
    async def checkwar_command(self, interaction: discord.Interaction, clan_tag: str):
        await interaction.response.defer(thinking=True)
        try:
            print(f"\n🔍 [DEBUG] /checkwar triggered for clan_tag input: '{clan_tag}'")
            result = await self.generate_war_embed(clan_tag)
            print(f"📊 [DEBUG] generate_war_embed returned type: {type(result)} | value: {result}")
            
            embed, war_state, error = result
            
            if error:
                print(f"❌ [DEBUG] generate_war_embed reported an operational error: {error}")
                await interaction.followup.send(f"❌ Error compiling log layout: `{error}`")
                return
                
            if war_state == "notInWar":
                print(f"🛡️ [DEBUG] Clan is verified to be NOT in war.")
                await interaction.followup.send(f"🛡️ The clan `{clan_tag.upper()}` is not in an active war.")
                return

            print(f"✅ [DEBUG] Sending completed embed layout response to Discord channel.")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            import traceback
            print("\n🚨 ====== [CRITICAL CHECKWAR EXCEPTION TRACEBACK] ======")
            traceback.print_exc()
            print("========================================================\n")
            await interaction.followup.send(f"❌ Internal pipeline crash: `{str(e)}`")


# STANDALONE COG SETUP REGISTRATION
async def setup(bot: commands.Bot):
    await bot.add_cog(WarTracker(bot))
    print("[Module Loader] war_tracker cog initialized structurally as formal class system.")
