import discord
from discord.ext import commands

# 1. Persistent Button that sits in your public #support channel
class TicketLaunchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # timeout=None means the button never stops working

    @discord.ui.button(label="📩 Open a Support Ticket", style=discord.ButtonStyle.primary, custom_id="launch_ticket_btn")
    async def launch_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        # Prevent duplicate tickets by scanning for channels named "ticket-username"
        base_channel_name = f"ticket-{member.name.lower().replace(' ', '-')}"
        existing_channel = discord.utils.get(guild.text_channels, name=base_channel_name)

        if existing_channel:
            await interaction.response.send_message(f"⚠️ You already have an open ticket here: {existing_channel.mention}", ephemeral=True)
            return

        # Acknowledge the interaction immediately to prevent timeouts
        await interaction.response.defer(ephemeral=True)

        # Base permissions configuration
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False), # Hide from everyone else
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True), # Let target user chat
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True) # Let the bot manage it
        }

        # OPTIONAL: Add Support Team Role permission if you have one
        # Replace 'Support Team' with the exact name of your server's staff role
        staff_role = discord.utils.get(guild.roles, name="Support Team")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            # Create the private support channel
            ticket_channel = await guild.create_text_channel(
                name=base_channel_name,
                overwrites=overwrites,
                topic=f"Support ticket opened by {member} (ID: {member.id})"
            )

            # Build an embed message inside the brand-new private channel
            embed = discord.Embed(
                title=f"🎫 Support Ticket for {member.name}",
                description="Welcome! Please explain your issue in detail here. A member of the support team will respond shortly.\n\nTo lock and archive this channel, click the close button below.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="ClashHunt Operations System")

            # Attach a closing management view inside the ticket
            await ticket_channel.send(content=f"{member.mention} | Staff", embed=embed, view=TicketControlView())
            
            # Send confirmation notice visible ONLY to the clicking user
            await interaction.followup.send(f"✅ Your ticket has been generated successfully! Go to {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to build ticket channel: {e}", ephemeral=True)

# 2. Control Button view that sits inside the private ticket room itself
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Double check permissions before letting a user erase a channel
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You do not have permissions to shut down support channels.", ephemeral=True)
            return

        await interaction.response.send_message("⚙️ Archiving and removing ticket channel in 5 seconds...", ephemeral=False)
        
        # Countdown delay to allow users to see confirmation
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

# 3. Main Cog wrapper linking into the dynamic bot loader
class TicketSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Critical event listener to make sure button clicks work even if the bot restarts!
    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent views globally on boot
        self.bot.add_view(TicketLaunchView())
        self.bot.add_view(TicketControlView())

    # Command to drop the master deployment button interface in your channel
    @commands.command(name="setup_tickets", prefix="?")
    @commands.has_permissions(administrator=True)
    async def deploy_ticket_system(self, ctx):
        """Drops the persistent ticket creation dashboard into the channel."""
        embed = discord.Embed(
            title="🛠️ Contact Support & Help Desk",
            description="Need assistance with your configurations, tracking setups, or accounts? Click the button below to initiate a dedicated one-on-one private support environment with our administrators.",
            color=discord.Color.from_rgb(78, 115, 223) # Matches your dashboard accents!
        )
        embed.set_footer(text="Secure Verification Required • Staff Only")
        
        # Post the message containing the launching view button
        await ctx.send(embed=embed, view=TicketLaunchView())
        await ctx.message.delete() # Clears command footprint out of chat history

async def setup(bot):
    await bot.add_cog(TicketSystemCog(bot))
