import json
from datetime import datetime
from io import BytesIO
from typing import Literal

import aiohttp
import fluxer
import fluxer.http as fhttp
from aiohttp import ClientSession

from . import common as c
from .common import Embed, File
from .enums import Platform
from ..interaction import Interactions, Interaction


def from_embed(embed: Embed) -> fluxer.Embed:
    return fluxer.Embed(embed.title, embed.description, footer=embed.footer, thumbnail=embed.thumbnail_url)


def from_file(file: File) -> fluxer.File:
    return fluxer.File(BytesIO(file.data), filename=file.filename)


class Attachment(c.Attachment):
    raw: fluxer.models.Attachment

    @property
    def filename(self) -> str:
        return self.raw.filename

    async def read(self) -> bytes:
        async with ClientSession() as session:
            async with session.get(self.raw.proxy_url) as res:
                return await res.read()


class User(c.User):
    raw: fluxer.User
    bot: fluxer.Bot

    @property
    def is_bot(self) -> bool:
        return self.raw.bot

    @property
    def id(self) -> int:
        return self.raw.id

    @property
    def full_tag(self) -> str:
        return f"{self.raw.username}#{self.raw.discriminator}"

    @property
    def display_name(self) -> str:
        return self.raw.display_name

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"

    async def get_dm(self) -> Channel | None:
        try:
            return await self.raw.create_dm()
        except fluxer.HTTPException:
            return None


class Channel(c.Channel):
    raw: fluxer.Channel
    bot: fluxer.Bot

    @property
    def id(self) -> int:
        return self.raw.id

    @property
    def dm(self) -> bool:
        return self.raw.type == fluxer.ChannelType.DM

    @property
    def name(self) -> str:
        return self.raw.name

    @property
    def guild(self) -> Guild:
        return Guild(self.raw.guild, self.bot)

    @property
    def mention(self) -> str:
        return f"<#{self.id}>"

    async def send(self, content: str, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context:
        message = await self.raw.send(
            content,
            embeds=[from_embed(e) for e in embeds or []],
            files=[from_file(f) for f in files or []],
            **kwargs
        )
        return Message(message, self.bot).context

    async def get_message(self, message_id: int) -> Message | None:
        try:
            return await self.raw.fetch_message(message_id)
        except fluxer.NotFound:
            return None

    async def delete_message(self, message_id: int):
        await self.raw.delete_messages([message_id])


class Guild(c.Guild):
    raw: fluxer.Guild
    bot: fluxer.Bot

    @property
    def id(self) -> int:
        return self.raw.id

    @property
    def name(self) -> str:
        return self.raw.name

    async def get_channel(self, channel_id: int) -> Channel | None:
        try:
            return await self.bot.fetch_channel(str(channel_id))
        except fluxer.NotFound:
            return None

    async def get_roles(self) -> list[Role]:
        return [Role(role, self.bot) for role in await self.raw.fetch_roles()]

    async def get_role(self, role_id: int) -> Role | None:
        roles = await self.get_roles()
        for role in roles:
            if role.id == role_id:
                return role
        return None

    async def get_member(self, user_id: int) -> Member | None:
        try:
            return Member(await self.raw.fetch_member(user_id), self.bot)
        except fluxer.NotFound:
            return None


class Member(c.Member):
    raw: fluxer.GuildMember
    bot: fluxer.Bot

    @property
    def user(self) -> User:
        return User(self.raw.user, self.bot)

    @property
    def nick(self) -> str:
        return self.raw.nick

    @property
    def display_name(self) -> str:
        return self.raw.display_name

    @property
    def roles(self) -> list[Role]:
        return [Role(role, self.bot) for role in self.raw.roles]


class Role(c.Role):
    raw: fluxer.Role
    bot: fluxer.Bot

    @property
    def id(self) -> int:
        return self.raw.id

    @property
    def name(self) -> str:
        return self.raw.name

    @property
    def permissions(self) -> int:
        return self.raw.permissions

    @property
    def is_everyone(self) -> bool:
        return self.raw.is_default

    @property
    def mention(self) -> str:
        return f"<@&{self.id}>"


class Message(c.Message):
    raw: fluxer.Message
    bot: fluxer.Bot

    @property
    def id(self) -> int:
        return self.raw.id

    @property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.raw.timestamp)

    @property
    def content(self) -> str:
        return self.raw.content

    @property
    def embeds(self) -> list[Embed]:
        return [Embed(e.get("title", ""), e.get("description", ""), e.get("footer", {}).get("text"), e.get("thumbnail", {}).get("url")) for e in self.raw.embeds]

    @property
    def attachments(self) -> list[Attachment]:
        return [Attachment(attachment, self.bot) for attachment in self.raw.attachments]

    @property
    def author(self) -> User:
        return User(self.raw.author, self.bot)

    @property
    def channel(self) -> Channel:
        return Channel(self.raw.channel, self.bot)

    @property
    def guild(self) -> Guild:
        return Guild(self.raw.guild, self.bot)

    @property
    def context(self) -> Context:
        return Context(self, self.bot)

    @property
    def mention(self) -> str:
        return f"https://web.fluxer.app/channels/{self.guild.id if not self.channel.dm else '@me'}/{self.channel.id}/{self.id}"

    @property
    def reference(self) -> Message | None:
        return Message(self.raw.referenced_message, self.bot) if self.raw.referenced_message else None

    async def delete(self):
        await self.raw.delete()

    async def reply(self, content: str, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context:
        message = await self.raw.reply(
            content,
            embeds=[from_embed(e) for e in embeds or []],
            files=[from_file(f) for f in files or []],
            **kwargs
        )
        return Message(message, self.bot).context

    async def edit(self, content: str, embeds: list[Embed] = None, **kwargs):
        await self.raw.edit(
            content,
            embeds=[from_embed(e) for e in embeds or []],
            **kwargs
        )

    async def remove_reaction(self, emoji: str | int, user: int | None | type(...) = ...):
        if user == ...:
            await self.raw.clear_reaction(emoji)
        else:
            await self.raw.remove_reaction(emoji, user or "@me")

    async def add_reaction(self, emoji: str | int):
        await self.raw.add_reaction(emoji)


class Webhook(c.Webhook):
    raw: fluxer.Webhook
    bot: fluxer.Bot

    @property
    def id(self) -> int:
        return self.raw.id

    @property
    def token(self) -> str:
        return self.raw.token

    @property
    def name(self) -> str:
        return self.raw.name

    async def send(self, content: str, username: str = None, avatar_url: str = None, mention: bool = False, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context:
        if not self.raw._http:
            raise RuntimeError("Cannot send with webhook without HTTPClient")

        files = files or []

        route = self.raw._http._route(
            "POST",
            "/webhooks/{webhook_id}/{token}",
            webhook_id=self.id,
            token=self.token,
        )
        payload = {}
        if content is not None:
            payload["content"] = content
        if embeds is not None:
            payload["embeds"] = [from_embed(embed).to_dict() for embed in embeds]
        if username is not None:
            payload["username"] = username
        if avatar_url is not None:
            payload["avatar_url"] = avatar_url
        if mention:
            payload["allowed_mentions"] = {
                "parse": ["users"]
            }
        params = {"wait": "true"}
        if files:
            form = aiohttp.FormData()
            payload["attachments"] = [
                {"id": i, "filename": file.filename} for i, file in enumerate(files)
            ]
            form.add_field(
                "payload_json",
                json.dumps(payload),
                content_type="application/json",
            )
            for i, file in enumerate(files):
                form.add_field(
                    f"files[{i}]",
                    file.data,
                    filename=file.filename,
                )
            data = await self.raw._http.request(route, data=form, params=params)
        else:
            data = await self.raw._http.request(
                route,
                json=payload,
                params=params,
            )

        return Message(fluxer.Message.from_data(data, self.raw._http), self.bot).context

    async def edit(self, context: Context, content: str, embeds: list[Embed] = None, **kwargs):
        await self.raw._http.request(
            fhttp.Route("PATCH", "/webhooks/{wid}/{wtk}/messages/{mid}", wid=self.id, wtk=self.token, mid=context.id),
            json={
                "content": content,
                "embeds": [from_embed(embed).to_dict() for embed in embeds or []]
            }
        )

    async def reply(self, context: Context, content: str, username: str = None, avatar_url: str = None, mention: bool = False, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context:
        if not self.raw._http:
            raise RuntimeError("Cannot send with webhook without HTTPClient")

        files = files or []

        route = self.raw._http._route(
            "POST",
            "/webhooks/{webhook_id}/{token}",
            webhook_id=self.id,
            token=self.token,
        )
        payload = {}
        if content is not None:
            payload["content"] = content
        if embeds is not None:
            payload["embeds"] = [from_embed(embed).to_dict() for embed in embeds]
        if username is not None:
            payload["username"] = username
        if avatar_url is not None:
            payload["avatar_url"] = avatar_url
        if mention:
            payload["allowed_mentions"] = {
                "parse": ["users"]
            }
        payload["message_reference"] = {
            "message_id": str(context.id)
        }
        params = {"wait": "true"}
        if files:
            form = aiohttp.FormData()
            payload["attachments"] = [
                {"id": i, "filename": file.filename} for i, file in enumerate(files)
            ]
            form.add_field(
                "payload_json",
                json.dumps(payload),
                content_type="application/json",
            )
            for i, file in enumerate(files):
                form.add_field(
                    f"files[{i}]",
                    file.data,
                    filename=file.filename,
                )
            data = await self.raw._http.request(route, data=form, params=params)
        else:
            data = await self.raw._http.request(
                route,
                json=payload,
                params=params,
            )

        return Message(fluxer.Message.from_data(data, self.raw._http), self.bot).context

    async def get_message_data(self, context: Context) -> Message:
        return context.message


class Bot(c.Bot):
    raw: fluxer.Bot
    bot: fluxer.Bot
    
    @property
    def id(self) -> int:
        return self.raw.user.id
    
    @property
    def user(self) -> User:
        return User(self.raw.user, self.bot)


class ReactionActionEvent(c.ReactionActionEvent):
    raw: fluxer.models.RawReactionActionEvent
    bot: fluxer.Bot

    async def context(self) -> Context:
        return Message(await self.bot.fetch_message(str(self.raw.channel_id), str(self.raw.message_id)), self.bot).context

    async def user(self) -> User:
        return User(await self.bot.fetch_user(str(self.raw.user_id)), self.bot)

    @property
    def emoji(self) -> str | int:
        return self.raw.emoji.name or self.raw.emoji.id

    @property
    def action(self) -> Literal["ADD"] | Literal["REMOVE"]:
        return "ADD" if self.raw.event_type == "REACTION_ADD" else "REMOVE"


class Context(c.Context):
    def __init__(self, message: Message, bot: fluxer.Bot):
        super().__init__(Platform.Fluxer, bot, message)
        self.bot = bot

    async def interact_to_delete(self, event: ReactionActionEvent):
        if event.emoji == "❌":
            context = await event.context()
            await context.message.delete()
            Interactions.instance.delete_interaction(context)
        return None

    async def reply(self, content: str, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context:
        try:
            ctx = await self.message.reply(content, embeds, files, **kwargs)
        except fluxer.NotFound:
            ctx = await self.channel.send(
                (f"<@{self.author.id}>\n" if not self.is_bot else "") + content,
                embeds, files, **kwargs)

        Interactions.instance.add_interaction(ctx, Interaction(self.author.id, self.interact_to_delete))
        return ctx

    @property
    def author(self) -> User:
        return self.message.author

    @property
    def channel(self) -> Channel:
        return self.message.channel

    @property
    def guild(self) -> Guild:
        return self.message.guild

    @property
    def is_bot(self) -> bool:
        return self.author.is_bot

    @property
    def id(self) -> int:
        return self.message.id

    @property
    def content(self) -> str:
        return self.message.content

    async def get_member(self, user_id: int) -> Member | None:
        return await self.guild.get_member(user_id)

    async def get_user(self, user_id: int) -> User | None:
        try:
            return User(await self.bot.fetch_user(str(user_id)), self.bot)
        except fluxer.NotFound:
            return None

    async def get_channel(self, channel_id: int) -> Channel | None:
        try:
            return Channel(await self.bot.fetch_channel(str(channel_id)), self.bot)
        except fluxer.NotFound:
            return None
