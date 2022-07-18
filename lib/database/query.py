from typing import Optional

from sqlalchemy.future import select
from sqlalchemy.sql import Select
from sqlalchemy.orm import selectinload

from lib.database.models import (
    Party,
    Poll,
    Choice,
    UserVoicePreference,
    GuildVoicePreference,
    VoiceDictionary,
    AudioTag,
    Feed,
    Reader,
    RecordedVoice
)


def select_party(guild_id: int, name: str) -> Select:
    return select(Party).where(Party.guild_id == guild_id).where(Party.name == name)


def select_parties(guild_id: int) -> Select:
    return select(Party).where(Party.guild_id == guild_id)


def create_poll(
        title: str,
        choices: list,
        limit: Optional[int],
        hidden: bool,
        guild_id: int,
        channel_id: int,
        message_id: int,
        owner_id: int) -> Poll:
    return Poll(
        title=title,
        limit=limit,
        hidden=hidden,
        choices=[Choice(emoji=str(emoji), value=str(value)) for (emoji, value) in choices],
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=message_id,
        owner_id=owner_id
    )


def get_poll_by_id(poll_id: int) -> Select:
    return select(Poll).where(Poll.id == poll_id).options(selectinload(Poll.choices).selectinload(Choice.votes))


def select_user_setting(user_id: int) -> Select:
    return select(UserVoicePreference).where(UserVoicePreference.user_id == user_id)


def select_guild_setting(guild_id: int) -> Select:
    return select(GuildVoicePreference).where(GuildVoicePreference.guild_id == guild_id)


def select_voice_dictionaries(guild_id: int) -> Select:
    return select(VoiceDictionary).where(VoiceDictionary.guild_id == guild_id)


def select_voice_dictionary(guild_id: int, before: str) -> Select:
    return select(VoiceDictionary).where(VoiceDictionary.guild_id == guild_id).where(VoiceDictionary.before == before)


def select_audio_tag(guild_id: int, name: str) -> Select:
    return select(AudioTag).where(AudioTag.guild_id == guild_id).where(AudioTag.name == name)


def select_audio_tags(guild_id: int) -> Select:
    return select(AudioTag).where(AudioTag.guild_id == guild_id)


def select_all_feeds() -> Select:
    return select(Feed).where(Feed.available).options(selectinload(Feed.readers))


def select_feed(url: str) -> Select:
    return select(Feed).where(Feed.available).where(Feed.url == url)


def select_reader(feed_id: int, channel_id: int) -> Select:
    return select(Reader).where(Reader.feed_id == feed_id).where(Reader.channel_id == channel_id)


def select_reader_by_id(reader_id: int) -> Select:
    return select(Reader).where(Reader.id == reader_id).options(selectinload(Reader.feed))


def select_reader_by_channel_id(channel_id: int) -> Select:
    return select(Reader).where(Reader.channel_id == channel_id).options(selectinload(Reader.feed))


def select_recorded_voice_by_uuid(uuid: str) -> Select:
    return select(RecordedVoice).where(RecordedVoice.uuid == uuid)
