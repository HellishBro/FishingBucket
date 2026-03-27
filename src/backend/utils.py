from datetime import datetime
from io import BytesIO
from typing import Any

from aiohttp import ClientSession
import fluxer
import fluxer.http as fhttp
import expr_dice_roller as dice

from .cache import TTLCache
from .data_reader import DataReader


def format_date(dt: datetime):
    day = dt.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]

    return dt.strftime(f"%b {day}{suffix} %Y")

async def read_file(url: str) -> str:
    async with ClientSession() as session:
        async with session.get(url) as res:
            if res.status != 200:
                return ""
            return await res.text()

async def read_file_blob(url: str) -> bytes:
    async with ClientSession() as session:
        async with session.get(url) as res:
            if res.status != 200:
                return b""
            return await res.read()

async def read_file_json(url: str) -> Any:
    async with ClientSession() as session:
        async with session.get(url) as res:
            if res.status != 200:
                return ""
            return await res.json()

guild_id_cache = TTLCache[int, int](1024, 3600)

async def get_guild_id_from_channel(bot: fluxer.Bot, channel_id: int) -> int:
    if ret := guild_id_cache.get(channel_id): return ret
    gid = (await bot.fetch_channel(str(channel_id))).guild_id
    guild_id_cache.set(channel_id, gid)
    return gid

async def mention_message(bot: fluxer.Bot, message: fluxer.Message) -> str:
    guild_id = message.guild_id
    if not message.guild_id:
        if message.channel_id:
            guild_id = await get_guild_id_from_channel(bot, message.channel_id)
    if guild_id is None:
        guild_id = "@me"

    return f"https://fluxer.app/channels/{guild_id}/{message.channel_id}/{message.id}"

async def compute_base_permissions(member: fluxer.models.GuildMember, guild: fluxer.Guild) -> int:
    ALL = 0xFFFF_FFFF_FFFF_FFFF
    if guild.owner_id == member.user.id:
        return ALL


    roles: list[fluxer.models.Role] = await guild.fetch_roles()

    permissions = [r for r in roles if r.id == guild.id][0].permissions

    for role in member.roles:
        permissions |= [r for r in roles if r.id == role][0].permissions

    if permissions & 0x8 == 0x8:
        return ALL

    return permissions

async def compute_overwrites(base_permissions: int, bot: fluxer.Bot, member: fluxer.models.GuildMember, channel: fluxer.Channel):
    ALL = 0xFFFF_FFFF_FFFF_FFFF
    # ADMINISTRATOR overrides any potential permission overwrites, so there is nothing to do here.
    if base_permissions & 0x8 == 0x8:
        return ALL

    permissions = base_permissions
    overwrites: list[dict] = (await bot._http.request(fhttp.Route("GET", "/channels/{cid}", cid=str(channel.id))))["permission_overwrites"] or []
    overwrite_everyone = [r for r in overwrites if int(r["id"]) == channel.guild_id]  # Find (@everyone) role overwrite and apply it.
    if overwrite_everyone:
        permissions &= ~int(overwrite_everyone[0]["deny"])
        permissions |= int(overwrite_everyone[0]["allow"])

    # Apply role specific overwrites.
    allow = 0x0
    deny = 0x0
    for role_id in member.roles:
        overwrite_role = [r for r in overwrites if int(r["id"]) == role_id]
        if overwrite_role:
            allow |= int(overwrite_role[0]["allow"])
            deny |= int(overwrite_role[0]["deny"])

    permissions &= ~deny
    permissions |= allow

    # Apply member specific overwrite if it exists.
    overwrite_member = [r for r in overwrites if int(r["id"]) == member.user.id]
    if overwrite_member:
        permissions &= ~int(overwrite_member[0]["deny"])
        permissions |= int(overwrite_member[0]["allow"])

    return permissions

async def compute_permissions(member: fluxer.models.GuildMember, bot: fluxer.Bot, channel: fluxer.Channel):
    base_permissions = await compute_base_permissions(member, await bot.fetch_guild(str(channel.guild_id)))
    return await compute_overwrites(base_permissions, bot, member, channel)

async def get_member(guild_id: int, bot: fluxer.Bot, user_id: int) -> fluxer.models.GuildMember:
    return fluxer.models.GuildMember.from_data(await bot._http.request(fhttp.Route("GET", "/guilds/{gid}/members/{uid}", gid=str(guild_id), uid=str(user_id))), bot._http)


async def edit_webhook(webhook: fluxer.Webhook, bot: fluxer.Bot, message: fluxer.Message, new_contents: str, embeds: list[dict] | None) -> fluxer.Message:
    return fluxer.Message.from_data(
        await bot._http.request(fhttp.Route("PATCH", "/webhooks/{wid}/{wtk}/messages/{mid}", wid=webhook.id, wtk=webhook.token, mid=message.id), json={
            "content": new_contents,
            "embeds": embeds or []
        }),
        bot._http
    )

async def convert_attachments(message_attachments: list[fluxer.models.Attachment]) -> list[fluxer.File]:
    parsed_attachments = []
    for attachment in message_attachments:
        parsed_attachments.append(fluxer.File(
            BytesIO(await read_file_blob(attachment.url)),
            filename=attachment.filename
        ))
    return parsed_attachments

def normalize_emojis(text: str) -> str:
    for key, emoji in DataReader.instance["emojis.json"]["forward_map"].items():
        text = text.replace(":" + key + ":", emoji)
    return text

def roll_dice(string: str, get_global_environment, set_global_environment) -> tuple[str, fluxer.Embed]:
    try:
        rep = dice.format_expression(string)[:100]
        try:
            res = dice.evaluate(string, get_global_environment(), True)
            set_global_environment(res.environment)
            if res.value is None:
                embed = fluxer.Embed(rep, f"{res.representation}")
                ret = "no value"
            else:
                embed = fluxer.Embed(rep, f"`{res.representation[:1000]}` = {res.value:g}")
                ret = f"{res.value:g}"
        except ValueError as e:
            embed = fluxer.Embed(rep, f"Error: {e.args[0]}")
            ret = "error"
    except ValueError as e:
        embed = fluxer.Embed(string[:100], f"Error: {e.args[0]}")
        ret = "error"
    return ret, embed