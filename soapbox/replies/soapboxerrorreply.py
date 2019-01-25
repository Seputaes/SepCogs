from cog_shared.seplib.utils import HexColor
from soapbox.replies import SoapboxEmbedReply


class SoapboxErrorReply(SoapboxEmbedReply):
    def __init__(self, message: str, title: str = "Error!"):
        super(SoapboxErrorReply, self).__init__(
            message=message, title=title, color=HexColor.error()
        )
