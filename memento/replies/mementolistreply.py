from typing import List

import discord

from memento.reminders import Reminder
from memento.replies import MementoEmbedReply


class MementoListReply(MementoEmbedReply):
    def __init__(self, reminders: List[Reminder], title: str):
        super(MementoListReply, self).__init__(message="", title=title)

        self.reminders = sorted(reminders, key=lambda k: k.dt)

    def build_message(self):
        raise NotImplementedError("Cannot run build message from this class.")

    def build_delete_msg(self):
        message = self.build_message()
        message += "\nYou can delete any of these reminders by replying with its number."
        return message

    def build(self):
        return discord.Embed(description=self.build_delete_msg(), color=self.color, title=self.TITLE)

    def build_clean(self):
        return discord.Embed(description=self.build_message(), color=self.color, title=self.TITLE)

    async def edit_to_clean(self, prev_message: discord.Message):
        await prev_message.edit(embed=self.build_clean())
