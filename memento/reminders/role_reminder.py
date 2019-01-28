from typing import Dict

from discord import TextChannel, Role
from discord.abc import Messageable

from redbot.core.bot import Red

from memento.reminders import Reminder


class RoleReminder(Reminder):
    def __init__(
        self,
        bot: Red,
        dt_str: str,
        text: str,
        timezone: str,
        created_by_id: int,
        role_id: int,
        channel_id: int,
        id_: str = None,
    ):
        super(RoleReminder, self).__init__(
            bot=bot, dt_str=dt_str, text=text, timezone=timezone, created_by_id=created_by_id, id_=id_
        )
        self.role_id = role_id
        self.channel_id = channel_id
        self.channel: TextChannel = bot.get_channel(channel_id)
        self.role: Role = self.channel.guild.get_role(role_id=role_id) if self.channel is not None else None

    @property
    def messageable(self) -> Messageable:
        return self.channel

    @property
    def mention(self) -> str:
        return self.role.mention

    def prepare_for_storage(self) -> Dict:
        base = self._base_pfs()
        base.update({"role_id": self.role_id, "channel_id": self.channel_id})
        return base
