import os
from datetime import datetime, timedelta
from typing import Dict, Optional

import aiohttp
import discord

from cog_shared.seplib.cog import SepCog
from cog_shared.seplib.replies import ErrorReply, SuccessReply
from cog_shared.seplib.utils import Result
from photosync.apis import GooglePhotos
from photosync.configs import GooglePhotosConfig
from redbot.core import Config, checks
from redbot.core.bot import Red
from redbot.core.commands import Context, commands, guild_only


class PhotoSync(SepCog):

    UPLOAD_URL = "https://photoslibrary.googleapis.com/v1/uploads"

    DISCORD_IMG_REQ_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0"
    }

    SCOPES = [
        "https://www.googleapis.com/auth/photoslibrary",
        "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata",
        "https://www.googleapis.com/auth/photoslibrary.sharing",
    ]

    def __init__(self, bot: Red):
        super(PhotoSync, self).__init__(bot=bot)

        self.guild_google_auth_config: Dict[int, Dict[str, str]] = {}
        self.guild_google_maps_config: Dict[int, Dict[str, str]] = {}
        self._guild_google_apis: Dict[int, GooglePhotos] = {}

        self._ensure_futures()

    async def _init_cache(self):
        await self.bot.wait_until_ready()

        guilds = await self.config.all_guilds()
        guild_google_auth = {}
        guild_google_maps = {}

        for guild_id, guild_dict in guilds.items():
            google_auth = guild_dict.get("google_auth")
            google_maps = guild_dict.get("google_maps")

            if google_auth:
                guild_google_auth[guild_id] = google_auth

            if google_maps:
                guild_google_maps[guild_id] = google_maps

        self.guild_google_auth_config = guild_google_auth
        self.guild_google_maps_config = guild_google_maps

    def _register_config_entities(self, config: Config):
        config.register_guild(google_auth={})
        config.register_guild(google_maps={})

    async def _get_google_api(self, guild: discord.Guild) -> Optional[GooglePhotos]:

        current_api = self._guild_google_apis.get(guild.id)

        if not current_api:

            guild_google_auth = self._get_guild_auth(guild=guild, service="google")
            if not guild_google_auth:
                return
            expires_str = guild_google_auth.get("expires")
            expires_dt = datetime.strptime(expires_str, "%Y-%m-%dT%H:%M:%SZ")
            current_api = GooglePhotos(
                access_token=guild_google_auth.get("access_token"),
                refresh_token=guild_google_auth.get("refresh_token"),
                expires=expires_dt,
            )
            refresh_data = await current_api.refresh_access_token(
                client_id=guild_google_auth.get("client_id"), client_secret=guild_google_auth.get("client_secret")
            )
            if refresh_data:
                new_expires = datetime.utcnow() + timedelta(seconds=refresh_data.get("expires_in"))
                refresh_data["expires"] = new_expires.strftime("%Y-%m-%dT%H:%M:%SZ")
                guild_google_auth.update(refresh_data)
                await self._update_guild_auth(guild=guild, service="google", auth=guild_google_auth)
        return current_api

    async def _add_google_mapping(self, guild: discord.Guild, channel: discord.TextChannel, album_name: str):
        current_map = self.guild_google_maps_config.get(guild.id, {})
        current_map[str(channel.id)] = album_name
        self.guild_google_maps_config[guild.id] = current_map
        await self.config.guild(guild=guild).google_maps.set(current_map)
        self.logger.info(f"Added Google Photos mapping: Channel: {channel.name}|{channel.id} | Album: {album_name}")

    def _get_google_album_name(self, channel: discord.TextChannel) -> Optional[str]:
        return self.guild_google_maps_config.get(channel.guild.id, {}).get(str(channel.id))

    async def _update_guild_auth(self, guild: discord.Guild, service: str, auth: Dict):

        if service == "google":
            self.guild_google_auth_config[guild.id] = auth
            await self.config.guild(guild=guild).google_auth.set(auth)
            self.logger.info(f"Updated Google Auth config for Guild: {guild.name}|{guild.id}.")
        else:
            self.logger.error(f"Unknown service {service}")
            return None

    def _get_guild_auth(self, guild: discord.Guild, service: str) -> Optional[Dict]:
        if service == "google":
            return self.guild_google_auth_config.get(guild.id)
        self.logger.error(f"Unknown service {service}")

    async def _get_google_album_id(self, guild: discord.Guild, album_name: str) -> Result[Optional[str]]:
        guild_api = await self._get_google_api(guild=guild)
        if not guild_api:
            return Result(success=False, error=f"Google Photos is not configure for Guild: {guild.id}", value=None)
        result = await guild_api.api.get_album_list()
        if not result.success:
            return result

        albums = result.value
        for album in albums:
            if album_name.lower() == album.get("title", "").lower():
                return Result(success=True, value=album.get("id"), error=None)

        # album does not exist, create it
        album_payload = {"title": album_name}
        create_result = await guild_api.api.create_album(album=album_payload)
        if not create_result.success:
            return create_result
        album_id = create_result.value.get("id")

        return Result(success=True, value=album_id, error=None)

    @staticmethod
    def _get_photo_urls_from_message(message: discord.Message):
        photo_urls = set()
        for attachment in message.attachments:
            if attachment.height is not None and attachment.width is not None:
                photo_urls.add(attachment.url)
        return photo_urls

    async def _get_discord_image(self, url: str) -> Optional[bytes]:
        async with aiohttp.ClientSession(headers=self.DISCORD_IMG_REQ_HEADERS) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()

    async def _upload_google_photo_and_get_token(self, guild: discord.Guild, photo_url: str) -> Result[Optional[str]]:
        discord_img = await self._get_discord_image(url=photo_url)
        if not discord_img:
            return Result(success=False, error="Unable to get Discord image", value=None)

        guild_api = await self._get_google_api(guild=guild)
        if not guild_api:
            return Result(success=False, error=f"Google API is not set up for guild {guild.id}", value=None)

        upload_result = await guild_api.api.upload_image(image_bytes=discord_img)
        return upload_result

    @staticmethod
    def _check_channel_permissions(channel: discord.TextChannel) -> Result:
        if channel.guild is None:
            return Result(success=False, error="Specified channel is not part of the server", value=None)
        elif not channel.permissions_for(channel.guild.me).read_messages:
            return Result(success=False, error="Bot does not have permissions to read that channel.", value=None)
        return Result(success=True, error=None, value=None)


    @commands.group(name="photosync")
    @checks.admin_or_permissions()
    @guild_only()
    async def photosync(self, ctx: Context):
        """
        Main PhotoSync entry command.
        """
        pass

    @photosync.group(name="guide")
    @checks.admin_or_permissions()
    async def photosync_guide(self, ctx: Context):
        """
        Configuration Guides for the Service APIs.
        """
        pass

    @photosync_guide.command(name="google")
    @checks.admin_or_permissions()
    async def photosync_guide_google(self, ctx: Context):
        """
        Explains the full process of configuring the Google Photos API. RUN THIS BEFORE CONFIGURING!
        """
        return await GooglePhotosConfig.config_guide(ctx=ctx)

    @photosync.group(name="config")
    @checks.admin_or_permissions()
    async def photosync_config(self, ctx: Context):
        """
        Configures the service APIs for PhotoSync.
        """
        pass

    @photosync_config.command(name="google")
    @checks.admin_or_permissions()
    async def photosync_config_google(self, ctx: Context, timeout: int = 60):
        """
        Starts the configuration wizard of the Google Photos API configuration.

        Be sure to run `[p]photosync guide` google to fully understand how the process works.

        :timeout: How much time you have in between each data entry command to enter its value.
        """
        updated_auth = await GooglePhotosConfig.start_config(ctx=ctx, timeout=timeout)
        if updated_auth:
            await self._update_guild_auth(guild=ctx.guild, auth=updated_auth, service="google")

    @photosync.group(name="continue")
    @checks.admin_or_permissions()
    async def photosync_continue(self, ctx: Context):
        """
        Continuation of the API configuration.
        """
        pass

    @photosync_continue.command(name="google")
    @checks.admin_or_permissions()
    async def photosync_continue_google(self, ctx: Context, timeout: int = 60):
        """
        Continue the configuration wizard for the Google Photos API.

        This must only be run after `[p]photosync config google` has been successfully run.

        :timeout: How much time you have in between each data entry command to enter its value
        """
        updated_auth = await GooglePhotosConfig.continue_config(
            ctx=ctx, auth_data=self._get_guild_auth(service="google", guild=ctx.guild), timeout=timeout
        )
        if updated_auth:
            await self._update_guild_auth(auth=updated_auth, guild=ctx.guild, service="google")
            # TODO: self._refresh_google_api(guild_id=ctx.guild.id, guild_auth=updated_auth)

    @photosync.group(name="map")
    @checks.admin_or_permissions()
    async def photosync_map(self, ctx: Context):
        """
        Map channels to service albums/folders.
        """
        pass

    @photosync_map.command(name="google")
    @checks.admin_or_permissions()
    async def photosync_map_google(self, ctx: Context, channel: discord.TextChannel, album_name: str):
        """
        Maps a discord channel to a Google Photos album by its name.

        You must first configure the Google Photos API with `[p]photosync config google`
        """
        channel_checks = self._check_channel_permissions(channel=channel)
        if not channel_checks.success:
            return ErrorReply(message=channel_checks.error).send(ctx)
        await self._add_google_mapping(guild=ctx.guild, channel=channel, album_name=album_name)
        return await ctx.tick()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Discord event to upload Google Photos.
        """

        if not isinstance(message.channel, discord.TextChannel):
            return

        album_name = self._get_google_album_name(channel=message.channel)
        if album_name is None:
            return

        album_id = await self._get_google_album_id(guild=message.guild, album_name=album_name)
        if not album_id.success:
            return
        album_id = album_id.value

        guild_api = await self._get_google_api(guild=message.guild)
        if not guild_api:
            self.logger.warning(f"Google Photos API is not configured for guild: {message.guild.id}")

        photo_urls = self._get_photo_urls_from_message(message=message)
        if not photo_urls:
            return

        for url in photo_urls:
            upload_result = await self._upload_google_photo_and_get_token(guild=message.guild, photo_url=url)
            if not upload_result.success:
                self.logger.error(upload_result.error)
                continue
            token = upload_result.value
            file_name = os.path.basename(url)

            batch_result = await guild_api.api.batch_create(album_id=album_id, upload_token=token, file_name=file_name)
            if not batch_result.success:
                self.logger.error(batch_result.error)
                continue
        await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @photosync.command(name="album")
    async def photosync_album(self, ctx: Context, *, album_name: str):
        result = await self._get_google_album_id(guild=ctx.guild, album_name=album_name)
        if not result.success:
            return await ErrorReply(message=result.error).send(ctx)
        return await SuccessReply(message=result.value).send(ctx)
