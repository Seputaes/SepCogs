from datetime import datetime
from typing import List

import discord
import timeago

from memento.reminders import RoleReminder
from memento.replies.mementolistreply import MementoListReply


class MementoChannelListReply(MementoListReply):
    def __init__(self, reminders=List[RoleReminder]):
        super(MementoChannelListReply, self).__init__(reminders=reminders, title="Channel Active Reminders")
        self.channel: discord.TextChannel = self.reminders[0].channel

    def build_message(self):
        message = f"Here's the active reminders for channel {self.channel.mention}:\n\n"
        for index, reminder in enumerate(self.reminders):
            count = index + 1
            time_string = timeago.format(date=reminder.dt, now=datetime.utcnow())
            message += "{}. **{}** | {}\n".format(count, reminder.text, time_string)
            message += f"  - Role: `{reminder.role.name}`\n"
        return message
