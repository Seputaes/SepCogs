from cog_shared.seplib.utils import HexColor
from memento.replies import MementoEmbedReply


class MementoErrorReply(MementoEmbedReply):
    def __init__(self, message: str, title: str = "Error!"):
        super(MementoErrorReply, self).__init__(message=message, title=title, color=HexColor.error())
