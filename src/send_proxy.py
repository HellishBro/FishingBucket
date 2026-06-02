import traceback
from typing import Literal

import expr_dice_roller as dice
import re

from .backend.cache import TTLCache
from .backend.config import Config
from .backend.database import Database, GuildPreference, UserAutoproxyPreference, Guild
from .backend.models import Proxy
from .backend.template_utils import Template
from .backend.dice_environments import global_functions
from .backend.utils import convert_attachments, normalize_emojis, roll_dice
from .commands.specific import get_uid
from .service import Platform, Context, Webhook, Attachment, Embed, Channel, Message


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


@TTLCache(2048, 3600).cache_async(["channel_id"])
async def get_webhook(context: Context) -> Webhook:
    webhook = None

    if webhook_id := await Database.instance.get_channel_webhook(context.channel.id, context.platform):
        webhook = await context.get_bot.get_webhook(webhook_id)

    if webhook is None:
        webhook = await context.channel.create_webhook(Config.instance.webhook)
        await Database.instance.put_channel_webhook_link(context.channel.id, webhook.id, context.platform)

    return webhook

async def send_proxy_message(proxy: Proxy, message: str, context: Context, attachments: list[Attachment], mention: bool, do_reply: bool) -> Context:
    webhook: Webhook = await get_webhook(context)

    mention_str = None
    if context.message.reference:
        lnk = await Database.instance.get_message_link(context.message.reference.id, context.channel.id)
        if lnk:
            parent_proxy = await Database.instance.get_proxy(lnk.proxy_id)
            mention_str = f"{parent_proxy.name} (<@{lnk.platform_user}>)"
        else:
            mention_str = context.message.reference.author.mention

    message, embeds = await modify_message(proxy.owner, await Database.instance.get_guild_preferences(Guild(context.guild.id, context.platform)), message, [])

    if context.message.reference and do_reply:
        return await webhook.reply(
            context.message.reference.context, message, proxy.effective_name, proxy.effective_avatar, mention, embeds,
            await convert_attachments(attachments), mention_str
        )

    return await webhook.send(
        message, proxy.effective_name, proxy.effective_avatar, mention, embeds, await convert_attachments(attachments)
    )


block_content_regex = re.compile(r"{{(.+?)}}")

async def modify_message(user: int, guild_preferences: GuildPreference, message: str, embeds: list[Embed]) -> tuple[str, list[Embed]]:
    clean_embeds = [embed for embed in embeds if embed.footer != "dice roll"]

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
        embed_list.append(embed)
        return f"`{ret}`"

    result = block_content_regex.sub(construct, message), embed_list + clean_embeds
    serialized = env.serialize()
    if serialized != fns:
        await Database.instance.set_user_preferences(user, dice_functions=serialized)
    return result


async def reproxy(context: Context, old_proxy: Proxy, new_proxy: Proxy):
    webhook: Webhook = await get_webhook(context)
    fixed_message = await webhook.get_message_data(context)
    contents = fixed_message.content
    attachments = fixed_message.attachments
    embeds = fixed_message.embeds
    parent_message = fixed_message.reference
    guild = Guild(context.channel.guild.id, context.platform)
    server_preferences = await Database.instance.get_guild_preferences(guild)
    print(context.content)
    await context.message.delete()
    await Database.instance.delete_link_message(context.message.id, context.channel.id)
    if parent_message:
        m = await webhook.reply(
            parent_message.context, contents, new_proxy.effective_name, new_proxy.effective_avatar, True, embeds,
            await convert_attachments(attachments), False
        )
    else:
        m = await webhook.send(
            contents, new_proxy.effective_name, new_proxy.effective_avatar, True, embeds, await convert_attachments(attachments)
        )

    await Database.instance.transfer_proxy_usage(old_proxy.id, new_proxy.id)
    await Database.instance.set_autoproxy_last_used_proxy(old_proxy.owner, guild, new_proxy.id)
    await Database.instance.link_message(m.id, context.channel.id, new_proxy.id, context.author.id, context.platform)
    logging_channel_id = server_preferences.logging_channel
    if logging_channel_id != 0:
        logging_channel = await context.get_channel(logging_channel_id)
        embed = Embed(
            f"Message Proxy Change",
            f"**Previous Proxy**: {old_proxy.effective_name}\n**New Proxy**: {new_proxy.effective_name}\n**Owner**: {context.author.mention} (`{context.author.id}`)\n**Channel**: {context.channel.mention} (`{context.channel.id}`)\n**New Message Link**: [jump]({m.message.mention})",
            thumbnail_url=new_proxy.effective_avatar
        )
        await logging_channel.send("", embeds=[embed])


async def edit_proxy_message(old_message: fluxer.Message, bot: fluxer.Bot, new_message_contents: str):
    embeds = old_message.embeds
    webhook = await get_webhook(old_message.channel_id, bot)
    lnk = await Database.instance.get_message_link(old_message.id, old_message.channel_id)
    proxy = await Database.instance.get_proxy(lnk.proxy_id)
    server_preferences = await Database.instance.get_guild_preferences(Guild((await bot.fetch_channel(str(old_message.channel_id))).guild_id, Platform.Fluxer))
    pre, old_msg = recover_original_message(old_message)
    contents, embeds = await modify_message(proxy.owner, server_preferences, new_message_contents, embeds)
    old_msg = old_message.content
    if pre:
        contents = pre + "\n" + contents
    m = await edit_webhook(webhook, bot, old_message, contents, embeds)
    logging_channel_id = server_preferences.logging_channel
    if logging_channel_id != 0:
        logging_channel = await bot.fetch_channel(str(logging_channel_id))
        message_link = await mention_message(bot, m)
        embed = fluxer.Embed(
            f"Message Edit",
            f"**Proxy**: {proxy.effective_name}\n**Owner**: <@{lnk.platform_user}> (`{lnk.platform_user}`)\n**Channel**: <#{m.channel_id}> (`{m.channel_id}`)\n**Message Link**: [jump]({message_link})\n**Old Message**:\n{'\n'.join('> ' + line for line in old_msg.split('\n'))}\n**New Message**:\n{'\n'.join('> ' + line for line in new_message_contents.split('\n'))}"
        )
        embed.set_thumbnail(url=proxy.effective_avatar)
        await logging_channel.send("", embeds=[embed])


@TTLCache(1024, 3600).cache_async(["user", "guild"])
async def get_member(bot: fluxer.Bot, guild: int, user: int) -> fluxer.GuildMember:
    return await (await bot.fetch_guild(str(guild))).fetch_member(user)


async def on_user_message(context: Context):
    if context.channel.dm:
        return

    owner = await get_uid(context)
    guild = Guild(context.guild.id, context.platform)

    roles = await (await context.get_member(context.author.id)).roles()

    if await Database.instance.get_allow_proxy(
            context.channel.id,
            guild,
            [role.id for role in roles][::-1],
            context.author.id
    ):
        autoproxy_prefs = await Database.instance.get_autoproxy_preference(owner, guild)
        proxied = await get_proxied_messages(context.content, owner, autoproxy_prefs)
        if proxied:
            logging_channel: Channel | None | Literal[False] = None
            proxy = None
            ctx = None

            for i, (proxy, m) in enumerate(proxied):
                try:
                    try:
                        ctx = await send_proxy_message(proxy, m, context, context.message.attachments, True, i == 0)
                    except Exception as e:
                        await context.reply(f"Messages could not be proxied! `{e}`")
                        return

                    if ctx:
                        await Database.instance.link_message(ctx.id, ctx.message.channel_id, proxy.id, context.author.id, context.platform)

                    if logging_channel is None:
                        server_preferences: GuildPreference = await Database.instance.get_guild_preferences(guild)
                        logging_channel_id = server_preferences.logging_channel
                        if logging_channel_id != 0:
                            logging_channel = await context.get_channel(logging_channel_id)
                        else:
                            logging_channel = False

                    if logging_channel:
                        if ctx:
                            message_link = ctx.message.mention
                            reply_msg = f"**Replying To**: [message link]({context.message.reference.mention})\n" if context.message.reference and i == 0 else ""
                            embed = Embed(
                                f"Proxied Message",
                                f"**Proxy**: {proxy.effective_name}\n**Owner**: {context.author.mention} (`{context.author.id}`)\n**Channel**: {context.channel.mention} (`{context.channel.id}`)\n**Message Link**: [jump]({message_link})\n{reply_msg}**Message**:\n{'\n'.join('> ' + line for line in m.split('\n'))}",
                                thumbnail_url=proxy.effective_avatar
                            )
                            await logging_channel.send("", [embed])

                except Exception as e:
                    print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                    if not ctx:
                        await context.reply(f"Messages could not be proxied! `{e}`")
                        return

                await Database.instance.use_proxy(proxy.id)

            if proxy:
                await Database.instance.set_autoproxy_last_used_proxy(owner, guild, proxy.id)

            await context.message.delete()
