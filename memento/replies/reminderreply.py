from cog_shared.seplib.utils import HexColor
from memento.replies.mementoembedreply import MementoEmbedReply


class ReminderReply(MementoEmbedReply):
    def __init__(self, message: str):
        super(ReminderReply, self).__init__(message=message, title="Reminder!", color=HexColor.orange())
