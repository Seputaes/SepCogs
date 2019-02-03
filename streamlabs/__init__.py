from redbot.core.bot import Red
from .streamlabs import Streamlabs


def setup(bot: Red):
    bot.add_cog(Streamlabs(bot))
