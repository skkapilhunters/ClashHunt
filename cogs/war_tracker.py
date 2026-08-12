import asyncio
import os
from datetime import datetime, timezone

import aiohttp  # type: ignore
import discord  # type: ignore
from bot_instance import bot
from discord import app_commands  # type: ignore
from discord.ext import commands, tasks  # type: ignore
from dotenv import load_dotenv  # type: ignore
from modules.scraper import scrape_fwa_details
from modules.war_conflict import generate_and_store_war_conflict
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
BASE_GATEWAY = "https://clash-hunt-api.vercel.app/proxy"


# --- SAFE AUTOCOMPLETE DROPDOWN FILTER (SERVER SCOPED) ---
async def clan_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
  """Generates dropdown options safely and fast to prevent Discord timeout."""
  try:
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
  except Exception as e:
    print(f"[Autocomplete Error] {e}")
    return []


class WarTracker(commands.Cog):

  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.session = None  # Placeholder for persistent session
    self.mongo_client = None
    self.db = None
    self.clans_collection = None
    self.conflicts_collection = None

    # Connect DB
    self.init_mongodb()

  async def cog_load(self):
    """Lifecycle hook: Called automatically when cog is added."""
    self.session = aiohttp.ClientSession()
    if not self.check_clan_war_loop.is_running():
      self.check_clan_war_loop.start()

  async def cog_unload(self):
    """Lifecycle hook: Called automatically when cog is unloaded/reloaded."""
    self.check_clan_war_loop.cancel()
    if self.session and not self.session.closed:
      await self.session.close()

  # --- DATABASE MANAGEMENT FUNCTIONS ---
  def init_mongodb(self):
    """Initializes MongoDB connection client."""
    if not MONGO_URI:
      print("[Critical Error] MONGO_URI is missing from your .env file!")
      return False

    self.mongo_client = AsyncIOMotorClient(MONGO_URI)
    self.db = self.mongo_client["ClashHunt"]
    self.clans_collection = self.db["tracked_clans"]
    self.conflicts_collection = self.db["war_conflicts"]
    print("[Database] WarTracker successfully connected to MongoDB.")
    return True

  async def db_add_clan(self, tag, name, channel_id, guild_id):
    await self.clans_collection.update_one(
        {"clan_tag": tag, "guild_id": guild_id},
        {
            "$set": {"clan_name": name, "channel_id": channel_id},
            "$setOnInsert": {"last_match_id": None, "last_phase": None},
        },
        upsert=True,
    )

  async def db_update_war_state(
      self, tag, guild_id, current_phase, opponent_tag
  ):
    """Updates stored war phase and opponent tag permanently in MongoDB."""
    await self.clans_collection.update_one(
        {"clan_tag": tag, "guild_id": guild_id},
        {
            "$set": {
                "last_phase": current_phase,
                "last_match_id": opponent_tag,
            }
        },
    )

  async def db_remove_clan(self, tag, guild_id):
    await self.clans_collection.delete_one(
        {"clan_tag": tag, "guild_id": guild_id}
    )

  async def db_get_guild_clans(self, guild_id):
    cursor = self.clans_collection.find({"guild_id": guild_id})
    clans = await cursor.to_list(length=100)

    clans_data = {}
    for c in clans:
      clans_data[c["clan_tag"]] = {
          "clan_name": c["clan_name"],
          "channel_id": c["channel_id"],
      }
    return clans_data

  async def db_get_all_global_clans(self):
    cursor = self.clans_collection.find({})
    return await cursor.to_list(length=1000)

  # --- COC DATA PARSERS ---
  def parse_coc_date(self, date_str):
    if not date_str:
      return None
    try:
      clean_str = date_str.replace(".000Z", "").replace("Z", "")
      dt = datetime.strptime(clean_str, "%Y%m%dT%H%M%S")
      return dt.replace(tzinfo=timezone.utc)
    except Exception:
      return None

  def get_th_composition(self, members):
    counts = {}
    for member in members:
      th = member.get("townhallLevel") or member.get("townHallLevel")
      if th:
        counts[th] = counts.get(th, 0) + 1

    sorted_th = sorted(counts.keys(), reverse=True)
    comp_strings = []
    for th in sorted_th:
      if th >= 12:
        comp_strings.append(f":th{th}: `{counts[th]}`")
      else:
        comp_strings.append(f"TH{th} `{counts[th]}`")
    return " ".join(comp_strings) if comp_strings else "No data"

  async def generate_war_embed(self, clan_tag):
    """Generates visual Discord Embed for /checkwar and auto-posts."""
    clean_tag = f"#{clan_tag.upper().replace('#', '').strip()}"

    params = {
        "endpoint": "clans",
        "tag": clean_tag,
        "suffix": "currentwar",
    }

    # Reusing self.session or fallback session
    session_to_use = self.session if self.session else aiohttp.ClientSession()
    should_close = self.session is None

    try:
      async with session_to_use.get(
          BASE_GATEWAY, params=params
      ) as response:
        if response.status != 200:
          return None, None, f"Proxy Error (Status: {response.status})"
        war_data = await response.json()
    finally:
      if should_close:
        await session_to_use.close()

    if war_data.get("state") == "notInWar":
      return None, "notInWar", None

    clan = war_data.get("clan", {})
    opponent = war_data.get("opponent", {})
    state = war_data.get("state")
    match_id = f"{opponent.get('tag')}-{state}"

    print(f"[Main Bot] Scraping FWA metrics for {clean_tag}...")
    fwa_metrics = await asyncio.to_thread(scrape_fwa_details, clean_tag)

    end_time = self.parse_coc_date(war_data.get("endTime"))
    time_left_text = "Unknown"
    if end_time:
      now = datetime.now(timezone.utc)
      delta = end_time - now
      total_hours = int(delta.total_seconds() // 3600)
      days = total_hours // 24
      hours = total_hours % 24
      time_left_text = f"{days}d {hours}h" if days > 0 else f"{hours}h"

    our_comp = self.get_th_composition(clan.get("members", []))
    enemy_comp = self.get_th_composition(opponent.get("members", []))
    clean_our_tag = clan.get("tag", "").replace("#", "")
    clean_enemy_tag = opponent.get("tag", "").replace("#", "")

    embed = discord.Embed(description="<@&1500908965196730480>", color=3368601)
    badge_url = clan.get("badgeUrls", {}).get(
        "medium",
        "https://api-assets.clashofclans.com/badges/200/GZm0ep4Lp9-5woM7I6P2DD61PIzuMuT2Jk3EeZbpKVc.png",
    )
    embed.set_thumbnail(url=badge_url)

    field_title = f"{clan.get('name')} vs {opponent.get('name')}"
    field_value = (
        f"**[{clan.get('name')}](https://link.clashofclans.com/en?action=OpenClanProfile&tag={clean_our_tag})**"
        f" (`{clan.get('tag')}`) **VS**"
        f" **[{opponent.get('name')}](https://link.clashofclans.com/en?action=OpenClanProfile&tag={clean_enemy_tag})**"
        f" (`{opponent.get('tag')}`)\n\n"
        f"**Match Type:** {fwa_metrics['match_type']}\n"
        f"**Sync Number:** #{fwa_metrics['sync_num']}\n"
        f"**War ID:** #{fwa_metrics['war_id']}\n"
        f"**Team Size:** {war_data.get('teamSize')} vs"
        f" {war_data.get('teamSize')}\n"
        f"**Ends in:** {time_left_text}\n\n"
        f"**Points Balance:** {fwa_metrics['point_balance']}\n\n"
        f"**CC Link:**"
        " [Link](https://link.clashofclans.com/en?action=OpenClanProfile&tag="
        f"{clean_our_tag})\n**Points Check:**"
        f" [Check](https://points.fwafarm.com/clan?tag={clean_our_tag})\n\n"
        f"**{clan.get('name')} Composition**\n{our_comp}\n\n"
        f"**{opponent.get('name')} Composition**\n{enemy_comp}"
    )

    embed.add_field(name=field_title, value=field_value, inline=False)
    return embed, match_id, None

  # --- BACKGROUND LOOP: AUTO POST & JSON DATABASE SYNC ---
  @tasks.loop(minutes=10)
  async def check_clan_war_loop(self):
    await self.bot.wait_until_ready()

    if not self.session:
      self.session = aiohttp.ClientSession()

    all_tracked_entries = await self.db_get_all_global_clans()
    if not all_tracked_entries:
      return

    for document in all_tracked_entries:
      tag = document["clan_tag"]
      guild_id = document["guild_id"]
      channel_id = document["channel_id"]

      last_recorded_phase = document.get("last_phase")
      last_posted_opponent = document.get("last_match_id")

      channel = self.bot.get_channel(channel_id)

      try:
        # 1. Fetch current war state via API using persistent session
        params = {"endpoint": "clans", "tag": tag, "suffix": "currentwar"}
        async with self.session.get(
            BASE_GATEWAY, params=params
        ) as response:
          if response.status != 200:
            continue
          war_data = await response.json()

        current_state = war_data.get("state")

        # Handle Not In War
        if current_state == "notInWar":
          if last_recorded_phase != "notInWar":
            await self.db_update_war_state(
                tag, guild_id, "notInWar", "notInWar"
            )
          continue

        opponent_tag = war_data.get("opponent", {}).get("tag")
        state_map = {
            "preparation": "Preparation Day",
            "inWar": "Battle Day",
            "warEnded": "War Ended",
        }
        current_phase = state_map.get(current_state, current_state)

        # Check if a new phase or new opponent occurred
        is_state_changed = (current_phase != last_recorded_phase) or (
            opponent_tag != last_posted_opponent
        )

        # DISCORD EMBED ALERT: Only send when state/opponent changes
        if is_state_changed:
          print(
              f"🔄 State change detected for {tag}: [{last_recorded_phase}] ->"
              f" [{current_phase}]"
          )
          if channel:
            embed, _, err = await self.generate_war_embed(tag)
            if embed and not err:
              await channel.send(embed=embed)

        # DATABASE SYNC: Update MongoDB if state changed OR if it's Battle Day
        if is_state_changed or current_phase == "Battle Day":
          print(
              "💾 Updating war conflict data in MongoDB for"
              f" {tag} (Phase: {current_phase})"
          )

          # Generate & Save complete Conflict JSON to MongoDB
          await generate_and_store_war_conflict(
              tag, guild_id, self.conflicts_collection
          )

          # Update tracked state flags in DB
          await self.db_update_war_state(
              tag, guild_id, current_phase, opponent_tag
          )

      except Exception as e:
        print(f"[Loop Exception] Tracking error on {tag}: {e}")

      await asyncio.sleep(1.5)

  # --- SLASH COMMANDS ---

  @app_commands.command(
      name="checkwar",
      description="Instantly check live status and generate war summary.",
  )
  @app_commands.autocomplete(clan_tag=clan_autocomplete)
  @app_commands.describe(
      clan_tag="Select a clan from your server's registered dashboard list."
  )
  async def checkwar_command(
      self, interaction: discord.Interaction, clan_tag: str
  ):
    await interaction.response.defer(thinking=True)
    try:
      embed, war_state, error = await self.generate_war_embed(clan_tag)

      if error:
        await interaction.followup.send(
            f"❌ Error compiling log layout: `{error}`"
        )
        return

      if war_state == "notInWar":
        await interaction.followup.send(
            f"🛡️ The clan `{clan_tag.upper()}` is not in an active war."
        )
        return

      # ALSO update database json manually when /checkwar is triggered
      await generate_and_store_war_conflict(
          clan_tag, interaction.guild_id, self.conflicts_collection
      )

      await interaction.followup.send(embed=embed)

    except Exception as e:
      await interaction.followup.send(
          f"❌ Internal pipeline crash: `{str(e)}`"
      )

  @app_commands.command(
      name="addclan", description="Register a new clan tag for tracking."
  )
  async def addclan(self, interaction: discord.Interaction, clan_tag: str):
    if not interaction.guild_id:
      return
    await interaction.response.defer(ephemeral=True)
    formatted_tag = f"#{clan_tag.upper().replace('#', '').strip()}"

    guild_clans = await self.db_get_guild_clans(interaction.guild_id)
    if formatted_tag in guild_clans:
      await interaction.followup.send(
          f"⚠️ `{formatted_tag}` is already tracked."
      )
      return

    params = {"endpoint": "clans", "tag": formatted_tag, "suffix": ""}
    async with aiohttp.ClientSession() as session:
      async with session.get(BASE_GATEWAY, params=params) as response:
        if response.status != 200:
          await interaction.followup.send(
              "❌ Registration rejected. Please check tag."
          )
          return
        data = await response.json()
        clan_name = data.get("name", "Unknown Clan")

    await self.db_add_clan(
        formatted_tag, clan_name, interaction.channel_id, interaction.guild_id
    )
    await interaction.followup.send(
        f"✅ Registered **{clan_name}** (`{formatted_tag}`)."
    )

  @app_commands.command(
      name="removeclan", description="Stop tracking a clan tag."
  )
  @app_commands.autocomplete(clan_tag=clan_autocomplete)
  async def removeclan(self, interaction: discord.Interaction, clan_tag: str):
    if not interaction.guild_id:
      return
    formatted_tag = clan_tag.upper().strip()
    guild_clans = await self.db_get_guild_clans(interaction.guild_id)

    if formatted_tag not in guild_clans:
      await interaction.response.send_message(
          "❌ That clan is not tracked.", ephemeral=True
      )
      return

    name = guild_clans[formatted_tag]["clan_name"]
    await self.db_remove_clan(formatted_tag, interaction.guild_id)
    await interaction.response.send_message(
        f"🗑️ Removed **{name}** (`{formatted_tag}`).", ephemeral=True
    )

  @app_commands.command(
      name="listclans", description="List all tracked clans in this server."
  )
  async def listclans(self, interaction: discord.Interaction):
    if not interaction.guild_id:
      return
    guild_clans = await self.db_get_guild_clans(interaction.guild_id)
    if not guild_clans:
      await interaction.response.send_message(
          "📭 No tracked clans.", ephemeral=True
      )
      return

    embed = discord.Embed(title="📋 Tracked Clans", color=0x336869)
    for tag, details in guild_clans.items():
      embed.add_field(
          name=f"{details['clan_name']} ({tag})",
          value=f"Channel: <#{details['channel_id']}>",
          inline=False,
      )
    await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
  await bot.add_cog(WarTracker(bot))
  print("[Module Loader] war_tracker cog loaded.")
