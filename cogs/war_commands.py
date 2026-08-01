import os
import discord
from discord.ext import commands
import motor.motor_asyncio

from modules.firebase_exporter import export_war_to_firebase


class WarCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        mongo_uri = os.getenv("MONGO_URI")
        self.collection = None
        
        if mongo_uri:
            client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
            try:
                db = client.get_default_database()
            except Exception:
                db_name = os.getenv("MONGO_DB_NAME", "clash_bot")
                db = client[db_name]
                
            self.collection = db["war_conflicts"]

    @commands.command(name="migratewar")
    @commands.has_permissions(administrator=True)
    async def migrate_war(self, ctx):
        """
        Pulls ALL records currently sitting in MongoDB 'war_conflicts', 
        pushes them to Firebase Firestore, and wipes them from MongoDB.
        Usage: !migratewar
        """
        # Resolve collection safely without triggering boolean evaluation
        db_collection = self.collection if self.collection is not None else getattr(self.bot, "db_collection", None)

        if db_collection is None:
            await ctx.send("❌ Could not connect to MongoDB. Check your `MONGO_URI` environment variable.")
            return

        status_msg = await ctx.send("⏳ Fetching all documents from MongoDB collection for bulk migration...")

        try:
            # 1. Retrieve all entries from MongoDB
            cursor = db_collection.find({})
            mongo_docs = await cursor.to_list(length=1000)

            if not mongo_docs:
                await status_msg.edit(content="⚠️ No documents found in MongoDB `war_conflicts` collection to migrate.")
                return

            migrated_count = 0
            failed_count = 0

            # 2. Loop through every document in MongoDB
            for doc in mongo_docs:
                clan_tag = doc.get("clan_tag")
                guild_id = doc.get("guild_id", ctx.guild.id)
                conflict_data = doc.get("conflict_data", {})

                if not clan_tag or not conflict_data:
                    continue

                # Force push to Firebase
                success = await export_war_to_firebase(clan_tag, guild_id, conflict_data)

                if success:
                    # Delete document from MongoDB
                    await db_collection.delete_one({"_id": doc["_id"]})
                    migrated_count += 1
                else:
                    failed_count += 1

            # 3. Final feedback message
            await status_msg.edit(
                content=(
                    f"✅ **Bulk Migration & Cleanup Complete!**\n"
                    f"• **Migrated & Removed from MongoDB:** `{migrated_count}`\n"
                    f"• **Failed:** `{failed_count}`\n"
                    f"• **Destination:** Firebase Firestore (`ended_wars` collection)"
                )
            )
        except Exception as e:
            await status_msg.edit(content=f"❌ Error during bulk migration: `{str(e)}`")


async def setup(bot):
    await bot.add_cog(WarCommands(bot))
