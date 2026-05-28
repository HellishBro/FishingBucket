from abc import abstractmethod, ABC

import fluxer
import discord

from .enums import Platform
from ..interaction import Interactions, Interaction


class Context[Bot, Message, Embed, Attachment, Member, User, Channel, Guild](ABC):
    def __init__(self, platform: Platform, bot: Bot, message: Message):
        self.platform = platform
        self.bot = bot
        self.message = message

    @abstractmethod
    async def reply(self, content: str, embeds: list[Embed], attachments: list[Attachment], **kwargs) -> Message: pass

    @abstractmethod
    @property
    def author(self) -> User: pass

    @abstractmethod
    @property
    def channel(self) -> Channel: pass

    @abstractmethod
    @property
    def guild(self) -> Guild: pass

    @abstractmethod
    @property
    def is_bot(self) -> bool: pass

    @abstractmethod
    async def get_member(self, user_id: int) -> Member: pass


class FluxerContext(Context[fluxer.Bot, fluxer.Message, fluxer.Embed, fluxer.File, fluxer.GuildMember, fluxer.User, fluxer.Channel, fluxer.Guild]):
    async def interact_to_delete(self, event: fluxer.models.RawReactionActionEvent):
        if event.emoji.name == "❌":
            await self.bot.delete_message(event.channel_id, event.message_id)
            return {"pop": True}
        return None

    async def reply(self, content: str, embeds: list[fluxer.Embed], attachments: list[fluxer.File], **kwargs) -> fluxer.Message:
        try:
            msg = await self.message.reply(content, embeds=embeds, files=attachments, **kwargs)
        except fluxer.errors.NotFound:
            msg = await self.message.channel.send((f"<@{self.message.author.id}>\n" if not self.is_bot else "") + content,
                                             embeds=embeds, files=attachments, **kwargs)

        Interactions.instance.add_interaction(msg.id, Interaction(self.message.author.id, self.interact_to_delete))
        return msg

    @property
    def author(self) -> fluxer.User:
        return self.message.author

    @property
    def channel(self) -> fluxer.Channel:
        return self.message.channel

    @property
    def is_bot(self) -> bool:
        return self.author.bot

    @property
    def guild(self) -> fluxer.Guild:
        return self.message.guild

    async def get_member(self, user_id: int) -> fluxer.GuildMember:
        return await self.guild.fetch_member(user_id)


class DiscordContext(Context[discord.Bot, discord.Message, discord.Embed, discord.File, discord.Member, discord.User, discord.TextChannel | discord.DMChannel, discord.Guild]):
    async def interact_to_delete(self, event: discord.RawReactionActionEvent):
        if event.emoji.name == "❌":
            await (await (await self.bot.fetch_channel(event.channel_id)).fetch_message(event.message_id)).delete()
            return {"pop": True}
        return None

    async def reply(self, content: str, embeds: list[discord.Embed], attachments: list[discord.File], **kwargs) -> discord.Message:
        try:
            msg = await self.message.reply(content, embeds=embeds, files=attachments, **kwargs)
        except discord.errors.NotFound:
            msg = await self.message.channel.send(
                (f"<@{self.message.author.id}>\n" if not self.is_bot else "") + content,
                embeds=embeds, files=attachments, **kwargs)

        Interactions.instance.add_interaction(msg.id, Interaction(self.message.author.id, self.interact_to_delete))
        return msg

    @property
    def author(self) -> discord.User:
        return self.message.author

    @property
    def channel(self) -> discord.TextChannel | discord.DMChannel:
        return self.message.channel

    @property
    def guild(self) -> discord.Guild:
        return self.message.guild

    @property
    def is_bot(self) -> bool:
        return self.author.bot

    async def get_member(self, user_id: int) -> discord.Member:
        return await self.guild.fetch_member(user_id)