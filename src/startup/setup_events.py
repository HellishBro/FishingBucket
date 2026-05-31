import discord
import fluxer

from ..interaction import Interactions
from ..service import Context, Platform, Server, FluxerServer, DiscordServer, FluxerContext, DiscordContext, ReactionActionEvent
from ..service.fluxer import Message as FluxerMessage, ReactionActionEvent as FluxerReactionActionEvent
from ..service.discord import Message as DiscordMessage, ReactionActionEvent as DiscordReactionActionEvent
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


async def handle_reaction(context: ReactionActionEvent, server: Server):
    user = await context.user()
    if user.is_bot: return

    ctx = await context.context()
    if await Interactions.instance.interact(
        ctx, user.id, (context, )
    ):
        return


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

    @server.event
    async def on_raw_reaction_add(event: fluxer.models.RawReactionActionEvent):
        context = FluxerReactionActionEvent(event, server.bot)
        await handle_reaction(context, server)


def setup_discord(server: DiscordServer):
    @server.event
    async def on_message(message: discord.Message):
        context = DiscordContext(DiscordMessage(message, server.bot), server.bot)
        await handle_message(context)

    @server.event
    async def on_raw_reaction_add(event: discord.RawReactionActionEvent):
        context = DiscordReactionActionEvent(event, server.bot)
        await handle_reaction(context, server)
