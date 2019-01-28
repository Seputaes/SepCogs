import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict

import discord
import pytz
from pytz.tzinfo import DstTzInfo

from redbot.core.bot import Red


class Reminder(ABC):

    ISO8601_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, bot: Red, dt_str: str, text: str, timezone: str, created_by_id: int, id_: str = None):
        self._bot = bot
        self.id_ = (
            id_ if id_ is not None else self.generate_unique_id(text=text, dt_str=dt_str, created_by_id=created_by_id)
        )
        self.dt_str = dt_str
        self.dt = datetime.strptime(dt_str, self.ISO8601_FORMAT)
        self.text = text
        self.timezone = timezone
        self.tz_info: DstTzInfo = pytz.timezone(timezone)
        self.created_by_id = created_by_id
        self.created_by: discord.User = bot.get_user(created_by_id)

    @staticmethod
    def generate_unique_id(text: str, dt_str: str, created_by_id: int) -> str:
        key = f"{text}{dt_str}{created_by_id}"
        return hashlib.sha1(key.encode("UTF-8")).hexdigest()[0:8]

    def _base_pfs(self) -> Dict:
        return {
            "id_": self.id_,
            "dt_str": self.dt_str,
            "text": self.text,
            "timezone": self.timezone,
            "created_by_id": self.created_by_id,
        }

    @property
    @abstractmethod
    def messageable(self) -> discord.abc.Messageable:
        raise NotImplementedError("Unable to retrieve this property from the abstract class")

    @property
    @abstractmethod
    def mention(self):
        raise NotImplementedError("Unable to retrieve this property from the abstract class")

    @abstractmethod
    def prepare_for_storage(self) -> Dict:
        raise NotImplementedError("Unable to call this method from the abstract class")
