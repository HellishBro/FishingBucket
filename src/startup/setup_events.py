import discord
import fluxer

from ..service.enums import Platform
from ..service.context import FluxerContext, DiscordContext, Context
from ..service.server import Server, Fluxer, Discord
from ..backend.config import Config
from ..commands.generic import get_command_awaitable, ParseError


async def handle_message(context: Context):
    if context.is_bot: return

    try:
        cmd = await get_command_awaitable(context, Config.instance.prefixes)
        if cmd:
            await cmd
    except ParseError as e:
        await context.reply(f"Error parsing command: {e.message}.\nUse `fish!help` to see command shape.")


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
        await handle_message(context)


def setup_discord(server: Discord):
    @server.event
    async def on_message(message: discord.Message):
        context = DiscordContext(Platform.Discord, server.bot, message)
        print("Discord:", message.content)
        await handle_message(context)
