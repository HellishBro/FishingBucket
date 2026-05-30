from abc import abstractmethod, ABC

import fluxer
import discord

from .enums import Platform
from ..interaction import Interactions, Interaction


class Context[Bot, Message, Embed, Attachment, Member, User, Channel, Guild, Role](ABC):
    def __init__(self, platform: Platform, bot: Bot, message: Message):
        self.platform = platform
        self.bot = bot
        self.message = message

    @abstractmethod
    async def reply(self, content: str, embeds: list[Embed] = None, attachments: list[Attachment] = None, **kwargs) -> Message: pass

    @property
    @abstractmethod
    def author(self) -> User: pass

    @property
    @abstractmethod
    def channel(self) -> Channel: pass

    @property
    @abstractmethod
    def guild(self) -> Guild: pass

    @property
    @abstractmethod
    def is_bot(self) -> bool: pass

    @property
    @abstractmethod
    def message_content(self) -> str: pass

    @abstractmethod
    async def get_member(self, user_id: int) -> Member | None: pass

    @abstractmethod
    async def get_user(self, user_id: int) -> User | None: pass

    @abstractmethod
    async def get_channel(self, channel_id: int) -> Channel | None: pass

    @abstractmethod
    async def get_role(self, role_id: int) -> Role | None: pass

    @abstractmethod
    async def get_roles(self) -> list[Role]: pass


class FluxerContext(Context[fluxer.Bot, fluxer.Message, fluxer.Embed, fluxer.File, fluxer.GuildMember, fluxer.User, fluxer.Channel, fluxer.Guild, fluxer.Role]):
    async def interact_to_delete(self, event: fluxer.models.RawReactionActionEvent):
        if event.emoji.name == "❌":
            await self.bot.delete_message(event.channel_id, event.message_id)
            return {"pop": True}
        return None

    async def reply(self, content: str, embeds: list[fluxer.Embed] = None, attachments: list[fluxer.File] = None, **kwargs) -> fluxer.Message:
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

    @property
    def message_content(self) -> str:
        return self.message.content

    async def get_member(self, user_id: int) -> fluxer.GuildMember | None:
        try:
            return await self.guild.fetch_member(user_id)
        except fluxer.errors.NotFound:
            return None

    async def get_user(self, user_id: int) -> fluxer.User | None:
        try:
            return await self.bot.fetch_user(str(user_id))
        except fluxer.errors.NotFound:
            return None

    async def get_channel(self, channel_id: int) -> fluxer.Channel | None:
        try:
            return await self.bot.fetch_channel(str(channel_id))
        except fluxer.errors.NotFound:
            return None

    async def get_role(self, role_id: int) -> fluxer.Role | None:
        roles = await self.get_roles()
        appropriate_roles = [role for role in roles if role.id == role_id]
        return appropriate_roles[0] if appropriate_roles else None

    async def get_roles(self) -> list[fluxer.Role]:
        return await self.guild.fetch_roles()


class DiscordContext(Context[discord.Bot, discord.Message, discord.Embed, discord.File, discord.Member, discord.User, discord.TextChannel | discord.DMChannel, discord.Guild, discord.Role]):
    async def interact_to_delete(self, event: discord.RawReactionActionEvent):
        if event.emoji.name == "❌":
            await (await (await self.bot.fetch_channel(event.channel_id)).fetch_message(event.message_id)).delete()
            return {"pop": True}
        return None

    async def reply(self, content: str, embeds: list[discord.Embed] = None, attachments: list[discord.File] = None, **kwargs) -> discord.Message:
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

    @property
    def message_content(self) -> str:
        return self.message.content

    async def get_member(self, user_id: int) -> discord.Member | None:
        try:
            return await self.guild.fetch_member(user_id)
        except discord.HTTPException:
            return None

    async def get_user(self, user_id: int) -> discord.User | None:
        try:
            return await self.bot.fetch_user(user_id)
        except discord.HTTPException:
            return None

    async def get_channel(self, channel_id: int) -> discord.TextChannel | None:
        try:
            return await self.guild.fetch_channel(channel_id)
        except discord.HTTPException:
            return None

    async def get_role(self, role_id: int) -> discord.Role | None:
        try:
            return await self.guild.fetch_role(role_id)
        except discord.HTTPException:
            return None

    async def get_roles(self) -> list[discord.Role]:
        return await self.guild.fetch_roles()