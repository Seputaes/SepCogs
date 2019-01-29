import asyncio
from typing import Dict, Optional

import discord

from cog_shared.seplib.cog import SepCog
from cog_shared.seplib.replies import ErrorReply
from cog_shared.seplib.utils.queues import EditMemberRoles
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.commands import Context
from .checks import get_liverole_action, bot_can_manage_roles
from .modification import Modification


class LiveRole(SepCog, commands.Cog):

    ROLE_MODIFICATION_INTERVAL = 2

    def __init__(self, bot: Red):
        super(LiveRole, self).__init__(bot=bot)

        self.edit_member_roles = EditMemberRoles(cog=self)

        self.guild_cache: Dict = {}
        self._ensure_futures()

    async def _init_cache(self) -> None:
        """
        Load the guild configuration of LiveRole from the database into the cache/local memory.
        :return:
        """
        await self.bot.wait_until_ready()

        guilds: Dict[int, Dict] = await self.config.all_guilds()

        for guild_id, guild_dict in guilds.items():
            config = guild_dict.get("config")
            if config:
                self.guild_cache[guild_id] = config

    def _register_config_entities(self, config: Config) -> None:
        """
        Register the config entities need for Live Role
        Needed:
          - Guild: "Config" -> Dict
        :param config: Liverole configuration for the guild.
        :return: None
        """
        config.register_guild(config={})

    def _get_guild_liverole_id(self, guild: discord.Guild) -> Optional[int]:
        """
        Gets the current LiveRole ID for the guild, if set.
        :param guild: Discord Guild
        :return: The configured LiveRole ID.
        """
        return self.guild_cache.get(guild.id, {}).get("role")

    async def _update_liverole_role(self, guild: discord.Guild, role: discord.Role):
        """
        Updates the LiveRole role in the cache and db configuration for the guild.
        :param guild: Discord Guild
        :param role: Discord ROle
        :return: None
        """
        current_config = self.guild_cache.get(guild.id, {})
        current_config["role"] = role.id
        self.guild_cache[guild.id] = current_config
        await self.config.guild(guild).config.set(current_config)
        self.logger.info(f"Updated LiveRole for Guild {guild}|{guild.id} to {role}|{role.id}")

    @commands.group(name="liverole")
    @checks.mod_or_permissions(manage_roles=True)
    @commands.guild_only()
    async def liverole(self, ctx: Context):
        """
        Main command for configuring LiveRole.
        """
        pass

    @liverole.group(name="set")
    @checks.mod_or_permissions(manage_roles=True)
    @commands.guild_only()
    async def liverole_set(self, ctx: Context):
        """
        Sets individual configuration options for LiveRole.
        """
        pass

    @liverole_set.command(name="role")
    @checks.mod_or_permissions(manage_roles=True)
    @commands.guild_only()
    async def liverole_set_role(self, ctx: Context, role: discord.Role):
        """
        Sets the role to be assigned to a user once they start streaming, and removed when they stop.

        This will not update any users who are CURRENTLY streaming.
        """

        result = bot_can_manage_roles(guild=ctx.guild)
        if not result.success:
            return await ErrorReply(result.error).send(ctx)

        await self._update_liverole_role(guild=ctx.guild, role=role)
        return await ctx.tick()

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Triggered when a Member Update event is sent by Discord. Checks if LiveRole has been configured,
        and if the user is streaming/stopped string, queues up an add/remove action of the role for the user.
        :param before: State of the user before the update.
        :param after: State of the user after the update.
        :return: None
        """

        action = get_liverole_action(before=before, after=after)
        if action is None:
            return

        guild_liverole_id = self._get_guild_liverole_id(after.guild)
        if not guild_liverole_id:
            return
        guild_liverole = after.guild.get_role(guild_liverole_id)

        if not guild_liverole:
            self.logger.error(f"Role with ID {guild_liverole_id} not found in Guild {after.guild.id}")
            return

        if action is True:
            await self.edit_member_roles.add_role(member=after, role=guild_liverole)
        elif action is False:
            await self.edit_member_roles.remove_role(member=after, role=guild_liverole)
