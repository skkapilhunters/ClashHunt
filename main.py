import os
from dotenv import load_dotenv
# Directly import the working bot instance from your unchanged war_tracker file
from cogs.war_tracker import bot

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

async def dynamic_setup_hook():
    """Scans the cogs folder for any new functions we add in the future."""
    print("-----------------------------------------------------")
    print("[System] Scanning 'cogs' folder for future functions...")
    
    if os.path.exists("./cogs"):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.startswith("__"):
                
                # CRITICAL FIX 1: Skip war_tracker because it's already instantiated and imported above
                if filename == "war_tracker.py":
                    continue
                    
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await bot.load_extension(cog_name)
                    print(f"📦 Successfully connected future module: {cog_name}")
                except Exception as e:
                    print(f"❌ Failed to load {cog_name}: {e}")
                    
    print("[System] Syncing global slash application commands...")
    try:
        # CRITICAL FIX 2: This forces Discord to register /playerwar immediately
        synced = await bot.tree.sync()
        print(f"🚀 Global sync complete! {len(synced)} commands active.")
    except Exception as e:
        print(f"❌ Tree sync failed: {e}")
    print("-----------------------------------------------------")

# Dynamically link the setup hook to your working bot
bot.setup_hook = dynamic_setup_hook

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("[Critical Error] DISCORD_BOT_TOKEN is missing from your .env file!")
    else:
        # Start the bot using your token
        bot.run(DISCORD_BOT_TOKEN)
