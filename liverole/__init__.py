from redbot.core.bot import Red
from .liverole import LiveRole


def setup(bot: Red):
    bot.add_cog(LiveRole(bot))
