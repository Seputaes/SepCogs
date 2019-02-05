import discord

from cog_shared.seplib.utils import Result


def check_remind_role_permissions(role: discord.Role, channel: discord.TextChannel) -> Result[bool]:
    msg_result = bot_can_msg_channel(channel=channel)
    if not msg_result.success:
        return msg_result
    mention_result = bot_can_mention_role(role=role)
    return mention_result


def bot_can_msg_channel(channel: discord.TextChannel) -> Result[bool]:
    if channel.permissions_for(channel.guild.me).send_messages:
        return Result(success=True, value=True, error=None)
    return Result(success=False, value=False, error="The bot does not have permissions to talk in that channel.")


def bot_can_mention_role(role: discord.Role) -> Result[bool]:
    if role.mentionable:
        return Result(success=True, error=None, value=True)
    return Result(success=False, value=False, error="That role is not able to be mentioned.")
