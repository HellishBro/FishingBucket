import time
import traceback
from typing import Literal

import expr_dice_roller as dice
import fluxer
import re

from .backend.cache import TTLCache
from .backend.config import Config
from .backend.database import Database, GuildPreference, UserAutoproxyPreference
from .backend.models import Proxy
from .backend.template_utils import Template
from .backend.dice_environments import global_functions
from .backend.utils import mention_message, convert_attachments, normalize_emojis, roll_dice, edit_webhook, \
    get_guild_id_from_channel, send_webhook
from .response import delete_message


def message_matches_trigger(message: str, triggers: list[str]) -> tuple[bool, str]:
    for trigger in triggers:
        if trigger:
            nm = normalize_emojis(trigger)
            nmm = normalize_emojis(message)
            res = Template.from_string(nm).match(nmm)
            if res.match:
                return True, res.content
    return False, ""

async def get_proxy_from_message(message: str, user_proxies: list[Proxy]) -> tuple[Proxy, str] | None:
    for proxy in user_proxies:
        if proxy.triggers:
            if (res := message_matches_trigger(message, proxy.triggers))[0]:
                return proxy, res[1]
    return None

async def get_proxied_messages(message: str, user_id: int, autoproxy_preferences: UserAutoproxyPreference | None) -> list[tuple[Proxy, str]]:
    res: list[tuple[Proxy, str]] = []
    autoproxy_proxy = None
    user_proxies = await Database.instance.get_user_proxies(user_id)
    if autoproxy_preferences and not autoproxy_preferences.expires_now():
        prox_id = autoproxy_preferences.proxy if autoproxy_preferences.proxy is not None else autoproxy_preferences.last_used_proxy
        autoproxy_proxy = await Database.instance.get_proxy(prox_id)
    for line in message.split("\n"):
        if proxy_m := await get_proxy_from_message(line, user_proxies):
            res.append(proxy_m)
        elif res: # proxy is not found for this line and there's a previous proxied message, meaning it's a continued line.
            res[-1] = (res[-1][0], res[-1][1] + "\n" + line)
        else: # no proxy was found and no previous proxied message, meaning no proxy is used, or that it is an autoproxy.
            if autoproxy_proxy:
                if res:
                    res[-1] = (res[-1][0], res[-1][1] + "\n" + line)
                else:
                    if line.startswith("\\") and not line.startswith("\\\\"):
                        return []
                    res.append((autoproxy_proxy, line))

            else:
                return []
    return res


@TTLCache(2048, 3600).cache_async(["webhook_id"])
async def fetch_webhook(bot: fluxer.Bot, webhook_id: int) -> fluxer.Webhook:
    return await bot.fetch_webhook(str(webhook_id))


@TTLCache(2048, 3600).cache_async(["channel_id"])
async def get_webhook(channel_id: int, bot: fluxer.Bot) -> fluxer.Webhook:
    if webhook_id := await Database.instance.get_channel_webhook(channel_id):
        webhook = await fetch_webhook(bot, webhook_id)
    else:
        webhook = await bot.create_webhook(str(channel_id), name=Config.instance.webhook)
        await Database.instance.put_channel_webhook_link(channel_id, int(webhook.id))
    return webhook

async def send_proxy_message(proxy: Proxy, message: str, parent_message: fluxer.Message | None, channel: fluxer.Channel, bot: fluxer.Bot, attachments: list[fluxer.models.Attachment]) -> fluxer.Message:
    webhook = await get_webhook(channel.id, bot)

    embeds = None

    """
    if parent_message:
        proxy_id = await Database.instance.get_proxy_id(parent_message.id, channel.id)
        if proxy_id:
            parent_proxy = await Database.instance.get_proxy(proxy_id)
            mention = f"{parent_proxy.name} (<@{parent_proxy.owner}>)"
            parent_name = parent_proxy.name
        else:
            mention = f"<@{parent_message.author.id}>"
            parent_name = parent_message.author.display_name

        trunc = parent_message.content
        trunc = trunc[:min(250, len(trunc))]
        embeds = [fluxer.Embed(
            "Reply",
            f"[Replying to]({await mention_message(bot, parent_message)}) {parent_name}:\n{'\n'.join(('> ' + line) for line in trunc.split('\n'))}"
        ).to_dict()]

        message = f"-# ↩ {mention}\n" + message
    """

    message, embeds = await modify_message(proxy.owner, await Database.instance.get_guild_preferences(channel.guild_id), message, embeds)
    return await send_webhook(webhook, message, embeds=embeds, username=proxy.effective_name, avatar_url=proxy.effective_avatar, files=await convert_attachments(attachments), wait=True, message_reference=parent_message)
    # return await webhook.send(message, embeds=embeds, username=proxy.effective_name, avatar_url=proxy.effective_avatar, files=await convert_attachments(attachments), wait=True)


block_content_regex = re.compile(r"{{(.+?)}}")

async def modify_message(user: int, guild_preferences: GuildPreference, message: str, embeds: list[dict] | None) -> tuple[str, list[dict]]:
    embed_list = []
    evaluator = dice.Evaluator()
    fns = (await Database.instance.get_user_preferences(user)).dice_functions
    if fns:
        env = dice.Environment.deserialize(evaluator, fns)
    else:
        env = dice.Environment()
    guild_fns = guild_preferences.dice_functions
    if guild_fns:
        guild_env = dice.Environment.deserialize(evaluator, guild_fns)
    else:
        guild_env = dice.Environment()

    global_environment = global_functions()
    global_environment.mutable = env
    global_environment.immutable = guild_env

    def construct(match: re.Match) -> str:
        def get_global_environment(): return global_environment
        def set_global_environment(ge):
            nonlocal global_environment
            global_environment = ge
        ret, embed = roll_dice(match.group(1), get_global_environment, set_global_environment)
        embed_list.append(embed.to_dict())
        return f"`{ret}`"

    result = block_content_regex.sub(construct, message), embed_list + (embeds or [])
    serialized = env.serialize()
    if serialized != fns:
        await Database.instance.set_user_preferences(user, dice_functions=serialized)
    return result


async def reproxy(old_message: fluxer.Message, bot: fluxer.Bot, old_proxy: Proxy, new_proxy: Proxy):
    contents = old_message.content
    attachments = old_message.attachments
    embeds = old_message.embeds
    parent_message = old_message.referenced_message
    webhook = await get_webhook(old_message.channel_id, bot)
    server_preferences = await Database.instance.get_guild_preferences((await bot.fetch_channel(str(old_message.channel_id))).guild_id)
    await old_message.delete()
    await Database.instance.delete_link_message(old_message.id, old_message.channel_id)
    embeds = [embed for embed in embeds if embed["title"] == "Reply"]
    contents, embeds = await modify_message(new_proxy.owner, server_preferences, contents, embeds)
    m = await send_webhook(webhook, contents, embeds=embeds, username=new_proxy.effective_name, avatar_url=new_proxy.effective_avatar, files=await convert_attachments(attachments), wait=True, message_reference=parent_message)
    await Database.instance.transfer_proxy_usage(old_proxy.id, new_proxy.id)
    await Database.instance.set_autoproxy_last_used_proxy(old_proxy.owner, await get_guild_id_from_channel(bot, old_message.channel_id), new_proxy.id)
    await Database.instance.link_message(m.id, m.channel_id, new_proxy.id)
    logging_channel_id = server_preferences.logging_channel
    if logging_channel_id != 0:
        logging_channel = await bot.fetch_channel(str(logging_channel_id))
        message_link = await mention_message(bot, m)
        embed = fluxer.Embed(
            f"Message Proxy Change",
            f"**Previous Proxy**: {old_proxy.effective_name}\n**New Proxy**: {new_proxy.effective_name}\n**Owner**: <@{new_proxy.owner}> (`{new_proxy.owner}`)\n**Channel**: <#{m.channel_id}> (`{m.channel_id}`)\n**New Message Link**: [jump]({message_link})"
        )
        embed.set_thumbnail(url=new_proxy.effective_avatar)
        await logging_channel.send("", embeds=[embed])


def recover_original_message(message: fluxer.Message) -> str:
    replying = any(embed["title"] == "Reply" for embed in message.embeds)
    if replying:
        pre, old_msg = message.content.split("\n", maxsplit=1)
        return old_msg
    return message.content


async def edit_proxy_message(old_message: fluxer.Message, bot: fluxer.Bot, new_message_contents: str):
    embeds = old_message.embeds
    webhook = await get_webhook(old_message.channel_id, bot)
    proxy = await Database.instance.get_proxy(await Database.instance.get_proxy_id(old_message.id, old_message.channel_id))
    server_preferences = await Database.instance.get_guild_preferences((await bot.fetch_channel(str(old_message.channel_id))).guild_id)
    embeds = [embed for embed in embeds if embed["title"] == "Reply"]
    replying = len(embeds) >= 1
    contents, embeds = await modify_message(proxy.owner, server_preferences, new_message_contents, embeds)
    old_msg = old_message.content
    if replying:
        pre, old_msg = old_message.content.split("\n", maxsplit=1)
        contents = pre + "\n" + contents
    m = await edit_webhook(webhook, bot, old_message, contents, embeds)
    logging_channel_id = server_preferences.logging_channel
    if logging_channel_id != 0:
        logging_channel = await bot.fetch_channel(str(logging_channel_id))
        message_link = await mention_message(bot, m)
        embed = fluxer.Embed(
            f"Message Edit",
            f"**Proxy**: {proxy.effective_name}\n**Owner**: <@{proxy.owner}> (`{proxy.owner}`)\n**Channel**: <#{m.channel_id}> (`{m.channel_id}`)\n**Message Link**: [jump]({message_link})\n**Old Message**:\n{'\n'.join('> ' + line for line in old_msg.split('\n'))}\n**New Message**:\n{'\n'.join('> ' + line for line in new_message_contents.split('\n'))}"
        )
        embed.set_thumbnail(url=proxy.effective_avatar)
        await logging_channel.send("", embeds=[embed])


@TTLCache(1024, 3600).cache_async(["user", "guild"])
async def get_member(bot: fluxer.Bot, guild: int, user: int) -> fluxer.GuildMember:
    return await (await bot.fetch_guild(str(guild))).fetch_member(user)


async def on_user_message(message: fluxer.Message, bot: fluxer.Bot):
    if not message.guild_id:
        return

    if await Database.instance.get_allow_proxy(int(message.channel_id), int(message.guild_id), (await get_member(bot, await get_guild_id_from_channel(bot, message.channel_id), message.author.id)).roles[::-1], message.author.id):
        guild_id = await get_guild_id_from_channel(bot, message.channel_id)
        autoproxy_prefs = await Database.instance.get_autoproxy_preference(message.author.id, guild_id)
        proxied = await get_proxied_messages(message.content, int(message.author.id), autoproxy_prefs)
        if proxied:
            parent = None
            if message.referenced_message is not None:
                channel_id, message_id = message.referenced_message.channel_id, message.referenced_message.id
                parent = await bot.fetch_message(str(channel_id), str(message_id))

            channel = await bot.fetch_channel(str(message.channel_id))
            logging_channel: fluxer.Channel | None | Literal[False] = None

            proxy = None
            msg = None

            for proxy, m in proxied:
                try:
                    try:
                        msg = await send_proxy_message(proxy, m, parent, channel, bot, message.attachments)
                    except fluxer.BadRequest as e:
                        await message.reply(f"Messages could not be proxied! `{e}`")
                        return

                    if msg:
                        await Database.instance.link_message(msg.id, msg.channel_id, proxy.id)

                    if logging_channel is None:
                        server_preferences = await Database.instance.get_guild_preferences(int(message.guild_id))
                        logging_channel_id = server_preferences[1]
                        if logging_channel_id != 0:
                            logging_channel = await bot.fetch_channel(str(logging_channel_id))
                        else:
                            logging_channel = False
                    if logging_channel is not False:
                        if msg:
                            message_link = await mention_message(bot, msg)
                            reply_msg = f"**Replying To**: [message link]({await mention_message(bot, parent)})\n" if parent else ""
                            embed = fluxer.Embed(
                                f"Proxied Message",
                                f"**Proxy**: {proxy.effective_name}\n**Owner**: <@{proxy.owner}> (`{proxy.owner}`)\n**Channel**: <#{message.channel_id}> (`{message.channel_id}`)\n**Message Link**: [jump]({message_link})\n{reply_msg}**Message**:\n{'\n'.join('> ' + line for line in m.split('\n'))}"
                            )
                            embed.set_thumbnail(url=proxy.effective_avatar)
                            await logging_channel.send("", embeds=[embed])

                    if parent:
                        parent = None

                except Exception as e:
                    if not msg:
                        await message.reply(f"Messages could not be proxied! `{e}`")
                        print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                        return

                await Database.instance.use_proxy(proxy.id)

            if proxy:
                await Database.instance.set_autoproxy_last_used_proxy(message.author.id, guild_id, proxy.id)

            await delete_message(message)
