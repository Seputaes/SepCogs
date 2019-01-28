import discord
from discord import Colour

from cog_shared.seplib.replies import EmbedReply
from cog_shared.seplib.utils import HexColor


class MementoEmbedReply(EmbedReply):

    TITLE_EMOJI = "\N{TIMER CLOCK}"

    def __init__(self, message: str, title: str, color: Colour = HexColor.purple()):
        super(MementoEmbedReply, self).__init__(message=message, emoji=None, color=color)
        self.title_text = f"{title} [Memento]"
        self.TITLE = f"{self.TITLE_EMOJI} {self.title_text}"

    def build(self):
        return discord.Embed(description=self.build_message(), color=self.color, title=self.TITLE)
