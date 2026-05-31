import discord
import fluxer

from ..service import Context, Platform, Server, FluxerServer, DiscordServer, FluxerContext, DiscordContext
from ..service.fluxer import Message as FluxerMessage
from ..service.discord import Message as DiscordMessage
from ..backend.config import Config
from ..commands.generic import get_command_awaitable, ParseError


async def handle_message(context: Context):
    if context.is_bot: return

    try:
        cmd = await get_command_awaitable(context, Config.instance.prefixes)
        if cmd:
            await cmd
    except ParseError as e:
        await context.reply(f"Error parsing command: {e.message}.\nUse `{Config.instance.prefixes[0]}help` to see command shape.")


def setup(server: Server):
    @server.event
    async def on_ready():
        print(f"Bot is online and ready for platform {server.platform.name}!")

    if server.platform is Platform.Fluxer:
        setup_fluxer(server)

    if server.platform is Platform.Discord:
        setup_discord(server)


def setup_fluxer(server: FluxerServer):
    @server.event
    async def on_message(message: fluxer.Message):
        context = FluxerContext(FluxerMessage(message, server.bot), server.bot)
        await handle_message(context)


def setup_discord(server: DiscordServer):
    @server.event
    async def on_message(message: discord.Message):
        context = DiscordContext(DiscordMessage(message, server.bot), server.bot)
        await handle_message(context)
