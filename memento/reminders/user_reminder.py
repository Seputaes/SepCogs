from typing import Dict, Optional

import discord

from redbot.core.bot import Red

from memento.reminders import Reminder


class UserReminder(Reminder):
    def __init__(self, bot: Red, dt_str: str, text: str, timezone: str, created_by_id: int, id_: str = None):
        super(UserReminder, self).__init__(
            bot=bot, dt_str=dt_str, text=text, timezone=timezone, created_by_id=created_by_id, id_=id_
        )

    @property
    def messageable(self) -> discord.abc.Messageable:
        return self.created_by

    @property
    def mention(self) -> Optional[str]:
        return None

    def prepare_for_storage(self) -> Dict:
        return self._base_pfs()
