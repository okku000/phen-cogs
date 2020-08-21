import discord
import aiohttp
import asyncio
import typing

from redbot.core import commands, checks, Config
from redbot.core.utils.chat_formatting import box

class AltDentifier(commands.Cog):
    """
    Check new users with AltDentifier API
    """

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.config = Config.get_conf(
            self,
            identifier=60124753086205362,
            force_registration=True,
        )
        default_guild = {
            "channel": None,
            "actions": {
                "0": None,
                "1": None,
                "2": None,
                "3": None
            }
        }

        self.config.register_guild(**default_guild)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @checks.mod_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.command()
    async def altcheck(self, ctx, *, member: discord.Member = None):
        """Check a user on AltDentifier."""

        if not member:
            member = ctx.author
        if member.bot:
            return await ctx.send("Bots can't really be alts you know..")
        e = await self.alt_request(member)
        await ctx.send(embed=e)

    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group()
    async def altset(self, ctx):
        """AltDentifier Settings"""

        if not ctx.subcommand_passed:
            data = await self.config.guild(ctx.guild).all()
            description = []

            if data["channel"]:
                channel = f"<#{data['channel']}>"
            else:
                channel = "None"
            
            description.append(f"AltDentifier Check Channel: {channel}")
            description = "\n".join(description)
            actionsDict = data["actions"]
            actions = []
            for key, value in actionsDict.items():
                actions.append(f"{key}: {value}")
            actions = box("\n".join(actions))

            color = await self.bot.get_embed_colour(ctx)
            e = discord.Embed(
                color=color,
                title=f"AltDentifier Settings",
                description=description
            )
            e.add_field(name="Actions", value=actions, inline=False)
            e.set_author(name=ctx.guild, icon_url=ctx.guild.icon_url)
            await ctx.send(embed=e)

    @altset.command()
    async def channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel to send AltDentifier join checks to.

        This also works as a toggle, so if no channel is provided, it will disable reminders for this server."""

        if not channel:
            await self.config.guild(ctx.guild).channel.clear()
            await ctx.send("Disabled AltDentifier join checks in this server.")
        else:
            try:
                await channel.send("Set this channel as the message channel for AltDentifier join checks")
                await self.config.guild(ctx.guild).channel.set(channel.id)
            except discord.errors.Forbidden:
                await ctx.send("I do not have permission to talk in that channel.")
        await ctx.tick()

    @checks.is_owner()
    @altset.command()
    async def action(self, ctx, level: int, action: typing.Union[discord.Role, str] = None):
        """Specify what actions to take when a member joins and has a certain Trust Level.

        Leave this empty to remove actions for the Level.        
        The available actions are:
        `kick`
        `ban`
        `mute`
        `role` (don't say 'role' for this, pass an actual role."""
        if not level in range(4):
            return await ctx.send("This is not a valid Trust Level. The valid Levels are: 0, 1, 2, and 3.")
        if not action:
            async with self.config.guild(ctx.guild).actions() as a:
                a[level] = None
            return await ctx.send(f"Removed actions for Trust Level {level}.")
        if isinstance(action, discord.Role):
            async with self.config.guild(ctx.guild).actions() as a:
                a[level] = action.id
        elif isinstance(action, str) and action.lower() not in ["kick", "ban", "mute"]:
            return await ctx.send("This is not a valid action. The valid actions are kick, ban and mute. For roles, supply a role.")
        else:
            async with self.config.guild(ctx.guild).actions() as a:
                a[level] = action.lower()
        await ctx.tick()

    async def alt_request(self, member: discord.Member):
        async with self.session.get(f"https://altdentifier.com/api/v2/user/{member.id}/trustfactor") as response:
            response = await response.json()
        color = await self.pick_color(response["trustfactor"])
        e = discord.Embed(
            color=color,
            title="AltDentifier Check",
            description=f"{member.mention} is {response['formatted_trustfactor']}\nTrust Factor: {response['trustfactor']}"
        )
        e.set_thumbnail(url=member.avatar_url)
        return e

    async def pick_color(self, trustfactor: int):
        if trustfactor == 0:
            color = discord.Color.dark_red()
        elif trustfactor == 1:
            color = discord.Color.red()
        elif trustfactor == 2:
            color = discord.Color.green()
        elif trustfactor == 3:
            color = discord.Color.dark_green()
        return color

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        data = await self.config.guild(member.guild).all()
        if not data["channel"]:
            return
        channel = member.guild.get_channel(data["channel"])
        if not channel:
            await self.config.guild(member.guild).channel.clear()
            return
        e = await self.alt_request(member)
        await channel.send(embed=e)