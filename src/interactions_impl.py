import asyncio
import time

import fluxer
from fluxer.models import RawReactionActionEvent

from .interaction import Interactions, message_reactions, remove_reaction
from .commands import command_list
from .backend.database import Database
from .send_proxy import on_user_message, recover_original_message, edit_proxy_message
from .backend.config import Config
from .backend.utils import mention_message
from . import response

ready = False

async def show_proxy_info(bot: fluxer.Bot, showing: fluxer.Message) -> fluxer.Embed | None:
    proxy_id = await Database.instance.get_proxy_id(showing.id, showing.channel_id)
    if proxy_id:
        if proxy := await Database.instance.get_proxy(proxy_id):
            return fluxer.Embed(
                "Proxied Message",
                f"**Proxy**: {proxy.name}\n**Owner**: <@{proxy.owner}> (`{proxy.owner}`)\n**Message Link**: [link]({await mention_message(bot, showing)})\n**Message**:\n{'\n'.join(('> ' + ln) for ln in showing.content.split('\n'))}"
            )
    return None


def setup(bot: fluxer.Bot):
    global ready
    ready = False

    editing_messages: dict[int, tuple[int, int]] = {} # user_id => (channel_id, message_id)
    handled_messages: dict[int, bool] = {}

    @bot.event
    async def on_ready():
        global ready
        print(f"Bot is online and ready!")
        if not ready:
            if Config.instance.use_extras:
                from .extras.down_runner import report_bot
                await report_bot("up")

        ready = True

    @bot.event
    async def on_message(message: fluxer.Message):
        handled_messages[message.id] = True
        await message_wrapper(message)
        handled_messages.pop(message.id)

    async def message_wrapper(message: fluxer.Message, editing: bool = False):
        if message.author.id == bot.user.id: return
        if message.author.bot: return

        if message.author.id in editing_messages:
            channel_id, message_id = editing_messages.pop(message.author.id)
            msg = await bot.fetch_message(str(channel_id), str(message_id))
            await edit_proxy_message(msg, bot, message.content)
            await message.author.send(f"Message edited: {await mention_message(bot, msg)}")
            return

        content = message.content.lower()
        for prefix in Config.instance.prefixes:
            if content.startswith(prefix):
                command = message.content[len(prefix):].strip()
                for cmd, handler in command_list.registry.items():
                    if command.startswith(cmd[0]):
                        if cmd[1] is None or editing is cmd[1]:
                            await handler(message, cmd[0], prefix)
                            return
                for alias, cmd in command_list.aliases.items():
                    if command.startswith(alias):
                        if (cmd, None) in command_list.registry:
                            await command_list.registry[cmd, None](message, alias, prefix)
                        else:
                            await command_list.registry[cmd, editing](message, alias, prefix)
                        return
                await response.respond(message, f"`{command}` is not recognized as a valid command! Use `{bot.command_prefix}help` to view all commands!")
                return

        await on_user_message(message, bot)


    @bot.event
    async def on_message_edit(message: fluxer.Message):
        if message.id in handled_messages: return
        await message_wrapper(message, True)


    @bot.event
    async def on_raw_reaction_add(event: RawReactionActionEvent):
        if event.user_id == bot.user.id: return

        if (event.message_id, event.user_id) not in message_reactions:
            message_reactions[(event.message_id, event.user_id)] = []

        if event.emoji.name in message_reactions[(event.message_id, event.user_id)]:
            return

        message_reactions[(event.message_id, event.user_id)].append(event.emoji.name)

        if await Interactions.instance.interact(event.message_id, event.user_id, (event, )):
            return

        if event.emoji.name == "❓":
            msg = await bot.fetch_message(str(event.channel_id), str(event.message_id))
            usr = await bot.fetch_user(str(event.user_id))
            if embed := await show_proxy_info(bot, msg):
                await usr.send("", embeds=[embed])
                await remove_reaction(msg, event.emoji.name, usr)
        if event.emoji.name == "❌":
            usr = await bot.fetch_user(str(event.user_id))
            proxy_id = await Database.instance.get_proxy_id(event.message_id, event.channel_id)
            if proxy_id:
                proxy = await Database.instance.get_proxy(proxy_id)
                if proxy.owner == usr.id:
                    await Database.instance.delete_link_message(event.message_id, event.channel_id)
                    message_reactions.pop((event.message_id, event.user_id))
                    await bot.delete_message(event.channel_id, event.message_id)
        if event.emoji.name == "📝":
            usr = await bot.fetch_user(str(event.user_id))
            proxy_id = await Database.instance.get_proxy_id(event.message_id, event.channel_id)
            if proxy_id:
                proxy = await Database.instance.get_proxy(proxy_id)
                if proxy.owner == usr.id:
                    msg = await bot.fetch_message(str(event.channel_id), str(event.message_id))
                    await remove_reaction(msg, event.emoji.name, usr)
                    await usr.send(f"Editing message:\n```\n{recover_original_message(msg)[1]}\n```")
                    await usr.send("Please enter the new content of the message here:")
                    editing_messages[usr.id] = (msg.channel_id, msg.id)
                    await asyncio.sleep(60)
                    if usr.id in editing_messages:
                        await usr.send("Message edit request expired!")
                        editing_messages.pop(usr.id)
        if event.emoji.name == "🔔":
            proxy_id = await Database.instance.get_proxy_id(event.message_id, event.channel_id)
            if proxy_id:
                msg = await bot.fetch_message(str(event.channel_id), str(event.message_id))
                prox = await Database.instance.get_proxy(proxy_id)
                await remove_reaction(msg, "🔔", event.user_id)
                await response.respond(msg, f"<@{prox.owner}>, <@{event.user_id}> has pinged you! Use :x: to delete this message (expires in 5 minutes).", user_id_override=prox.owner)

    @bot.event
    async def on_message_delete(data: dict):
        channel_id, message_id = int(data["channel_id"]), int(data["id"])
        proxy_id = await Database.instance.get_proxy_id(message_id, channel_id)
        if proxy_id:
            await Database.instance.delete_link_message(message_id, channel_id)


def clear(bot: fluxer.Bot):
    bot._event_handlers.clear()
