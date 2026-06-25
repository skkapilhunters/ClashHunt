import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_linked_players = os.getenv("MONGO_linked_players")

class PlayerLink(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mongo_client = AsyncIOMotorClient(MONGO_URI)
        # FIXED: Removed quotes so it reads your actual environment variable values
        self.db = self.mongo_client[MONGO_DB_NAME]
        self.players_collection = self.db[MONGO_linked_players]
        # Your reliable proxy engine gateway address
        self.base_gateway = "https://clash-hunt-api.vercel.app/proxy"

    async def get_linked_tag(self, discord_id: int):
        user_data = await self.players_collection.find_one({"discord_id": discord_id})
        return user_data["player_tag"] if user_data else None

    @app_commands.command(name="link", description="Link your Clash of Clans account to your Discord profile.")
    @app_commands.describe(player_tag="Your unique in-game player tag (e.g. #9URV90YY).")
    async def link_player(self, interaction: discord.Interaction, player_tag: str):
        await interaction.response.defer(ephemeral=True)
        
        # Clean up the tag text string layout natively
        formatted_tag = f"#{player_tag.upper().replace('#', '').strip()}"
        
        # Set up parameters structurally for your proxy
        params = {
            "endpoint": "players",
            "tag": formatted_tag,
            "suffix": ""
        }

        async with aiohttp.ClientSession() as session:
            # Your proxy handles the keys, headers, and encoding automatically under the hood now!
            async with session.get(self.base_gateway, params=params) as response:
                if response.status != 200:
                    await interaction.followup.send("❌ Valid player tag not found.")
                    return
                player_data = await response.json()

        player_name = player_data.get("name", "Unknown Player")
        townhall = player_data.get("townHallLevel", "Unknown TH")

        await self.players_collection.update_one(
            {"discord_id": interaction.user.id},
            {"$set": {"player_tag": formatted_tag, "player_name": player_name}},
            upsert=True
        )
        await interaction.followup.send(f"🔗 Linked **{player_name}** (TH{townhall} | `{formatted_tag}`).")

    @app_commands.command(name="unlink", description="Remove your linked player data.")
    async def unlink_player(self, interaction: discord.Interaction):
        linked_tag = await self.get_linked_tag(interaction.user.id)
        if not linked_tag:
            await interaction.response.send_message("⚠️ No active link configuration found.", ephemeral=True)
            return

        await self.players_collection.delete_one({"discord_id": interaction.user.id})
        await interaction.response.send_message("🗑️ Account links removed.", ephemeral=True)

    @app_commands.command(name="profile", description="Display your linked player metrics.")
    async def show_profile(self, interaction: discord.Interaction):
        await interaction.response.defer()
        player_tag = await self.get_linked_tag(interaction.user.id)
        if not player_tag:
            await interaction.followup.send("❌ Link your profile first via `/link`.")
            return

        # Structure proxy layout parameters for routing profiles
        params = {
            "endpoint": "players",
            "tag": player_tag,
            "suffix": ""
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_gateway, params=params) as response:
                if response.status != 200:
                    await interaction.followup.send("❌ Failed to contact CoC servers via proxy pipeline.")
                    return
                p_data = await response.json()

        embed = discord.Embed(title=f"🛡️ Profile: {p_data.get('name')} ({player_tag})", color=0x3498db)
        embed.add_field(name="Town Hall", value=f"TH {p_data.get('townHallLevel')}", inline=True)
        embed.add_field(name="XP Level", value=p_data.get('expLevel'), inline=True)
        embed.add_field(name="Trophies", value=f"🏆 {p_data.get('trophies')}", inline=True)
        
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerLink(bot))
