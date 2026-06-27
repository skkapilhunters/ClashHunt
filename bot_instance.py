
# In your bot initialization file (e.g., bot_instance.py)
import os
import discord
from discord.ext import commands

# If you get a proxy URL from a service like Webshare or a free rotation proxy:
PROXY_URL = os.getenv("PROXY_URL") # e.g., http://username:password@proxy_ip:port

bot = commands.Bot(
    command_prefix="!", 
    # proxy=PROXY_URL,  # Routes Discord API traffic through a clean IP
    intents=discord.Intents.default()
)
