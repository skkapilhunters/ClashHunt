import asyncio
import discord # type: ignore
from discord.ext import tasks, commands # type: ignore
from discord import app_commands # type: ignore
import aiohttp # type: ignore
import os
from datetime import datetime, timezone
from dotenv import load_dotenv # type: ignore
from motor.motor_asyncio import AsyncIOMotorClient # type: ignore

# Imports
from bot_instance import bot
from modules.scraper import scrape_fwa_details
from modules.war_conflict import generate_and_store_war_conflict

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
BASE_GATEWAY = "https://clash-hunt-api.vercel.app/proxy"

class WarTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mongo_client = None
        self.db = None
        self.clans_collection = None
        self.conflicts_collection = None
        self.init_mongodb()

    def init_mongodb(self):
        if not MONGO_URI:
            print("[Critical Error] MONGO_URI is missing!")
            return False
        
        self.mongo_client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.mongo_client["ClashHunt"]
        self.clans_collection = self.db["tracked_clans"]
        self.conflicts_collection = self.db["war_conflicts"]
        print("[Database] WarTracker & WarConflicts connected to MongoDB.")
        
        if not self.check_clan_war_loop.is_running():
            self.check_clan_war_loop.start()
        return True

    # Database query helpers
    async def db_get_all_global_clans(self):
        cursor = self.clans_collection.find({})
        return await cursor.to_list(length=1000)

    async def db_update_war_phase(self, tag, guild_id, current_phase, opponent_tag):
        """Persists state tracking in MongoDB."""
        await self.clans_collection.update_one(
            {"clan_tag": tag, "guild_id": guild_id},
            {"$set": {"last_phase": current_phase, "last_match_id": opponent_tag}}
        )

    # --- STATE-AWARE BACKGROUND MONITOR ---
    @tasks.loop(minutes=10)
    async def check_clan_war_loop(self):
        await self.bot.wait_until_ready()
        all_tracked_entries = await self.db_get_all_global_clans()
        if not all_tracked_entries: return

        for document in all_tracked_entries:
            tag = document["clan_tag"]
            guild_id = document["guild_id"]
            channel_id = document["channel_id"]
            
            # Retrieve last phase recorded ('Preparation Day', 'Battle Day', etc.)
            last_recorded_phase = document.get("last_phase")
            last_posted_opponent = document.get("last_match_id")

            channel = self.bot.get_channel(channel_id)
            
            try:
                # 1. Fetch current war state via API
                params = {"endpoint": "clans", "tag": tag, "suffix": "currentwar"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(BASE_GATEWAY, params=params) as response:
                        if response.status != 200: continue
                        war_data = await response.json()

                current_state = war_data.get("state") # 'preparation', 'inWar', 'notInWar'
                
                if current_state == "notInWar":
                    if last_recorded_phase != "notInWar":
                        await self.db_update_war_phase(tag, guild_id, "notInWar", "notInWar")
                    continue

                opponent_tag = war_data.get("opponent", {}).get("tag")

                # Map state strings
                state_map = {
                    "preparation": "Preparation Day",
                    "inWar": "Battle Day",
                    "warEnded": "War Ended"
                }
                current_phase = state_map.get(current_state, current_state)

                # 🔥 PHASE CHANGE TRIGGER:
                # Runs scraper and updates MongoDB conflict document on phase changes
                if current_phase != last_recorded_phase or opponent_tag != last_posted_opponent:
                    
                    print(f"🔄 Phase transition detected for {tag}: [{last_recorded_phase}] ➡️ [{current_phase}]")

                    # Execute war_conflict logic (runs scraper + builds JSON + saves to DB)
                    await generate_and_store_war_conflict(tag, guild_id, self.conflicts_collection)

                    # Update tracking flags in DB to prevent duplicate calls
                    await self.db_update_war_phase(tag, guild_id, current_phase, opponent_tag)

            except Exception as e:
                print(f"[Loop Exception] Tracking error on {tag}: {e}")
            
            await asyncio.sleep(2)

    def cog_unload(self):
        self.check_clan_war_loop.cancel()

async def setup(bot: commands.Bot):
    await bot.add_cog(WarTracker(bot))
    print("[Module Loader] war_tracker cog initialized.")
