from typing import Dict, Set

import discord


class Modification(object):
    def __init__(self, member: discord.Member, actions: Dict[bool, Set]):
        self.member = member
        self.actions = actions
