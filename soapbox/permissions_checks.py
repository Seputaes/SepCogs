import discord

from cog_shared.seplib.utils import Result


# TODO: NEEDS TRANSLATION


def check_configure_permissions(trigger: discord.VoiceChannel, category: discord.CategoryChannel) -> Result[bool]:
    """
    Verifies the bot's permissions to perform operations when configuring channel and category.
    :param trigger: Soapbox trigger channel specified by the user
    :param category: New VC category specified by the user
    :return: Result of the checks, with error message if not successful.
    """

    cat_manage = bot_can_manage_category(category=category)
    if not cat_manage.success:
        return cat_manage
    move_members = bot_can_move_members(channel=trigger)
    if not move_members.success:
        return move_members

    return Result(success=True, error=None, value=True)


def bot_can_manage_category(category: discord.CategoryChannel) -> Result[bool]:
    """
    Checks if the bot can manage channels in the specified category.
    :param category: Discord server category.
    :return: Result of the check, with error message if not successful.
    """
    if category.permissions_for(member=category.guild.me).manage_channels:
        return Result(success=True, value=True, error=None)
    return Result(
        success=False, value=False, error="The bot does not have permissions to manage channels in that category."
    )


def bot_can_move_members(channel: discord.VoiceChannel) -> Result[bool]:
    """
    Checks if the bot can move members in the specified trigger channel.
    :param channel: Trigger channel specified by the user.
    :return: Result of the check, with error message if not successful.
    """
    if channel.permissions_for(channel.guild.me).move_members:
        return Result(success=True, value=True, error=None)
    return Result(
        success=False,
        value=False,
        error="The bot does not have permissions to move members out of the trigger channel.",
    )
