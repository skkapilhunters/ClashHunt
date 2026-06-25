import discord
from discord.ext import commands

# Initialize the shared bot instance cleanly in one place
intents = discord.Intents.default()
intents.message_content = True  

bot = commands.Bot(command_prefix="!", intents=intents)
