import json
from abc import abstractmethod, ABC
from datetime import datetime
from typing import Any, Literal

from .enums import Platform


class Embed:
    def __init__(self, title: str, description: str, footer: str = None, thumbnail_url: str = None):
        self.title = title
        self.description = description
        self.footer = footer
        self.thumbnail_url = thumbnail_url


class File:
    def __init__(self, filename: str, mime_type: str, data: bytes):
        self.filename = filename
        self.mime_type = mime_type
        self.data = data


class Attachment(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def filename(self) -> str: pass

    @property
    @abstractmethod
    def url(self) -> str: pass

    @abstractmethod
    async def read(self) -> bytes: pass

    async def read_json(self) -> Any:
        return json.loads((await self.read()).decode("utf-8"))


class User(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def is_bot(self) -> bool: pass

    @property
    @abstractmethod
    def id(self) -> int: pass

    @property
    @abstractmethod
    def full_tag(self) -> str: pass

    @property
    @abstractmethod
    def display_name(self) -> str: pass

    @property
    @abstractmethod
    def mention(self) -> str: pass

    @abstractmethod
    async def get_dm(self) -> Channel | None: pass


class Channel(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def id(self) -> int: pass

    @property
    @abstractmethod
    def dm(self) -> bool: pass

    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def guild(self) -> Guild: pass

    @property
    @abstractmethod
    def guild_id(self) -> int: pass

    @property
    @abstractmethod
    def mention(self) -> str: pass

    @abstractmethod
    async def send(self, content: str, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context: pass

    @abstractmethod
    async def get_message(self, message_id: int) -> Message | None: pass

    @abstractmethod
    async def delete_message(self, message_id: int): pass

    @abstractmethod
    async def create_webhook(self, name: str) -> Webhook: pass

    @abstractmethod
    async def permissions_for(self, member: Member) -> Permissions: pass


class Guild(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def id(self) -> int: pass

    @property
    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    async def get_channel(self, channel_id: int) -> Channel | None: pass

    @abstractmethod
    async def get_roles(self) -> list[Role]: pass

    @abstractmethod
    async def get_role(self, role_id: int) -> Role | None: pass

    @abstractmethod
    async def get_member(self, user_id: int) -> Member | None: pass


class Member(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def user(self) -> User: pass

    @property
    @abstractmethod
    def nick(self) -> str: pass

    @property
    @abstractmethod
    def display_name(self) -> str: pass

    @abstractmethod
    async def roles(self) -> list[Role]: pass


class Role(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def id(self) -> int: pass

    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def permissions(self) -> Permissions: pass

    @property
    @abstractmethod
    def is_everyone(self) -> bool: pass

    @property
    @abstractmethod
    def mention(self) -> str: pass


class Message(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def id(self) -> int: pass

    @property
    @abstractmethod
    def timestamp(self) -> datetime: pass

    @property
    @abstractmethod
    def content(self) -> str: pass

    @property
    @abstractmethod
    def embeds(self) -> list[Embed]: pass

    @property
    @abstractmethod
    def attachments(self) -> list[Attachment]: pass

    @property
    @abstractmethod
    def author(self) -> User: pass

    @property
    @abstractmethod
    def channel(self) -> Channel: pass

    @property
    @abstractmethod
    def channel_id(self) -> int: pass

    @property
    @abstractmethod
    def guild_id(self) -> int: pass

    @property
    @abstractmethod
    def guild(self) -> Guild: pass

    @property
    @abstractmethod
    def context(self) -> Context: pass

    @abstractmethod
    async def mention(self) -> str: pass

    @property
    @abstractmethod
    def has_reference(self) -> bool: pass

    @abstractmethod
    async def get_reference(self) -> Message | None: pass

    @abstractmethod
    async def delete(self): pass

    @abstractmethod
    async def reply(self, content: str, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context: pass

    @abstractmethod
    async def edit(self, content: str, embeds: list[Embed] = None, **kwargs): pass

    @abstractmethod
    async def remove_reaction(self, emoji: str | int, user: int | None | type(...) = ...): pass

    @abstractmethod
    async def add_reaction(self, emoji: str | int): pass


class Webhook(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def id(self) -> int: pass

    @property
    @abstractmethod
    def token(self) -> str: pass

    @property
    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    async def send(self, content: str, username: str = None, avatar_url: str = None, mention: bool = False, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context: pass

    @abstractmethod
    async def edit(self, context: Context, content: str, embeds: list[Embed] = None, **kwargs): pass

    @abstractmethod
    async def reply(self, context: Context, content: str, username: str = None, avatar_url: str = None, mention: bool = False, embeds: list[Embed] = None, files: list[File] = None, mention_str: str | Literal[False] = None) -> Context: pass

    @abstractmethod
    async def get_message_data(self, context: Context) -> Message: pass


class Bot(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def id(self) -> int: pass

    @property
    @abstractmethod
    def user(self) -> User: pass

    @property
    @abstractmethod
    def guilds(self) -> list[Guild]: pass

    @abstractmethod
    async def get_webhook(self, webhook_id: int) -> Webhook | None: pass


class ReactionActionEvent(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @abstractmethod
    async def context(self) -> Context: pass

    @abstractmethod
    async def user(self) -> User: pass

    @property
    @abstractmethod
    def emoji(self) -> str | int: pass

    @property
    @abstractmethod
    def action(self) -> Literal["ADD"] | Literal["REMOVE"]: pass


class Permissions(ABC):
    def __init__(self, raw, bot):
        self.raw = raw
        self.bot = bot

    @property
    @abstractmethod
    def manage_messages(self) -> bool: pass


class Context(ABC):
    def __init__(self, platform: Platform, bot: Bot, message: Message):
        self.platform = platform
        self.bot = bot
        self.message = message

    @abstractmethod
    async def reply(self, content: str, embeds: list[Embed] = None, files: list[File] = None, **kwargs) -> Context: pass

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
    def id(self) -> int: pass

    @property
    @abstractmethod
    def content(self) -> str: pass

    @abstractmethod
    async def get_member(self, user_id: int) -> Member | None: pass

    @abstractmethod
    async def get_user(self, user_id: int) -> User | None: pass

    @abstractmethod
    async def get_channel(self, channel_id: int) -> Channel | None: pass

    @property
    @abstractmethod
    def get_bot(self) -> Bot: pass
