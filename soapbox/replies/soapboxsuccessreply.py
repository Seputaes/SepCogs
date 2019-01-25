from cog_shared.seplib.utils import HexColor
from soapbox.replies import SoapboxEmbedReply


class SoapboxSuccessReply(SoapboxEmbedReply):
    def __init__(self, message: str, title: str = "Success!"):
        super(SoapboxSuccessReply, self).__init__(
            message=message, title=title, color=HexColor.success()
        )
