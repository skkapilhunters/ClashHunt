import discord
from discord.ext import commands
from aiohttp import web
import asyncio
from datetime import datetime

class ResourceAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 1. REPLACE THIS with your actual channel ID where you want the alert to go
        self.ALERT_CHANNEL_ID = 1523672111439151194 
        
        # Setup the web routes
        self.web_app = web.Application()
        # Accepting both POST and GET requests on the /post path
        self.web_app.router.add_post('/post', self.handle_webhook)
        self.web_app.router.add_get('/post', self.handle_webhook)
        self.runner = None

        # Start the server as a background task when the bot is ready
        self.bot.loop.create_task(self.start_server())

    async def start_server(self):
        await self.bot.wait_until_ready()
        self.runner = web.AppRunner(self.web_app)
        await self.runner.setup()
        
        # Render assigns ports dynamically via the PORT environment variable
        import os
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(self.runner, '0.0.0.0', port)
        await site.start()
        print(f"📡 Webhook server listening on port {port}")

    async def handle_webhook(self, request):
        try:
            # Extract data straight from the URL parameters (?account_name=...&townhall=...)
            params = request.query
            
            account_name = params.get('account_name', 'Unknown')
            townhall = params.get('townhall', 'N/A')
            total_builders = params.get('total_builders', 'N/A')
            player_gold = params.get('player_gold', '0')
            player_elixir = params.get('player_elixir', '0')

            # Fetch your channel
            channel = self.bot.get_channel(self.ALERT_CHANNEL_ID)
            if channel:
                # Structure the description using your exact custom layout
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
                    color=16766720, # Gold color hex convert
                    timestamp=datetime.utcnow()
                )
                
                embed.set_footer(
                    text="Blood Alliance Resource Tracker",
                    icon_url="https://cdn.discordapp.com/icons/1153720899715993681/32c5bfa1aea37d50fbfae15f45eac478.webp"
                )

                # Send it to your channel
                await channel.send(embed=embed)
                
                # What the browser user sees upon hitting enter
                return web.Response(text="<h1>✅ Success! Embed posted to Discord.</h1>", content_type="text/html")
            else:
                return web.Response(text="<h1>❌ Channel not found</h1>", content_type="text/html", status=500)

        except Exception as e:
            print(f"Error handling webhook: {e}")
            return web.Response(text="<h1>❌ Internal Error</h1>", content_type="text/html", status=500)

    def cog_unload(self):
        if self.runner:
            asyncio.ensure_future(self.runner.cleanup())

async def setup(bot):
    await bot.add_cog(ResourceAlert(bot))
