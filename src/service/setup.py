import discord
import fluxer

from .enums import Platform
from .context import FluxerContext, DiscordContext
from .server import Server, Fluxer, Discord


def setup(server: Server):
    @server.event
    async def on_ready():
        print(f"Bot is online and ready for platform {server.platform.name}!")

    if server.platform is Platform.Fluxer:
        setup_fluxer(server)

    if server.platform is Platform.Discord:
        setup_discord(server)


def setup_fluxer(server: Fluxer):
    @server.event
    async def on_message(message: fluxer.Message):
        context = FluxerContext(Platform.Fluxer, server.bot, message)
        print("Fluxer:", message.content)

def setup_discord(server: Discord):
    @server.event
    async def on_message(message: discord.Message):
        context = DiscordContext(Platform.Discord, server.bot, message)
        print("Discord:", message.content)
