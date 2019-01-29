from typing import Optional

import discord

from cog_shared.seplib.utils import Result


def get_liverole_action(before: discord.Member, after: discord.Member) -> Optional[bool]:
    """
    Checks the 4 possible states of activity, and returns True/False if this will be an add/remove action,
    or None if it should not trigger the LiveRole.
    :param before: Discord Member state before the update event
    :param after: Discord Member state after the update event
    :return: True/False for Add/Remove, or None if not a LiveRole update.
    """
    if isinstance(before.activity, discord.Streaming) and isinstance(after.activity, discord.Streaming):
        return None
    elif isinstance(after.activity, discord.Streaming):
        return True
    elif isinstance(before.activity, discord.Streaming):
        return False
    else:
        return None


def bot_can_manage_roles(guild: discord.Guild) -> Result:
    return Result.get_result(
        check=lambda: guild.me.guild_permissions.manage_roles,
        error="This bot is not allowed to manage roles on this server.",
    )
