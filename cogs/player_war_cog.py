import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

class PlayerWarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.base_gateway = "https://clash-hunt-api.vercel.app/proxy"

    @app_commands.command(name="playerwar", description="Check if a player is in war and look up their live attack performance.")
    @app_commands.describe(player_tag="The unique Clash of Clans player tag (e.g., #2PP92CR0Q)")
    async def playerwar(self, interaction: discord.Interaction, player_tag: str):
        # Standardize the tag format to include an uppercase '#' prefix
        player_tag = player_tag.upper().strip()
        if not player_tag.startswith("#"):
            player_tag = f"#{player_tag}"

        # Defer the response immediately to prevent Discord's 3-second interaction timeout
        await interaction.response.defer()

        async with aiohttp.ClientSession() as session:
            try:
                # -------------------------------------------------------------
                # STEP 1: Fetch Player Profile to identify their current Clan
                # -------------------------------------------------------------
                player_params = {"endpoint": "players", "tag": player_tag, "suffix": ""}
                async with session.get(self.base_gateway, params=player_params) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"❌ Could not find a player profile with the tag `{player_tag}`.")
                        return
                    
                    player_profile = await resp.json()
                    player_name = player_profile.get("name", "Unknown")
                    clan_info = player_profile.get("clan")
                    
                    if not clan_info:
                        await interaction.followup.send(f"🛡️ **{player_name}** is currently clanless. Cannot check war logs.")
                        return
                    
                    clan_tag = clan_info.get("tag")
                    clan_name = clan_info.get("name")

                # -------------------------------------------------------------
                # STEP 2: Query the Clan's Active War Registry
                # -------------------------------------------------------------
                war_params = {"endpoint": "clans", "tag": clan_tag, "suffix": "currentwar"}
                async with session.get(self.base_gateway, params=war_params) as war_resp:
                    if war_resp.status != 200:
                        await interaction.followup.send("❌ Failed to communicate with the clan war registry backend.")
                        return
                    
                    war_data = await war_resp.json()
                    war_state = war_data.get("state")
                    
                    if war_state == "notInWar":
                        await interaction.followup.send(f"🛡️ The clan **{clan_name}** ({clan_tag}) is not currently engaged in an active war.")
                        return

                    clan_members = war_data.get("clan", {}).get("members", [])
                    
                    target_player = None
                    for member in clan_members:
                        if member.get("tag") == player_tag:
                            target_player = member
                            break
                    
                    if not target_player:
                        await interaction.followup.send(f"❌ **{player_name}** is inside the clan, but was left out of this specific war lineup.")
                        return

                # -------------------------------------------------------------
                # STEP 3: Compile Stats and Build the Rich Embed
                # -------------------------------------------------------------
                attacks = target_player.get("attacks", [])
                attacks_used = len(attacks)
                map_position = target_player.get("mapPosition", "N/A")
                
                # Choose border color based on activity
                embed_color = discord.Color.brand_red() if attacks_used > 0 else discord.Color.orange()
                
                embed = discord.Embed(
                    title=f"⚔️ War Roster Tracking: {player_name}",
                    description=f"Live attack monitoring for player `{player_tag}`.",
                    color=embed_color
                )
                
                # Grab the clan badge icon directly from Supercell's media delivery system
                if clan_info.get("badgeUrls"):
                    badge_id = clan_info.get("badgeUrls", {}).get("large", "").split("/")[-1]
                    if badge_id:
                        embed.set_thumbnail(url=f"https://api-assets.clashofclans.com/badges/512/{badge_id}")
                
                embed.add_field(name="Clan Name", value=f"{clan_name} ({clan_tag})", inline=True)
                embed.add_field(name="Map Position", value=f"#{map_position}", inline=True)
                embed.add_field(name="War Status", value=f"🟢 {war_state.upper()}", inline=True)
                embed.add_field(name="Total Attacks Cast", value=f"📊 **{attacks_used}** used", inline=False)

                if attacks_used > 0:
                    total_stars = 0
                    total_destruction = 0
                    hit_logs_text = ""

                    for idx, attack in enumerate(attacks, 1):
                        stars = attack.get("stars", 0)
                        destruction = attack.get("destructionPercentage", 0)
                        opponent_tag = attack.get("opponentTag")
                        
                        total_stars += stars
                        total_destruction += destruction
                        hit_logs_text += f"`[{idx}]` vs `{opponent_tag}` ➔ ⭐ **{stars}** | 💥 **{destruction}%**\n"
                    
                    avg_destruction = round(total_destruction / attacks_used, 1)
                    
                    embed.add_field(name="🎯 Hit Breakdown Logs", value=hit_logs_text, inline=False)
                    embed.add_field(name="🌟 Total Stars Earned", value=f"⭐ **{total_stars}**", inline=True)
                    embed.add_field(name="📈 Avg Destruction", value=f"💥 **{avg_destruction}%**", inline=True)
                else:
                    embed.add_field(name="💤 Attack Status", value="Player has not executed any war base targets yet in this setup.", inline=False)

                embed.set_footer(text="Clash of Clans Tracker • Live Grid Sync")
                
                # Send the complete payload to the channel
                await interaction.followup.send(embed=embed)

            except Exception as e:
                print(f"Pipeline error inside /playerwar command: {e}")
                await interaction.followup.send("💥 An internal exception occurred while compiling the dataset layout.")

# This setup function must be at the end of the file for the bot to load the cog properly
async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerWarCog(bot))