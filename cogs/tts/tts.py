from typing import TYPE_CHECKING, List
from collections import defaultdict
import asyncio
import json
import re

from discord.ext.commands import (
    Cog,
    command,
    guild_only,
)
import discord

from lib.context import Context
from lib.database.query import select_user_setting, select_guild_setting, select_voice_dictionaries
from lib.database.models import UserVoicePreference, GuildVoicePreference, VoiceDictionary
from lib.checks import bot_connected_only, user_connected_only, voice_channel_only
from lib.tts import TextToSpeechEngine

if TYPE_CHECKING:
    from bot import MiniMaid


comment_compiled = re.compile(r"//.*[^\n]\n")


class TextToSpeechBase(Cog):
    def __init__(self, bot: 'MiniMaid') -> None:
        self.reading_guilds = {}
        self.bot = bot
        self.locks = defaultdict(asyncio.Lock)
        self.users = {}
        self.engines = {}
        self.english_dict = {}
        with open("dic.json", "r") as f:
            t = f.read()
            self.english_dict = json.loads(re.sub(comment_compiled, "", t))


class TextToSpeechCommandMixin(TextToSpeechBase):
    @command()
    @voice_channel_only()
    @user_connected_only()
    @guild_only()
    async def join(self, ctx: Context) -> None:
        command()
        if ctx.guild.id in self.reading_guilds.keys():
            await ctx.error("すでに接続しています", f"`{ctx.prefix}move`コマンドを使用してください。")
            return

        channel = ctx.author.voice.channel

        await channel.connect(timeout=30.0)
        self.reading_guilds[ctx.guild.id] = (ctx.channel.id, channel.id)
        await ctx.success("接続しました。")

    @command()
    @bot_connected_only()
    @guild_only()
    async def leave(self, ctx: Context) -> None:
        await ctx.guild.voice_client.disconnect(force=True)
        async with self.locks[ctx.guild.id]:
            del self.engines[ctx.guild.id]
            del self.reading_guilds[ctx.guild.id]
        del self.reading_guilds[ctx.guild.id]
        await ctx.success("切断しました。")

    @command()
    @voice_channel_only()
    @user_connected_only()
    @bot_connected_only()
    @guild_only()
    async def move(self, ctx: Context) -> None:
        await ctx.voice_client.disconnect()
        async with self.locks[ctx.guild.id]:
            del self.reading_guilds[ctx.guild.id]
        await ctx.author.voice.channel.connect(timeout=30.0)
        self.reading_guilds[ctx.guild.id] = (ctx.channel.id, ctx.author.voice.channel.id)
        await ctx.success("移動しました。")

    @command()
    async def skip(self, ctx: Context) -> None:
        self.bot.dispatch("skip_tts", ctx)


class TextToSpeechEventMixin(TextToSpeechBase):
    async def queue_text_to_speech(self, message: discord.Message) -> None:
        user_preference = await self.get_user_preference(message.author.id)
        engine = await self.get_engine(message.guild.id)
        if message.author.bot and not engine.guild_preference.read_bot:
            return
        source = await engine.generate_source(message, user_preference, self.english_dict)

        async with self.locks[message.guild.id]:
            voice_client: discord.VoiceClient = message.guild.voice_client
            if voice_client is None:
                return

            def check(ctx):
                return ctx.channel.id == message.channel.id and ctx.author.id == message.author.id

            event = asyncio.Event(loop=self.bot.loop)
            voice_client.play(source, after=lambda err: event.set())
            for coro in asyncio.as_completed([event.wait(), self.bot.wait_for("skip_tts", check=check, timeout=None)]):
                result = await coro
                if isinstance(result, Context):
                    voice_client.stop()
                    await result.success("skipしました。")

    async def get_engine(self, guild_id: int) -> TextToSpeechEngine:
        if guild_id in self.engines.keys():
            return self.engines[guild_id]
        async with self.bot.db.Session() as session:
            async with session.begin():
                result = await session.execute(select_guild_setting(guild_id))
                pref = result.scalars().first()
                if pref is not None:
                    e = TextToSpeechEngine(self.bot.loop, pref, await self.get_dictionaries(guild_id))
                    self.engines[guild_id] = e
                    return e
                new = GuildVoicePreference(guild_id=guild_id)
                session.add(new)
        e = TextToSpeechEngine(self.bot.loop, new, await self.get_dictionaries(guild_id))
        self.engines[guild_id] = e
        return e

    async def get_dictionaries(self, guild_id: int) -> List[VoiceDictionary]:
        async with self.bot.db.Session() as session:
            async with session.begin():
                result = await session.execute(select_voice_dictionaries(guild_id))
                return result.scalars().all()

    async def get_user_preference(self, user_id: int) -> UserVoicePreference:
        if user_id in self.users.keys():
            return self.users[user_id]

        async with self.bot.db.Session() as session:
            async with session.begin():
                result = await session.execute(select_user_setting(user_id))
                pref = result.scalars().first()
                if pref is not None:
                    self.users[user_id] = pref
                    return pref
                new = UserVoicePreference(user_id=user_id)
                session.add(new)
        self.users[user_id] = new
        return new

    @Cog.listener(name="on_message")
    async def read_text(self, message: discord.Message) -> None:
        if message.content is None:
            return
        if message.guild is None:
            return
        if message.guild.id not in self.reading_guilds.keys():
            return
        context = await self.bot.get_context(message, cls=Context)
        if context.command is not None:
            return

        text_channel_id, voice_channel_id = self.reading_guilds[message.guild.id]
        if message.channel.id != text_channel_id:
            return

        await self.queue_text_to_speech(message)

    @Cog.listener(name="on_user_preference_update")
    async def on_user_preference_update(self, preference: UserVoicePreference):
        self.users[preference.user_id] = preference

    @Cog.listener(name="on_guild_preference_update")
    async def on_guild_preference_update(self, preference: GuildVoicePreference):
        if preference.guild_id in self.engines.keys():
            self.engines[preference.guild_id].update_guild_preference(preference)

    @Cog.listener(name="on_voice_dictionary_add")
    async def dictionary_add(self, guild: discord.Guild, dic: VoiceDictionary):
        if guild.id in self.engines.keys():
            self.engines[guild.id].update_dictionary("add", dic)

    @Cog.listener(name="on_voice_dictionary_update")
    async def dictionary_update(self, guild: discord.Guild, dic: VoiceDictionary):
        if guild.id in self.engines.keys():
            self.engines[guild.id].update_dictionary("update", dic)

    @Cog.listener(name="on_voice_dictionary_remove")
    async def dictionary_remove(self, guild: discord.Guild, dic: VoiceDictionary):
        if guild.id in self.engines.keys():
            self.engines[guild.id].update_dictionary("remove", dic)


class TextToSpeechCog(TextToSpeechCommandMixin, TextToSpeechEventMixin):
    def __init__(self, bot: 'MiniMaid') -> None:
        super(TextToSpeechCog, self).__init__(bot)


def setup(bot: 'MiniMaid') -> None:
    return bot.add_cog(TextToSpeechCog(bot))
