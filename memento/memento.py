import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Type, Union

import discord
import pytz
import recurrent
from pytz.tzinfo import DstTzInfo

from cog_shared.seplib.cog import SepCog
from cog_shared.seplib.replies import InteractiveActions
from cog_shared.seplib.utils import ContextWrapper, Result
from memento.permissions_checks import check_remind_role_permissions
from memento.reminders import Reminder, RoleReminder, UserReminder
from memento.replies import (
    MementoEmbedReply,
    MementoErrorReply,
    MementoRoleListReply,
    MementoUserListReply,
    ReminderReply,
)
from memento.replies.mementochannellistreply import MementoChannelListReply
from memento.timezonestrings import TimezoneStrings
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.commands import Context


class Memento(SepCog):
    MONITOR_PROCESS_INTERVAL = 2
    CONFIRM_DT_FORMAT = "%b %d, %Y %I:%M:%S%p"
    TIMEZONES_URL = "https://sep.gg/timezones"

    def __init__(self, bot: Red):
        super(Memento, self).__init__(bot=bot)

        self.user_config_cache = {}
        self.user_reminder_cache: Dict[int, List[UserReminder]] = {}
        self.role_reminder_cache: Dict[int, List[RoleReminder]] = {}

        self._add_future(self.__monitor_reminders())
        self._ensure_futures()

    async def _init_cache(self):
        """
        Load the user and role reminders from the database into the cache/local memory.
        :return: None
        """
        await self.bot.wait_until_ready()

        users: Dict[int, Dict] = await self.config.all_users()
        roles: Dict[int, Dict] = await self.config.all_roles()

        user_config = {}
        user_reminders = {}
        role_reminders = {}

        for user_id, user_dict in users.items():
            config: Dict = user_dict.get("config")
            reminders: List[Dict] = user_dict.get("reminders", [])

            if config:
                user_config[user_id] = config
            cache_reminders: List[UserReminder] = []
            for reminder in reminders:
                try:
                    cache_reminders.append(UserReminder(bot=self.bot, **reminder))
                except TypeError as e:
                    self.logger.error(f"Error building UserReminder from database. Error: {e}")
                    continue
            user_reminders[user_id] = cache_reminders

        for role_id, role_dict in roles.items():
            reminders: List[Dict] = role_dict.get("reminders")
            cache_reminders: List[RoleReminder] = []
            for reminder in reminders:
                try:
                    cache_reminders.append(RoleReminder(bot=self.bot, **reminder))
                except TypeError as e:
                    self.logger.error(f"Error building RoleReminder from database. Error: {e}")
                    continue
            role_reminders[role_id] = cache_reminders

        self.user_config_cache = user_config
        self.user_reminder_cache = user_reminders
        self.role_reminder_cache = role_reminders

    def _register_config_entities(self, config: Config):
        """
        Register the config entities we will need for Memento.
        Needed:
          - User: Config and Reminder
          - Roles: Reminders
        :param config: Red config
        :return:  None
        """
        config.register_user(config={}, reminders=[])
        config.register_role(reminders=[])

    async def __monitor_reminders(self):
        """
        Async future which loops while the cog is loaded to check for reminders which are triggered.
        :return: None
        """
        await self.bot.wait_until_ready()

        while self == self.bot.get_cog(self.__class__.__name__):
            now = datetime.utcnow()
            trigger_reminders: List[Reminder] = []

            for user_id, user_reminders in self.user_reminder_cache.items():
                for reminder in user_reminders:
                    if reminder.dt <= (now - timedelta(minutes=60)):
                        self.logger.error("Reminder is too far in the past. Was the bot shut down or cog unloaded?")
                        await self._delete_reminder(reminder=reminder)
                    elif reminder.dt <= now:
                        trigger_reminders.append(reminder)
                        await self._delete_reminder(reminder=reminder)
                        self.logger.info(
                            f"User Reminder triggered. Target: {reminder.messageable} | " f"id: {reminder.id_}"
                        )

            for role_id, role_reminders in self.role_reminder_cache.items():
                for reminder in role_reminders:
                    if reminder.dt <= (now - timedelta(minutes=60)):
                        self.logger.error("Reminder is too far in the past. Was the bot shut down or cog unloaded?")
                        await self._delete_reminder(reminder=reminder)
                    elif reminder.dt <= now:
                        trigger_reminders.append(reminder)
                        await self._delete_reminder(reminder=reminder)
                        self.logger.info(
                            f"Role Reminder triggered. Target: {reminder.messageable} | " f"id: {reminder.id_}"
                        )

            for reminder in trigger_reminders:
                reply = ReminderReply(message=reminder.text)
                reply.content = reminder.mention
                await reply.send(reminder.messageable)

            await asyncio.sleep(self.MONITOR_PROCESS_INTERVAL)

    async def _update_user_config(self, user: discord.User, config: Dict):
        """
        Overwrites the user config with the specified config map.
        :param user: Discord user
        :param config: Map of str/obj keys to store in the user's config
        :return: None
        """
        self.user_config_cache[user.id] = config
        await self.config.user(user).config.set(config)

    def _get_user_timezone(self, user: discord.User) -> Optional[str]:
        """
        Gets the user's timezone string stored in the config.
        :param user: Discord user
        :return: User's timezone string, which can be placed into pytz
        """
        return self.user_config_cache.get(user.id, {}).get("timezone")

    async def _set_user_timezone(self, user: discord.User, timezone: str):
        """
        Updates the user's configuration to set the timezone field.
        This should be a valid pytz timezone string.
        :param user: Discord USer
        :param timezone: pytz-compatible timezone string
        :return: None
        """
        current = self.user_config_cache.get(user.id, {})
        current.update({"timezone": timezone})
        self.user_config_cache[user.id] = current
        await self._update_user_config(user=user, config=current)
        self.logger.info(f"Set user timezone. User: {user} | TZ: {timezone}")

    def _get_user_reminders(self, user: discord.User) -> List[UserReminder]:
        """
        Retrieves the user's reminders from the cache.
        :param user: Discord User
        :return: List of the user's active reminders
        """
        return self.user_reminder_cache.get(user.id, [])

    def _get_role_reminders(self, role: discord.Role) -> List[RoleReminder]:
        """
        Retrieves the role's active reminders from the cache.
        :param role: Discord role
        :return: List of the role's active reminders
        """
        return self.role_reminder_cache.get(role.id, [])

    async def _update_user_reminders(self, user: discord.User, reminders: List[UserReminder]):
        """
        Overwrites the user's reminder list with the one provided.
        :param user: Discord User
        :param reminders: Complete list of user reminders which will overwrite the user's current list
        :return: None
        """
        self.user_reminder_cache[user.id] = reminders
        db_reminders = [r.prepare_for_storage() for r in reminders]
        await self.config.user(user=user).reminders.set(db_reminders)
        self.logger.info(f"Updated reminders for User: {user} | Total: {len(reminders)}")

    async def _update_role_reminders(self, role: discord.Role, reminders: List[RoleReminder]):
        """
        Overwrites the role's reminder list with the one provided.
        :param role: Discord Role
        :param reminders: Complete list of role reminders which will overwrite the role's current list
        :return: None
        """
        self.role_reminder_cache[role.id] = reminders
        db_reminders = [r.prepare_for_storage() for r in reminders]
        await self.config.role(role=role).reminders.set(db_reminders)
        self.logger.info(f"Updated reminders for Role: {role} | Total: {len(reminders)}")

    async def _add_user_reminder(self, user: discord.User, dt: datetime, text: str, timezone: str):
        """
        Adds a single user reminder to the user's existing reminder list in the cache and database.
        :param user: Discord User
        :param dt: UTC-timezone agnostic datetime
        :param text: Reminder text to send to the user when the reminder triggers.
        :param timezone: User's timezone which was set at the time the reminder was created.
        :return: None
        """
        reminders = self._get_user_reminders(user=user)
        reminders.append(
            UserReminder(
                bot=self.bot,
                created_by_id=user.id,
                text=text,
                timezone=timezone,
                dt_str=dt.strftime(UserReminder.ISO8601_FORMAT),
            )
        )
        self.logger.info(f"Adding user reminder: User: {user} | DT: {dt} | Total Reminders: {len(reminders)}")
        await self._update_user_reminders(user=user, reminders=reminders)

    async def _add_role_reminder(
        self,
        user: discord.User,
        role: discord.Role,
        channel: discord.TextChannel,
        dt: datetime,
        text: str,
        timezone: str,
    ):
        """
        Adds a single role reminder to the role's existing reminder list in the cache and database.
        :param user: Discord.py User who created the reminder
        :param role: Discord.py role which will be pinged.
        :param channel: Discord.py channel which will have the reminder sent to it.
        :param dt: UTC-timezone agnostic datetime
        :param text: Reminder text to send to the channel when the reminder triggers.
        :param timezone: Creating user's timezone which was set at the time the reminder was created.
        :return: None
        """
        reminders = self._get_role_reminders(role=role)
        reminders.append(
            RoleReminder(
                bot=self.bot,
                created_by_id=user.id,
                text=text,
                timezone=timezone,
                dt_str=dt.strftime(RoleReminder.ISO8601_FORMAT),
                role_id=role.id,
                channel_id=channel.id,
            )
        )
        self.logger.info(
            f"Adding role reminder added: Created By: {user} | Role: {role} | Channel: {channel} | DT: {dt}"
        )
        await self._update_role_reminders(role=role, reminders=reminders)

    async def _delete_reminder(self, reminder: Reminder):
        """
        Delete's a single reminder from the cache and database (if found)
        :param reminder: Reminder to delete
        :return: None
        """
        if isinstance(reminder, UserReminder):
            current = self._get_user_reminders(user=reminder.created_by)
            new_reminders = [r for r in current if r.id_ != reminder.id_]
            await self._update_user_reminders(user=reminder.created_by, reminders=new_reminders)
            self.logger.info(f"Deleted User reminder. User: {reminder.created_by} | ID: {reminder.id_}")
            return
        elif isinstance(reminder, RoleReminder):
            current = self._get_role_reminders(role=reminder.role)
            new_reminders = [r for r in current if r.id_ != reminder.id_]
            await self._update_role_reminders(role=reminder.role, reminders=new_reminders)
            self.logger.info(f"Deleted Role reminder. Role: {reminder.role} | ID: {reminder.id_}")
            return
        self.logger.error(f"Unable to delete reminder. Unknown reminder type: {reminder}")

    @staticmethod
    def _parse_command_str(command_str: str) -> Optional[Tuple[str, str]]:
        """
        Parses a reminder (user and role) command string into its time and text components.
        :param command_str: Raw command string from the reminder command
        :return: Tuple, first index is the time string, second is the reminder text
        """
        command_split = command_str.split("|", 1)
        if len(command_split) != 2:
            return None
        return command_split[0], command_split[1]

    @staticmethod
    def _get_recurrent_for_tz(tz_info: DstTzInfo) -> recurrent.RecurringEvent:
        """
        Gets a Recurrent object for a specific timezone, so that future dates can be calculated accurately
        :param tz_info: Pytz timezone object
        :return: Recurrent RecurringEvent localized to the timezone.
        """
        now = datetime.utcnow()
        localized = pytz.UTC.localize(now).astimezone(tz_info).replace(tzinfo=None)
        return recurrent.RecurringEvent(now_date=localized)

    def _parse_time_str(self, user: discord.User, reminder_time: str) -> Optional[datetime]:
        """
        Parse a time string into a datetime UTC-timezone aware datetime.
        :param user: Discord user for which to calculate the datetime string
        :param reminder_time: Reminder time string from the command.
        :return: UTC-timezone aware datetime object.
        """
        tz_str = self._get_user_timezone(user=user)
        tz_info = pytz.timezone(tz_str)
        tz_recurrent = self._get_recurrent_for_tz(tz_info=tz_info)
        parsed = tz_recurrent.parse(reminder_time)

        if parsed is None:
            self.logger.info(f"Unable to parse user's time string: {reminder_time}")
            return None

        dt = tz_info.localize(parsed)
        return dt.astimezone(tz=pytz.UTC)

    @commands.group(name="memento", aliases=["remind"])
    async def memento(self, ctx: Context):
        """
        Create reminders for yourself or to ping a role in a specified channel.
        """
        pass

    @memento.group(name="set")
    async def memento_set(self, ctx: Context):
        """
        Collection of user-specific configuration settings for Memento.
        """
        pass

    @memento_set.command(name="tz")
    async def memento_set_tz(self, ctx: Context, tz: str):
        """
        Sets your timezone preference which will be used for absolute dates and times.

        This must be set prior to setting up reminders.
        """

        tz_str = TimezoneStrings.get_pytz_string(tz=tz)
        if not tz_str:
            valid_options = ", ".join(TimezoneStrings.get_timezone_options())
            message = (
                f"{tz} is not a valid timezone. Please choose from one of:\n\n"
                f"{valid_options}\n\n"
                f"For a **complete** list of valid timezones, please see [this list]({self.TIMEZONES_URL})"
            )
            reply = MementoErrorReply(title="Invalid Timezone", message=message)
            return await reply.send(ctx)
        await self._set_user_timezone(user=ctx.author, timezone=tz_str)
        return await ctx.tick()

    async def _handle_reminder_command(
        self,
        ctx: Context,
        command_str: str,
        reminder_type: Type[Reminder],
        role: Optional[discord.Role],
        channel: Optional[discord.TextChannel],
    ) -> Result[bool]:
        """
        Shared helper method for handling both user and role/channel reminder commands.
        :param ctx: Red context in which the command was issued
        :param command_str: Raw command string from the command
        :param reminder_type: Class of the type of reminder being created
        :param role: Discord role (optional, required in the case of Role Reminders)
        :param channel: Discord channel (optional, required in the case of Role Reminders)
        :return: Result success True if successful or success False with error message.
        """
        user_timezone = self._get_user_timezone(user=ctx.author)
        if not user_timezone:
            reply = MementoErrorReply(
                title="Timezone Not Set",
                message=f"You need to set your timezone with `{ctx.prefix}memento set tz` before creating reminders.",
            )
            await reply.send(ctx)
            await ContextWrapper(ctx).cross()
            return Result(success=False, error="Timezone not set", value=False)

        command_ok = self._parse_command_str(command_str=command_str)
        if not command_ok:
            message = "I was unable to understand that string. Please try again."
            reply = MementoErrorReply(title="Unable to parse command", message=message)
            await reply.send(ctx)
            await ContextWrapper(ctx).cross()
            return Result(success=False, error="Unable to parse command", value=False)

        time_str, text = command_ok
        parsed_dt = self._parse_time_str(user=ctx.author, reminder_time=time_str)
        if not parsed_dt:
            message = "I was unable to understand that time. Please try again."
            reply = MementoErrorReply(title="Invalid time specified", message=message)
            await reply.send(ctx)
            await ContextWrapper(ctx).cross()
            return Result(success=False, error="Invalid time specified", value=False)

        if parsed_dt <= datetime.now(tz=pytz.UTC):
            message = "The time specified occurs in the past."
            reply = MementoErrorReply(title="Invalid time specified", message=message)
            await reply.send(ctx)
            await ContextWrapper(ctx).cross()
            return Result(success=False, error="Time occurs in past", value=False)

        user_time_str = parsed_dt.astimezone(pytz.timezone(user_timezone)).strftime(self.CONFIRM_DT_FORMAT)

        if reminder_type is UserReminder:
            reminder_context = "you with a DM"
            add_func = lambda: self._add_user_reminder(user=ctx.author, dt=parsed_dt, text=text, timezone=user_timezone)
        elif reminder_type is RoleReminder:
            reminder_context = f"role `{role.name}` in channel {channel.mention}"
            add_func = lambda: self._add_role_reminder(
                user=ctx.author, role=role, channel=channel, dt=parsed_dt, text=text, timezone=user_timezone
            )
        else:
            self.logger.error(
                f"Invalid reminder type passed in. Expecting UserReminder or RoleReminder, got: {reminder_type}"
            )
            return Result(
                success=False,
                error="Invalid type passed to reminder command. Please contact cog author. This should never happen!",
                value=False,
            )

        confirm_msg = (
            f"Great! I'll remind {reminder_context} when the time comes.\n"
            "Please confirm that the following time is correct:\n\n"
            f"**{user_time_str}**"
        )

        confirm_embed = MementoEmbedReply(message=confirm_msg, title="Reminder Confirmation").build()
        confirmed = await InteractiveActions.yes_or_no_action(ctx=ctx, message=None, embed=confirm_embed)

        if confirmed:
            await add_func()
            await ctx.tick()
        return Result(success=True, error=None, value=True)

    @memento.group(name="me", invoke_without_command=True)
    async def memento_me(self, ctx: Context, *, command_str: str):
        """
        Create a reminder at a specified time which the bot will DM to you.

        You must set your timezone with `[p]memento set tz` before using this command.

        Command format: <time string> | <message>

        You can use common natural language for the time. For example:

          - tomorrow at 9pm | Call Sarah.
          - in 3 hours | Check if the turkey is done
          - friday at noon | Open loot boxes in Overwatch

        The message is the message which the bot will send you in a DM when the time of the reminder passes.
        """
        result = await self._handle_reminder_command(
            ctx=ctx, command_str=command_str, reminder_type=UserReminder, role=None, channel=None
        )
        if not result.success:
            self.logger.info(f"Error occurred while parsing User reminder command. Error: {result.error}")

    @memento_me.command(name="list")
    async def memento_me_list(self, ctx: Context):
        """
        DM's you a list of your active reminders. You can delete reminders from this DM.
        """
        user_reminders = self._get_user_reminders(user=ctx.author)
        if not user_reminders:
            reply = MementoEmbedReply(message="You have no personal reminders.", title="Reminder List")
            return await reply.send(ctx)

        reply = MementoUserListReply(reminders=user_reminders)
        if ctx.guild is not None:
            await ctx.send(f"{ctx.author.mention}: I sent you a DM with your reminders.")
        embed_msg = await reply.send(ctx.author)

        valid_choices = [str(i + 1) for i in range(len(user_reminders))]
        choice = await InteractiveActions.wait_for_dm_choice(
            bot=self.bot, dm=embed_msg.channel, valid_choices=valid_choices
        )
        if choice is not None:
            reminder_to_delete = user_reminders[choice]
            await self._delete_reminder(reminder=reminder_to_delete)
        await reply.edit_to_clean(prev_message=embed_msg)

    @memento.group(name="role", invoke_without_command=True)
    @commands.guild_only()
    @checks.mod_or_permissions()
    async def memento_role(self, ctx: Context, role: discord.Role, channel: discord.TextChannel, *, command_str: str):
        """
        Create a reminder at a specified time. The bot will mention the role in the specified channel.

        You must set your timezone with `[p]memento set tz` before using this command.

        Command format: <role> <channel> <time string> | <message>

        You can use common natural language for the time. For example:

          - tomorrow at 9pm | Call Sarah.
          - in 3 hours | Check if the turkey is done
          - friday at noon | Open loot boxes in Overwatch

        The message is the message which the bot will send to the specified channel when the time comes.
        """
        result = check_remind_role_permissions(channel=channel, role=role)
        if not result.success:
            return await MementoErrorReply(message=result.error).send(ctx)

        result = await self._handle_reminder_command(
            ctx=ctx, command_str=command_str, reminder_type=RoleReminder, role=role, channel=channel
        )
        if not result.success:
            self.logger.info(f"Error occurred while parsing Role reminder command. Error: {result.error}")

    @memento_role.command(name="list", invoke_without_command=True)
    @commands.guild_only()
    @checks.mod_or_permissions()
    async def memento_role_list(self, ctx: Context, *, channel_or_role: Union[discord.Role, discord.TextChannel, str]):
        """
        Lists the active reminders for the specified role or channel.

        If a role is supplied, it will output a list of all reminders which will mention that role,
        along with the channels the message will be sent to.

        If a channel is supplied, it will output a list of all reminders which will reminder a specified channel,
        along with the role which will be mentioned in the channel.

        You can delete reminders from this list.
        """
        if isinstance(channel_or_role, str):
            return MementoErrorReply(message=f"`{channel_or_role}` is not a text channel or server role.")

        if isinstance(channel_or_role, discord.Role):
            role_reminders = self._get_role_reminders(role=channel_or_role)

            if not role_reminders:
                return MementoEmbedReply(
                    message=f"There are no active reminders for role `{channel_or_role.name}`",
                    title=f"Reminder List for Role: {channel_or_role.name}",
                ).send(ctx)

            reply = MementoRoleListReply(reminders=role_reminders)
            embed_msg = await reply.send(ctx)

            valid_choices = [str(i + 1) for i in range(len(role_reminders))]
            choice = await InteractiveActions.wait_for_author_choice(ctx=ctx, valid_choices=valid_choices)

            if choice is not None:
                reminder_to_delete = role_reminders[choice]
                await self._delete_reminder(reminder=reminder_to_delete)
            await reply.edit_to_clean(prev_message=embed_msg)

        elif isinstance(channel_or_role, discord.TextChannel):
            channel_reminders: List[RoleReminder] = []
            for role_id, role_reminders in self.role_reminder_cache.items():
                for reminder in role_reminders:
                    if channel_or_role.id == reminder.channel.id:
                        channel_reminders.append(reminder)

            embed_title = f"Reminder List for Channel: {channel_or_role.name}"
            if not channel_reminders:
                return MementoEmbedReply(
                    message=f"There are no active reminders for channel {channel_or_role.mention}", title=embed_title
                )

            reply = MementoChannelListReply(reminders=channel_reminders)
            embed_msg = await reply.send(ctx)

            valid_choices = [str(i + 1) for i in range(len(channel_reminders))]
            choice = await InteractiveActions.wait_for_author_choice(ctx=ctx, valid_choices=valid_choices)

            if choice is not None:
                reminder_to_delete = channel_reminders[choice]
                await self._delete_reminder(reminder=reminder_to_delete)
            await reply.edit_to_clean(prev_message=embed_msg)
