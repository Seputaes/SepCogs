import discord

from cog_shared.seplib.replies import EmbedReply
from cog_shared.seplib.utils import HexColor


class SoapboxEmbedReply(EmbedReply):

    TITLE_EMOJI = "\N{PUBLIC ADDRESS LOUDSPEAKER}"

    def __init__(self, message: str, title: str, color=HexColor.orange()):
        super(SoapboxEmbedReply, self).__init__(message=message, emoji=None, color=color)
        self.title_text = f"{title} [Soapbox]"
        self.TITLE = f"{self.TITLE_EMOJI} {self.title_text}"

    def build(self):
        return discord.Embed(description=self.build_message(), color=self.color, title=self.TITLE)
