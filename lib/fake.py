from discord.ext import commands
import discord
from typing import Optional


class FakeEmoji(discord.Emoji):
    def __init__(self, _id) -> None:
        self.id = _id

    def __eq__(self, other) -> bool:
        if isinstance(other, FakeEmoji):
            return other.id == self.id
        return False


class FakeBot(commands.Bot):
    def __init__(self) -> None:
        super(FakeBot, self).__init__("")

    def get_emoji(self, id: int) -> Optional[FakeEmoji]:
        if id == 1:
            return FakeEmoji(id)
        return None
