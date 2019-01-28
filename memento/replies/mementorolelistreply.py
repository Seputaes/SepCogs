from datetime import datetime
from typing import List

import discord
import timeago

from memento.reminders import RoleReminder
from memento.replies.mementolistreply import MementoListReply


class MementoRoleListReply(MementoListReply):
    def __init__(self, reminders=List[RoleReminder]):
        super(MementoRoleListReply, self).__init__(reminders=reminders, title="Role Active Reminders")
        self.role: discord.Role = self.reminders[0].role

    def build_message(self):
        message = f"Here's the active reminders for role `{self.role.name}`:\n\n"
        for index, reminder in enumerate(self.reminders):
            count = index + 1
            time_string = timeago.format(date=reminder.dt, now=datetime.utcnow())
            message += "{}. **{}** | {}\n".format(count, reminder.text, time_string)
            message += f"  - Channel: {reminder.channel.mention}\n"
        return message
