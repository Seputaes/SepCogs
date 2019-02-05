from typing import Dict, List, Optional, Union

import discord

from cog_shared.seplib.cog import SepCog
from cog_shared.seplib.replies import InteractiveActions
from cog_shared.seplib.utils import ContextWrapper, HexColor, Result
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.commands import Context
from soapbox.permissions_checks import bot_can_manage_category, bot_can_move_members, check_configure_permissions
from soapbox.replies import SoapboxEmbedReply, SoapboxErrorReply, SoapboxSuccessReply


class Soapbox(SepCog, commands.Cog):
    """
    Soapbox is a cog which allows users to create their own temporary voice channels by entering a
    specific voice channel. When no users are in that temporary channel,
    it's automatically deleted.

    There are several configuration options available to you:
       - Set the trigger channel and the category the temporary channels will be created in.
       - Set the Channel suffix of the temporary channels: [p]soapbox set suffix
       - Set the maximum number of temporary channels one specific user can have
    """

    DEFAULT_SOAPBOX_SUFFIX = "| \N{TIMER CLOCK}"
    DEFAULT_MAX_USER_SOAPBOXES = 2
    HARD_MAX_USER_SOAPBOXES_CAP = 100

    def __init__(self, bot: Red):
        super(Soapbox, self).__init__(bot=bot)

        self.guild_config_cache: Dict[int, Dict] = {}

        self._ensure_futures()

    async def _init_cache(self):
        """
        Loads Soapbox's guild configuration into a local cache/memory.
        :return: None
        """
        await self.bot.wait_until_ready()

        guilds_config: Dict[int, Dict[str, Dict]] = await self.config.all_guilds()
        guild_cache: Dict[int, Dict] = {}

        for guild_id, guild_data in guilds_config.items():
            config = guild_data.get("config")
            if config:
                guild_cache[guild_id] = config

        self.guild_config_cache = guild_cache

    def _register_config_entities(self, config: Config):
        # register configuration for guilds in Soapbox
        config.register_guild(config={})

    def _get_soapbox_suffix(self, guild: discord.Guild) -> str:
        """
        Retrieves the specified guild's Soapbox channel suffix.
        :param guild: Guild for which to get the Soapbox channel suffix.
        :return: Guild's Soapbox channel suffix. None if there isn't one set.
        """
        suffix: Optional[str] = self.guild_config_cache.get(guild.id, {}).get("suffix")
        if suffix is None:
            self.logger.debug(f"Suffix not found in the cache for Guild {guild.id}. Returning default.")
            return self.DEFAULT_SOAPBOX_SUFFIX
        return suffix

    def _get_max_user_channels(self, guild: discord.Guild) -> int:
        """
        Retrieves the specified guild's Soapbox max user channels setting.
        This is the number of Soapbox channels that can be assigned to a user at any given time.
        :param guild: Guild for which to get the max user channels setting.
        :return: Int, max number of user Soapbox channels.
        """
        max_chan: Optional[int] = self.guild_config_cache.get(guild.id, {}).get("user_max_channels")
        if max_chan is None:
            self.logger.debug(f"Max user channels is not in the cache for Guild {guild.id}. Returning default.")
            return self.DEFAULT_MAX_USER_SOAPBOXES
        return max_chan

    def _get_soapbox_channel(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        """
        Retrieves the specified guild's Soapbox channel which triggers Soapbox.
        :param guild: Guild for which to get the Soapbox channel.
        :return: Guild's Soapbox channel. None if there isn't one set.
        """
        channel_id = self.guild_config_cache.get(guild.id, {}).get("trigger_channel")
        if channel_id is None:
            return None

        channel = guild.get_channel(channel_id)
        if channel is None:
            self.logger.error(f"Soapbox channel no longer exists! Guild: {guild.id} | Channel ID: {channel_id})")
        return channel

    def _get_soapbox_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        """
        Retrieves the specified guild's Soapbox category.
        :param guild: Guild for which to get the Soapbox category.
        :return: Guild's Soapbox category. None if there isn't one set.
        """
        category_id = self.guild_config_cache.get(guild.id, {}).get("category")
        if category_id is None:
            return None

        category = guild.get_channel(category_id)
        if category is None:
            self.logger.error(f"Soapbox category no longer exists! Guild: {guild.id} | " f"Category ID: {category_id}")
        return category

    async def _set_soapbox_config(self, channel: discord.VoiceChannel, category: discord.CategoryChannel) -> None:
        """
        Updates the guild's configuration in the cache and database with the specified trigger
        channel and category for the Soapbox channels.
        :param channel: Voice channel which will trigger Soapbox.
        :param category: Category for the new Soapbox channels.
        :return: None
        """
        guild: discord.Guild = channel.guild
        guild_cache = {
            "trigger_channel": channel.id,
            "category": category.id,
            "user_max_channels": self._get_max_user_channels(guild=guild),
            "suffix": self._get_soapbox_suffix(guild=guild),
        }
        self.guild_config_cache[guild.id] = guild_cache
        await self.config.guild(guild).config.set(guild_cache)
        self.logger.info(
            f"Updated the configuration for Guild {guild.id} | Category: {category.id} | " f"Channel: {channel.id}"
        )

    async def _set_single_soapbox_config(
        self, guild: discord.Guild, key: str, value: Union[int, float, str, List, Dict, None]
    ) -> None:
        """
        Updates a single guild configuration value in the cache and database.
        It does not do any validation on the key or value type.

        :param guild: Discord.py Guild object
        :param key: String key of the config value
        :param value: Config value (any valid JSON type)
        :return: None
        """

        guild_cache: Dict = self.guild_config_cache.get(guild.id, {})
        guild_cache[key] = value

        self.guild_config_cache[guild.id] = guild_cache
        await self.config.guild(guild).config.set(self.guild_config_cache.get(guild.id))
        self.logger.info(f"Updated single config for Guild: {guild.id} | key: {key} | value: {value}")

    @staticmethod
    def _channel_is_empty(channel: discord.VoiceChannel) -> bool:
        vc = channel.guild.get_channel(channel_id=channel.id)
        return len(vc.members) == 0

    def _has_soapbox_suffix(self, channel: discord.VoiceChannel) -> bool:
        """
        Checks if the channel has the soapbox suffix.
        :param channel: Voice channel to check.
        :return: Boolean indicating whether it has the Soapbox suffix.
        """
        return channel.name.endswith(self._get_soapbox_suffix(guild=channel.guild))

    def _is_soapbox_channel(self, channel: discord.VoiceChannel) -> bool:
        """
        Checks if the channel is a Soapbox channel.
        :param channel: Voice channel to check!
        :return: Boolean indicating whether it is a Soapbox channel.
        """
        return channel.category == self._get_soapbox_category(guild=channel.guild) and self._has_soapbox_suffix(
            channel=channel
        )

    def _should_delete_channel(self, channel: discord.VoiceChannel):
        """
        Checks if the specified channel is eligible for deletion.
        :param channel: Channel to check
        :return: Boolean whether it is eligible to be deleted.
        """
        return self._is_soapbox_channel(channel=channel) and self._channel_is_empty(channel=channel)

    def _check_delete_channels(
        self, category: discord.CategoryChannel = None, guild: discord.Guild = None
    ) -> List[discord.VoiceChannel]:
        """
        Gets a list of Voice Channels that would be deleted by Soapbox based on the suffix.

        The list which is returned INCLUDES channels which are not empty. This is because
        there is no guarantee the channel won't be empty once Soapbox is configured.

        :param category: Category where Soapbox will operate. Deleting channels is limited to
        this scope. If category is None, Guild must be set.
        :param guild: Guild to use for the list of voice channels if Category is not set.
                      This is used when the Soapbox category has not been set.

        :return: List of voice channels that would be deleted.
        """

        if category is None and guild is None:
            raise ValueError("Either category or guild must be supplied.")

        if category is None:
            voice_channels = guild.voice_channels
        else:
            voice_channels = [c for c in category.channels if isinstance(c, discord.VoiceChannel)]
        return [vc for vc in voice_channels if self._has_soapbox_suffix(channel=vc)]

    async def _get_soapbox_channel_name(self, member: discord.Member) -> Optional[str]:
        """
        Returns the name of the Soapbox channel which will be created for the user.
        If the member has reached their maximum channel limit, it will return None
        :param member: Member for which to create the Soapbox channel.
        :return: New channel name. None if the user has hit their max channels.
        """
        max_channel = self._get_max_user_channels(guild=member.guild)
        suffix = self._get_soapbox_suffix(guild=member.guild)

        for i in range(1, max_channel + 1):
            channel_name = f"{member.display_name} #{i} {suffix}"
            channel_exists = discord.utils.get(member.guild.voice_channels, name=channel_name)
            if not channel_exists:
                return channel_name
        await member.send(f"You're only allowed to have {max_channel} voice channels.")
        return None  # the user has hit their maximum

    async def _create_soapbox_channel(
        self, category: discord.CategoryChannel, member: discord.Member
    ) -> Result[Optional[discord.VoiceChannel]]:
        """
        Creates a Soapbox channel for a member in the specified category.
        :param category: Category in which to create the Soapbox channel.
        :param member: Member for which to create the Soapbox channel.
        :return: Returns either a Failure Result with error message or the new VC.
        """
        try:
            guild: discord.Guild = category.guild

            channel_name = await self._get_soapbox_channel_name(member=member)
            if channel_name is None:
                message = f"Member {member.id} is not allowed to create more Soapbox channels"
                return Result(success=False, error=message, value=None)

            new_vc: discord.VoiceChannel = await guild.create_voice_channel(
                category=category, name=channel_name, reason="Created by Soapbox Cog."
            )
            self.logger.info(f"Created new Soapbox channel. Guild: {guild.id} | Member: {member} | " f"VC: {new_vc.id}")
            return Result(success=True, value=new_vc, error=None)
        except discord.HTTPException as e:
            self.logger.error(f"Error from Discord while creating voice channel. Error: {e}")
            message = e.args[0] if e.args else ""
            return Result(
                success=False,
                error=f"Discord returned an error while creating a voice channel. " f"Error: {message}",
                value=None,
            )

    async def _move_member_to_channel(self, member: discord.Member, channel: discord.VoiceChannel) -> Result:
        """
        Moves a member into the specified voice channel.
        :param member: The member to move.
        :param channel: The voice channel to move the member to.
        :return: None
        """
        try:
            await member.move_to(channel=channel, reason="Moved by Soapbox Cog.")
            self.logger.info(f"Moved member into channel. Member: {member} | Channel: {channel.id}")
            return Result(success=True, error=None, value=None)
        except discord.HTTPException as e:
            return Result(
                success=False,
                error=f"Error from Disocrd when attempting to move user to " f"Soapbox Channel. Error: {e}",
                value=None,
            )

    async def _move_member_and_delete(self, member: discord.Member) -> Result:
        """
        Creates a dummy "kick channel" which is used to forcefully move the member out
        of the Soapbox Trigger channel.
        :param member: Member for which to create a kick channel and delete.
        :return: None
        """
        try:
            kick_channel: discord.VoiceChannel = await member.guild.create_voice_channel(
                name="_DEL_{}".format(member.display_name)
            )
            await self._move_member_to_channel(member=member, channel=kick_channel)
            await kick_channel.delete(reason="Soapbox kick channel. Deleting temporary kick channel.")
            self.logger.info(
                f"Deleting kick channel. Guild: {member.guild.id} | "
                f"Member: {member} | Channel ID: {kick_channel.id}"
            )
            return Result(success=True, error=None, value=None)
        except discord.HTTPException as e:
            return Result(
                success=False,
                error=f"Discord returned an error while attempting to create/delete Kick channel. " f"Error: {e}",
                value=None,
            )

    async def _create_channel_and_move(self, category: discord.CategoryChannel, member: discord.Member) -> Result:
        """
        Attempts to create a new Soapbox channel for a member and move them to it.

        :param category: Category in which to create the Soapbox channel.
        :param member: Member for which to create the Soapbox channel.
        :return: Result, with success True if successful or an Error if Failure.
        """
        result = await self._create_soapbox_channel(category=category, member=member)

        if not result.success:
            result = await self._move_member_and_delete(member=member)
            self.logger.error(result.error)
            return result
        return await self._move_member_to_channel(member=member, channel=result.value)

    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """
        Discord event which fires when a member changes voice channels.

        Handles the following functionality:
           - Creates a new VC for a member if they entered the Soapbox trigger channel.
           - Deletes empty Soapbox channels

        :param member: Member object given to us by Discord who's voice state changed.
        :param before: Before voice state of the member (which includes the channel)
        :param after: After voice state of the member (which includes the channel)
        :return: None
        """

        if before.channel == after.channel:
            return  # edge case, do nothing

        if after.channel is not None and after.channel == self._get_soapbox_channel(guild=member.guild):
            category = self._get_soapbox_category(member.guild)
            if not category:
                self.logger.error(f"Soapbox category has not been configured for guild {after.channel.guild.id}")
                return  # the category doesn't exist
            result = bot_can_manage_category(category=category)
            if not result.success:
                self.logger.error(f"{result.error}" f"Guild: {category.guild} | Category ID: {category.id}")
                return
            return await self._create_channel_and_move(category=category, member=member)

        if before.channel is not None:
            if self._is_soapbox_channel(channel=before.channel) and self._channel_is_empty(before.channel):
                result = bot_can_manage_category(before.channel.category)
                if not result.success:
                    self.logger.error(
                        f"Unable to delete empty soapbox channel {result.error}"
                        f"Guild: {before.channel.guild.id} | "
                        f"Category ID: {before.channel.category.id}"
                    )
                    return
                try:
                    await before.channel.delete(reason="Deleted by Soapbox Cog. Channel was empty.")
                    self.logger.info(
                        f"Soapbox channel is empty. Deleting channel. "
                        f"Guild: {before.channel.guild.id} | "
                        f"Channel: {before.channel.id}"
                    )
                except discord.HTTPException as e:
                    self.logger.error(f"Discord error while deleting empty Soapbox channel. {e}")

    @commands.group(name="soapbox")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox(self, ctx: Context):
        """
        Soapbox allows members to create their own temporary voice channels.

        **WARNING:** Configuring Soapbox will ***delete*** all empty voice channels which end
                     with the default suffix. To see a list of channels it would delete,
                     type `[p]soapbox check`.
        """
        pass

    @soapbox.command(name="config", aliases=["configure"])
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox_config(
        self, ctx: Context, trigger_channel: discord.VoiceChannel, target_category: discord.CategoryChannel
    ):
        """
        Main Soapbox configuration of the trigger channel and channel category.

        Configures soapbox with the trigger voice channel and target category for the temporary
        Soapbox channels.

        This will use the default suffix and Max User channels. To change these (and any other)
        configs in the future, use the `[p]soapbox set` command.

        **trigger_channel:** Name/ID/Link of the voice channel which will trigger a new
                             temporary Soapbox channel to be created for the user.
        **target_category:** The category where the new Soapbox channel will be created.
                             The channel will have the same permissions as the category.
        """

        # check that the bot has the necessary permissions to perform this command's action
        result = check_configure_permissions(trigger=trigger_channel, category=target_category)
        if not result.success:
            self.logger.info(
                f"Permission check error: {result.error} | "
                f"VC: <{trigger_channel.name}:{trigger_channel.id}> | "
                f"Category: <{target_category.name}:{target_category.id}>"
            )
            return await SoapboxErrorReply(result.error).send(ctx)

        # see if there are any channels which will be deleted as a result of configuring
        # if so, prompt the user
        del_channels = self._check_delete_channels(category=target_category)

        if del_channels:
            # format a confirmation reply
            confirm_message = "**The following channels are __at risk__ of being deleted:**\n"
            for index, channel in enumerate(del_channels):
                confirm_message += f"\n{index+1}. `{channel.name}`"
            confirm_message += "\nAre you sure you wish to proceed?"

            confirm_embed = SoapboxEmbedReply(message=confirm_message, title="Channel Check").build()
            confirmed = await InteractiveActions.yes_or_no_action(ctx=ctx, embed=confirm_embed)

            if not confirmed:
                await ContextWrapper(ctx).cross()
                return
        await self._set_soapbox_config(channel=trigger_channel, category=target_category)
        success_message = (
            "Great! Soapbox has been configured for:\n\n"
            f"**Trigger Channel:** `{trigger_channel.name}`\n"
            f"**Target Category:** `{target_category.name}`\n"
            f"**Max Channels (per user):** `{self._get_max_user_channels(ctx.guild)}`\n"
            f"**Channel Suffix:** `{self._get_soapbox_suffix(ctx.guild)}`"
        )
        await SoapboxEmbedReply(
            message=success_message, title="Successfully Configured!", color=HexColor.success()
        ).send(ctx)
        await ctx.tick()

    @soapbox.group(name="set")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox_set(self, ctx: Context):
        """
        Set individual configuration options for Soapbox.
        """
        pass

    async def _base_command_set(
        self,
        ctx: Context,
        key: str,
        key_name: str,
        value: Union[int, float, str, List, Dict, None],
        value_name: str,
        result: Optional[Result],
    ) -> None:
        """
        Common method for setting individual Soapbox configs from commands.
        Validation should happen before calling this method.
        :param ctx: Context for the command that was called.
        :param key: Key of the config setting to update.
        :param key_name: Friendly name which will be repeated back to the user.
        :param value: Raw value to insert at the the key.
        :param value_name: Friendly string for the value (eg, channel Name) to repeat to user.
        :param result: Any validation result which was run prior to executing this command.
        :return: None
        """

        if result is not None and not result.success:
            await ContextWrapper(ctx).cross()
            return await SoapboxErrorReply(result.error).send(ctx)

        await self._set_single_soapbox_config(guild=ctx.guild, key=key, value=value)
        success_message = "The following configuration has been updated:\n\n" f"**{key_name}:** {value_name}"
        await SoapboxSuccessReply(message=success_message, title=f"Configured {key_name}").send(ctx)
        await ctx.tick()

    @soapbox_set.command(name="channel")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox_set_channel(self, ctx: Context, *, channel: discord.VoiceChannel):
        """
        Configures the voice channel which will trigger Soapbox.

        The bot must have permissions to move users out of the channel.
        """
        result = bot_can_move_members(channel=channel)

        return await self._base_command_set(
            ctx=ctx,
            key="trigger_channel",
            key_name="Trigger Channel",
            value=channel.id,
            value_name=channel.name,
            result=result,
        )

    @soapbox_set.command(name="category")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox_set_category(self, ctx: Context, *, category: discord.CategoryChannel):
        """
        Configures the category where new Soapbox channels will be created.

        The bot must have permission to manage the category.
        """
        result = bot_can_manage_category(category=category)

        return await self._base_command_set(
            ctx=ctx,
            key="category",
            key_name="Soapbox Category",
            value=category.id,
            value_name=category.name,
            result=result,
        )

    @soapbox_set.command(name="max_channels")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox_set_max_channels(self, ctx: Context, *, max_channels: int):
        """
        Configures the max number of Soapbox channels that can be assigned to a user at a time.

        The number of channels must be greater than 0.
        """

        if max_channels <= 0:
            await SoapboxErrorReply(message="The number of max channels must be greater than 0.").send(ctx)

        return await self._base_command_set(
            ctx=ctx,
            key="user_max_channels",
            key_name="Max Channels (per user)",
            value=max_channels,
            value_name=str(max_channels),
            result=None,
        )

    @soapbox_set.command(name="suffix")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox_set_suffix(self, ctx: Context, *, suffix: str):
        """
        Configures the suffix which will be appended to new Soapbox channels.

        This is an identifier that Soapbox uses for detecting when the channels are ready
        to be cleaned up.
        """

        suffix = suffix.strip()

        return await self._base_command_set(
            ctx=ctx, key="suffix", key_name="Soapbox Channel Suffix", value=suffix, value_name=suffix, result=None
        )

    @soapbox.command(name="check")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def soapbox_check(self, ctx: Context):
        """
        Checks if there are any voice channels on the server that are at risk for deletion once Soapbox is activated.
        """
        # passing None for category will check all VC's on the server.
        del_channels = self._check_delete_channels(category=None, guild=ctx.guild)

        if del_channels:
            message = "**The following channels are __at risk__ of being deleted:**\n"
            for index, channel in enumerate(del_channels):
                message += f"\n{index + 1}. `{channel.name}`"

            return await SoapboxEmbedReply(message=message, title="Channel Check").send(ctx)
        else:
            message = (
                "There are no channels currently at risk of deletion. This could change if "
                "any are created or you change the Soapbox suffix with "
                f"`{ctx.prefix}soapbox set suffix` "
                f"before activating Soapbox."
            )
            return await SoapboxErrorReply(message=message, title="Channel Check").send(ctx)
