import discord
from discord.ext import commands
import aiohttp
import asyncio
import time

class ProxyTester(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # URL used to test the proxy connection (HTTPBin returns your current IP)
        self.test_url = "http://httpbin.org/ip"

    def parse_proxy(self, proxy_str):
        """Parses IP:Port or IP:Port:User:Pass formats into a valid aiohttp proxy URL."""
        parts = proxy_str.strip().split(":")
        
        if len(parts) == 2:
            # Format: IP:Port
            return f"http://{parts[0]}:{parts[1]}"
        elif len(parts) == 4:
            # Format: IP:Port:Username:Password
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        return None

    async def test_single_proxy(self, session, raw_proxy):
        """Tests a single proxy and returns its status and ping."""
        proxy_url = self.parse_proxy(raw_proxy)
        if not proxy_url:
            return {"proxy": raw_proxy, "status": "❌ Invalid Format", "ping": None}

        start_time = time.time()
        try:
            # Setting a 5-second timeout so slow proxies get dropped quickly
            async with session.get(self.test_url, proxy=proxy_url, timeout=5) as response:
                if response.status == 200:
                    ping = round((time.time() - start_time) * 1000)
                    return {"proxy": raw_proxy, "status": "✅ Working", "ping": ping}
                else:
                    return {"proxy": raw_proxy, "status": f"❌ Error {response.status}", "ping": None}
        except Exception:
            return {"proxy": raw_proxy, "status": "❌ Dead / Timed Out", "ping": None}

    @commands.command(name="testproxies", prefix="?")
    @commands.has_permissions(manage_messages=True)
    async def test_proxies(self, ctx, *, proxy_list: str):
        """
        Tests a list of proxies.
        Usage: ?testproxies 
        IP:Port
        IP:Port:User:Pass
        """
        # Split the user input by lines to get individual proxies
        raw_proxies = [line.strip() for line in proxy_list.split("\n") if line.strip()]
        
        if not raw_proxies:
            await ctx.send("❌ Please provide at least one proxy to test.")
            return

        status_msg = await ctx.send(f"⚡ Testing {len(raw_proxies)} proxies... please wait.")

        # Run all proxy checks simultaneously using an aiohttp session
        async with aiohttp.ClientSession() as session:
            tasks = [self.test_single_proxy(session, p) for p in raw_proxies]
            results = await asyncio.gather(*tasks)

        # Separate the results
        working_proxies = []
        dead_proxies_count = 0
        invalid_count = 0

        for r in results:
            if "✅ Working" in r["status"]:
                working_proxies.append(f"`{r['proxy']}` - 🏓 {r['ping']}ms")
            elif "Invalid Format" in r["status"]:
                invalid_count += 1
            else:
                dead_proxies_count += 1

        # Sort working proxies by the lowest ping (best first)
        working_proxies.sort(key=lambda x: int(x.split("🏓 ")[1].replace("ms`", "").replace("ms", "")))

        # Build output embed
        embed = discord.SummaryEmbed if hasattr(discord, 'SummaryEmbed') else discord.Embed(
            title="🌐 Proxy Test Results",
            color=discord.Color.green() if working_proxies else discord.Color.red()
        )
        
        embed.add_field(name="📊 Summary", value=f"✅ Working: {len(working_proxies)}\n❌ Dead/Timed out: {dead_proxies_count}\n⚠️ Invalid Format: {invalid_count}", inline=False)

        if working_proxies:
            # Display up to the top 15 best proxies to prevent hitting embed text limits
            best_list = "\n".join(working_proxies[:15])
            if len(working_proxies) > 15:
                best_list += f"\n*...and {len(working_proxies) - 15} more working proxies.*"
            embed.add_field(name="⚡ Best Working Proxies (Sorted by Ping)", value=best_list, inline=False)
        else:
            embed.description = "No working proxies were found from your list."

        await status_msg.delete()
        await ctx.send(embed=embed)

    @test_proxies.error
    async def proxy_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Please provide a list of proxies. Example:\n`?testproxies 123.45.67.89:8080`")

async def setup(bot):
    await bot.add_cog(ProxyTester(bot))
