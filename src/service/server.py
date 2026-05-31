from abc import ABC, abstractmethod
from typing import Callable, Coroutine, Any

import discord
import fluxer

from .common import Bot as BotT
from .discord import Bot as DiscordBot
from .fluxer import Bot as FluxerBot
from .enums import Platform
from ..backend.config import Config

type Coro = Callable[..., Coroutine[Any, Any, Any]]


class Server[Bot = fluxer.Bot | discord.Bot](ABC):
    bot: Bot
    platform: Platform

    @abstractmethod
    async def start(self): pass

    @abstractmethod
    async def close(self): pass

    @abstractmethod
    def event(self, function: Coro): pass

    @abstractmethod
    def clear_events(self): pass

    @abstractmethod
    def get_bot(self) -> BotT: pass


class Fluxer(Server[fluxer.Bot]):
    platform = Platform.Fluxer
    bot: fluxer.Bot

    def __init__(self):
        self.events: list[Coro] = []

    async def start(self):
        self.bot = fluxer.Bot(intents=fluxer.Intents.default(), api_url=Config.instance.api_url)
        for event in self.events:
            self.bot.event(event)
        await self.bot.start(Config.instance.token)

    async def close(self):
        await self.bot.close()

    def event(self, function: Coro):
        self.events.append(function)

    def clear_events(self):
        self.bot._event_handlers.clear()

    def get_bot(self) -> FluxerBot:
        return FluxerBot(self.bot, self.bot)


class Discord(Server[discord.Bot]):
    platform = Platform.Discord
    bot: discord.Bot

    def __init__(self):
        self.events: list[Coro] = []

    async def start(self):
        self.bot = discord.Bot(intents=discord.Intents.all())
        for event in self.events:
            self.bot.event(event)
        await self.bot.start(Config.instance.discord.token)

    async def close(self):
        await self.bot.close()

    def event(self, function: Coro):
        self.events.append(function)

    def clear_events(self):
        self.bot._event_handlers.clear()

    def get_bot(self) -> DiscordBot:
        return DiscordBot(self.bot, self.bot)


ALL_SERVERS = [Fluxer, Discord]

SERVER_INSTANCES: list[Server] = []

def setup_instances() -> list[Server]:
    for server in ALL_SERVERS:
        SERVER_INSTANCES.append(server())

    return SERVER_INSTANCES
