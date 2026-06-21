import asyncio
import time

import discord
import fluxer

from ..backend.database import Database
from ..backend.models import Platform
from ..interaction import Interactions
from ..send_proxy import on_user_message, edit_proxy_message
from ..service import Context, Server, FluxerServer, DiscordServer, FluxerContext, DiscordContext, \
    ReactionActionEvent, Embed, Message
from ..service.fluxer import Message as FluxerMessage, ReactionActionEvent as FluxerReactionActionEvent
from ..service.discord import Message as DiscordMessage, ReactionActionEvent as DiscordReactionActionEvent
from ..backend.config import Config
from ..commands.generic import get_command_awaitable, ParseError, EarlyExitException


editing_proxy_messages: dict[tuple[int, Platform], tuple[int, Message]] = {} # (user_id, platform) => (channel id, message)
handled_messages: dict[tuple[int, Platform, str], float] = {} # (message_id, platform, content) => timestamp


async def message_wrapper(context: Context):
    if context.is_bot: return

    content = context.content
    if (context.id, context.platform, content) in handled_messages: return

    handled_messages[context.id, context.platform, content] = time.time()
    await handle_message(context)
    await asyncio.sleep(1)
    handled_messages.pop((context.id, context.platform, content))


async def handle_message(context: Context):
    key = (context.author.id, context.platform)
    if key in editing_proxy_messages and editing_proxy_messages[key][0] == context.message.channel_id:
        msg = editing_proxy_messages[key][1]
        editing_proxy_messages.pop(key)
        lnk = await Database.instance.get_message_link(msg.id, msg.channel_id)
        uid = await Database.instance.get_user_id(context.author.id, context.platform, False)
        await edit_proxy_message(msg.context, context.content, lnk, uid)
        await context.reply(f"Message edited! {await msg.mention()}")
        return

    try:
        cmd = await get_command_awaitable(context, Config.cfg(context.platform).prefixes)
        if cmd:
            await cmd
            return
    except ParseError as e:
        await context.reply(f"Error parsing command: {e.message}.\nUse `{Config.prefix(context.platform)}help` to see command shape.")
        return
    except EarlyExitException:
        return

    await on_user_message(context)


async def handle_reaction(context: ReactionActionEvent, server: Server):
    user = await context.user()
    if user.is_bot: return

    ctx = await context.context()
    if await Interactions.instance.interact(ctx, user.id, (context, )):
        return

    uid = await Database.instance.get_user_id(user.id, ctx.platform, False)

    if context.emoji == "❓":
        lnk = await Database.instance.get_message_link(ctx.id, ctx.message.channel_id)
        if lnk:
            if proxy := await Database.instance.get_proxy(lnk.proxy_id):
                e = Embed(
                    "Proxied Message",
                    f"**Proxy**: {proxy.name}\n**Owner**: <@{lnk.platform_user}> (`{lnk.platform_user}`)\n**Message Link**: [link]({await ctx.message.mention()})\n**Message**:\n{'\n'.join(('> ' + ln) for ln in ctx.content.split('\n'))}"
                )
                dm = await user.get_dm()
                await dm.send("", [e])
                await ctx.message.remove_reaction("❓", user.id)
                return

    if context.emoji == "❌":
        lnk = await Database.instance.get_message_link(ctx.id, ctx.message.channel_id)
        if lnk:
            if (proxy := await Database.instance.get_proxy(lnk.proxy_id)) and proxy.owner == uid:
                await Database.instance.delete_link_message(ctx.id, ctx.message.channel_id)
                await ctx.message.delete()
                return

    if context.emoji == "📝":
        lnk = await Database.instance.get_message_link(ctx.id, ctx.message.channel_id)
        if lnk:
            proxy = await Database.instance.get_proxy(lnk.proxy_id)
            if proxy.owner == uid:
                await ctx.message.remove_reaction("📝", user.id)
                channel = await user.get_dm()
                raw = await ctx.get_wh_message_data(ctx)
                await channel.send(f"Editing message:\n```\n{raw.content}\n```")
                await channel.send("Please enter the new content of the message here:")
                editing_proxy_messages[user.id, ctx.platform] = channel.id, raw
                await asyncio.sleep(120)
                if (user.id, ctx.platform) in editing_proxy_messages:
                    await channel.send("Message edit request expired!")
                    editing_proxy_messages.pop((user.id, ctx.platform))

    if context.emoji == "🔔":
        lnk = await Database.instance.get_message_link(ctx.id, ctx.message.channel_id)
        if lnk:
            await ctx.message.remove_reaction("🔔", user.id)
            await ctx.reply(
                f"<@{lnk.platform_user}>, {user.mention} has pinged you! Use :x: to delete this message (expires in 5 minutes).",
                user_id_override=lnk.platform_user
            )
            return


def setup(server: Server):
    server.ready = False

    @server.event
    async def on_ready():
        server.ready = True
        print(f"Bot is online and ready for platform {server.platform.name}!")

    if server.platform is Platform.Fluxer:
        setup_fluxer(server)

    if server.platform is Platform.Discord:
        setup_discord(server)


def setup_fluxer(server: FluxerServer):
    @server.event
    async def on_message(message: fluxer.Message):
        context = FluxerContext(FluxerMessage(message, server.bot), server.bot)
        await message_wrapper(context)

    @server.event
    async def on_message_edit(message: fluxer.Message):
        context = FluxerContext(FluxerMessage(message, server.bot), server.bot)
        await message_wrapper(context)

    @server.event
    async def on_raw_reaction_add(event: fluxer.models.RawReactionActionEvent):
        context = FluxerReactionActionEvent(event, server.bot)
        await handle_reaction(context, server)

    @server.event
    async def on_message_delete(data: dict):
        channel_id, message_id = int(data["channel_id"]), int(data["id"])
        lnk = await Database.instance.get_message_link(message_id, channel_id)
        if lnk:
            await Database.instance.delete_link_message(message_id, channel_id)


def setup_discord(server: DiscordServer):
    @server.event
    async def on_message(message: discord.Message):
        if message.type in (discord.MessageType.default, discord.MessageType.reply):
            context = DiscordContext(DiscordMessage(message, server.bot), server.bot)
            await message_wrapper(context)

    @server.event
    async def on_message_edit(before: discord.Message, after: discord.Message):
        context = DiscordContext(DiscordMessage(after, server.bot), server.bot)
        await message_wrapper(context)

    @server.event
    async def on_raw_reaction_add(event: discord.RawReactionActionEvent):
        context = DiscordReactionActionEvent(event, server.bot)
        await handle_reaction(context, server)

    @server.event
    async def on_message_delete(message: discord.Message):
        lnk = await Database.instance.get_message_link(message.id, message.channel.id)
        if lnk:
            await Database.instance.delete_link_message(message.id, message.channel.id)
