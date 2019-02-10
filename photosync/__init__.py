from redbot.core.bot import Red
from .photo_sync import PhotoSync


def setup(bot: Red):
    bot.add_cog(PhotoSync(bot))
