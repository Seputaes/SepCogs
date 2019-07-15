from typing import Optional, Dict, Union

import discord

from cog_shared.seplib.replies import ErrorReply, SuccessReply, InteractiveActions
from cog_shared.seplib.utils import GetReplyPredicate, ContextWrapper, Result, HexColor
from photosync.apis.google_photos import GoogleAuthorizeAPI, GoogleTokenAPI
from photosync.replies.photosync_reply import PhotoSyncReply
from redbot.core.commands import Context


class GooglePhotosConfig(object):
    @staticmethod
    async def config_guide(ctx: Context) -> discord.Message:
        message = (
            "Here's an overview of the steps you need to take to get Google Photos up and running:\n\n"
            "1. Log into your Google Account at https://console.developers.google.com/\n"
            "2. Create a new Project and give it a name\n"
            '3. Select the Project and click "+ ENALBE APIS AND SERVICES"\n'
            "4. Select Photos Library API and Enable.\n"
            "5. Go back to the Project Dashboard and to Credentials.\n"
            "6. Go to Oauth consent Screen and add an Application Name\n"
            "7. In the Scopes section, add the following scopes:\n"
            "  - https://www.googleapis.com/auth/photoslibrary\n"
            "  - https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata\n"
            "  - https://www.googleapis.com/auth/photoslibrary.sharing\n"
            "8. Save\n"
            "9. Go to Credentials > Create > OAuth Client ID. Select Web Application.\n"
            '10. Enter Name and for the Redirect URI, enter "https://localhost/gp_auth"\n'
            "  - **WARNING:** DO NOT enter a domain here that you do NOT have control over!\n"
            "11. Save. Make note of the Redirect URI, and the Client ID and Secret that appears when you save. "
            "You will need them later."
        )
        return await PhotoSyncReply(message=message, title="Google Photos API Configuration Guide").send(ctx)

    @staticmethod
    async def __config_welcome(ctx: Context, timeout: int) -> bool:
        welcome_title = "Google Photos Configuration [Part 1 of 6] - Streamlabs Application Setup"
        welcome_message = (
            f"{ctx.author.mention} Welcome to Google Photos configuration!\n\n"
            f"**WARNING:** Make sure you are running this configuration in a SECURE/PRIVATE CHANNEL!\n\n"
            f"The operations you will be performing will require telling me secret keys and codes. "
            f"I will do my best to clean them up, but there's still risk of them being exposed.\n\n"
            f"Again, execute this configuration in a **SECURE/PRIVATE CHANNEL**. This will be the last warning.\n\n"
        )
        welcome_embed = PhotoSyncReply(message=welcome_message, title=welcome_title).build()
        await ctx.send(content=ctx.author.mention, embed=welcome_embed)

        # confirmation of private channel

        confirm_title = "Google Photos Configuration - Private Channel Confirmation"
        confirm_message = "Please confirm that this channel is private"
        confirm_embed = PhotoSyncReply(message=confirm_message, title=confirm_title, color=HexColor.warning()).build()

        confirm_response = await InteractiveActions.yes_or_no_action(ctx=ctx, embed=confirm_embed, timeout=timeout)
        return confirm_response

    @staticmethod
    async def __config_get_response(ctx: Context, timeout: int, title: str, message: str):
        reply = PhotoSyncReply(message=message, title=title)
        await reply.send(ctx)

        predicate_check = GetReplyPredicate.string_reply(ctx=ctx, user=ctx.author)
        await ctx.bot.wait_for("message", check=predicate_check, timeout=timeout)
        response_text = predicate_check.result.clean_content
        await predicate_check.result.delete()
        return response_text

    @staticmethod
    async def __config_client_id(ctx: Context, timeout: int) -> str:
        title = "Google Photos Configruation [Part 2 of 6] - Client ID"
        message = "Please tell me the **Client ID** of your Google Photos App"
        return await GooglePhotosConfig.__config_get_response(ctx=ctx, timeout=timeout, message=message, title=title)

    @staticmethod
    async def __config_client_secret(ctx: Context, timeout: int) -> str:
        title = "Google Photos Configuration [Part 3 of 6] - Client Secret"
        message = "Please tell me the **Client Secret** of your Google Photos App"
        return await GooglePhotosConfig.__config_get_response(ctx=ctx, timeout=timeout, message=message, title=title)

    @staticmethod
    async def __config_redirect_uri(ctx: Context, timeout: int) -> str:
        title = "Google Photos Configuration [Part 4 of 6] - Redirect URI"
        message = "Please tell me the **Redirect URI** of your Google Photos App"
        return await GooglePhotosConfig.__config_get_response(ctx=ctx, timeout=timeout, message=message, title=title)

    @staticmethod
    async def __config_auth_code(ctx: Context, timeout: int = 60) -> str:
        title = "Google Photos Configuration [Part 6 of 6] - Enter Authorization Code"
        message = (
            "Great! In the address of the page you were redirected to (it probably won't load), "
            "tell me the **code** parameter.\n\n"
            "__**For example**__\n"
            "**Address:** `https://localhost/gp_auth?code=HrHiYOCo8N3xgL9tkk&scopes=photoslibrary`\n"
            "**Your Code:** `HrHiYOCo8N3xgL9tkk`\n\n"
        )
        return await GooglePhotosConfig.__config_get_response(ctx=ctx, timeout=timeout, message=message, title=title)

    @staticmethod
    async def __config_give_auth_url(ctx: Context, auth_url: str):
        title = "Google Photos Configuration [Part 5 of 6] - App Authorization"
        message = (
            f"You'll now need to **authorize** your Google Photos App to interact with you Google Photos account.\n\n"
            f"Please go to [this URL]({auth_url}) and authorize the App.\n\n"
        )
        next_step_message = (
            f"Once you've authorized the app and have been redirected (likely to a blank page), "
            f"please continue with command `{ctx.prefix}photosync continue google`"
        )
        embed = PhotoSyncReply(message=message, title=title).build()
        embed.add_field(name="Next Step", inline=False, value=next_step_message)
        return await ctx.send(content=ctx.author.mention, embed=embed)

    @staticmethod
    async def start_config(ctx: Context, timeout: int = 60) -> Optional[Dict[str, str]]:
        auth_data = {}

        # CONFIG INTRO MESSAGE
        confirmed = await GooglePhotosConfig.__config_welcome(ctx=ctx, timeout=timeout)
        if not confirmed:
            await ContextWrapper(ctx).cross()
            return

        # CLIENT ID
        client_id = await GooglePhotosConfig.__config_client_id(ctx=ctx, timeout=timeout)
        if not client_id:
            await ContextWrapper(ctx).cross()
            return
        auth_data["client_id"] = client_id

        # CLIENT SECRET
        client_secret = await GooglePhotosConfig.__config_client_secret(ctx=ctx, timeout=timeout)
        if not client_secret:
            await ContextWrapper(ctx).cross()
            return
        auth_data["client_secret"] = client_secret

        # REDIRECT URI
        redirect_uri = await GooglePhotosConfig.__config_redirect_uri(ctx=ctx, timeout=timeout)
        if not redirect_uri:
            await ContextWrapper(ctx).cross()
            return
        auth_data["redirect_uri"] = redirect_uri

        # ASK USER TO APPROVE APP
        auth_url = GoogleAuthorizeAPI.build_auth_url(client_id=client_id, redirect_uri=redirect_uri)
        await GooglePhotosConfig.__config_give_auth_url(ctx=ctx, auth_url=auth_url)
        return auth_data

    @staticmethod
    async def continue_config(
        ctx: Context, auth_data: Dict[str, str], timeout: int = 60
    ) -> Optional[Dict[str, Union[str, int]]]:
        if not all(k in auth_data for k in ["client_id", "client_secret", "redirect_uri"]):
            message = (
                f"Configuration for this guild is not started or complete. "
                f"Please run `{ctx.prefix}photosync config google` first."
            )
            return await ErrorReply(message=message).send(ctx)

        auth_code = await GooglePhotosConfig.__config_auth_code(ctx=ctx, timeout=timeout)
        if not auth_code:
            await ContextWrapper(ctx).cross()
            return

        result = await GoogleTokenAPI.get_access_token(
            client_id=auth_data.get("client_id"),
            client_secret=auth_data.get("client_secret"),
            redirect_uri=auth_data.get("redirect_uri"),
            auth_code=auth_code,
        )
        if not result.success:

            return await ErrorReply(
                message="Authentication check failed. Please ensure"
                "that the provided Auth Code is correct "
                "and Auth Code are correct."
            ).send(ctx)
        auth_data.update(result.value)
        await SuccessReply(message="Successfully authenticated to the Google API.").send(ctx)
        return auth_data
