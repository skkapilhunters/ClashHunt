import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import motor.motor_asyncio  # Async MongoDB driver (pip install motor)

class RoleManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Pull MongoDB URI directly from your .env setup
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            print("❌ [Roles Cog] Error: 'MONGO_URI' not found in .env!")
            return

        # Initialize Async MongoClient
        self.db_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.db_client["discord_bot_db"]        # Your database name
        self.collection = self.db["temporary_roles"]     # Your collection name
        
        # Start the background checking loop automatically
        self.check_temp_roles.start()

    def cog_unload(self):
        self.check_temp_roles.cancel()

    # ==========================================
    # 1. PERMANENT ROLE COMMAND (?role123)
    # ==========================================
    @commands.command(name="admin")
    async def give_perm_role(self, ctx):
        ROLE_ID = 1519709968847081675  # 👈 REPLACE with your real Permanent Role ID
        role = ctx.guild.get_role(ROLE_ID)

        if not role:
            return await ctx.send("❌ Error: Permanent role not found in server configurations.")

        if role in ctx.author.roles:
            return await ctx.send("✨ You already have this permanent role!")

        try:
            await ctx.author.add_roles(role)
            await ctx.send(f"✅ Success! You have been granted **{role.name}** permanently.")
        except discord.Forbidden:
            await ctx.send("❌ My role hierarchy is too low to assign this role!")

    # ==========================================
    # 2. TEMPORARY ROLE COMMAND (?role456)
    # ==========================================
    @commands.command(name="admin7")
    async def give_temp_role(self, ctx):
        ROLE_ID = 1519709968847081675  # 👈 REPLACE with your real Temporary Role ID
        DAYS_DURATION = 7             # Change this to 30 if you want 30 days
        
        role = ctx.guild.get_role(ROLE_ID)

        if not role:
            return await ctx.send("❌ Error: Temporary role not found in server configurations.")

        # Calculate exact expiry timestamp in UTC
        expiry_time = datetime.now(timezone.utc) + timedelta(days=DAYS_DURATION)

        # Database document schema
        role_data = {
            "guild_id": ctx.guild.id,
            "user_id": ctx.author.id,
            "role_id": role.id,
            "expiry": expiry_time  # MongoDB native Date format
        }

        try:
            # Update if already exists, insert if new (Upsert)
            await self.collection.update_one(
                {"guild_id": ctx.guild.id, "user_id": ctx.author.id, "role_id": role.id},
                {"$set": role_data},
                upsert=True
            )

            await ctx.author.add_roles(role)
            await ctx.send(f"⏳ Success! You have been granted **{role.name}** for **{DAYS_DURATION} days**.")
        except discord.Forbidden:
            await ctx.send("❌ My role hierarchy is too low to assign this role!")
        except Exception as e:
            await ctx.send("❌ Database connection error. Failed to store expiration.")
            print(f"MongoDB Error: {e}")

    # ==========================================
    # 3. BACKGROUND DATABASE SCANNER (Runs every 60 seconds)
    # ==========================================
    @tasks.loop(seconds=60)
    async def check_temp_roles(self):
        now = datetime.now(timezone.utc)
        
        try:
            # Query MongoDB for all records where expiry is less than or equal to current time
            cursor = self.collection.find({"expiry": {"$lte": now}})
            expired_records = await cursor.to_list(length=100) # Process batches of up to 100

            for record in expired_records:
                guild = self.bot.get_guild(record["guild_id"])
                if guild:
                    member = guild.get_member(record["user_id"])
                    role = guild.get_role(record["role_id"])

                    if member and role and role in member.roles:
                        try:
                            await member.remove_roles(role)
                            print(f"🗑️ Removed expired temporary role {role.name} from {member.name}")
                        except discord.Forbidden:
                            print(f"⚠️ Permissions missing to strip role in guild: {guild.name}")
                
                # Delete tracking record out of MongoDB after processing
                await self.collection.delete_one({"_id": record["_id"]})

        except Exception as e:
            print(f"⚠️ Error running MongoDB role checking loop: {e}")

    @check_temp_roles.before_loop
    async def before_check_temp_roles(self):
        await self.bot.wait_until_ready()

# Setup hook needed to register your cog automatically
async def setup(bot):
    await bot.add_cog(RoleManager(bot))
