import discord

from cog_shared.seplib.utils import Result


def check_remind_role_permissions(role: discord.Role, channel: discord.TextChannel) -> Result:
    msg_result = bot_can_msg_channel(channel=channel)
    if not msg_result.success:
        return msg_result
    mention_result = bot_can_mention_role(role=role)
    return mention_result


def bot_can_msg_channel(channel: discord.TextChannel) -> Result:
    return Result.get_result(
        check=lambda: channel.permissions_for(channel.guild.me).send_messages,
        error="The bot does not have permissions to talk in that channel.",
    )


def bot_can_mention_role(role: discord.Role) -> Result:
    return Result.get_result(check=lambda: role.mentionable, error="That role is not able to be mentioned.")
