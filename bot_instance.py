import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True  
intents.members = True  # 🔥 CRITICAL: Add this line so on_member_join works!

bot = commands.Bot(command_prefix="!", intents=intents)
