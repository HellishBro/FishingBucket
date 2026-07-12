from collections import Counter

from .generic import hook_command, EarlyExitException
from .specific import get_uid
from .utils import paged_proxy_list
from ..backend.database import Database
from ..backend.models import Proxy
from ..service import Context, Embed


async def get_spotlight_proxies(uid: int, reformat = False) -> list[Proxy]:
    user_settings = await Database.instance.get_user_preferences(uid)
    spotlights = user_settings.spotlight
    proxies: list[Proxy] = []
    for spotlight in spotlights:
        prox = await Database.instance.get_proxy(spotlight)
        if prox:
            proxies.append(prox)

    if reformat and len(spotlights) != len(proxies):
        await Database.instance.set_user_preferences(uid, spotlight=[proxy.id for proxy in proxies])

    return proxies


async def set_proxies(context: Context, uid: int, proxies: list[Proxy]):
    await Database.instance.set_user_preferences(uid, spotlight=[proxy.id for proxy in proxies])
    if proxies:
        await context.reply("", [Embed(
            "Spotlight updated!",
            f"Successfully set your spotlight to **{'**, **'.join(prox.name for prox in proxies)}**!"
        )])
    else:
        await context.reply("", [Embed(
            "Spotlight updated!",
            "Successfully cleared your spotlight!"
        )])

async def ensure_no_dup(context: Context, proxies: list[Proxy]) -> list[Proxy]:
    dup_list = []
    traversed = []
    for prox in proxies:
        if prox in traversed and prox not in dup_list:
            dup_list.append(prox)
        if prox not in traversed:
            traversed.append(prox)
    if dup_list:
        await context.reply(f"Error: proxies cannot appear more than once in spotlight: **{'**, **'.join(prox.name for prox in dup_list)}**")
        raise EarlyExitException()
    return traversed


def setup():
    @hook_command("spotlight list")
    async def _(context: Context):
        uid = await get_uid(context)
        proxies = await get_spotlight_proxies(uid, True)
        channel = await context.get_this_channel()
        await paged_proxy_list(context, proxies, f"Spotlight of {context.author.display_name}", 0, channel.dm)

    @hook_command("spotlight set")
    async def _(context: Context, proxies: list[Proxy]):
        uid = await get_uid(context)
        await set_proxies(context, uid, await ensure_no_dup(context, proxies))

    @hook_command("spotlight clear")
    async def _(context: Context):
        uid = await get_uid(context)
        await set_proxies(context, uid, [])

    @hook_command("spotlight add")
    async def _(context: Context, proxy: Proxy):
        uid = await get_uid(context)
        proxies = await get_spotlight_proxies(uid)
        proxies.append(proxy)
        await set_proxies(context, uid, await ensure_no_dup(context, proxies))

    @hook_command("spotlight pop")
    async def _(context: Context):
        uid = await get_uid(context)
        proxies = await get_spotlight_proxies(uid)
        if len(proxies) == 0:
            await context.reply("Error: you have no proxies in your spotlight!")
        proxies.pop()
        await set_proxies(context, uid, proxies)

    @hook_command("spotlight insert")
    async def _(context: Context, proxy: Proxy, index: int):
        uid = await get_uid(context)
        proxies = await get_spotlight_proxies(uid)
        index_0 = index - 1
        if 0 <= index_0 < len(proxies):
            proxies.insert(index_0, proxy)
            await set_proxies(context, uid, await ensure_no_dup(context, proxies))
        else:
            await context.reply(f"Error: cannot insert into index {index}!")