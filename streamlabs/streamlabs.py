from typing import Dict, List

import discord

from cog_shared.seplib.cog import SepCog
from cog_shared.seplib.replies import ErrorReply
from cog_shared.seplib.utils import ContextWrapper, Result
from cog_shared.streamlabsapi.api import SLAPI
from cog_shared.streamlabsapi.commands.streamlabs_config import StreamlabsConfig
from cog_shared.streamlabsapi.replies import StreamlabsReply
from redbot.core import Config, commands, checks
from redbot.core.bot import Red
from redbot.core.commands import Context


class Streamlabs(SepCog, commands.Cog):
    def __init__(self, bot: Red):
        super(Streamlabs, self).__init__(bot=bot)

        self.guild_config_cache: Dict[int, Dict[str, object]] = {}
        self.guild_auth_cache: Dict[int, Dict[str, str]] = {}
        self.sl_api: Dict[int, SLAPI] = {}

        self._ensure_futures()

    async def _init_cache(self):
        """
        Load the guild config and token cache from the database.
        :return:
        """
        await self.bot.wait_until_ready()

        guilds = await self.config.all_guilds()

        guild_config = {}
        guild_auth = {}

        for guild_id, guild_dit in guilds.items():
            config = guild_dit.get("config")
            auth = guild_dit.get("auth")

            if config:
                guild_config[guild_id] = config

            if auth:
                guild_auth[guild_id] = auth

        self.guild_config_cache = guild_config
        self.guild_auth_cache = guild_auth

        for guild_id, guild_auth in self.guild_auth_cache.items():
            self._refresh_streamlabs_api(guild_id=guild_id, guild_auth=guild_auth)

    def _guild_is_configured(self, guild_id: int) -> bool:
        return guild_id in self.guild_auth_cache and "access_token" in self.guild_auth_cache.get(guild_id)

    def _refresh_streamlabs_api(self, guild_id: int, guild_auth: Dict) -> None:
        if self._guild_is_configured(guild_id=guild_id):
            self.sl_api[guild_id] = SLAPI(access_token=guild_auth.get("access_token"))
            return
        self.logger.info(f"No Streamlabs API access token found for guild: {guild_id}")

    def _register_config_entities(self, config: Config):
        # register configuration for guilds in Soapbox
        config.register_guild(config={})
        config.register_guild(auth={})

    def _get_guild_auth(self, guild: discord.Guild):
        return self.guild_auth_cache.get(guild.id, None)

    async def _update_guild_auth(self, auth: Dict):
        self.guild_auth_cache = auth
        for guild_id, guild_auth in self.guild_auth_cache.items():
            guild = self.bot.get_guild(guild_id)
            await self.config.guild(guild).auth.set(guild_auth)
        self.logger.info(f"Updated Auth config.")

    async def _check_command_guild_configured(self, ctx: Context):
        sl_api = self.sl_api.get(ctx.guild.id)
        if sl_api is None:
            await ErrorReply(
                message=f"Streamlabs is not configured for this guild. Run `{ctx.prefix}streamlabs config`"
            ).send(ctx)
            await ContextWrapper(ctx).cross()
            return False
        return sl_api

    @commands.group(name="streamlabs")
    @checks.admin_or_permissions()
    async def streamlabs(self, ctx: Context):
        """
        Main Streamlabs command entry point.
        """
        pass

    @streamlabs.command(name="guide")
    @checks.admin_or_permissions()
    async def streamlabs_guide(self, ctx: Context):
        """
        Explains the full process for configuring the Streamlabs cog. RUN THIS BEFORE CONFIGURING!
        """
        return await StreamlabsConfig.config_guide(ctx=ctx)

    @streamlabs.command(name="config")
    @checks.admin_or_permissions()
    async def streamlabs_config(self, ctx: Context, timeout: int = 60):
        """
        Starts the configuration wizard of the Streamlabs cog to hook up to your Streamlabs App and account.

        Be sure to run [p]streamlabs guide to fully understand how the process works.
        """
        updated_auth = await StreamlabsConfig.start_config(
            ctx=ctx, timeout=timeout, guild_auth_map=self.guild_auth_cache
        )
        if updated_auth:
            await self._update_guild_auth(auth=updated_auth)

    @streamlabs.command(name="continue")
    @checks.admin_or_permissions()
    async def streamlabs_continue(self, ctx: Context, timeout: int = 60):
        """
        Continue the configuration wizard of the Streamlabs cog.

        This must only be run after [p]streamlabs config has been successfully run.
        """
        updated_auth = await StreamlabsConfig.continue_config(
            ctx=ctx, timeout=timeout, guild_auth_map=self.guild_auth_cache
        )
        if updated_auth:
            await self._update_guild_auth(auth=updated_auth)
            self._refresh_streamlabs_api(guild_id=ctx.guild.id, guild_auth=updated_auth.get(ctx.guild.id, {}))

    @streamlabs.group(name="alert")
    @checks.admin_or_permissions()
    async def streamlabs_alert(self, ctx: Context):
        """
        Trigger Streamlabs alerts from within Discord!
        """
        pass

    @streamlabs_alert.command(name="follow")
    @checks.admin_or_permissions()
    async def streamlabs_alert_follow(self, ctx: Context, *, message: str):
        """
        Trigger a follow-type alert on Streamlabs.

        The message is exactly what will display as the alert message. You can indicate special text by surrounding
        it with single asterisks.

        For example: This is my *special* text.

        This text will be highlighted with the secondary color specified in your Streamlabs configuration.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        await sl_api.alerts.create_alert(type_="follow", message=message)

    @streamlabs_alert.command(name="subscription")
    @checks.admin_or_permissions()
    async def streamlabs_alert_subscription(self, ctx: Context, message: str, user_message: str):
        """
        Trigger a subscription-type alert on Streamlabs.

        The message is exactly what will display as the alert message. You can indicate special text by surrounding
        it with single asterisks.

        For example: This is my *special* text.

        This text will be highlighted with the secondary color specified in your Streamlabs configuration.

        The user_message is the sub-text that will display under the primary message.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        await sl_api.alerts.create_alert(type_="subscription", message=message, user_message=user_message)

    @streamlabs_alert.command(name="donation")
    @checks.admin_or_permissions()
    async def streamlabs_alert_donation(self, ctx: Context, message: str, user_message: str):
        """
        Trigger a donation-type alert on Streamlabs.

        The message is exactly what will display as the alert message. You can indicate special text by surrounding
        it with single asterisks.

        For example: This is my *special* text.

        This text will be highlighted with the secondary color specified in your Streamlabs configuration.

        The user_message is the sub-text that will display under the primary message.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        await sl_api.alerts.create_alert(type_="donation", message=message, user_message=user_message)

    @streamlabs_alert.command(name="host")
    @checks.admin_or_permissions()
    async def streamlabs_alert_host(self, ctx: Context, *, message: str):
        """
        Trigger a host-type alert on Streamlabs.

        The message is exactly what will display as the alert message. You can indicate special text by surrounding
        it with single asterisks.

        For example: This is my *special* text.

        This text will be highlighted with the secondary color specified in your Streamlabs configuration.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        await sl_api.alerts.create_alert(type_="host", message=message)

    @streamlabs_alert.command(name="mute")
    @checks.admin_or_permissions()
    async def streamlabs_alert_mute(self, ctx: Context):
        """
        Mute sound on all streamlabs alerts until the `[p]streamlabs alert unmute` command is run.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        result = await sl_api.alerts.mute_volume()
        if not result.success:
            return await ErrorReply(message=f"There was an error muting the alert volume: {result.error}").send(ctx)
        await ctx.tick()

    @streamlabs_alert.command(name="unmute")
    @checks.admin_or_permissions()
    async def streamlabs_alert_unmute(self, ctx: Context):
        """
        Unmute sound on all streamlabs alerts.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        result = await sl_api.alerts.unmute_volume()
        if not result.success:
            return await ErrorReply(message=f"There was an error unmuting the alert volume: {result.error}").send(ctx)
        await ctx.tick()

    @streamlabs_alert.command(name="pause")
    @checks.admin_or_permissions()
    async def streamlabs_alert_pause(self, ctx: Context):
        """
        Pause all Streamlabs alerts until the `[p]streamlabs alert unpause` command is run.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        result = await sl_api.alerts.pause_queue()
        if not result.success:
            return await ErrorReply(message=f"There was an error pausing the alert queue: {result.error}").send(ctx)
        await ctx.tick()

    @streamlabs_alert.command(name="unpause")
    @checks.admin_or_permissions()
    async def streamlabs_alert_unpause(self, ctx: Context):
        """
        Unpause the Streamlabs alert queue. This will allow the alerts which were paused to flow again.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        result = await sl_api.alerts.unpause_queue()
        if not result.success:
            return await ErrorReply(message=f"There was an error unpausing the alert queue: {result.error}").send(ctx)
        await ctx.tick()

    @streamlabs_alert.command(name="show_video")
    @checks.admin_or_permissions()
    async def streamlabs_alert_show_video(self, ctx: Context):
        """
        Toggle showing Streamlabs Media Share videos in the alert box.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        result = await sl_api.alerts.show_video()
        if not result.success:
            return await ErrorReply(message=f"There was an error showing the Media Share video: {result.error}").send(
                ctx
            )
        await ctx.tick()

    @streamlabs_alert.command(name="hide")
    @checks.admin_or_permissions()
    async def streamlabs_alert_hide_video(self, ctx: Context):
        """
        Hides Streamlabs Media Share videos in the alert box.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        result = await sl_api.alerts.hide_video()
        if not result.success:
            return await ErrorReply(message=f"There was an error hiding the Media Share video: {result.error}").send(
                ctx
            )
        await ctx.tick()

    @streamlabs.group(name="donations")
    @checks.admin_or_permissions()
    async def streamlabs_donations(self, ctx: Context):
        """
        Get and create Streamlabs donations!
        """
        pass

    @streamlabs_donations.command(name="list")
    @checks.admin_or_permissions()
    async def streamlabs_donations_list(
        self,
        ctx: Context,
        limit: int = None,
        before: int = None,
        after: int = None,
        currency: str = None,
        verified: bool = None,
    ):
        """
        Lists Streamlabs donations based on the criteria you provide.

        :param limit: Maximum number of results to get.
        :param before: Limits the donations to those before a certain donation ID.
        :param after: Limits the donations to those after a certain donation ID.
        :param currency: Limits the donations to specified currency code: https://dev.streamlabs.com/docs/currency-codes
        :param verified: Boolean to indicate whether you only want verified donations.
        """
        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return

        donations = await sl_api.donations.get_donations(
            limit=limit, before=before, after=after, currency=currency, verified=verified
        )
        donations_list: List[Dict] = donations.get("data")

        if not donations_list:
            return await StreamlabsReply(
                message="You have no donations that match that criteria.", title="Donation List"
            ).send(ctx)
        else:
            message = "Here's a list of the donations that match your criteria:\n\n"
            for index, donation in enumerate(donations_list):
                num = index + 1
                name = donation.get("name")
                amount = donation.get("amount")
                currency = donation.get("currency")
                message += f"{num}. Name: {name} | Amount: {amount} | Currency: {currency}\n"
            return await StreamlabsReply(message=message, title="Donation List").send(ctx)

    @streamlabs_donations.command(name="create")
    @checks.admin_or_permissions()
    async def streamlabs_donation_create(
        self,
        ctx: Context,
        name: str,
        identifier: str,
        amount: float,
        currency: str,
        message: str = None,
        created_at: str = None,
        skip_alert: bool = False,
    ):
        """
        Creates a new Streamlabs donation.

        :param name: The name of the donor. Has to be between 2-25 chars and can only be alphanumeric + underscores.
        :param identifier: An identifier for this donor, which is used to group donations with the same donor.
                           For example, if you create more than one donation with the same identifier,
                           they will be grouped together as if they came from the same donor.
                           Typically this is best suited as an email address, or a unique hash.
        :param amount: The amount of this donation.
        :param currency: The 3 letter currency code for this donation: https://dev.streamlabs.com/docs/currency-codes
        :param message: The message from the donor. Must be < 255 characters
        :param created_at: A timestamp that identifies when this donation was made. Defaults to Now.
        :param skip_alert:Boolean to indicate whether the alert should be skipped when the donation is posted.
        :return: Prints out the new Donation ID
        """

        sl_api = await self._check_command_guild_configured(ctx=ctx)
        if not sl_api:
            return
        response = await sl_api.donations.create_donation(
            name=name,
            identifier=identifier,
            amount=amount,
            currency=currency,
            message=message,
            created_at=created_at,
            skip_alert=skip_alert,
        )
        if isinstance(response, Result) and not response.success:
            return await ErrorReply(message=response.error).send(ctx)
        await StreamlabsReply(message=f"Donation created with ID: {response}", title="Donation Created").send(ctx)
