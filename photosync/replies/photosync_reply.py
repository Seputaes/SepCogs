import discord
from discord import Color

from cog_shared.seplib.replies import EmbedReply
from cog_shared.seplib.utils import HexColor


class PhotoSyncReply(EmbedReply):
    def __init__(self, message: str, title: str, color: Color = HexColor.gold()):
        super(PhotoSyncReply, self).__init__(message=message, emoji=None, color=color)
        self.TITLE = title

    def build(self):
        embed = discord.Embed(description=self.build_message(), color=self.color, title=self.TITLE)
        embed.set_author(name="PhotoSync Cog by Seputaes")
        return embed
