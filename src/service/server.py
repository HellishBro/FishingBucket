from abc import ABC, abstractmethod
from typing import Callable, Coroutine, Any

import discord
import fluxer

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


class Fluxer(Server[fluxer.Bot]):
    platform = Platform.Fluxer

    def __init__(self):
        self.bot = fluxer.Bot(intents=fluxer.Intents.default(), api_url=Config.instance.api_url)

    async def start(self):
        await self.bot.start(Config.instance.token)

    async def close(self):
        await self.bot.close()

    def event(self, function: Coro):
        self.bot.event(function)

    def clear_events(self):
        self.bot._event_handlers.clear()


class Discord(Server[discord.Bot]):
    platform = Platform.Discord

    def __init__(self):
        self.bot = discord.Bot(intents=discord.Intents.all())

    async def start(self):
        await self.bot.start(Config.instance.discord.token)

    async def close(self):
        await self.bot.close()

    def event(self, function: Coro):
        self.bot.event(function)

    def clear_events(self):
        self.bot._event_handlers.clear()


ALL_SERVERS = [Fluxer, Discord]