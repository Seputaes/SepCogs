from datetime import datetime
from typing import List

import timeago

from memento.reminders import UserReminder
from memento.replies.mementolistreply import MementoListReply


class MementoUserListReply(MementoListReply):
    def __init__(self, reminders=List[UserReminder]):
        super(MementoUserListReply, self).__init__(reminders=reminders, title="Your Active Reminders")

    def build_message(self):
        message = f"Here's your active reminders:\n\n"
        for index, reminder in enumerate(self.reminders):
            count = index + 1
            time_string = timeago.format(date=reminder.dt, now=datetime.utcnow())
            message += "{}. **{}** | {}\n".format(count, reminder.text, time_string)
        return message
