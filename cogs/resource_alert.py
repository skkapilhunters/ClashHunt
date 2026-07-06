import discord
from discord.ext import commands
from datetime import datetime

class ResourceAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # REPLACE THIS with your actual channel ID where you want the alert to go
        self.ALERT_CHANNEL_ID = 1523672111439151194 

    async def send_resource_embed(self, account_name, townhall, total_builders, player_gold, player_elixir):
        # Fetch your channel
        channel = self.bot.get_channel(self.ALERT_CHANNEL_ID)
        if not channel:
            print(f"❌ [ResourceAlert] Channel {self.ALERT_CHANNEL_ID} not found.")
            return False

        # Structure the description using your custom layout
        embed_description = (
            f"Attention! **{account_name}** has reached maximum resource capacity and needs attention.\n\n"
            f"### 📊 Account Details:\n"
            f"<a:parrow:1516089889110753383> **Town Hall:** Level {townhall}\n"
            f"<a:rarroww:1516090007914287237> **Available Builders:** {total_builders}\n\n"
            f"### 💰 Current Resources:\n"
            f"<a:yarrow:1516090009596198963> **Gold:** {player_gold} (MAX)\n"
            f"<a:rarroww:1516090007914287237> **Elixir:** {player_elixir} (MAX)\n\n"
            f"<a:wow:1516089962431250473> Log in now to spend your resources on upgrades and keep those builders busy!"
        )

        # Assemble the Embed
        embed = discord.Embed(
            title="<a:bluestar:1516089971100876800> Resource Alert: Storage Full!",
            description=embed_description,
            color=16766720, # Gold color
            timestamp=datetime.utcnow()
        )
        
        embed.set_footer(
            text="Blood Alliance Resource Tracker",
            icon_url="https://cdn.discordapp.com/icons/1153720899715993681/32c5bfa1aea37d50fbfae15f45eac478.webp"
        )

        # Send it to your channel
        await channel.send(embed=embed)
        return True

async def setup(bot):
    await bot.add_cog(ResourceAlert(bot))
